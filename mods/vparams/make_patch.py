"""Genera mods/vparams/patch.json (vedi vparams.S).

    python mods/vparams/make_patch.py         # richiede binutils m68k in WSL (CONTRIBUTING.md)

Le mod registrano i loro parametri con una patch accodata a vparams.entry(slot, id, get, set).
"""

from __future__ import annotations

import hashlib
import json
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

LOAD = 0x4000_0400
IMG, RAM = modarea_layout.IMG, modarea_layout.RAM     # area mod (mods/modarea)
CODE = RAM + 0x7E00                     # codice di vparams
VP_TABLE, VP_N = RAM + 0x8000, 32
HOOKS = [(0x4000_D870, "2f02747c222f0008", "vp_kit"),
         (0x4000_D94A, "2f02222f0008", "vp_get"),
         (0x4000_DA32, "2f032f02222f000c", "vp_set"),
         (0x4003_A244, "4fefffb048d7", "vp_draw_hook")]
WSL_BINUTILS = "~/tools/m68k/root"


def sha(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def wsl(cmd: str) -> str:
    r = subprocess.run(["wsl.exe", "-e", "bash", "-lc", cmd], capture_output=True, text=True)
    if r.returncode:
        raise SystemExit(f"comando WSL fallito:\n{cmd}\n{r.stderr}")
    return r.stdout


def entry(slot: int, pid: int, get: int, put: int, what: str, guard: int = 0) -> dict:
    """Register one virtual id; guard is an optional zero-argument ownership predicate."""
    if not 0 <= slot < VP_N or not 0 < pid < 505:
        raise ValueError((slot, pid))
    addr = VP_TABLE + 16 * slot
    return {"section": 3, "addr": f"{IMG + addr - RAM:#010X}", "len": 16, "append": True,
            "hex": struct.pack(">HHIII", pid, 0, get, put, guard).hex(), "ram": f"{addr:#010x}",
            "what": f"vparams[{slot}]: id {pid} -> {what}" + (" (scoped)" if guard else "")}

def main() -> None:
    stock = REPO / "firmware" / "Syntakt_OS1.41.syx"
    sec3 = eft.unpack(stock, REPO / "unpacked" / stock.stem, ids=[3])[3].read_bytes()
    with tempfile.TemporaryDirectory(prefix="vparams-") as tmp:
        tmp = Path(tmp)
        shutil.copy(HERE / "vparams.S", tmp / "vparams.S")
        w = eft.to_wsl_path(tmp)
        bu = f"R={WSL_BINUTILS}; export LD_LIBRARY_PATH=$R/usr/lib/x86_64-linux-gnu; cd {w}; "
        wsl(bu + f"$R/usr/bin/m68k-linux-gnu-as -mcpu=54418 --defsym VP_TABLE={VP_TABLE} vparams.S -o v.o")
        wsl(bu + f"$R/usr/bin/m68k-linux-gnu-ld -N -Ttext={CODE:#x} -o v.elf v.o")
        wsl(bu + "$R/usr/bin/m68k-linux-gnu-objcopy -O binary v.elf v.bin")
        syms = {p[2]: int(p[0], 16) for p in (l.split() for l in wsl(bu + "$R/usr/bin/m68k-linux-gnu-nm v.elf").splitlines()) if len(p) == 3}
        blob = (tmp / "v.bin").read_bytes()
    if CODE + len(blob) > VP_TABLE:
        raise SystemExit("codice troppo grande")
    patches = [{"section": 3, "addr": f"{IMG + CODE - RAM:#010X}", "len": len(blob), "append": True,
                "hex": blob.hex(), "ram": f"{CODE:#010x}", "what": "(area mod) vp_kit, vp_get, vp_set"}]
    for addr, orig, sym in HOOKS:
        old = sec3[addr - LOAD:addr - LOAD + len(orig) // 2]
        if old.hex() != orig:
            raise SystemExit(f"{addr:#x}: byte inattesi")
        code = struct.pack(">HI", 0x4EF9, syms[sym]) + (b"\x4e\x71" if len(orig) == 16 else b"")
        patches.append({"section": 3, "addr": f"{addr:#010X}", "len": len(code), "expect_sha256": sha(old),
                        "hex": code.hex(), "what": f"aggancio: jmp {sym}" + (" ; nop" if len(orig) == 16 else "")})
    spec = {"name": "vparams", "os": "1.41", "requires": ["modarea"],
            "description": "Parametri virtuali delle mod: agganci alle funzioni centrali dei parametri di kit "
                           "e tabella di registrazione in RAM.",
            "generated_by": "mods/vparams/make_patch.py",
            "layout": {"table": f"{VP_TABLE:#010x}", "entries": VP_N},
            "symbols": {k: f"{syms[k]:#010x}" for k in ("vp_kit", "vp_get", "vp_set", "vp_find", "vp_draw_hook")},
            "patches": patches}
    (HERE / "patch.json").write_text(json.dumps(spec, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"patch.json: {len(blob)} B a {CODE:#x}; tabella a {VP_TABLE:#x}")


if __name__ == "__main__":
    main()
