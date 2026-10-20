# RC2 validation and compatibility

| Check | Result | Evidence |
| --- | --- | --- |
| Official OS input gate | Only stock SHA-256 `8e2488f462c4a5656396a895f113bcd415e9900fa8709340dccf45d4cb9ed19e` is accepted; altered input is rejected. | HOST-TESTED |
| All nonempty selections | 255/255 pass preimage, overlap, dependency, CPU2 and heap-layout checks. | BUILD-VALIDATED |
| Original MAX 1.0 RC2 | `7b879fc3e3dba3d715ef2bbafc7e4ba74925b0547e5c15df4ac5827850bc1f36`. | BUILD-VALIDATED |
| Historical MAX recovery image | `7cb4bfd3da4af9c417ae812ec205036a85a430f3be62263cf58e6ae31df2c093`. | HARDWARE-TESTED |
| MAX FULL + FM4 | `83febfec562351fbd01817b9f97dd000b087eb361ea9579ed6ce5d2616090cdd`; 157 patches, 56,598-byte modarea, 18,514-byte margin. | HARDWARE-ACCEPTED / BUILD-VALIDATED |
| FM4 ONLY | `1f74cad579848132aad0b25bc9371b7dd2bbee72961cd98a3e351cd8695e860e`; 19,610-byte margin. | BUILD-VALIDATED; limited hardware evidence |
| Container checks | Checksums, decoded sections 3 and 7, protected sections, and 4,096-byte minimum margin. | BUILD-VALIDATED |

Kari reported RC2 acceptance for MAX FULL + FM4: MIDI AMP SEL1-SEL8 editing, MIDI SYN, MIDI-to-FX-to-MIDI switching, FX SYN compressor, FX TRIG Beat Repeat, FX3 audio, and FM4 page 2/audio. This does not prove every machine, project state, algorithm, or custom combination.

The compressor FUNC + NO volume transient remains open. FM4 ONLY, custom combinations, long sessions, and clean standard-user Windows environments remain useful community tests.
