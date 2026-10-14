# Syntakt MAX (OS 1.41)

Build `out/synthack-max.syx` from the owner's verified stock file. This folder
contains no Elektron firmware or generated patch bytes. It does not transmit
the result to a device.

## Inputs and build

- Original SyntHack source base: `b536fa598cc2587d718905144e4c597947a5770c`
- Separate sibling Workbench checkout: `49a7a1e5ac1ac4c6869f01b94a820f2b625dada5`
- Stock: `firmware/Syntakt_OS1.41.syx`, SHA-256
  `8e2488f462c4a5656396a895f113bcd415e9900fa8709340dccf45d4cb9ed19e`
- Existing baseline: `out/synthack.syx`, SHA-256
  `b7f725d2cd2eace2f97a5f67a58ec5819dc398f2cd736a13e3f5bf01fa3dc8c0`
- Run `python3 tools/max/build_max.py` from the SyntHack checkout. Pass
  `--node /path/to/node` to select a runtime, or set `SYNTHACK_NODE`. Otherwise
  the builder finds `node` on PATH. Native Linux Node and Windows `node.exe`
  invoked from WSL are supported.

The builder regenerates all Workbench code and wave data from verified stock,
makes temporary stock-hash-guarded patches, and calls SyntHack's guarded build.
It compares the final decompressed sections with both the Workbench generator
and the pre-existing SyntHack build. No image stacking occurs.

## Included

| Source | Feature | Evidence before this build |
| --- | --- | --- |
| SyntHack | Boot splash | Project reports hardware-proven; source and emulator tests |
| SyntHack | Dual mono input | Project reports hardware-proven; source and emulator tests |
| SyntHack | Master compressor | Project reports hardware-proven; source and emulator tests |
| SyntHack | Readable parameter values | Project reports hardware-proven; source and emulator tests |
| SyntHack | Beat repeat | Project reports hardware-proven; source and emulator tests |
| SyntHack | Third send FX | Project reports hardware-proven; source and emulator tests |
| SyntHack | Mod area and virtual parameters | Required infrastructure; source and build tests |
| Workbench | 31 SY CHORD wave frames, WAVE 4..124, and screen pictures | Source project reports hardware checks for the patch method; this particular bank is build-only |
| Workbench | Deja Vu DV-F and DV-T, loop modes, SPH, names and icons | Source project reports hardware-proven implementation; source and end-to-end tests |

The 31-wave bank has six saw variants, six pulse variants, five harmonic
textures, six synthetic textures and eight chord textures. Exact names and
WAVE positions are in `out/synthack-max.json`. The shared WAVE 0 sample and
its screen picture remain stock. Morph values 1..3 follow the new WAVE 4.

## Expanded discovery and exclusions

| Project or candidate | Finding and specific reason for exclusion |
| --- | --- |
| SyntHack `mod-zero` | Example-only menu rename, no useful function |
| SyntHack roadmap items | PIN, arpeggiator, new machines and other listed ideas have no released OS 1.41 patch in the inspected main branch |
| [Syntaktful](https://github.com/romanjeff/syntaktful) | Two-ColdFire/FPGA research and compressor draft, with no released patch; its cross-chip compressor control path remains unresolved. The separate working SyntHack compressor is included |
| [Modded-Cycles](https://github.com/18nelli18/Modded-Cycles) | Its patches target Model:Cycles OS 1.13. It imports Syntakt engine data *out* into Model:Cycles; its arpeggiator, trig-hold, LFO and sequencer mods have Model:Cycles addresses, UI and storage, not Syntakt 1.41 patches |
| [elekloader](https://github.com/irpina/elekloader) | No Syntakt device backend or Syntakt module in inspected source |
| [Modwerk / Octamod](https://github.com/repeat98/modwerk) | Syntakt machine profile exists but format, rebuild, boot, core and mods are all marked open; no buildable Syntakt SDK module |
| [OctaBam](https://github.com/sambanks/octabam) | Octatrack OS 1.40C target, different patch addresses, audio architecture and UI/storage paths; no Syntakt patch |
| Hidden GATE/hold | No source patch, OS 1.41 address, control path or direct hardware proof found in the reviewed Syntakt projects or public search; unverified research lead |
| External MIDI apps | Syntakt control applications are host software, not firmware-resident patches |

The added repositories, main branches, release tags and public search did not
yield another implemented Syntakt OS 1.41 feature that meets the port criteria.
Techniques from other devices are useful references, but not byte-compatible
mods. No speculative port was placed into the final image.

## Compatibility and validation

- The 15 generated Workbench patch spans do not overlap SyntHack's patch spans.
  Deja Vu uses stock-blank section-3 runs at `0x402b9b00..0x402ba000` and
  `0x402ba000..0x402bb780`. SyntHack's appended mod image starts at
  `0x40348000`; the Workbench screen pictures are at section-3 offsets
  `0x31e7a8..0x3208dc`. Section 7 changes only the SY CHORD bank.
- The SyntHack mod area occupies 54,818 of 65,536 bytes, leaving 10,718.
  Deja Vu uses its own original-image cave and does not consume mod-area RAM.
- Syntaktful's current research disputes an analog master-VCA insert point,
  while SyntHack documents CV 35/36 as master controls and reports hardware
  testing of its compressor. This run did not resolve that independent
  architecture disagreement. A device test must check compression on both
  digital and analog tracks at the main outputs and over USB.
- The final section-3 decompression margin is 19,038 bytes versus a 4,096-byte
  minimum. Stock is 99,938; the prior SyntHack build is 18,084.
- SyntHack documents roughly 89% CPU use at rest on its device, about 2,000
  instructions per block for the compressor when on, and up to about 2,300
  for FX3. Wave table playback adds no new DSP routine; Deja Vu adds LFO
  evaluation work. The combined peak load and UI responsiveness need a
  device stress test, because no cycle budget was measured for this image.
- Final container reports Syntakt 1.41 and valid checksums. The guarded build
  verifies that protected and untouched sections decode identically to stock,
  changed bytes stay inside declared patches, and the appended image roundtrips.
- Baseline comparison confirms every byte outside Workbench's declared regions
  matches `out/synthack.syx` in decoded sections 3 and 7. The shared WAVE 0
  frame is bit-identical to stock.
- SyntHack full tests: 281 passed, 1 skipped with temporary pytest, Unicorn,
  NumPy and pyfiglet dependencies. Workbench DV tests, DV+wave end-to-end,
  chord-bank, DSP and graphics tests passed. Its wave end-to-end test passed
  its checks up to a missing optional local hardware-golden `.syx` file.
- This combined build has no hardware, listening, MIDI or timing measurement.
  The source projects' earlier hardware evidence does not prove this particular
  combined image or 31-wave bank on the device. CPU/runtime cost of the
  combination has not been measured.

## Final artifact

`out/synthack-max.syx` (Syntakt OS 1.41), SHA-256
`8cb28f5abd2b03779b0ad4452c84d6f745ddc137e075e297313899dfdf9e61a0`.

Remaining device validation requires a single controlled hardware session:
backup/restore readiness, boot, all retained SyntHack controls, DV modes on
both LFOs and multiple tracks, wave listening and pictures across WAVE values,
storage/reload, CPU/dropout stress, and rollback. This build has not been sent.

## Preparing a source checkout

Keep [Firmware Workbench](https://github.com/Bezronczek/syntakt-firmware-workbench)
in a sibling directory named `syntakt-firmware-workbench`, checked out at the
revision above. Supply your own official stock file; firmware is never included.
Python 3, Node with ES module support, Git, a C compiler and Make are required.
Build the pinned unpack/repack tool and the SyntHack comparison baseline first:

```sh
bash tools/unpack/setup_eft.sh
python3 tools/build/build.py --stock firmware/Syntakt_OS1.41.syx \
  mods/splash mods/dual-mono mods/modarea mods/vparams mods/master-comp \
  mods/readable-values mods/beat-repeat mods/fx3 -o out/synthack.syx
python3 tools/max/build_max.py
```

Generated output and temporary stock-derived patches stay in ignored directories.
The source-only publishing branches retain the upstream history. This tool does
not flash firmware. Enable the existing local commit guard with
`git config core.hooksPath tools/hooks`.
