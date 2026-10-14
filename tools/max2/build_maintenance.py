"""Regenerate a validation-only MAX compatibility overlay; FM4 source is absent.

Original mods/, tools/max/, stock, baseline and MAX image are not modified.
Requires the repository-local binutils/GCC packages in out/max2-toolchain/root.
"""
import hashlib
import importlib.util
import json
import os
import re
import shutil
import struct
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
HERE = Path(__file__).resolve().parent
WORK = ROOT / "out" / (sys.argv[1] if len(sys.argv) > 1 else "max2-maintenance-work")
TC = ROOT / "out" / "max2-toolchain" / "root"
sys.path[:0] = [str(ROOT / "tools" / "unpack"), str(ROOT / "tools" / "build")]
import eft
from build import build

LOAD, DESC, OBJS = 0x40000400, 0x4022d59c, 0x41b9fa24
TABLE, POBJS, CODE = 0x46010000, 0x46017000, 0x4600f000
MODIMG = 0x40348000
COMP_OLD = [144, 122, 91, 101, 127, 59, 115]
FX_OLD = [246, 247, 248, 250, 251, 252, 249, 253]
BR_OLD = [113, 124]
MAP = dict(zip(COMP_OLD + FX_OLD + BR_OLD, range(505, 522)))
DONORS = [144, 122, 144, 144, 126, 126, 115] + [250] * 8 + [93] * 2
TYPES = [0, 8, 0, 0, 8, 0, 12] + [0] * 10
NAMES = ["splash", "dual-mono", "modarea", "vparams", "master-comp",
         "readable-values", "beat-repeat", "fx3"]


def run(args, cwd=None):
    env = dict(os.environ, LD_LIBRARY_PATH=str(TC / "usr/lib/x86_64-linux-gnu"))
    try:
        return subprocess.check_output(args, cwd=cwd, env=env, text=True, stderr=subprocess.STDOUT)
    except subprocess.CalledProcessError as err:
        raise RuntimeError(err.output) from err


def bu(name, *args, cwd=None):
    return run([str(TC / "usr/bin" / ("m68k-linux-gnu-" + name)), *map(str, args)], cwd)


def native(cmd):
    cmd = cmd.replace("R=~/tools/m68k/root", "R=" + str(TC))
    cmd = cmd.replace("gcc-13", "gcc-14").replace("libexec/gcc/m68k-linux-gnu/13/", "libexec/gcc-cross/m68k-linux-gnu/14/")
    return run(["bash", "-lc", cmd])


def module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    mod.wsl = native
    return mod


def fixed(raw, addr, data, what):
    old = raw[addr - LOAD:addr - LOAD + len(data)]
    assert len(old) == len(data)
    return {"section": 3, "addr": hex(addr), "len": len(data),
            "expect_sha256": hashlib.sha256(old).hexdigest(), "hex": data.hex(), "what": what}


def appended(addr, data, what):
    return {"section": 3, "addr": hex(MODIMG + addr - 0x46000000),
            "append": True, "ram": hex(addr), "len": len(data), "hex": data.hex(), "what": what}


def assemble(source, base, directory, incs=None):
    directory.mkdir(parents=True, exist_ok=True)
    (directory / "unit.S").write_text(source)
    for name, data in (incs or {}).items():
        (directory / name).write_bytes(data) if isinstance(data, bytes) else (directory / name).write_text(data)
    bu("as", "-mcpu=54418", "unit.S", "-o", "unit.o", cwd=directory)
    bu("ld", "-N", "-Ttext=" + hex(base), "-o", "unit.elf", "unit.o", cwd=directory)
    bu("objcopy", "-O", "binary", "unit.elf", "unit.bin", cwd=directory)
    return (directory / "unit.bin").read_bytes()


def main():
    expected_base = "b536fa598cc2587d718905144e4c597947a5770c"
    subprocess.check_call(["git", "-C", str(ROOT), "merge-base", "--is-ancestor", expected_base, "HEAD"])
    subprocess.check_call(["git", "-C", str(ROOT), "diff", "--exit-code", expected_base, "--",
                           "mods", "tools/build", "tools/unpack", "tools/emu", "tools/splash",
                           "tests", "pytest.ini"])
    assert subprocess.check_output(["git", "-C", str(ROOT.parent / "syntakt-firmware-workbench"), "rev-parse", "HEAD"],text=True).strip() == "49a7a1e5ac1ac4c6869f01b94a820f2b625dada5"
    if WORK.exists():
        raise SystemExit(f"Preserving existing experiment {WORK}; choose a new WORK directory for another run")
    WORK.mkdir(parents=True)
    hashes = {p: hashlib.sha256((ROOT / p).read_bytes()).hexdigest() for p in
              ("firmware/Syntakt_OS1.41.syx", "out/synthack.syx", "out/synthack-max.syx")}
    assert hashes["firmware/Syntakt_OS1.41.syx"] == "8e2488f462c4a5656396a895f113bcd415e9900fa8709340dccf45d4cb9ed19e"
    for sub in ("firmware", "tools"):
        (WORK / sub).symlink_to(ROOT / sub, target_is_directory=True)
    (WORK / "mods").mkdir()
    for name in NAMES:
        if name in ("master-comp", "fx3", "beat-repeat", "modarea", "vparams"):
            shutil.copytree(ROOT / "mods" / name, WORK / "mods" / name)
        else:
            (WORK / "mods" / name).symlink_to(ROOT / "mods" / name, target_is_directory=True)
    registry = WORK / "mods/vparams/make_patch.py"
    registry.write_text(registry.read_text().replace("not 0 < pid < 505", "not 0 < pid < 522"))
    raw = eft.unpack(ROOT / "firmware/Syntakt_OS1.41.syx", WORK / "stock", ids=[3])[3].read_bytes()
    extra = [bytearray(raw[DESC - LOAD + old * 52:DESC - LOAD + (old + 1) * 52])
             for old in COMP_OLD + FX_OLD + BR_OLD]
    for n, row in enumerate(extra):
        struct.pack_into(">I", row, 4, 0x10000 + 505 + n)
        row[24:32] = b"\xff" * 8  # no MIDI CC/NRPN aliases
        row[36:40] = bytes(4)     # not in native modulation destination lists
    overrides = []
    eft.to_wsl_path = lambda p: str(Path(p).resolve())
    for name in ("master-comp", "fx3", "beat-repeat"):
        folder = WORK / "mods" / name
        source = folder / ("comp.S" if name == "master-comp" else "fx3.c" if name == "fx3" else "br.c")
        text = source.read_text()
        if name == "master-comp":
            text = re.sub(r"(\.equ\s+OBJS,\s+)0x41B9FA24", r"\g<1>" + hex(POBJS - 505 * 84), text)
            text = text.replace("comp_init:\n", "comp_init:\n        jsr     0x4600f080\n")
        else:
            ids = FX_OLD if name == "fx3" else BR_OLD
            text = re.sub(r"\b(" + "|".join(map(str, ids)) + r")\b", lambda m: str(MAP[int(m[0])]), text)
            # RPT page uses moveq: private ids require full-width immediates.
            text = re.sub(r"moveq\s+#(520|521)", r"move.l  #\1", text)
            if name == "fx3":
                text = text.replace("0x41B9FA24u", hex(POBJS - 505 * 84) + "u")
            label = "fx3_page_stub" if name == "fx3" else "br_page_stub"
            text = text.replace('"' + label + ':\\n"', '"' + label + ':\\n"\n    "        jsr     0x4600f080\\n"')
        source.write_text(text)
        mod = module("max2_" + name.replace("-", "_"), folder / "make_patch.py")
        if name == "master-comp":
            mod.PARAMS = [(a, b, MAP[i], d) for a, b, i, d in mod.PARAMS]
            mod.INIT_FIX = []
        elif name == "fx3":
            mod.PARAMS = [(MAP[p[0]], *p[1:]) for p in mod.PARAMS]
        else:
            mod.RPTS = [(MAP[p[0]], *p[1:]) for p in mod.RPTS]
        saved = sys.argv
        sys.argv = [str(folder / "make_patch.py")]
        try:
            mod.main()
        finally:
            sys.argv = saved
        spec = json.loads((folder / "patch.json").read_text())
        proto_sites = {}
        drop_sites = set()
        if name == "fx3":
            for pid, _, _, _, _, protos, extras in mod.PARAMS:
                proto_sites.update({addr: (pid, off) for off, (addr, _, _) in protos.items()})
                drop_sites.update(addr for addr, *_ in extras)
        elif name == "beat-repeat":
            for pid, _, _, protos, extras in mod.RPTS:
                proto_sites.update({addr: (pid, off) for off, (addr, _) in protos.items()})
                drop_sites.update(addr for addr, *_ in extras)
        kept = []
        for p in spec["patches"]:
            addr = int(p["addr"], 16)
            if not p.get("append") and DESC + 52 * 505 <= addr < DESC + 52 * 522:
                pid, off = divmod(addr - DESC, 52)
                extra[pid - 505][off:off + p["len"]] = bytes.fromhex(p["hex"])
            elif addr in proto_sites:
                pid, off = proto_sites[addr]
                overrides.append((POBJS + 84 * (pid - 505) + off, int(p["hex"], 16)))
            elif addr not in drop_sites:
                kept.append(p)
        spec["patches"] = kept
        spec["requires"].append("private-params")
        (folder / "patch.json").write_text(json.dumps(spec, indent=2) + "\n")
    # The loader already owns this hook. Add the private-table copy after SHLZ
    # and before the OS's BSS clear; the new RAM lies above the BSS region.
    loader_dir = WORK / "mods/modarea"
    source = (loader_dir / "modarea.S").read_text().replace("7:      movem.l", "7:      move.l  IMG,%d1\n        cmpi.l  #MAGIC,%d1\n        bne.s   10f\n        jsr     0x4600f000\n10:     movem.l")
    loader = assemble(source, 0x40338d80, WORK / "loader-build")
    assert 0x40338d80 + len(loader) < 0x40339000
    spec = json.loads((loader_dir / "patch.json").read_text())
    spec["patches"][0] = fixed(raw, 0x40338d80, loader, "modarea + private descriptors before BSS clear")
    (loader_dir / "patch.json").write_text(json.dumps(spec, indent=2) + "\n")
    object_inc = "".join(f".long {donor},{typ}\n" for donor, typ in zip(DONORS, TYPES))
    object_inc += "object_overrides:\n" + "".join(f".long {dst},{src}\n" for dst, src in overrides) + ".long 0,0\n"
    payload = assemble((HERE / "private_params.S").read_text(), CODE, WORK / "private-build",
                       {"descriptors.bin": b"".join(extra), "objects.inc": object_inc})
    assert len(payload) <= 0x1000, f"namespace exceeds remaining code region: {len(payload)}"
    patches = [appended(CODE, payload, "private descriptor initialization and objects")]
    needle = struct.pack(">I", DESC)
    pos = 0
    references = []
    while (pos := raw.find(needle, pos)) >= 0:
        references.append(LOAD + pos)
        patches.append(fixed(raw, LOAD + pos, struct.pack(">I", TABLE), "descriptor table base"))
        pos += 4
    assert len(references) == 56, f"unexpected table reference count {len(references)}"
    # The stock parameter upper-bound instructions are compared against the
    # complete descriptor count. Leave the native object getter's bound alone.
    bounds = []
    for m in re.finditer(bytes.fromhex("0c") + b"[\\x80-\\x87]" + bytes.fromhex("000001f9"), raw[:0x1c0000]):
        addr = LOAD + m.start()
        if addr == 0x4007b9b6:
            continue
        bounds.append(addr)
        patches.append(fixed(raw, addr + 2, struct.pack(">I", 522), "private descriptor upper bound"))
    for m in re.finditer(bytes.fromhex("0c") + b"[\\x80-\\x87]" + bytes.fromhex("000001f8"), raw[:0x1c0000]):
        patches.append(fixed(raw, LOAD + m.start() + 2, struct.pack(">I", 521), "private descriptor last index"))
    # Two UI paths compare an address register containing the logical ID.
    # These are CMPA, rather than the CMPi data-register forms above.
    for addr, expected, limit in [(0x400425de,"bdfc000001f9",522),
                                  (0x400dffda,"bbfc000001f8",521)]:
        assert raw[addr-LOAD:addr-LOAD+6].hex() == expected
        patches.append(fixed(raw,addr+2,struct.pack(">I",limit),"private descriptor CMPA bound"))
    assert raw[0x4007b9b2 - LOAD:0x4007b9bc - LOAD].hex() == "222f00040c81000001f9"
    patches.append(fixed(raw, 0x4007b9b2, struct.pack(">HIHH", 0x4ef9, CODE + 0x200, 0x4e71, 0x4e71), "private object lookup; stock ids unchanged"))
    ns = WORK / "mods/private-params"
    ns.mkdir()
    (ns / "patch.json").write_text(json.dumps({"name": "private-params", "os": "1.41", "requires": ["modarea"], "patches": patches}, indent=2))
    # Reuse the preserved Workbench generator to retain the exact MAX wave bank.
    max1 = module("max1_builder", ROOT / "tools/max/build_max.py")
    paths = eft.unpack(ROOT / "firmware/Syntakt_OS1.41.syx", WORK / "wave-stock", ids=[3, 7])
    target_paths = {sid: WORK / f"workbench-{sid}.bin" for sid in (3, 7)}
    meta = WORK / "workbench.json"
    run([str(max1.NODE), "tools/max/generate.mjs", *[max1.winpath(paths[s]) for s in (3, 7)],
         *[max1.winpath(target_paths[s]) for s in (3, 7)], max1.winpath(meta)], ROOT)
    wb = json.loads(meta.read_text())
    originals = {s: paths[s].read_bytes() for s in (3, 7)}
    targets = {s: target_paths[s].read_bytes() for s in (3, 7)}
    max1.ROOT = WORK
    wbpatch = max1.generate_patches(originals, targets, wb["regions"], max1.occupied())
    wbd = WORK / "mods/workbench-max"
    wbd.mkdir()
    (wbd / "patch.json").write_text(json.dumps({"name": "workbench-max", "os": "1.41", "patches": wbpatch}))
    output = WORK / "maintenance-validation.syx"
    result = build(ROOT / "firmware/Syntakt_OS1.41.syx", [WORK / "mods" / n for n in NAMES] + [ns, wbd], output)
    final_sections = eft.unpack(output, WORK / "final-sections", ids=[3,7])
    baseline_sections = eft.unpack(ROOT / "out/synthack-max.syx", WORK / "max1-sections", ids=[3,7])
    assert final_sections[7].read_bytes() == baseline_sections[7].read_bytes()
    final3, baseline3 = final_sections[3].read_bytes(), baseline_sections[3].read_bytes()
    for region in (r for r in wb["regions"] if r["section"] == 3):
        assert final3[region["start"]:region["end"]] == baseline3[region["start"]:region["end"]]
    result.update({"fm4": "blocked: implementation source unavailable", "parameter_ids": MAP,
                   "namespace_payload_bytes": len(payload), "descriptor_references": references,
                   "bound_sites": bounds, "input_hashes": hashes})
    (WORK / "validation.json").write_text(json.dumps(result, indent=2) + "\n")
    assert all(hashlib.sha256((ROOT / p).read_bytes()).hexdigest() == h for p, h in hashes.items())
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
