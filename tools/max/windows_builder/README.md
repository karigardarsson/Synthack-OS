# Syntakt MAX 1.0 Windows Builder

This directory builds a local Windows application for a user-supplied, official
Syntakt OS 1.41 `.syx`. It contains source-derived patches and the MIT-licensed
container tool source only. It contains no Elektron firmware, unpacked firmware
sections, device projects, samples, or generated `.syx` files.

The builder accepts only SHA-256
`8e2488f462c4a5656396a895f113bcd415e9900fa8709340dccf45d4cb9ed19e`
and releases output only after it matches the MAX 1.0 golden SHA-256
`7cb4bfd3da4af9c417ae812ec205036a85a430f3be62263cf58e6ae31df2c093`.

Run `build_windows.ps1` from Windows. It compiles the bundled MIT
`elektron-firmware-tool`, then uses PyInstaller to create one local `.exe`.
The application has no networking or transfer code and never flashes hardware.
