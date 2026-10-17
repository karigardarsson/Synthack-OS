# Syntakt MAX 1.0 FAQ

## Do I need to have OS 1.41 installed first?

You need an unchanged, official Syntakt OS 1.41 .syx file for the builder. The
builder does not read from, connect to, or update your Syntakt. It creates a
local MAX file from that official 1.41 input.

## My Syntakt is on OS 1.42. Can I use the builder?

The builder will not accept an OS 1.42 file; it accepts only the exact official
OS 1.41 input listed in the installation guide. Building a MAX file is possible
without changing the device, but installing a 1.41-derived MAX file on a
Syntakt currently running 1.42 has not been hardware-tested by this project.
Keep your official 1.42 and 1.41 files, make backups, and use Elektron's own
update and recovery guidance for any version change.

## Where do I get official OS 1.41?

Download it from the Syntakt section of [Elektron support](https://www.elektron.se/support).
Use the original, unmodified file. The builder checks its fingerprint and
rejects other versions or altered inputs.

## Do the 31 SY CHORD waves replace stock waves?

Yes. MAX replaces WAVE values 4, 8, through 124 with its fixed 31-wave bank.
Shared WAVE 0 is unchanged. Existing sounds that use a replaced WAVE value can
sound different after MAX is installed, so back up your sounds before trying it.

## Does the master compressor have a sidechain input?

No separate sidechain source is selectable. The compressor listens to the
analog master mix bus and applies gain reduction to that same analog master
output. It is therefore self-keyed master compression, rather than a
DAW-style external or per-track sidechain.

## Does the builder work on Windows or Mac?

Windows 11 x64 is the tested platform. The package targets Windows 10/11 x64,
but Windows 10 has not been tested by this project. A community member has
reported success running the builder under Wine on a Mac; that is a report,
not a supported or independently verified macOS configuration.

## Are there demonstration videos?

No demonstration video is included with this release. The feature list and
screens are documented in the repository. Community videos or posts can be
useful demonstrations, but they do not establish compatibility with every
Syntakt, operating system, interface, or project.

## What should I back up, and how do I recover?

Back up projects and sounds using your normal Elektron workflow before any
firmware update. Keep an unchanged official OS image and a recovery-capable
DIN MIDI interface available. Read the [installation guide](INSTALL.md) and
[recovery guidance](../../../RECOVERY.md) before installing anything. The
builder never transfers firmware to the device.

Recovery was demonstrated on one Syntakt with an UNO Synth Pro X DIN path.
Other interfaces and device states have not been validated. Do not use startup
reset options as an OS-update substitute.
