# RC1 validation and compatibility

## Evidence

| Check | Result | Evidence level |
| --- | --- | --- |
| Official OS input gate | Only SHA-256 `8e2488f462c4a5656396a895f113bcd415e9900fa8709340dccf45d4cb9ed19e` accepted; altered input rejected. | Native Windows core test |
| All nonempty feature selections | 255/255 pass stock preimage, patch overlap, dependency, CPU2 and heap-layout checks. Empty/unknown selections rejected. | Host static test |
| Original MAX 1.0 preset | SHA-256 `7cb4bfd3da4af9c417ae812ec205036a85a430f3be62263cf58e6ae31df2c093`; boot margin 19,052 bytes. | Linux and Windows build; published image hardware-proven |
| MAX FULL + FM4 preset | SHA-256 `3eaaf21ca0ed137eba14e321269d69383769da9210f818d0ad1db24356696d89`; boot margin 18,930 bytes. | Linux and Windows build; byte-identical to user-reported initial hardware-tested candidate |
| FM4 ONLY preset | SHA-256 `1f74cad579848132aad0b25bc9371b7dd2bbee72961cd98a3e351cd8695e860e`; boot margin 19,610 bytes. | Linux and Windows build; exact profile hardware-untested |
| Custom CHORD-only example | SHA-256 `61b66e27d4237e48f3b155e8321204629477a4ae5546b06d7c2d8cdf591dbaa3`; boot margin 21,279 bytes. | Linux build; hardware-untested as this exact custom image |
| Container checks | Section checksums, decoded sections 3 and 7 and the minimum 4,096-byte boot margin verified for the built profiles. | Native package checks |
| Windows package | EXE built on Windows 11 x64; archive excludes OS UCRT/APISet DLLs and contains the helper and manifest; process starts. | Package inspection and startup smoke |

All 255 selections are **offline-compatible**, not hardware-validated configurations. The exact per-selection results are in [COMPATIBILITY_MATRIX.csv](COMPATIBILITY_MATRIX.csv). The only integrated profile with user-reported FM4 hardware operation is the exact MAX FULL + FM4 image. Custom combinations, FM4 ONLY as generated here, clean-machine runtime and full packaged-GUI interaction remain untested. The planned one-session combined test is in [HARDWARE_TEST.md](HARDWARE_TEST.md).

The source builders and native Windows builder core produced identical hashes for all three presets. No claim is made that the full stock UI, all project states, all FM algorithms, MIDI, or every optional-mod combination have been exercised on hardware. The test matrix verifies patch compatibility and container safety; it cannot prove runtime interactions.

## Important FM4-only distinction

The historical standalone FM4 RC1 is reproducible at SHA-256 `8197f9c73175d89a527635b57ad42aa7ce243a495f20e0c8548d9cbb81d81a8a`, but its manifest calls the legacy `0x46000000` loader while the linked FM4 UI data addresses are in the `0x444E...` heap area. The modular builder uses the heap-reserved loader, as does the tested integrated build. Thus FM4 ONLY is deliberately **not byte-identical** to RC1. Hardware testing must identify the exact image hash, not merely the feature name.

## Remaining gates before public distribution

- Kári's planned combined hardware acceptance session for the MAX FULL + FM4 image.
- Manual packaged-GUI test of input selection, build, cancellation and success/error dialogs. The Windows Computer Use launch attempt timed out; core output and process startup passed.
- Independent clean Windows 10/11 standard-user test, including an unwritable destination and Unicode filename.
- Review of any hardware failures or project compatibility differences discovered during that session.
