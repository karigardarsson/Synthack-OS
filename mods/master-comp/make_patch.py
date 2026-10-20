"""Genera mods/master-comp/patch.json: compressore sui VCA del master (vedi README.md).

    python mods/master-comp/make_patch.py [--thr 0x4000 --atk 0x1800 --rel 0x2000 --mup 0x2000 --rat 4]

Valori di default delle manopole (0..0x7F00) e ratio di default quando acceso (1..8).
Tabelle e costanti da dsp.py (formule, nessun dato Elektron). Richiede binutils m68k in WSL.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import shutil
import struct
import subprocess
import sys
import tempfile
import importlib.util
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
sys.path[:0] = [str(REPO / "tools" / "unpack"), str(REPO / "tools" / "build"), str(HERE)]
import eft  # noqa: E402
import modarea_layout  # noqa: E402
from dsp import ATTACK, C_OCT, EXP_T, LOG_T, RATIO, RELEASE  # noqa: E402
_vp = importlib.util.spec_from_file_location("vparams_make_patch", REPO / "mods" / "vparams" / "make_patch.py")
vparams = importlib.util.module_from_spec(_vp)
_vp.loader.exec_module(vparams)

RAT_NAMES = ["OFF", "1.5:1", "2:1", "3:1", "4:1", "6:1", "8:1", "16:1", "20:1"]


def unit_tables() -> dict[str, list[str]]:
    """Testi con le unita' reali per ogni indice 0..127 (valore >> 8), dalle formule di dsp.py."""
    def ms(t: float) -> str:
        if t < 10:
            return f"{t:.1f}ms"
        if t < 1000:
            return f"{round(t)}ms"
        return f"{t / 1000:.1f}s"

    def db(x: float, plus: bool = False) -> str:
        r = round(x)
        return f"{'+' if plus and r > 0 else ''}{r}dB"

    tabs = {}
    tabs["thr"] = [db(60 * (i << 8) / 32768 - 60) for i in range(128)]
    tabs["atk"] = [ms(0.1 + 99.9 * (i / 127) ** 2) for i in range(128)]
    tabs["rel"] = [ms(10 + 1990 * (i / 127) ** 2.5) for i in range(128)]
    tabs["mup"] = [db(24.08 * (i << 8) / 32768, plus=True) for i in range(128)]
    tabs["rat"] = [RAT_NAMES[min(8, ((i << 8) + 0xFE0 // 2) // 0xFE0)] for i in range(128)]
    tabs["gr"] = [db(-18 * (0x7F00 - (i << 8)) / 0x7F00) for i in range(128)]   # barra piena = 0 dB
    for k, v in tabs.items():
        assert all(len(t) <= 5 for t in v), (k, max(v, key=len))
    return tabs


def fmt_include() -> str:
    out = []
    for k, texts in unit_tables().items():
        out.append(f"t_{k}:")
        for t in texts:
            b = t.encode("ascii").ljust(6, b"\x00")
            out.append("        .byte   " + ", ".join(str(x) for x in b))
    return "\n".join(out) + "\n"

LOAD = 0x4000_0400
# area mod (mods/modarea, tools/build/modarea_layout.py): offset 0, byte accodati alla sezione 3
MODAREA_RAM, MODAREA_IMG, MODAREA_SIZE = modarea_layout.RAM, modarea_layout.IMG, 0x2000
CODE_BASE = MODAREA_RAM + 0x0000        # offset 0 dell'area mod
FREE_END = MODAREA_RAM + MODAREA_SIZE
UI_BASE, UI_END = MODAREA_RAM + 0x6300, MODAREA_RAM + 0x7000
DRAW_HOOK, DRAW_ORIG = 0x4003_A244, "4fefffb048d7"  # generic SourcePage 8-slot draw prologue
CFLAGS = "-mcpu=54418 -O2 -ffreestanding -fno-builtin -nostdlib -fno-pic -fno-common -Wall -Wextra"
HOOK, HOOK_END = 0x4009_053E, 0x4009_0562
HOOK_ORIG = "0c810000ffff6f06223c0000ffff374100460c830000ffff6f06263c0000ffff37430048"

# ---- interfaccia: id logici liberi (vedi comp.S e docs/)
# Gli id "nascosti" usati fino alla v0.8 (144, 122, 91, 101, 127, 59, 115) sono quasi tutti ALIAS che
# l'OS mette sulle pagine in certi modi: 59 = GAIN al posto di RESO nei filtri EQ dei track, 122 = REV
# sulla pagina 2 del MIXER, 91/101 = SLEW al posto di SPH degli LFO, 127 = PAN al posto di BAL. Con le
# nostre funzioni al loro posto quelle manopole mostravano il compressore e non funzionavano.
# 262..268 are native MIDI CC Select descriptors on Syntakt. They are borrowed only while the
# active SourcePage belongs to the FX track, then their captured MIDI state is restored.
DESC = 0x4022_D59C                      # descrittori: 52 B, indice = id logico
PARAMS = [  # (nome breve, nome lungo, id, massimo)
    ("THR", "Comp Threshold", 262, 0x7F00),
    ("ATK", "Comp Attack", 263, 0x7F00),
    ("REL", "Comp Release", 264, 0x7F00),
    ("MUP", "Comp Makeup", 265, 0x7F00),
    ("RAT", "Comp Ratio", 266, 0x7F00),        # 9 posizioni: 0 = OFF, 1..8 = 1.5..20:1
    ("GR", "Gain Reduction", 267, 0x7F00),     # misuratore, sola lettura
    ("COMP", "Compressor On/Off", 268, 0x100),  # interruttore
]
# agganci alle funzioni centrali dei parametri di kit: (indirizzo, byte originali, simbolo)
VP_SLOT0 = 0                            # posti nella tabella di vparams: 0..6
# inizializzatore degli oggetti per-parametro (indirizzi 1.41): ai nuovi id lo stesso aspetto che
# avevano gli id vecchi con le correzioni della v0.8. +4 prototipo del valore: qui d3 = 0x401D6B44
# (come 144/91/101), d4 = 0x401D6B34 (come 122/127/59), d5 = 0x401D6B74 (come 115). Il tipo (+0, passo
# dell'encoder: 0, 8 come 122/127, 12 interruttore) lo scrive comp_init.
INIT_FIX = [(0x4018_F750, "2f05", "2f03", "id 262 (THR) +4: prototipo come 144"),
            (0x4018_F776, "41b9d8b0", "41b9dcd0", "id 262 (THR) +36: manopola come 144"),
            (0x4018_F7AA, "2f05", "2f04", "id 263 (ATK) +4: prototipo come 122"),
            (0x4018_F7CA, "41b9d8b0", "41b9dc00", "id 263 (ATK) +36: come 122"),
            (0x4018_F7EA, "41b9d670", "41b9d5d0", "id 263 (ATK) +68: barra come 122"),
            (0x4018_F7FA, "2f05", "2f03", "id 264 (REL) +4: prototipo come 91"),
            (0x4018_F81A, "41b9d8b0", "41b9dcd0", "id 264 (REL) +36: manopola come 91"),
            (0x4018_F84A, "2f05", "2f03", "id 265 (MUP) +4: prototipo come 101"),
            (0x4018_F86E, "41b9d8b0", "41b9dcd0", "id 265 (MUP) +36: manopola come 101"),
            (0x4018_F89A, "2f05", "2f04", "id 266 (RAT) +4: prototipo come 125/126"),
            (0x4018_F8BE, "41b9d8b0", "41b9dc00", "id 266 (RAT) +36: come 125/126"),
            (0x4018_F8DA, "41b9d670", "41b9d5d0", "id 266 (RAT) +68: barra"),
            (0x4018_F8EE, "2f05", "2f04", "id 267 (GR) +4: prototipo come 59"),
            (0x4018_F914, "41b9d8b0", "41b9dc00", "id 267 (GR) +36: come IN LR"),
            (0x4018_F934, "41b9d670", "41b9d5d0", "id 267 (GR) +68: barra come IN LR"),
            (0x4018_F966, "41b9d8b0", "41b9d9f0", "id 268 (COMP) +36: come 115"),
            (0x4018_F986, "41b9d670", "41b9d680", "id 268 (COMP) +68: come 115")]
TYPES = {"THR": 0, "ATK": 8, "REL": 0, "MUP": 0, "RAT": 8, "GR": 0, "COMP": 12}   # +0 degli oggetti
RAT_STEP = 0xFE0
PAGE_HOOK, PAGE_ORIG = 0x4019_5156, "42b941b9f968"      # clr.l 0x41B9F968 (ultima casella vuota, all'avvio)
WSL_BINUTILS = "~/tools/m68k/root"


def sha(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def wsl(cmd: str) -> str:
    r = subprocess.run(["wsl.exe", "-e", "bash", "-lc", cmd], capture_output=True, text=True)
    if r.returncode:
        raise SystemExit(f"comando WSL fallito:\n{cmd}\n{r.stderr}")
    return r.stdout


def build_blob(defs: dict[str, int], incs: dict[str, str]) -> tuple[bytes, dict[str, int], list[int], str]:
    with tempfile.TemporaryDirectory(prefix="mcomp-") as tmp:
        tmp = Path(tmp)
        shutil.copy(HERE / "comp.S", tmp / "comp.S")
        for name, text in incs.items():
            (tmp / name).write_text(text, encoding="ascii")
        w = eft.to_wsl_path(tmp)
        bu = f"R={WSL_BINUTILS}; export LD_LIBRARY_PATH=$R/usr/lib/x86_64-linux-gnu; cd {w}; "
        sym = " ".join(f"--defsym {k}={v & 0xFFFFFFFF}" for k, v in defs.items())
        wsl(bu + f"$R/usr/bin/m68k-linux-gnu-as -mcpu=54418 {sym} comp.S -o c.o")
        wsl(bu + f"$R/usr/bin/m68k-linux-gnu-ld -N -Ttext={CODE_BASE:#x} -o c.elf c.o")
        wsl(bu + "$R/usr/bin/m68k-linux-gnu-objcopy -O binary c.elf c.bin")
        syms = {}
        for line in wsl(bu + "$R/usr/bin/m68k-linux-gnu-nm c.elf").splitlines():
            parts = line.split()
            if len(parts) == 3:
                syms[parts[2]] = int(parts[0], 16)
        dis = wsl(bu + "$R/usr/bin/m68k-linux-gnu-objdump -d -m m68k:isa-c:emac c.elf")
        blob = (tmp / "c.bin").read_bytes()
    emac = []
    for m in re.finditer(r"^\s*([0-9a-f]+):\s+(?:[0-9a-f]{4} ?)+\s+(\S+)\s*(.*)$", dis, re.M):
        if re.match(r"^(mac[lw]|msac[lw]|movclrl)$", m[2]) or re.search(r"%(acc|macsr|mask)", m[3]):
            emac.append(int(m[1], 16))
    return blob, syms, emac, dis

def build_ui_blob(defs: dict[str, int], primary_syms: dict[str, int]) -> tuple[bytes, dict[str, int], str]:
    """Build the context-local compressor UI helper in the FM4-compatible +0x6300 gap."""
    with tempfile.TemporaryDirectory(prefix="mcomp-ui-") as tmp:
        tmp = Path(tmp)
        shutil.copy(HERE / "comp_ui.c", tmp / "comp_ui.c")
        shutil.copy(HERE / "comp_ui.S", tmp / "comp_ui.S")
        w = eft.to_wsl_path(tmp)
        bu = f"R={WSL_BINUTILS}; export LD_LIBRARY_PATH=$R/usr/lib/x86_64-linux-gnu; cd {w}; "
        gcc = "$R/usr/bin/m68k-linux-gnu-gcc-13 -B$R/usr/libexec/gcc/m68k-linux-gnu/13/ -B$R/usr/bin/m68k-linux-gnu-"
        names = [f"n_{n.lower()}_{kind}" for n, _, _, _ in PARAMS for kind in ("s", "l")]
        missing = [name for name in names + ["comp_init"] if name not in primary_syms]
        if missing:
            raise SystemExit("missing compressor UI symbols: " + ", ".join(missing))
        macros = [f"-DCOMP_INIT={primary_syms['comp_init']:#x}"]
        macros += [f"-D{k}={v:#x}" for k, v in defs.items() if k.startswith("D_")]
        macros += [f"-D{name.upper()}={primary_syms[name]:#x}" for name in names]
        warn = wsl(bu + f"{gcc} {CFLAGS} {' '.join(macros)} -c comp_ui.c -o ui.o")
        if "warning" in warn:
            raise SystemExit(warn)
        wsl(bu + "$R/usr/bin/m68k-linux-gnu-as -mcpu=54418 comp_ui.S -o ui_s.o")
        wsl(bu + f"$R/usr/bin/m68k-linux-gnu-ld -N -Ttext={UI_BASE:#x} -e comp_draw_hook -o ui.elf ui_s.o ui.o")
        undef = wsl(bu + "$R/usr/bin/m68k-linux-gnu-nm -u ui.elf").strip()
        if undef:
            raise SystemExit("unexpected compressor UI undefined symbols: " + undef)
        heads = wsl(bu + "$R/usr/bin/m68k-linux-gnu-objdump -h ui.elf")
        for name, size in re.findall(r"^\s*\d+\s+(\.\S+)\s+([0-9a-f]+)", heads, re.M):
            if name in (".bss", ".sbss") and int(size, 16):
                raise SystemExit("compressor UI helper must not use BSS")
        wsl(bu + "$R/usr/bin/m68k-linux-gnu-objcopy -O binary -j .text -j .rodata -j .data ui.elf ui.bin")
        syms = {}
        for line in wsl(bu + "$R/usr/bin/m68k-linux-gnu-nm ui.elf").splitlines():
            parts = line.split()
            if len(parts) == 3:
                syms[parts[2]] = int(parts[0], 16)
        dis = wsl(bu + "$R/usr/bin/m68k-linux-gnu-objdump -d -m m68k:isa-c:emac ui.elf")
        blob = (tmp / "ui.bin").read_bytes()
    return blob, syms, dis


def main() -> None:
    ap = argparse.ArgumentParser()
    for k, v in (("thr", 0x4000), ("atk", 0x1800), ("rel", 0x2000), ("mup", 0x2000)):
        ap.add_argument(f"--{k}", type=lambda s: int(s, 0), default=v)
    ap.add_argument("--rat", type=int, default=4, help="ratio di default quando acceso (1..8)")
    ap.add_argument("--no-drive-knob", action="store_true",
                    help="non copiare il disegno della manopola di DRIVE su THR..MUP")
    a = ap.parse_args()
    params = [a.thr, a.atk, a.rel, a.mup, a.rat]

    # salvataggio: 4 parole = valore XOR default (15 bit) + un bit di RAT ciascuna; zero = default, spento
    defs = {"C_OCT": C_OCT, "D_THR": a.thr, "D_ATK": a.atk, "D_REL": a.rel, "D_MUP": a.mup,
            "D_RAT": a.rat * RAT_STEP, "GFX_ON": 0 if a.no_drive_knob else 1}
    defs.update({f"ID_{n}": i for n, _, i, _ in PARAMS})
    defs.update({f"TY_{n}": TYPES[n] for n, _, _, _ in PARAMS})
    nl = "\n"
    tables = "".join(f"        .long   {', '.join(str(v) for v in tab[k:k + 8])}{nl}"
                     for tab in (ATTACK, RELEASE, RATIO) for k in range(0, len(tab), 8))
    names = "".join(f'n_{n.lower()}_s: .asciz "{n}"{nl}n_{n.lower()}_l: .asciz "{ln}"{nl}'
                    for n, ln, _, _ in PARAMS)
    incs = {"dt_tables.inc": tables, "names.inc": names, "fmt_tables.inc": fmt_include()}
    defs.update({f"LOG_T{i}": v for i, v in enumerate(LOG_T)})
    defs.update({f"EXP_T{i}": v for i, v in enumerate(EXP_T)})

    stock = REPO / "firmware" / "Syntakt_OS1.41.syx"
    sec3 = eft.unpack(stock, REPO / "unpacked" / stock.stem, ids=[3])[3].read_bytes()
    blob, syms, emac, dis = build_blob(defs, incs)
    ui_blob, ui_syms, ui_dis = build_ui_blob(defs, syms)
    if UI_BASE + len(ui_blob) > UI_END:
        raise SystemExit(f"compressor UI helper does not fit: {len(ui_blob)} B")
    end = CODE_BASE + len(blob)
    if end > FREE_END:
        raise SystemExit(f"non ci sta: {len(blob)} B (liberi {FREE_END - CODE_BASE})")
    site = sec3[HOOK - LOAD:HOOK_END - LOAD]
    if site.hex() != HOOK_ORIG:
        raise SystemExit("i byte del punto d'aggancio non sono quelli attesi")
    tramp = struct.pack(">HIHH", 0x4EB9, syms["comp_hook"], 0x6000, HOOK_END - (HOOK + 8))

    def fixed(addr: int, new: bytes, what: str, expect: str | None = None) -> dict:
        old = sec3[addr - LOAD:addr - LOAD + len(new)]
        if expect is not None and old.hex() != expect:
            raise SystemExit(f"{addr:#x}: byte inattesi {old.hex()} (attesi {expect})")
        return {"section": 3, "addr": f"{addr:#010X}", "len": len(new),
                "expect_sha256": sha(old), "hex": new.hex(), "what": what}

    ui = []
    for slot, (n, _, i, _) in enumerate(PARAMS):      # parametri virtuali (mods/vparams), posti 0..6
        ui.append(vparams.entry(VP_SLOT0 + slot, i, syms["get_hook"], syms["set_hook"], f"master-comp {n}", ui_syms["comp_active_context"]))
    defaults = {"THR": a.thr, "ATK": a.atk, "REL": a.rel, "MUP": a.mup, "RAT": a.rat * RAT_STEP, "GR": 0, "COMP": 0x100}
    ui.append(fixed(DRAW_HOOK, struct.pack(">HI", 0x4EF9, ui_syms["comp_draw_hook"]),
                    "generic SourcePage draw: scope compressor descriptors and slots to the FX context", DRAW_ORIG))

    primary_symbols = {
        "comp_hook", "scale", "k_const", "k_state", "k_logt", "k_expt", "k_fallback",
        "k_ids", "k_dt", "k_off", "kit_hook", "get_hook", "set_hook", "convert",
        "comp_page_stub", "changed", "k_seen", "stor", "getv", "setv", "getr", "setr", "tab_fmt", "null_mgr",
        "comp_init", "k_fmts", "meter", "meter_val", "k_meter", "k_tick", "k_shown", "k_on",
        "n_thr_s", "n_thr_l", "n_atk_s", "n_atk_l", "n_rel_s", "n_rel_l", "n_mup_s", "n_mup_l",
        "n_rat_s", "n_rat_l", "n_gr_s", "n_gr_l", "n_comp_s", "n_comp_l",
    }
    symbols = {k: f"{v:#010x}" for k, v in sorted(syms.items()) if k in primary_symbols}
    symbols.update({k: f"{v:#010x}" for k, v in ui_syms.items()
                    if k in ("comp_draw_hook", "comp_active_context", "comp_ui_update")})

    spec = {
        "name": "master-comp", "os": "1.41", "requires": ["modarea", "vparams"],
        "description": "Compressore sul master analogico (VCA del master) con l'algoritmo del "
                       "compressore in stile Digitakt; manopole THR ATK REL MUP RAT (0 = OFF) e misuratore GR "
                       "sulla pagina SYN della FX track; valori salvati nel kit del pattern (o globali con "
                       "SYN global). Valori di partenza " +
                       " ".join(f"{k.upper()}={getattr(a, k):#06x}" for k in ("thr", "atk", "rel", "mup")) +
                       f" RAT={a.rat}",
        "generated_by": "mods/master-comp/make_patch.py",
        "params": [f"{v:#06x}" for v in params],
        "storage": {"kit_block": "L2+70 (puntatore 0x800030BC)", "global_block": "0x41B9D3B0",
                    "word_offsets": [12, 14, 2, 8]},
        "symbols": symbols,
        "emac_sites": [f"{x:#010x}" for x in emac],
        "patches": [
            {"section": 3, "addr": f"{MODAREA_IMG + CODE_BASE - MODAREA_RAM:#010X}", "len": len(blob),
             "append": True, "hex": blob.hex(), "ram": f"{CODE_BASE:#010x}",
             "what": "(area mod) routine del compressore + costanti del preset + stato + tabelline"},
            {"section": 3, "addr": f"{MODAREA_IMG + UI_BASE - MODAREA_RAM:#010X}", "len": len(ui_blob),
             "append": True, "hex": ui_blob.hex(), "ram": f"{UI_BASE:#010x}",
             "what": "(area mod +0x6300) scoped compressor UI ownership helper"},
            {"section": 3, "addr": f"{HOOK:#010X}", "len": len(tramp),
             "expect_sha256": sha(sec3[HOOK - LOAD:HOOK - LOAD + len(tramp)]), "hex": tramp.hex(),
             "what": "trampolino: jsr comp_hook ; bra.w 0x40090562 (sostituisce limite e scrittura dei CV del master)"},
        ] + ui,
    }
    (HERE / "patch.json").write_text(json.dumps(spec, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    (REPO / "out" / "master-comp").mkdir(parents=True, exist_ok=True)
    (REPO / "out" / "master-comp" / "comp.lst").write_text(dis, encoding="utf-8")
    print(f"patch.json: {len(blob)} B in area mod a {CODE_BASE:#x}..{end:#x} (liberi ancora {FREE_END - end} B), "
          f"{len(emac)} istruzioni EMAC; trampolino {tramp.hex()}")


if __name__ == "__main__":
    main()
