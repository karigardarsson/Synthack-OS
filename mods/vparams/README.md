# vparams

Shared "virtual parameters" for mods: hidden parameter ids that a mod reads and writes its own way (RAM state, free kit words…) instead of the OS.

- Hooks the three central kit-parameter functions: is-kit `0x4000D870`, get `0x4000D94A`, set `0x4000DA32`.
- Table at mod-area offset `+0x8000`: 32 entries `{id, reserved, get, set, guard}` (16 bytes). Each mod writes its entries with `vparams.entry(slot, id, get, set, guard=0)` (an appended patch). A nonzero guard can make an entry context-local; otherwise registered ids report "kit = 1" and get/set jump to the mod with the OS stack layout. A rejected guard and every other id resume the original code unchanged.
- Slots: 0–6 master-comp, 7–8 beat-repeat, 9–16 fx3.

Tested through `tests/test_master_comp.py` (including "other ids behave exactly like the original") and `tests/test_beat_repeat.py`.
