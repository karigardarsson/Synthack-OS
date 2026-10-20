# Syntakt MAX Modular Builder - experimental RC2

Build a Syntakt OS 1.41 image locally from your own untouched official Elektron OS 1.41 `.syx`. This Windows builder selects eight community feature groups, manages dependencies, verifies the result, and never connects to your instrument.

RC2 restores native MIDI parameter ownership when optional MAX effects are active. The exact **MAX FULL + FM4** output passed Kari's combined manual hardware acceptance session. Other presets and custom selections remain experimental unless listed below.

## Included feature groups

| Selection | What it adds |
| --- | --- |
| Master Compressor | Analog-master VCA compression, kit settings and gain-reduction display on FX SYN. |
| FX3 | Third send effect: chorus, flanger, phaser or crusher. |
| Beat Repeat | Hold FX-track retrig key 13 or 14 to loop steps and locks; RPT1/RPT2 set loop length. |
| Dual Mono Input | Independent IN L and IN R levels in mono external-input mode. |
| Readable Values | Supported filter, envelope, send and FX values with useful units. |
| Deja Vu LFO | DV-F and DV-T looping random shapes, five loop lengths and SPH behavior; seven stock shapes remain. |
| SY CHORD Wave Bank | 31 replacement SY CHORD waves at WAVE 4, 8, ..., 124; WAVE 0 remains stock. |
| SY FM4 | Four-operator FM on SY TONE ALGO 1-11 with a second SYN page; ALGO 0 is stock SY TONE. |

The GUI offers **MAX FULL + FM4**, **Original MAX 1.0**, **FM4 ONLY**, and **CUSTOM**. All 255 nonempty selections are build-validated for patch compatibility and placement, but not individually hardware-tested.

## Build

1. Back up projects and sounds. Keep the official OS 1.41 file available for recovery. The required input SHA-256 is `8e2488f462c4a5656396a895f113bcd415e9900fa8709340dccf45d4cb9ed19e`.
2. Extract the ZIP and run `Syntakt-MAX-Modular-OS1.41-Builder.exe` on Windows 10/11 x64.
3. Select the official stock `.syx`, verify the input hash, select a preset or groups, and choose a new writable output filename.
4. Keep the success SHA-256 and adjacent selected-mod JSON report with your private image.

## Preset evidence

| Preset | SHA-256 | Evidence |
| --- | --- | --- |
| Original MAX 1.0 | `7b879fc3e3dba3d715ef2bbafc7e4ba74925b0547e5c15df4ac5827850bc1f36` | RC2 builder output, BUILD-VALIDATED. The published historical recovery image remains `7cb4bfd3da4af9c417ae812ec205036a85a430f3be62263cf58e6ae31df2c093`. |
| MAX FULL + FM4 | `83febfec562351fbd01817b9f97dd000b087eb361ea9579ed6ce5d2616090cdd` | HARDWARE-ACCEPTED for RC2 MIDI ownership, FX3, compressor UI, Beat Repeat UI, and FM4 page 2/audio. |
| FM4 ONLY | `1f74cad579848132aad0b25bc9371b7dd2bbee72961cd98a3e351cd8695e860e` | BUILD-VALIDATED heap-loader profile with limited hardware evidence. |

The builder works offline with its bundled helper. It needs no separate Python, Git, GCC, or MSYS2 at runtime. It is unsigned. It does not fix the reported compressor FUNC + NO transient.

See VALIDATION.md, RECOVERY.md, ATTRIBUTION.md, HARDWARE_TEST.md, and FEEDBACK.md.
