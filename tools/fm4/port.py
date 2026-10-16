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
    # FM4-local IDs follow the 505 native rows; no occupied native ID is reused.
    for name, old, new in [
        ("R_ALGO", 1, 505), ("R_RAT3", 2, 506), ("R_LEV3", 3, 507),
        ("R_DEC3", 4, 508), ("R_RAT4", 5, 509), ("R_LEV4", 12, 510),
        ("R_DEC4", 13, 511), ("R_DET", 14, 512),
    ]:
        source, count = re.subn(rf"(?m)^#define\s+{name}\s+{old}$",
                                f"#define {name} {new}", source)
        if count != 1:
            raise RuntimeError(f"FM4 parameter anchor not unique: {name}")
    # Exploratory FM4-only donor pointers avoid writes past the 505 native
    # objects. Whether UI callbacks mutate a donor remains unverified.
    before = source[source.index("static int ready;"):source.index("/* SY FM4's page")]
    after = '''/* Page-local objects live for the OS session. Their four std::function
 * members are cloned through the native manager-aware copy constructor. */
__attribute__((section(".data"))) static u32 fm4m_ui_objects[PAGE2_N][INFO_LONGS];
__attribute__((section(".data"))) static u32 fm4m_objects_ready;

static void init_once(void) {
    if (fm4m_objects_ready)
        return;
    for (int i = 0; i < PAGE2_N; i++)
        if (REC_INFO(info_from[i])[7] == 0)
            return;
    void (*copy_fun)(void *, const void *) = (void *)0x401882be;
    for (int i = 0; i < PAGE2_N; i++) {
        const u32 *src = REC_INFO(info_from[i]);
        u32 *dst = fm4m_ui_objects[i];
        for (int k = 0; k < 5; k++)
            dst[k] = src[k];
        for (int off = 20; off < 84; off += 16)
            copy_fun((uint8_t *)dst + off, (const uint8_t *)src + off);
    }
    fm4m_objects_ready = 1;
}

u32 fm4m_ui_object(u32 id) {
    if (id >= 505 && id < 513) {
        init_once();
        return (u32)fm4m_ui_objects[id - 505];
    }
    return (u32)REC_INFO(id < 505 ? id : 0);
}

/* Used only at the two generic encoder guards. Native IDs keep their exact
 * old result; FM4 IDs pass only for SourcePageView on page 2. */
u32 fm4m_scoped_id(void *view, u32 id) {
    if (id <= 504)
        return id;
    if (id >= 505 && id <= 512 && ((volatile u32 *)view)[0] == 0x401ca0dc &&
        ((volatile u32 *)view)[0x90 / 4] == 1)
        return id;
    return 0;
}

/* Only FM4 page-2 IDs take the new logical-word and track-classification
 * route. Every native ID delegates to its untouched OS 1.41 function. */
u32 fm4m_ui_lix(u32 id) {
    if (id >= 505 && id <= 512)
        return 0x36 + (id - 505);
    return ((u32 (*)(u32))0x400a5c4a)(id);
}

u32 fm4m_ui_track_param(u32 id) {
    if (id >= 505 && id <= 512)
        return 1;
    return ((u32 (*)(u32))0x400a61a4)(id);
}

u32 fm4m_ui_range_values(u32 id, u32 *dst) {
    const record_t *rec = &fm4m_records[id - 505];
    dst[0] = rec->min;
    dst[1] = rec->max;
    dst[2] = rec->def;
    return (u32)dst;
}

__asm__(
    "    .text\\n"
    "    .globl fm4m_id_guard\\n"
    "fm4m_id_guard:\\n"
    "    lea -16(%sp),%sp\\n"
    "    movem.l %d1-%d2/%a0-%a1,(%sp)\\n"
    "    move.l %d2,-(%sp)\\n"
    "    move.l %a2,-(%sp)\\n"
    "    jsr fm4m_scoped_id\\n"
    "    addq.l #8,%sp\\n"
    "    movem.l (%sp),%d1-%d2/%a0-%a1\\n"
    "    lea 16(%sp),%sp\\n"
    "    rts\\n"
    "    .globl fm4m_id_guard_d0\\n"
    "fm4m_id_guard_d0:\\n"
    "    lea -16(%sp),%sp\\n"
    "    movem.l %d1-%d2/%a0-%a1,(%sp)\\n"
    "    move.l %d0,-(%sp)\\n"
    "    move.l %a2,-(%sp)\\n"
    "    jsr fm4m_scoped_id\\n"
    "    addq.l #8,%sp\\n"
    "    movem.l (%sp),%d1-%d2/%a0-%a1\\n"
    "    lea 16(%sp),%sp\\n"
    "    rts\\n"
    "    .globl fm4m_key_guard\\n"
    "fm4m_key_guard:\\n"
    "    move.l %d0,-(%sp)\\n"
    "    cmpi.l #504,%d3\\n"
    "    bls 3f\\n"
    "    move.l %d3,-(%sp)\\n"
    "    move.l %a2,-(%sp)\\n"
    "    jsr fm4m_scoped_id\\n"
    "    addq.l #8,%sp\\n"
    "    tst.l %d0\\n"
    "    bne 3f\\n"
    "    move.l (%sp)+,%d0\\n"
    "    addq.l #4,%sp\\n"
    "    jmp 0x4003c2b0\\n"
    "3:  move.l (%sp)+,%d0\\n"
    "    rts\\n"
    "    .globl fm4m_post_guard\\n"
    "fm4m_post_guard:\\n"
    "    move.l %d0,-(%sp)\\n"
    "    cmpi.l #504,%d2\\n"
    "    bls 2f\\n"
    "    move.l %d2,-(%sp)\\n"
    "    move.l %a2,-(%sp)\\n"
    "    jsr fm4m_scoped_id\\n"
    "    addq.l #8,%sp\\n"
    "    tst.l %d0\\n"
    "    bne 2f\\n"
    "    move.l (%sp)+,%d0\\n"
    "    addq.l #4,%sp\\n"
    "    jmp 0x4003bb76\\n"
    "2:  move.l (%sp)+,%d0\\n"
    "    rts\\n"
    "    .globl fm4m_range_guard\\n"
    "fm4m_range_guard:\\n"
    "    move.l 4(%sp),%d0\\n"
    "    cmpi.l #505,%d0\\n"
    "    blo 1f\\n"
    "    cmpi.l #512,%d0\\n"
    "    bhi 1f\\n"
    "    move.l %a0,-(%sp)\\n"
    "    move.l %d0,-(%sp)\\n"
    "    jsr fm4m_ui_range_values\\n"
    "    addq.l #8,%sp\\n"
    "    rts\\n"
    "1:  jmp 0x400a62c8\\n");

'''
    source = _replace(source, before, after)
    source = _replace(source,
        "if (fm4 && V(view, PAGE_INDEX) == 1 && knob < 9)",
        "if (fm4 && fm4m_objects_ready && V(view, PAGE_INDEX) == 1 && knob < 9)")
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
        struct.pack_into(">I", row, 32, 505 + i)
        struct.pack_into(">I", main_blob, records_at + 52*i + 32, 505 + i)
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


def local_descriptor_space_patches(raw3, assets):
    """Stage eight FM4 descriptors without moving the native descriptor base.

    The following stock position tables and their preceding signed-index
    window are copied to free heap-modarea space. Five absolute references move. This
    helper does not make the UI safe: native ID bounds remain to be audited.
    """
    desc_end = 0x40233C30
    table_begin = 0x40233BD4
    table_end = 0x40233E78
    table_ram = MODAREA_RAM + 0x6000
    if assets["main_syms"]["__bss_end"] > table_ram:
        raise RuntimeError("FM4 CPU1 BSS overlaps relocated stock tables")
    if table_ram + table_end - table_begin > MODAREA_RAM + 0x7e00:
        raise RuntimeError("relocated tables overlap vparams")
    stock_tables = raw3[table_begin - LOAD:table_end - LOAD]
    if len(stock_tables) != 0x2a4:
        raise RuntimeError("incomplete stock position tables")
    spec = [_append(3, IMG + 0x6000, stock_tables, "FM4 displaced stock position tables")]
    for site, old, new in (
        (0x400AAECA, desc_end, table_ram + 0x5c),
        (0x400AD470, desc_end, table_ram + 0x5c),
        (0x400A6E84, desc_end + 0x100, table_ram + 0x15c),
        (0x400A6E20, 0x40233DD4, table_ram + 0x200),
        (0x400A6E94, 0x40233DD4, table_ram + 0x200),
    ):
        offset = site - LOAD
        if struct.unpack_from(">I", raw3, offset)[0] != old:
            raise RuntimeError(f"stock position-table reference changed at {site:#x}")
        spec.append(_fixed(raw3, 3, site, struct.pack(">I", new),
                           "FM4 relocated stock position-table reference"))
    for i, row in enumerate(assets["records"]):
        at = desc_end + 52 * i
        spec.append(_fixed(raw3, 3, at, row, f"FM4-local descriptor {505+i}"))
    return spec


def scoped_id_guard_patches(raw3, assets):
    """Stage two page-scoped encoder guards; not included in firmware yet."""
    entries = (
        (0x4003B8D4, bytes.fromhex("0c80000001f863024280"), 2, "fm4m_id_guard"),
        (0x4003B6BE, bytes.fromhex("0c82000001f86204200260024280"), 4, "fm4m_id_guard"),
    )
    result = []
    for addr, expected, nops, symbol in entries:
        jump = b"\x4e\xb9" + struct.pack(">I", assets["main_syms"][symbol])
        old = raw3[addr - LOAD:addr - LOAD + len(expected)]
        if old != expected:
            raise RuntimeError(f"FM4 encoder guard changed at {addr:#x}")
        data = jump + b"\x4e\x71" * nops
        if len(data) != len(expected):
            raise RuntimeError("FM4 encoder guard patch length mismatch")
        result.append(_fixed(raw3, 3, addr, data, "FM4 page-scoped encoder ID guard"))
    return result


def scoped_post_edit_guard_patch(raw3, assets):
    """Retain the native post-edit bound and admit page-2 FM4 IDs only."""
    addr = 0x4003BAAE
    old = bytes.fromhex("0c82000001f8620000c0")
    if raw3[addr - LOAD:addr - LOAD + len(old)] != old:
        raise RuntimeError("FM4 post-edit guard changed")
    data = b"\x4e\xb9" + struct.pack(">I", assets["main_syms"]["fm4m_post_guard"]) + b"\x4e\x71" * 2
    return _fixed(raw3, 3, addr, data, "FM4 scoped post-edit redraw guard")


def scoped_key_guard_patch(raw3, assets):
    """Preserve key-handler skip behavior for non-FM4 high IDs."""
    addr = 0x4003BDB6
    old = bytes.fromhex("0c83000001f8620004f2")
    if raw3[addr - LOAD:addr - LOAD + len(old)] != old:
        raise RuntimeError("FM4 key guard changed")
    data = b"\x4e\xb9" + struct.pack(">I", assets["main_syms"]["fm4m_key_guard"]) + b"\x4e\x71" * 2
    return _fixed(raw3, 3, addr, data, "FM4 scoped key-handler guard")


def scoped_notify_guard_patch(raw3, assets):
    """Stage the second direct descriptor-index clamp in the notify path."""
    addr = 0x4003C634
    old = bytes.fromhex("0c80000001f863024280")
    if raw3[addr - LOAD:addr - LOAD + len(old)] != old:
        raise RuntimeError("FM4 notification guard changed")
    data = b"\x4e\xb9" + struct.pack(">I", assets["main_syms"]["fm4m_id_guard_d0"]) + b"\x4e\x71" * 2
    return _fixed(raw3, 3, addr, data, "FM4 scoped notification descriptor guard")


def scoped_ui_metadata_patches(raw3, assets):
    """Stage UI call-site routing; native metadata functions remain intact."""
    sites = (
        (0x4003B5D6, 0x400A5C4A, "fm4m_ui_lix"),
        (0x4003B6FC, 0x400A5C4A, "fm4m_ui_lix"),
        (0x4003BD1E, 0x400A5C4A, "fm4m_ui_lix"),
        (0x40037C6C, 0x400A5C4A, "fm4m_ui_lix"),
        (0x40037F1A, 0x400A5C4A, "fm4m_ui_lix"),
        (0x40037F78, 0x400A5C4A, "fm4m_ui_lix"),
        (0x40037EFA, 0x400A61A4, "fm4m_ui_track_param"),
    )
    result = []
    for addr, old, symbol in sites:
        expected = b"\x4e\xb9" + struct.pack(">I", old)
        if raw3[addr - LOAD:addr - LOAD + 6] != expected:
            raise RuntimeError(f"FM4 UI metadata call changed at {addr:#x}")
        data = b"\x4e\xb9" + struct.pack(">I", assets["main_syms"][symbol])
        result.append(_fixed(raw3, 3, addr, data, f"FM4-local UI metadata {symbol}"))
    return result


def scoped_ui_range_patches(raw3, assets):
    """Route identified SourcePageView range reads without changing stock IDs."""
    sites = (0x4003804E, 0x4003B156, 0x40042876)
    result = []
    for addr in sites:
        expected = b"\x4e\xb9" + struct.pack(">I", 0x400A62C8)
        if raw3[addr - LOAD:addr - LOAD + 6] != expected:
            raise RuntimeError(f"FM4 UI range call changed at {addr:#x}")
        data = b"\x4e\xb9" + struct.pack(">I", assets["main_syms"]["fm4m_range_guard"])
        result.append(_fixed(raw3, 3, addr, data, "FM4 page-local UI range"))
    return result


def scoped_ui_object_patches(raw3, assets):
    """Stage identified edit/draw call sites; do not alter native accessor."""
    target = struct.pack(">I", assets["main_syms"]["fm4m_ui_object"])
    refs = (
        (0x40038060, 0x4007B9B2),
        (0x40038580, 0x4007B9B2),
        (0x40038BF8, 0x4007B9B2),
        (0x4003B96E, 0x4007B9B2),
        (0x40043526, 0x4007B9B2),
    )
    result = []
    for addr, old in refs:
        expected = struct.pack(">I", old)
        if raw3[addr - LOAD:addr - LOAD + 4] != expected:
            raise RuntimeError(f"FM4 UI object reference changed at {addr:#x}")
        result.append(_fixed(raw3, 3, addr, target, "FM4 page-local UI object"))
    return result


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
