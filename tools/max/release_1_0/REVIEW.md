# MAX 1.0 local release review — 2026-10-17

Status: **GO for public community release with the documented Windows 11 test scope. The runtime redistribution gate is resolved.** No push, tag, release, flash or transmission was performed.

The former gate concerned 44 Microsoft UCRT/APISet DLLs collected from an undocumented host dependency directory. All 44 are now excluded. Native Windows startup confirms use of system UCRT. The retained VCRUNTIME140.dll matches Python.org's official 3.12.10 distribution byte for byte, whose Windows redistribution conditions are included. See [runtime evidence](RUNTIME_REDISTRIBUTION.md) and [exact DLL inventory](RUNTIME_DLL_INVENTORY.csv).

Candidate EXE: `ae0c4eb65beb79baaf0634fb9107bfa2a95abd35274e6c35f4228a621e9e2f92` (10570255 bytes). Firmware output remains `7cb4bfd3da4af9c417ae812ec205036a85a430f3be62263cf58e6ae31df2c093`. The previous EXE `cc0c042b69b46e5ffa06cbbe06b9f69ac0d5a6a9267e31f6d6495bc029ab7c3b` and previous review ZIP remain unchanged as rollback artifacts. Firmware code, patches, manifest, builder core and GUI source are unchanged.

Native Windows validation passed: new EXE startup with system-only PATH; actual system UCRT loading; packaged helper; golden core build using resources extracted from the new EXE; output container integrity; incorrect-input rejection; five focused tests; final asset inventory and ZIP checks. No network connection was observed during startup; the local build used no network downloads. This is not evidence of a network-isolated run.

Latest user evidence: Kári reports the complete GUI workflow succeeded with the new EXE (`ae0c4eb65beb79baaf0634fb9107bfa2a95abd35274e6c35f4228a621e9e2f92`). The earlier native startup and extracted-assets core build also passed. Coverage limits: Independent clean-machine/non-admin testing, Windows 10 runtime testing, cancelled/unwritable-destination GUI cases and exhaustive hardware/MIDI/Overbridge/project coverage remain untested. The output firmware itself is unchanged from the hardware-proven baseline.

Publish the complete ZIP (including its internal SHA256SUMS.txt), with GITHUB_RELEASE.md as the release body, after human review. See PUBLICATION_PLAN.md for the exact destination and tag plan. Keep all notices with the EXE; its embedded notice alone is incomplete. Select the reviewed source commit on `codex/max-builder-windows`. Do not publish firmware `.syx` files, the obsolete review ZIP, full local machine-path audit artifacts, or an FM4 source branch as this release. This run makes no release/tag or remote changes.
