# Syntakt MAX 1.0 — building and installation

## Build locally on Windows

1. Extract the complete release ZIP, including notices. Target Windows 10/11 x64; Windows 11 x64 is the tested environment. Windows 10 remains untested. The EXE is unsigned; verify its checksum before running. A security prompt is possible; do not disable security protections to run it.
2. Obtain official **Syntakt OS 1.41** directly from [Elektron support](https://www.elektron.se/support). Keep an unchanged copy for recovery. Other versions or modified inputs are rejected.
3. Run `Syntakt-MAX-1.0-Builder.exe`, choose the stock `.syx`, click **Build and Save MAX 1.0**, then choose an output destination in the save dialog. Wait for its success dialog.
4. Verify the output SHA-256 with PowerShell: `Get-FileHash -Algorithm SHA256 -LiteralPath 'C:\path\to\your-output.syx'`. It must equal `7cb4bfd3da4af9c417ae812ec205036a85a430f3be62263cf58e6ae31df2c093`.

Stock SHA-256: `8e2488f462c4a5656396a895f113bcd415e9900fa8709340dccf45d4cb9ed19e`

EXE SHA-256: `ae0c4eb65beb79baaf0634fb9107bfa2a95abd35274e6c35f4228a621e9e2f92`

The packaged app builds offline and requires no separate Python, WSL, Git, compiler or MIDI connection. Runtime independence was tested on the development Windows system; an independent clean-machine and standard-user test remains outstanding. Choose a writable folder. If the app reports an error, do not use any partial output.

## Install separately with Elektron's tools

The builder never sends firmware. Before deciding to install, back up projects and sounds using your established Elektron backup workflow; read `RECOVERY.md` and have a working DIN recovery interface available. Follow [Elektron's OS update instructions](https://support.elektron.se/support/solutions/articles/43000662701-how-to-update-your-device-via-sysex-transfer) with your locally generated file. For a normally booting Syntakt, use Elektron Transfer's supported OS update flow and the device's confirmation prompts. Do not interrupt power or transfer.

Modified firmware is unofficial and provided without warranty. Recovery was demonstrated on Kári's unit using an UNO Synth Pro X DIN path; success on other interfaces or device states is not guaranteed. To return to stock, use the separately retained official image and Elektron's normal or startup-menu recovery procedure. Never use reset options as an OS-update substitute.

There is no generated `.syx` in this release. Do not upload generated firmware or official stock firmware to public issues or releases. Report builder logs/errors and hashes instead.
