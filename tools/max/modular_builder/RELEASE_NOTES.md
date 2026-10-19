# Syntakt MAX Modular Builder — experimental RC1

One offline Windows x64 builder combines eight selectable groups: Master Compressor, FX3, Beat Repeat, Dual Mono Input, Readable Values, Déjà Vu LFO, 31-wave SY CHORD bank, and SY FM4. Presets cover MAX FULL + FM4, byte-identical Original MAX 1.0, and a corrected FM4-only heap-loader build. Custom selections automatically include required infrastructure.

The builder accepts only an unmodified official Syntakt OS 1.41 file supplied by the user. It verifies patch preimages, overlap, container checksums, decoded sections and boot decompression margin, saves an output hash and selected-mod report, and never transfers firmware to hardware. No proprietary firmware or generated `.syx` is in the release package.

Published MAX 1.0 remains unchanged. The full integrated preset reproduces the existing MAX+FM4 candidate byte for byte. FM4-only differs from the historical RC1 because that RC1 used a legacy loader address inconsistent with linked FM4 heap addresses. The modular FM4-only image needs its own hardware test. All 255 nonempty selections pass offline static gates, but custom runtime combinations are not individually hardware-proven.

This RC remains **local and unpublished** pending Kári's combined hardware acceptance test and packaged-GUI/clean-machine checks. See [README.md](README.md), [VALIDATION.md](VALIDATION.md), [HARDWARE_TEST.md](HARDWARE_TEST.md), [ATTRIBUTION.md](ATTRIBUTION.md), and [RECOVERY.md](RECOVERY.md).
