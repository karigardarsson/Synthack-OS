# Syntakt MAX Modular Builder — experimental RC1

Build a Syntakt OS 1.41 firmware image locally from your own unmodified official Elektron OS 1.41 `.syx`. The builder lets you choose eight community feature groups, manages their infrastructure automatically, verifies the result, and never connects to your instrument.

The project is actively developed. The published MAX 1.0 image is hardware-proven, and the complete MAX FULL + FM4 preset reproduces the previously hardware-tested integrated candidate byte for byte. The builder and all 255 nonempty feature selections have passed meaningful host-side structural checks. More custom combinations and workflows are still being explored, so feedback and test reports are welcome.

The builder targets Windows 10/11 x64. It was packaged and started on Windows 11 x64; preset builds and the source-level GUI flow passed native Windows tests. A manual visual test of the packaged file dialogs and an independent clean-machine test are still welcome. The executable is unsigned.

## Included feature groups

| Selection | What it adds |
| --- | --- |
| Master Compressor | Analog-master VCA compression, kit settings and gain-reduction display on FX SYN. |
| FX3 | Third send effect: chorus, flanger, phaser or crusher. |
| Beat Repeat | Hold FX-track retrig key 13 or 14 to loop steps and parameter locks; RPT1/RPT2 set loop length. |
| Dual Mono Input | Independent IN L and IN R levels in mono external-input mode. |
| Readable Values | Supported filter, envelope, send and FX values shown with useful units. |
| Déjà Vu LFO | DV-F and DV-T looping random shapes, five loop lengths and SPH behavior; seven stock shapes remain. |
| SY CHORD Wave Bank | 31 replacement SY CHORD waves at WAVE 4, 8, …, 124, with graphics; WAVE 0 remains stock. |
| SY FM4 | Four-operator FM on SY TONE ALGO 1–11, with a second SYN page; ALGO 0 is stock SY TONE. |

The GUI offers **MAX FULL + FM4**, **Original MAX 1.0**, **FM4 ONLY**, and **CUSTOM**. The support modules are selected automatically. Custom means any nonempty combination of the eight groups. All 255 nonempty selections are BUILD-VALIDATED for patch compatibility and placement. Their musical behavior has not been individually tested on hardware. Removing features can change a project's sound; in particular, the CHORD bank changes sounds that use replaced WAVE values.

## Build

1. Back up projects and sounds using your established Elektron workflow. Keep an unchanged official OS 1.41 file available for recovery. Obtain it from [Elektron support](https://www.elektron.se/support). The required stock SHA-256 is `8e2488f462c4a5656396a895f113bcd415e9900fa8709340dccf45d4cb9ed19e`.
2. Extract the complete ZIP and run `Syntakt-MAX-Modular-OS1.41-Builder.exe`.
3. Select the official stock `.syx`, verify the displayed input hash, then choose a preset or feature groups.
4. Choose **Build and Save Firmware**, then a new writable `.syx` filename. The builder refuses to overwrite an existing image or its selected-mod `.json` report.
5. Keep the success dialog's SHA-256 and the adjacent `.json` report with your private image.

## Preset evidence

| Preset | SHA-256 | Evidence |
| --- | --- | --- |
| Original MAX 1.0 | `7cb4bfd3da4af9c417ae812ec205036a85a430f3be62263cf58e6ae31df2c093` | HARDWARE-TESTED published MAX 1.0 image. |
| MAX FULL + FM4 | `3eaaf21ca0ed137eba14e321269d69383769da9210f818d0ad1db24356696d89` | BUILD-VALIDATED and byte-identical to the initially HARDWARE-TESTED integrated candidate. The complete combined acceptance session remains planned. |
| FM4 ONLY | `1f74cad579848132aad0b25bc9371b7dd2bbee72961cd98a3e351cd8695e860e` | BUILD-VALIDATED corrected heap-loader profile. This exact image is still EXPERIMENTAL on hardware. |

The earlier standalone FM4 RC1 fingerprint `8197f9c7…` is intentionally not a modular-builder target: its legacy loader placement conflicts with linked FM4 heap addresses. Initial standalone FM4 observations therefore do not automatically apply to the new FM4 ONLY hash.

The builder works offline with its bundled helper. It needs no separately installed Python, Git, GCC, or MSYS2 at runtime. For evidence details, recovery instructions, licensing, the hardware checklist, and feedback guidance, see [VALIDATION.md](VALIDATION.md), [RECOVERY.md](RECOVERY.md), [ATTRIBUTION.md](ATTRIBUTION.md), [HARDWARE_TEST.md](HARDWARE_TEST.md), and [FEEDBACK.md](FEEDBACK.md).
