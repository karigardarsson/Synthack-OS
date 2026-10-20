"""Mod beat-repeat: ripetizione dal sequencer, eseguita nell'emulatore.

Il tick originale fa avanzare lo step di ogni traccia (step + 1, a capo sulla lunghezza) e poi, alla fine
dell'iterazione, chiama il nostro trampolino (0x4008D152). Qui si simula quell'avanzamento e si esegue il
codice vero della mod. Con la FX track attiva la ripetizione parte tenendo premuti i tasti di retrig 13
(RPT1) e 14 (RPT2): si entra nel nostro trampolino come dal ramo dei tasti 13-16 di KeyboardView, con la
traccia attiva simulata; il rilascio passa anche dal dispatcher. I rate passano da vparams.
"""

import json
import struct
import sys
from pathlib import Path

import pytest

pytest.importorskip("unicorn")
from unicorn import UC_ARCH_M68K, UC_HOOK_CODE, UC_MODE_BIG_ENDIAN, Uc  # noqa: E402
from unicorn.m68k_const import (UC_CPU_M68K_ANY, UC_M68K_REG_A0, UC_M68K_REG_A1, UC_M68K_REG_A2,  # noqa: E402
                                UC_M68K_REG_A3, UC_M68K_REG_A4, UC_M68K_REG_A5, UC_M68K_REG_A6,
                                UC_M68K_REG_A7, UC_M68K_REG_D0, UC_M68K_REG_D1, UC_M68K_REG_D2,
                                UC_M68K_REG_D3, UC_M68K_REG_SR)

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "tools" / "build"), str(ROOT / "tools" / "unpack")]
import eft  # noqa: E402
import modarea_layout  # noqa: E402

MA = modarea_layout.RAM                                    # area mod (mods/modarea)
MA_PAGE, MA_MAP = 0x444E_0000, 0x2_0000                     # area mod e radice dell'interfaccia (0x444E1334)
assert MA_PAGE <= MA and MA + modarea_layout.SIZE <= MA_PAGE + MA_MAP

SY = ROOT / "firmware" / "Syntakt_OS1.41.syx"
MODS = [ROOT / "mods" / m / "patch.json" for m in ("vparams", "beat-repeat")]
pytestmark = pytest.mark.skipif(not (SY.exists() and all(p.exists() for p in MODS)), reason="OS o patch assenti")

LOAD, STACK, RET = 0x4000_0400, 0x5000_8000, 0x5000_F000
PAT, STEPS, UI = 0x5000_1000, 0x5000_0800, 0x5000_0C00
PROJECT, PROJECT_PTR = 0x5000_2800, 0x444E_13F4
SOURCE_DRAW, SOURCE_DRAW_CONT = 0x4003_A244, 0x4003_A24C     # pattern finto, step[13], interfaccia
VIEW, TRACK, EV = 0x5000_2000, 0x5000_2300, 0x5000_2400       # KeyboardView finta, traccia attiva, evento
RPT1, RPT2 = 269, 124
HANDLED, NATIVE, LOWER = 0x4002_E954, 0x4002_EA9A, 0x4002_EBA6  # uscite del ramo dei tasti 13-16
DISPATCH, ACTIVE, DRAW = 0x4000_839E, 0x4001_FF74, 0x400F_8C18
GET, SET, KIT = 0x4000_D94A, 0x4000_DA32, 0x4000_D870


@pytest.fixture()
def m():
    return Machine()


class Machine:
    def __init__(self):
        sec3 = eft.unpack(SY, ROOT / "unpacked" / SY.stem, ids=[3])[3].read_bytes()
        self.spec = json.loads(MODS[1].read_text(encoding="utf-8"))
        self.sym = {k: int(v, 16) for k, v in self.spec["symbols"].items()}
        uc = self.uc = Uc(UC_ARCH_M68K, UC_MODE_BIG_ENDIAN, cpu=UC_CPU_M68K_ANY)
        uc.mem_map(0x4000_0000, 0x0040_0000)
        uc.mem_write(LOAD, sec3)
        uc.mem_map(0x41B9_0000, 0x2_0000)
        uc.mem_map(MA_PAGE, MA_MAP)
        uc.mem_map(0x5000_0000, 0x4_0000)
        uc.mem_map(0x8000_0000, 0x1_0000)                         # SRAM: puntatore al kit (0 = nessuno)
        for f in MODS:
            for p in json.loads(f.read_text(encoding="utf-8"))["patches"]:
                uc.mem_write(int(p["ram"], 16) if p.get("append") else int(p["addr"], 16), bytes.fromhex(p["hex"]))
        uc.mem_write(RET, b"\x4e\x75")
        uc.mem_write(0x444E_1334, struct.pack(">I", UI))
        uc.mem_write(PROJECT_PTR, struct.pack(">I", PROJECT))
        uc.mem_write(PAT + 136057, b"\x00")                      # lunghezza unica del pattern
        self.length(16)
        # traccia attiva (0x4001FF74) -> move.l TRACK,d0 ; rts ; testo (0x400F8C18) -> rts, argomenti letti
        uc.mem_write(ACTIVE, struct.pack(">HIH", 0x2039, TRACK, 0x4E75))
        uc.mem_write(DRAW, b"\x4e\x75")
        self.track(12)

    def track(self, t):
        self.uc.mem_write(TRACK, struct.pack(">I", t))

    def length(self, n):
        self.uc.mem_write(PAT + 136052, struct.pack(">h", n))

    def call(self, fn, args, stop=None):
        """Chiama fn. Con stop: ("cont", sp, sp d'ingresso) se arriva al codice originale, altrimenti d0."""
        uc = self.uc
        sp = STACK - 4 * (len(args) + 1)
        uc.mem_write(sp, struct.pack(f">{len(args) + 1}I", RET, *[a & 0xFFFFFFFF for a in args]))
        uc.reg_write(UC_M68K_REG_SR, 0x2700)
        uc.reg_write(UC_M68K_REG_A7, sp)
        if stop is None:
            uc.emu_start(fn, RET, count=100_000)
            return uc.reg_read(UC_M68K_REG_D0) & 0xFFFFFFFF
        hit = []

        def at(uc_, addr, size, _):
            if addr in (stop, RET):
                hit.append(addr)
                uc_.emu_stop()
        h = uc.hook_add(UC_HOOK_CODE, at)
        uc.emu_start(fn, 0, count=100_000)
        uc.hook_del(h)
        assert hit, "non arriva ne' al ritorno ne' al codice originale"
        if hit[0] == stop:
            return "cont", uc.reg_read(UC_M68K_REG_A7), sp
        return uc.reg_read(UC_M68K_REG_D0) & 0xFFFFFFFF

    def rate(self, pid, pos):
        self.call(SET, [0x5000_0000, pid, pos << 8, 1])

    def event(self, code, flags):
        self.uc.mem_write(EV + 12, struct.pack(">II", code, flags))

    def key(self, n, down):
        """Tasto di trig n (1..16) nel ramo dei tasti 13-16 di KeyboardView, come a 0x4002EA92.
        Ritorna (dove esce, d0, sp): HANDLED, NATIVE (tasti 13-16) o LOWER (tasti 1-12)."""
        uc = self.uc
        code = 23 + n
        self.event(code, 1 if down else 0)
        for r, v in ((UC_M68K_REG_D0, code), (UC_M68K_REG_D2, EV), (UC_M68K_REG_A2, VIEW),
                     (UC_M68K_REG_D3, 0x33), (UC_M68K_REG_A3, 0xA3), (UC_M68K_REG_A5, 0xA5)):
            uc.reg_write(r, v)
        uc.reg_write(UC_M68K_REG_SR, 0x2700)
        uc.reg_write(UC_M68K_REG_A7, STACK)
        hit = []

        def at(uc_, addr, size, _):
            if addr in (HANDLED, NATIVE, LOWER):
                hit.append(addr)
                uc_.emu_stop()
        h = uc.hook_add(UC_HOOK_CODE, at)
        uc.emu_start(self.sym["br_kbd_hook"], 0, count=100_000)
        uc.hook_del(h)
        assert hit
        for r, v in ((UC_M68K_REG_D2, EV), (UC_M68K_REG_A2, VIEW), (UC_M68K_REG_D3, 0x33),
                     (UC_M68K_REG_A3, 0xA3), (UC_M68K_REG_A5, 0xA5)):
            assert uc.reg_read(r) == v                         # registri dell'OS intatti
        return hit[0], uc.reg_read(UC_M68K_REG_D0), uc.reg_read(UC_M68K_REG_A7)

    def dispatch(self, n, down):
        self.event(23 + n, 1 if down else 0)
        return self.call(self.sym["br_ev_hook"], [0x5000_0000, EV], stop=DISPATCH)

    def held(self):
        return self.uc.mem_read(self.sym["br_held"], 1)[0]

    def source_draw(self):
        """Run the patched generic SourcePage draw prologue through its stock continuation."""
        uc = self.uc
        uc.mem_write(STACK - 4, struct.pack(">I", RET))
        uc.reg_write(UC_M68K_REG_SR, 0x2700)
        uc.reg_write(UC_M68K_REG_A7, STACK - 4)
        uc.emu_start(SOURCE_DRAW, SOURCE_DRAW_CONT, count=100_000)
        assert uc.reg_read(UC_M68K_REG_A7) == STACK - 4 - 80

    def hook(self, t):
        """Fine dell'iterazione della traccia t nel tick, come a 0x4008D152 (d2 gia' incrementato)."""
        uc = self.uc
        regs = {UC_M68K_REG_D2: t + 1, UC_M68K_REG_A2: PAT, UC_M68K_REG_A3: PAT + 1177 * t,
                UC_M68K_REG_A4: STEPS + t, UC_M68K_REG_D3: 100, UC_M68K_REG_A6: 200, UC_M68K_REG_A5: 300,
                UC_M68K_REG_D0: 0xD0, UC_M68K_REG_D1: 0xD1, UC_M68K_REG_A0: 0xA0, UC_M68K_REG_A1: 0xA1}
        for r, v in regs.items():
            uc.reg_write(r, v)
        uc.mem_write(STACK - 4, struct.pack(">I", RET))
        uc.reg_write(UC_M68K_REG_SR, 0x2700)           # prima di A7: il cambio di modo scambia lo stack
        uc.reg_write(UC_M68K_REG_A7, STACK - 4)
        uc.emu_start(self.sym["br_step_hook"], RET, count=100_000)
        for r, v in ((UC_M68K_REG_D3, 101), (UC_M68K_REG_A6, 201), (UC_M68K_REG_A5, 301),
                     (UC_M68K_REG_D0, 0xD0), (UC_M68K_REG_D1, 0xD1), (UC_M68K_REG_A0, 0xA0),
                     (UC_M68K_REG_A1, 0xA1), (UC_M68K_REG_D2, t + 1), (UC_M68K_REG_A4, STEPS + t)):
            assert uc.reg_read(r) & 0xFFFFFFFF == v                 # istruzioni sostituite e registri
        assert uc.reg_read(UC_M68K_REG_A7) == STACK

    def step(self, t):
        return self.uc.mem_read(STEPS + t, 1)[0]

    def advance(self, t, n):
        """Come il tick originale: step + 1, a capo sulla lunghezza, poi il nostro aggancio."""
        cur = (self.step(t) + 1) % n
        self.uc.mem_write(STEPS + t, bytes([cur]))
        self.hook(t)
        return self.step(t)


def play(m, t, n, events):
    """Sequenza degli step suonati; events = {indice: azione(m) prima dell'avanzamento}."""
    m.uc.mem_write(STEPS + t, bytes([0]))
    m.hook(t)
    out = [m.step(t)]
    for i in range(1, 16):
        if i in events:
            events[i](m)
            m.hook(t)                                  # un tick senza avanzamento
        out.append(m.advance(t, n))
    return out


def hold(n):
    return lambda m: m.key(n, True)


def release(n):
    return lambda m: m.key(n, False)


def test_repeat_loops_the_slice_and_resumes_in_time(m):
    m.rate(RPT1, 1)                                    # 1/8 = 2 step
    seq = play(m, 0, 16, {6: hold(13), 10: release(13)})  # premuto dopo lo step 5, rilasciato dopo 4 step
    assert seq == [0, 1, 2, 3, 4, 5, 4, 5, 4, 5, 10, 11, 12, 13, 14, 15]


@pytest.mark.parametrize("pos, L", [(0, 1), (2, 3), (3, 4), (4, 8), (5, 16)])
def test_every_length(m, pos, L):
    m.rate(RPT2, pos)
    seq = play(m, 1, 16, {6: hold(14)})
    anchor = 5 - 5 % L
    assert seq[6:] == [anchor + (5 - anchor + 1 + i) % L for i in range(10)]


def test_short_track_wraps_on_its_length(m):
    m.length(6)
    m.rate(RPT1, 4)
    seq = play(m, 2, 6, {4: hold(13)})                 # 8 step su una traccia di 6: resta dentro 0..5
    assert all(s < 6 for s in seq)


def test_nothing_without_press(m):
    assert play(m, 3, 16, {}) == list(range(16))


def test_second_key_switches_rate_from_real_position(m):
    m.rate(RPT1, 1)                                    # 1/8
    m.rate(RPT2, 0)                                    # 1/16
    seq = play(m, 4, 16, {6: hold(13), 9: hold(14), 12: release(14)})
    # RPT1: 4 5 4 | RPT2: lo step reale appena suonato e' 8 -> 8 8 8 | rilascio: RPT1 dal reale 11
    assert seq == [0, 1, 2, 3, 4, 5, 4, 5, 4, 8, 8, 8, 10, 11, 10, 11]


def test_release_after_track_change_stops(m):
    m.rate(RPT1, 1)

    def leave(m):
        m.track(3)                                     # altra traccia: il ramo resta all'OS...
        m.dispatch(13, False)                          # ...ma il rilascio passa dal dispatcher
    seq = play(m, 5, 16, {6: hold(13), 10: leave})
    assert seq == [0, 1, 2, 3, 4, 5, 4, 5, 4, 5, 10, 11, 12, 13, 14, 15]


def test_keys_13_14_on_fx_track_are_ours(m):
    where, _, sp = m.key(13, True)
    assert where == HANDLED and sp == STACK and m.held() == 1
    where, _, sp = m.key(14, True)
    assert where == HANDLED and m.held() == 3
    assert m.key(13, False)[0] == HANDLED and m.held() == 2
    assert m.key(14, False)[0] == HANDLED and m.held() == 0


@pytest.mark.parametrize("track, n", [(3, 13), (11, 14), (12, 15), (12, 16)])
def test_native_retrig_elsewhere(m, track, n):
    m.track(track)
    where, d0, sp = m.key(n, True)
    assert (where, d0, sp) == (NATIVE, 23 + n, STACK)  # stesso stato del codice originale
    assert m.held() == 0


def test_lower_keys_untouched(m):
    where, d0, sp = m.key(5, True)
    assert (where, d0, sp) == (LOWER, 28, STACK)
    assert m.held() == 0


def test_dispatcher_hook_passes_through(m):
    m.key(14, True)
    cont, sp, entry = m.dispatch(3, False)             # rilascio di un altro tasto: nessun effetto
    assert cont == "cont" and sp == entry
    assert struct.unpack(">II", m.uc.mem_read(sp + 4, 8)) == (0x5000_0000, EV)
    assert m.held() == 2
    m.dispatch(14, True)                               # pressione: nessun effetto
    assert m.held() == 2
    m.dispatch(14, False)
    assert m.held() == 0


def test_slot_graphic_draws_the_division(m):
    got = []

    def at(uc, addr, size, _):
        sp = uc.reg_read(UC_M68K_REG_A7)
        args = struct.unpack(">9I", uc.mem_read(sp + 4, 36))
        cstr = lambda a: bytes(uc.mem_read(a, 8)).split(b"\0")[0].decode()
        got.append((args[0], args[1], args[2], args[3], args[4], args[5],
                    cstr(args[6]), cstr(args[7]), cstr(args[8])))
    h = m.uc.hook_add(UC_HOOK_CODE, at, begin=DRAW, end=DRAW)
    m.call(m.sym["br_gfx"], [0, 0x200, 0x5000_5000, 30, 40])
    m.uc.hook_del(h)
    assert got == [(0x5000_5000, 0x402A_91C0, 38, 45, 1, 0, "XXXX", "%s", "3/16")]


def test_rates_through_vparams(m):
    for pid in (RPT1, RPT2):
        assert m.call(KIT, [0x5000_0000, pid]) == 1
    assert m.call(GET, [0x5000_0000, RPT1]) == 0       # 1/16
    assert m.call(GET, [0x5000_0000, RPT2]) == 0x100   # 1/8
    m.uc.mem_write(UI + 96, b"\x00")
    m.rate(RPT2, 3)
    assert m.call(GET, [0x5000_0000, RPT2]) == 0x300
    assert m.call(GET, [0x5000_0000, RPT1]) == 0
    assert m.uc.mem_read(UI + 96, 1)[0] == 1           # ridisegno richiesto
    m.call(SET, [0x5000_0000, RPT1, 0x9000, 1])
    assert m.call(GET, [0x5000_0000, RPT1]) == 0x500   # limitato
    m.call(SET, [0x5000_0000, RPT1, -50, 1])
    assert m.call(GET, [0x5000_0000, RPT1]) == 0


def test_texts(m):
    buf = 0x5000_3000
    out = []
    for pos in range(6):
        m.call(m.sym["br_invoke"], [0, pos << 8, buf])
        raw = bytes(m.uc.mem_read(buf, 8))
        out.append(raw[:raw.index(0)].decode())
    assert out == ["1/16", "1/8", "3/16", "1/4", "1/2", "1BAR"]


def test_fx_trig_slots_are_claimed_at_the_shared_page_boundary(m):
    m.source_draw()
    assert struct.unpack(">II", m.uc.mem_read(0x41B9_F924, 8)) == (RPT1, RPT2)


def test_patched_bytes(m):
    want = {0x4008_D152: "5283528e528d", 0x4002_EA92: "7223b2806c00010e", 0x4000_B420: "4eb94000839e",
            SOURCE_DRAW: "4fefffb048d7", 0x4019_50F0: "42b941b9f928", 0x4019_50A8: "42b941b9f924"}
    sec3 = eft.unpack(SY, ROOT / "unpacked" / SY.stem, ids=[3])[3].read_bytes()
    for a, orig in want.items():
        assert sec3[a - LOAD:a - LOAD + len(orig) // 2].hex() == orig


def test_rates_saved_in_the_kit(m):
    """RPT1/RPT2 nella parola dell'id interno 0x37 del kit del pattern, XOR i default (1/16, 1/8)."""
    kit_a, kit_b = 0x5003_0000, 0x5003_0100
    m.uc.mem_write(0x8000_30BC, struct.pack(">I", kit_a))
    m.uc.mem_write(kit_a, bytes(142))
    assert m.call(GET, [0x5000_0000, RPT1]) == 0 << 8 and m.call(GET, [0x5000_0000, RPT2]) == 1 << 8
    m.rate(RPT1, 4)
    m.rate(RPT2, 5)
    assert struct.unpack(">H", m.uc.mem_read(kit_a + 110, 2))[0] == (5 ^ 1) << 8 | 4
    raw = bytes(m.uc.mem_read(kit_a, 142))
    assert raw[:110] == bytes(110) and raw[112:] == bytes(30)     # il resto del kit non si tocca
    m.uc.mem_write(kit_b, bytes(142))
    m.uc.mem_write(kit_b + 110, struct.pack(">H", (3 ^ 1) << 8 | 2))
    m.uc.mem_write(0x8000_30BC, struct.pack(">I", kit_b))         # altro pattern
    assert m.call(GET, [0x5000_0000, RPT1]) == 2 << 8 and m.call(GET, [0x5000_0000, RPT2]) == 3 << 8
    m.uc.mem_write(kit_b + 110, bytes([0xFF, 0xFF]))            # valori fuori scala: limitati
    assert m.call(GET, [0x5000_0000, RPT1]) == 5 << 8


def test_midi_context_restores_sel8_and_uses_the_native_virtual_route(m):
    """Leaving FX restores the exact CC8 descriptor/object/slot state before MIDI AMP draws."""
    before = {}
    for pos, pid in enumerate((RPT1, RPT2)):
        desc, obj = 0x4022_D59C + 52 * pid, 0x41B9_FA24 + 84 * pid
        d = bytes((0x20 + pos + i) & 0xff for i in range(52))
        o = bytes((0x80 + pos + i) & 0xff for i in range(84))
        m.uc.mem_write(desc, d)
        m.uc.mem_write(obj, o)
        before[desc], before[obj] = d, o
    slots = struct.pack(">II", 0x11110001, 0x11110002)
    m.uc.mem_write(0x41B9_F924, slots)

    m.track(12)
    m.source_draw()
    assert struct.unpack(">II", m.uc.mem_read(0x41B9_F924, 8)) == (RPT1, RPT2)

    m.track(11)
    m.source_draw()
    assert bytes(m.uc.mem_read(0x41B9_F924, 8)) == slots
    for addr, original in before.items():
        assert bytes(m.uc.mem_read(addr, len(original))) == original
    assert m.call(GET, [0x5000_0000, RPT1], stop=0x4000_D950)[0] == "cont"
    assert m.call(SET, [0x5000_0000, RPT1, 0x100, 1], stop=0x4000_DA3A)[0] == "cont"
