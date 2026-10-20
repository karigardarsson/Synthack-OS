# Syntakt MAX Modular Builder OS 1.41 — User Guide

Syntakt MAX Modular Builder is an unofficial, offline Windows builder for
creating an experimental Syntakt OS 1.41 image from **your own unmodified
official OS 1.41 `.syx` file**. It offers eight selectable feature groups:
SY FM4, Master Compressor, FX3, Beat Repeat, Déjà Vu LFO, the expanded SY
CHORD wave bank, Dual Mono Input and Readable Values.

It is not an Elektron product and is not affiliated with Elektron. The builder
does not transfer firmware, connect to a Syntakt, or include Elektron firmware.
Use it only with a backed-up instrument and the official recovery path close at
hand.

## Read this before building

### Evidence labels used in this guide

| Label | Meaning |
| --- | --- |
| **HARDWARE-TESTED** | Observed on a real Syntakt for the exact image stated. It is not an exhaustive regression claim. |
| **BUILD-VALIDATED** | The host-side builder accepted the stock input and passed patch, dependency, placement, checksum, decoded-section, CPU2 and boot-margin checks. It is not a hardware-use claim. |
| **SOURCE-DERIVED** | Control location or persistence follows the patched source and tests, but needs a real-instrument check. |
| **NEEDS HARDWARE CONFIRMATION** | Do not treat this as established behaviour until it has been checked on the exact generated image. |

The builder accepts only the official OS 1.41 SHA-256:

```text
8e2488f462c4a5656396a895f113bcd415e9900fa8709340dccf45d4cb9ed19e
```

All 255 non-empty modular selections have **BUILD-VALIDATED** patch
compatibility and placement. That does not make 255 musical workflows or
hardware combinations proven.

### Back up and make a recovery plan

1. Back up projects and sounds with your established Elektron workflow.
2. Keep an unchanged official OS 1.41 `.syx` and a known-good image available.
3. Build only from a private copy of the official file. Preserve the generated
   image's SHA-256 and its adjacent selected-mods JSON report.
4. Read [Recovery](../tools/max/modular_builder/RECOVERY.md) before attempting
   a manual OS transfer. If a problem occurs, stop rather than resetting or
   erasing data.

The builder targets Windows 10/11 x64 and is unsigned. Windows 11 x64 is the
tested platform; Windows 10 x64 is a target, not an independently verified
platform. It works offline and bundles what it needs at runtime; it does not
require Python, Git, GCC or MSYS2 to be installed separately.

## Build an image

1. Extract the complete RC1 ZIP and run
   `Syntakt-MAX-Modular-OS1.41-Builder.exe`.
2. Select the official OS 1.41 `.syx`. Confirm that the displayed input hash is
   the one above.
3. Choose a preset or choose feature groups under **CUSTOM**.
4. Select **Build and Save Firmware** and give the output a new, writable name.
   The builder will not overwrite an existing `.syx` or selected-mods report.
5. Keep both the output's SHA-256 and the JSON report. They identify what was
   actually built.
6. Treat OS installation as a separate manual activity using Elektron's
   supported process. Do not interrupt power or transfer.

### Presets, dependencies and fingerprints

| Preset | What it selects | Output SHA-256 | Status |
| --- | --- | --- | --- |
| **Original MAX 1.0** | The seven established MAX groups (not FM4) | `7cb4bfd3da4af9c417ae812ec205036a85a430f3be62263cf58e6ae31df2c093` | **HARDWARE-TESTED** image; also BUILD-VALIDATED. |
| **MAX FULL + FM4** | All eight groups | `3eaaf21ca0ed137eba14e321269d69383769da9210f818d0ad1db24356696d89` | **BUILD-VALIDATED**; byte-identical to the initially hardware-tested integrated candidate. The complete combined acceptance session remains pending. |
| **FM4 ONLY** | SY FM4 with required support modules | `1f74cad579848132aad0b25bc9371b7dd2bbee72961cd98a3e351cd8695e860e` | **BUILD-VALIDATED**, experimental on hardware. It does not inherit the initial FM4 hardware claim. |
| **CUSTOM** | Any non-empty combination | Varies; record the builder result | **BUILD-VALIDATED** structurally, hardware behaviour unproven for that exact image. |

Dependencies are automatic. Master Compressor, FX3, Beat Repeat, Readable
Values and FM4 receive the shared support they require; you do not manually
select infrastructure. The previous standalone FM4 RC1 fingerprint is not a
modular-builder target, so historical standalone-FM4 observations do not prove
the FM4 ONLY profile.

## Feature guide

### SY FM4

**What it does.** SY FM4 adds four-operator FM algorithms to **SY TONE**.
**ALGO 0** remains stock SY TONE; **ALGO 1–11** select the FM algorithms.

**Where it is.** Select the SY TONE machine and open **SYN page 2**. The final
integrated metadata confirms these eight Page-2 controls: ALGO, RAT3, LEV3,
DEC3, RAT4, LEV4, DEC4 and DET. The physical encoder order for the last four
is not independently documented in this checkout, so this guide deliberately
does not claim one.

| Control | Purpose |
| --- | --- |
| ALGO | Selects stock (0) or one of the eleven FM algorithms (1–11). |
| RAT3 / LEV3 / DEC3 | Ratio, level and decay for operator 3. |
| RAT4 / LEV4 / DEC4 | Ratio, level and decay for operator 4. |
| DET | FM detune. |

**First test.** On a disposable SY TONE sound, play a short pattern, select
ALGO 1, then make a small RAT3 or LEV3 change on SYN page 2. Add a held-trig
lock, save, reload and compare. Initial FM4 hardware observations cover sound,
editing, a parameter lock and save/reload. This is not a claim that every
algorithm or edit path is proven.

**Musical starting points.**

- Begin with moderate operator levels and long decays; introduce RAT3 or RAT4
  gradually for movement rather than starting with both at maximum.
- Use a p-lock on ALGO or one operator level for a single accented step, then
  save a separate sound before exploring aggressive ratios.

**Persistence and limit.** Initial FM4 hardware observations cover sound,
editing, p-lock and save/reload; source and emulator tests additionally cover
logical sound storage and pattern-lock lanes. The **FM4 ONLY** profile has a
different firmware fingerprint and heap-loader arrangement, so it does not
inherit that hardware-validation claim and needs its own coverage. The full
MIDI/SYN/FX3 interaction is not established for every modular image.

### Master Compressor

**What it does.** A feed-forward compressor detects the analogue mix before
the master VCAs and controls the master VCA path. It is a master-bus processor,
not a per-track insert, and has no dry/wet control.

**Where it is.** Select the **FX track → SYN** page.

| Control | Range / behaviour |
| --- | --- |
| THR | Threshold, −60 to 0 dB. |
| ATK | Attack, 0.1 to 100 ms. |
| REL | Release, 10 ms to 2 s. |
| MUP | Makeup, 0 to +24 dB, limited by master volume range. |
| RAT | OFF, 1.5:1, 2:1, 3:1, 4:1, 6:1, 8:1, 16:1 or 20:1. |
| GR | Read-only gain-reduction meter; full bar means no reduction. |
| COMP | On/off comparison switch. It starts on and is not saved. |
| DRIVE | Unchanged stock control. |

**First test.** At a safe monitoring level, start with RAT off. Turn RAT to
2:1 or 4:1, lower THR until GR moves, then compare with COMP. Keep MUP low at
first so comparison is not only louder-versus-quieter.

**Two musical uses.**

- For a glued drum-and-synth pattern, choose a slower ATK, a moderate ratio and
  adjust THR until only the loudest hits move GR.
- For a pumping transition, use a faster ATK and shorter REL, then automate or
  p-lock the *source material* rather than expecting a dry/wet blend.

**Saving and limits.** The compressor settings are source-defined as kit
settings (per pattern), or global when SYN global is on; existing projects load
with it off. Toggling the external-input mixer's global setting also copies the
shared storage block. Treat FUNC+NO-related behaviour as **NEEDS HARDWARE
CONFIRMATION**; a reported transient is not resolved by RC1.

### FX3: chorus, flanger, phaser and crusher

**What it does.** FX3 is a third send effect alongside delay and reverb. Audio
tracks send to it with SND3; the effect can then return directly and/or feed the
delay.

**Where it is.**

- On an audio track: **AMP page 1, slot G = SND3**. PAN moves to page 2.
- On the FX track: press **REVERB** again to reach **REVERB page 2**.

| TYPE | B | C | D | E | F |
| --- | --- | --- | --- | --- | --- |
| CHOR | SPD 0.05–10 Hz | DEP 0–8 ms | TIME 1–30 ms | FDBK 0–90% | WID 0–180° |
| FLNG | SPD 0.02–5 Hz | DEP 0–4 ms | TIME 0.1–8 ms | FDBK −95–+95% | WID 0–180° |
| PHSR | SPD 0.02–5 Hz | DEP 0–6 oct | FREQ 100 Hz–4 kHz | FDBK −90–+90% | WID 0–100% |
| CRSH | SRR 24 kHz–750 Hz | BITS 16–1 | DRV 0–24 dB | — | — |

On this page, **DEL** sends FX3 into delay and **VOL** is the FX3 return. For
flanger and phaser, feedback is bipolar: centre is none. Crusher is mono and
hides unused controls.

**First test.** On a single audio track, bring SND3 up modestly, select CHOR
and raise VOL. Compare TYPEs before using feedback. Test DEL only after the
direct return is audible.

**Two musical uses.**

- Use a small SND3 amount and a slow CHOR for width, leaving the original
  track present on the dry path.
- For a controlled transition, change CRSH BITS or SRR by hand, then return to
  a saved normal value. FX3 parameter p-locking itself is not documented here
  as verified behaviour.

**Saving and limits.** SND3 is saved with each track in the kit and is
source-supported as p-lockable. FX3 settings are kit settings, per pattern like
delay and reverb. FX3 runs at 24 kHz, so it is intentionally not a
full-bandwidth parallel bus. FX3 parameter-lock behaviour is not claimed as
verified here.

**Known RC1 MIDI/FX3 routing regression.** FX3 controls can appear on a MIDI
track's SYN page because the FX3 implementation globally reuses descriptor IDs
246–253. This observation does not establish that MIDI playback is broken. A
temporary workaround is to build a **CUSTOM** image with **FX3 unchecked**;
that omits this particular FX3 routing modification. It requires rebuilding and
reinstalling firmware—there is no live toggle—and it is not a hardware-proven
fix. Record the generated-image hash when testing it.

### Beat Repeat

**What it does.** Beat Repeat loops the currently played sequencer slice,
including notes and parameter locks, on every track including analogue tracks.

**Where it is.** Select the **FX track → TRIG** page. **RPT1** and **RPT2**
occupy its first two slots. During playback, hold FX-track **retrig key 13**
for RPT1 or **14** for RPT2; release to return in time. If both are held, the
last pressed wins. Keys 15–16 and retrig keys on other tracks remain stock.

RPT1/RPT2 choices are: **1/16, 1/8, 3/16, 1/4, 1/2, 1BAR**.

**First test.** With a simple pattern running, set RPT1 to 1/8, hold key 13 for
one beat, then release. Confirm the pattern returns to its normal timeline.

**Two musical uses.**

- Put RPT1 at 1/8 and RPT2 at 1/2 to switch between fill-like and breakdown
  repeats without changing a track's own sound.
- Lock an interesting note or sound change underneath the repeat; the loop
  repeats the sequencer slice and its p-locks, not merely audio.

**Saving and limit.** Rates are stored with the kit (per pattern). Older
projects use 1/16 and 1/8 defaults. **NEEDS HARDWARE CONFIRMATION** for live
performance interactions beyond the described key handling, especially with
any custom modular image.

### Déjà Vu LFO

**What it does.** Déjà Vu adds two looping random LFO shapes while retaining
the seven native shapes:

- **DV-F** is free-running.
- **DV-T** restarts on notes.

Use the normal LFO shape selector. **MODE** chooses a 2, 4, 8, 16 or 32-step
loop; **SPH** moves from new random values at 0, through repeating behaviour
around 64, toward reordering at 127.

**First test.** Select DV-F, choose MODE 2, set SPH near 0 and apply a subtle
amount to filter frequency or pitch. Then try MODE 8 and SPH 64. Switch to
DV-T to hear the note-restarted version.

**Two musical uses.**

- DV-T with modest depth is useful for repeatable variation on each note while
  keeping the pattern's rhythm clear.
- DV-F with a longer MODE and moderate SPH can add slow movement to pads or
  effects without writing automation.

**Persistence and limit.** The guide has source-derived behaviour and
hardware evidence for Original MAX 1.0, but custom images still need an exact
hardware check. Sounds using DV behaviour will not retain that behaviour after
returning to stock firmware.

### Expanded SY CHORD 31-wave bank

**What it does.** This fixed bank replaces selected SY CHORD wave positions
with saw, pulse, harmonic, synthetic and chord textures, including matching
graphics. **WAVE 0 remains stock**. The added anchors are WAVE 4, 8, ... 124;
intermediate positions interpolate as normal.

| WAVE range | Examples |
| --- | --- |
| 4–48 | Saw, soft/bright/odd/folded/reverse saw; square and pulse variants |
| 52–68 | Organ, drawbar, hollow odd, fifth and octave stacks |
| 72–92 | FM bright/glass/wood, wavefold, formant, sync edge |
| 96–124 | Major, minor, sus4, diminished, major 7, dominant 7, minor 7 and major 9 chords |

**Where it is.** Choose **SY CHORD → SYN → WAVE**. Use WAVE 4 for a simple
first check and WAVE 96 for the Major chord texture; verify WAVE 0 remains the
native sound.

**Two musical uses.**

- Use the lower saw/pulse positions as a quick tonal base, then p-lock WAVE to
  a harmonic or synthetic position for an accent.
- The chord waves place their root four octaves above the played note; lower
  TUNE when you want a lower apparent chord register.

**Saving and limits.** Existing sounds or patterns that use replaced or
neighbouring WAVE values can sound different. Bright waves may alias at high
pitches. Save a copy before auditioning older work, and do not expect stock
firmware to reproduce the added bank.

### Dual Mono Input

**What it does.** When external input routing is mono, Dual Mono gives the left
and right physical inputs independent level controls. Stereo routing remains
stock.

**Where it is.** Set **SETTINGS → AUDIO ROUTING → EXTERNAL IN = mono**, then
open the **External Mixer** page. The top row becomes `IN L · IN R · – · –`;
the lower row remains `DEL · REV · – · FX`, with shared sends.

**First test — NEEDS HARDWARE CONFIRMATION.** Feed a source into both inputs,
or test them one at a time. Change IN L and IN R independently and confirm the
separate levels. If no external source is present, record the item as untested.

**Two musical uses.**

- Balance two mono devices at the mixer before sharing the same delay/reverb
  sends.
- Use a quiet input on one side as a live texture, with its own level moves,
  while keeping the main input stable.

**Limit.** This is level separation, not independently pannable inputs; the
hardware input path has only two VCAs. In stereo input mode, the code path is
intended to remain identical to stock.

### Readable Values

**What it does.** Supported existing parameters display useful units instead
of only 0–127. It changes display text, not the underlying parameter ranges.

**Where it is.** Browse ordinary track, AMP, filter, mixer and delay/reverb
pages. Supported controls show units such as Hz, dB, ms, %, or INF.

| Supported groups | Examples |
| --- | --- |
| Filter / envelope | Digital filter frequency; BASE/WDTH; filter DEL/ATK/DEC/REL; SUS |
| Amp | ATK/DEC/REL and HOLD; analogue times are shown as estimates where marked `~` |
| Level / sends | LEV, VOL, IN, DEL and REV as dB values |
| Delay / reverb | HPF/LPF, return levels, pre-delay and shelving frequency/gain |

**First test.** Visit a filter frequency, an amp envelope, a track level and a
delay/reverb control; compare the unit label while turning the normal encoder.

**Two musical uses.**

- Match two sounds by time or frequency rather than trying to remember their
  unrelated raw values.
- Use dB send labels to make small, repeatable parallel-FX adjustments.

**Limit.** Parameters without a meaningful physical unit remain numeric;
examples include RESO, LFOs and some analogue filter controls. `~` means an
analogue time estimate, not a laboratory calibration.

## RC1 limitations and hardware checklist

Before describing an image as ready for a live set, check the exact generated
hash and then work through this focused list:

1. Cold boot, ordinary transport, track selection and stock SY TONE at ALGO 0.
2. FM4 Page-2 rendering/editing, a held-trig lock, save/reload and project
   reload. **NEEDS HARDWARE CONFIRMATION.**
3. FX3 audibility in each TYPE, return level, then compressor response and GR.
   On a MIDI track, check whether FX3 controls appear on SYN and record the
   generated hash. If testing the workaround, build and install a new CUSTOM
   image without FX3; do not treat it as a live setting or proven fix.
4. Beat Repeat keys 13 and 14 at more than one rate; release cleanly in time.
5. DV-F/DV-T, WAVE 4 and 96, then native WAVE 0.
6. Dual Mono with real external sources, and readable-value labels.
7. Reopen a saved sound, kit and pattern. Photograph/record exceptions and
   retain the SHA-256 and selected-mods JSON.

The builder validates format, dependencies and integrity. It does **not** prove
every MIDI, UI, project, FM algorithm or custom-combination workflow on every
instrument. Report the exact output hash, preset/selection, feature exercised,
steps, expected result and observed result. See [the RC1 hardware plan](../tools/max/modular_builder/HARDWARE_TEST.md)
and [feedback guidance](../tools/max/modular_builder/FEEDBACK.md).

## Recovery and publishing

If behaviour is unstable, stop, preserve evidence and use the official OS
recovery workflow described in [RECOVERY.md](../tools/max/modular_builder/RECOVERY.md).
The documented startup-menu recovery needs physical MIDI OUT to Syntakt MIDI
IN; USB MIDI is not used for that recovery route. The reset options named in
that document are not required for normal OS recovery and can erase data.

RC1 is publicly available at [Syntakt MAX Modular Builder RC1](https://github.com/karigardarsson/Synthack-OS/releases/tag/syntakt-max-modular-builder-rc1).
For a future update, carry forward links to this guide, the quick reference,
validation, attribution, recovery, hardware plan and feedback template. Do not
call a future image fully hardware-proven until its skipped/failed checklist
items have been reviewed.
