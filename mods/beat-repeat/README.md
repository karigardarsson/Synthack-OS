# beat-repeat

Sequencer beat repeat for live use.

- **RPT1 / RPT2** on the FX track TRIG page (first two slots): `1/16 · 1/8 · 3/16 · 1/4 · 1/2 · 1BAR`, shown as text.
- With the FX track selected, **hold retrig key 13** (RPT1) or **14** (RPT2) to repeat; release to resume **in time**, where the pattern would have been. Holding both: the last pressed wins.
- Keys 15–16, and keys 13–16 on other tracks, keep the stock retrig.

Every track loops the slice of that length (in its own steps, aligned to its grid) that contains the step just played. It repeats sequencer steps — notes and p-locks — so it works on **all tracks, analog ones included**. Rates are saved with the kit (per pattern), in a word of the pattern kit the OS never uses (internal id 0x37); older projects load 1/16 and 1/8.

## How it works

- Sequencer tick interrupt `0x4008C924`: per track, step index `0x43BD73FC + t` advances and wraps on the track/pattern length. A hook at the end of each track's iteration (`0x4008D152`) rewinds it into the slice and keeps the real position.
- Keys: hook in the keys 13–16 branch of `KeyboardView::consumeKeyEvent` (`0x4002EA92`), after the OS mode checks; releases are also caught at the event dispatcher (`0x4000B420`).
- RPT1/RPT2 reuse ids 269/124 through [vparams](../vparams), but only while the FX track owns its TRIG page. The scoped UI helper restores the captured native MIDI descriptor, object, page-slot, and get/set routes before a MIDI page draws. Up to v0.8.0 RPT1 was id 113, an alias of the delay mix: moved in v0.8.1.
- `br.c` (C, ColdFire gcc) in the mod area at offset `+0x4000`.

Test: `tests/test_beat_repeat.py` (step sequences, every length, short tracks, rate switch, keys and native fallback, release after track change, parameters, texts, slot graphic).
