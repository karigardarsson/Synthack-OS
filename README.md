# SyntHack OS

Unofficial, modular firmware mods for the **Elektron Syntakt** (OS 1.41).
Each mod is a small patch applied to the stock OS you download from elektron.se — no firmware is distributed here.

> **Not affiliated with Elektron.** Modified firmware can make your device unusable and may void your warranty.
> Learn the [recovery procedure](RECOVERY.md) before flashing. Use at your own risk.

## This fork: upstream MAX and SY FM4

**HARDWARE-PROVEN:** Kári's upstream-based MAX build for OS 1.41 booted and its musical features worked on a real Syntakt. It combines Angelo-politek's heap-based SyntHack mods with Déjà Vu LFO shapes and a 31-wave SY CHORD bank. The known-good local image has SHA-256 `7cb4bfd3da4af9c417ae812ec205036a85a430f3be62263cf58e6ae31df2c093`. See [build notes](tools/max/UPSTREAM_REBUILD.md). No firmware image is distributed here.

**IN DEVELOPMENT:** Rxuting's MIT-licensed SY FM4 port for OS 1.41. CPU1 and CPU2 components compile; sound storage and selected parameter-lock paths pass offline tests. The page-local UI adapter is partial: selected-sound getter/setter routing and complete page-2 interaction remain unresolved. There is no unified MAX + FM4 image, and FM4 has not been tested on hardware. See [FM4 status](tools/fm4/OS141_PORT_STATUS.md) and [Rxuting's license](tools/fm4/LICENSE).

Original SyntHack work is by [Angelo-politek](https://github.com/Angelo-politek/Synthack-OS). The Déjà Vu and SY CHORD source integration uses the separately pinned [Firmware Workbench](https://github.com/Bezronczek/syntakt-firmware-workbench); SY FM4 is by [Rxuting](https://github.com/Rxuting/sy-fm4). This branch contains source, tests and notes; building requires a separately obtained stock firmware file.

**Status:** `v0.8.1` — seven mods running on real hardware.

## Features

| Feature | Status | What it does |
|---|---|---|
| [Master compressor](mods/master-comp) | ✅ v0.5.0 | Bus compressor on the **analog master** (via the master VCAs). Digitakt-style curves. THR · ATK · REL · MUP · RAT + gain-reduction meter + ON/OFF switch on the FX track SYN page, values in dB / ms / ratio. Saved per pattern, or global with *SYN global*. |
| [Dual mono input](mods/dual-mono) | ✅ v0.5.0 | With EXTERNAL IN set to mono, **IN L** and **IN R** get independent levels on the External Mixer page. |
| [Boot splash](mods/splash) | ✅ v0.8.1 | "SyntHack" logo and version after the official intro. Boot time unchanged. |
| [Mod area](mods/modarea) | ✅ infra | 64 KB for mod code, stored compressed and unpacked at boot into a block reserved from the OS heap. |
| [Readable parameter values](mods/readable-values) | ✅ v0.5.0 | Hz, dB, ms and % instead of 0–127: filters, envelopes, levels, sends, delay and reverb, on every track and the FX track. Computed from the same data the DSP uses; analog parts measured on the device. |
| [Beat repeat](mods/beat-repeat) | ✅ v0.6.0 | Sequencer stutter on **all tracks** (analog too): hold retrig keys 13/14 on the FX track to loop the last 1/16 … 1 bar (rates RPT1/RPT2 on the TRIG page, saved with the kit) and resume in time. |
| [Third send FX](mods/fx3) | ✅ v0.8.0 | **SND3** on every track (AMP page 1, next to DEL and REV; PAN moves to page 2) into a **chorus, flanger, phaser or crusher**, with its own page (REVERB tab, page 2) saved with the kit, independent return level and a send into the delay. |
| PIN lock | ⬜ planned | Optional PIN at power-on, as a theft deterrent. Recovery via OS reflash stays possible. |
| Dual mono v2 | ⬜ planned | Separate IN L / IN R pages with their own FX sends. |
| New LFO shapes · 3rd LFO / mod matrix | ⬜ planned | |
| Arpeggiator · Euclidean circle UI | ⬜ planned | |
| Resampling to SP TWINSHOT · advanced sampler | ⬜ planned | |
| New machines: RISER / DOWNFILTER, SY SWARM+ | ⬜ planned | Requires custom audio-engine code (CPU #2). |
| Web builder | ⬜ planned | Pick mods in the browser, build your `.syx` locally. |

## Known issues

- **v0.8.0 and earlier: projects with samples (SP TWINSHOT) can crash at boot** ([#4](https://github.com/Angelo-politek/Synthack-OS/issues/4)). The mod code lived in RAM that the OS uses when it loads samples. Fixed in v0.8.1: the mod code now lives in a block of the OS heap. Recovery for the old versions: flash stock 1.41; projects and samples are not affected.

## Roadmap

```mermaid
flowchart LR
  A["Foundations ✅<br/>unpack/repack · emulator<br/>build tool · recovery"] --> B["First mods ✅<br/>splash · dual mono<br/>master compressor"]
  B --> C["UI & usability<br/>readable values ✅ · PIN lock<br/>dual mono v2"]
  C --> D["FX & performance<br/>beat repeat ✅ · third send FX ✅<br/>arp · euclidean UI · LFOs"]
  D --> E["Engine mods<br/>new machines · sampler<br/>resampling"]
  B -.-> W["Web builder"]
```

## How it works

- `tools/unpack` — unpack/repack the `.syx` (wraps [elektron-firmware-tool](https://github.com/mischa85/elektron-firmware-tool)).
- `mods/<name>/patch.json` — *where* to patch, a hash of the expected original bytes, and **our** new bytes.
- `tools/build/build.py` — stock OS + chosen mods → verified `.syx` (refuses wrong OS, overlaps, protected sections).
- `tools/emu` — ColdFire emulator (Unicorn + our EMAC model). Every mod is tested against the original code before flashing.

Technical findings: [docs/](docs). Writing your own mod: [docs/modding-guide.md](docs/modding-guide.md).

## Build your OS

Requires Python 3, WSL/Linux and your own `Syntakt_OS1.41.syx` (see [firmware/README.md](firmware/README.md)).

```sh
bash tools/unpack/setup_eft.sh                 # once (WSL/Linux)
git config core.hooksPath tools/hooks          # once: blocks firmware files from commits
python tools/build/build.py --stock firmware/Syntakt_OS1.41.syx \
    mods/splash mods/dual-mono mods/modarea mods/vparams mods/master-comp mods/readable-values mods/beat-repeat \
    mods/fx3 -o out/synthack.syx
```

Flash `out/synthack.syx` with Elektron Transfer (USB, *Drop* page). To go back, flash the stock OS the same way.

## Contributing

Issues and pull requests are welcome — see [CONTRIBUTING.md](CONTRIBUTING.md).
Please don't post mods or instructions on Elektronauts (forbidden there); use GitHub.

## License

MIT for everything in this repository ([LICENSE](LICENSE)). See [LEGAL.md](LEGAL.md).
