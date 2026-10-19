# RC1 validation and compatibility

## What has been checked

| Check | Result | Evidence level |
| --- | --- | --- |
| Official OS input gate | Only SHA-256 `8e2488f462c4a5656396a895f113bcd415e9900fa8709340dccf45d4cb9ed19e` is accepted; altered input is rejected. | HOST-TESTED |
| All nonempty feature selections | 255/255 pass stock preimage, patch overlap, dependency, CPU2 and heap-layout checks. Empty and unknown selections are rejected. | BUILD-VALIDATED |
| Original MAX 1.0 preset | SHA-256 `7cb4bfd3da4af9c417ae812ec205036a85a430f3be62263cf58e6ae31df2c093`; boot margin 19,052 bytes. | HARDWARE-TESTED image; BUILD-VALIDATED on Linux and Windows |
| MAX FULL + FM4 preset | SHA-256 `3eaaf21ca0ed137eba14e321269d69383769da9210f818d0ad1db24356696d89`; boot margin 18,930 bytes. | BUILD-VALIDATED on Linux and Windows; byte-identical to the initially HARDWARE-TESTED candidate |
| FM4 ONLY preset | SHA-256 `1f74cad579848132aad0b25bc9371b7dd2bbee72961cd98a3e351cd8695e860e`; boot margin 19,610 bytes. | BUILD-VALIDATED; this exact profile is EXPERIMENTAL on hardware |
| Custom CHORD-only example | SHA-256 `61b66e27d4237e48f3b155e8321204629477a4ae5546b06d7c2d8cdf591dbaa3`; boot margin 21,279 bytes. | BUILD-VALIDATED; hardware-untested as this exact custom image |
| Container integrity | Section checksums, decoded sections 3 and 7, protected stock sections, and the 4,096-byte minimum boot margin passed. | BUILD-VALIDATED |
| Windows package | EXE built on Windows 11 x64; archive excludes OS UCRT/APISet DLLs and contains the expected helper and manifest; process starts. | BUILD-VALIDATED |
| GUI callbacks | Input selection, cancellation, build progress/success, saved report, and invalid-input error flow passed with native Windows Tk; output matched the integrated hash. | HOST-TESTED |

The exact per-selection outcomes are in [COMPATIBILITY_MATRIX.csv](COMPATIBILITY_MATRIX.csv). This is substantial coverage of compatibility at build time, while still leaving real musical use of many custom combinations for community testing.

## What still benefits from testing

The planned combined acceptance session covers the exact MAX FULL + FM4 image. FM4 ONLY as generated here, custom combinations, a clean standard-user Windows environment, and the packaged EXE's visual file-dialog workflow remain useful next tests. Results, photos, and reports from those sessions will help focus the next release.

The source builders and native Windows core produced identical hashes for all three presets. They do not establish every stock UI path, project state, FM algorithm, MIDI behavior, or optional-mod combination on every instrument. See [HARDWARE_TEST.md](HARDWARE_TEST.md) and [FEEDBACK.md](FEEDBACK.md).

## FM4-only profile

The historical standalone FM4 RC1 is reproducible at SHA-256 `8197f9c73175d89a527635b57ad42aa7ce243a495f20e0c8548d9cbb81d81a8a`, but its manifest uses a legacy `0x46000000` loader while the linked FM4 UI data is in the `0x444E...` heap area. The modular builder uses the heap-reserved loader, as does the tested integrated build. This is why FM4 ONLY deliberately has a new hash and needs testing as its own profile.
