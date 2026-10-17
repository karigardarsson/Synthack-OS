# Syntakt MAX 1.0

Unofficial community mod bundle for **Elektron Syntakt OS 1.41**, built locally from your own official OS file with a standalone Windows builder. No Elektron firmware is distributed. Not affiliated with or supported by Elektron.

**Hardware evidence:** Kári's upstream-based MAX image booted and its musical features functioned on one Syntakt. Known-good output SHA-256: `7cb4bfd3da4af9c417ae812ec205036a85a430f3be62263cf58e6ae31df2c093`. Kári also manually completed the Windows GUI build workflow. Other hardware/software configurations and exhaustive regressions are not certified.

**Release preparation:** local draft only; no release has been published by this run. See [release notes](tools/max/release_1_0/RELEASE_NOTES.md), [installation](tools/max/release_1_0/INSTALL.md), [attribution](tools/max/release_1_0/ATTRIBUTION.md), and [open review item](tools/max/release_1_0/REVIEW.md). Windows 11 x64 is the tested builder platform. Read [recovery guidance](RECOVERY.md) before installing modified firmware.

## Included in MAX 1.0

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

The exact 31-wave list is in the release notes. MAX is a fixed build, not the Workbench wave editor. Existing sounds using replaced waves will change timbre. **SY FM4 is not included**: it remains separate development, with unresolved complete page-2 editing and no unified hardware-tested build.

## Credits and source

Original SyntHack mods and heap-based infrastructure: [Angelo-politek and contributors](https://github.com/Angelo-politek/Synthack-OS). Déjà Vu and SY CHORD implementation: [Bezronczek / Firmware Workbench](https://github.com/Bezronczek/syntakt-firmware-workbench). MAX integration, fixed bank recipes and Windows builder: Kári Garðarsson's fork, developed with Codex assistance. Container tooling: [Marcel Bierling / elektron-firmware-tool](https://github.com/mischa85/elektron-firmware-tool).

Pinned source revisions and license requirements: [attribution map](tools/max/release_1_0/ATTRIBUTION.md). Source build: [upstream MAX build notes](tools/max/UPSTREAM_REBUILD.md); Windows packaging: [builder README](tools/max/windows_builder/README.md). Mod details remain under [mods/](mods); reverse-engineering and emulator notes under [docs/](docs). FM4 research is documented separately in [tools/fm4/](tools/fm4/OS141_PORT_STATUS.md).

Repository community code is MIT ([LICENSE](LICENSE)); packaged third-party runtimes have their own terms. These licenses do not grant rights over Elektron firmware. See [LEGAL.md](LEGAL.md). Do not commit stock/generated firmware, extracted OS sections, device projects or samples.
