# Syntakt MAX 2: FM4 blocked; compatibility work preserved

Status on 2026-10-14: **incomplete**. No SY FM4 implementation was found in
the public source checked during this run. A separate, reproducible maintenance
experiment preserves the original MAX feature set and fixes parameter conflicts
in software tests. It is not recommended as a maintenance-only hardware update.

## Preservation and branch

Source is published on `syntakt-max2-compat`, based on the `syntakt-max`
integration and upstream `b536fa598cc2587d718905144e4c597947a5770c`. The original
`codex/syntakt-max2-fm4` branch is retained locally. The tracked `mods/` sources
remain unchanged; MAX publishing adds portable Node selection without changing
its firmware patches. Generated overlays
and firmware reside under ignored `out/`; earlier experiments remain there.

| Preserved input | SHA-256 |
| --- | --- |
| `firmware/Syntakt_OS1.41.syx` | `8e2488f462c4a5656396a895f113bcd415e9900fa8709340dccf45d4cb9ed19e` |
| `out/synthack.syx` | `b7f725d2cd2eace2f97a5f67a58ec5819dc398f2cd736a13e3f5bf01fa3dc8c0` |
| `out/synthack-max.syx` | `8cb28f5abd2b03779b0ad4452c84d6f745ddc137e075e297313899dfdf9e61a0` |

The original MAX source was checkpointed at
`out/checkpoints/max1-source-20261014.tar.gz`; all three source files were compared
with that archive before MAX2 development. Publishing subsequently changes only
Node runtime/path selection and documentation in the MAX tool. Original 31-wave and Deja Vu generation
continues to use Workbench revision `49a7a1e5ac1ac4c6869f01b94a820f2b625dada5`.

## FM4 discovery and bounded feasibility

[SyntHack issue #1](https://github.com/Angelo-politek/Synthack-OS/issues/1)
describes Rxuting's 1.40A implementation and reports hardware testing. It is a
coordination proposal, not an implementation package. The issue has no comments
with attached source. The public fork has only `main` and `os-1.42`; neither
contains FM4 source, a patch generator, an engine payload or algorithm tables.
Its releases and pull-request lists are empty.

The public [digiemu PR #33](https://github.com/irpina/digiemu/pull/33) contains
Syntakt 1.40A board, panel and second-CPU emulation support. The author's
`syntakt` emulator tree has no FM4 implementation files. The PR does not provide
a verified 1.41 full-system test environment; its stated FPGA/main-output model
is incomplete. No engine was reconstructed from the issue text.

The precise missing material is the CPU #2 prep/render source and algorithms,
CPU #1 page/descriptors and lock/save mapping, shared-RAM publisher/consumer,
loader/patch generator and ALGO-0 regression fixtures. Without those, the
reported 11 algorithms, page-2 controls, p-lock persistence and voice timing
cannot be ported or independently validated.

There is a plausible route once source is provided: section-7 patches and
appends are already accepted by the guarded builder; SY TONE's original engine
can remain the ALGO-0 path; the documented per-track logical indices and lock
lanes can be checked against stock 1.41; and CPU #1 has a free image gap between
the readable-values payload and beat repeat. The issue's proposed `+0xF000`
placement is now occupied by the namespace below. Exact FM4 memory and cycle
budgets remain unverified because the implementation is absent.

## Implemented maintenance

The [upstream compressor fix](https://github.com/Angelo-politek/Synthack-OS/issues/3)
correctly identifies unsafe stock aliases. Its replacement IDs 262..268 are
also native MIDI CC-selection descriptors in 1.41, so they were not adopted as
global mod IDs. The repair uses new private IDs instead:

| Mod | Previous IDs | Private IDs | Saved data |
| --- | --- | --- | --- |
| Compressor | 144,122,91,101,127,59,115 | 505..511 | Existing external-mixer words and ratio bits, unchanged |
| FX3 | 246,247,248,250,251,252,249,253 | 512..519 | Existing four packed kit words, unchanged |
| Beat repeat | 113,124 | 520,521 | Existing rate word, unchanged |

All three mods are recompiled from their existing sources in an isolated overlay.
The compressor processing, FX3 effects/send routing and beat-repeat behavior are
retained. The original native MIDI source and CC-select descriptors and their
objects are preserved, as are filter GAIN/RESO, MIXER reverb volume, LFO SLEW/SPH,
pan/balance and the former delay/reverb-routing aliases.

The private extension copies the native descriptor table at boot and appends 17
private descriptors. It relocates all 56 native table references, updates the
decoded descriptor bounds (including two CMPA UI cases), and directs the native
object getter to separate objects for IDs 505..521. It clones those objects with
the OS's actual std::function copier. Original descriptor rows and object storage
remain available; retained MAX changes for SND3, Deja Vu and dual mono remain.
Private descriptors have unique internal keys, no MIDI CC/NRPN binding and no
native modulation-destination flag. No stock logical ID is registered in vparams.

SND3 retains ID 72 and its original per-track storage slot; it is not a virtual
parameter alias. This relies on the existing SyntHack source analysis that its
native amp-delay word is unused by the DSP. Physical validation of all contexts
is still required. No FM4 parameter slots or communication fields are claimed.

## Memory, runtime and compatibility

- The namespace payload is 1,964 bytes at `0x4600F000`; the 64 KiB mod-area
  high-water mark is 63,404 bytes, leaving 2,132 bytes at its top plus internal
  gaps. FX3's delay line at `+0xE000` remains separate.
- The copied 522-row descriptor table uses 27,144 bytes at `0x46010000`.
  Seventeen objects use 1,428 bytes at `0x46017000`, with a readiness word at
  `0x46017FFC`. This reserves 32 KiB of the previously documented unused DDR
  region above the stock BSS. It has source/map and emulator evidence, not a
  hardware RAM-ownership trace.
- The namespace adds a boot copy and UI lookup work. CPU #2 code is unchanged
  from MAX, and its entire decoded section 7 remains bit-identical to MAX.
  Existing compressor/FX3 instruction-budget tests pass; combined real-time
  CPU/UI headroom is not measured.
- The guarded builder rejects overlaps and verifies declared differences,
  all untouched/protected sections, container checksums and decompression.
  The Workbench regions and section 7 are compared directly against MAX.
- Complete UI boot, physical MIDI traffic, project/sound reload, temporary-save
  behavior and listening tests have not been performed on this image.

## Validation and reproduction

The complete applicable overlay suite passed **288 tests, with 3 skips**.
The skips are the existing Windows-path-only wrapper test and two obsolete assertions
about rewriting native object-initializer sites; those two were replaced by
private-object copying, graphics, native-object preservation and lookup tests.
Nine new checks execute the complete maintenance image, its loader, every stock
object lookup, native group/internal getters, all descriptor-bound instructions,
native MIDI/alias dispatch, compressor/FX3 storage and retained Workbench bytes.
The original behavioral tests are copied into the ignored overlay with expected
mod IDs and RAM fixtures updated; original test files are unchanged.

The image is build/emulator-tested only. Its local validation artifact is
`out/max2-maintenance-work-r7/maintenance-validation.syx`, OS 1.41, SHA-256
`117317fff7cc87d12a2972fc2a55fc0cde25fcdd6ed0200f9389dc6db416d79c`.
It matched the r6 build byte for byte. Checksums pass, and the section-3 boot
decompression margin is 18,766 bytes against the 4,096-byte minimum. These
results are recorded in the accompanying `validation.json`. **It contains no FM4.**

Build with a new experiment directory name:

```sh
python3 tools/max2/build_maintenance.py max2-maintenance-replay
python3 tools/max2/prepare_tests.py max2-maintenance-replay
PYTHONPATH=out/max2-testdeps python3 -m pytest -q out/max2-maintenance-replay/tests
```

The builder refuses to overwrite an existing experiment directory. Its local
GCC 14/binutils packages are extracted under `out/max2-toolchain/root`, rather
than installed into Ubuntu. Python test dependencies are under
`out/max2-testdeps`. The same verified stock and Workbench revision are required. The builder accepts
commits descended from the original source base and verifies that its original
mods, build/unpack/emulator tools and behavioral tests still match that base. No transmission or flashing is performed.

## Twinshot exception: recorded, deferred

The related report is [upstream issue #4](https://github.com/Angelo-politek/Synthack-OS/issues/4).
Its photograph shows `EXCEPTION 0x0034`, firmware line `v1.41 MZ F46004000`,
and a first data row containing `4008D158 0000765A`. The displayed register/data
rows are not labelled here, so no program-counter interpretation is asserted.
The original photograph is preserved as
`out/max2-audit/twinshot-issue4-image.jpg`.

The report describes a transfer that failed to leave the transfer screen,
followed by a boot exception, stock recovery and a repeat exception after
reinstalling the same custom image. This makes the transfer a possible trigger;
it does not establish a root cause. The reported FUNC+NO FX3 temporary-save
behavior is also unresolved. This run did not reproduce either event and makes
no crash-fix claim.

## Recommended next hardware test

Obtain the FM4 implementation before planning another firmware update. Integrate
and validate it with this maintenance source, then test one combined candidate:
ALGO 0 against stock SY TONE; all eleven algorithms; page-2 controls, p-locks,
sound/pattern save and reload; eight-voice timing; native MIDI channel/bank/program,
controllers and CC selection; filter/mixer/LFO/pan aliases; compressor, FX3,
beat repeat, dual mono and Deja Vu together; and the SY CHORD bank/screens.
The maintenance-only image is not a recommendation to flash now. Twinshot crash
reproduction remains deferred.

## Toolchain prerequisites for a fresh checkout

First follow [MAX setup](../max/README.md#preparing-a-source-checkout) and build
the MAX comparison image. The maintenance experiment uses GCC 14 and binutils
for `m68k-linux-gnu`, extracted locally in `out/max2-toolchain/root`. The validated
Ubuntu amd64 package set was:

| Package | Version used |
| --- | --- |
| binutils-m68k-linux-gnu, libsframe3 | 2.46-3ubuntu2 |
| gcc-14-m68k-linux-gnu, gcc-14-m68k-linux-gnu-base, cpp-14-m68k-linux-gnu, libgcc-14-dev-m68k-cross | 14.3.0-14ubuntu1cross2 |
| libisl23 | 0.27-1build1 |
| libmpc3 | 1.3.1-3 |

Download those packages with `apt-get download` into
`out/max2-toolchain/packages` and extract each with
`dpkg-deb -x PACKAGE.deb out/max2-toolchain/root` from the repository root.
This does not install system packages. Availability depends on the Ubuntu
package repository; a different toolchain has not been qualified for byte-identical
output. Install pytest, Unicorn, NumPy and pyfiglet into an isolated environment
or `out/max2-testdeps` for the test command above. Toolchain packages, dependencies,
extracted firmware, generated overlays and validation images are excluded from Git.
