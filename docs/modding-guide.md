# Modding guide

How the mods in this repository are built, and how to do the common things: hook code, add a page or a parameter, give it a name, a text and an icon, save its value, add audio processing without slowing the UI down. Addresses are for Syntakt OS 1.41, CPU #1 (section 3). Reference material: [memory-map](memory-map.md), [ui-parameters](ui-parameters.md), [audio-path](audio-path.md), [emulation](emulation.md), [firmware-format](firmware-format.md).

## 1. Workflow

1. `mods/<name>/make_patch.py` compiles the code (GNU as or gcc for ColdFire, `-mcpu=54418`) and writes `patch.json`: for each change, the address, a SHA-256 of the original bytes and our bytes. Code larger than a few hundred bytes goes to the [mod area](../mods/modarea) (`"append": true`, linked at `modarea_layout.RAM + offset`, in the OS heap).
2. `tests/test_<name>.py` loads the stock section 3 into Unicorn, applies the patch and runs the original code around it. EMAC instructions run in Python (`tools/emu/emac.py`): give it the list of EMAC sites of your code.
3. `tools/build/build.py` checks every hash, overlaps and the boot decompression margin, and writes the `.syx`.
4. Flash, test on the device, only then publish.

Mod area (first 64 KB block of the OS heap, from `modarea_layout.RAM`; unpacked at boot, zeroed beyond the code):

| Offset | Use |
|---|---|
| `+0x0000` | master-comp |
| `+0x2000` | readable-values |
| `+0x4000` | beat-repeat |
| `+0x7E00` | vparams code; `+0x8000` vparams table (32 × 12 B) |
| `+0xA000` | fx3 code and data; `+0xE000` fx3 delay line (4 KB) |

Section 3 free fill `0x40338740–0x40339000`: splash, dual-mono, modarea loader (nearly full).

**Rules learned the hard way**

- Never touch sections 2 and 6; never make the boot intro longer.
- Never use the RAM above the BSS (`0x45565490–0x48000000`): no code refers to it, but the OS writes all over it when it loads samples ([#4](https://github.com/Angelo-politek/Synthack-OS/issues/4)). Memory for mods comes from the mod area, i.e. from the OS heap.
- Keep the boot decompression margin (build fails under 4 KB). Zero padding is the worst case.
- No `.bss` in mod code: put variables in `.data` (`__attribute__((section(".data")))`). The mod area is zeroed anyway, but the build checks.
- No libgcc: `nm -u` must be empty. ColdFire has `divu.l`/`remu.l`, `ff1`, `mvs`/`mvz`, `sats` — GCC uses them.
- ColdFire limits: `muls.l` takes no absolute address (use `d16(An)`), no `exg`, `movem` only with `(An)`/`d16(An)`, short branches reach ±127 B.

## 2. Hooking code

A hook replaces ≥ 6 bytes of OS code with `jsr ours` (padded with `nop`), and the trampoline **replays the replaced instructions** before returning. The patch stores the hash of the original bytes, so a different OS version fails the build instead of crashing.

- Save every register you use; the OS keeps values in registers across the hook point.
- Replaced `pea` pairs (arguments of the next call): pop the return address, push the arguments, `jmp` back (`fx3_mix_hook`).
- Replaced `jsr f`: do your work, then `jmp f` with the stack untouched (`fx3_del_hook`).
- Replaced EMAC instructions: replay them first (`fx3_trk_hook`). If your code uses EMAC, set `MACSR` yourself and leave `ACC0` at 0 (the OS sum routines start from it).
- One-time setup at boot: hook an instruction of the page initializer (`0x401885D2…`), e.g. a `clr.l` that empties a page slot (`fx3_page_stub`, `comp_page_stub`). Objects built earlier in that initializer are ready.

## 3. Parameters

Logical id → descriptor (`0x4022D59C + 52·id`: group, internal id, min/max/default, MIDI, names at +40/+48). An id without a page or a MIDI CC is not necessarily free: if another descriptor has the same group and internal id, it is an **alias** that the OS can put on a page in some modes (#3). `tests/test_id_audit.py` rejects aliases, MIDI CC/NRPN and ids shared between mods; ids in use are listed in [ui-parameters](ui-parameters.md#hidden-ids-used-by-the-mods). Patch min/max/default and the name pointers in the descriptor to make the id yours.

**Virtual parameters** ([vparams](../mods/vparams)): register `{id, get, set}` in the table and the three kit functions (is-kit, get, set) call your functions for that id. Values are 0…0x7F00 (127 × 256). `set` must request a redraw: `*(*0x444E1334 + 96) = 1`.

**Saving.** Two kinds of spare storage, both saved by the OS without knowing:

- **Per track**: engine word +106 (internal id 39, hidden id 72 "amp delay time") is saved per track and p-lockable. fx3 uses it for SND3 (a real OS parameter: only its descriptor and page slot change).
- **Per kit (pattern)**: `*0x800030BC` is the pattern kit = the FX track's parameters, one word per internal id (offset = 2 × id, 142 B). Words with no use: ids 0, 0x1A, 0x24, 0x27, 0x29, 0x2A, 0x37, 0x46 and 0x38 (hidden id 144). master-comp uses 0x24/0x27/0x29/0x2A, fx3 0/0x1A/0x38/0x46, beat-repeat 0x37: **all taken**. Store values **XOR their default**, so old projects (zero words) load with defaults. Read the word on every use (pattern changes swap the kit); fall back to RAM while the pointer is 0. With *global* FX blocks the OS uses a container at `0x41B9D3B0` instead (master-comp follows the SYN flag).
- **Kit on storage** (FUNC+YES/NO, project save): the FX block goes through a position table that drops words 0x1A and 0x46 and reads word 0 back from 0x1A. fx3 keeps those three words in 8 reserved bytes of the stored block (hooks at `0x400A6D96` / `0x400A6D2E`). Any new kit word must survive the round trip tested in `tests/test_fx3.py`.

## 4. Pages and tabs

- **Page objects** live in BSS (array at `0x41B9F3C8`, 44 B each): names and 8 slot ids. Slots are read at draw time: write a slot to move a parameter, write 0 to empty it (fx3 hides the crusher's unused knobs this way, `SLOTS[4..5]`).
- **AMP pages** (track), first slot (A) of each variant: page 1 `0x41B9F60C` (AHD envelope) / `0x41B9F638` (ADSR), page 2 `0x41B9F664` / `0x41B9F690`; 4 B per slot. fx3 puts SND3 in slot G of page 1 (`0x41B9F624`, `0x41B9F650`) and PAN in slot E of page 2 (`0x41B9F674`, `0x41B9F6A0`), from a stub at the end of the AMP pages in the initializer (`0x40194A50`).
- **Tabs** are built from constant arrays of page indices plus a count, e.g. REVERB `{21}` (count at `0x4003588C`, array pointer at `0x40035892`). To add a page: point the array to your own `{21, 25}` and set the count to 2 — the tab key then cycles the pages. Page 25 ("OB8") is a stock page, not a globally free allocation. A mod that borrows it must scope and restore its UI ownership.
- **Tab classes** can draw slots their own way: the DELAY/REVERB class draws slots 5–6 as one filter box (fx3 sends page 25 to the generic 8-slot draw `0x4003A244`); the AMP class draws ids 73–77 and unknown ids as the envelope (a patched branch at `0x40041E84` lets id 72 draw normally).
- Page names: pointers in the initializer (`fx3` patches two `pea`); to rename at runtime, point them to a RAM buffer and rewrite it.

## 5. Text, icons and styles

Each parameter has an object at `0x41B9FA24 + 84·id` with `std::function`s (16 B: `data0, data1, manager, invoker`):

| Offset | Called as | Role |
|---|---|---|
| +20 | `invoker(fn, value, char *buf)` | value → text (≤ 6 characters fit a slot) |
| +36 | `invoker(fn, value, ctx, x, y)` | icon / value graphic |
| +68 | (style) | how the value is shown around the icon: bar, knob, … ; empty = default renderer |

At boot the initializer copies shared **prototypes** into each object (`pea <prototype>` before `0x401882BE`). Two ways to change them:

- **At build time** (fixed look): patch the `pea` operand of that id to another prototype — this is how SND3 got the machines' MOD icon and the delay-send bar.
- **At runtime** (look depends on state): write the 16 bytes yourself as `{0, 0, our_manager, invoker}`, where `our_manager` is a no-op (`return 0`) and `invoker` is your function, or the invoker read from a prototype's +12. Only do this for invokers that ignore the functor data (check the disassembly: they never read the first argument), and **only from UI code** (formatters, graphics, set): if the audio interrupt rewrote a `std::function` while the UI was calling it, the UI would jump to a half-written address. Don't raw-copy OS prototypes: their data points to a heap functor shared with the prototype.

Useful prototypes (+36 icon, +68 style as the OS pairs them; "frames" icons pick a picture by value):

| Prototype | Used by | Notes |
|---|---|---|
| `0x41B9DCD0` | most knobs | plain knob |
| `0x41B9DC70` + `D660` | LFO DEP, delay WID | bipolar value |
| `0x41B9DBD0` / `DBA0` + `D5D0` | track DEL / REV send | send icon + bar |
| `0x41B9DB80` + `D660` | PAN, BAL | pan |
| `0x41B9DC00` + `D5C0` | track VOL | level |
| `0x41B9DCB0` + `D670` | OVER (all machines) | overdrive, frames |
| `0x41B9D6B0` | SPD (machine 467) | frames |
| `0x41B9D730` | MOD | frames |
| `0x41B9D7D0` / `D7E0` | sweep time / depth | frames |
| `0x41B9D740` / `D760` / `D780` + `D660` | BAL / TONE / noise colour | frames |
| `0x41B9D830` | TICK | frames |
| `0x41B9DCD0` + `D5E0` | delay FDBK | feedback style |

Avoid prototypes whose invoker reads project state (e.g. `0x41B9DB90`, `DBB0`, `DBC0` read the FX routing; `D8F0`, `D920`, `DB10` read the project): they would draw the OS state, not your value. The full list (id → prototypes) can be rebuilt by scanning the initializer for `pea 0x41B9Dxxx` before each object address.

Drawing yourself: text `0x400F8C18(ctx, font, x, y, centred, 0, width_template, fmt, ...)` (fonts `0x402A91C0` 4×6, `0x402A9DC4` 3×6); images `0x400F8DAC(ctx, image, x, y, centred)`, 1-bit, 28 B header (+4 width, +8 height, +12 words per row, +16 pixels, +20 mask); icon sets are built from resources at boot (`0x444E….`), frame by value with `0x400F927C(set, value)`. The slot box is about x−1…x+18, y…y+16.

## 6. Audio processing

Everything runs in the audio interrupt (`0x400A3856`), once per 32-sample block (1 500 per second). The OS already uses ~89 % of the CPU at rest; the UI and the sequencer get the rest. **A few thousand instructions per block are enough to make the UI lag.** fx3 is the reference for adding an effect:

- **Where**: the mix function `0x4008F1CA`. Per-track loop `0x4008F21E` (track gains, sends, mute mask at `fp−508`); sends summed by OS routines with EMAC `msac` (result = −Σ g·x, keep that sign convention); delay call `0x4008F828`; master sums before `0x4008FB04`, after which the direct bus `0x8000DAD0` can still be modified. Sources: digital tracks `0x80003D50`, analog `0x80003950`, 128 B per channel.
- **Cost**: count instructions in the emulator (`UC_HOOK_CODE`; call `uc.ctl_flush_tb()` first or already-translated blocks are not counted) and keep a regression test (`tests/test_fx3.py::test_cost_per_block`).
- **Cheap by design**: do nothing when there is nothing to do (no sends, output not listened to, silent input and tail done); compute at 24 kHz where the sound allows it (average pairs in, linear interpolation out); sum only the tracks that send; write results straight into the OS bus instead of an extra pass; run hot loops in assembly; skip work at steady state (fx3's gain ramp only runs when a target changed — flagged by the per-track hook).
- **Smoothing that ends**: a ramp `c += (t − c) >> n` never reaches `t`; snap when close, or the effect never goes idle.
- **Bounded reads**: a modulated delay line read without wrap checks must limit how far the delay moves per block (fx3: 8 samples, a sudden TIME change glides).
- **Not idle time**: the DSPI wait at the start of the interrupt (`0x40102066`) is ~0 in practice (the transfer of the previous block is already over).

## 7. Testing on the device

- Keep a test build only when the emulator cannot answer (timing, analog parts). Measurements done so far: interrupt load with DTIM0 (`0xFC07000C`) at entry/exit; analog curves recorded through an audio interface (`tools/measure`).
- Check save/reload, pattern change and power cycle for anything stored in the kit.
