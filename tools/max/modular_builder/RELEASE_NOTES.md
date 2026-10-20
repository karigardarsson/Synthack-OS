# Syntakt MAX Modular Builder - RC2

RC2 is an experimental Windows x64 offline builder for Syntakt OS 1.41. It provides eight selectable feature groups, automatic dependencies, presets, and a checked build report beside each private firmware file. It never connects to a Syntakt.

## RC2 maintenance update

RC2 corrects three MIDI parameter-ownership collisions:

- FX3 no longer replaces MIDI SYN controls.
- Master Compressor no longer replaces MIDI AMP SEL1-SEL7.
- Beat Repeat no longer replaces MIDI AMP SEL8.

The exact **MAX FULL + FM4** image was manually accepted on Kari's Syntakt: MIDI AMP SEL1-SEL8 editing, MIDI SYN, MIDI-to-FX-to-MIDI switching, FX SYN compressor controls, FX TRIG Beat Repeat controls, FX3 audio, and SY FM4 page 2/audio passed. This is hardware evidence for that image only, not every builder selection.

The reported compressor volume transient during FUNC + NO remains under investigation; RC2 does not claim to correct it.

## Included groups and use

Master Compressor, FX3, Beat Repeat, Dual Mono Input, Readable Values, Deja Vu LFO, the 31-wave SY CHORD bank, and SY FM4 are independently selectable. MAX FULL + FM4, Original MAX 1.0, FM4 ONLY, and CUSTOM are available. The builder adds support modules only when required.

Supply your own untouched official OS 1.41 file, SHA-256 `8e2488f462c4a5656396a895f113bcd415e9900fa8709340dccf45d4cb9ed19e`. This ZIP includes no Elektron firmware or generated `.syx` image. It validates all 255 nonempty feature selections at build time; this does not make all selections hardware-tested.

Back up projects and sounds, retain the official OS for recovery, and read README.md and RECOVERY.md. Existing sounds that use replaced SY CHORD waves can change timbre.

Credits: Rxuting (SY FM4), Angelo-politek and SyntHack contributors (infrastructure and MAX components), Bezronczek (Deja Vu and SY CHORD Workbench implementations), and Kari Gardarsson (OS 1.41 integration, validation, builder). Full notices are in ATTRIBUTION.md and `licenses/`.
