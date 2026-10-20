"""Mod fx3 (terza mandata, chorus), eseguita nell'emulatore con la routine delle mandate dell'OS.

- trampolino del ciclo per traccia: bersagli della mandata come l'OS per DEL/REV ((v/32768)^2 per livello,
  media dei lati, a meta' per la somma delle coppie), mute, istruzioni EMAC sostituite rieseguite, registri
  intatti;
- fx3_run (somme del master): bus 3 a 24 kHz = media delle coppie di campioni pesata come le mandate
  dell'OS; chorus come ritardo puro; ritorno sul bus diretto con il segno dell'OS, riportato a 48 kHz per
  interpolazione lineare; a riposo senza mandate, senza ascoltatori o con ingressi muti; costo per blocco
  limitato (prove di regressione sul numero di istruzioni);
- fx3_dsnd (prima del delay): uscita del blocco precedente nel bus del delay; pagina, parametri, testi.
"""

import json
import random
import struct
import sys
from pathlib import Path

import pytest

pytest.importorskip("unicorn")
from unicorn import UC_ARCH_M68K, UC_HOOK_CODE, UC_MODE_BIG_ENDIAN, Uc  # noqa: E402
from unicorn.m68k_const import (UC_CPU_M68K_ANY, UC_M68K_REG_A0, UC_M68K_REG_A1, UC_M68K_REG_A3,  # noqa: E402
                                UC_M68K_REG_A6, UC_M68K_REG_A7, UC_M68K_REG_D0, UC_M68K_REG_D1,
                                UC_M68K_REG_D2, UC_M68K_REG_D3, UC_M68K_REG_D7, UC_M68K_REG_SR)

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "tools" / "build"), str(ROOT / "tools" / "unpack"), str(ROOT / "tools" / "emu")]
import eft  # noqa: E402
import modarea_layout  # noqa: E402
from emac import UnicornEmac  # noqa: E402

MA = modarea_layout.RAM                                    # area mod (mods/modarea)
MA_PAGE, MA_MAP = 0x444E_0000, 0x2_0000                     # area mod e radice dell'interfaccia (0x444E1334)
assert MA_PAGE <= MA and MA + modarea_layout.SIZE <= MA_PAGE + MA_MAP

SY = ROOT / "firmware" / "Syntakt_OS1.41.syx"
MODS = [ROOT / "mods" / m / "patch.json" for m in ("vparams", "fx3")]
pytestmark = pytest.mark.skipif(not (SY.exists() and all(p.exists() for p in MODS)), reason="OS o patch assenti")

LOAD, STACK, RET, UI = 0x4000_0400, 0x5000_8000, 0x5000_F000, 0x5000_0C00
FRAME, TRK = 0x5000_4000, 0x5000_5000
SRC_DIG, SRC_ANA, OUT_A, OUT_B = 0x8000_3D50, 0x8000_3950, 0x8000_DAD0, 0x8000_DFD0
GET, SET, KIT = 0x4000_D94A, 0x4000_DA32, 0x4000_D870
IDS = {"TYPE": 246, "SPD": 247, "DEP": 248, "TIME": 250, "FDBK": 251, "WID": 252, "DSND": 249, "VOL": 253}
DELAY, DLY_IN = 0x4009_6890, 0x8000_DBD0


def s32(v):
    v &= 0xFFFF_FFFF
    return v - (1 << 32) if v & 0x8000_0000 else v


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
        uc.mem_map(0x5000_0000, 0x1_0000)
        uc.mem_map(0x8000_0000, 0x1_0000)
        for f in MODS:
            for p in json.loads(f.read_text(encoding="utf-8"))["patches"]:
                uc.mem_write(int(p["ram"], 16) if p.get("append") else int(p["addr"], 16), bytes.fromhex(p["hex"]))
        uc.mem_write(RET, b"\x4e\x75")
        uc.mem_write(0x444E_1334, struct.pack(">I", UI))
        uc.mem_write(0x444E_13F4, struct.pack(">I", 0x5000_7000))
        uc.mem_write(0x4001_FF74, bytes((0x70, 12, 0x4E, 0x75)))  # default active FX track
        self.emac = UnicornEmac(uc, [int(a, 16) for a in self.spec["emac_sites"]])

    def call(self, fn, args=(), regs=None):
        uc = self.uc
        sp = STACK - 4 * (len(args) + 1)
        uc.mem_write(sp, struct.pack(f">{len(args) + 1}I", RET, *[a & 0xFFFFFFFF for a in args]))
        for r, v in (regs or {}).items():
            uc.reg_write(r, v & 0xFFFFFFFF)
        uc.reg_write(UC_M68K_REG_SR, 0x2700)
        uc.reg_write(UC_M68K_REG_A7, sp)
        uc.emu_start(fn, RET, count=2_000_000)
        assert self.emac.error is None
        return uc.reg_read(UC_M68K_REG_D0) & 0xFFFFFFFF

    def longs(self, a, n):
        return [s32(v) for v in struct.unpack(f">{n}I", self.uc.mem_read(a, 4 * n))]

    def put(self, a, vals):
        self.uc.mem_write(a, struct.pack(f">{len(vals)}I", *[v & 0xFFFFFFFF for v in vals]))

    def param(self, name, v):
        self.call(SET, [0x5000_0000, IDS[name], v << 8, 1])


def frac(a, b):
    return ((a >> 16) * (b >> 16)) << 1


def fx_context(m, track):
    """Run the FX3 ownership predicate against a tiny native-track selector stub."""
    m.put(0x444E_13F4, [0x5000_7000])
    m.uc.mem_write(0x4001_FF74, bytes((0x70, track, 0x4E, 0x75)))  # moveq #track,d0 ; rts
    m.uc.ctl_flush_tb()
    return m.call(m.sym["fx3_active_context"])


def track(m, t, gl, gr, v, mute=0):
    """Il trampolino come nel ciclo per traccia dell'OS: d0/d1 guadagni, d3 traccia, a3 struttura, fp quadro."""
    m.put(FRAME - 508, [mute])
    m.uc.mem_write(TRK + 106, struct.pack(">h", v))
    m.emac.state.acc[0] = m.emac.state.acc[1] = 0
    regs = {UC_M68K_REG_D0: gl, UC_M68K_REG_D1: gr, UC_M68K_REG_D2: 0x1234, UC_M68K_REG_D3: t,
            UC_M68K_REG_D7: s32(-2 * 0x7F00 * 0x7F00), UC_M68K_REG_A0: 0xA0, UC_M68K_REG_A1: 0xA1,
            UC_M68K_REG_A3: TRK, UC_M68K_REG_A6: FRAME}
    m.call(m.sym["fx3_trk_hook"], regs=regs)
    for r, val in regs.items():
        assert m.uc.reg_read(r) & 0xFFFFFFFF == val & 0xFFFFFFFF            # registri dell'OS intatti
    assert m.uc.reg_read(UC_M68K_REG_A7) == STACK
    assert m.emac.state.acc[0] != 0 and m.emac.state.acc[1] != 0           # msac sostituite rieseguite
    return m.longs(m.sym["fx3_tgt"], 16)


@pytest.mark.parametrize("t, v", [(0, 0x7F00), (3, 0x4000), (9, 0x2000), (11, 0), (5, -3)])
def test_track_targets_like_os_sends(m, t, v):
    gl, gr = 0x6000_0000, 0x2000_0000
    tgt = track(m, t, gl, gr, v)
    g = 2 * v * v if v > 0 else 0
    assert tgt[t] == frac((gl >> 1) + (gr >> 1), g) >> 1
    assert abs(tgt[t] / 2 ** 30 - (gl + gr) / 2 ** 32 * (max(v, 0) / 32768) ** 2) < 1e-3
    assert (m.longs(m.sym["fx3_moving"], 1)[0] != 0) == (v > 0)  # bersaglio cambiato: rampa


def test_muted_track_sends_nothing(m):
    assert track(m, 2, 0x6000_0000, 0x6000_0000, 0x7F00)[2] != 0
    assert track(m, 2, 0x6000_0000, 0x6000_0000, 0x7F00, mute=1 << 2)[2] == 0


def test_fx_track_and_beyond_ignored(m):
    assert track(m, 12, 0x6000_0000, 0x6000_0000, 0x7F00) == [0] * 16


def run_block(m):
    """Come l'OS: jsr fx3_del_hook al posto del delay (qui un rts), argomenti intatti; poi il trampolino
    delle somme del master (ritorna con le due pea sostituite in pila)."""
    m.uc.mem_write(DELAY, b"\x4e\x75")
    m.call(m.sym["fx3_del_hook"], [0x1111, 0x2222, 0x3333])
    assert m.uc.reg_read(UC_M68K_REG_A7) == STACK - 16 + 4
    m.uc.reg_write(UC_M68K_REG_A6, FRAME)
    m.call(m.sym["fx3_mix_hook"])
    assert m.uc.reg_read(UC_M68K_REG_A7) == STACK - 8
    assert m.emac.state.acc[0] == 0                             # le somme dell'OS partono da acc0 = 0


def sat(v):
    return max(-2 ** 31, min(2 ** 31 - 1, v))


def ret_ref(wet, gain, a, h):
    """fx3_ret: a -= 2 * wet * guadagno a 48 kHz; dispari = campione del chorus, pari = media col precedente."""
    a, h = list(a), list(h)
    for n in range(16):
        for c in (0, 1):
            x = wet[2 * n + c] * gain
            a[4 * n + c] = sat(a[4 * n + c] - (h[c] + x))
            a[4 * n + 2 + c] = sat(a[4 * n + 2 + c] - 2 * x)
            h[c] = x
    return a, h


def gains(m, g):
    m.put(m.sym["fx3_tgt"], g + [0] * (16 - len(g)))
    m.put(m.sym["fx3_cur"], g + [0] * (16 - len(g)))         # nessuna rampa
    m.put(m.sym["fx3_moving"], [1])                            # come il ciclo per traccia


@pytest.mark.parametrize("on", [range(12), range(8), range(8, 12), [3], [10], [0, 11], [6, 7], [2, 5, 9]])
def test_bus_is_the_os_send_sum(m, on):
    """Tutte, digitali, analogiche (un passaggio con 12/8/4 canali) e una o due tracce (un passaggio ciascuna)."""
    dig = [((k * 7919 + n * 104729) % 65536 - 32768) << 12 for k in range(8) for n in range(32)]
    ana = [((k * 31337 + n * 7) % 65536 - 32768) << 12 for k in range(4) for n in range(32)]
    m.put(SRC_DIG, dig)
    m.put(SRC_ANA, ana)
    m.put(SRC_ANA + 512, [0x7FFF_FFFF] * 8)                   # oltre i canali: non deve entrare
    m.put(m.sym["fx3_bus"], [12345] * 16)
    g = [0x0800_0000 * (k + 1) if k in on else 0 for k in range(12)]
    gains(m, g)
    run_block(m)
    bus = m.longs(m.sym["fx3_bus"], 16)
    pair = lambda x, k, n: x[32 * k + 2 * n] + x[32 * k + 2 * n + 1]
    for n in range(16):
        want = (-sum(g[k] * pair(dig, k, n) for k in range(8)) * 2
                - sum(g[8 + k] * pair(ana, k, n) for k in range(4)) * 2)
        assert abs(bus[n] - want / 2 ** 32) < 64, n


def test_gain_follows_target_smoothly_and_lands_exactly(m):
    m.put(m.sym["fx3_tgt"], [0x4000_0000] + [0] * 15)
    m.put(m.sym["fx3_moving"], [1])
    seen = []
    for _ in range(80):                                          # ~58 blocchi (40 ms) per arrivare
        run_block(m)
        seen.append(m.longs(m.sym["fx3_cur"], 1)[0])
    assert seen[0] == 0x4000_0000 >> 2                           # 1/4 a blocco
    assert all(a < b for a, b in zip(seen, seen[1:])) or seen[-1] == 0x4000_0000
    assert seen[-1] == 0x4000_0000


def settle(m, **params):
    """Parametri e due blocchi muti con mandata attiva: LFO e posizioni di lettura a regime."""
    for k, v in params.items():
        m.param(k, v)
    gains(m, [0x4000_0000])                                    # guadagno 1 (meta')
    m.put(SRC_DIG, [0] * 256)
    run_block(m)
    run_block(m)


def impulse(m):
    sig = [0] * 256
    sig[10] = 0x1234 << 16                                      # coppia 5 a 24 kHz
    m.put(SRC_DIG, sig)
    run_block(m)
    bus5 = m.longs(m.sym["fx3_bus"], 16)[5]
    m.put(SRC_DIG, [0] * 256)
    return bus5


def test_chorus_without_depth_is_a_pure_delay(m):
    settle(m, DEP=0, TIME=0, FDBK=0, VOL=127)                  # 1 ms = 24 campioni a 24 kHz
    bus5 = impulse(m)
    m.put(OUT_A, [0] * 64)
    run_block(m)
    wet = m.longs(m.sym["fx3_wet"], 32)
    y = bus5 >> 16
    k = 5 + 24 - 16
    assert wet[2 * k] == y != 0
    assert wet[2 * k + 1] == wet[2 * k]
    assert sum(1 for v in wet if v) == 2
    x = y * 32767                                               # ritorno a 48 kHz, interpolato
    out = m.longs(OUT_A, 64)
    assert out[4 * k:4 * k + 8] == [-x, -x, -2 * x, -2 * x, -x, -x, 0, 0]
    assert sum(1 for v in out if v) == 6


def test_idle_without_sends_and_after_tail(m):
    settle(m, DEP=0, TIME=0, FDBK=0)
    assert m.longs(m.sym["fx3_idle"], 1) == [0]
    gains(m, [0])
    for _ in range(1024 // 16 + 2):
        run_block(m)
    assert m.longs(m.sym["fx3_idle"], 1) == [1]
    m.put(OUT_A, [5] * 64)
    m.put(DLY_IN, [5] * 64)
    run_block(m)
    assert m.longs(OUT_A, 64) == [5] * 64                       # a riposo non tocca le uscite
    assert m.longs(DLY_IN, 64) == [5] * 64


def count(m, fn):
    n = [0]
    m.uc.ctl_flush_tb()                                        # i blocchi gia' tradotti non vedrebbero il gancio
    h = m.uc.hook_add(UC_HOOK_CODE, lambda *a: n.__setitem__(0, n[0] + 1))
    fn()
    m.uc.hook_del(h)
    return n[0]


def loud(m):
    m.put(SRC_DIG, [((n * 7919) % 65536 - 32768) << 14 for n in range(256)])
    m.put(SRC_ANA, [((n * 7907) % 65536 - 32768) << 14 for n in range(256)])


def block_cost(m):
    """Istruzioni di un blocco nei due trampolini (le chiamate dei test hanno un rts in piu' ciascuna)."""
    return count(m, lambda: run_block(m)) - 3


def test_cost_per_block(m):
    """Regressione sul carico: istruzioni per blocco (32 campioni, 1500 blocchi al secondo). L'OS usa gia'
    quasi tutta la CPU: ogni istruzione qui toglie tempo all'interfaccia."""
    for _ in range(1024 // 16 + 2):
        run_block(m)
    rest = block_cost(m)
    assert rest < 120, rest                                     # nessuna mandata
    loud(m)
    gains(m, [0x4000_0000])                                    # una traccia, senza retroazione ne' DEL
    run_block(m)                                               # a regime (il primo blocco fa la rampa)
    one = block_cost(m)
    assert one < 1400, one                                     # era ~3100
    for t, most in ((1, 1600), (2, 1800), (3, 950)):           # FLNG e PHSR con retroazione (FDBK 0 = -95/-90 %)
        m.param("TYPE", t)
        run_block(m)
        assert block_cost(m) < most, t
    m.param("TYPE", 0)
    gains(m, [0x4000_0000] * 12)
    m.param("FDBK", 64)
    m.param("DSND", 64)
    run_block(m)
    worst = block_cost(m)
    assert worst < 2400, worst                                 # era ~3800


def test_sends_on_but_inputs_silent(m):
    """Sequencer fermo con SND3 alzato: dopo la coda resta solo la somma del bus."""
    settle(m, FDBK=0)
    gains(m, [0x4000_0000] * 8)
    loud(m)
    run_block(m)
    m.put(SRC_DIG, [1 << 16] * 256)                             # fondo sotto la soglia
    m.put(SRC_ANA, [0] * 256)
    for _ in range(1024 // 16 + 40):                           # coda (TIME + DEP) e linea da svuotare
        run_block(m)
    assert m.longs(m.sym["fx3_idle"], 1) == [1]
    m.put(OUT_A, [5] * 64)
    idle = block_cost(m)
    assert idle < 600, idle
    assert m.longs(OUT_A, 64) == [5] * 64
    loud(m)                                                     # riparte subito
    run_block(m)
    assert m.longs(m.sym["fx3_idle"], 1) == [0]


def test_return_added_with_os_sign(m):
    wet = [(n - 16) * 2000 for n in range(32)]                  # scala 16 bit, 24 kHz
    h0 = [123456, -654321]
    st = 0x5000_3800
    for gain in (32767, -20000, 1):
        m.put(m.sym["fx3_wet"], wet)
        m.put(st, h0)
        m.put(OUT_A, [1000] * 64)
        m.call(m.sym["fx3_ret"], [m.sym["fx3_wet"], gain, OUT_A, st])
        want, h = ret_ref(wet, gain, [1000] * 64, h0)
        assert m.longs(OUT_A, 64) == want
        assert m.longs(st, 2) == h
    m.put(st, [0, 0])
    m.put(OUT_A, [0x7FFF_0000] * 64)
    m.call(m.sym["fx3_ret"], [m.sym["fx3_wet"], 32767, OUT_A, st])
    assert m.longs(OUT_A, 64)[2] == 0x7FFF_FFFF                   # saturazione come l'OS


def test_return_only_on_the_direct_bus(m):
    settle(m, DEP=0, TIME=0, FDBK=0, VOL=127)
    m.put(OUT_B, [-1000] * 64)
    impulse(m)
    for _ in range(3):
        run_block(m)
    assert m.longs(OUT_B, 64) == [-1000] * 64                  # bus del blocco FX analogico: non toccato
    m.param("VOL", 0)
    m.param("DSND", 10)
    m.put(OUT_A, [1000] * 64)
    run_block(m)
    assert m.longs(OUT_A, 64) == [1000] * 64


def test_mix_hook_replays_pushes(m):
    uc = m.uc
    uc.mem_write(0x5000_E000, b"\x4e\x71" * 2 + b"\x4e\x75")   # nop ; nop ; rts (dopo il trampolino)
    sp = STACK - 4
    uc.mem_write(sp, struct.pack(">I", 0x5000_E000))
    uc.reg_write(UC_M68K_REG_SR, 0x2700)
    uc.reg_write(UC_M68K_REG_A7, sp)
    uc.reg_write(UC_M68K_REG_A6, FRAME)
    hit = []

    def at(uc_, addr, size, _):
        if addr == 0x5000_E000:
            hit.append(uc_.reg_read(UC_M68K_REG_A7))
            uc_.emu_stop()
    h = uc.hook_add(UC_HOOK_CODE, at)
    uc.emu_start(m.sym["fx3_mix_hook"], 0, count=200_000)
    uc.hook_del(h)
    assert hit == [STACK - 8]
    assert struct.unpack(">II", uc.mem_read(STACK - 8, 8)) == (0x8000_E0F0, FRAME - 296)


def test_page_slots_and_reverb_tab(m):
    assert fx_context(m, 12) == 1
    assert m.longs(0x41B9_F81C, 9) == [246, 247, 248, 250, 251, 252, 249, 253, 0]
    m.call(m.sym["fx3_amp_stub"])                               # AMP 1: ... DEL REV SND3 VOL; AMP 2: PAN in E
    assert m.longs(0x41B9_F624, 1) == [72] and m.longs(0x41B9_F650, 1) == [72]
    assert m.longs(0x41B9_F674, 1) == [80] and m.longs(0x41B9_F6A0, 1) == [80]
    assert m.longs(m.sym["fx3_reverb_pages"], 2) == [21, 25]


def test_parameters_through_vparams(m):
    assert fx_context(m, 12) == 1
    for name, pid in IDS.items():
        assert m.call(KIT, [0x5000_0000, pid]) == 1
    assert m.call(GET, [0x5000_0000, IDS["VOL"]]) == 100 << 8
    m.param("SPD", 90)
    assert m.call(GET, [0x5000_0000, IDS["SPD"]]) == 90 << 8
    m.param("TYPE", 3)                                          # CHOR FLNG PHSR CRSH
    assert m.call(GET, [0x5000_0000, IDS["TYPE"]]) == 3 << 8
    m.param("TYPE", 9)
    assert m.call(GET, [0x5000_0000, IDS["TYPE"]]) == 3 << 8
    m.call(SET, [0x5000_0000, IDS["WID"], 0x9000, 1])
    assert m.call(GET, [0x5000_0000, IDS["WID"]]) == 127 << 8


@pytest.mark.parametrize("fn, v, text", [("fx3_fmt_type", 0, "CHOR"), ("fx3_fmt_spd", 0, "0.05Hz"),
                                         ("fx3_fmt_spd", 127, "10.0"), ("fx3_fmt_del", 0, "1.0ms"),
                                         ("fx3_fmt_del", 127, "30ms"), ("fx3_fmt_dep", 0, "0.00ms"),
                                         ("fx3_fmt_dep", 127, "8.0ms")])
def test_texts(m, fn, v, text):
    buf = 0x5000_3000
    m.call(m.sym[fn], [0, v << 8, buf])
    raw = bytes(m.uc.mem_read(buf, 12))
    assert raw[:raw.index(0)].decode() == text


def test_patched_bytes():
    want = {0x4008_F3A0: "ae000900ae810900", 0x4008_FB04: "486efed848798000e0f0",
            0x4019_4A50: "42b941b9f6a0", 0x4003_588C: "7201",
            0x4003_5890: "203c401c7fa8", 0x4019_49EA: "42b941b9f674", 0x4004_2CE0: "4fefffa048d77cfc",
            0x4008_F828: "4eb940096890", 0x4004_1E84: "605c"}
    sec3 = eft.unpack(SY, ROOT / "unpacked" / SY.stem, ids=[3])[3].read_bytes()
    for a, orig in want.items():
        assert sec3[a - LOAD:a - LOAD + len(orig) // 2].hex() == orig


def stub_calls(m, addr, nargs, fn, args):
    """Esegue fn con un rts al posto della routine dell'OS a addr; ritorna gli argomenti di ogni chiamata."""
    m.uc.mem_write(addr, b"\x4e\x75")
    got = []

    def at(uc, a, size, _):
        sp = uc.reg_read(UC_M68K_REG_A7)
        got.append([s32(v) for v in struct.unpack(f">{nargs}I", uc.mem_read(sp + 4, 4 * nargs))])
    h = m.uc.hook_add(UC_HOOK_CODE, at, begin=addr, end=addr)
    m.call(fn, args)
    m.uc.hook_del(h)
    return got


def test_send_graphics():
    spec = json.loads(MODS[1].read_text(encoding="utf-8"))
    fixes = {int(p["addr"], 16): p["hex"] for p in spec["patches"] if not p.get("append")}
    assert 0x4019_4E2A not in fixes                              # stock Source-page setup is untouched
    assert 0x4018_F356 not in fixes and 0x4018_F372 not in fixes # FX3 object changes are runtime scoped
    assert fixes[0x4018_B37A] == "41b9d730" and fixes[0x4018_B396] == "41b9d5d0"   # SND3 remains native


def test_type_drawn_as_text(m):
    calls = stub_calls(m, 0x400F_8C18, 9, m.sym["fx3_type_gfx"], [0, 0, 0x5000_5000, 30, 40])
    c = calls[0]
    text = lambda a: bytes(m.uc.mem_read(a, 8)).split(b"\0")[0].decode()
    assert c[:6] == [0x5000_5000, 0x402A_91C0, 38, 45, 1, 0]
    assert (text(c[6]), text(c[7]), text(c[8])) == ("XXXX", "%s", "CHOR")


@pytest.mark.parametrize("page, target", [(25, 0x4003_A244), (21, 0x4004_2CE8), (20, 0x4004_2CE8)])
def test_draw_hook_routes_only_our_page(m, page, target):
    if page == 25:
        assert fx_context(m, 12) == 1
    obj, vec = 0x5000_6000, 0x5000_6100
    m.put(vec, [21, page])
    m.put(obj + 124, [vec])
    m.put(obj + 144, [1])
    uc = m.uc
    sp = STACK - 12
    uc.mem_write(sp, struct.pack(">3I", RET, obj, 0x5000_5000))
    uc.reg_write(UC_M68K_REG_SR, 0x2700)
    uc.reg_write(UC_M68K_REG_A7, sp)
    hit = []

    def at(uc_, a, size, _):
        if a in (0x4003_A244, 0x4004_2CE8):
            hit.append((a, uc_.reg_read(UC_M68K_REG_A7)))
            uc_.emu_stop()
    h = uc.hook_add(UC_HOOK_CODE, at)
    uc.emu_start(m.sym["fx3_draw_hook"], 0, count=1000)
    uc.hook_del(h)
    assert hit[0][0] == target
    assert hit[0][1] == (sp if target == 0x4003_A244 else sp - 96)


@pytest.mark.parametrize("fn, v, text", [("fx3_fmt_fdbk", 0, "0%"), ("fx3_fmt_fdbk", 127, "90%"),
                                         ("fx3_fmt_wid", 64, "91deg"), ("fx3_fmt_wid", 127, "180deg"),
                                         ("fx3_fmt_vol", 0, "-inf"), ("fx3_fmt_vol", 127, "0.0dB"),
                                         ("fx3_fmt_vol", 100, "-4.2dB")])
def test_more_texts(m, fn, v, text):
    buf = 0x5000_3000
    m.call(m.sym[fn], [0, v << 8, buf])
    raw = bytes(m.uc.mem_read(buf, 12))
    assert raw[:raw.index(0)].decode() == text


def test_fx3_claim_restores_native_midi_objects_and_descriptors(m):
    ids = (246, 247, 248, 250, 251, 252, 249, 253)
    desc = lambda pid: 0x4022_D59C + 52 * pid
    slots = [0x6000 + i for i in range(9)]
    m.put(0x41B9_F81C, slots)
    m.put(obj(250), [0xAB00 + i for i in range(21)])
    before_obj = {pid: bytes(m.uc.mem_read(obj(pid), 84)) for pid in ids}
    before_desc = {pid: bytes(m.uc.mem_read(desc(pid), 52)) for pid in ids}
    assert fx_context(m, 12) == 1
    assert m.longs(0x41B9_F81C, 9) == [246, 247, 248, 250, 251, 252, 249, 253, 0]
    assert any(bytes(m.uc.mem_read(desc(pid), 52)) != before_desc[pid] for pid in ids)
    assert fx_context(m, 11) == 0
    assert m.longs(0x41B9_F81C, 9) == slots
    for pid in ids:
        assert bytes(m.uc.mem_read(obj(pid), 84)) == before_obj[pid]
        assert bytes(m.uc.mem_read(desc(pid), 52)) == before_desc[pid]


def test_send_to_delay_adds_scaled_chorus(m):
    settle(m, DEP=0, TIME=0, FDBK=0, VOL=127, DSND=127)
    impulse(m)
    run_block(m)
    wet = m.longs(m.sym["fx3_wet"], 32)                        # DEL = 127: guadagno 32767
    assert any(wet)
    m.put(DLY_IN, [7] * 64)
    run_block(m)                                                # nel delay al blocco dopo
    assert m.longs(DLY_IN, 64) == ret_ref(wet, -32767, [7] * 64, [0, 0])[0]
    m.param("DSND", 0)
    m.put(DLY_IN, [7] * 64)
    run_block(m)
    assert m.longs(DLY_IN, 64) == [7] * 64


@pytest.mark.parametrize("fb", [0, 90])
def test_send_to_delay_with_and_without_feedback(m, fb):
    settle(m, DEP=40, TIME=20, FDBK=fb, VOL=0, DSND=100)       # VOL 0: la mandata al delay basta
    impulse(m)
    ds = round(32767 * (100 / 127) ** 2)
    prev, h, seen = m.longs(m.sym["fx3_wet"], 32), [0, 0], False
    for _ in range(12):                                         # TIME 20: ~68 campioni a 24 kHz
        m.put(DLY_IN, [5] * 64)
        run_block(m)
        want, h = ret_ref(prev, -ds, [5] * 64, h)
        assert m.longs(DLY_IN, 64) == want
        prev = m.longs(m.sym["fx3_wet"], 32)
        seen |= any(prev)
    assert seen


@pytest.mark.parametrize("start", [20, -12, 63, -63])
def test_ramp_does_not_stick_near_zero(m, start):
    """(t - c) >> 5 si fermava a pochi punti da zero: FX3 restava attivo (e pesante) fino al riavvio."""
    m.put(m.sym["fx3_tgt"], [0] * 16)
    m.put(m.sym["fx3_cur"], [start] + [0] * 15)
    m.put(m.sym["fx3_moving"], [1])
    run_block(m)
    assert m.longs(m.sym["fx3_cur"], 1) == [0]


def test_back_to_idle_after_heavy_use(m):
    settle(m, FDBK=127, DEP=127, TIME=127)
    sig = [((n * 7919) % 65536 - 32768) << 15 for n in range(256)]
    m.put(SRC_DIG, sig)
    gains(m, [0x4000_0000] * 8)
    for _ in range(50):
        run_block(m)
    m.put(m.sym["fx3_tgt"], [0] * 16)                           # SND3 a zero, tracce ancora in play
    m.put(m.sym["fx3_moving"], [1])
    blocks = 0
    while m.longs(m.sym["fx3_idle"], 1) != [1]:
        run_block(m)
        blocks += 1
        assert blocks < 3000, "FX3 non torna a riposo"           # 2 secondi
    assert m.longs(m.sym["fx3_cur"], 16) == [0] * 16


def test_nothing_runs_when_nobody_listens(m):
    settle(m, VOL=0, DSND=0)
    m.put(DLY_IN, [5] * 64)
    run_block(m)
    assert m.longs(m.sym["fx3_idle"], 1) == [1]
    assert m.longs(DLY_IN, 64) == [5] * 64
    assert block_cost(m) < 120


@pytest.mark.parametrize("dep, spd, time", [(127, 127, 127), (127, 127, 0), (60, 90, 30)])
def test_chorus_reads_stay_in_the_line(m, dep, spd, time):
    """Senza maschera per campione le prese devono restare nella linea doppia (4 KB a MA + 0xE000)."""
    from unicorn import UC_HOOK_MEM_READ
    settle(m, DEP=dep, SPD=spd, TIME=time, FDBK=100, WID=127)
    loud(m)
    seen = []
    h = m.uc.hook_add(UC_HOOK_MEM_READ, lambda uc, acc, a, size, v, _: seen.append(a),
                      begin=(MA + 0xD000), end=(MA + 0x1_0000))
    m.uc.ctl_flush_tb()                                         # i blocchi gia' tradotti non vedrebbero il gancio
    for _ in range(400):                                        # piu' di un periodo dell'LFO a 10 Hz
        run_block(m)
    m.uc.hook_del(h)
    line = [a for a in seen if a >= (MA + 0xE000)]
    assert line and min(line) >= (MA + 0xE000) and max(line) < (MA + 0xF000)


def test_track_hook_cheap_when_snd3_is_off(m):
    """Il trampolino gira per ogni traccia a ogni blocco, anche senza FX3: con SND3 a zero esce subito."""
    n = count(m, lambda: track(m, 4, 0x6000_0000, 0x6000_0000, 0))
    assert n <= 11, n
    assert track(m, 4, 0x6000_0000, 0x6000_0000, 0x7F00)[4] != 0
    m.put(m.sym["fx3_moving"], [0])
    assert track(m, 4, 0x6000_0000, 0x6000_0000, 0)[4] == 0  # spenta dopo essere stata accesa: azzerata
    assert m.longs(m.sym["fx3_moving"], 1) != [0]


# ---- v0.8: salvataggio nel kit, tipi, nomi e testi per tipo

KIT_PTR, KIT_A, KIT_B = 0x8000_30BC, 0x5000_A000, 0x5000_A100
WOFF = (0, 52, 112, 140)                                        # id interni 0, 0x1A, 0x38, 0x46
DEFV = (0, 60, 64, 64, 0, 64, 0, 100)


def kit_words(m, base):
    return [struct.unpack(">H", m.uc.mem_read(base + o, 2))[0] for o in WOFF]


def put_kit(m, base, vals):
    m.uc.mem_write(base, bytes(142))
    for j, o in enumerate(WOFF):
        w = (vals[2 * j] ^ DEFV[2 * j]) << 8 | (vals[2 * j + 1] ^ DEFV[2 * j + 1])
        m.uc.mem_write(base + o, struct.pack(">H", w))


def text(m, a, n=24):
    return bytes(m.uc.mem_read(a, n)).split(b"\0")[0].decode()


def test_params_saved_in_the_kit_words(m):
    m.put(KIT_PTR, [KIT_A])
    m.uc.mem_write(KIT_A, bytes(142))
    assert m.call(GET, [0x5000_0000, IDS["VOL"]]) == 100 << 8     # parole a zero = default
    m.param("SPD", 90)
    m.param("TIME", 3)
    m.param("VOL", 127)
    m.param("TYPE", 2)
    assert kit_words(m, KIT_A) == [2 << 8 | (90 ^ 60), 3 ^ 64, 0, 127 ^ 100]
    raw = bytes(m.uc.mem_read(KIT_A, 142))
    others = [i for i in range(0, 142, 2) if i not in WOFF and raw[i:i + 2] != b"\0\0"]
    assert others == []                                          # il resto del kit non si tocca


def test_pattern_change_follows_the_kit(m):
    put_kit(m, KIT_A, [0, 10, 20, 30, 40, 50, 60, 70])
    put_kit(m, KIT_B, [2, 11, 21, 31, 41, 51, 61, 71])
    m.put(KIT_PTR, [KIT_A])
    run_block(m)
    assert list(m.uc.mem_read(m.sym["fx3_p"], 8)) == [0, 10, 20, 30, 40, 50, 60, 70]
    m.put(KIT_PTR, [KIT_B])                                       # altro pattern
    run_block(m)
    assert list(m.uc.mem_read(m.sym["fx3_p"], 8)) == [2, 11, 21, 31, 41, 51, 61, 71]
    assert m.call(GET, [0x5000_0000, IDS["DEP"]]) == 21 << 8
    m.call(m.sym["fx3_fmt_dep"], [0, 21 << 8, 0x5000_3000])     # l'interfaccia ridisegna
    assert text(m, m.sym["fx3_n3_s"]) == "FREQ" and text(m, m.sym["fx3_page_l"]) == "Phaser"
    m.uc.mem_write(KIT_B + 0, struct.pack(">H", 0xFF00))         # valori fuori scala: limitati
    run_block(m)
    assert m.uc.mem_read(m.sym["fx3_p"], 1)[0] == 3


@pytest.mark.parametrize("t, n1, n3, n3l", [(0, "SPD", "TIME", "Chorus Delay"),
                                             (1, "SPD", "TIME", "Flanger Delay"),
                                             (2, "SPD", "FREQ", "Phaser Frequency"),
                                             (3, "SRR", "DRV", "Crusher Drive")])
def test_names_follow_the_type(m, t, n1, n3, n3l):
    m.param("TYPE", t)
    assert (text(m, m.sym["fx3_n1_s"]), text(m, m.sym["fx3_n3_s"])) == (n1, n3)
    assert text(m, m.sym["fx3_n3_l"]) == n3l

@pytest.mark.parametrize("t, fn, v, want", [
    (1, "fx3_fmt_fdbk", 64, "0%"), (1, "fx3_fmt_fdbk", 127, "+95%"), (1, "fx3_fmt_fdbk", 0, "-95%"),
    (1, "fx3_fmt_del", 0, "0.10ms"), (1, "fx3_fmt_del", 127, "8.0ms"), (1, "fx3_fmt_spd", 127, "5.00Hz"),
    (2, "fx3_fmt_del", 0, "100Hz"), (2, "fx3_fmt_del", 127, "4.0kHz"), (2, "fx3_fmt_dep", 127, "6.0oct"),
    (2, "fx3_fmt_wid", 127, "100%"), (2, "fx3_fmt_fdbk", 127, "+90%"),
    (3, "fx3_fmt_spd", 0, "24kHz"), (3, "fx3_fmt_spd", 127, "750Hz"), (3, "fx3_fmt_dep", 0, "16bit"),
    (3, "fx3_fmt_dep", 127, "1bit"), (3, "fx3_fmt_del", 127, "24.0dB"), (3, "fx3_fmt_fdbk", 50, "-"),
    (0, "fx3_fmt_type", 2, "PHSR"), (0, "fx3_fmt_type", 3, "CRSH")])
def test_texts_per_type(m, t, fn, v, want):
    m.param("TYPE", t)
    buf = 0x5000_3000
    m.call(m.sym[fn], [0, v << 8, buf])
    assert text(m, buf, 12) == want


def s16(v):
    return max(-32768, min(32767, v))


def ph_coef(tim):
    import math
    t = [math.tan(math.pi * 20 * 2 ** (i / 32) / 24000) for i in range(292)]
    tab = [round(4096 * (x - 1) / (x + 1)) for x in t]
    fidx = round(32 * 256 * math.log2(100 * 40 ** (tim / 127) / 20))
    i, f = fidx >> 8, fidx & 0xFF
    return tab[i] + (((tab[i + 1] - tab[i]) * f) >> 8)


def phaser_ref(bus, st, a, fb, w):
    """4 celle allpass: y = a (x - s_k) / 4096 + s_k-1; sinistra (x + y) / 2, destra sinistra - w y."""
    out = []
    for b in bus:
        u = b >> 16
        if fb:
            u = s16(u + ((s32(st[4] * fb) >> 8) >> 7))
        x = u
        for k in range(1, 5):
            y = (s32((x - st[k]) * a) >> 12) + st[k - 1]
            st[k - 1] = x
            x = y
        st[4] = x
        left = s16((x + st[0]) >> 1)
        out += [left, s16(left - (s32(x * w) >> 14))]
    return out


@pytest.mark.parametrize("fdbk", [64, 127, 10])
def test_phaser_matches_the_model(m, fdbk):
    settle(m, TYPE=2, DEP=0, TIME=70, FDBK=fdbk, WID=90, VOL=127)
    x = (fdbk - 64) * 29491
    fb = max(-29491, min(29491, int(x / 63)))                     # come la divisione in C (verso zero)
    w = 16384 * 90 // 127
    st = [0] * 5
    loud(m)
    for _ in range(6):
        run_block(m)
        bus = m.longs(m.sym["fx3_bus"], 16)
        assert m.longs(m.sym["fx3_wet"], 32) == phaser_ref(bus, st, ph_coef(70), fb, w)


def test_crusher_matches_the_model(m):
    spd, dep, tim = 40, 90, 60
    settle(m, TYPE=3, SPD=spd, DEP=dep, TIME=tim, VOL=127)
    n = 1 + (31 * spd + 63) // 127
    sh = (15 * dep + 63) // 127
    g = round(256 * 10 ** (24 * tim / 127 / 20))
    cnt, hold, seen = 32 % n, 0, set()                          # i due blocchi muti di settle
    loud(m)
    for _ in range(4):
        run_block(m)
        want = []
        for b in m.longs(m.sym["fx3_bus"], 16):
            cnt += 1
            if cnt >= n:
                cnt = 0
                hold = s16(((b >> 16) * g) >> 8) & -(1 << sh)
            want += [hold, hold]
        assert m.longs(m.sym["fx3_wet"], 32) == want
        seen |= set(want)
    assert len(seen) > 4


def test_type_change_drops_the_old_tail(m):
    settle(m, TYPE=0, FDBK=120, VOL=127)
    loud(m)
    for _ in range(10):
        run_block(m)
    m.put(SRC_DIG, [0] * 256)
    m.put(SRC_ANA, [0] * 256)
    m.param("TYPE", 1)
    m.param("FDBK", 64)                                         # flanger senza retroazione
    run_block(m)
    run_block(m)
    assert m.longs(m.sym["fx3_wet"], 32) == [0] * 32          # linea svuotata al cambio


@pytest.mark.parametrize("t", [0, 1])
def test_time_jumps_glide_and_reads_stay_in_the_line(m, t):
    from unicorn import UC_HOOK_MEM_READ
    settle(m, TYPE=t, DEP=127, SPD=127, TIME=0, FDBK=110, WID=127)
    loud(m)
    seen = []
    h = m.uc.hook_add(UC_HOOK_MEM_READ, lambda uc, acc, a, size, v, _: seen.append(a),
                      begin=(MA + 0xD000), end=(MA + 0x1_0000))
    m.uc.ctl_flush_tb()                                         # i blocchi gia' tradotti non vedrebbero il gancio
    for k in range(300):                                        # TIME 0 <-> 127 di colpo, ripetutamente
        if k % 40 == 0:
            m.param("TIME", 127 if (k // 40) % 2 == 0 else 0)
        run_block(m)
    m.uc.hook_del(h)
    line = [a for a in seen if MA + 0xE000 <= a < MA + 0xF000]
    assert line and min(line) >= (MA + 0xE000) and max(line) < (MA + 0xF000)


LOOK = {0: [(0x41B9_D6B0, 0), (0x41B9_D730, 0), (0x41B9_D7D0, 0), (0x41B9_DCD0, 0x41B9_D5E0), (0x41B9_D740, 0x41B9_D660)],
        1: [(0x41B9_D6B0, 0), (0x41B9_D7E0, 0), (0x41B9_D7D0, 0), (0x41B9_DC70, 0x41B9_D660), (0x41B9_D740, 0x41B9_D660)],
        2: [(0x41B9_D6B0, 0), (0x41B9_D7E0, 0), (0x41B9_D760, 0x41B9_D660), (0x41B9_DC70, 0x41B9_D660),
            (0x41B9_D740, 0x41B9_D660)],
        3: [(0x41B9_D780, 0x41B9_D660), (0x41B9_D830, 0), (0x41B9_DCB0, 0x41B9_D670), (0, 0), (0, 0)]}


def obj(i):
    return 0x41B9_FA24 + 84 * i


@pytest.mark.parametrize("t", [0, 1, 2, 3, 0])
def test_icons_and_slots_follow_the_type(m, t):
    assert fx_context(m, 12) == 1
    protos = {a for row in LOOK.values() for pair in row for a in pair if a}
    for a in protos:                                            # prototipi "costruiti all'avvio": firme
        m.put(a, [a, a + 1, a + 2, a + 3])
    if t == 0:
        m.param("TYPE", 3)                                      # da un altro tipo
    m.param("TYPE", t)
    for i, pid in enumerate((247, 248, 250, 251, 252)):
        g, st = LOOK[t][i]                                      # {0, 0, fx3_mgr, invoker del prototipo}
        mgr = m.sym["fx3_mgr"]
        assert m.longs(obj(pid) + 36, 4) == ([0, 0, mgr, g + 3] if g else [0] * 4), (pid, hex(g))
        assert m.longs(obj(pid) + 68, 4) == ([0, 0, mgr, st + 3] if st else [0] * 4), pid
    want = [246, 247, 248, 250, 0, 0, 249, 253] if t == 3 else [246, 247, 248, 250, 251, 252, 249, 253]
    assert m.longs(0x41B9_F81C, 8) == want                      # il crusher lascia vuote FDBK e WID


def test_audio_interrupt_never_rewrites_the_ui(m):
    """Cambio di pattern a un kit con altro tipo: l'interrupt aggiorna i valori, nomi e icone li cambia
    solo l'interfaccia (al primo disegno o lettura)."""
    m.call(m.sym["fx3_fmt_spd"], [0, 0, 0x5000_3000])          # interfaccia: tipo 0 sistemato
    m.put(obj(247) + 36, [0x1111] * 4)
    put_kit(m, KIT_A, [3, 10, 20, 30, 40, 50, 60, 70])
    m.put(KIT_PTR, [KIT_A])
    gains(m, [0x4000_0000])
    run_block(m)
    assert m.uc.mem_read(m.sym["fx3_p"], 1)[0] == 3
    assert m.longs(obj(247) + 36, 4) == [0x1111] * 4             # non toccata dall'interrupt
    assert text(m, m.sym["fx3_n1_s"]) == "SPD"
    m.call(m.sym["fx3_fmt_spd"], [0, 0, 0x5000_3000])
    assert text(m, m.sym["fx3_n1_s"]) == "SRR"
    assert m.longs(0x41B9_F81C + 16, 2) == [0, 0]


# ----------------------------------------------------------------------------- kit nel file (FUNC+YES/NO)
KSER, KDES = 0x400A_6D96, 0x400A_6D2E          # blocco della FX track: kit -> file, file -> kit
FILE, KBLK, KIT2 = 0x5000_6000, 0x5000_6100, 0x5000_6200
FX3_WORDS = (0, 0x1A, 0x38, 0x46)               # parole del kit usate da fx3
LFO_DEST = (4, 12)                              # destinazioni degli LFO: indice convertito con la tabella


def valid(words):
    """Parole del kit con destinazioni LFO valide (0 = nessuna), come le scrive l'OS."""
    return [0 if i in LFO_DEST else w for i, w in enumerate(words)]


def round_trip(m, words, file_fill=0x00):
    """Blocco del kit (71 parole) -> file -> nuovo kit, con le funzioni dell'OS. -> parole rilette."""
    m.uc.mem_write(KBLK, struct.pack(">71H", *words))
    m.uc.mem_write(FILE, bytes([file_fill]) * 160)
    assert m.call(KSER, [FILE, KBLK]) & 0xFF == 1
    m.uc.mem_write(KIT2, b"\xee" * 142)
    assert m.call(KDES, [KIT2, FILE]) & 0xFF == 1
    return list(struct.unpack(">71H", m.uc.mem_read(KIT2, 142)))


def test_stock_kit_file_loses_fx3_words():
    """Senza gli agganci (OS stock): la tabella delle posizioni perde 0x1A e 0x46 e rilegge nella 0 il
    valore della 0x1A. Era FUNC+NO che portava fx3 dal chorus al crusher (issue #4)."""
    m = Machine()
    for addr, orig in ((KSER, "2f0b2f0a246f000c"), (KDES, "4feffff448d71c00")):
        m.uc.mem_write(addr, bytes.fromhex(orig))
    words = valid([0x1000 + i for i in range(71)])
    back = round_trip(m, words)
    assert back[0] == words[0x1A] and back[0x1A] == 0xEEEE and back[0x46] == 0xEEEE
    assert [i for i in range(71) if back[i] != words[i]] == [0, 0x1A, 0x46]


def test_kit_file_keeps_every_word():
    m = Machine()
    rnd = random.Random(4)
    for _ in range(20):
        words = valid([rnd.randrange(0x10000) for _ in range(71)])
        assert round_trip(m, words, file_fill=rnd.randrange(256)) == words
    raw = m.uc.mem_read(FILE + 148, 8)
    assert struct.unpack(">4H", raw) == (0x5348, words[0], words[0x1A], words[0x46])


def test_kit_file_without_marker_gives_fx3_defaults():
    """File scritto dall'OS stock (o da v0.8.0): niente marcatore -> parole di fx3 a zero (= default),
    non il valore spostato dalla 0x1A."""
    m = Machine()
    words = valid([0x2000 + i for i in range(71)])
    m.uc.mem_write(KBLK, struct.pack(">71H", *words))
    m.call(KSER, [FILE, KBLK])
    m.uc.mem_write(FILE + 148, bytes(8))                    # come l'OS stock: byte azzerati
    m.uc.mem_write(KIT2, b"\xee" * 142)
    m.call(KDES, [KIT2, FILE])
    back = struct.unpack(">71H", m.uc.mem_read(KIT2, 142))
    assert back[0] == back[0x1A] == back[0x46] == 0
    assert all(back[i] == words[i] for i in range(71) if i not in (0, 0x1A, 0x46))


def test_kit_hooks_keep_failure_paths():
    m = Machine()
    assert m.call(KSER, [0, KBLK]) & 0xFF == 0
    m.uc.mem_write(FILE, struct.pack(">I", 7))              # tipo di blocco sbagliato: l'OS rifiuta
    assert m.call(KDES, [KIT2, FILE]) & 0xFF == 0
