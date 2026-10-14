"""Behavior checks on the complete maintenance image and preserved MAX image."""
import json
import struct
import sys
from pathlib import Path

import pytest
from unicorn import Uc, UC_ARCH_M68K, UC_MODE_BIG_ENDIAN, UC_HOOK_CODE
from unicorn.m68k_const import *

WORK = Path(__file__).resolve().parents[1]
ROOT = WORK.parents[1]
sys.path.insert(0, str(ROOT / "tools/unpack"))
import eft

LOAD, TABLE, OBJECTS = 0x40000400, 0x46010000, 0x46017000
NATIVE_DESC, NATIVE_OBJECTS = 0x4022d59c, 0x41b9fa24
RET, STACK = 0x5000f000, 0x50008000


@pytest.fixture(scope="module")
def images(tmp_path_factory):
    tmp = tmp_path_factory.mktemp("namespace-images")
    result = {}
    for name, file in [("new", WORK / "maintenance-validation.syx"),
                       ("max1", ROOT / "out/synthack-max.syx"),
                       ("stock", ROOT / "firmware/Syntakt_OS1.41.syx")]:
        result[name] = eft.unpack(file, tmp / name, ids=[3, 7])
    return result


class CPU:
    def __init__(self, raw, boot=True):
        uc = self.uc = Uc(UC_ARCH_M68K, UC_MODE_BIG_ENDIAN, cpu=UC_CPU_M68K_ANY)
        for start, size in [(0x40000000, 0x400000), (0x46000000, 0x20000),
                            (0x41b90000, 0x30000), (0x43bde000, 0x1000),
                            (0x444e0000, 0x10000), (0x80000000, 0x10000),
                            (0x50000000, 0x20000)]:
            uc.mem_map(start, size)
        uc.mem_write(LOAD, raw)
        uc.mem_write(RET, b"\x4e\x75")
        if boot:
            uc.reg_write(UC_M68K_REG_SR, 0x2700)
            uc.reg_write(UC_M68K_REG_A7, STACK)
            uc.emu_start(0x400004b2, 0x400004ba, count=2000000)

    def call(self, addr, args=(), stop=RET):
        sp = STACK - 4 * (len(args) + 1)
        self.uc.mem_write(sp, struct.pack(f">{len(args)+1}I", RET, *[v & 0xffffffff for v in args]))
        self.uc.reg_write(UC_M68K_REG_SR, 0x2700)
        self.uc.reg_write(UC_M68K_REG_A7, sp)
        self.uc.emu_start(addr, stop, count=200000)
        return self.uc.reg_read(UC_M68K_REG_D0) & 0xffffffff


def test_stock_descriptors_and_all_native_object_lookups_are_preserved(images):
    raw = images["new"][3].read_bytes()
    stock = images["stock"][3].read_bytes()
    m = CPU(raw)
    original = stock[NATIVE_DESC-LOAD:NATIVE_DESC-LOAD+505*52]
    retained = raw[NATIVE_DESC-LOAD:NATIVE_DESC-LOAD+505*52]
    assert bytes(m.uc.mem_read(TABLE, 505*52)) == retained
    for pid in range(505):
        if pid not in (72,90,100,125): # retained SND3, Deja Vu and dual-mono descriptor changes
            assert retained[pid*52:(pid+1)*52] == original[pid*52:(pid+1)*52],pid
    for pid in range(505):
        assert m.call(0x4007b9b2, [pid]) == NATIVE_OBJECTS + 84 * pid
        # Execute the firmware's real descriptor-group getter through its relocated base.
        expected = struct.unpack_from(">I", original, pid*52)[0]
        assert m.call(0x400a5c6c, [pid]) == expected
        assert m.call(0x400a5c4a, [pid]) == struct.unpack_from(">I",retained,pid*52+4)[0]
    for pid in (-1, 522, 10000):
        assert m.call(0x4007b9b2, [pid]) == NATIVE_OBJECTS
    assert m.call(0x4007b9b2, [505]) == OBJECTS
    assert m.call(0x4007b9b2, [521]) == OBJECTS + 16*84


def test_private_object_cloning_preserves_native_midi_and_alias_objects(images):
    m = CPU(images["new"][3].read_bytes())
    # Empty-capture function objects with distinguishable invokers. Copying is
    # performed by the actual OS std::function copier, not a host replacement.
    for pid in range(505):
        m.uc.mem_write(NATIVE_OBJECTS+pid*84, struct.pack(">I", pid % 13) +
                       b"".join(struct.pack(">4I", 0, 0, 0, 0x11110000+pid*5+k) for k in range(5)))
    before = bytes(m.uc.mem_read(NATIVE_OBJECTS, 505*84))
    manager = 0x5000e000
    m.uc.mem_write(manager,bytes.fromhex("70004e75"))
    send = struct.pack(">4I",0,0,manager,0x12345678)
    bar = struct.pack(">4I",0,0,manager,0x23456789)
    m.uc.mem_write(0x41b9dbd0,send)
    m.uc.mem_write(0x41b9d5d0,bar)
    m.call(0x4600f080)
    assert bytes(m.uc.mem_read(NATIVE_OBJECTS, 505*84)) == before
    types = [0,8,0,0,8,0,12] + [0]*10
    for i, expected in enumerate(types):
        assert struct.unpack(">I", m.uc.mem_read(OBJECTS+i*84,4))[0] == expected
    assert bytes(m.uc.mem_read(OBJECTS+13*84+36,16)) == send # FX3 DEL send graphic
    assert bytes(m.uc.mem_read(OBJECTS+13*84+68,16)) == bar
    fx = json.loads((WORK/"mods/fx3/patch.json").read_text())["symbols"]
    for i, name in enumerate(["type","spd","dep","del","fdbk","wid","vol","vol"]):
        invoker = struct.unpack(">I", m.uc.mem_read(OBJECTS+(7+i)*84+32,4))[0]
        assert invoker == int(fx["fx3_fmt_"+name],16)
    m.call(0x4600f080)
    assert bytes(m.uc.mem_read(NATIVE_OBJECTS,505*84)) == before


def test_all_descriptor_bounds_accept_private_ids(images):
    m=CPU(images["new"][3].read_bytes())
    spec=json.loads((WORK/"mods/private-params/patch.json").read_text())
    for p in spec["patches"]:
        if p.get("append") or not any(s in p["what"] for s in ("upper bound","last index","CMPA bound")):
            continue
        address=int(p["addr"],16)-2
        opcode=struct.unpack(">H",m.uc.mem_read(address,2))[0]
        limit=int(p["hex"],16)
        if opcode>>8==0x0c:
            register=UC_M68K_REG_D0+(opcode&7)
        else:
            register=UC_M68K_REG_A0+((opcode>>9)&7)
        next_bytes=bytes(m.uc.mem_read(address+6,4))
        m.uc.mem_write(address+6,bytes.fromhex("55c757c6")) # SCS d7; SEQ d6 materialize lazy flags
        for pid in (505,521,522):
            m.uc.reg_write(register,pid)
            m.uc.reg_write(UC_M68K_REG_SR,0x2700)
            m.uc.emu_start(address,address+10,count=3)
            assert bool(m.uc.reg_read(UC_M68K_REG_D7)&255)==(pid<limit),(hex(address),pid,limit)
            assert bool(m.uc.reg_read(UC_M68K_REG_D6)&255)==(pid==limit),(hex(address),pid,limit)
        m.uc.mem_write(address+6,next_bytes)


@pytest.mark.parametrize("fn,resume", [(0x4000d870,0x4000d878),
                                        (0x4000d94a,0x4000d950),
                                        (0x4000da32,0x4000da3a)])
def test_native_ids_resume_native_dispatch_with_identical_state(images,fn,resume):
    old, new = CPU(images["stock"][3].read_bytes(),boot=False), CPU(images["new"][3].read_bytes())
    for pid in [59,91,101,113,115,122,124,127,144,*range(246,270)]:
        states=[]
        for m in (old,new):
            m.uc.reg_write(UC_M68K_REG_D2,0x22222222)
            m.uc.reg_write(UC_M68K_REG_D3,0x33333333)
            m.call(fn,[0x50000100,pid,0x4000,1],resume)
            sp=m.uc.reg_read(UC_M68K_REG_A7)
            states.append((sp,bytes(m.uc.mem_read(sp,32)),*[m.uc.reg_read(r) for r in
                          (UC_M68K_REG_D1,UC_M68K_REG_D2,UC_M68K_REG_D3)]))
        assert states[0]==states[1],pid


def test_existing_compressor_storage_decodes_identically(images):
    old,new=CPU(images["max1"][3].read_bytes()),CPU(images["new"][3].read_bytes())
    for m in (old,new):
        m.uc.mem_write(0x800030bc,struct.pack(">I",0x50004000))
        m.uc.mem_write(0x50004000+70,bytes.fromhex("00000000012300002345000045675678"))
    for oldid,newid in zip([144,122,91,101,127],range(505,510)):
        assert old.call(0x4000d94a,[0x50000000,oldid]) == new.call(0x4000d94a,[0x50000000,newid])


def test_existing_fx3_storage_and_readbacks_match(images):
    old,new=CPU(images["max1"][3].read_bytes()),CPU(images["new"][3].read_bytes())
    for m in (old,new):
        m.uc.mem_write(0x800030bc,struct.pack(">I",0x50004000))
    for oldid,newid,value in zip([246,247,248,250,251,252,249,253],range(512,520),[2,32,48,71,23,86,19,91]):
        for m,pid in ((old,oldid),(new,newid)):
            m.call(0x4000da32,[0x50000000,pid,value<<8,1])
        assert old.call(0x4000d94a,[0x50000000,oldid]) == new.call(0x4000d94a,[0x50000000,newid])
        assert bytes(old.uc.mem_read(0x50004000,142)) == bytes(new.uc.mem_read(0x50004000,142))


def test_deja_vu_and_wave_bank_unchanged_from_max(images):
    old3,new3=images["max1"][3].read_bytes(),images["new"][3].read_bytes()
    for start,end in [(0x402b9b00,0x402bb780),(0x4031eba8,0x40320cdc)]:
        assert old3[start-LOAD:end-LOAD] == new3[start-LOAD:end-LOAD]
    assert images["max1"][7].read_bytes() == images["new"][7].read_bytes()
