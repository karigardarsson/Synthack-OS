"""Instruction-level test of staged SourcePageView encoder ID guards."""
import struct
import sys
from pathlib import Path

import pytest
from unicorn import UC_HOOK_CODE
from unicorn.m68k_const import (
    UC_M68K_REG_A0, UC_M68K_REG_A1, UC_M68K_REG_A2, UC_M68K_REG_A7,
    UC_M68K_REG_D0, UC_M68K_REG_D1, UC_M68K_REG_D2, UC_M68K_REG_D3, UC_M68K_REG_PC, UC_M68K_REG_SR,
)

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "tools" / "fm4"), str(ROOT / "tests")]
import port  # noqa: E402
from test_fx3 import Machine  # noqa: E402


@pytest.fixture(scope="module")
def assets(tmp_path_factory):
    if not port.UPSTREAM.exists() or not port.TC.exists():
        pytest.skip("pinned FM4 source or ColdFire toolchain unavailable")
    return port.prepare(tmp_path_factory.mktemp("fm4-page-guard") / "work")


def test_actual_guards_accept_only_fm4_page_two(assets):
    raw = (ROOT / "unpacked/Syntakt_OS1.41/section_3_MAIN_OS.bin").read_bytes()
    patches = port.scoped_id_guard_patches(raw, assets)
    assert [int(p["addr"], 16) for p in patches] == [0x4003B8D4, 0x4003B6BE]
    m = Machine()
    m.uc.mem_write(port.MAIN, assets["main_blob"])
    for patch in patches:
        m.uc.mem_write(int(patch["addr"], 16), bytes.fromhex(patch["hex"]))
    view = 0x50001000
    fixed = {UC_M68K_REG_D1: 0x12003456, UC_M68K_REG_A0: 0x50003000,
             UC_M68K_REG_A1: 0x50004000, UC_M68K_REG_A2: view}
    for begin, end in ((0x4003B8D4, 0x4003B8DE), (0x4003B6BE, 0x4003B6CC)):
        for vptr, page, pid, expected in (
            (0x401CA0DC, 1, 505, 505),  # ALGO
            (0x401CA0DC, 1, 512, 512),  # DET
            (0x401CA0DC, 0, 505, 0),
            (0x401CA0DC, 2, 512, 0),
            (0x401C9B00, 1, 505, 0),
            (0x401CA0DC, 1, 504, 504),
            (0x401CA0DC, 1, 513, 0),
            (0x401CA0DC, 1, 0xFFFFFFFF, 0),
        ):
            m.uc.mem_write(view, struct.pack(">I", vptr))
            m.uc.mem_write(view + 0x90, struct.pack(">I", page))
            for reg, val in fixed.items():
                m.uc.reg_write(reg, val)
            m.uc.reg_write(UC_M68K_REG_D2, pid)
            m.uc.reg_write(UC_M68K_REG_D0, pid)
            m.uc.reg_write(UC_M68K_REG_SR, 0x2700)
            m.uc.reg_write(UC_M68K_REG_A7, 0x50008000)
            m.uc.emu_start(begin, end, count=200)
            assert m.uc.reg_read(UC_M68K_REG_D0) == expected
            assert m.uc.reg_read(UC_M68K_REG_D2) == pid
            assert m.uc.reg_read(UC_M68K_REG_A7) == 0x50008000
            assert m.uc.reg_read(UC_M68K_REG_SR) & 0xFF00 == 0x2700
            for reg, val in fixed.items():
                assert m.uc.reg_read(reg) == val


def test_scoped_metadata_matches_every_native_id_and_routes_all_fm4_values(assets):
    raw = (ROOT / "unpacked/Syntakt_OS1.41/section_3_MAIN_OS.bin").read_bytes()
    patches = port.scoped_ui_metadata_patches(raw, assets)
    assert len(patches) == 7
    stock, staged = Machine(), Machine()
    staged.uc.mem_write(port.MAIN, assets["main_blob"])
    for patch in patches:
        staged.uc.mem_write(int(patch["addr"], 16), bytes.fromhex(patch["hex"]))
    s = assets["main_syms"]
    for pid in range(505):
        assert staged.call(s["fm4m_ui_lix"], [pid]) == stock.call(0x400A5C4A, [pid])
        assert staged.call(s["fm4m_ui_track_param"], [pid]) == stock.call(0x400A61A4, [pid])
    for k in range(8):
        pid = 505 + k
        assert staged.call(s["fm4m_ui_lix"], [pid]) == 0x36 + k
        assert staged.call(s["fm4m_ui_track_param"], [pid]) == 1
    for pid in (513, 0xFFFFFFFF):
        assert staged.call(s["fm4m_ui_lix"], [pid]) == stock.call(0x400A5C4A, [pid])
        assert staged.call(s["fm4m_ui_track_param"], [pid]) == stock.call(0x400A61A4, [pid])
    for patch in patches:
        site = int(patch["addr"], 16)
        pid = 512
        staged.uc.reg_write(UC_M68K_REG_SR, 0x2700)
        staged.uc.reg_write(UC_M68K_REG_A7, 0x50008000)
        staged.uc.mem_write(0x50008000, struct.pack(">I", pid))
        staged.uc.emu_start(site, site + 6, count=200)
        assert staged.uc.reg_read(UC_M68K_REG_D0) == (1 if site == 0x40037EFA else 0x3D)
        assert staged.uc.reg_read(UC_M68K_REG_A7) == 0x50008000


def test_local_ui_objects_use_native_manager_clone_and_do_not_alias_donors(assets):
    m = Machine()
    m.uc.mem_write(port.MAIN, assets["main_blob"])
    s = assets["main_syms"]
    donors = (192, 191, 192, 194, 191, 192, 194, 369)
    manager = 0x5000F100
    m.uc.mem_write(manager, b"\x4e\x75")
    originals = {}
    for donor in set(donors):
        addr = 0x41B9FA24 + 84 * donor
        row = bytearray(84)
        struct.pack_into(">5I", row, 0, *(0x10000000 + donor + j for j in range(5)))
        for j in range(4):
            struct.pack_into(">4I", row, 20 + 16 * j,
                             0x20000000 + donor + j, 0x30000000 + j,
                             manager, 0x40077000 + j)
        m.uc.mem_write(addr, bytes(row))
        originals[donor] = bytes(row)
    operations = []

    def clone_callback(uc, addr, size, user):
        if addr != manager:
            return
        sp = uc.reg_read(UC_M68K_REG_A7)
        dst, src, op = struct.unpack(">3I", uc.mem_read(sp + 4, 12))
        operations.append((dst, src, op))
        uc.mem_write(dst, bytes(uc.mem_read(src, 8)))

    hook = m.uc.hook_add(UC_HOOK_CODE, clone_callback)
    try:
        assert m.call(s["fm4m_ui_object"], [505]) == s["fm4m_ui_objects"]
    finally:
        m.uc.hook_del(hook)
    assert len(operations) == 32
    assert all(op == 2 for _, _, op in operations)
    assert struct.unpack(">I", m.uc.mem_read(s["fm4m_objects_ready"], 4))[0] == 1
    for k, donor in enumerate(donors):
        local = s["fm4m_ui_objects"] + 84 * k
        assert bytes(m.uc.mem_read(local, 84)) == originals[donor]
        assert bytes(m.uc.mem_read(0x41B9FA24 + 84 * donor, 84)) == originals[donor]
    m.uc.mem_write(s["fm4m_ui_objects"] + 20, struct.pack(">I", 0xDEADBEEF))
    assert bytes(m.uc.mem_read(0x41B9FA24 + 84 * 192, 84)) == originals[192]
    assert struct.unpack(">I", m.uc.mem_read(s["fm4m_ui_objects"] + 2 * 84 + 20, 4))[0] != 0xDEADBEEF


def test_identified_ui_object_calls_use_private_objects_without_native_aliases(assets):
    raw = (ROOT / "unpacked/Syntakt_OS1.41/section_3_MAIN_OS.bin").read_bytes()
    patches = port.scoped_ui_object_patches(raw, assets)
    assert [int(p["addr"], 16) for p in patches] == [
        0x40038060, 0x40038580, 0x40038BF8, 0x4003B96E, 0x40043526]
    stock, staged = Machine(), Machine()
    staged.uc.mem_write(port.MAIN, assets["main_blob"])
    for patch in patches:
        staged.uc.mem_write(int(patch["addr"], 16), bytes.fromhex(patch["hex"]))
    fn = assets["main_syms"]["fm4m_ui_object"]
    for pid in range(505):
        assert staged.call(fn, [pid]) == stock.call(0x4007B9B2, [pid])
    for k in range(8):
        assert staged.call(fn, [505 + k]) == assets["main_syms"]["fm4m_ui_objects"] + 84 * k
    for pid in (513, 0xFFFFFFFF):
        assert staged.call(fn, [pid]) == stock.call(0x4007B9B2, [pid])
    for callsite in (0x4003857E, 0x4003B96C, 0x40043524):
        staged.uc.reg_write(UC_M68K_REG_SR, 0x2700)
        staged.uc.reg_write(UC_M68K_REG_A7, 0x50008000)
        staged.uc.mem_write(0x50008000, struct.pack(">I", 505))
        staged.uc.emu_start(callsite, callsite + 6, count=200)
        assert staged.uc.reg_read(UC_M68K_REG_D0) == assets["main_syms"]["fm4m_ui_objects"]
        assert staged.uc.reg_read(UC_M68K_REG_A7) == 0x50008000


def test_page_local_ranges_delegate_native_and_cover_algo_det(assets):
    raw = (ROOT / "unpacked/Syntakt_OS1.41/section_3_MAIN_OS.bin").read_bytes()
    patches = port.scoped_ui_range_patches(raw, assets)
    assert [int(p["addr"], 16) for p in patches] == [0x4003804E, 0x4003B156, 0x40042876]
    stock, staged = Machine(), Machine()
    staged.uc.mem_write(port.MAIN, assets["main_blob"])
    for patch in patches:
        staged.uc.mem_write(int(patch["addr"], 16), bytes.fromhex(patch["hex"]))
    fn = assets["main_syms"]["fm4m_range_guard"]
    out = 0x50001000
    for pid in range(505):
        stock.uc.mem_write(out, b"\xaa" * 12)
        staged.uc.mem_write(out, b"\xaa" * 12)
        assert staged.call(fn, [pid], {UC_M68K_REG_A0: out}) == stock.call(0x400A62C8, [pid], {UC_M68K_REG_A0: out})
        assert bytes(staged.uc.mem_read(out, 12)) == bytes(stock.uc.mem_read(out, 12))
    for k, rec in enumerate(assets["records"]):
        staged.uc.mem_write(out, b"\xaa" * 12)
        assert staged.call(fn, [505+k], {UC_M68K_REG_A0: out}) == out
        assert struct.unpack(">3I", staged.uc.mem_read(out, 12)) == struct.unpack_from(">3I", rec, 8)
    for site in (0x4003804E, 0x4003B156, 0x40042876):
        staged.uc.mem_write(out, b"\xaa" * 12)
        staged.uc.reg_write(UC_M68K_REG_A0, out)
        staged.uc.reg_write(UC_M68K_REG_SR, 0x2700)
        staged.uc.reg_write(UC_M68K_REG_A7, 0x50008000)
        staged.uc.mem_write(0x50008000, struct.pack(">I", 505))
        staged.uc.emu_start(site, site+6, count=200)
        assert struct.unpack(">3I", staged.uc.mem_read(out, 12)) == (0, 0x0B00, 0)
        assert staged.uc.reg_read(UC_M68K_REG_A7) == 0x50008000


def test_post_edit_redraw_guard_keeps_native_bound_and_scopes_fm4(assets):
    raw = (ROOT / "unpacked/Syntakt_OS1.41/section_3_MAIN_OS.bin").read_bytes()
    patch = port.scoped_post_edit_guard_patch(raw, assets)
    assert int(patch["addr"], 16) == 0x4003BAAE
    stock, staged = Machine(), Machine()
    staged.uc.mem_write(port.MAIN, assets["main_blob"])
    staged.uc.mem_write(0x4003BAAE, bytes.fromhex(patch["hex"]))
    view = 0x50001000
    for m in (stock, staged):
        m.uc.mem_write(view, struct.pack(">I", 0x401CA0DC))
    for pid, page in ((0, 1), (504, 1), (505, 0), (505, 1), (512, 1), (513, 1)):
        for m in (stock, staged):
            m.uc.mem_write(view + 0x90, struct.pack(">I", page))
            m.uc.reg_write(UC_M68K_REG_SR, 0x2700)
            m.uc.reg_write(UC_M68K_REG_A7, 0x50008000)
            m.uc.reg_write(UC_M68K_REG_A2, view)
            m.uc.reg_write(UC_M68K_REG_D0, 0x12345678)
            m.uc.reg_write(UC_M68K_REG_D2, pid)
            stops = []
            def on_code(uc, addr, size, user):
                if addr in (0x4003BAB8, 0x4003BB76):
                    stops.append(addr)
                    uc.emu_stop()
            h = m.uc.hook_add(UC_HOOK_CODE, on_code)
            try:
                m.uc.emu_start(0x4003BAAE, 0x4003BB78, count=1000)
            finally:
                m.uc.hook_del(h)
            assert stops
            expected = 0x4003BAB8 if pid <= 504 or (m is staged and page == 1 and 505 <= pid <= 512) else 0x4003BB76
            assert stops == [expected]
            assert m.uc.reg_read(UC_M68K_REG_D0) == 0x12345678
            assert m.uc.reg_read(UC_M68K_REG_D2) == pid
            assert m.uc.reg_read(UC_M68K_REG_A7) == 0x50008000


def test_key_and_notification_guards_are_page_scoped(assets):
    raw = (ROOT / "unpacked/Syntakt_OS1.41/section_3_MAIN_OS.bin").read_bytes()
    key = port.scoped_key_guard_patch(raw, assets)
    notify = port.scoped_notify_guard_patch(raw, assets)
    stock, staged = Machine(), Machine()
    staged.uc.mem_write(port.MAIN, assets["main_blob"])
    for patch in (key, notify):
        staged.uc.mem_write(int(patch["addr"], 16), bytes.fromhex(patch["hex"]))
    view = 0x50001000
    for m in (stock, staged):
        m.uc.mem_write(view, struct.pack(">I", 0x401CA0DC))
    for pid, page in ((0, 1), (504, 1), (505, 0), (505, 1), (512, 1), (513, 1)):
        for m in (stock, staged):
            m.uc.mem_write(view + 0x90, struct.pack(">I", page))
            m.uc.reg_write(UC_M68K_REG_SR, 0x2700)
            m.uc.reg_write(UC_M68K_REG_A7, 0x50008000)
            m.uc.reg_write(UC_M68K_REG_A2, view)
            m.uc.reg_write(UC_M68K_REG_D0, 0x12345678)
            m.uc.reg_write(UC_M68K_REG_D3, pid)
            stops = []
            def on_code(uc, addr, size, user):
                if addr in (0x4003BDC0, 0x4003C2B0):
                    stops.append(addr)
                    uc.emu_stop()
            h = m.uc.hook_add(UC_HOOK_CODE, on_code)
            try:
                m.uc.emu_start(0x4003BDB6, 0x4003C2B2, count=1000)
            finally:
                m.uc.hook_del(h)
            assert stops == [0x4003BDC0 if pid <= 504 or (m is staged and page == 1 and 505 <= pid <= 512) else 0x4003C2B0]
            assert m.uc.reg_read(UC_M68K_REG_D0) == 0x12345678
            assert m.uc.reg_read(UC_M68K_REG_D3) == pid
            assert m.uc.reg_read(UC_M68K_REG_A7) == 0x50008000
    for pid, page, expected in ((504, 1, 504), (505, 0, 0), (505, 1, 505), (512, 1, 512), (513, 1, 0)):
        staged.uc.mem_write(view + 0x90, struct.pack(">I", page))
        staged.uc.reg_write(UC_M68K_REG_SR, 0x2700)
        staged.uc.reg_write(UC_M68K_REG_A7, 0x50008000)
        staged.uc.reg_write(UC_M68K_REG_A2, view)
        staged.uc.reg_write(UC_M68K_REG_D0, pid)
        staged.uc.emu_start(0x4003C634, 0x4003C63E, count=200)
        assert staged.uc.reg_read(UC_M68K_REG_D0) == expected
        assert staged.uc.reg_read(UC_M68K_REG_A7) == 0x50008000


def test_stock_model_getters_and_adjuster_still_block_new_ids():
    # Actual OS routines: descriptor/object shims alone do not provide values.
    m = Machine()
    for fn in (0x40011B18, 0x40011FBC):
        for pid in range(505, 513):
            assert m.call(fn, [0x50001000, pid]) == 0
    for pid in range(505, 513):
        assert m.call(0x40012316, [0x50001000, pid, 0x4000, 0x100]) == 0x4000
