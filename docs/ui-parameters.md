# UI and parameters

## Parameter descriptors

Table at `0x4022D59C`, **505 records × 52 B, index = logical id**.

| Offset | Field |
|---|---|
| +0 / +4 | group / internal id (the value key) |
| +8 / +12 / +16 | min / max / default (UI values, 0..0x7F00 = 0..127) |
| +24 / +28 | MIDI CC (`cc<<16 \| 0xFFFF`) / NRPN |
| +32 | storage index |
| +36 | capability flags (e.g. `0xE00` → listed as modulation destination) |
| +40 / +48 | long / short name pointers |

Aliases share group + internal id. Ids 270–504 are machine parameters; hidden ids and their use by the mods: see [below](#hidden-ids-used-by-the-mods).

## Pages

Static C++ initializer `0x401885D2–0x401968F4` builds page objects in BSS (44 B: short name, long name, 8 logical ids).

| Page | Address | Slots |
|---|---|---|
| MIX3 External Mixer | `0x41B9F7E8` | `126 · – · – · – · 129 · 130 · 128 · 132` |
| FX track SYN (FX Drive) | `0x41B9F948` | `– ×7 · 150 (DRIVE)` |

Slots are read at draw time: changing them at runtime changes the page (0 = empty slot). AMP slots: page 1 `0x41B9F60C` / `0x41B9F638` (AHD / ADSR variant), page 2 `0x41B9F664` / `0x41B9F690`.

- Page elements: array of 37 at `0x41B9F3C8` (44 B each), index → element `0x4007B9D0`. Page 25 ("OB8 / Outbox 8") is a Digitakt leftover, always empty: fx3 uses it.
- **Tabs** are page widgets built from constant arrays of page indices + count (`0x4017DA3A`), e.g. DELAY `{20}` at `0x401C7FAC`, REVERB `{21}` at `0x401C7FA8` (built at `0x40035890`), generic class `0x40042B58`. A tab with N pages cycles them on its key; widget +124 = page vector, +144 = current position. The page's virtual +188 returns the id under an encoder.
- Per-object fields before the prototypes: +0 type (0 = plain value, others change the encoder step: MIDI-track ids use 4/5, toggles 12), +4 value prototype (`d3` = discrete/standard, as in LFO MODE).

## Drawing

- Each slot asks a parameter model (by descriptor group: 61/55 trig, 49–54 FX/global, 63 special, else track sound) to draw: +36 graphic called as `invoker(fn, value, ctx, x, y)`; the slot box is about x−1…x+18, y…y+16.
- +68 empty = no style: the default renderer (as LFO MODE, COND). Text: `0x400F8C18(ctx, font, x, y, centred, 0, width template, fmt, ...)` (vsprintf); fonts `0x402A9DC4` (3×6), `0x402A91C0` (4×6), `0x402A7354`.
- Images: 1-bit, 28 B (`+4` width, `+8` height, `+12` words per row, `+16` pixels, `+20` mask, MSB = left), blitted by `0x400F8DAC(ctx, image, x, y, centred)`. Icon sets live in RAM (built from resources), frame by value `0x400F927C`.
- Class overrides: the DELAY/REVERB tab draws slots 5–6 as one HPF/LPF filter box (`0x40042CE0`); the AMP tab (`0x40041DA6`) draws ids 73–77 (and unknown ids) as part of the envelope graph, without their own graphic.

## Keys

- Key events: +12 code (trig keys 1–16 = 24–39, encoders A–H = 40–47), +16 flags (bit 0 down, bit 3 auto-repeat). All key events pass through `0x4000839E`, called at `0x4000B420`.
- Page key handler `0x4003BC74` (encoder press: id under the encoder via +188). `KeyboardView::consumeKeyEvent` `0x4002E850`: keys 13–16 (retrig) branch at `0x4002EA92`, after the mode checks.

## Hidden ids used by the mods

| Id | Stock meaning | Mod use |
|---|---|---|
| 262–268 | Digitakt-derived "CC1–CC7 Select" descriptor labels | master-comp (virtual, via [vparams](../mods/vparams)); the labels do not establish anything about Syntakt MIDI-track playback |
| 144 | amp delay time | the kit word of 144 stores fx3 |
| 72 | amp "Delay Time", saved per track, unused | fx3 SND3 (native, per track) |
| 269, 124 | Digitakt MIDI-track "CC8 Select", reverb routing | beat-repeat RPT1/RPT2 (virtual) |
| 246–253 | Globally reusable descriptor IDs | fx3 page (virtual); on RC1 their global reuse can expose FX3 controls on a MIDI track's SYN page |

Ids 1–5 and 11–18 are tied to MIDI CCs (bank select, data entry, all notes off…): not reusable.

**Hidden is not free.** Ids without an obvious stock page are often *aliases* the OS swaps onto a page: 59 GAIN replaces 60 RESO for track filter types 2–6 (`0x40042140` in 1.42), 122 REV shows on MIXER page 2, 91/101 SLEW replace SPH, 125 IN and 127 PAN replace IN LR and BAL, 113 is the delay mix (114). Same group + internal id as the visible parameter = alias: do not reuse. The RC1 FX3 regression demonstrates that globally reused IDs also need real MIDI-track UI coverage; it does not by itself show that MIDI playback is broken. `tests/test_id_audit.py` checks every id the mods register.

## Per-parameter objects

`0x41B9FA24 + 84·id` (built at boot). Four `std::function`s copied from shared prototypes:

| Offset | Role |
|---|---|
| +20 | value → text formatter, called as `invoker(fn, value 0..0x7F00, char *buf)` (numeric: `0x40077F86`). Replaceable at runtime with our own `{data, data, manager, invoker}`; the manager must be non-null |
| +36 | value graphic (knob / bar / bipolar). DRIVE has its own (`0x40071408`) |
| +68 | graphic style: `0x41B9D5D0` bar, `0x41B9D670` knob, `0x41B9D660` bipolar ("hourglass") |

The init code (`pea <prototype>`) decides the look of each id; patching that operand changes it. At runtime, write `{0, 0, own manager, invoker}` from UI code only — details and a list of icons in the [modding guide](modding-guide.md#5-text-icons-and-styles).
It copies with `0x401882BE(dst, src)`: plain `std::function` copy (manager called with *clone*). Formatter groups: `0x41B9DFD0` plain 0–127 (269 ids), `0x41B9DFB0` numeric (41), `0x41B9DF90` bipolar (40), `0x41B9DDB0` times with INF (18).

**Active track** (0–11, 12 = FX track): `0x4001FF74(project + 48)`, project = `*0x444E13F4` (singleton `0x4016E804`). Track parameters 58–85 are shared by all tracks.

## Reading and writing values

Kit-level parameters go through three functions, keyed by **logical id**:

| Function | Address |
|---|---|
| is kit parameter? | `0x4000D870(obj, id)` |
| get | `0x4000D94A(obj, id)` → value |
| set | `0x4000DA32(obj, id, value, flag)` → clamps, stores, notifies (UI redraw) |

Group handlers use jump tables by logical id (e.g. external mixer: get `0x4000C8B0`, set `0x4000C9A4`).

## Kit storage and "global FX"

- UI kit struct (`obj->vfunc40`): internal mixer +2…+26, external +28…+45, DRIVE +46, FX filter +48…+71, FX amp +72…+99.
- Pattern kit (`*0x800030BC`, 142 B): the FX track's parameters, **one word per internal id** (offset = 2 × id, ids 0…0x46), copied whole to the engine (`0x80002874`). Blocks: LFO +2…+33, delay +34…+53, reverb +54…+69, external +70…+87, filter +88…+111, amp +112…+139 (DRIVE +124). Words the OS does not use: ids 0, 0x1A, 0x24, 0x27, 0x29, 0x2A, 0x37, 0x46 (+ 0x38 = hidden id 144).
- Global flags `0x43BDE444`: bit 0 internal mixer, 1 external, **2 SYN (DRIVE)**, 3 filter, 4 amp. Enabled blocks are copied (memcpy) between kit and the global container `0x41B9D3B0`; the engine sync `0x400A1D18` copies whole blocks.
- **Unused words**, saved with the kit: external block UI +30, +36, +40, +42 (pattern kit +72, +78, +82, +84) → master compressor; pattern kit +0, +52, +112, +140 (ids 0, 0x1A, 0x38, 0x46) → fx3; +110 (id 0x37) → beat-repeat.
- **Kit file format** (FUNC+YES/NO, project save): the FX block is written by `0x400A6D96` and read by `0x400A6D2E` through a position table (`0x40233E78` / `0x40233F90`) that **drops words 0x1A and 0x46 and reads word 0 back from 0x1A**; LFO destinations (words 4, 12) go through the same table. Bytes +148…+155 of the 156-byte file block are zeroed and never read: fx3 keeps its three words there. A new kit word must survive this round trip (`tests/test_fx3.py`).
