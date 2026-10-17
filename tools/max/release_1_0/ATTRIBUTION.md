# Syntakt MAX 1.0 attribution

MAX is a community integration of existing mods. It does not claim authorship of those mods or of Elektron's OS. Git history records this fork's integration and builder commits under Kári Garðarsson; development used Codex assistance.

| Component / contribution | Author or project | Exact source / license | Requirement |
| --- | --- | --- | --- |
| Compressor, FX3, Beat Repeat, dual mono, readable values, splash, heap modarea, vparams, build/emulator infrastructure | Angelo-politek and Syntakt+ contributors | [Synthack-OS at 3e5e9e83](https://github.com/Angelo-politek/Synthack-OS/tree/3e5e9e83caced4a29043ca2a8f3a71cde4b6460a), including heap fix c48f0937; MIT | Retain copyright and permission notice: `licenses/SyntHack-MIT.txt`. |
| DV-F/DV-T, SY CHORD wave replacement, interpolation-compatible bank generation, pictures, chord-cycle synthesis | Bezronczek | [Firmware Workbench at 49a7a1e5](https://github.com/Bezronczek/syntakt-firmware-workbench/tree/49a7a1e5ac1ac4c6869f01b94a820f2b625dada5); MIT | Retain copyright and permission notice: `licenses/Workbench-MIT.txt`. |
| MAX integration, fixed 31-wave selection and analytic waveform recipes, guarded combined build, reproducibility checks | Kári Garðarsson's fork, with Codex assistance | [integration commit 6bdc769](https://github.com/karigardarsson/Synthack-OS/commit/6bdc769); repository MIT | Preserve upstream notices; these are integration/bank contributions, not newly authored compressor, FX or LFO engines. |
| Standalone Windows GUI/core, manifest packaging, Windows helper portability fixes | Kári Garðarsson's fork, with Codex assistance | [builder commit 564b04c](https://github.com/karigardarsson/Synthack-OS/commit/564b04c), packaging a82a14b; repository MIT | Preserve repository and helper notices. These local commits may not yet exist at the linked public URLs until publication. |
| Firmware container helper | Marcel Bierling / mischa85 | [elektron-firmware-tool](https://github.com/mischa85/elektron-firmware-tool); MIT; vendored source in `tools/max/windows_builder/vendor/elektron-firmware-tool` | `licenses/elektron-firmware-tool-MIT.txt`. Windows mkdir wrapper is a fork portability change. |
| Python 3.12.10 and bundled library notices | Python Software Foundation and listed contributors | [Python 3.12.10](https://www.python.org/downloads/release/python-31210/); PSF and bundled licenses | Full installed `LICENSE.txt`, including Microsoft binary restrictions, in `licenses/Python-3.12.10.txt`. |
| Tcl/Tk 8.6.15 | Tcl/Tk contributors named in notices | [Tcl](https://github.com/tcltk/tcl/tree/core-8-6-15), [Tk](https://github.com/tcltk/tk); Tcl/Tk permissive terms | Verbatim Tcl and Tk notices in `licenses/`. |
| PyInstaller 6.22.3 bootloader and runtime hooks | PyInstaller contributors | [PyInstaller](https://github.com/pyinstaller/pyinstaller/tree/v6.22.3); GPL with bootloader exception; runtime hooks Apache-2.0 | Full `licenses/PyInstaller-6.22.3.txt`; bundling does not make MAX firmware GPL. |
| OpenSSL 3.0.16 / zlib 1.3.1 | OpenSSL contributors / Jean-loup Gailly and Mark Adler | [OpenSSL](https://github.com/openssl/openssl/tree/openssl-3.0.16), [zlib](https://github.com/madler/zlib/tree/v1.3.1); Apache-2.0 / zlib | Full notices in `licenses/`; Python's notice collection covers other bundled standard-library components. |
| Microsoft VC/UCRT DLLs | Microsoft Corporation | Supplied through Windows/Python/host dependency environment; proprietary runtime terms, not MIT | Preserve Microsoft notices and restrictions in Python's license. See `REVIEW.md`: provenance of host-collected UCRT/APISet DLLs still needs confirmation before publication. |

Déjà Vu's behavior is inspired by Mutable Instruments Marbles, as credited by Workbench. No claim is made that MAX includes Mutable Instruments code. No third-party sampled wave collection or WaftWave bank is used in this fixed MAX bank.

Rxuting's MIT-licensed [SY FM4](https://github.com/Rxuting/sy-fm4) remains separate research. FM4, the old MAX2 private-object architecture, arbitrary wave importing, new MIDI features and planned upstream features are not included in MAX 1.0.

Elektron firmware remains Elektron's proprietary work. The release requires the user's separately acquired official OS; community licenses grant no rights to distribute that firmware or generated images. Syntakt and Elektron are trademarks of their owners. No Elektron affiliation or endorsement is claimed.

Distribute the complete ZIP with these notices; the existing EXE's embedded notice only names the container helper. The external notices complete the attribution for this release without changing the verified EXE.
