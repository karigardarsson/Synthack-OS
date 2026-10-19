# Release writing standard

Use this short guide for Syntakt-related release pages, release notes, installation guides, and issue templates.

## Lead with the project

Start with what the project adds and the evidence behind it. State the relevant evidence level beside the claim:

- **HARDWARE-TESTED** — observed on a physical device.
- **HOST-TESTED** — verified by host-side tests.
- **EMULATOR-TESTED** — exercised in a simulated environment.
- **BUILD-VALIDATED** — built with structural, integrity, or packaging checks.
- **EXPERIMENTAL** — useful work that still needs practical coverage.

Only use categories that genuinely apply. Build or host validation does not establish complete device behavior.

## State limits naturally

After describing successful testing, name the important untested areas in one short paragraph. Treat them as opportunities for further testing, not as predictions of failure. Keep essential recovery, licensing, and input-firmware requirements in their dedicated pages instead of repeating them everywhere.

Suggested wording:

> This project is actively developed and has been tested in the ways described below. More configurations and workflows are still being explored, so feedback and test reports are welcome.

For firmware projects, add a practical reminder to keep a backup and the official firmware available for recovery.

## Invite useful feedback

Ask people to share the project version or image hash, device/OS version, selected options, exact steps, expected result, observed result, and any relevant photo or log. Thank testers and contributors without implying support for configurations that have not been verified.

## Preserve provenance

Keep original authors, licenses, third-party notices, official-firmware ownership, and hardware evidence intact. Do not turn a successful compile, static scan, or one device session into a broader compatibility claim.
