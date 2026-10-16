"""Offline OS 1.41 FM4 voice render checks without constructing a firmware image."""
import importlib.util
import struct
import sys
from pathlib import Path

import pytest

pytest.importorskip("unicorn")
from unicorn import Uc, UC_ARCH_M68K, UC_HOOK_CODE, UC_MODE_BIG_ENDIAN  # noqa: E402
from unicorn.m68k_const import UC_CPU_M68K_ANY, UC_M68K_REG_A7, UC_M68K_REG_SR  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools" / "fm4"))
import port  # noqa: E402

LOAD = 0x40000400
RET = 0x5000F000


@pytest.fixture(scope="module")
def voice_assets(tmp_path_factory):
    if not port.UPSTREAM.exists() or not port.TC.exists():
        pytest.skip("pinned FM4 source or ColdFire toolchain unavailable")
    assets = port.prepare(tmp_path_factory.mktemp("fm4-voice") / "work")
    spec = importlib.util.spec_from_file_location("fm4_s7patch", port.UPSTREAM / "patch/s7patch.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    stock = (ROOT / "unpacked/Syntakt_OS1.41/section_7_blob.raw").read_bytes()
    patched, prep, render = mod.patch(stock, assets["syn_blob"], assets["syn_stub"], 4)
    assert (prep, render) == (assets["syn_syms"]["syn_fm4_prep"],
                               assets["syn_syms"]["syn_fm4_render"])
    return assets, stock, patched


def voice_cpu(section, blob):
    uc = Uc(UC_ARCH_M68K, UC_MODE_BIG_ENDIAN, cpu=UC_CPU_M68K_ANY)
    for addr, size in ((0, 0x10000), (0x40000000, 0x100000),
                       (0x47000000, 0x10000), (0x50000000, 0x10000),
                       (0x80000000, 0x20000)):
        uc.mem_map(addr, size)
    uc.mem_write(LOAD, section)
    uc.mem_write(0x47000000, blob)
    uc.mem_write(RET, b"\x4e\x75")
    uc.reg_write(UC_M68K_REG_SR, 0x2700)
    return uc


def call(uc, entry, args):
    uc.mem_write(0x50008000, struct.pack(">" + "I" * (len(args) + 1), RET, *args))
    uc.reg_write(UC_M68K_REG_A7, 0x50008000)
    ticks = [0]
    hook = uc.hook_add(UC_HOOK_CODE, lambda *_: ticks.__setitem__(0, ticks[0] + 1))
    try:
        uc.emu_start(entry, RET, count=1_000_000)
    finally:
        uc.hook_del(hook)
    return ticks[0]


def test_algo_zero_matches_stock_tone_bit_exact(voice_assets):
    assets, stock, patched = voice_assets
    ref = voice_cpu(stock, assets["syn_blob"])
    fm4 = voice_cpu(patched, assets["syn_blob"])
    state, output = 0x80000000, 0x80010000
    for uc in (ref, fm4):
        uc.mem_write(state, bytes(0x708))
        uc.mem_write(output, bytes(128))
    call(ref, 0x40007214, [output, state])
    call(fm4, assets["syn_syms"]["syn_fm4_render"], [output, state])
    assert bytes(fm4.mem_read(output, 128)) == bytes(ref.mem_read(output, 128))
    assert bytes(fm4.mem_read(state, 0x708)) == bytes(ref.mem_read(state, 0x708))


def test_all_eleven_algorithms_render_distinct_blocks(voice_assets):
    assets, _, patched = voice_assets
    uc = voice_cpu(patched, assets["syn_blob"])
    s = assets["syn_syms"]
    state, params, output = 0x80010000, 0x80011000, 0x80012000
    blocks, ticks = [], []
    for algo in range(11):
        uc.mem_write(state, bytes(64))
        uc.mem_write(output, bytes(128))
        uc.mem_write(params, struct.pack(">Bx4I4ii4i", algo,
                     18_000_000, 27_000_000, 39_000_000, 51_000_000,
                     4096, 1750, 2200, 2800, 1000, 32767, 32767, 32767, 32767))
        call(uc, s["fm4_init"], [state])
        ticks.append(call(uc, s["fm4_render"], [state, params, output, 32]))
        block = bytes(uc.mem_read(output, 128))
        assert block != bytes(128), f"silent algorithm {algo + 1}"
        blocks.append(block)
    assert len(set(blocks)) == 11
    assert all(0 < n < 1_000_000 for n in ticks)
