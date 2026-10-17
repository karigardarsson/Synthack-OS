# Legal

*Not legal advice.*

- **Not affiliated with, endorsed or supported by Elektron Music Machines.** "Elektron", "Syntakt", "Digitakt" are trademarks of their owners, used only to describe compatibility.
- **No Elektron firmware is distributed.** No `.syx`, no extracted or disassembled sections. Users build from the stock OS they downloaded. `.gitignore` and the pre-commit hook (`tools/hooks`) enforce this.
- **Patches contain only our bytes** (our compiled code, our constants) plus SHA-256 hashes of the original bytes they expect.
- **Interoperability.** Analysis is limited to what our independently written mods need to run on the user's own device (EU Directive 2009/24/EC arts. 5–6; Italian L. 633/1941 arts. 64-ter/quater).
- **Not for sale.** Neither the mods nor prebuilt `.syx` files.
- Community code is **MIT**. The Windows builder includes the MIT elektron-firmware-tool helper and packaged Python/Tcl/Tk/PyInstaller runtimes, with their own license terms; see [release attribution](tools/max/release_1_0/ATTRIBUTION.md). Unicorn is a separately installed emulator and is not bundled in the Windows release. No blanket MIT claim applies to third-party runtimes or Elektron firmware.
