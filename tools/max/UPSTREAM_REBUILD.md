# Upstream-based Syntakt MAX (OS 1.41)

Source: Angelo-politek/Synthack-OS 3e5e9e83caced4a29043ca2a8f3a71cde4b6460a, including heap fix c48f09372dba1a8beca949d97fbf6001d0f413ca. Workbench is pinned to 49a7a1e5ac1ac4c6869f01b94a820f2b625dada5. The official stock input must hash to 8e2488f462c4a5656396a895f113bcd415e9900fa8709340dccf45d4cb9ed19e.

This isolated branch leaves prior MAX/MAX2 work and images unchanged. Upstream reserves the first 64 KiB OS heap block at 0x444E38C0..0x444F38C0; executable mods begin at 0x444E38D0. The loader unpacks into that block and heap initialization reserves it before other allocations. No mod is linked at the unsafe 0x46000000 address.

## Build

Keep stock locally at firmware/Syntakt_OS1.41.syx and the pinned Workbench checkout in sibling ../syntakt-firmware-workbench. Set EFT_BIN to a compiled elektron-firmware-tool if required and provide Node with ES modules.

First build upstream-only with tools/build/build.py, selecting splash, dual-mono, modarea, vparams, master-comp, readable-values, beat-repeat and fx3, with output out/upstream-base.syx. Then run tools/max/build_upstream_max.py with --node and --output out/synthack-upstream-max.syx. The builder refuses overwrites, regenerates guarded Workbench patches from stock, and compares unchanged bytes against upstream-only.

Included: upstream splash, dual mono, compressor, readable values, Beat Repeat, FX3 and vparams; Workbench Deja Vu DV-F/DV-T and 31 SY CHORD waves with graphics. Shared WAVE 0 is unchanged.

Image out/synthack-upstream-max.syx SHA-256: 7cb4bfd3da4af9c417ae812ec205036a85a430f3be62263cf58e6ae31df2c093. A separate build was byte-identical. Container: OS 1.41, checksums valid, section-3 decompression margin 19,052 bytes (minimum 4,096). Upstream-only image hash: 38986eb3ffcffd9938b9980e3f78dcbc977f2d3e984c6a63b815deb10374e39b.

Tests: 295 upstream passed, 1 skipped; focused modarea/ID/FX3 111 passed. Workbench DV, chord-bank and picture tests passed; DV plus waves end-to-end passed. Generic Workbench wave end-to-end passed assertions until an optional local golden image work/syntakt141_sychord_saw30.syx was missing (ENOENT). This is missing fixture data, not hardware evidence.

## Hardware result and FM4 status

The image above booted on a real Syntakt, and Kári confirmed the musical features functioned. This is hardware evidence for the upstream-based MAX baseline only; preserve its exact SHA-256 image.

Rxuting/sy-fm4 a596b6393fc43582fd3ae0234ac04e198b779edb is MIT licensed; its license is copied to tools/fm4/LICENSE. FM4 CPU1 and CPU2 components compile, and offline tests cover sound storage and selected parameter-lock paths. The page-local UI adapter remains partial: selected-sound getter/setter routing and complete page-2 editing are unresolved. Native descriptor rows 36..43 are occupied, and global object-table expansion is unsafe. No unified MAX + FM4 image has been generated or tested on hardware. See [FM4 port status](../fm4/OS141_PORT_STATUS.md) for the current technical blockers.
