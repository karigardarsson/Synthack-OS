# Syntakt MAX Modular Builder OS 1.41 — Quick Reference

> **Experimental RC1.** This page is a fast control map, not a replacement for
> [the full user guide](MAX_USER_GUIDE.md). It applies only to an image built
> from the exact official Syntakt OS 1.41 input accepted by the builder.

## Choose a builder preset

| Preset | Selects | Evidence status |
| --- | --- | --- |
| **MAX FULL + FM4** | All eight feature groups | BUILD-VALIDATED; byte-identical to the initially hardware-tested integrated candidate. The complete combined acceptance session is still pending. |
| **Original MAX 1.0** | The seven MAX groups, without FM4 | The known hardware-tested MAX 1.0 image. |
| **FM4 ONLY** | SY FM4 plus its required support modules | BUILD-VALIDATED only. This new heap-loader profile is **experimental on hardware**. |
| **CUSTOM** | Any non-empty selection of the eight groups | All 255 possible non-empty selections are structurally/build validated; individual musical behaviour is not hardware-proven. |

The builder adds its support modules automatically. It does not connect to the
instrument and it refuses an altered or wrong stock OS input. Keep the output
SHA-256 and the adjacent selected-mods JSON report.

## Navigation and controls

| Feature | Where to find it | Controls | First safe check |
| --- | --- | --- | --- |
| **SY FM4** | Select **SY TONE**; set **ALGO 1–11**; open **SYN page 2** | ALGO, RAT3, LEV3, DEC3, RAT4, LEV4, DEC4, DET | On a disposable sound, select ALGO 1, play a short pattern and change one Page-2 value. **NEEDS HARDWARE CONFIRMATION.** |
| **Master Compressor** | **FX track → SYN** | THR, ATK, REL, MUP, RAT, GR (meter), COMP; DRIVE stays stock | Start with RAT off, then turn it on and lower THR at modest volume. |
| **FX3** | Send: audio track **AMP page 1, slot G (SND3)**. Effect: **FX track → REVERB**, press REVERB again for page 2 | TYPE; B–F are effect-specific; DEL is FX3-to-delay send; VOL is FX3 return | Raise SND3 a little, choose CHOR, raise VOL, then compare other TYPEs. **MIDI SYN/FX3 UI regression is under investigation in RC1.** |
| **Beat Repeat** | **FX track → TRIG page**, first two slots; while playing, hold **retrig key 13** or **14** | RPT1/RPT2: 1/16, 1/8, 3/16, 1/4, 1/2, 1BAR | Hold key 13 for one beat and release; playback should resume in time. |
| **Déjà Vu LFO** | A track's normal **LFO shape** selection | DV-F (free) or DV-T (note-restarted); MODE; SPH | Choose DV-F, MODE 2 and SPH 0; route LFO gently to pitch or filter. |
| **SY CHORD Wave Bank** | **SY CHORD → SYN → WAVE** | WAVE 4, 8, ... 124 are the added fixed bank; WAVE 0 remains stock | Try WAVE 4 and WAVE 96 on a temporary sound, then return to WAVE 0. |
| **Dual Mono Input** | Set **SETTINGS → AUDIO ROUTING → EXTERNAL IN = mono**, then open **External Mixer** | IN L and IN R become independent; sends remain shared | Feed L and R separately and change each input level. |
| **Readable Values** | Existing supported parameter pages | Display labels only: Hz, dB, ms, %, INF where appropriate | Browse filter, envelope, level and FX parameters; unsupported controls remain 0–127. |

## Do not skip these cautions

- Back up projects and sounds before changing OS firmware. Keep the original
  official OS 1.41 file and a known-good image available.
- The RC1 builder is offline; installation is a separate, manual operation
  using Elektron's supported process. Never interrupt power or transfer.
- Replaced SY CHORD WAVE values alter the timbre of older sounds that use them.
- **Do not call custom combinations “hardware-tested.”** Their evidence is
  structural/build validation only.
- If the instrument fails to boot or behaves unexpectedly, stop and follow
  [the recovery guidance](../tools/max/modular_builder/RECOVERY.md). Do not
  reset or erase projects as a first response.

For parameter ranges, save/p-lock behaviour, limitations and the RC1 hardware
checklist, see [MAX_USER_GUIDE.md](MAX_USER_GUIDE.md).
