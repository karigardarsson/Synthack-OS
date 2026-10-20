"""Mod master-comp: routine ColdFire vs modello (dsp.py), interfaccia, salvataggio.

Esegue sull'OS Syntakt patchato il tratto 0x4009053E..0x40090562 (trampolino + comp_hook) a ogni
"blocco", con segnali finti sugli ADC 6/7, e le funzioni centrali dei parametri agganciate.
Serve l'OS Syntakt 1.41 (saltato se manca).
"""

import json
import math
import random
import struct
import sys
from pathlib import Path

import pytest

pytest.importorskip("unicorn")
from unicorn import UC_ARCH_M68K, UC_HOOK_CODE, UC_MODE_BIG_ENDIAN, Uc  # noqa: E402
from unicorn.m68k_const import (UC_CPU_M68K_ANY, UC_M68K_REG_A3, UC_M68K_REG_A7,  # noqa: E402
                                UC_M68K_REG_D0, UC_M68K_REG_D1, UC_M68K_REG_D2, UC_M68K_REG_D3,
                                UC_M68K_REG_SR)

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "tools" / "build"), str(ROOT / "tools" / "emu"), str(ROOT / "tools" / "unpack"), str(ROOT / "mods" / "master-comp")]
import eft  # noqa: E402
import modarea_layout  # noqa: E402
from emac import UnicornEmac  # noqa: E402

MA = modarea_layout.RAM                                    # area mod (mods/modarea)
MA_PAGE, MA_MAP = 0x444E_0000, 0x2_0000                     # area mod e radice dell'interfaccia (0x444E1334)
assert MA_PAGE <= MA and MA + modarea_layout.SIZE <= MA_PAGE + MA_MAP

SY = ROOT / "firmware" / "Syntakt_OS1.41.syx"
SPEC_F = ROOT / "mods" / "master-comp" / "patch.json"
pytestmark = pytest.mark.skipif(not (SY.exists() and SPEC_F.exists()), reason="OS Syntakt o patch assenti")

LOAD = 0x4000_0400
HOOK, AFTER = 0x4009_053E, 0x4009_0562
ADC_L, ADC_R = 0x8000_3C50, 0x8000_3CD0
HW, STACK, RET = 0x5000_2000, 0x5001_0000, 0x5000_8000
FX_SLOTS = 0x41B9_F950
PROJECT_PTR, PROJECT, ACTIVE_TRACK = 0x444E_13F4, 0x5000_7000, 0x4001_FF74
DRAW, DRAW_CONT = 0x4003_A244, 0x4003_A24C
KIT_PTR, KIT, KIT_BLK = 0x8000_30BC, 0x5000_4000, 70
GLOB_BLK, GLOBAL_FLAGS = 0x41B9_D3B0, 0x43BD_E444
WOFF = {"THR": 12, "ATK": 14, "REL": 2, "MUP": 8}      # parole nel blocco esterno
UI_ROOT, UI = 0x444E_1334, 0x5000_A000
IDS = {"THR": 262, "ATK": 263, "REL": 264, "MUP": 265, "RAT": 266, "GR": 267, "COMP": 268}
OLD_IDS = (144, 122, 91, 101, 127, 59, 115)               # alias dell'OS usati fino alla v0.8
RAT_STEP = 0xFE0
OBJS = 0x41B9_FA24
GET, SET, KIT_FN = 0x4000_D94A, 0x4000_DA32, 0x4000_D870
REGS = [getattr(__import__("unicorn.m68k_const", fromlist=["x"]), f"UC_M68K_REG_{r}")
        for r in ("D0", "D2", "D4", "D5", "D6", "D7", "A0", "A1", "A2", "A4", "A5")]


@pytest.fixture(scope="module")
def setup():
    spec = json.loads(SPEC_F.read_text(encoding="utf-8"))
    sec3 = eft.unpack(SY, ROOT / "unpacked" / SY.stem, ids=[3])[3].read_bytes()
    return spec, sec3, None


class Machine:
    def __init__(self, spec, sec3, kit=True):
        uc = self.uc = Uc(UC_ARCH_M68K, UC_MODE_BIG_ENDIAN, cpu=UC_CPU_M68K_ANY)
        uc.mem_map(0x4000_0000, 0x0040_0000)
        uc.mem_write(LOAD, sec3)
        uc.mem_map(MA_PAGE, MA_MAP)                      # area mod (dopo la rilocazione)
        vp = json.loads((ROOT / "mods" / "vparams" / "patch.json").read_text(encoding="utf-8"))
        for p in spec["patches"] + vp["patches"]:          # i parametri virtuali passano da vparams
            dst = int(p["ram"], 16) if p.get("append") else int(p["addr"], 16)
            uc.mem_write(dst, bytes.fromhex(p["hex"]))
        uc.mem_map(0x8000_0000, 0x1_0000)
        uc.mem_map(0x5000_0000, 0x2_0000)
        uc.mem_map(0x41B9_D000, 0xA000)                     # globale, pagine, oggetti (BSS, fino a id 268)
        uc.mem_map(0x43BD_E000, 0x1000)                     # bit global
        uc.mem_write(FX_SLOTS, struct.pack(">8i", 0, 0, 0, 0, 0, 0, 0, 150))
        uc.mem_write(PROJECT_PTR, struct.pack(">I", PROJECT))
        uc.mem_write(ACTIVE_TRACK, bytes((0x70, 12, 0x4e, 0x75)))  # moveq #12,d0 ; rts
        uc.mem_write(KIT_PTR, struct.pack(">I", KIT if kit else 0))
        uc.mem_write(RET, b"\x4e\x75")
        self.emac = UnicornEmac(uc, [int(a, 16) for a in spec.get("emac_sites", [])])

    def block(self, left, right, cv_l, cv_r, macsr=0x20):
        uc = self.uc
        uc.mem_write(ADC_L, struct.pack(">32i", *left))
        uc.mem_write(ADC_R, struct.pack(">32i", *right))
        uc.mem_write(HW, bytes(128))
        self.emac.state.load_macsr(macsr)
        uc.reg_write(UC_M68K_REG_SR, 0x2700)
        uc.reg_write(UC_M68K_REG_A7, STACK)
        uc.reg_write(UC_M68K_REG_A3, HW)
        uc.reg_write(UC_M68K_REG_D1, cv_l)
        uc.reg_write(UC_M68K_REG_D3, cv_r)
        marks = [0x1111_0000 + i for i in range(len(REGS))]
        for r, v in zip(REGS, marks):
            uc.reg_write(r, v)
        uc.emu_start(HOOK, AFTER, count=200_000)
        assert self.emac.error is None, self.emac.error
        assert [uc.reg_read(r) & 0xFFFFFFFF for r in REGS] == marks       # registri preservati
        assert uc.reg_read(UC_M68K_REG_A7) == STACK
        assert self.emac.state.macsr == macsr                              # MACSR ripristinato
        assert self.emac.state.acc[0] == 0                                 # accumulatore pulito
        return struct.unpack_from(">2H", uc.mem_read(HW + 70, 4))

    def call(self, fn, args, stop=RET):
        uc = self.uc
        sp = STACK - 4 * (len(args) + 1)
        uc.mem_write(sp, struct.pack(f">{len(args) + 1}I", RET, *[a & 0xFFFFFFFF for a in args]))
        uc.reg_write(UC_M68K_REG_SR, 0x2700)
        uc.reg_write(UC_M68K_REG_A7, sp)
        uc.emu_start(fn, stop, count=10_000)
        assert self.emac.error is None, self.emac.error
        return uc.reg_read(UC_M68K_REG_D0) & 0xFFFFFFFF

    def get(self, name):
        return self.call(GET, [0x5000_0000, IDS[name]])

    def set(self, name, value):
        self.call(SET, [0x5000_0000, IDS[name], value, 1])

    def words(self, addr):
        return struct.unpack(">I", self.uc.mem_read(addr, 4))[0]


def reduction(m):
    """Riduzione mostrata dal misuratore GR: la barra e' piena a 0 dB e si svuota."""
    return 0x7F00 - m.get("GR")


def preset_of(spec):
    v = [int(x, 16) for x in spec["params"]]
    return {"THR": v[0], "ATK": v[1], "REL": v[2], "MUP": v[3], "RAT": v[4] * RAT_STEP}


def model(_, p):
    from dsp import Compact, Preset
    return Compact(Preset(p["THR"], p["ATK"], p["REL"], p["MUP"], p["RAT"] // RAT_STEP - 1))


def signal(rnd, n_blocks):
    ph = 0
    for _ in range(n_blocks):
        amp = 10 ** (rnd.uniform(-70, 0) / 20)
        f = rnd.choice([55, 220, 1000, 5000])
        left = [int(amp * 0.999 * 2**31 * math.sin(2 * math.pi * f * (ph + i) / 48000)) for i in range(32)]
        right = [int(v * rnd.uniform(-1, 1)) for v in left]
        ph += 32
        yield left, right


def expected(g, cv):
    cv = min(cv, 65535)
    return min(65535, (cv * g) >> 12)


# ----------------------------------------------------------------------------- default e spento
def test_new_kit_reads_preset_and_compressor_is_off(setup):
    spec, sec3, _ = setup
    m = Machine(spec, sec3)
    p = preset_of(spec)
    for k in ("THR", "ATK", "REL", "MUP"):
        assert m.get(k) == p[k]                     # due parole a zero = preset
    assert m.get("RAT") == 0                         # ... con compressore spento
    loud = [int(0.9 * 2**31 * math.sin(2 * math.pi * 200 * i / 48000)) for i in range(32)]
    for _ in range(20):
        assert m.block(loud, loud, 30000, 70000) == (30000, 65535)   # CV originali (limitati)
    assert reduction(m) == 0


# ----------------------------------------------------------------------------- compressore acceso
def test_matches_compact_model_bit_exact(setup):
    spec, sec3, dt = setup
    m = Machine(spec, sec3)
    p = preset_of(spec)
    m.set("RAT", p["RAT"])
    mod = model(dt, p)
    rnd = random.Random(7)
    for left, right in signal(rnd, 300):
        cv_l, cv_r = rnd.randrange(0, 70000), rnd.randrange(0, 70000)
        got = m.block(left, right, cv_l, cv_r)
        g = mod.block(left, right)
        assert got == (expected(g, cv_l), expected(g, cv_r))


def test_parameters_change_the_compressor_like_the_model(setup):
    spec, sec3, dt = setup
    rnd = random.Random(11)
    for _ in range(6):
        p = {k: rnd.randrange(0, 0x80) << 8 for k in ("THR", "ATK", "REL", "MUP")}
        p["RAT"] = rnd.randrange(1, 9) * RAT_STEP
        m = Machine(spec, sec3)
        for k, v in p.items():
            m.set(k, v)
            assert m.get(k) == v
        mod = model(dt, p)
        for left, right in signal(rnd, 40):
            got = m.block(left, right, 40000, 40000)
            assert got == (expected(mod.block(left, right), 40000),) * 2


def test_loud_signal_reduces_cv_and_meter_shows_it(setup):
    spec, sec3, _ = setup
    m = Machine(spec, sec3)
    m.set("RAT", 8 * RAT_STEP)                       # 20:1
    loud = [int(0.9 * 2**31 * math.sin(2 * math.pi * 200 * i / 48000)) for i in range(32)]
    quiet = m.block([0] * 32, [0] * 32, 30000, 30000)[0]
    for _ in range(200):
        got = m.block(loud, loud, 30000, 30000)[0]
    assert got < quiet / 2
    gr = reduction(m)
    assert 0x1000 < gr <= 0x7F00                     # riduzione di qualche dB visibile
    m.set("GR", 0)                                   # sola lettura: ignorato
    assert reduction(m) == gr


# ----------------------------------------------------------------------------- salvataggio
def test_values_live_in_the_pattern_kit_words(setup):
    spec, sec3, _ = setup
    m = Machine(spec, sec3)
    d = preset_of(spec)
    m.set("THR", 0x1234)
    m.set("RAT", 3 * RAT_STEP)                       # 3 = 0b0011: bit 15 di THR e ATK
    w = {k: struct.unpack(">H", m.uc.mem_read(KIT + KIT_BLK + o, 2))[0] for k, o in WOFF.items()}
    assert w["THR"] & 0x7FFF == 0x1234 ^ d["THR"]
    assert [w[k] >> 15 for k in ("THR", "ATK", "REL", "MUP")] == [1, 1, 0, 0]
    assert all(w[k] & 0x7FFF == 0 for k in ("ATK", "REL", "MUP"))      # default -> 0
    assert bytes(m.uc.mem_read(GLOB_BLK, 18)) == bytes(18)             # il globale non e' toccato
    for o in (12, 14, 2, 8):                         # altro kit (parole a zero) -> default, spento
        m.uc.mem_write(KIT + KIT_BLK + o, bytes(2))
    assert m.get("THR") == d["THR"] and m.get("RAT") == 0


def test_full_resolution_is_kept(setup):
    spec, sec3, _ = setup
    m = Machine(spec, sec3)
    for k in ("THR", "ATK", "REL", "MUP"):
        for v in (0x0001, 0x1234, 0x3F7F, 0x7EFF, 0x7F00):
            m.set(k, v)
            assert m.get(k) == v


def test_syn_global_uses_the_global_words(setup):
    spec, sec3, _ = setup
    m = Machine(spec, sec3)
    m.set("MUP", 0x7F00)
    m.uc.mem_write(GLOBAL_FLAGS, struct.pack(">I", 4))          # SYN global
    assert m.get("MUP") == preset_of(spec)["MUP"]                # globale ancora a zero = default
    m.set("MUP", 0x0512)
    assert m.get("MUP") == 0x0512
    m.uc.mem_write(GLOBAL_FLAGS, struct.pack(">I", 0))
    assert m.get("MUP") == 0x7F00                                # il kit ha il suo valore
    assert bytes(m.uc.mem_read(GLOB_BLK + WOFF["MUP"], 2)) != bytes(2)


def test_no_kit_yet_uses_ram_fallback(setup):
    spec, sec3, _ = setup
    m = Machine(spec, sec3, kit=False)
    m.set("REL", 0x3300)
    assert m.get("REL") == 0x3300


def test_set_clamps_to_range(setup):
    spec, sec3, _ = setup
    m = Machine(spec, sec3)
    m.set("RAT", 0x7FFF)
    assert m.get("RAT") == 0x7F00
    m.set("ATK", -5)
    assert m.get("ATK") == 0
    m.set("THR", 0x7FFF)
    assert m.get("THR") == 0x7F00


# ----------------------------------------------------------------------------- integrazione OS
def test_our_ids_are_kit_params(setup):
    spec, sec3, _ = setup
    m = Machine(spec, sec3)
    for i in IDS.values():
        assert m.call(KIT_FN, [0x5000_0000, i]) == 1


@pytest.mark.parametrize("fn,resume", [(KIT_FN, 0x4000_D878), (GET, 0x4000_D950), (SET, 0x4000_DA3A)])
def test_other_ids_resume_original_code_identically(setup, fn, resume):
    """Per un id non nostro lo stato alla ripresa e' lo stesso dell'OS originale."""
    spec, sec3, _ = setup
    states = []
    for patched in (False, True):
        m = Machine(spec if patched else {"patches": [], "emac_sites": []}, sec3)
        uc = m.uc
        uc.reg_write(UC_M68K_REG_D2, 0x2222_2222)
        uc.reg_write(UC_M68K_REG_D3, 0x3333_3333)
        m.call(fn, [0x5000_0100, 126, 0x4000, 1], resume)
        sp = uc.reg_read(UC_M68K_REG_A7)
        states.append((sp, bytes(uc.mem_read(sp, 32)), uc.reg_read(UC_M68K_REG_D1), uc.reg_read(UC_M68K_REG_D2),
                       uc.reg_read(UC_M68K_REG_D3)))
    assert states[0] == states[1]


@pytest.mark.parametrize("fn,resume", [(GET, 0x4000_D950), (SET, 0x4000_DA3A)])
def test_midi_ids_resume_native_get_set_without_compressor_dispatch(setup, fn, resume):
    """IDs 262..268 remain native parameter routes when the selected page is MIDI."""
    spec, sec3, _ = setup
    states = []
    for patched in (False, True):
        m = Machine(spec if patched else {"patches": [], "emac_sites": []}, sec3)
        # The stock selector is a tiny function in the fixture: choose a MIDI track.
        m.uc.mem_write(ACTIVE_TRACK, bytes((0x70, 11, 0x4e, 0x75)))
        m.uc.ctl_flush_tb()
        m.call(fn, [0x5000_0100, 262, 0x4000, 1], resume)
        sp = m.uc.reg_read(UC_M68K_REG_A7)
        states.append((sp, bytes(m.uc.mem_read(sp, 32)), m.uc.reg_read(UC_M68K_REG_D1),
                       m.uc.reg_read(UC_M68K_REG_D2), m.uc.reg_read(UC_M68K_REG_D3)))
    assert states[0] == states[1]


def set_active_track(m, spec, track):
    m.uc.mem_write(ACTIVE_TRACK, bytes((0x70, track & 0xff, 0x4e, 0x75)))
    m.uc.ctl_flush_tb()
    return m.call(int(spec["symbols"]["comp_active_context"], 16), [])


def test_fx_context_claims_the_knobs_without_a_boot_page_patch(setup):
    spec, sec3, _ = setup
    m = Machine(spec, sec3)
    m.uc.mem_write(FX_SLOTS, struct.pack(">8i", 0, 0, 0, 0, 0, 0, 0, 150))
    assert set_active_track(m, spec, 12) == 1
    assert list(struct.unpack(">8i", m.uc.mem_read(FX_SLOTS, 32))) == [*IDS.values(), 150]
    sec = {int(p["addr"], 16): p for p in spec["patches"] if not p.get("append")}
    vp = json.loads((ROOT / "mods" / "vparams" / "patch.json").read_text(encoding="utf-8"))
    vp_sec = {int(p["addr"], 16): p for p in vp["patches"] if not p.get("append")}
    assert 0x4019_5156 not in sec
    assert DRAW not in sec and DRAW in vp_sec


def invoke_draw(m):
    m.uc.ctl_flush_tb()
    m.uc.mem_write(STACK - 4, struct.pack(">I", RET))
    m.uc.reg_write(UC_M68K_REG_SR, 0x2700)
    m.uc.reg_write(UC_M68K_REG_A7, STACK - 4)
    m.uc.emu_start(DRAW, DRAW_CONT, count=100_000)
    assert m.uc.reg_read(UC_M68K_REG_A7) == STACK - 4 - 80


def test_midi_context_restores_native_compressor_ids_and_slots(setup):
    """The MIDI page receives its exact stock descriptor/object/slot state back."""
    spec, sec3, _ = setup
    m = Machine(spec, sec3)
    before = {}
    for pos, ident in enumerate(IDS.values()):
        desc = 0x4022_D59C + 52 * ident
        obj = OBJS + 84 * ident
        d = bytes((pos + i) & 0xff for i in range(52))
        o = bytes((0x80 + pos + i) & 0xff for i in range(84))
        m.uc.mem_write(desc, d)
        m.uc.mem_write(obj, o)
        before[desc] = d
        before[obj] = o
    slots = struct.pack(">8I", *(0x11110000 + i for i in range(8)))
    m.uc.mem_write(FX_SLOTS, slots)

    set_active_track(m, spec, 12)
    assert bytes(m.uc.mem_read(FX_SLOTS, 32)) != slots
    assert set_active_track(m, spec, 11) == 0
    assert bytes(m.uc.mem_read(FX_SLOTS, 32)) == slots
    for addr, original in before.items():
        assert bytes(m.uc.mem_read(addr, len(original))) == original


def test_draw_hook_claims_on_fx_and_restores_before_midi_draw(setup):
    """The patched generic SourcePage prologue preserves its caller ABI and scopes ownership."""
    spec, sec3, _ = setup
    m = Machine(spec, sec3)
    stock_slots = struct.pack(">8I", *(0x22220000 + i for i in range(8)))
    m.uc.mem_write(FX_SLOTS, stock_slots)
    for r, value in zip(REGS, range(0x71000000, 0x71000000 + len(REGS))):
        m.uc.reg_write(r, value)
    marks = [m.uc.reg_read(r) for r in REGS]

    m.uc.mem_write(ACTIVE_TRACK, bytes((0x70, 12, 0x4e, 0x75)))
    invoke_draw(m)
    assert list(struct.unpack(">8i", m.uc.mem_read(FX_SLOTS, 32)))[:7] == list(IDS.values())
    assert [m.uc.reg_read(r) for r in REGS] == marks

    m.uc.mem_write(ACTIVE_TRACK, bytes((0x70, 11, 0x4e, 0x75)))
    invoke_draw(m)
    assert bytes(m.uc.mem_read(FX_SLOTS, 32)) == stock_slots
    assert [m.uc.reg_read(r) for r in REGS] == marks


def test_shared_vparams_draw_scopes_compressor_and_beat_repeat_together(setup):
    """The single draw hook claims both FX-only pages and restores both on MIDI."""
    spec, sec3, _ = setup
    m = Machine(spec, sec3)
    br = json.loads((ROOT / "mods" / "beat-repeat" / "patch.json").read_text(encoding="utf-8"))
    for patch in br["patches"]:
        dst = int(patch["ram"], 16) if patch.get("append") else int(patch["addr"], 16)
        m.uc.mem_write(dst, bytes.fromhex(patch["hex"]))

    comp_slots = struct.pack(">8I", *(0x22220000 + i for i in range(8)))
    trig_slots = struct.pack(">2I", 0x33330001, 0x33330002)
    m.uc.mem_write(FX_SLOTS, comp_slots)
    m.uc.mem_write(0x41B9_F924, trig_slots)

    m.uc.mem_write(ACTIVE_TRACK, bytes((0x70, 12, 0x4e, 0x75)))
    invoke_draw(m)
    assert list(struct.unpack(">8I", m.uc.mem_read(FX_SLOTS, 32)))[:7] == list(IDS.values())
    assert struct.unpack(">2I", m.uc.mem_read(0x41B9_F924, 8)) == (269, 124)

    m.uc.mem_write(ACTIVE_TRACK, bytes((0x70, 11, 0x4e, 0x75)))
    invoke_draw(m)
    assert bytes(m.uc.mem_read(FX_SLOTS, 32)) == comp_slots
    assert bytes(m.uc.mem_read(0x41B9_F924, 8)) == trig_slots


def test_audio_block_leaves_the_page_alone(setup):
    spec, sec3, _ = setup
    m = Machine(spec, sec3)
    weird = [1, 2, 3, 4, 5, 6, 7, 8]
    m.uc.mem_write(FX_SLOTS, struct.pack(">8i", *weird))
    m.block([0] * 32, [0] * 32, 1000, 1000)                     # niente interfaccia nell'interrupt audio
    assert list(struct.unpack(">8i", m.uc.mem_read(FX_SLOTS, 32))) == weird


def test_constants_follow_stored_values_without_recomputing_every_block(setup):
    spec, sec3, _ = setup
    m = Machine(spec, sec3)
    m.set("RAT", 8 * RAT_STEP)
    loud = [int(0.9 * 2**31 * math.sin(2 * math.pi * 200 * i / 48000)) for i in range(32)]
    for _ in range(50):
        m.block(loud, loud, 30000, 30000)
    on = m.block(loud, loud, 30000, 30000)
    m.set("RAT", 0)                                             # spento: CV originali dal blocco dopo
    assert m.block(loud, loud, 30000, 30000) == (30000, 30000)
    m.set("RAT", 8 * RAT_STEP)
    for _ in range(50):
        m.block(loud, loud, 30000, 30000)
    assert m.block(loud, loud, 30000, 30000) == on


# ----------------------------------------------------------------------------- rifiniture v0.4.1
def test_rat_moves_one_position_per_small_step_and_fills_the_bar(setup):
    spec, sec3, _ = setup
    m = Machine(spec, sec3)
    assert m.get("RAT") == 0
    for i in range(1, 9):                            # manopola verso destra: +0x100 per scatto
        m.set("RAT", m.get("RAT") + 0x100)
        assert m.get("RAT") == i * RAT_STEP
    m.set("RAT", m.get("RAT") + 0x100)               # oltre il massimo: resta a 8
    assert m.get("RAT") == 0x7F00                    # barra piena
    for i in range(7, -1, -1):                       # verso sinistra
        m.set("RAT", m.get("RAT") - 0x40)
        assert m.get("RAT") == i * RAT_STEP
    m.set("RAT", 5 * RAT_STEP + 300)                 # salto: posizione piu' vicina
    assert m.get("RAT") == 5 * RAT_STEP


def test_meter_rises_fast_and_falls_slowly(setup):
    spec, sec3, _ = setup
    m = Machine(spec, sec3)
    m.set("RAT", 8 * RAT_STEP)
    loud = [int(0.9 * 2**31 * math.sin(2 * math.pi * 200 * (i + 32 * b) / 48000)) for b in range(1) for i in range(32)]
    for _ in range(100):
        m.block(loud, loud, 30000, 30000)
    top = reduction(m)
    assert top > 0x2000
    m.block([0] * 32, [0] * 32, 30000, 30000)
    after1 = reduction(m)
    assert top - 0x400 < after1 <= top               # non crolla in un blocco
    for _ in range(3000):                            # ~2 s di silenzio
        m.block([0] * 32, [0] * 32, 30000, 30000)
    assert reduction(m) == 0


def comp_init(m, spec):
    """The active FX context installs the compressor view state on demand."""
    assert set_active_track(m, spec, 12) == 1


def test_init_copies_drive_knob_graphics(setup):
    spec, sec3, _ = setup
    m = Machine(spec, sec3)
    drive = OBJS + 84 * 150 + 36
    m.uc.mem_write(drive, bytes(range(0xA0, 0xB0)))
    comp_init(m, spec)
    for k in ("THR", "ATK", "REL", "MUP"):
        assert bytes(m.uc.mem_read(OBJS + 84 * IDS[k] + 36, 16)) == bytes(range(0xA0, 0xB0))
    for i in (IDS["RAT"], IDS["GR"]):                # RAT e GR restano barre
        assert bytes(m.uc.mem_read(OBJS + 84 * i + 36, 16)) == bytes(16)


def test_formatters_ignore_the_function_data(setup):
    spec, sec3, _ = setup
    m = Machine(spec, sec3)
    comp_init(m, spec)
    for name in ("THR", "RAT"):                      # anche se l'OS copia la std::function senza dati
        obj = OBJS + 84 * IDS[name] + 20
        before = call_fmt(m, 0x4000, name)
        m.uc.mem_write(obj, bytes.fromhex("deadbeef") * 2)
        assert call_fmt(m, 0x4000, name) == before


# ----------------------------------------------------------------------------- v0.4.2
def call_fmt(m, value, name="RAT"):
    """Chiama il formattatore di un parametro come farebbe l'OS: invoker(funzione, valore, buffer)."""
    obj = OBJS + 84 * IDS[name] + 20
    mgr, inv = struct.unpack(">II", m.uc.mem_read(obj + 8, 8))
    assert mgr != 0                                  # l'OS controlla che ci sia un gestore
    buf = 0x5000_C000
    m.uc.mem_write(buf, bytes([0xEE]) * 16)
    m.call(inv, [obj, value, buf])
    raw = bytes(m.uc.mem_read(buf, 16))
    return raw[:raw.index(0)].decode()


def test_rat_text(setup):
    spec, sec3, _ = setup
    m = Machine(spec, sec3)
    comp_init(m, spec)
    texts = [call_fmt(m, i * RAT_STEP) for i in range(9)]
    assert texts == ["OFF", "1.5:1", "2:1", "3:1", "4:1", "6:1", "8:1", "16:1", "20:1"]
    assert call_fmt(m, 0x7F00) == "20:1" and call_fmt(m, 100) == "OFF"


@pytest.mark.parametrize("name, cases", [
    ("THR", {0: "-60dB", 0x4000: "-30dB", 0x7F00: "0dB"}),
    ("ATK", {0: "0.1ms", 0x7F00: "100ms"}),
    ("REL", {0: "10ms", 0x7F00: "2.0s"}),
    ("MUP", {0: "0dB", 0x4000: "+12dB", 0x7F00: "+24dB"}),
    ("GR", {0x7F00: "0dB", 0: "-18dB"}),
])
def test_unit_texts(setup, name, cases):
    spec, sec3, _ = setup
    m = Machine(spec, sec3)
    comp_init(m, spec)
    for v, txt in cases.items():
        assert call_fmt(m, v, name) == txt
    assert call_fmt(m, -5, name) == call_fmt(m, 0, name)          # fuori range: limitato
    assert call_fmt(m, 0x9000, name) == call_fmt(m, 0x7F00, name)


def test_unit_texts_match_the_formulas_for_every_step(setup):
    spec, sec3, _ = setup
    import importlib.util
    mp = importlib.util.spec_from_file_location("comp_make_patch", ROOT / "mods" / "master-comp" / "make_patch.py")
    mod = importlib.util.module_from_spec(mp)
    mp.loader.exec_module(mod)
    tabs = mod.unit_tables()
    m = Machine(spec, sec3)
    comp_init(m, spec)
    for name in ("THR", "ATK", "REL", "MUP", "GR"):
        assert [call_fmt(m, i << 8, name) for i in range(128)] == tabs[name.lower()]


def test_meter_asks_for_redraw_only_when_it_changes(setup):
    spec, sec3, _ = setup
    m = Machine(spec, sec3)
    m.uc.mem_write(UI_ROOT, struct.pack(">I", UI))
    m.set("RAT", 8 * RAT_STEP)
    loud = [int(0.9 * 2**31 * math.sin(2 * math.pi * 200 * i / 48000)) for i in range(32)]
    flagged = 0
    for _ in range(120):
        m.uc.mem_write(UI + 96, b"\0")
        m.block(loud, loud, 30000, 30000)
        flagged += m.uc.mem_read(UI + 96, 1)[0]
    assert 1 <= flagged <= 120 // 24 + 1             # al massimo un ridisegno ogni 24 blocchi
    for _ in range(4000):                            # silenzio: il misuratore scende a 0 e si ferma
        m.block([0] * 32, [0] * 32, 30000, 30000)
    m.uc.mem_write(UI + 96, b"\0")
    for _ in range(100):
        m.block([0] * 32, [0] * 32, 30000, 30000)
    assert m.uc.mem_read(UI + 96, 1)[0] == 0         # fermo: nessun ridisegno


def test_knob_change_asks_for_redraw_like_original_setters(setup):
    spec, sec3, _ = setup
    m = Machine(spec, sec3)
    m.uc.mem_write(UI_ROOT, struct.pack(">I", UI))
    for name, value in (("THR", 0x2345), ("RAT", 2 * RAT_STEP)):
        m.uc.mem_write(UI + 96, b"\0")
        m.set(name, value)
        assert m.uc.mem_read(UI + 96, 1)[0] == 1
    m.uc.mem_write(UI + 96, b"\0")
    m.set("GR", 0x1000)                              # sola lettura: niente
    assert m.uc.mem_read(UI + 96, 1)[0] == 0


# ----------------------------------------------------------------------------- v0.5: interruttore ON/OFF
def test_on_off_switch_bypasses_and_restores(setup):
    spec, sec3, _ = setup
    m = Machine(spec, sec3)
    assert m.get("COMP") == 0x100                    # acceso all'avvio
    m.set("RAT", 8 * RAT_STEP)
    loud = [int(0.9 * 2**31 * math.sin(2 * math.pi * 200 * i / 48000)) for i in range(32)]
    for _ in range(50):
        on = m.block(loud, loud, 30000, 30000)
    assert on[0] < 30000                             # comprime
    m.set("COMP", 0)
    assert m.get("COMP") == 0 and m.get("RAT") == 8 * RAT_STEP   # RAT resta impostato
    for _ in range(20):
        assert m.block(loud, loud, 30000, 70000) == (30000, 65535)   # come RAT = OFF
    for _ in range(3000):                            # il misuratore torna a ~20 dB/s
        m.block(loud, loud, 30000, 30000)
    assert reduction(m) == 0
    m.set("COMP", 0x100)
    for _ in range(50):
        again = m.block(loud, loud, 30000, 30000)
    assert again[0] < 30000


def test_on_off_text_and_page_slot(setup):
    spec, sec3, _ = setup
    m = Machine(spec, sec3)
    comp_init(m, spec)
    assert call_fmt(m, 0x100, "COMP") == "ON" and call_fmt(m, 0, "COMP") == "OFF"
    m.set("COMP", 0)
    m.block([0] * 32, [0] * 32, 1000, 1000)          # la casella resta nostra anche da spento
    assert struct.unpack(">8i", m.uc.mem_read(FX_SLOTS, 32))[6] == IDS["COMP"]


# ----------------------------------------------------------------------------- v0.8.1: id liberi
def test_old_alias_ids_are_left_to_the_os(setup):
    """59 (GAIN dei filtri EQ), 122 (REV del MIXER), 91/101 (SLEW), 127 (PAN): l'OS li usa come alias
    sulle pagine; la mod non li registra e non tocca i loro descrittori."""
    spec, sec3, _ = setup
    table = [p for p in spec["patches"] if p.get("append") and "vparams[" in p.get("what", "")]
    ids = {struct.unpack(">H", bytes.fromhex(p["hex"])[:2])[0] for p in table}
    assert ids == set(IDS.values())
    desc = 0x4022_D59C
    for i in OLD_IDS:
        lo, hi = desc + 52 * i, desc + 52 * i + 52
        assert not any(lo < int(p["addr"], 16) + p["len"] and int(p["addr"], 16) < hi
                       for p in spec["patches"] if not p.get("append")), i


def test_init_sets_the_encoder_type_of_the_new_ids(setup):
    spec, sec3, _ = setup
    m = Machine(spec, sec3)
    for i in IDS.values():
        m.uc.mem_write(OBJS + 84 * i, struct.pack(">I", 1))         # MIDI-track type
    comp_init(m, spec)
    want = {"THR": 0, "ATK": 8, "REL": 0, "MUP": 0, "RAT": 8, "GR": 0, "COMP": 12}
    for k, v in want.items():
        assert struct.unpack(">I", m.uc.mem_read(OBJS + 84 * IDS[k], 4))[0] == v


# ----------------------------------------------------------------------------- costo per blocco (v0.8.1)
def block_cost(m, left, right):
    n = [0]
    m.uc.ctl_flush_tb()                                        # i blocchi gia' tradotti non vedrebbero il gancio
    h = m.uc.hook_add(UC_HOOK_CODE, lambda *a: n.__setitem__(0, n[0] + 1))
    m.block(left, right, 40000, 40000)
    m.uc.hook_del(h)
    return n[0]


def test_cost_per_block(setup):
    """Regressione sul carico (issue #2): il rilevatore per blocco costa una frazione di quello per campione
    (~2 000 istruzioni fino alla v0.8.0). L'OS usa gia' ~89 % della CPU: ogni istruzione qui la toglie
    all'interfaccia."""
    spec, sec3, _ = setup
    m = Machine(spec, sec3)
    rnd = random.Random(3)
    sig = list(signal(rnd, 4))
    m.block(*sig[0], 40000, 40000)                             # costanti gia' calcolate
    off = block_cost(m, *sig[1])
    m.set("RAT", 4 * RAT_STEP)
    m.block(*sig[1], 40000, 40000)                             # ricalcolo delle costanti (una volta)
    on = max(block_cost(m, *s) for s in sig[2:])
    noisy = [rnd.randrange(-2**31, 2**31) for _ in range(32)]  # ogni campione un nuovo picco o minimo
    worst = block_cost(m, noisy, noisy)
    assert off < 150, off
    assert on < 650 and worst < 650, (on, worst)                # v0.8.0: ~2 000
