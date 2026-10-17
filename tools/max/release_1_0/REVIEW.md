# MAX 1.0 local release review — 2026-10-17

Status: **prepared locally; HOLD public publication pending the runtime provenance item below**. No GitHub push, tag, release, hardware flash or MIDI transfer was performed.

## Open publication gate

PyInstaller's actual Analysis-00.toc collected `ucrtbase.dll` and APISet DLLs from a host Codex runtime/libheif dependency directory, rather than an identified Windows SDK redistribution folder. The UCRT DLL has a valid Microsoft signature and version 10.0.26100.4654. The host dependency manifest identifies libheif and other libraries but supplies no redistribution terms for these Microsoft files. No installed Windows SDK Redist directory was found. Python's Microsoft binary restrictions are included, but do not establish the source/grant for the additional host-collected files.

This is an **incomplete redistribution evidence chain**, not evidence of infringement or a runtime defect. Microsoft documents local UCRT deployment using SDK Redist DLLs: https://learn.microsoft.com/en-us/cpp/windows/universal-crt-deployment . Before publishing the binary, establish the applicable grant for these exact DLLs. If that cannot be established, a separately authorized packaging-only rebuild should use a documented redistributable source or rely on the Windows 11 system UCRT, followed by hash and GUI validation. The existing verified EXE was deliberately preserved in this run.

## Validation record

- Exact release input: builder code at `4525e3aa6fdf2ec7dc9e5f52e57d870c3f41272c`; no builder-core, firmware, manifest or executable changes in this release-preparation run.
- EXE: `cc0c042b69b46e5ffa06cbbe06b9f69ac0d5a6a9267e31f6d6495bc029ab7c3b`, 11626089 bytes. Known-good firmware: `7cb4bfd3da4af9c417ae812ec205036a85a430f3be62263cf58e6ae31df2c093`. Stock: `8e2488f462c4a5656396a895f113bcd415e9900fa8709340dccf45d4cb9ed19e`.
- User-reported manual GUI success is recorded in RELEASE_NOTES.md without inventing a separately measured output hash.
- Earlier focused/core/container tests are attributed as earlier evidence, not rerun firmware validation. This run rechecks file hashes, manifest composition, licenses, package allowlist, archive integrity, Git diff and protected-source hashes.
- MIT SyntHack, Workbench and helper licenses included verbatim; Python's installed license collection, PyInstaller license/exception, Tcl/Tk terms, OpenSSL and zlib notices included externally. This is a multi-license package; the top-level MIT does not relicense runtimes or Elektron firmware.
- Remaining test coverage limits: independent clean Windows machine; normal non-admin account; cancelled file chooser and unwritable-destination GUI cases; exhaustive device/MIDI/Overbridge/project compatibility.

## Proposed publication shape (not executed)

Title: `Syntakt MAX 1.0`

Upload the complete reviewed Windows ZIP plus its external SHA256SUMS.txt; use RELEASE_NOTES.md as the release body. Do not attach the raw EXE alone because its external notices are required. Do not attach any firmware `.syx`. Select the eventual reviewed source commit on this builder branch; do not use an FM4 branch as the release target. No tag was created by this run.
