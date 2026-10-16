"""Compile Rxuting's pinned MIT SY FM4 source for Syntakt OS 1.41.

All stock-derived patches are generated in an ignored work directory. The
upstream checkout is read-only to this script and must be at the pinned commit.
"""
import hashlib
import importlib.util
import json
import os
import re
import shutil
import struct
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
UPSTREAM = ROOT.parent / "sy-fm4"
REVISION = "a596b6393fc43582fd3ae0234ac04e198b779edb"
TC = ROOT.parent / "Synthack-OS/out/max2-toolchain/root"
LOAD = 0x40000400
MAIN = 0x444E88D0
IMG = 0x40348000
MODAREA_RAM = 0x444E38D0


def _replace(source, before, after):
    if source.count(before) not in (1, 2):
        raise RuntimeError(f"FM4 source anchor not unique: {before!r}")
    return source.replace(before, after)


def _symbols(path):
    result = {}
    for line in path.read_text().splitlines():
        bits = line.split()
        if len(bits) == 3:
            result[bits[2]] = int(bits[0], 16)
    return result


def _make(directory, target):
    prefix = str(TC / "usr/bin/m68k-linux-gnu-")
    env = dict(os.environ, LD_LIBRARY_PATH=str(TC / "usr/lib/x86_64-linux-gnu"))
    subprocess.run([
        "make", "-C", str(directory), target,
        "CC=" + prefix + "gcc-14", "OBJCOPY=" + prefix + "objcopy",
        "NM=" + prefix + "nm",
    ], check=True, env=env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)


def prepare(work):
    rev = subprocess.check_output(["git", "-C", str(UPSTREAM), "rev-parse", "HEAD"], text=True).strip()
    if rev != REVISION:
        raise RuntimeError(f"SY FM4 revision {rev} differs from pinned {REVISION}")
    engine = work / "fm4-engine"
    shutil.copytree(UPSTREAM / "engine", engine, ignore=shutil.ignore_patterns("*.o", "*.elf", "*.bin", "*.map", "test_fm4", "wav"))
    main_c = engine / "main/main_fm4.c"
    source = main_c.read_text()
    # Function pointers and data addresses mapped from the exact 1.40A and
    # 1.41 stock images. No version-wide offset is assumed.
    changes = {
        "0x40043f9c": "0x40044c54", "0x40043bfc": "0x40044894",
        "0x400f6984": "0x40103788", "0x400f6990": "0x40103794",
        "0x41b888cc": "0x41b9fa24", "0x402205a4": "0x402340a4",
        "0x4022067c": "0x4023417c", "0x40220490": "0x40233f90",
        "0x43bc76a4": "0x43bde7fc", "0x43bc7588": "0x43bde6e0",
        "0x43bc72f4": "0x43bde44c", "0x43bc65e4": "0x43bdd73c",
    }
    for before, after in changes.items():
        source = _replace(source, before, after)
    # Reuse eight native Error placeholders without MIDI mappings.
    for name, old, new in [
        ("R_ALGO", 1, 36), ("R_RAT3", 2, 37), ("R_LEV3", 3, 38),
        ("R_DEC3", 4, 39), ("R_RAT4", 5, 40), ("R_LEV4", 12, 41),
        ("R_DEC4", 13, 42), ("R_DET", 14, 43),
    ]:
        source, count = re.subn(rf"(?m)^#define\s+{name}\s+{old}$",
                                f"#define {name} {new}", source)
        if count != 1:
            raise RuntimeError(f"FM4 parameter anchor not unique: {name}")
    main_c.write_text(source)
    ld = engine / "main/blob.ld"
    ld.write_text(_replace(ld.read_text(), ". = 0x47000000;", f". = {MAIN:#x};"))
    _make(engine / "main", "blob.bin")
    _make(engine / "syn", "all")
    main_blob = bytearray((engine / "main/blob.bin").read_bytes())
    syn_blob = (engine / "syn/blob.bin").read_bytes()
    syn_stub = (engine / "syn/stub.bin").read_bytes()
    main_syms = _symbols(engine / "main/blob.map")
    syn_syms = _symbols(engine / "syn/blob.map")
    if main_syms["__bss_end"] > MODAREA_RAM + 0x7e00:
        raise RuntimeError("FM4 MAIN payload/BSS overlaps the vparams block")
    if MAIN + len(main_blob) != main_syms["__blob_end"]:
        raise RuntimeError("FM4 MAIN blob does not match its linker map")
    if 0x4005df10 + len(syn_blob) > LOAD + 0x60000 - 5:
        raise RuntimeError("FM4 voice payload exceeds the section-7 limit")
    records_at = main_syms["fm4m_records"] - MAIN
    records = [bytearray(main_blob[records_at + 52*i:records_at + 52*(i+1)]) for i in range(8)]
    for i, row in enumerate(records):
        if len(row) != 52:
            raise RuntimeError("incomplete FM4 descriptor")
        struct.pack_into(">I", row, 32, 36 + i)
        struct.pack_into(">I", main_blob, records_at + 52*i + 32, 36 + i)
    main_blob = bytes(main_blob)
    report = {
        "upstream_commit": REVISION, "main_bytes": len(main_blob),
        "main_bss_end": hex(main_syms["__bss_end"]),
        "voice_bytes": len(syn_blob), "voice_stub_bytes": len(syn_stub),
    }
    (work / "fm4-assets.json").write_text(json.dumps(report, indent=2) + "\n")
    return {"main_blob": main_blob, "main_syms": main_syms,
            "syn_blob": syn_blob, "syn_stub": syn_stub, "syn_syms": syn_syms,
            "records": records, "report": report}


def _fixed(raw, section, addr, data, what):
    offset = addr - LOAD
    if offset < 0 or offset + len(data) > len(raw):
        raise RuntimeError(f"FM4 patch outside section {section}: {addr:#x}")
    return {"section": section, "addr": hex(addr), "len": len(data),
            "expect_sha256": hashlib.sha256(raw[offset:offset+len(data)]).hexdigest(),
            "hex": data.hex(), "what": what}


def _append(section, addr, data, what):
    return {"section": section, "addr": hex(addr), "append": True,
            "len": len(data), "hex": data.hex(), "what": what}


def patches(raw3, raw7, assets, work, native_dma_wait=False):
    m = assets["main_syms"]
    u32 = lambda n: struct.pack(">I", n)
    jmp = lambda name: b"\x4e\xf9" + u32(m[name])
    patch = []
    # Eight stock Error descriptors receive the FM4 records.
    vptr = 0x401ca0dc
    main_entries = assets["main_blob"][:8]
    patch.append(_fixed(raw3, 3, vptr + 47*4, main_entries[:4], "FM4 SYN knob descriptor"))
    patch.append(_fixed(raw3, 3, vptr + 19*4, main_entries[4:8], "FM4 SYN page title"))
    # Original stock records 36..43 are Error placeholders: no MIDI mapping.
    desc = 0x4022d59c
    for i, row in enumerate(assets["records"]):
        at = desc + 52 * (36 + i)
        old = raw3[at - LOAD:at - LOAD + 52]
        if len(old) != 52 or struct.unpack_from(">II", old, 0) != (0xffffffff, 0xffffffff) or struct.unpack_from(">II", old, 24) != (0xffffffff, 0xffffffff):
            raise RuntimeError(f"FM4 descriptor {36+i} is not a stock no-MIDI placeholder")
        patch.append(_fixed(raw3, 3, at, row, f"FM4 descriptor {36+i}"))
    patch.append(_fixed(raw3, 3, 0x400a73be, b"\x41\xf9" + u32(m["fm4m_sound_l2p"]), "FM4 sound save slot map"))
    patch.append(_fixed(raw3, 3, 0x400a73da, b"\x72\x7c", "FM4 sound save slot bound"))
    load = b"\x4e\xb9" + u32(m["fm4m_load_shim"]) + b"\x43\xf9" + u32(m["fm4m_sound_p2l"]) + b"\x4e\x71" * 11
    patch.append(_fixed(raw3, 3, 0x400a6ff2, load, "FM4 sound load with stock defaults"))
    patch.append(_fixed(raw3, 3, 0x400a8152, b"\x4b\xf9" + u32(m["fm4m_lane_of_lix"]), "FM4 pattern lock writer A"))
    patch.append(_fixed(raw3, 3, 0x400a82be, b"\x45\xf9" + u32(m["fm4m_lane_of_lix"]), "FM4 pattern lock writer B"))
    patch.append(_fixed(raw3, 3, 0x400a7fc6, b"\x7a\x57", "FM4 pattern lock reader bound"))
    patch.append(_fixed(raw3, 3, 0x400a6cba, jmp("fm4m_phys_to_lix"), "FM4 lock lane to logical index"))
    if not native_dma_wait:
        patch.append(_fixed(raw3, 3, 0x400a2036, jmp("fm4m_dma_wait"), "FM4 page 2 shared RAM publisher"))
    patch.append(_fixed(raw3, 3, 0x400a6138, b"\x4e\xb9" + u32(m["fm4m_index_done"]), "FM4 defaults index"))
    patch.append(_fixed(raw3, 3, 0x402535a7, b"SY FM4\x00\x00", "FM4 machine name"))
    patch.append(_fixed(raw3, 3, 0x402535af, b"SYF4\x00", "FM4 short name"))
    patch.append(_append(3, IMG + (MAIN - MODAREA_RAM), assets["main_blob"], "FM4 main CPU code and records"))
    # Section 7 is byte-identical in stock OS 1.40A and 1.41. Execute the
    # pinned upstream patcher on 1.41 bytes, then declare exactly its diffs.
    spec = importlib.util.spec_from_file_location("fm4_s7patch", UPSTREAM / "patch/s7patch.py")
    s7 = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(s7)
    target7, prep, render = s7.patch(raw7, assets["syn_blob"], assets["syn_stub"], 4)
    if (prep, render) != (assets["syn_syms"]["syn_fm4_prep"], assets["syn_syms"]["syn_fm4_render"]):
        raise RuntimeError("FM4 voice table entries mismatch")
    i = 0
    while i < len(raw7):
        if raw7[i] == target7[i]:
            i += 1
            continue
        start = i
        while i < len(raw7) and raw7[i] != target7[i]:
            i += 1
        patch.append(_fixed(raw7, 7, LOAD + start, target7[start:i], "FM4 voice loader or engine-4 dispatch"))
    patch.append(_append(7, LOAD + len(raw7), target7[len(raw7):], "FM4 voice CPU engine"))
    folder = work / "mods/fm4"
    folder.mkdir()
    (folder / "patch.json").write_text(json.dumps({"name": "fm4", "os": "1.41",
            "requires": ["modarea"], "patches": patch}, indent=2) + "\n")
    return folder
