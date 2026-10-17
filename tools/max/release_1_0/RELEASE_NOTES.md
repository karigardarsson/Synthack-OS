# Syntakt MAX 1.0 — release notes (local draft)

Community mod bundle for **Elektron Syntakt OS 1.41**, with a standalone **Windows 11 x64** builder. The user supplies official stock firmware; the release contains no firmware image. This draft has not been pushed or released.

## Included

| Included feature | What it does | Origin |
| --- | --- | --- |
| Master compressor | Analog-master VCA compression with threshold, attack, release, makeup, ratio, gain-reduction meter and comparison switch on FX SYN. Settings stored with the kit; no dry/wet control. | Angelo-politek / SyntHack |
| Third send FX | SND3 sends audio tracks to chorus, flanger, phaser or crusher; FX REVERB page 2 controls the effect, return and delay send. Kit storage and track send p-locks. | Angelo-politek / SyntHack |
| Beat Repeat | Hold FX-track retrig key 13 or 14 to loop sequencer steps and p-locks on all tracks, including analog tracks; release resumes in time. RPT1/RPT2 select 1/16, 1/8, 3/16, 1/4, 1/2 or one bar. | Angelo-politek / SyntHack |
| Dual mono input | In mono external-input mode, IN L and IN R have independent levels on the External Mixer page. | Angelo-politek / SyntHack |
| Readable values | Shows supported filter, envelope, level, send, delay and reverb values in units such as Hz, dB, ms and percent. | Angelo-politek / SyntHack |
| Déjà Vu LFO | Adds DV-F (free-running) and DV-T (restarts on notes). MODE selects 2/4/8/16/32 steps; SPH moves from new random values (0), through repeating (64), to reordering (127). Retains the seven native shapes. | Bezronczek / Firmware Workbench |
| 31 SY CHORD waves and graphics | Fixed bank of saw, pulse, harmonic, synthetic and chord textures at WAVE 4, 8, …, 124, with matching screen pictures and interpolation between slots. Shared WAVE 0 stays unchanged. | Workbench implementation; MAX bank selection/formulas by Kári's integration work; chord synthesis by Workbench |
| SyntHack splash | Retains the upstream SyntHack v0.8.1 startup graphic. MAX 1.0 is the bundle version, not a changed Elektron OS version. | Angelo-politek / SyntHack |
| Heap modarea and vparams | Reserves 64 KiB of the OS heap for mod code and provides shared kit-parameter dispatch. Infrastructure supporting the musical mods. | Angelo-politek / SyntHack |

## Fixed SY CHORD bank

| WAVE | Name |
| --- | --- |
| 4 | Saw |
| 8 | Soft saw |
| 12 | Bright saw |
| 16 | Odd saw |
| 20 | Folded saw |
| 24 | Reverse saw |
| 28 | Square |
| 32 | Pulse 25 |
| 36 | Pulse 12 |
| 40 | Pulse 38 |
| 44 | Soft pulse |
| 48 | Double pulse |
| 52 | Organ 1-2-4 |
| 56 | Drawbar |
| 60 | Hollow odd |
| 64 | Fifth stack |
| 68 | Octave stack |
| 72 | FM bright |
| 76 | FM glass |
| 80 | FM wood |
| 84 | Wavefold |
| 88 | Formant |
| 92 | Sync edge |
| 96 | Major chord |
| 100 | Minor chord |
| 104 | Sus4 chord |
| 108 | Diminished chord |
| 112 | Major 7 chord |
| 116 | Dominant 7 chord |
| 120 | Minor 7 chord |
| 124 | Major 9 chord |

Bright waves may alias at high pitches. The eight chord waves use Workbench's default harmonic construction; the root is four octaves above the played note, so lower TUNE as appropriate. Existing sounds/patterns using replaced or neighboring WAVE values will sound different. DV sounds will not retain their DV behavior on stock firmware.

## Evidence and limits

- Kári reports this exact MAX firmware booted and its musical features functioned on one real Syntakt. This is not an exhaustive regression of every machine, project, MIDI/CC path, Overbridge configuration or performance/load combination.
- Kári manually tested the Windows GUI: selected official OS 1.41, built successfully, saw the success dialog and generated MAX firmware. The builder only releases output matching the golden hash below. No separate hash of Kári's manually generated file was supplied.
- Offline evidence already recorded in the build notes: 295 upstream tests passed / 1 skipped; 111 focused modarea/ID/FX3 tests passed; Workbench DV/bank/picture tests passed. One generic Workbench end-to-end comparison lacked an optional golden fixture. These are software results, not additional hardware tests.
- RC validation: 5 focused builder tests passed; native Windows core matched the golden output; invalid input was rejected without output; executable launch was verified. Clean-machine/non-admin testing and GUI cancel/unwritable-destination cases remain untested.
- OS 1.41 with the exact input fingerprint only. No support claim for other Elektron devices, OS versions, Windows versions or ARM systems. FM4 is excluded.
- Retained upstream limits: compressor is analog-master VCA processing without dry/wet; toggling external-input global state also copies its stored settings. FX3 runs at 24 kHz. Upstream parameter-ID ownership is retained; native MIDI behavior is not claimed comprehensively validated by this release.

## Files and fingerprints

Windows executable: `Syntakt-MAX-1.0-Builder.exe`, 11,626,089 bytes, unsigned.

Executable SHA-256: `cc0c042b69b46e5ffa06cbbe06b9f69ac0d5a6a9267e31f6d6495bc029ab7c3b`

Required official OS 1.41 SHA-256: `8e2488f462c4a5656396a895f113bcd415e9900fa8709340dccf45d4cb9ed19e`

Verified MAX output SHA-256: `7cb4bfd3da4af9c417ae812ec205036a85a430f3be62263cf58e6ae31df2c093`

The source pipeline and native Windows builder produce the same output. Container checksums passed; section-3 decompression margin is 19,052 bytes. The hardware-proven image and executable remain byte-identical. The ZIP adds documentation and notices around that executable.

Read `INSTALL.md`, `RECOVERY.md`, `ATTRIBUTION.md` and the license files before use. `REVIEW.md` records the remaining public-release gate. Source: [Kári's fork](https://github.com/karigardarsson/Synthack-OS). Original mods: [Angelo-politek](https://github.com/Angelo-politek/Synthack-OS) and [Bezronczek](https://github.com/Bezronczek/syntakt-firmware-workbench).
