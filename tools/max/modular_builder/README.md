# Syntakt MAX Modular Builder — experimental RC1

Build a Syntakt OS 1.41 firmware image locally from **your own unmodified official Elektron OS 1.41 `.syx`**. This package contains no Elektron firmware or ready-to-flash image. It does not connect to or update the instrument.

The builder targets Windows 10/11 x64. It was packaged and started on Windows 11 x64; the three preset builds and a custom build passed native Windows core tests. The packaged GUI's file-dialog workflow and a clean Windows machine have **not** yet been independently tested. The executable is unsigned.

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

The GUI offers **MAX FULL + FM4**, **Original MAX 1.0**, **FM4 ONLY**, and **CUSTOM**. The support modules are selected automatically. Custom means any nonempty combination of the eight groups. Static patch and placement checks passed for all 255 nonempty combinations; their musical behavior has not been individually tested on hardware. Do not assume projects retain identical sound when a feature is removed. In particular, the CHORD bank changes existing sounds that use replaced WAVE values.

## Build

1. Back up projects and sounds using your established Elektron workflow. Keep an unchanged official OS 1.41 file for recovery. Obtain it from [Elektron support](https://www.elektron.se/support). The required stock SHA-256 is `8e2488f462c4a5656396a895f113bcd415e9900fa8709340dccf45d4cb9ed19e`.
2. Extract the **entire ZIP**. Run `Syntakt-MAX-Modular-OS1.41-Builder.exe`.
3. Select the official stock `.syx` and verify the displayed input hash. Select a preset or feature groups.
4. Choose **Build and Save Firmware**, then a **new**, writable `.syx` filename. The builder refuses to overwrite an existing image or its selected-mod `.json` report.
5. Wait for the success dialog. It displays the output SHA-256 and saves a `.json` report alongside the `.syx`. Keep that report with your private image.

The three pinned preset output hashes are:

| Preset | SHA-256 | Evidence |
| --- | --- | --- |
| Original MAX 1.0 | `7cb4bfd3da4af9c417ae812ec205036a85a430f3be62263cf58e6ae31df2c093` | Byte-identical to published hardware-proven MAX 1.0. |
| MAX FULL + FM4 | `3eaaf21ca0ed137eba14e321269d69383769da9210f818d0ad1db24356696d89` | Byte-identical to the previously tested integrated candidate; a complete combined acceptance test remains outstanding. |
| FM4 ONLY | `1f74cad579848132aad0b25bc9371b7dd2bbee72961cd98a3e351cd8695e860e` | Corrected heap-loader profile; this exact image is hardware-untested. |

The older standalone FM4 RC1 fingerprint `8197f9c7…` is intentionally **not** a modular-builder target. Its legacy loader placement conflicts with the linked FM4 heap addresses. The separate FM4 repository records initial standalone hardware observations, but those observations must not be transferred to this newly generated FM4-only profile.

The program builds offline with its bundled helper. It needs no separately installed Python, Git, GCC or MSYS2 at runtime. This was inspected and tested on the development Windows system, not on a clean standard-user machine. If any check fails, do not use the output. Consult [VALIDATION.md](VALIDATION.md) and [RECOVERY.md](RECOVERY.md).

## Install and recovery

The builder never sends firmware. Only Kári's planned combined hardware test is currently proposed; this RC is **not approved for public release**. Before any manual installation, review [RECOVERY.md](RECOVERY.md), keep a verified official stock image and backups, and follow Elektron's official OS update instructions. Never use device reset options as an OS-update substitute.

This is unofficial experimental firmware, unaffiliated with Elektron. See [ATTRIBUTION.md](ATTRIBUTION.md), the complete [licenses](licenses/), [RELEASE_NOTES.md](RELEASE_NOTES.md), and the [single-session hardware checklist](HARDWARE_TEST.md).
