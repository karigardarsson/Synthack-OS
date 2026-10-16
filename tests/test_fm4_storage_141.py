"""Exercise FM4 storage patches against the real OS 1.41 save/load routines.

This is an emulator-only probe; no FM4 firmware image is constructed.
"""
import struct
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools" / "fm4"))
import port  # noqa: E402
from test_fx3 import Machine, round_trip, valid  # noqa: E402

SAVE, LOAD = 0x400A7366, 0x400A6F7E
TRACK, FILE, RELOADED = 0x50005000, 0x50006000, 0x50007000
DEFAULTS = [0, 0x0400, 0, 0x4C00, 0x0400, 0, 0x4C00, 0x4000]


@pytest.fixture(scope="module")
def fm4_assets(tmp_path_factory):
    if not port.UPSTREAM.exists() or not port.TC.exists():
        pytest.skip("pinned FM4 source or ColdFire toolchain unavailable")
    return port.prepare(tmp_path_factory.mktemp("fm4-storage") / "work")


def machine(fm4_assets, patched=True):
    m = Machine()
    m.uc.mem_write(port.MAIN, fm4_assets["main_blob"])
    s = fm4_assets["main_syms"]
    m.call(s["fm4m_boot"])
    if patched:
        u32 = lambda n: struct.pack(">I", n)
        patches = (
            (0x400A73BE, b"\x41\xf9" + u32(s["fm4m_sound_l2p"])),
            (0x400A73DA, b"\x72\x7c"),
            (0x400A6FF2, b"\x4e\xb9" + u32(s["fm4m_load_shim"])
             + b"\x43\xf9" + u32(s["fm4m_sound_p2l"]) + b"\x4e\x71" * 11),
        )
        for addr, data in patches:
            m.uc.mem_write(addr, data)
    return m


def words(m, addr, n):
    return list(struct.unpack(f">{n}H", m.uc.mem_read(addr, n * 2)))


def test_real_sound_save_reload_keeps_new_and_legacy_words(fm4_assets):
    m = machine(fm4_assets)
    values = [0 if i in (4, 12) else 0x100 + i for i in range(54)]
    values += [0x0300, 0x0400, 0x3100, 0x4C00, 0x0500, 0x4100, 0x4300, 0x4000]
    m.uc.mem_write(TRACK + 20, struct.pack(">62H", *values))
    assert m.call(SAVE, [FILE, TRACK, 0]) & 0xFF == 1
    assert words(m, FILE + 28 + 2 * 54, 8) == values[54:]
    assert m.call(LOAD, [RELOADED, FILE]) & 0xFF == 1
    assert words(m, RELOADED + 20, 62) == values


def test_real_legacy_sound_loads_fm4_defaults(fm4_assets):
    m = machine(fm4_assets, patched=False)
    legacy = [0 if i in (4, 12) else 0x200 + i for i in range(54)]
    m.uc.mem_write(TRACK + 20, struct.pack(">54H", *legacy))
    assert m.call(SAVE, [FILE, TRACK, 0]) & 0xFF == 1
    assert words(m, FILE + 28 + 2 * 54, 8) == [0] * 8
    s = fm4_assets["main_syms"]
    m.uc.mem_write(0x400A6FF2, b"\x4e\xb9" + struct.pack(">I", s["fm4m_load_shim"])
                   + b"\x43\xf9" + struct.pack(">I", s["fm4m_sound_p2l"])
                   + b"\x4e\x71" * 11)
    assert m.call(LOAD, [RELOADED, FILE]) & 0xFF == 1
    assert words(m, RELOADED + 20, 54) == legacy
    assert words(m, RELOADED + 20 + 2 * 54, 8) == DEFAULTS


def test_fx3_kit_file_regression_with_fm4_storage_patches(fm4_assets):
    m = machine(fm4_assets)
    values = valid([0x1100 + i for i in range(71)])
    assert round_trip(m, values) == values


def test_lock_lane_mapping_preserves_native_and_fx_track(fm4_assets):
    m = machine(fm4_assets)
    s = fm4_assets["main_syms"]
    for k in range(8):
        lane, logical = 0x50 + k, 0x36 + k
        assert m.call(s["fm4m_phys_to_lix"], [0, lane]) == logical
        assert m.call(s["fm4m_phys_to_lix"], [12, lane]) == 0
        assert words(m, s["fm4m_lane_of_lix"] + 4 * logical + 2, 1) == [lane]


def test_native_ui_object_accessor_does_not_supply_fm4_objects():
    m = Machine()
    base = 0x41B9FA24
    assert m.call(0x4007B9B2, [504]) == base + 84 * 504
    for pid in range(505, 513):
        assert m.call(0x4007B9B2, [pid]) == base


def test_real_pattern_lock_pack_and_reload_all_fm4_lanes(fm4_assets):
    m = machine(fm4_assets)
    s = fm4_assets["main_syms"]
    patches = (
        (0x400A8152, b"\x4b\xf9" + struct.pack(">I", s["fm4m_lane_of_lix"])),
        (0x400A82BE, b"\x45\xf9" + struct.pack(">I", s["fm4m_lane_of_lix"])),
        (0x400A7FC6, b"\x7a\x57"),
        (0x400A6CBA, b"\x4e\xf9" + struct.pack(">I", s["fm4m_phys_to_lix"])),
    )
    for addr, data in patches:
        m.uc.mem_write(addr, data)
    m.uc.mem_map(0x51000000, 0x40000)
    m.uc.mem_map(0x52000000, 0x10000)
    source, packed = 0x51000000, 0x52000000
    # The stock 1.41 pattern layout uses a byte marker at +9216+logical,
    # a word value at +2*logical, and 130-byte serialized lock rows.
    for i, value in [(8, 0x2700)] + [(54 + k, 0x4000 + k) for k in range(8)]:
        m.uc.mem_write(source + 9216 + i, b"\x01")
        m.uc.mem_write(source + 2 * i, struct.pack(">H", value))
    assert m.call(0x400A811A, [packed, source]) & 0xFF == 1
    rows = [bytes(m.uc.mem_read(packed + 130 * k, 4)) for k in range(9)]
    assert [r[0] for r in rows[1:]] == list(range(0x50, 0x58))
    assert all(r[1] == 0 for r in rows)
    assert [struct.unpack(">H", r[2:])[0] for r in rows[1:]] == [0x4000 + k for k in range(8)]
    assert m.call(0x400A7F0C, [source, packed]) & 0xFF == 1
    for i, value in [(8, 0x2700)] + [(54 + k, 0x4000 + k) for k in range(8)]:
        assert m.uc.mem_read(source + 9216 + i, 1) == b"\x01"
        assert words(m, source + 2 * i, 1) == [value]


def test_fm4_cpu1_publishes_all_voice_parameters(fm4_assets):
    m = machine(fm4_assets)
    s = fm4_assets["main_syms"]
    m.uc.mem_map(0x10000000, 0x10000)
    m.uc.mem_map(0x43BD0000, 0x10000)
    for voice in range(8):
        for knob in range(8):
            logical = 0x0E + voice * 0x47 + 0x36 + knob
            m.uc.mem_write(0x800021B0 + logical * 2,
                           struct.pack(">H", 0x1000 + voice * 0x100 + knob))
    m.call(s["fm4m_dma_wait"])
    values = words(m, 0x10000700, 64)
    assert values == [0x1000 + voice * 0x100 + knob
                      for voice in range(8) for knob in range(8)]


def test_fm4_local_ids_have_dedicated_ui_object_addresses(fm4_assets):
    m = machine(fm4_assets)
    s = fm4_assets["main_syms"]
    donors = [192, 191, 192, 194, 191, 192, 194, 369]
    for k, donor in enumerate(donors):
        assert m.call(s["fm4m_ui_object"], [505 + k]) == s["fm4m_ui_objects"] + 84 * k
        assert struct.unpack(">I", fm4_assets["records"][k][32:36])[0] == 505 + k
    for pid in (0, 15, 16, 36, 43, 190, 504):
        assert m.call(s["fm4m_ui_object"], [pid]) == 0x41B9FA24 + 84 * pid
    assert m.call(s["fm4m_ui_object"], [513]) == 0x41B9FA24
