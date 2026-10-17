# Windows runtime redistribution — resolved

## Cause and correction

PyInstaller 6.22.3 explicitly includes UCRT/APISet names for older Windows compatibility. On this host its dependency search collected 44 matching files from a Codex libheif dependency directory. Their signatures established identity, not redistribution permission. The previous review package remains a rollback artifact and is superseded for publication.

The maintained `tools/max/windows_builder/windows.spec` now removes `ucrtbase.dll`, `api-ms-win-*.dll` and `ext-ms-win-*.dll` from Analysis binaries before EXE assembly. Exactly 44 files were removed in this build: 43 APISet DLLs and UCRT, all PE file version `10.0.26100.4654`. No ext-ms files were present. It also fails packaging if another retained `.dll` comes from outside the selected Python installation. `build_windows.ps1` uses this specification and checks PyInstaller's exit status. No firmware, patch, manifest, GUI or builder-core source changed.

The exact old/new inventory, versions and fingerprints are in [RUNTIME_DLL_INVENTORY.csv](RUNTIME_DLL_INVENTORY.csv). `HOST_LIBHEIF` denotes the original host dependency tree, `PYTHON312` the Windows Python 3.12 installation. Full actual source paths are preserved in local ignored audit CSVs rather than embedded as developer paths in the public package.

## Authoritative deployment evidence

- [Microsoft: Universal CRT deployment](https://learn.microsoft.com/en-us/cpp/windows/universal-crt-deployment): UCRT is an OS component on Windows 10 and later. Windows 10/11 uses the system copy even if an app includes another. The SDK Redist source is needed for local redistribution; this package instead excludes those OS files entirely.
- [PyInstaller 6.22.3 DLL policy](https://github.com/pyinstaller/pyinstaller/blob/v6.22.3/PyInstaller/depend/dylib.py#L130-L139): its own comments say APISet/UCRT need not be bundled when targeting Windows 10 and later. Its default include policy accounts for their collection here.
- [PyInstaller spec-file documentation](https://pyinstaller.org/en/stable/spec-files.html): Analysis binary TOCs are supplied to EXE packaging. The checked-in spec filters that TOC; the final CArchive, rather than Analysis alone, is checked for exclusions.

Packaging requires **Windows 10/11 x64**. Native runtime tests were performed on **Windows 11 x64** only; Windows 10 and other platforms were not tested. No Windows 8/8.1 support is claimed after this exclusion.

## Retained DLLs and provenance

| DLL | PE file version | Source |
| --- | --- | --- |
| libcrypto-3.dll | 3.0.16.0 | `PYTHON312/DLLs/libcrypto-3.dll` |
| python312.dll | 3.12.10150.1013 | `PYTHON312/python312.dll` |
| tcl86t.dll | 8.6.2.15 | `PYTHON312/DLLs/tcl86t.dll` |
| tk86t.dll | 8.6.2.15 | `PYTHON312/DLLs/tk86t.dll` |
| VCRUNTIME140.dll | 14.42.34438.0 | `PYTHON312/VCRUNTIME140.dll` |
| zlib1.dll | 1.3.1.0 | `PYTHON312/DLLs/zlib1.dll` |

All six are byte-identical to the previous package. Python/Tcl/Tk/OpenSSL/zlib retain their original notices. `VCRUNTIME140.dll` remains because the packaged Python and library binaries import it; it is not the removed UCRT DLL.

For the Microsoft VC runtime, the exact bytes were matched against [Python.org's official Python 3.12.10 x64 embeddable ZIP](https://www.python.org/ftp/python/3.12.10/python-3.12.10-embed-amd64.zip). Download SHA-256: `4acbed6dd1c744b0376e3b1cf57ce906f9dc9e95e68824584c8099a63025a3c3`. Its `VCRUNTIME140.dll` SHA-256 is `052ad6a20d375957e82aa6a3c441ea548d89be0981516ca7eb306e063d5027f4`. Its `python312.dll` also matches the packaged DLL exactly. The official archive's LICENSE.txt matches the complete `licenses/Python-3.12.10.txt` already shipped here (SHA-256 `e502c6b880ff58d614901495a9009c136539cd0b1e2a2abb8fc00b934c203419`).

That official Windows license explicitly permits redistribution of the Windows Python binary build subject to its Microsoft Distributable Code conditions. The full license and extracted conditions are retained. This Windows-only app preserves notices, claims no Microsoft endorsement, and does not relicense Microsoft runtime code as MIT. Provenance is established by an official distribution byte match and its terms, not signature alone. Python's runtime binaries are unmodified; only application code and packaging are added.

## Native validation and limits

| Check | Result / scope |
| --- | --- |
| Final archive inventory | PASS: 955 members, six DLLs, zero UCRT/APISet payload files; no firmware `.syx`, section binaries or samples. |
| EXE startup | PASS on Windows 11 x64 with PATH limited to Windows System32; both onefile processes remained alive. |
| Actual UCRT location | PASS: both processes loaded `C:\WINDOWS\System32\ucrtbase.dll`. Application Python/Tcl/Tk/crypto/zlib and VC runtime were loaded from the onefile extraction area. |
| Native helper | PASS: helper extracted from the new EXE executed --help with exit 0 and performed the container operations used by the complete core build. |
| Golden firmware | PASS: native Windows core driven by an installed test Python, using helper and manifest extracted from the new EXE, generated `7cb4bfd3da4af9c417ae812ec205036a85a430f3be62263cf58e6ae31df2c093`; checksums OK and decompression margin 19,052 bytes. This is not a new GUI-dialog end-to-end test. |
| Incorrect input | PASS: exact-stock hash gate rejected invalid input without output. |
| Focused builder tests | PASS: all five on native Windows. |
| Helper preservation | All nine PE section byte sequences unchanged from prior helper; rebuilt PE timestamp/header checksum differ. |
| Offline behavior | Local build completed with no downloads or network services; no TCP/UDP endpoints observed during EXE startup. No network-isolation/firewall test was performed. |
| Rollback / firmware | Prior EXE and review ZIP preserved; known-good firmware, manifest, patches and builder core unchanged. |

The new EXE is `ae0c4eb65beb79baaf0634fb9107bfa2a95abd35274e6c35f4228a621e9e2f92`, 10,570,255 bytes, unsigned. Kári's complete manual GUI test was of the prior EXE `cc0c042b69b46e5ffa06cbbe06b9f69ac0d5a6a9267e31f6d6495bc029ab7c3b`. The application source is unchanged; startup and packaged-resource core tests were repeated for the new EXE. An independent clean-machine/non-admin run, a fresh manual GUI build using the new hash, and Windows 10 runtime testing remain coverage limits. They are not represented as completed tests.

**The specific UCRT/APISet redistribution gate is resolved:** those 44 files are absent from the distributable. The one retained Microsoft application-runtime DLL has an exact official-distribution match and accompanying redistribution conditions. The candidate is suitable for public community distribution with the complete ZIP's notices and these stated test limits. No publication is authorized or performed by this preparation run.
