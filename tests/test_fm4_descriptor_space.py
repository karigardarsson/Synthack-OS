"""Prove a narrow FM4 descriptor gap without constructing a firmware image."""
import json
import struct
import sys
from pathlib import Path

import pytest
from unicorn.m68k_const import UC_M68K_REG_D0, UC_M68K_REG_D2

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "tools" / "fm4"), str(ROOT / "tests")]
import port  # noqa: E402
from test_fx3 import Machine  # noqa: E402


@pytest.fixture(scope="module")
def assets(tmp_path_factory):
    if not port.UPSTREAM.exists() or not port.TC.exists():
        pytest.skip("pinned FM4 source or ColdFire toolchain unavailable")
    return port.prepare(tmp_path_factory.mktemp("fm4-local-desc") / "work")


def test_stock_position_converters_survive_local_descriptor_gap(assets):
    raw = (ROOT / "unpacked/Syntakt_OS1.41/section_3_MAIN_OS.bin").read_bytes()
    spec = port.local_descriptor_space_patches(raw, assets)
    assert len(spec) == 14  # one copy, five references, eight descriptors
    baseline, relocated = Machine(), Machine()
    table_ram = port.MODAREA_RAM + 0x6000
    for item in spec:
        addr = table_ram if item.get("append") else int(item["addr"], 16)
        relocated.uc.mem_write(addr, bytes.fromhex(item["hex"]))
    outcomes = []
    for m in (baseline, relocated):
        for addr in (0x50005000, 0x50006000):
            m.uc.mem_write(addr, bytes((i * 37) & 255 for i in range(256)))
        m.uc.mem_write(0x50006000, bytes(4))
        run = []
        for fn in (0x400A6E02, 0x400A6E6E):
            run.append((m.call(fn, [0x50005000, 0x50006000]),
                        bytes(m.uc.mem_read(0x50005000, 160))))
        outcomes.append(run)
    assert outcomes[0] == outcomes[1]
    # The next stock table at 0x40233DD4 is deliberately not moved.
    assert bytes(relocated.uc.mem_read(0x40233DD4, 32)) == raw[0x40233DD4-port.LOAD:0x40233DD4-port.LOAD+32]
    for k in range(8):
        row = bytes(relocated.uc.mem_read(0x40233C30 + 52 * k, 52))
        assert struct.unpack_from(">I", row, 32)[0] == 505 + k
        assert row == assets["records"][k]


def test_actual_descriptor_accessors_need_scoped_fm4_bounds(assets):
    raw = (ROOT / "unpacked/Syntakt_OS1.41/section_3_MAIN_OS.bin").read_bytes()
    before, staged = Machine(), Machine()
    for item in port.local_descriptor_space_patches(raw, assets):
        addr = port.MODAREA_RAM + 0x6000 if item.get("append") else int(item["addr"], 16)
        staged.uc.mem_write(addr, bytes.fromhex(item["hex"]))
    # The real OS 1.41 accessors at 0x400A5C4A/6C compare against 505.
    # Test-only bound changes exercise their exact code with the contiguous
    # eight FM4 rows; this is not a firmware patch.
    staged.uc.mem_write(0x400A5C50, struct.pack(">I", 513))
    staged.uc.mem_write(0x400A5C72, struct.pack(">I", 513))
    for pid in (0, 15, 16, 36, 43, 190, 369, 504, 513, 0xFFFFFFFF):
        for fn in (0x400A5C4A, 0x400A5C6C):
            assert staged.call(fn, [pid]) == before.call(fn, [pid])
    for k in range(8):
        pid = 505 + k
        assert before.call(0x400A5C4A, [pid]) == 0xFFFFFFFF
        assert staged.call(0x400A5C4A, [pid]) == 0x36 + k
        assert staged.call(0x400A5C6C, [pid]) == 0xFFFFFFFF


def test_descriptor_copy_does_not_overlap_existing_max_appends():
    lo = port.MODAREA_RAM + 0x6000
    hi = lo + 0x2A4
    for path in (ROOT / "mods").glob("*/patch.json"):
        for item in json.loads(path.read_text())["patches"]:
            if item.get("append") and "ram" in item:
                begin = int(item["ram"], 16)
                end = begin + len(bytes.fromhex(item["hex"]))
                assert max(lo, begin) >= min(hi, end), path


def test_actual_shared_ui_guards_reject_fm4_ids():
    m = Machine()
    for pid, expected in ((503, 503), (504, 504), (505, 0), (512, 0)):
        m.uc.reg_write(UC_M68K_REG_D0, pid)
        m.uc.emu_start(0x4003B8D4, 0x4003B8DE, count=3)
        assert m.uc.reg_read(UC_M68K_REG_D0) == expected
    for pid, expected in ((503, 503), (504, 504), (505, 0), (512, 0)):
        m.uc.reg_write(UC_M68K_REG_D2, pid)
        m.uc.reg_write(UC_M68K_REG_D0, 0xDEADBEEF)
        m.uc.emu_start(0x4003B6BE, 0x4003B6CC, count=5)
        assert m.uc.reg_read(UC_M68K_REG_D0) == expected


def test_firmware_generator_still_rejects_occupied_native_rows(assets, tmp_path):
    raw3 = (ROOT / "unpacked/Syntakt_OS1.41/section_3_MAIN_OS.bin").read_bytes()
    raw7 = (ROOT / "unpacked/Syntakt_OS1.41/section_7_blob.raw").read_bytes()
    with pytest.raises(RuntimeError, match="FM4 descriptor 36"):
        port.patches(raw3, raw7, assets, tmp_path)
    assert not (tmp_path / "mods/fm4/patch.json").exists()
