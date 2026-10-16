# SY FM4 on upstream MAX: OS 1.41 offline status

The initial findings below are retained for provenance; the page-local adapter checkpoint at the end supersedes their test count and UI blocker description.

The upstream MAX image at `out/synthack-upstream-max.syx` is unchanged (SHA-256 `7cb4bfd3da4af9c417ae812ec205036a85a430f3be62263cf58e6ae31df2c093`). The user reports it boots and works musically on hardware. No combined FM4 firmware image has been generated.

The port uses Rxuting's pinned MIT source at commit `a596b6393fc43582fd3ae0234ac04e198b779edb`. CPU1 and CPU2 code compile; section-7 staging fits. The exploratory CPU1 source uses FM4-only IDs 505-512 and avoids writes to native object instances beyond ID 504. Its proposed donor-object pointers have not been exercised through the complete UI. The firmware patch generator deliberately retains the stock-row ownership guard and cannot build a candidate.

## Verified offline

- Actual OS 1.41 sound save/load routines preserve all eight logical values at 0x36-0x3D; legacy SY TONE data loads ALGO 0 defaults.
- Actual pattern-lock writer/reader round-trip all eight FM4 lanes 0x50-0x57, alongside a native lock.
- CPU1 DMA publisher places eight values per voice in shared RAM; FX3 kit round-trip still passes with FM4 storage overlays.
- Section-7 Unicorn render checks show bit-exact stock SY TONE state/output for ALGO 0 and distinct nonzero output for the 11 FM4 algorithms. This is emulator evidence, not hardware audio proof.
- A 0x2A4-byte stock position-table window can be copied to heap modarea +0x6000, with five absolute operand references retargeted. Actual OS 1.41 converters gave identical results before and after. This region does not overlap existing MAX append payloads. The vacated descriptor gap fits eight 52-byte rows without moving the native descriptor base.
- Actual descriptor accessors at 0x400A5C4A and 0x400A5C6C can read FM4 rows in a test-only bound extension while preserving tested native IDs and out-of-range fallback.
- Focused suite: 126 tests passed (FM4 storage, voice, descriptor-space, ID audit, FX3 and modarea).

## Exact remaining blocker

SourcePageView slot 47 can return FM4 IDs 505-512, but two actual shared UI guard fragments at 0x4003B8D4 and 0x4003B6BE clamp all of them to ID 0; Unicorn confirms both accept native ID 504. The shared object accessor at 0x4007B9B2 also maps every new ID to object 0. The page-2 descriptor gap and donor pointer prototype are not wired into firmware because the complete encoder, draw, notification, default initialization and object-mutation paths have not been proven safe for IDs 505-512. Kit/project outer serialization and full UI interaction also remain unverified. A narrow bound change may be possible but cannot be treated as sufficient without those call paths and native regression checks.

Focused question for Angelo or Rxuting: On OS 1.41, which SourcePageView-specific hook points can route IDs 505-512 through the shared encoder/render/notification handlers and supply visual objects without mutating native donor objects? A working call graph for 0x4003B870 and the branch containing 0x4003B6BE would let us finish a scoped implementation while preserving native ID behavior.


## Page-local adapter implementation checkpoint (current branch)

The preparer now compiles eight separate 84-byte UI objects at fixed OS-session
addresses. It copies their scalar header and uses stock `0x401882BE` to clone
the four `std::function` members with their native manager operation (2).
It does not mutate donor objects. FM4 IDs 505-512 are exposed from SourcePageView
only after those objects finish initializing. The page-scoped guard helpers and
call-site patch generators cover the two encoder clamps, post-edit redraw,
key handler, notification clamp, six logical-index call sites, one track
classification site, three range sites, and five identified object sites.
All native IDs delegate to stock behavior in the tested helpers.

These patches remain staged helpers; `patches()` still rejects occupied native
rows 36-43 and cannot emit a firmware candidate. The proper eight descriptors
fit in the vacated contiguous gap after relocating 0x2A4 bytes of stock position
tables. The compiled CPU1 blob is 2,972 bytes; its BSS ends at `0x444E97C0`,
272 bytes before the relocated table at `0x444E98D0`. The 34 staged ranges
do not overlap each other or 206 address-bearing existing MAX patch entries.
CPU1 and CPU2 blobs rebuild byte-identically.

**Blocking call edge:** at `0x4003B57A` / `0x4003B5A2` the generic editor
calls the selected sound model's virtual getter/setter (+0x28/+0x50) with the
descriptor ID. Its stock implementations are not yet identified for both
selected-track and held-trig contexts. The actual OS model getters tested at
`0x40011B18` and `0x40011FBC` return zero for all IDs 505-512; the shared
adjuster `0x40012316` leaves a high-ID value unchanged because of its native
504 bound. Therefore passing the UI guard, range and object checks does not
provide a working value edit. Applying the staged patches as firmware would be
unsafe. Drawing and notification beyond the inspected sites, pattern/project
outer persistence, and full page-switch interaction are also unproven.

Focused suite: 134 passed, including instruction-level staged guard, logical
metadata, object-clone, range, key and notification checks; actual OS sound,
lock, voice, FX3, ID-audit and modarea regressions. No hardware validation of
FM4. The known-good upstream MAX image remains SHA-256
`7cb4bfd3da4af9c417ae812ec205036a85a430f3be62263cf58e6ae31df2c093`.
No unified image generated.

Question for Angelo/Rxuting: On OS 1.41, which concrete model vtable is held
at SourcePageView+0xA0 for selected-track sound and for held-trig sound, and
which getter/setter entries can safely route descriptor IDs 505-512 to logical
sound indices 0x36-0x3D while retaining the stock lock and notification path?

## Sound-model editor trace (current run)

The complete encoder route is more specific than the earlier getter/setter
description. SourcePageView first selects an active model through vtable slot
+0xC4 at 0x40037D70, which delegates to 0x4001C422. Its adjustment path at
0x400380C6 invokes active-model slot +0x20; the two relevant native model
vtables use 0x40012316. The arguments are (model, descriptor_id,
current_value, encoder_delta). Its result is passed to
0x4000DA32(context, descriptor_id, value, 1), which performs the native
write and notification dispatch.

The call at 0x4003B5A2 is not that persistent write path: for one active model
it resolves to 0x400121A8, a value-conversion helper. Replacing it would create
a misleading UI-only result.

A bounded Unicorn trace of the real 0x40037E50 instruction sequence confirms
that the native helper receives (context, 505, encoder_delta) before it would
tail-call 0x4000DA32. The trace used only synthetic view state, so it does not
establish the hardware-selected track or held-trig provider layout. For high
IDs, native 0x40012316 rejects the range and native 0x4000DA32 has no safe
logical-storage or notification route.

**Current safety gate:** an FM4 adapter must preserve both the model selected
by 0x4001C422 and the native write/notification semantics at 0x4000DA32 for
ordinary tracks and held trigs. Directly writing a logical word would not
demonstrate p-lock creation, restoration, or UI notification equivalence.
No candidate is generated from this checkpoint.

Focused question for Angelo/Rxuting: which model/provider operation used by
0x4000DA32 is the supported way to write a logical sound index while
preserving held-trig locks and change notifications, and can it accept
indices 0x36..0x3D without widening the global descriptor tables?
