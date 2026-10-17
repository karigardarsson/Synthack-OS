# Syntakt MAX 1.0 Windows Builder

The distributable is `Syntakt-MAX-1.0-Builder.exe`. It is a local Windows
application for a user-supplied official Syntakt OS 1.41 `.syx`. It never
connects to or transfers firmware to a device.

## External tester use

1. Run the supplied `.exe`.
2. Choose your official Syntakt OS 1.41 `.syx`.
3. Confirm its displayed SHA-256 is
   `8e2488f462c4a5656396a895f113bcd415e9900fa8709340dccf45d4cb9ed19e`.
4. Click **Build and Save MAX 1.0**, then choose a new output filename.
5. The builder releases the output only if its SHA-256 is
   `7cb4bfd3da4af9c417ae812ec205036a85a430f3be62263cf58e6ae31df2c093`.

The executable bundles its runtime and does not require Python, WSL, Node,
Git, MSYS2, GCC, an administrator account, or network access at runtime.
It has been tested on Windows 11 x64. Kári manually completed stock selection,
build, success dialog and output generation. An independent clean-machine and
standard-user test remains outstanding. See the [release review](../release_1_0/REVIEW.md).

## Contents and licensing

The package contains source-derived patch data, the MIT-licensed
`elektron-firmware-tool` helper, and its notice in
`resources/THIRD_PARTY_NOTICES.txt`. Distribute the complete release ZIP with
the additional upstream and runtime notices in [release attribution](../release_1_0/ATTRIBUTION.md);
the existing EXE alone does not carry all of these external notices. It contains no Elektron firmware,
unpacked firmware sections, device projects, samples, or generated `.syx`
files.

## Developer packaging

`build_windows.ps1` compiles the bundled MIT helper and uses PyInstaller to
create the one-file executable. This requires Windows Python with PyInstaller
and MSYS2 UCRT64 GCC; these are build-time dependencies only.

## Windows runtime packaging

The maintained `windows.spec` excludes OS-provided UCRT/APISet DLLs for the
Windows 10/11 target and rejects retained DLLs from outside the selected Python
installation. Windows 11 x64 startup and packaged-resource core tests passed;
Windows 10 and an independent clean machine remain untested. The new EXE needs
a fresh manual GUI run if validation of every file-dialog interaction at its
new fingerprint is required. See [runtime provenance and validation](../release_1_0/RUNTIME_REDISTRIBUTION.md).
