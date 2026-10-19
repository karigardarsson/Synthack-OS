# Syntakt recovery

Keep the official stock OS 1.41 and backups before installing modified firmware. Recovery has been demonstrated on Kári's Syntakt using the UNO Synth Pro X DIN path; this does not guarantee recovery for every interface or failure. MAX's patch tools preserve the bootstrap, but that alone is not proof of recovery.

## Device still boots

Use Elektron Transfer and the supported OS-update procedure with your official stock `.syx`. Follow the device confirmation prompts and do not interrupt power.

## Device does not boot normally

Follow [Elektron's SysEx recovery instructions](https://support.elektron.se/support/solutions/articles/43000662701-how-to-update-your-device-via-sysex-transfer) and the [Syntakt manual, startup-menu section](https://www.elektron.se/wp-content/uploads/2026/03/Syntakt-User-Manual_ENG_OS1.40_260304.pdf). The linked manual covers OS 1.40; the startup-menu procedure is the relevant reference, not proof of MAX compatibility.

1. Connect the interface's physical MIDI OUT to Syntakt MIDI IN.
2. Hold FUNC while powering on to open STARTUP.
3. Select TRIG 4, OS UPGRADE.
4. In Elektron Transfer's SYSEX TRANSFER page, choose OS upgrade via device startup menu and send the official stock image to the DIN MIDI port.
5. Follow the prompts and wait for completion; DIN transfer may take tens of minutes.

Startup-menu OS upgrade requires physical MIDI; USB MIDI is unavailable for that procedure. Interface SysEx support matters. TRIG 2 and TRIG 3 are reset operations and can erase data; they are not required for this OS recovery procedure.

The MAX builder only creates a local file. It performs no backup, device update, reset or recovery. Retain your own backup and official image.
