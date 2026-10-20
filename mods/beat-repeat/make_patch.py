"""Mod beat-repeat: costruisce patch.json da br.c.

- compila br.c per ColdFire e lo collega nell'area mod a +0x4000;
- aggancia l'avanzamento degli step del sequencer (0x4008D152), i tasti di retrig 13-16 di KeyboardView
  (0x4002EA92) e il dispatcher degli eventi (0x4000B420);
- RPT1 and RPT2 reuse MIDI ids 269 and 124 only in the FX TRIG context.
  A scoped helper captures and restores descriptors, objects, page slots, and vparams routing outside that context.

    python mods/beat-repeat/make_patch.py
"""

from __future__ import annotations

import hashlib
import importlib.util
import json
import re
import shutil
import struct
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
sys.path[:0] = [str(REPO / "tools" / "unpack"), str(REPO / "tools" / "build")]
import eft  # noqa: E402
import modarea_layout  # noqa: E402

_vp = importlib.util.spec_from_file_location("vparams_make_patch", REPO / "mods" / "vparams" / "make_patch.py")
vparams = importlib.util.module_from_spec(_vp)
_vp.loader.exec_module(vparams)

LOAD = 0x4000_0400
MODAREA_RAM, MODAREA_IMG = modarea_layout.RAM, modarea_layout.IMG
CODE_BASE, CODE_END = MODAREA_RAM + 0x4000, MODAREA_RAM + 0x5000
UI_BASE, UI_END = MODAREA_RAM + 0x6900, MODAREA_RAM + 0x7E00
TOOLS = "~/tools/m68k/root"
CFLAGS = "-mcpu=54418 -O2 -ffreestanding -fno-builtin -nostdlib -fno-pic -fno-common -Wall -Wextra"
VP_SLOT = 7                             # posti 7 e 8 della tabella di vparams
DESC = 0x4022_D59C                      # descrittori dei parametri: 52 B, indice = id
NO_STYLE = 0x41B9_FA68                 # +68 dell'id 0: std::function vuota (nessuno stile, come LFO MODE)
STEP_HOOK, STEP_ORIG = 0x4008_D152, "5283528e528d"      # addq d3 ; addq a6 ; addq a5
KBD_HOOK, KBD_ORIG = 0x4002_EA92, "7223b2806c00010e"    # moveq #35,d1 ; cmp.l d0,d1 ; bge.w 0x4002EBA6
EV_HOOK, EV_ORIG = 0x4000_B420, "4eb94000839e"          # jsr 0x4000839e (dispatcher degli eventi)
PAGE_HOOK, PAGE_ORIG = 0x4019_50F0, "42b941b9f928"      # clr.l 0x41B9F928 (pagina TRIG della FX track)
# (id, nome, default, operandi dei prototipi dell'oggetto: +20 formattatore, +36 grafica, +68 stile
#  con i valori originali, poi le correzioni per farli comportare come LFO MODE (93): valore discreto)
RPTS = [
    (269, "1", 0x000, {20: (0x4018_F9AA, "41b9dfd0"), 36: (0x4018_F9BC, "41b9d8b0"), 68: (0x4018_F9D8, "41b9d670")},
     [(0x4018_F99E, "7201", "7200", "id 269 +0: tipo 1 -> 0 (come 93); +4 e' gia' il prototipo discreto (d5)")]),
    (124, "2", 0x100, {20: (0x4018_C3DE, "41b9de90"), 36: (0x4018_C3EC, "41b9d9f0"), 68: (0x4018_C40C, "41b9d680")},
     [(0x4018_C3D2, "720c", "7200", "id 124 +0: tipo 12 -> 0 (come 93)")]),
]


def sha(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def wsl(cmd: str) -> str:
    r = subprocess.run(["wsl.exe", "-e", "bash", "-lc", cmd], capture_output=True, text=True)
    if r.returncode:
        raise SystemExit(f"comando WSL fallito:\n{cmd}\n{r.stderr}")
    return r.stdout + r.stderr


def build_blob() -> tuple[bytes, dict[str, int], str]:
    with tempfile.TemporaryDirectory(prefix="br-") as tmp:
        tmp = Path(tmp)
        shutil.copy(HERE / "br.c", tmp / "br.c")
        w = eft.to_wsl_path(tmp)
        env = f"R={TOOLS}; export LD_LIBRARY_PATH=$R/usr/lib/x86_64-linux-gnu; cd {w}; "
        gcc = "$R/usr/bin/m68k-linux-gnu-gcc-13 -B$R/usr/libexec/gcc/m68k-linux-gnu/13/ -B$R/usr/bin/m68k-linux-gnu-"
        warn = wsl(env + f"{gcc} {CFLAGS} -c br.c -o br.o")
        if "warning" in warn:
            raise SystemExit(warn)
        wsl(env + f"$R/usr/bin/m68k-linux-gnu-ld -N -Ttext={CODE_BASE:#x} -e br_step -o br.elf br.o")
        undef = wsl(env + "$R/usr/bin/m68k-linux-gnu-nm -u br.elf").strip()
        if undef:
            raise SystemExit(f"simboli esterni non permessi (libgcc?): {undef}")
        heads = wsl(env + "$R/usr/bin/m68k-linux-gnu-objdump -h br.elf")
        for name, size in re.findall(r"^\s*\d+\s+(\.\S+)\s+([0-9a-f]+)", heads, re.M):
            if name in (".bss", ".sbss") and int(size, 16):
                raise SystemExit("br.c non deve avere variabili in .bss (l'area mod e' copiata, non azzerata)")
        wsl(env + "$R/usr/bin/m68k-linux-gnu-objcopy -O binary -j .text -j .rodata -j .data br.elf br.bin")
        syms = {}
        for line in wsl(env + "$R/usr/bin/m68k-linux-gnu-nm br.elf").splitlines():
            parts = line.split()
            if len(parts) == 3:
                syms[parts[2]] = int(parts[0], 16)
        dis = wsl(env + "$R/usr/bin/m68k-linux-gnu-objdump -d -m m68k:isa-c:emac br.elf")
        blob = (tmp / "br.bin").read_bytes()
    return blob, syms, dis


def build_ui_blob(primary_syms: dict[str, int]) -> tuple[bytes, dict[str, int]]:
    """Build the Beat Repeat UI scope helper in the FM4-compatible +0x6900 gap."""
    with tempfile.TemporaryDirectory(prefix="br-ui-") as tmp:
        tmp = Path(tmp)
        shutil.copy(HERE / "br_ui.c", tmp / "br_ui.c")
        w = eft.to_wsl_path(tmp)
        env = f"R={TOOLS}; export LD_LIBRARY_PATH=$R/usr/lib/x86_64-linux-gnu; cd {w}; "
        gcc = "$R/usr/bin/m68k-linux-gnu-gcc-13 -B$R/usr/libexec/gcc/m68k-linux-gnu/13/ -B$R/usr/bin/m68k-linux-gnu-"
        names = ("br_proto", "br_gfx_proto", "br_name1_s", "br_name1_l", "br_name2_s", "br_name2_l")
        missing = [name for name in names if name not in primary_syms]
        if missing:
            raise SystemExit("missing Beat Repeat UI symbols: " + ", ".join(missing))
        macros = " ".join(f"-D{name.upper()}={primary_syms[name]:#x}" for name in names)
        warn = wsl(env + f"{gcc} {CFLAGS} {macros} -c br_ui.c -o ui.o")
        if "warning" in warn:
            raise SystemExit(warn)
        wsl(env + f"$R/usr/bin/m68k-linux-gnu-ld -N -Ttext={UI_BASE:#x} -e br_active_context -o ui.elf ui.o")
        undef = wsl(env + "$R/usr/bin/m68k-linux-gnu-nm -u ui.elf").strip()
        if undef:
            raise SystemExit("unexpected Beat Repeat UI undefined symbols: " + undef)
        heads = wsl(env + "$R/usr/bin/m68k-linux-gnu-objdump -h ui.elf")
        for name, size in re.findall(r"^\s*\d+\s+(\.\S+)\s+([0-9a-f]+)", heads, re.M):
            if name in (".bss", ".sbss") and int(size, 16):
                raise SystemExit("Beat Repeat UI helper must not use BSS")
        wsl(env + "$R/usr/bin/m68k-linux-gnu-objcopy -O binary -j .text -j .rodata -j .data ui.elf ui.bin")
        syms = {}
        for line in wsl(env + "$R/usr/bin/m68k-linux-gnu-nm ui.elf").splitlines():
            parts = line.split()
            if len(parts) == 3:
                syms[parts[2]] = int(parts[0], 16)
        blob = (tmp / "ui.bin").read_bytes()
    return blob, syms


def main() -> None:
    stock = REPO / "firmware" / "Syntakt_OS1.41.syx"
    sec3 = eft.unpack(stock, REPO / "unpacked" / stock.stem, ids=[3])[3].read_bytes()
    blob, syms, dis = build_blob()
    ui_blob, ui_syms = build_ui_blob(syms)
    if UI_BASE + len(ui_blob) > UI_END:
        raise SystemExit(f"Beat Repeat UI helper does not fit: {len(ui_blob)} B")
    if CODE_BASE + len(blob) > CODE_END:
        raise SystemExit(f"non ci sta: {len(blob)} B")
    if re.search(r"\b(mac|msac|movclr)\w*\b|%acc|%macsr", dis):
        raise SystemExit("br.c non deve usare l'EMAC")

    def fixed(addr: int, new: bytes, what: str, expect: str | None = None) -> dict:
        old = sec3[addr - LOAD:addr - LOAD + len(new)]
        if expect is not None and old.hex() != expect:
            raise SystemExit(f"{addr:#x}: byte inattesi {old.hex()} (attesi {expect})")
        return {"section": 3, "addr": f"{addr:#010X}", "len": len(new), "expect_sha256": sha(old),
                "hex": new.hex(), "what": what}

    jsr = lambda sym: struct.pack(">HI", 0x4EB9, syms[sym])
    jmp = lambda sym: struct.pack(">HI", 0x4EF9, syms[sym])
    patches = [
        {"section": 3, "addr": f"{MODAREA_IMG + CODE_BASE - MODAREA_RAM:#010X}", "len": len(blob),
         "append": True, "hex": blob.hex(), "ram": f"{CODE_BASE:#010x}", "what": "(area mod) br.c"},
        {"section": 3, "addr": f"{MODAREA_IMG + UI_BASE - MODAREA_RAM:#010X}", "len": len(ui_blob),
         "append": True, "hex": ui_blob.hex(), "ram": f"{UI_BASE:#010x}",
         "what": "(area mod +0x6900) scoped Beat Repeat UI ownership helper"},
        fixed(STEP_HOOK, jsr("br_step_hook"), "avanzamento degli step: jsr br_step_hook", STEP_ORIG),
        fixed(KBD_HOOK, jmp("br_kbd_hook") + bytes.fromhex("4e71"),
              "tasti di retrig 13-16 (KeyboardView): jmp br_kbd_hook ; nop", KBD_ORIG),
        fixed(EV_HOOK, jsr("br_ev_hook"), "dispatcher degli eventi: jsr br_ev_hook (rilascio)", EV_ORIG),
    ]
    want = {20: syms["br_proto"], 36: syms["br_gfx_proto"], 68: NO_STYLE}
    for n, (pid, tag, default, ops, extra) in enumerate(RPTS):
        r = DESC + 52 * pid
        patches.append(vparams.entry(VP_SLOT + n, pid, syms["br_get"], syms["br_set"], f"beat-repeat RPT{tag}", ui_syms["br_active_context"]))
    spec = {
        "name": "beat-repeat", "os": "1.41", "requires": ["modarea", "vparams"],
        "description": "Beat repeat dal sequencer: RPT1 e RPT2 (1/16, 1/8, 3/16, 1/4, 1/2, 1BAR) sulla pagina "
                       "TRIG della FX track; con la FX track attiva, tenendo premuti i tasti di retrig 13 e 14 "
                       "si ripetono gli ultimi step di tutte le tracce, a tempo.",
        "generated_by": "mods/beat-repeat/make_patch.py",
        "symbols": {k: f"{syms[k]:#010x}" for k in ("br_step", "br_step_hook", "br_kbd", "br_kbd_hook", "br_ev",
                                                     "br_ev_hook", "br_page_stub", "br_get", "br_set",
                                                     "br_invoke", "br_gfx", "br_proto", "br_gfx_proto",
                                                     "br_rate", "br_held")} | {"br_active_context": f"{ui_syms['br_active_context']:#010x}"},
        "patches": patches,
    }
    (HERE / "patch.json").write_text(json.dumps(spec, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    (REPO / "out" / "beat-repeat").mkdir(parents=True, exist_ok=True)
    (REPO / "out" / "beat-repeat" / "br.lst").write_text(dis, encoding="utf-8")
    print(f"patch.json: {len(blob)} B a {CODE_BASE:#x}..{CODE_BASE + len(blob):#x}")


if __name__ == "__main__":
    main()
