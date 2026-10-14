# Syntakt MAX

A hobby/community fork of [SyntHack OS](https://github.com/Angelo-politek/Synthack-OS)
for Elektron Syntakt **OS 1.41**, combining its mods with
[Firmware Workbench](https://github.com/Bezronczek/syntakt-firmware-workbench).
This repository publishes source, build tools and technical notes. Supply your
own official firmware locally; no firmware images or extracted firmware are distributed.

## Implemented

- Master compressor, third send FX (chorus/flanger/phaser/crusher), beat repeat,
  dual mono input, readable parameter values and the SyntHack splash.
- Deja Vu **DV-F / DV-T** LFO shapes, loop controls, labels and icons.
- **31 SY CHORD waves** with screen graphics: saw, pulse, harmonic, synthetic
  and chord textures. Shared WAVE 0 remains stock.
- Guarded builds from verified stock, patch overlap checks, protected-section
  checks, firmware integrity validation and emulator tests.

## Evidence and current research

**Hardware:** upstream authors report device testing of the existing SyntHack
mods and Workbench patch methods. Our combined MAX image, this particular wave
bank and MAX2 compatibility changes have **not been hardware-qualified**.
No hardware validation is inferred from successful builds or emulator tests.

**Software:** MAX reproduced the same image hash; 281 SyntHack tests passed
(1 skipped), plus Workbench Deja Vu, wave, DSP and graphics checks. Full evidence,
memory findings and limitations are in [the MAX report](tools/max/README.md).

**Research:** SY FM4 is blocked on missing implementation source; the public
[proposal](https://github.com/Angelo-politek/Synthack-OS/issues/1) describes a
hardware-tested OS 1.40A engine but does not supply it. Twinshot exception
investigation is deferred; its failed transfer is a possible trigger, not a
confirmed cause. MAX parameter-ID compatibility work is on the separate
[`syntakt-max2-compat` branch](https://github.com/karigardarsson/Synthack-OS/tree/syntakt-max2-compat).

## Branches and building

- **`syntakt-max`**: combined MAX source and build report.
- **`syntakt-max2-compat`**: MAX plus experimental MIDI/FX3, compressor and
  beat-repeat parameter isolation. It contains no FM4 and is not a
  maintenance-only flash recommendation.
- **`main`**: retained upstream baseline.

See [MAX build instructions](tools/max/README.md#preparing-a-source-checkout).
Generated files stay local under ignored `out/`. Enable the existing commit
guard with `git config core.hooksPath tools/hooks`.

Upstream architecture notes: [docs/](docs/). Contribution and firmware handling:
[CONTRIBUTING.md](CONTRIBUTING.md), [LEGAL.md](LEGAL.md) and [RECOVERY.md](RECOVERY.md).
Original source and this fork use the [MIT license](LICENSE).
