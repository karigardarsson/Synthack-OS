Syntakt MAX 1.0 combines community mods for **Elektron Syntakt OS 1.41**, with a standalone Windows builder that creates firmware locally from **your own official OS 1.41 file**.

**Experimental, unofficial firmware. Not affiliated with, endorsed by or supported by Elektron. Modified firmware may fail; back up your data and understand DIN recovery before installation.**

### Community credits

Original SyntHack mods and heap-based infrastructure: **[Angelo-politek / SyntHack](https://github.com/Angelo-politek/Synthack-OS)**. Déjà Vu LFO and SY CHORD wave/graphics implementation: **[Bezronczek / Syntakt Firmware Workbench](https://github.com/Bezronczek/syntakt-firmware-workbench)**. MAX integration, fixed wave-bank selection/recipes and Windows builder: Kári Garðarsson's fork, with Codex assistance. The container helper is by [Marcel Bierling / mischa85](https://github.com/mischa85/elektron-firmware-tool).

### Seven feature groups

1. **Master compressor:** analog-master compression with FX SYN controls and gain-reduction display.
2. **Third send FX:** chorus, flanger, phaser or crusher, with track sends, return level and delay send.
3. **Beat Repeat:** hold FX-track retrig keys 13/14 to repeat sequencer steps on digital and analog tracks; release resumes in time.
4. **Dual mono input:** independent external L/R input levels in mono mode.
5. **Readable values:** supported parameters shown in Hz, dB, ms and percent.
6. **Déjà Vu LFO:** DV-F and DV-T random-step loops, five loop lengths and SPH loop behavior; native shapes retained.
7. **31-wave SY CHORD bank:** saw, pulse, harmonic, synthetic and chord textures with matching graphics. Shared WAVE 0 is unchanged.

The upstream SyntHack splash and heap modarea/vparams infrastructure are retained. **SY FM4 is not included.**

### Use

1. Download and extract **Syntakt-MAX-1.0-Windows-x64.zip**. Keep its notices and licenses with the EXE.
2. Obtain official **Syntakt OS 1.41** from [Elektron support](https://www.elektron.se/support). The builder rejects other versions or modified inputs.
3. Run the builder on Windows, select that stock `.syx`, click **Build and Save MAX 1.0**, and choose a new output filename. Wait for the success dialog.
4. Verify the generated file's SHA-256 below. Read the [FAQ](https://github.com/karigardarsson/Synthack-OS/blob/syntakt-max-release/tools/max/release_1_0/FAQ.md), [installation instructions](https://github.com/karigardarsson/Synthack-OS/blob/syntakt-max-v1.0/tools/max/release_1_0/INSTALL.md) and [recovery guidance](https://github.com/karigardarsson/Synthack-OS/blob/syntakt-max-v1.0/RECOVERY.md) before separately using Elektron Transfer. The builder performs no device transfer.

The release contains **no Elektron firmware, generated `.syx`, extracted OS sections, projects or samples**. No separate Python, WSL, compiler or Git installation is required to run the builder.

### Validation and limits

Kári reports the exact MAX output booted and its musical features worked on one Syntakt. Kári also reports successful complete GUI builds with the **latest EXE fingerprint below**. Native Windows core tests matched the golden output; invalid input was rejected; five focused builder tests passed. The UCRT/APISet redistribution gate is resolved, with runtime provenance and notices included.

Windows 11 x64 is tested. Packaging targets Windows 10/11 x64; Windows 10, an independent clean/non-admin machine, cancelled/unwritable-destination GUI cases and exhaustive MIDI/Overbridge/project compatibility remain untested. Bright CHORD waves may alias at high pitches; replaced WAVE values change existing sounds' timbre. DV shapes do not retain their behavior on stock firmware.

The unchanged ZIP contains the validation snapshot from before the latest manual GUI test. This release description records the newer result; the EXE and ZIP are byte-identical to the verified candidate.

### SHA-256

```text
ZIP:       92d83f258a26d80cbedcaa1ddb5763f61ecbda1df1a06da4e061fe4a12db675d
EXE:       ae0c4eb65beb79baaf0634fb9107bfa2a95abd35274e6c35f4228a621e9e2f92
Stock OS:  8e2488f462c4a5656396a895f113bcd415e9900fa8709340dccf45d4cb9ed19e
MAX output:7cb4bfd3da4af9c417ae812ec205036a85a430f3be62263cf58e6ae31df2c093
```

The ZIP is 10,349,823 bytes; the unsigned EXE is 10,570,255 bytes. MAX 1.0 is the community bundle version; the base Elektron OS is 1.41. See the [full feature list](https://github.com/karigardarsson/Synthack-OS/blob/syntakt-max-v1.0/tools/max/release_1_0/RELEASE_NOTES.md) and [attribution map](https://github.com/karigardarsson/Synthack-OS/blob/syntakt-max-v1.0/tools/max/release_1_0/ATTRIBUTION.md). Original MIT notices and separate runtime licenses are included in the ZIP; they grant no rights over Elektron firmware.
