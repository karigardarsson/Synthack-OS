# Syntakt MAX 1.0 Windows Builder

The distributable is `Syntakt-MAX-1.0-Builder.exe`. It is a local Windows
application for a user-supplied official Syntakt OS 1.41 `.syx`. It never
connects to or transfers firmware to a device.

## External tester use

1. Run the supplied `.exe`.
2. Choose your official Syntakt OS 1.41 `.syx`.
3. Confirm its displayed SHA-256 is
   `8e2488f462c4a5656396a895f113bcd415e9900fa8709340dccf45d4cb9ed19e`.
4. Choose a new output filename.
5. The builder releases the output only if its SHA-256 is
   `7cb4bfd3da4af9c417ae812ec205036a85a430f3be62263cf58e6ae31df2c093`.

The executable bundles its runtime and does not require Python, WSL, Node,
Git, MSYS2, GCC, an administrator account, or network access at runtime.
It has been tested on Windows 11 x64; an independent clean-machine test
remains outstanding.

## Contents and licensing

The package contains source-derived patch data, the MIT-licensed
`elektron-firmware-tool` helper, and its notice in
`resources/THIRD_PARTY_NOTICES.txt`. It contains no Elektron firmware,
unpacked firmware sections, device projects, samples, or generated `.syx`
files.

## Developer packaging

`build_windows.ps1` compiles the bundled MIT helper and uses PyInstaller to
create the one-file executable. This requires Windows Python with PyInstaller
and MSYS2 UCRT64 GCC; these are build-time dependencies only.
