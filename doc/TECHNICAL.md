# Super Punch-Out!! Special Edition — Technical Reference

This document covers the full reverse-engineering and implementation details behind the patches described in [README.md](../README.md). It is intended for ROM hackers, the technically curious, and anyone who wants to continue this work.

**Reference:** all `CODE_*`, `DATA_*`, `UNK_*` labels and `%InsertGarbageData` regions referenced in this document follow the conventions of [**Yoshifanatic1's Super Punch-Out!! Disassembly**](https://github.com/Yoshifanatic1/Super-Punch-Out-Disassembly), which has been an invaluable reference throughout the development of this hack.

The recommended distribution is the bundled [`spo_special_edition_v2.0.ips`](../patches/spo_special_edition_v2.0.ips), which stacks every patch in this repo and stamps a correct SNES header checksum for the combined ROM. The two headline gameplay features are [`spo_versus_hack.ips`](../patches/standalone/spo_versus_hack.ips) — VERSUS MODE, letting either controller pick on the opponent-select screen — and [`spo_iron_circuit.ips`](../patches/standalone/spo_iron_circuit.ips) — the IRON CIRCUIT fifth circuit.

Two further patches live in the ROM's expansion region: [`spo_alt_opponents_colors.ips`](../patches/standalone/spo_alt_opponents_colors.ips) — per-opponent alternate palettes — and [`spo_msu1_v6.ips`](../patches/standalone/spo_msu1_v6.ips) — MSU-1 CD-quality audio (Kurrono's patch). All other patches are independent quality-of-life improvements that can be applied in any combination: `spo_disable_security_checksum.ips`, `spo_alt_glove_colors.ips`, `spo_profile_stats_fix.ips`, `spo_super_macho_man_fix.ips`, `spo_how_to_typo_fix.ips`, `spo_title_screen_special_ring.ips`, `spo_title_screen_special_logo.ips`, `spo_jp_charset_enabled.ips`, and `spo_end_credits.ips`.

**Compatibility guarantee:** the sub-2MB standalone patches in this repo are byte-disjoint with one another. Applied on top of an original `Super Punch-Out!! (USA).sfc` ROM, the combined result is identical to the bundled `spo_special_edition_v2.0.ips`. There are two intentional cross-patch overlaps, both resolved by apply order in the bundle builder ([`scripts/build_spo_se20_bundle.py`](../scripts/build_spo_se20_bundle.py)):

- **File `0x452AB` (`$08:D2AB`)** — `spo_super_macho_man_fix.ips` and `spo_iron_circuit.ips` both hook this per-fighter dispatch site. The bundle applies iron last so its hook wins; the macho-man fix's hook is restored at runtime via a chained-stub pattern (documented under `spo_super_macho_man_fix.ips`).
- **File `0x017E5` (`$00:97E5`)** — `spo_alt_opponents_colors.ips` re-hooks the fight-init palette load that `spo_alt_glove_colors.ips` also uses, chaining back to the glove trampoline so both run. Glove is applied first.

The two expansion-region patches (`spo_alt_opponents_colors.ips` and `spo_msu1_v6.ips`) share the ExLoROM window at file `0x200000+` but their data ranges are disjoint (MSU-1 driver `0x200000–0x20007D`; alt-opp stubs and palettes `0x20047E–0x200B7F`). Because each standalone IPS blankets the whole expansion window with zeros around its own data, the bundle builder applies both "sparse" — writing only their non-zero expansion bytes — then expands to 2.5MB and stamps the ExLoROM checksum once.

**Building the bundle:** [`scripts/build_spo_se20_bundle.py`](../scripts/build_spo_se20_bundle.py) reproduces `spo_special_edition_v2.0.ips` from a vanilla ROM:

```
python scripts/build_spo_se20_bundle.py <vanilla.sfc> [out.sfc]
```

It applies every standalone patch in the documented order, resolves the overlaps above, stamps the ExLoROM split+repeat checksum, and writes `patches/spo_special_edition_v2.0.ips`. The individual standalone patches are each reproduced by their own `scripts/build_spo_*.py` builder.

---

## Table of contents

1. [ROM structure](#1-rom-structure)
2. [The secret 2-player mode](#2-the-secret-2-player-mode)
3. [Title screen state machine](#3-title-screen-state-machine)
4. [Mode Select architecture](#4-mode-select-architecture)
5. [Versus Hack — patch-by-patch breakdown](#5-versus-hack--patch-by-patch-breakdown)
6. [Standalone patches — technical detail](#6-standalone-patches--technical-detail)
7. [Free space map](#7-free-space-map)
8. [Text encoding and screen descriptor system](#8-text-encoding-and-screen-descriptor-system)
9. [Key addresses quick reference](#9-key-addresses-quick-reference)
10. [Title screen BG layout quirk](#10-title-screen-bg-layout-quirk)

---

## 1. ROM structure

**Format:** LoROM (32 KB banks mapped at SNES $8000–$FFFF). The vanilla ROM is 2 MB.

**ExLoROM expansion (bundle):** `spo_alt_opponents_colors.ips` and `spo_msu1_v6.ips` expand the ROM to 2.5 MB and switch it to ExLoROM. This adds the SNES `$40:8000–$40:FFFF` bank (file `0x200000–0x207FFF`) and sets the makeup byte at file `0x7FD5` to `$32`. The header checksum then uses the ExLoROM split+repeat formula: the first 2 MB summed once plus the 0.5 MB expansion summed four times, `& 0xFFFF`. Patches that stay under 2 MB are unaffected and continue to compute the plain LoROM checksum on their own.

**File offset formula:**
```
file_offset = bank × 0x8000 + (SNES_addr − 0x8000)
```

Examples:
```
SNES $01:B194 → file 0x0B194
SNES $01:E16F → file 0x0E16F
SNES $0D:A3DA → file 0x6A3DA
SNES $0D:FA69 → file 0x6FA69
SNES $02:8408 → file 0x10408
SNES $40:847E → file 0x2047E  (ExLoROM expansion)
```

**Direct Page register** is set to `$0C00` by `CODE_01B0F0` at title-screen entry and maintained throughout. All DP-relative references (e.g. `$10`, `$11`, `$23`) resolve to WRAM `$0C10`, `$0C11`, `$0C23`, etc.

**Original ROM MD5:** `97fe7d7d2a1017f8480e60a365a373f0`

---

## 2. The secret 2-player mode

The game contains a dormant 2-player mode. The P2 boss-control flag lives at WRAM `$0030`; when it equals `$08`, Controller 2 drives the opponent. The code that sets this flag lives at SNES `$81:80CC`:

```asm
$81:80CC  LDA $0607      ; game mode flag
          CMP #$02       ; is this a VERSUS session?
          BNE +$10       ; skip if not
          ...
$81:80D4  BNE +$99       ; skip flag-set if button combo not held
$81:80D6  LDA #$08
          STA <$30       ; set P2 boss-control flag
          LDA #$80
          STA <$3D       ; set supplemental flag
```

The `BNE +$99` at `$81:80D4` (file `0x80D4`) nearly always branches past the flag-set because it guards against a specific button combination on the character-info screen. The Versus route in this hack bypasses the info screen entirely, so without a fix this code never runs and the CPU controls both fighters.

The Game Genie code `DD62-DF00` and GameShark code `180D5:00` both fix this by zeroing the branch offset at `$81:80D4`. This hack instead replaces the 12-byte block at `$01:80CA` (file `0x080CA`) — the entire `CMP #$02; BNE $806F; LDA $00AB; AND $00AF; BPL $806F` sequence — with a `JSL` to a dispatch stub at `$0D:FB99` plus a small BNE/JMP scaffold. The stub returns `A=0` when the P2-control flags should be set (and sets `$30=$08`, `$3D=$80` itself), or `A!=0` to skip. Two conditions trigger flag-set:

1. The VERSUS flag `$7E:1D74 == 1` (the path this hack uses for VERSUS mode entries).
2. The original `$0607=$02` + L+SELECT button-combo check (preserved verbatim so the secret pre-main-menu 2-player mode still triggers exactly when vanilla would).

The vanilla 2-player mode is reachable only via a hidden code path that runs *before* the main menu and routes through the secret menu's own pre-fight screen — it never fires on a normal Time Attack match. Time Attack therefore takes the "A!=0" path through our dispatch stub and behaves byte-for-byte vanilla at runtime.

**Discovery:** this mechanic was first publicly documented in 2022.

---

## 3. Title screen state machine

Entry point: `CODE_01B0F0` (file `0xB0F0`) — sets Direct Page = `$0C00`.

The machine dispatches on two nested state variables, `$01` and `$03`, via indexed indirect jump tables:

```
CODE_01B12D: LDX $01 → JMP (DATA_01B132, X)
  $01=0 → CODE_01B138: LDX $03 → JMP (DATA_01B13D, X)
    $03=$00 → CODE_01B14D   menu init
    $03=$0A → CODE_01B24C   menu interaction (cursor lives here)
    $03=$0C → CODE_01B389   circuit select
    $03=$0E → CODE_01B5C3   data clear
  $01=2 → CODE_01B8A3       post-confirm (new game / circuit entry)
  $01=4 → CODE_01BB61       Mode Select + Championship sub-machine
```

**Interactive menu loop** (`CODE_01DFB4`, state `$03=$0A`, sub-state `$05=2`): calls `CODE_01D8F7` for button input, then dispatches:

```
A-button → CODE_01E0A3
DPad     → CODE_01E123 → up/down/left/right handlers
Start    → CODE_01E005
```

**Cursor position encoding:** the cursor is a 16-bit word stored across DP+`$10` (X, lo byte) and DP+`$11` (Y, hi byte). The A-button handler reads `LDX $10` (16-bit) and compares it against known cursor values:

| Value  | Menu item      |
|--------|----------------|
| `$BF80`| NEW GAME       |
| `$BF90`| CONTINUE       |
| `$AFA0`| DATA CLEAR     |
| `$BFB0`| circuit select |

---

## 4. Mode Select architecture

### Design decision: duplicating Time Attack rather than using the secret VS menu

The game contains a dormant VS menu that is never reachable through normal play (`CODE_00B29C` and surrounding code). Routing Versus through it was considered and rejected for two reasons:

1. **Not part of the normal game loop.** The secret VS menu sits outside the state machine that governs the title screen and Mode Select. Entering it from Mode Select context causes a corrupt first frame because the VRAM state, CGRAM palette, and engine sub-states expected by that code are never set up by the normal flow. Recovering to a clean game loop after the match also proved unreliable through this path.

2. **The Time Attack path is clean and already correct.** The Time Attack opponent-select screen is a fully functional, menu-driven character picker that sits squarely inside the normal game-state machine. By duplicating its screen descriptor and routing Versus through the same state machine path, Versus gets a working opponent-select screen, clean back-out navigation, and a correct post-match return with no extra work.

The result is that Versus mode reuses the Time Attack infrastructure throughout. The VERSUS handler sets a new 1-byte WRAM flag at `$7E:1D74` and then enters the vanilla TA dispatch at `$01:C926`. The in-engine mode flag `$0607` ends up at `$01` (TA's value) for the entire VERSUS session — the fight engine runs unmodified TA code. A handful of hook points (header swap, table-hide, P2-mirrors-P1 input merge, P2-control dispatch, circuit-count override) gate on `$7E:1D74 == 1` to apply VERSUS-only behavior on top of the shared path. Time Attack itself runs byte-for-byte vanilla at runtime.

**Post-match behavior:** when a Versus match ends, the engine takes the vanilla TA post-match path, which returns the player to the opponent-select screen. The `$7E:1D74` flag persists across matches — successive matches stay on the VERSUS path until the player backs out, so rematches don't require re-selection from Mode Select. Pressing B on opponent-select clears the flag via the back-out stub at `$01:8463`, and the next TA entry behaves vanilla.

Reached via `$01=4`, `$03=2`. The sub-machine dispatches on `$05` via `DATA_01BC76`:

```
$05=0 → $BC82   init (sets disable flags, renders layout)
$05=4 → $BE8C   interactive input handler
$05=8 → $C905   confirm dispatch (maps cursor index → action)
```

### Layout system

Screen text is driven by a two-level table chain rooted at `DATA_0DA3DA` (file `0x6A3DA`). Entry 2 of that table is a bank-relative pointer to the Mode Select layout sub-table.

**Layout sub-table record format** (4 bytes each):
```
[text_idx][attr][WRAM_lo][WRAM_hi]
```
- `text_idx`: index into `DATA_0DA332` (text string pointer table)
- `attr`: `$1C` = selectable (highlight when cursor is on it), `$20` = always visible
- `WRAM lo/hi`: target address in the WRAM tilemap buffer

Terminator: `$00`.

**Tilemap address formula:**
```
WRAM_addr = $5000 + row × $40 + col × 2
```

### Cursor highlight system

Two independent systems — both must be consistent:

**System 1 — highlight renderer** (`CODE_01CC79`): loops `$14 + 1` times (where `$14` = item count − 1). For each item, reads the disable flag at DP+`$20+x`; if zero, renders the highlight tile at the current D0 position (advances by `$0100` per item). Purely visual.

**System 2 — interactive cursor** (`CODE_01DDD8` onward): tracks cursor position in DP+`$10`/`$11`, updates OAM sprite position, handles DPad input.

### Confirm dispatch — `CODE_01C905`

After the player confirms a selection, `$07E3` holds the 0-based cursor item index. `CODE_01C905` maps it to a state transition:

Original (4-item menu):
```
$07E3=0 → CHAMPIONSHIP  (STZ $03/$05; JMP $C752 → INC $01×2)
$07E3=1 → TIME ATTACK   (STA $0607=#$01; STZ $05; JMP $C74C → INC $03×2)
$07E3=2 → RECORDS VIEW  (LDA #$04; STA $03; BRA $C951)
$07E3=3 → BUTTON SETTINGS (LDA #$06; STA $03; BRA $C951)
```

Our patch inserts a JMP at `$C90E` to redirect all indices ≥ 1 through a 5-item stub in free space.

---

## 5. Versus Hack — patch-by-patch breakdown

All records are applied to the original unmodified ROM. Records are listed in file-offset order. Every patch in this repository includes a checksum record at file `0x7FDC` (4 bytes) that updates the SNES header so the patched ROM passes the hardware integrity check.

The hack uses a new 1-byte WRAM flag at **`$7E:1D74`** as its "this is a VERSUS session" indicator. The flag is set by the VERSUS handler at `$01:FFC9` before entering the Time Attack codepath, read by every VERSUS-specific stub, and cleared by the back-out stub at `$01:8463`. Match end intentionally does NOT clear the flag — successive matches stay on the VERSUS path until the player backs out.

---

### [1] File `0x008018` — Header swap thunk (4 bytes)

```
Old: 4C 18 80   JMP $8018   (self-referencing dead-loop)
New: 5C C9 FB 0D   JML $0D:FBC9
```

Lives in the 18-byte dead-loop region at `$01:8018–$01:8029` (three self-referencing JMPs at `$8018`/`$801B`/`$801E` plus 9 bytes of zero-fill). The thunk one-way JMLs into the bank-`$0D` header swap stub at `$0D:FBC9`. The header stub does the flag-check, optionally overrides A, and tail-JMLs to the descriptor renderer at `$01:D1FC` — preserving the JSR return chain that arrived via the redirect at `$01:BD0F` (record [10]).

**Why not put the whole stub here?** The full conditional stub is 19 bytes (`LDA.l $7E:1D74` is 4 bytes vs. the original VS hack's 3-byte `LDA $0607`). The 18-byte dead-loop zone is one byte short. Relocating the conditional logic to bank-`$0D` (where free space is plentiful) and leaving a 4-byte JML thunk in bank `$01` solves the size problem without disturbing the renderer's intra-bank JSR/RTS contract.

---

### [2] File `0x080CA` — P2 control hook (12 bytes)

```
Old: C9 02 D0 A1 AD AB 00 2D AF 00 10 99
New: 22 99 FB 0D D0 03 4C DE 80 4C 6F 80
```

Replaces the original `CMP #$02; BNE $806F; LDA $00AB; AND $00AF; BPL $806F` block at SNES `$81:80CA` with:

```asm
JSL $0D:FB99   ; P2 control dispatch stub (handles VERSUS + secret-combo cases)
BNE +3         ; A≠0 on return: skip to JMP $806F
JMP $80DE      ; flag was set → continue normally (past the original $30/$3D writes)
JMP $806F      ; not set → skip the P2-control block
```

The new dispatch stub at `$0D:FB99` itself sets `$30=$08` and `$3D=$80` when appropriate (the caller's `JMP $80DE` lands past those instructions). See record [15].

---

### [3] File `0x008457` — Trampoline 1: conditional TA disable (12 bytes)

```asm
D0 02        BNE +2     ; if $700010,X ≠ 0 (has progress): skip to RTS
E6 22        INC $22    ; no progress: disable TIME ATTACK
60           RTS
EA×7                    ; padding
```

Called via `JSR $8457` at `$01:BBE2` (record [8]). Ensures TIME ATTACK is only greyed out when there is no Championship progress. The `BNE +2` branches directly to RTS when progress exists, skipping the `INC $22`.

---

### [4] File `0x008463` — Back-out clear stub (7 bytes)

```asm
22 99 FD 0D   JSL $0D:FD99   ; → bank-$0D clear stub (zero $7E:1D74)
4C 66 C7      JMP $C766       ; continue to original epilog
```

When the player backs out of opponent-select, `BEEE: JMP $C766` is redirected here first (see record [9]). The stub calls into the bank-`$0D` clear stub to zero `$7E:1D74`, then tail-jumps to the original epilog target.

Lives in the same `%InsertGarbageData` zone as trampoline 1 (`$01:8457–$01:846A` is empty zero-fill in vanilla; the trampoline + back-out stub together consume 19 bytes from `$01:8457–$01:8469`, leaving the byte at `$01:846A` as the only `$00` survivor between our stubs and the start of `DATA_01840B` jump-table entry `$60` at `$01:846B`).

---

### [5] File `0x00BB93` — Item count: 4 → 5 (1 byte)

```
Old: 03   LDX #$0003
New: 04   LDX #$0004
```

At SNES `$01:BB93`, sets `$14 = 4` (5 items, 0-indexed) for the highlight-cursor loop.

---

### [6] File `0x00BB99` — Highlight base address (1 byte)

```
Old: 02   LDX #$024C   ($47 = $024C → D0 starts at $5000+$024C+2 = row 9)
New: 01   LDX #$014C   ($47 = $014C → D0 starts at row 5)
```

Shifts the cursor-highlight starting position up by 4 rows to match CHAMPIONSHIP's new position.

---

### [7] Files `0x00BBA3`, `0x00BBA7`, `0x00BBB3–BBB4` — Disable flag init (4 bytes)

Four in-place edits to the `LDX/STX` pairs that initialise items' `$20–$24` disable flags at menu init, for both the has-save and new-game paths. Net effect:

| Item | No progress | Has progress |
|---|---|---|
| CHAMPIONSHIP | enabled | enabled |
| VERSUS | enabled | enabled |
| TIME ATTACK | disabled | enabled |
| RECORDS VIEW | disabled | enabled |
| BUTTON SETTINGS | enabled | enabled |

---

### [8] File `0x00BBE2` — Progress gate rewrite (17 bytes)

Replaces the original conditional `INC`/`STZ` block (`$01:BBE2–BBF2`) with:

```asm
JSR $8457      ; trampoline 1
NOP
STZ $24        ; BUTTON SETTINGS always enabled
LDA $700010,X  ; SRAM Minor Championship progress flag
BEQ +3         ; no progress: skip STZ $23
STZ $23        ; RECORDS VIEW: enabled with progress
NOP : NOP : NOP
```

---

### [8b] Files `0x00BBC7`, `0x00BBD0`, `0x00BBD3` — Decoration tilemap + arrow positions for 5-item layout (6 bytes)

Three 2-byte adjustments to header decoration and arrow sprite positions to match the new 5-item layout (rows 5/9/13/17/21):

| File offset | Old | New | Effect |
|---|---|---|---|
| `0x00BBC7` | `14 59` | `54 58` | MENU/SELECT decoration tilemap addr `$5994` → `$5854` (visual row 2) |
| `0x00BBD0` | `10 01` | `50 00` | Left arrow position `$0110` → `$0050` |
| `0x00BBD3` | `2E 01` | `6E 00` | Right arrow position `$012E` → `$006E` |

---

### [9] File `0x00BC1D` — OAM cursor Y base (1 byte)

```
Old: 47   LDX #$472C ($53 = $47)
New: 27   LDX #$272C ($53 = $27)
```

OAM cursor Y formula: `Y = item_index × $20 + $53 + 1`. Adjusting `$53` from `$47` to `$27` shifts the cursor sprite 32 px up to align with CHAMPIONSHIP at its new row 5 position.

---

### [10] In-place hook redirects (10 bytes across 5 sites)

Five 2-byte JSR/JMP operand redirects and one 5-byte hook replacement, all pointing existing call sites at our stubs:

| File offset | SNES | Old → New | Purpose |
|---|---|---|---|
| `0x00BCAA+1` | `$01:BCAA` | `JSR $D641` → `JSR $FFD3` | Circuit-count read → trampoline 2 (record [12c]) |
| `0x00BD0F+1` | `$01:BD0F` | `JSR $D1FC` → `JSR $8018` | Renderer call → header thunk (record [1]) |
| `0x00BE7A+1` | `$01:BE7A` | `JSL $0E:F3DD` → `JSL $0D:FB62` | Init table-hide hook (record [16]) |
| `0x00BEC8` | `$01:BEC8` | `LDX #$000F; JSR $D7BC` (6B) → `JSL $00:FDD0 / NOP / NOP` (6B) | Char-switch table-hide hook (record [17]) |
| `0x00BECE` | `$01:BECE` | `JSR $D8F7; CMP #$09` (5B) → `JSL $0D:FC4C / NOP` (5B) | P2-mirrors-P1 hook (record [18]) |
| `0x00BEEF+1` | `$01:BEEF` | `JMP $C766` → `JMP $8463` | Opponent-select back-out → clear stub (record [4]) |
| `0x00C90E` | `$01:C90E` | `CMP #$01; BEQ ...` (3B) → `JMP $FFB0` (3B) | Mode Select confirm → dispatch stub (record [11]) |

---

### [11] File `0x00FFB0` — 5-item Mode Select dispatch stub (19 bytes, SNES `$01:FFB0`)

```asm
C9 01        CMP #$01
F0 15        BEQ +$15   ; → $FFC9 (VERSUS handler — record [12])
C9 02        CMP #$02
F0 0B        BEQ +$0B   ; → $FFC3 (TIME ATTACK trampoline — record [12a])
C9 03        CMP #$03
F0 0A        BEQ +$0A   ; → $FFC6 (RECORDS VIEW trampoline — record [12b])
A9 06        LDA #$06    ; BUTTON SETTINGS fall-through
85 03        STA $03
4C 51 C9     JMP $C951   ; → STZ $05/$07; PLB; RTL
```

Reached from the JMP at `$01:C90E` (record [10]). The trampolines and handlers that follow at `$FFC3` are packed contiguously immediately after.

---

### [12a] File `0x00FFC3` — TIME ATTACK + RECORDS VIEW trampolines (6 bytes)

```asm
; $FFC3 — TIME ATTACK:
4C 26 C9     JMP $C926   ; STA $0607=#$01; STZ $05; JMP $C74C
; $FFC6 — RECORDS VIEW:
4C 30 C9     JMP $C930   ; LDA #$04; STA $03; BRA $C951
```

---

### [12] File `0x00FFC9` — VERSUS handler (10 bytes, SNES `$01:FFC9`)

```asm
A9 01            LDA #$01
8F 74 1D 7E      STA.l $7E:1D74   ; raise VERSUS flag
4C 26 C9         JMP $C926        ; enter vanilla TA dispatch
EA               NOP              ; padding so trampoline 2 stays aligned at $FFD3
```

The VERSUS handler reached by `BEQ +$15` from the dispatch stub at `$FFB0`. Sets the VS flag at `$7E:1D74`, then enters the vanilla TIME ATTACK dispatch at `$C926` — the engine runs unmodified TA code with `$0607=$01` for the rest of the session. All VERSUS-specific behavior is layered on top via the stubs that gate on `$7E:1D74`.

---

### [12c] File `0x00FFD3` — Trampoline 2: conditional circuit count (14 bytes, SNES `$01:FFD3`)

```asm
AF 74 1D 7E   LDA.l $7E:1D74
C9 01         CMP #$01
F0 03         BEQ +3     ; if VERSUS: skip to LDA #$04
4C 41 D6      JMP $D641  ; else: tail-call SRAM circuit-count reader
A9 04         LDA #$04   ; VERSUS: force 4 circuits (all characters always available)
60            RTS
```

Reached via the `JSR $FFD3` redirect at `$01:BCAA` (record [10]). On VERSUS opponent-select the trampoline returns 4 (all circuits selectable regardless of save state); on Time Attack it tail-calls the original `JSR $D641` SRAM reader so progress-gating works normally.

Occupies `$FFD3–$FFE0` (14 B). One byte longer than the equivalent in the original VS hack because the long-absolute read of `$7E:1D74` is 4 bytes (vs. 3 for the original direct-page `$0607` read). The extension consumes 1 of the 4 previously-free bytes at `$01:FFE0–$FFE3`.

---

### [13] Files `0x06A38C`, `0x06A3A0`, `0x06A3DE`, `0x06A47E` — Text/descriptor pointer redirects (8 bytes)

Four 2-byte pointer redirects in the `DATA_0DA332` (text string) and `DATA_0DA3DA` (screen descriptor) tables:

| File offset | Pointer | Old → New | Repurpose |
|---|---|---|---|
| `0x06A38C` | DA332[`$2D`] | (prototype name garbage) → `$FB03` | "PLAYER 2" tile data (record [14c]) |
| `0x06A3A0` | DA332[`$37`] | `$ACB5` (unused game text) → `$FAC3` | "VERSUS" tile data (record [14b]) |
| `0x06A3DE` | DA3DA entry 2 | `$AD6A` → `$FA86` | New Mode Select layout (record [14a]) |
| `0x06A47E` | DA3DA byte-offset `$A4` | `$5188` (unused garbage) → `$FACA` | VERSUS opponent-select descriptor (record [14d]) |

---

### [14a] File `0x06FA86` — New Mode Select layout sub-table (61 bytes)

```
0D 1C 4E 51   CHAMPIONSHIP  row 5  col 7   ($514E)
0C 1C 6A 51   MODE          row 5  col 21  ($516A)
37 1C 54 52   VERSUS        row 9  col 10  ($5254)
0C 1C 64 52   MODE          row 9  col 18  ($5264)
0F 1C 50 53   TIME          row 13 col 8   ($5350)
12 1C 5A 53   ATTACK        row 13 col 13  ($535A)
0C 1C 68 53   MODE          row 13 col 20  ($5368)
10 1C 4E 54   RECORDS       row 17 col 7   ($544E)
0E 1C 5E 54   VIEW          row 17 col 15  ($545E)
0C 1C 6A 54   MODE          row 17 col 21  ($546A)
11 1C 4C 55   BUTTON        row 21 col 6   ($554C)
13 1C 5A 55   SETTING       row 21 col 13  ($555A)
0C 1C 6C 55   MODE          row 21 col 22  ($556C)
0C 20 54 58   MODE          header row     ($5854)
05 20 5C 58   <<SELECT      header row     ($585C)
00            terminator
```

15 records × 4 bytes + 1 terminator = 61 bytes.

---

### [14b] File `0x06FAC3` — "VERSUS" tile data (7 bytes)

```
06 1F 0E 1B 1C 1E 1C
```

Format: `[length][tile…]`. Length = 6. Tiles: V=`1F`, E=`0E`, R=`1B`, S=`1C`, U=`1E`, S=`1C`.

---

### [14d] File `0x06FACA` — 12-record VERSUS opponent-select descriptor (49 bytes)

Full descriptor for the VERSUS opponent-select screen. Contains all four circuit rows (Special, World, Major, Minor), the VERSUS MODE header at row 2, and the `< PLAYER 2 SELECT >` row.

Key records:
```
0A 1C 84 53   SPECIAL   row 14 col 2   ($5384)
0B 1C 94 53   CIRCUIT   row 14 col 10  ($5394)
37 0C 94 50   VERSUS    row 2  col 10  ($5094)
0C 0C A2 50   MODE      row 2  col 17  ($50A2)
05 20 60 59   <<SELECT  row 37 col 16  ($5960)
2D 20 50 59   PLAYER 2  row 37 col 8   ($5950)
00            terminator
```

---

### [14c] File `0x06FB03` — "PLAYER 2" tile data (9 bytes)

```
08 19 15 0A 22 0E 1B EF 02
```

Length = 8. Tiles: P=`19`, L=`15`, A=`0A`, Y=`22`, E=`0E`, R=`1B`, space=`EF`, 2=`02`. Tile `EF` is the correct space glyph in this font (not `64`, which renders as a Japanese character).

---

### [15] File `0x06FB99` — P2 control dispatch stub (48 bytes, SNES `$0D:FB99`)

```asm
;-- VERSUS path: check $7E:1D74 --
AF 74 1D 7E      LDA.l $7E:1D74
C9 01            CMP #$01
D0 0B            BNE vanilla_path  ; → offset +11
;-- VERSUS branch: set P2-control flags --
A9 08 85 30      LDA #$08; STA $30   ; P2 boss-control flag
A9 80 85 3D      LDA #$80; STA $3D   ; supplemental flag
A9 00 6B         LDA #$00; RTL       ; A=0 → caller continues to JMP $80DE
;-- vanilla_path: reproduce original $0607=$02 + button-combo check --
AD 07 06         LDA $0607
C9 02            CMP #$02
D0 13            BNE not_combo       ; → not_combo
AD AB 00         LDA $00AB
2D AF 00         AND $00AF
10 0B            BPL not_combo       ; combo not held
;-- secret-combo branch: set P2-control flags --
A9 08 85 30      LDA #$08; STA $30
A9 80 85 3D      LDA #$80; STA $3D
A9 00 6B         LDA #$00; RTL       ; A=0
;-- not_combo --
A9 01 6B         LDA #$01; RTL       ; A!=0 → caller skips P2-control block
```

Called via `JSL $0D:FB99` from the hook at `$01:80CA` (record [2]). When `$7E:1D74=1` (VERSUS), sets `$30=$08`/`$3D=$80` unconditionally — Controller 2 always controls the opponent. Otherwise reproduces the original `$0607=$02` + L+SELECT button-combo check verbatim, so the hidden 2-player mode (reachable only via the secret pre-main-menu path) still triggers exactly when vanilla would. The return-value convention (A=0 = flag set, A≠0 = not set) lets the caller at `$01:80CA` branch on BNE.

The stub MUST set `$30/$3D` itself — the caller's `A=0` branch is `JMP $80DE`, which lands PAST the original `LDA #$08; STA $30; LDA #$80; STA $3D` block at `$01:80D6–$80DD`. Returning A=0 without writing the flags would crash the engine in TA mode.

---

### [16] File `0x06FB62` — Init table-hide stub (55 bytes, SNES `$0D:FB62`)

The opponent-select screen normally shows a BEST TIME / YOUR BEST score table. On VERSUS that table is meaningless. This stub and record [17] blank a 30×7 tile rectangle on BG1 and BG3 when `$7E:1D74 == 1`. Time Attack renders the score table normally.

```asm
22 DD F3 0E      JSL $0E:F3DD       ; preserved original work
AF 74 1D 7E      LDA.l $7E:1D74     ; gate
C9 01            CMP #$01
D0 2A            BNE skip_to_RTL    ; not VERSUS → exit
08               PHP
C2 30            REP #$30           ; 16-bit M/X/Y
A2 82 54         LDX #$5482         ; BG1 row 18 col 1
A9 07 00         LDA #$0007         ; row counter (7)
48               PHA
row_loop:
  A0 1E 00         LDY #$001E       ; 30 cells per row
  A9 00 00         LDA #$0000       ; empty tile
  inner:
    9F 00 00 7E      STA.l $7E0000,x   ; BG1
    9F 00 08 7E      STA.l $7E0800,x   ; BG3 (BG1 + $0800)
    E8 E8 88         INX, INX, DEY
    D0 F3            BNE inner
  8A 18 69 04 00 AA  TXA, CLC, ADC #$0004, TAX  ; advance to next row
  68 3A 48           PLA, DEC, PHA
  D0 E2              BNE row_loop
68 28            PLA, PLP
6B               RTL
```

Blanks a 30-col × 7-row rectangle (cols 1-30, rows 18-24) on both BG1 and BG3 by writing `$0000` (tile 0, palette 0 — universally transparent). BG3 tilemap is at WRAM `$5800-$5FFF`, exactly `$0800` above BG1 at `$5000`, so a single inner loop writes both layers without extra arithmetic.

Body is byte-identical to the equivalent stub in the original VS hack except the 7-byte gate has been replaced with an 8-byte `LDA.l $7E:1D74 / CMP #$01 / BNE` sequence. The `BNE +42` offset is unchanged because both the branch site and the target (the final RTL byte) shift by the same +1 position.

---

### [17] File `0x07DD0` — Char-switch table-hide stub (72 bytes, SNES `$00:FDD0`)

Lives in **bank `$00`** (`UNK_00F5D0` zone) rather than bank `$0D`, because no single contiguous free run in the VS-hack-vacated bank-`$0D` zones is large enough to hold this stub alongside the 217-byte P2-mirrors-P1 stub (record [18]). The stub body is bank-position-independent (only relative branches plus one `LDA.l $01:D7D2,x`), so relocation is mechanical — only the JSL operand in the hook (record [10]) changes.

```asm
08               PHP
E2 30            SEP #$30          ; 8-bit (D7BC body expects this)
A2 0F            LDX #$0F          ; (replicates the LDX #$000F we removed)
A0 08            LDY #$08
d7bc_loop:
  BF D2 D7 01      LDA.l $01:D7D2,x   ; cross-bank read of bank-$01 lookup table
  99 87 03         STA.w $0387,y
  CA 88            DEX, DEY
  D0 F5            BNE d7bc_loop
A9 80 8D 7D 03   LDA #$80, STA $037D
8D 87 03         STA $0387
AF 74 1D 7E      LDA.l $7E:1D74    ; gate
C9 01            CMP #$01
D0 24            BNE skip_to_PLP_RTL
C2 30            REP #$30          ; 16-bit
A2 82 5C         LDX #$5C82        ; BG3 row 18 col 1
A9 07 00         LDA #$0007
48               PHA
row_loop:
  A0 1E 00         LDY #$001E
  A9 00 00         LDA #$0000
  inner:
    9F 00 00 7E      STA.l $7E0000,x   ; BG3 only (X already at BG3 base)
    E8 E8 88         INX, INX, DEY
    D0 F7            BNE inner
  8A 18 69 04 00 AA  TXA, CLC, ADC #$0004, TAX
  68 3A 48           PLA, DEC, PHA
  D0 E6              BNE row_loop
68               PLA
28 6B            PLP, RTL
```

Inlines `CODE_01D7BC`'s body (DMA list setup at `$0387` — needed every char-switch in both modes), then conditionally blanks BG3 only when `$7E:1D74 == 1`. BG1 doesn't need re-blanking because the char-switch render path doesn't touch it. The `LDA.l $01:D7D2,x` long-indexed read accesses the bank-`$01` lookup table directly, avoiding the need for a bank-`$01` trampoline.

---

### [18] File `0x06FC4C` — P2-mirrors-P1 merge + poll stub (217 bytes, SNES `$0D:FC4C`)

On VERSUS opponent-select only, Controller 2's D-pad / A / Start are merged into Controller 1's pressed-this-frame globals before the menu's input dispatch reads them — so either player can navigate and confirm. Gated on `$7E:1D74 == 1`, so the merge is skipped on Time Attack opponent-select (which shares the same runloop). Back-out clears the flag, so the feature deactivates automatically.

```asm
;-- gate on VERSUS opponent-select --
AF 74 1D 7E      LDA.l $7E:1D74
C9 01            CMP #$01
F0 08            BEQ do_merge
9C A6 00         STZ $00A6        ; not VERSUS: clear P2 prev-held shadow
9C A7 00         STZ $00A7
80 45            BRA poll

;-- P2 lo-byte edge detect: A button = bit 7 --
do_merge:
AD A4 00         LDA $00A4        ; P2 held lo
48               PHA
4D A6 00         EOR $00A6        ; ^ prev
2D A4 00         AND $00A4        ; & cur → newly-pressed lo
29 80            AND #$80
F0 08            BEQ skip_A
A9 80            LDA #$80
0D 95 00         ORA $0095
8D 95 00         STA $0095        ; mark P1 A as pressed-this-frame
skip_A:
68               PLA
8D A6 00         STA $00A6        ; update shadow lo

;-- P2 hi-byte edge detect: Start = bit 4, DPad = bits 3..0 --
AD A5 00         LDA $00A5        ; P2 held hi
48               PHA
4D A7 00         EOR $00A7
2D A5 00         AND $00A5        ; → newly-pressed hi
AA               TAX              ; save in X
29 10            AND #$10
F0 08            BEQ skip_Start
A9 80            LDA #$80
0D A1 00         ORA $00A1
8D A1 00         STA $00A1        ; mark P1 Start as pressed-this-frame
skip_Start:
8A               TXA
29 0F            AND #$0F
F0 0B            BEQ skip_DPad
8D 92 00         STA $0092        ; direction nibble
A9 80            LDA #$80
0D 93 00         ORA $0093
8D 93 00         STA $0093        ; mark P1 DPad as pressed-this-frame
skip_DPad:
68               PLA
8D A7 00         STA $00A7        ; update shadow hi

;-- poll: PEA + JMP into a verbatim copy of $01:D8F7's body --
poll:
F4 21 FD         PEA #$FD21       ; fake intra-bank return = post_poll - 1
4C A7 FC         JMP $FCA7        ; into D8F7-clone block
;-- bytes $FCA7..$FD21: byte-for-byte copy of $01:D8F7 (122 bytes; LDX #0,
;--   then nine `LDA $00xx; BMI handler` pairs, an `LDA #0; RTS` early-out,
;--   nine `AND #$7F; STA; BRA tail` handlers, and an `INX×9; TXA; RTS` tail)
;-- after RTS: returns to $FD22 below --

;-- post_poll: re-issue displaced CMP and return --
C9 09            CMP #$09         ; restore caller's flag-set
6B               RTL
```

**Why inline `D8F7` instead of calling it:** the body at `$01:D8F7` ends in `RTS` (intra-bank return). Calling it from bank `$0D` via `JSL` would return to bank `$0D` correctly (`RTL` semantics) — but `D8F7` doesn't end in `RTL`. Calling it via `JML` with a faked far-return on the stack also fails because `RTS` is intra-bank: it would resume in whatever bank `JML` arrived in (bank `$01`), and bank `$01` has no free space for the post-poll completion code. The cleanest solution is to copy `D8F7`'s 122-byte body verbatim into bank `$0D` (it's bank-position-independent — every read/write uses absolute mode against `$0090–$00A3` with DBR=$00) and invoke it via `PEA + JMP` so its `RTS` lands inside the stub. The `CMP #$09` after `RTS` reproduces the displaced opcode so the caller's `BEQ $BEFC` branches off the correct flag.

**P2 pressed-this-frame derivation:** the original game does not compute "P2 newly-pressed" anywhere — only P1 has dedicated globals (`$0092/$0093/$0095/$00A1`). The stub synthesizes it via `held XOR prev_held AND held`, using two unused WRAM bytes (`$00A6`/`$00A7`) as the prev-held shadow. When `$7E:1D74 ≠ 1` the shadow is zeroed so the next entry to VERSUS opponent-select starts fresh.

**Locality of the feature:** every other entry path to the opponent-select runloop leaves `$7E:1D74` clear (TA dispatches `JMP $C926` directly without setting the flag; the VERSUS handler at `$01:FFC9` is the only writer). Back-out clears it via record [4]. The CMP/BEQ gate is sufficient to scope the merge to VERSUS only.

---

### [19] File `0x06FBC9` — Header swap stub (21 bytes, SNES `$0D:FBC9`)

Called via `JML $0D:FBC9` from the bank-`$01` thunk at `$01:8018` (record [1]). The thunk was reached via `JSR $8018` from `$01:BD0F` (record [10]), so a 16-bit return address is on the stack.

```asm
48               PHA              ; save caller's A (the descriptor index $0C/$0E)
AF 74 1D 7E      LDA.l $7E:1D74
C9 01            CMP #$01
F0 05            BEQ versus_branch
68               PLA              ; non-VERSUS: restore A
5C FC D1 01      JML $01:D1FC     ; tail-call descriptor renderer

versus_branch:
68               PLA              ; balance stack
A9 A4            LDA #$A4         ; override descriptor index to VERSUS descriptor
5C FC D1 01      JML $01:D1FC     ; tail-call renderer
```

The JML chain preserves the original `JSR $8018`'s 16-bit return: the thunk's JML adds nothing to the stack, this stub PHA/PLA balances itself, and the final JML to `$D1FC` leaves the JSR return intact so the renderer's `RTS` returns through the original `JSR $BD0F` call site cleanly.

**Critical note (preserved from the original design):** PLA on SNES updates the N and Z processor flags from the pulled value — not from the preceding CMP. The BEQ must come before PLA on the non-VERSUS path, or it always sees Z=0. This version routes both paths through their own PLA so the BEQ is safely BEFORE the PLA in each path.

---

### [20] File `0x06FD99` — Back-out clear stub (7 bytes, SNES `$0D:FD99`)

```asm
A9 00            LDA #$00
8F 74 1D 7E      STA.l $7E:1D74
6B               RTL
```

Called via `JSL $0D:FD99` from the bank-`$01` back-out clear stub at `$01:8463` (record [4]). Zeroes the VERSUS flag so subsequent TA matches behave vanilla.

---

## 6. Standalone patches — technical detail

Each standalone patch has a companion doc in `doc/standalone/` that includes the patch records, byte-for-byte effect descriptions, free-space inventory, compatibility notes, and a **patch in asm form** section with the full assembler overlay. This section documents the deeper technical context (rationale, data-structure background, layout reasoning, etc.); the standalone docs are the right place for machine-readable asm.

Standalone doc links: [VERSUS_HACK](standalone/VERSUS_HACK.md) · [IRON_CIRCUIT](standalone/IRON_CIRCUIT.md) · [ALT_GLOVE_COLORS](standalone/ALT_GLOVE_COLORS.md) · [PROFILE_STATS_FIX](standalone/PROFILE_STATS_FIX.md) · [SUPER_MACHO_MAN_FIX](standalone/SUPER_MACHO_MAN_FIX.md) · [HOW_TO_TYPO_FIX](standalone/HOW_TO_TYPO_FIX.md) · [TITLE_SCREEN_SPECIAL_RING](standalone/TITLE_SCREEN_SPECIAL_RING.md) · [TITLE_SCREEN_SPECIAL_LOGO](standalone/TITLE_SCREEN_SPECIAL_LOGO.md) · [JP_CHARSET_ENABLED](standalone/JP_CHARSET_ENABLED.md) · [CREDITS](standalone/END_CREDITS.md) · [DISABLE_SECURITY_CHECKSUM](standalone/DISABLE_SECURITY_CHECKSUM.md)

### [`spo_alt_glove_colors.ips`](../patches/standalone/spo_alt_glove_colors.ips)

**What it does:** Adds a runtime glove-color selector. Each opponent has a circuit-default color (Minor=vanilla green, Major=blue, World=red, Special=yellow, Iron=white, mirroring the per-circuit glove tones in Punch-Out!! Wii); the player can override via L (blue), R (red), X (yellow), Y (vanilla green), or L+R (white) held during the pre-fight transition. The override applies only to the current match — the next fight reseeds. All player-glove animation states render in the chosen mode's hue: rest, the powered-up cycling animation, the knock-out-punch / rapid-punch frames, the portrait HUD (rest + both powered-up frames), the BG-tile renders for the victory pose / knockdown / get-up animations, and the player sprite on the ending credits screen.

The full byte-level breakdown (hook sites, stub assembly, color tables) lives in the standalone doc [doc/standalone/ALT_GLOVE_COLORS.md](standalone/ALT_GLOVE_COLORS.md). This section covers the deeper technical context: *why* this is a runtime patch instead of a ROM-data patch, the glove animation state machine, and the cross-bank-RTS trap the portrait hooks had to navigate.

**Why runtime, not ROM-data:** patching `Layer1_Contender.bin` directly produces the right rest color but bleeds into the post-match BEST TIME background (which reuses parts of the contender palette region) and corrupts opponent palettes (since the per-fighter palette tables overlap the same WRAM range). The runtime approach leaves all ROM palette data intact and writes per-mode colors directly into WRAM at fight init, scoped to the WRAM slots actually read by player-only animations.

**Glove animation state machine:** the player's gloves render through *two* systems with five distinct WRAM sources:

| State | Render system | WRAM target | Driven by |
|---|---|---|---|
| Rest gloves | sprite OAM palette 0 c12-c15 | `$7E:0518-$051F` | written by Hook 1 trampoline at fight init (MVN 1) |
| Powered-up (cycling charged-up) | sprite OAM palette 0 c12-c15 (same slot) | `$7E:0518-$051F` | engine snapshots rest, writes powered-up colors during animation, restores rest after — `CODE_00DD43` writer is hooked to use a per-mode lookup |
| Knock-out-punch / rapid-punch | sprite OAM palette 3 c12-c15 | `$7E:0578-$057F` | `CODE_00DDAA` writer hooked for per-mode lookup; Hook 1 also pre-writes the chosen color into `$0578-$057F` (MVN 3) so the engine's snapshot/restore preserves it across attacks |
| Portrait HUD (rest + 2 powered-up frames) | sprite OAM palette 1 c12-c13 | `$7E:0538/$053A` | `CODE_00EC6E` is called from 4 sites; each is hooked, and the stubs frame-detect via the c12 word the engine just wrote |
| Victory pose / knockdown / get-up | BG layer 1 with BG palette 2 c12-c15 | `$7E:0458-$045F` | written by Hook 1 trampoline at fight init (MVN 2) |
| Ending credits screen (final stats / "THE END") | sprite OAM palette 4 c12-c15 | `$7E:0580-$058F` | Static ROM patch at file `0x05DF` (`DATA_008547` palette 4 c12-c15) — no runtime hook needed |

**The contender DMA + knock-out-punch snapshot/restore interaction:** at fight init, a DMA at `$00:97DF` copies `Layer1_Contender.bin` bytes into WRAM `$0540-$057F`. Bytes 56-63 of that file are vanilla glove green and land at `$0578-$057F` (sprite OAM palette 3 c12-c15). The engine's knock-out-punch state uses a snapshot/restore mechanism (`CODE_00DE01` snapshots `$0578-$057E` to DP `$22-$28` before attack frames; `CODE_00DDCC` restores after). Without intervention the snapshot captures vanilla green, the DDAA hook briefly writes our per-mode color during the attack, then the restore puts vanilla green back over our color — a visible green flash right after every knock-out-punch.

The fix is the third MVN in Hook 1: at fight init the trampoline overwrites `$0578-$057F` with the chosen mode's color *before* the engine ever runs the snapshot. The snapshot then captures our color, and the restore preserves it across attacks.

**Hook point: `$00:97E5`** (file `0x017E5`) — universal fight-init, inside `CODE_009762`. The original 6 bytes there (`A2 00 00 A0 E0 3E` = `LDX #$0000; LDY #$3EE0`) are replaced with `JSL $0D:FDD2 + 2×NOP`; the trampoline re-emits the displaced LDX/LDY before RTL. Note that `CODE_00913B` (which also does an MVN from bank `$08` to WRAM `$0540`) is **not** the universal fight-init — its only caller is gated by a P1+P2 button mask and reaches it only via the secret 2-player VS path.

Memory environment at the hook: DBR=`$0D` (set by upstream `LDA #DATA_0D8010>>16; PHA; PLB`), DP=`$2100` (from upstream `LDX #!REGISTER_ScreenDisplayRegister; PHX; PLD`), X is 16-bit, A is 8-bit. All WRAM access uses long addressing (`LDA.l`/`STA.l`) — direct-page would target PPU registers (`$2100+offset`) and absolute would target bank-`$0D` ROM.

**The cross-bank-RTS trap (portrait hooks):** `CODE_00EC6E` ends with intra-bank `RTS`, not `RTL`. JSL'ing it directly from bank `$0D` corrupts both the stack (RTS pops 2, JSL pushed 3) and PBR — RTS doesn't restore PBR, so the CPU resumes at `$00:<our_offset>` instead of `$0D:<our_offset>` after the call. The fix is a 5-byte trampoline at `$00:F5D0` (`JSR EC6E + RTL`): the sep-variant portrait stubs `JSL` the trampoline, the trampoline does an intra-bank `JSR` (RTS-balanced), then `RTL`s back to bank `$0D` cleanly.

The rts-variant portrait hook (site `$00:EC69`, originally `JSR EC6E + RTS`) has a different stack scenario: the original `RTS` was meant to return to a bank-`$00` caller of `CODE_00EC87`. The replacement stub lives in bank `$00` (`UNK_00F5D0+5`) so its closing RTS runs with PBR=`$00` and pops the bank-`$00` caller's return cleanly. The stub does `JSR EC6E` directly (intra-bank, balanced), runs the per-mode fixup, then `PLA PLA PLA` to drop our own JSL frame (PCL/PCH/PBR) before falling through to `RTS`.

**Per-frame portrait detection:** `CODE_00EC6E` reads from one of 11 source tables (`DATA_00ED03..DATA_00EDF3` for 9 brightness levels of rest, plus `DATA_00EE11` for blink frame A and `DATA_00EE2F` for blink frame B). The portrait stubs detect which frame the engine just loaded by re-reading `$7E:0538` after EC6E returns:

| `$0538` value | Frame | Frame offset into portrait table |
|---|---|---|
| `$0D4A` | blink A (powered-up frame 1) | 16 |
| `$14B1` | blink B (powered-up frame 2) | 32 |
| anything else | rest | 0 |

Then `table_offset = frame_offset + (mode-1)*4` indexes into the 48-byte portrait table at `$00:FDA0` (3 frames × 4 modes × 4 bytes per entry, c12 word + c13 word).

**Mode flag at WRAM `$7E:1D70`:** placed in high low-RAM rather than direct-page low-RAM because the fight engine clobbers `$00A8` and adjacent low-RAM addresses during gameplay via direct-page accesses (DP=`$0000` collides with absolute `$00A8`). `$7E:1D70` is untouched by direct-page activity in the fight loop. Reseeded by Hook 1 every fight init — there is no persistent state across matches, so no back-out clear hook is needed.

**Free space consumed:**
- Bank `$0D`: 459 bytes used within `$0D:FDAA-$0D:FFCE`. Inside the disassembly's `%InsertGarbageData($0DFA69, ...)` zone.
- Bank `$00`: 74 bytes at `$00:F5D0-$00:F619`. Inside the disassembly's `UNK_00F5D0` `%InsertGarbageData` zone.
- File `0x05DF` (SNES `$00:85DF`): 8 bytes — `DATA_008547` (ColorEndScreen.bin) palette 4 c12-c15. In-place edit, no free space consumed.

For the full asm overlay and per-mode color tables, see [doc/standalone/ALT_GLOVE_COLORS.md](standalone/ALT_GLOVE_COLORS.md).

---

### [`spo_iron_circuit.ips`](../patches/standalone/spo_iron_circuit.ips)

**What it does:** Adds a fifth circuit, **IRON CIRCUIT**, to Championship Mode → Circuit Select. A 16-opponent gauntlet that runs every fighter in opponent order from Gabby Jay through Nick Bruiser without HP recovery between fights. Player stamina and a cumulative knockdown count carry across every match; the run ends in TKO when the cumulative KD count reaches 3. The patch also makes the SPECIAL CIRCUIT slot always render on the Championship Mode and Time Attack circuit-select screens (with vanilla disabled-until-unlocked rendering preserved) so the new 5-row layout is consistent regardless of save state.

The full byte-level breakdown — hook sites, stub assembly, free-space layout, WRAM/SRAM map — lives in the standalone doc [doc/standalone/IRON_CIRCUIT.md](standalone/IRON_CIRCUIT.md). This section covers the deeper technical context: *why* iron's design hijacks Special Circuit's identity, the architecture of the 16-opponent chain, and the championship-belt screen flag-passing pattern.

#### Why iron hijacks `$0601 = $03` (Special Circuit)

The vanilla circuit-themed asset loads (BG, ring, palette, announcer, pre-fight title text, score-tally circuit name, etc.) all key off `$0601` (the circuit number, 0..3). Rather than introduce a new circuit ID and patch every downstream lookup, iron's confirm hook writes `$0601 = $03` (Special) on iron entry. Every asset load then naturally inherits Special's data, with three flag-gated overrides on top:

- **BG2 palette** at `$00:9C18` — substitutes a deep-red (rust) palette for Special's purple, giving iron a distinct look on pre-fight + BEST TIME screens.
- **Pre-fight title** at `$08:D19D` — substitutes a runtime-staged `IRON⋆CIRCUIT` letter-byte string for Special's `SPECIAL⋆CIRCUIT`. The shared `⋆CIRCUIT` suffix re-renders unmodified.
- **Score-tally circuit name** at `$01:9EEC` — substitutes a new IRON descriptor at `$0D:FA69` for the engine's per-circuit name lookup so the post-match score line reads `IRON CIRCUIT TOTAL`.

The actual opponent index is `$0600`, kept independent of the circuit identity. Iron's confirm hook resets `$0600 = 0` (Gabby Jay) on iron entry; POST_MATCH at `$00:B250` drives the 16-opp chain by replicating the engine's natural `INC $0600` and gating chain advance on `$0600 < $10`.

#### 16-opponent chain architecture

The vanilla post-fight flow at `$00:B231` decrements `$0602` (the remaining-fights counter, initialized to 3 for a 4-fight circuit) and jumps to either the next-fight handler or the circuit-complete handler depending on whether `$0602` reached zero. Iron replaces this with a single hook at `$00:B250` (POST_MATCH override) that:

1. Replicates the eaten `DEC $0602`.
2. On non-iron, JMLs to the original `$00:88B1` (next-fight target).
3. On iron with `$0600 < $10`, writes `$0602 = $0600 EOR $0F`, then JMLs to `$00:88B1`. The EOR encoding makes `$0602 == 0` only when post-INC `$0600 == $0F` (i.e. transitioning into fight 16) — that fires the engine's `CODE_00D6C5` celebration animation gate during the win sequence, so Nick Bruiser gets the same jump-180-arm-raise as every other circuit's final boss.
4. On iron with `$0600 >= $10`, clears the iron flag and JMLs to credits via the championship-belt screen handler.

The EOR encoding is mandatory for byte-budget reasons — the v19 stub region is hardcoded to 320 bytes, and a naive `CMP/BEQ/LDA/BRA/LDA/STA` encoding overflows that budget. The `EOR #$0F ; STA $0602` form is 5 bytes vs. 13.

#### Championship belt screen — secondary flag pattern

The iron-complete path needs a championship-belt screen with iron-themed presentation (rust BG, steel-blue belt, `IRON CIRCUIT CLEAR` title, opponent records suppressed, `16 Wins {N} Loss` W/L line). Multiple sub-hooks inside `CODE_00BEE8` and `CODE_08BFBC` need to know "this is the iron belt screen" — but the iron flag `$7E:1D71` has already been cleared by the iron-complete path before the belt screen runs (so the belt-screen sub-hooks would see `$7E:1D71 = 0` and take the vanilla path).

The pattern: a separate **iron belt-screen flag** at `$7E:1D72` (with `$7E:1D73` for M=16 read alignment) is set by CHAMP_SCREEN immediately before `JSR $BEE8` and cleared after. All belt-screen sub-hooks (BF81 palette, CHAMP_TITLE, TEXT_SKIP, W/L digit override) check `$7E:1D72` instead of the iron flag. A defensive `B231_INIT` hook at `$00:B231` clears both bytes on every post-fight (all circuits) so cold-boot WRAM `$FF` doesn't trigger iron rendering on vanilla circuits.

#### SRAM persistence

Iron W/L data is stored at `$700FE8 + slot` (primary) and `$701FE8 + slot` (backup), 1 byte per slot, 8 slots. These addresses sit past the engine's per-slot record table (`$700100..$700F7F`, 30 records × `$80` stride) and outside the engine's checksum sweep (`CODE_01ACFB` only sweeps `$700004..$700100` per outer iteration). The dual-write covers the rare `CODE_01ACCA` corruption-recovery path, which `MVN`s `$701000..$701FFF` over `$700000..$700FFF` and would clobber primary if backup didn't match.

Encoding is offset-by-1 with `$00` reserved for "never completed":

| Encoded value | Meaning |
|---|---|
| `$00` | Never completed (matches both fresh battery SRAM and post-ALL-CLEAR zeroed SRAM — no init code required) |
| `$01` | 16-0 (perfect) |
| `$02` | 16-1 |
| `$03` | 16-2 |

Only runs with 2 or fewer losses are saved. A run that ends via a 3rd cumulative KD does not update the record. The Circuit Select W/L line renders only when the encoded byte is non-zero.

**Clearing iron records on profile delete.** ALL CLEAR (the title-screen DATA CLEAR option) zeros the entire SRAM, so iron data is wiped automatically. Per-profile FILE KILL is different: the engine's slot-delete routine (`CODE_01B736`) only zeros the slot record at `$700100 + slot*$80`, leaving the iron W/L bytes at `$700FE8 + slot` intact. A 4-byte hook at `$01:B7D6` (replaces the `LDA.l $700005` immediately following the slot's `STA.l $700006,X`) calls a small bank-`$01` stub that zeros both `$700FE8,X` (primary) and `$701FE8,X` (backup), then replicates the eaten instruction. X already holds the slot index from the engine's earlier `TAX`. ALL CLEAR uses a different routine (`CODE_01ABAD`) and is unaffected.

For the full asm overlay, hook table, and stub map, see [doc/standalone/IRON_CIRCUIT.md](standalone/IRON_CIRCUIT.md).

---

### [`spo_profile_stats_fix.ips`](../patches/standalone/spo_profile_stats_fix.ips)

**What it does:** Corrects Mr. Sandman's profile screen (wrong stats copied from Super Macho Man) and Mad Clown's profile screen (weight listed as 390 lbs instead of 370 lbs).

After patching:
- Mr. Sandman: age 30, weight 270 lbs, record 28-4 (correct JP values, also confirmed in the game's manual)
- Mad Clown: weight 370 lbs

**Problem 1 — Sandman:** Mr. Sandman's profile data at file `0x42CD1` is a copy of Super Macho Man's record (`$08AC89`). A copy-paste error in the original source.

**Problem 2 — Mad Clown:** Mad Clown's weight at file `0x42CA5` is `0x19` ("9"), giving "390 lbs". The correct value is `0x17` ("7"), giving "370 lbs".

**Data format:** `[country][0A][age 2 digits][0A][weight 2 digits][0A][record][00]`
Font encoding: digits `0–9` = `$10–$19`, dash = `$F4`. Weight is stored as 2 digits; the renderer appends a literal "0" ("27" → "270 lbs").

**Sandman fix:** 10 bytes at file `0x42CD8`:
```
Old: 12 18 0A 12 13 0A 12 19 F4 13   ("28", "23", "29-3" — Macho's stats)
New: 13 10 0A 12 17 0A 12 18 F4 14   ("30", "27", "28-4" — correct JP values)
```

**Mad Clown fix:** 1 byte at file `0x42CA5`:
```
Old: 19   (digit "9" → 390 lbs)
New: 17   (digit "7" → 370 lbs)
```

---

### [`spo_super_macho_man_fix.ips`](../patches/standalone/spo_super_macho_man_fix.ips)

**What it does:** Fixes the original ROM's "SUPER MACHOMAN" → "SUPER MACHO MAN" typo across every screen in the game (Mode Select, opponent select, time-attack title card, Personal Records, BEST TIME table, pre-fight profile). The corrected spelling matches the US manual and every other appearance of the character — Punch-Out!! (1987, NES) and Punch-Out!! (2009, Wii).

**Background:** Super Macho Man is the only fighter whose two-word surname is collapsed in the original ROM — every other two-word boss name (MAD CLOWN, ARAN RYAN, BOB CHARLIE, etc.) is correctly spaced. The on-ROM "MACHOMAN" is a deliberate typo that ships in every region.

**Why Nintendo shipped the typo:** the layout system literally cannot fit "SUPER MACHO MAN" with the correct spacing on the pre-fight profile screen. That screen renders a header line of the form `<RANK> <FIGHTER NAME>` in a custom double-height font (1 column wide × 2 rows tall per letter). For champion fighters, `<RANK>` is `CHAMP.`, and the renderer auto-centers the whole line based on its visible length:

| Fighter         | Rank prefix | Total chars |
|---|---|---|
| MR. SANDMAN     | `CHAMP.`    | 6 + 1 + 10 = 17 |
| ARAN RYAN       | `CHAMP.`    | 6 + 1 + 9 = 16 |
| MAD CLOWN       | `CHAMP.`    | 6 + 1 + 9 = 16 |
| HEIKE KAGERO    | `CHAMP.`    | 6 + 1 + 12 = 19 |
| **SUPER MACHOMAN** (original) | `CHAMP.`    | 6 + 1 + 14 = **21** |
| **SUPER MACHO MAN** (corrected) | `CHAMP.`    | 6 + 1 + 15 = **22** |
| NICK BRUISER    | `CHAMP.`    | 6 + 1 + 12 = 19 |

The available horizontal layout slot is exactly 21 columns. With the correct "SUPER MACHO MAN" (15 chars), the line is 22 columns wide and overflows by one tile. Nintendo most likely solved this by collapsing "MACHO MAN" into "MACHOMAN" — exactly fitting the slot — and shipped that everywhere for consistency. This is the single hardest constraint in the patch.

**Why it took more than a one-byte string edit:** the boss name is rendered by **two different code paths** with different fonts and layouts, and extending the string from 14 → 15 chars overflows fixed layout slots on three of the four screen types. The fix combines a string redirect, three descriptor column tweaks, a banner-table redirect with a new entry in free space, and a per-fighter code patch so Macho Man's profile-screen portrait shifts +4 pixels right (giving the longer name room to fit) without affecting any other fighter's portrait.

**Two boss-name systems, two fonts:**

| System | Font | Used by | Source |
|---|---|---|---|
| Menu-font (1 tile per char) | A=`$0A`, …, Z=`$23`, space=`$FF` (column-skip), `$EF`=`<` glyph | Mode Select, opponent-select, TA title card, Personal Records | DA332 entry `$30` (`$0D:AC85`) |
| Banner-font (1 col × 2 rows per char) | A=`$45`, B=`$46`, …, M=`$61`, S=`$67`, space=`$EF` (real tile, not a skip) | BEST TIME table, pre-fight profile screen | Per-fighter table at `$08:BB3D` |

(Note: `$FF` is the menu-font's column-skip sentinel and is the correct space tile for menu-font strings — the renderer at `CODE_01D24D` advances the tilemap pointer without writing, leaving the previously-cleared BG tile visible. `$EF` in the menu font is a real tile — the literal `<` glyph (used by the original `<<SELECT` header). The new menu-font MACHO MAN string at `$0D:FD69` uses `$FF` for the inter-word space; the banner-font entry at `$08:D926` uses `$EF` because the banner renderer treats `$EF` as a real space tile, not a skip.)

**Banner-font letter map** (top tile values; bottom-half tile is always top + `$10`):

| Letter | Tile | Letter | Tile |
|---|---|---|---|
| A | `$45` | M | `$61` |
| B | `$46` | N | `$62` |
| C | `$47` | O | `$63` |
| D | `$48` | P | `$64` |
| E | `$49` | R | `$66` |
| H | `$4C` | S | `$67` |
| I | `$4D` | T | `$68` |
| K | `$4F` | U | `$69` |
| L | `$60` | W | `$6B` |
| (space) | `$EF` | Y | `$6D` |

**The four screens:**

| # | Screen | Font | Source data |
|---|---|---|---|
| 1 | Mode Select / opponent-select / time-attack title card | menu | DA332 index `$30` |
| 2 | Personal Records (PR) | menu | DA332 index `$30`, drawn via descriptor at `$0D:AE91` |
| 3 | Opponent-select / TA two-line title (large) | menu | DA332 index `$30`, drawn via descriptor at `$0D:AF71` |
| 4 | BEST TIME table + pre-fight profile screen | banner | Per-fighter table at `$08:BB3D` |

Screens 1–3 share the same DA332 string entry, so they're all fixed by a single redirect (plus column tweaks for the layouts that don't fit the longer string). Screen 4 uses a completely separate data structure with its own font encoding and rendering routine, requiring a banner-table redirect plus a per-fighter code patch.

**Patch records:**

| File offset | Bytes | Effect |
|---|---|---|
| `0x06A392` | `69 FD` | DA332 entry `$30` redirect → `$0D:FD69` (new "MACHO MAN" string) |
| `0x06FD69` | 10 B | New length-prefixed string `09 16 0A 0C 11 18 FF 16 0A 17` ("MACHO MAN" with `$FF` space) |
| `0x06AE8F` | `04` | PR descriptor: SUPER WRAM-lo `$5C06`→`$5C04` (col 3 → col 2) |
| `0x06AE93` | `10` | PR descriptor: MACHO MAN WRAM-lo `$5C12`→`$5C10` (col 9 → col 8) |
| `0x06AF73` | `28` | TA title card: MACHO MAN WRAM-lo `$542A`→`$5428` (col 21 → col 20) |
| `0x043B53` | `26 D9` | Banner-table pointer for fighter idx 11 → `$08:D926` |
| `0x045926` | 19 B | New banner entry: prefix `00 00 00`, name `S U P E R [space] M A C H O [space] M A N`, terminator |
| `0x0452AB` | 5 B | Hook in profile renderer: replace `LDX #$38A8; STX $7A` with `JSL $0D:FD87; NOP` |
| `0x06FD87` | 18 B | Per-fighter portrait X-shift stub at `$0D:FD87` |

**Per-fighter portrait stub (`$0D:FD87`):** the profile-screen renderer loads the portrait sprite's base position as a packed 16-bit `$38A8` (Y=`$38`, X=`$A8`) and stores it to `$7A`. Replacing that with a JSL to a stub lets us conditionally load `$38AC` (X+4 = half a tile column right) for fighter index 11 only. The 4-pixel shift creates room on the left side of Macho Man's portrait so the wider "CHAMP. SUPER MACHO MAN" line fits without overflowing the layout slot — every other fighter's portrait stays at its original position.

```asm
A5 00            LDA $00         ; fighter index
C9 0B            CMP #$0B        ; Macho Man?
F0 06            BEQ macho
A2 A8 38         LDX #$38A8      ; default Y/X
86 7A            STX $7A
6B               RTL
macho:
A2 AC 38         LDX #$38AC      ; Macho: +4 px right
86 7A            STX $7A
6B               RTL
```

**Why the PR descriptor needs both `$2F` and `$30` shifted (not just `$30`):** the original layout placed SUPER (5 chars) at col 3 and MACHOMAN (8 chars) at col 9, with a 1-column gap at col 8 — the rendered text ends exactly at col 16, the right edge of the layout slot. Naively shifting only the new 9-char "MACHO MAN" to col 8 fits within col 16 but eats the inter-word gap (the M of MACHO now sits at col 8), rendering as "SUPERMACHO MAN". Shifting both records left by one (SUPER c3→c2, MACHO MAN c9→c8) preserves the gap at col 7 and keeps the line centered cleanly within cols 2–16.

**Banner-table entry format** (`$08:BB3D` is a 16-pointer table; each entry has a 3-byte prefix):

```
[byte[0]: BEST-TIME / PR X-offset]
[byte[1]: profile-screen X-offset]
[byte[2]: post-CHAMP gap (in tile columns × 2)]
[name tile bytes... (banner-font encoding)]
[$00 terminator]
```

byte[0] is added (×2) to the X-base for the BEST TIME / PR renderer at `CODE_08D4AF` — lower = farther left. The new entry uses byte[0] = `$00` (vs the original `$01` for MACHOMAN), which anchors the now-15-char name 1 column further left to fit. PISTON HURRICANE (the only original 16-char name) also uses byte[0] = `$00`, confirming the convention.

**Why the portrait shift (rather than a text shift) on the profile screen:** the pre-fight profile renderer (`CODE_08D162`) reads byte[1] of the prefix and computes an X-base of `$61C2 + 2 × byte[1]` for the whole `<RANK> <FIGHTER NAME>` line, then draws the rank prefix (5 cols wide), advances X by 10 + `2 × byte[2]`, and finally draws the name. byte[1] and byte[2] are both already at their minimum value `$00` for our entry, and there's no banner-data byte that can shift only the name without also moving CHAMP. Shifting `$61C2` directly would move the whole line — including CHAMP. Instead, shifting the **portrait sprite** 4 pixels right (which has pixel-level granularity since it's OAM) creates room on the layout's left side for the wider name, leaving CHAMP. anchored at its original column. The corrected name fits without overflowing.

**Cosmetic side effect:** the portrait has a separate drop-shadow (drawn by code we never identified) that doesn't follow the +4 px shift, so on Macho Man's profile screen the portrait and its shadow are slightly offset. The mismatch is 4 pixels and only visible by side-by-side comparison with other fighters' profiles — accepted as a minor trade-off.

**Free-space allocations:** 19 B in bank `$08` at `$08:D926` (inside the disassembly's `%InsertGarbageData($08D926, ...)` zone — dead development-time data, never referenced at runtime), 10 B in bank `$0D` at `$0D:FD69` (new menu-font string), and 18 B in bank `$0D` at `$0D:FD87` (portrait stub). All inside disassembly-documented `%InsertGarbageData` regions — verified by ROM-wide JSL/JML/JSR/JMP search to be unreferenced.

---

### [`spo_how_to_typo_fix.ips`](../patches/standalone/spo_how_to_typo_fix.ips)

**What it does:** Fixes a single-letter typo in the in-game tutorial demo (the HOW-TO-PLAY attract sequence). The UPPERCUT lesson string in the original ROM reads *"Knock Out Punches can be highly **devestating**!"* — corrected to **devastating**.

**Data location:** the tutorial demo's text strings live in `DATA_08B83E` (SNES `$08:B83E`, file `0x4383E`) and use a custom run-length-style font encoding where each byte after a `$8X` length prefix is a single character tile index. The relevant 12-character segment encodes `devestating!`:

```
8C 1C 0A 3C 0A 24 08 10 08 1E 06 20 16
   d  e  v  e  s  t  a  t  i  n  g  !
```

`$8C` is the run length (12 chars); the bytes that follow are the per-character tile indices. In this encoding `e = $0A` and `a = $10`. The fix patches the 4th character byte from `$0A` (`e`) to `$10` (`a`).

**Patch record:** 1 byte at file `0x43876`:
```
Old: 0A   ('e')
New: 10   ('a')
```

---

### [`spo_title_screen_special_ring.ips`](../patches/standalone/spo_title_screen_special_ring.ips)

**What it does:** Replaces the title-screen ring logo and background color palette with the Special Circuit variants. The SUPER PUNCH-OUT!! logo is unchanged; only the ring artwork and colors behind and around it are swapped. All in-game circuit screens are unaffected — only the title screen is altered.

Redirects two sites in the title-screen frame handler `CODE_008EE4`:

| File offset | Old | New | Effect |
|---|---|---|---|
| `0x0F25` | `02` | `08` | `LDX #$8002` → `LDX #$8008` — loads Special Circuit ring logo GFX instead of Minor Circuit |
| `0x0F68–0F6A` | `AE 18 80` | `A2 B6 99` | `LDX DATA_088000+$18` → `LDX #$99B6` — reads Special Circuit palette directly instead of via the pointer table, leaving the table entry (and all in-game Minor Circuit references) unchanged |

Bank `$0E` header table: `+$00` = MainMenu font, `+$02` = MinorCircuit, `+$04` = MajorCircuit, `+$06` = WorldCircuit, `+$08` = SpecialCircuit.

---

### [`spo_title_screen_special_logo.ips`](../patches/standalone/spo_title_screen_special_logo.ips)

**What it does:** Writes the text **SPECIAL EDITION** into the title screen's BG3 tilemap buffer at row 12, cols 6–22 (with a one-tile gap between SPECIAL and EDITION), using the standard menu font (palette 2, priority 1). Rendered every time the title screen BG init routine runs.

**Hook** (6 bytes at file `0x44906`, SNES `$08:C906`):

```
Old: A0 01 18  8C 00 43   LDY.w #$1801 / STY.w $4300
New: 22 DF FB 0D  EA EA   JSL $0D:FBDF / NOP / NOP
```

This is the 6 bytes immediately after the last `JSL CODE_08C433` call in `CODE_08C8AB` (the title screen BG init routine). The two displaced instructions are re-executed at the top of the stub.

**Stub** (109 bytes at `$0D:FBDF`, file `0x6FBDF`):

```asm
A0 01 18        LDY.w #$1801        ; displaced instr 1
8C 00 43        STY.w $4300         ; displaced instr 2
C2 20           REP #$20            ; 16-bit A
A9 1C 28        LDA.w #$281C        ; S  → WRAM $530C
8F 0C 53 7E     STA.l $7E530C
...             (13 more LDA/STA pairs for P,E,C,I,A,L,_,E,D,I,T,I,O,N)
A9 17 28        LDA.w #$2817        ; N  → WRAM $532A
8F 2A 53 7E     STA.l $7E532A
E2 20           SEP #$20            ; restore 8-bit A
6B              RTL
```

Tile entry format: `$28XX` = priority 1, palette 2, tile index XX. Font encoding: A–Z = `$0A–$23`. The space between words (col 13 = WRAM `$531A`) is left unwritten — the background fill tile at that position acts as the gap.

**BG3 tilemap address formula (title screen):**

```
WRAM = $5000 + row × 64 + col × 2
```

The `$5000` block is DMA'd to VRAM `$4C00` by `CODE_08C8AB`. Despite `BG3SC` (`$2109`) being set to `$59` (→ VRAM `$5800`) elsewhere in the title screen init, empirically the `$5000` block (→ VRAM `$4C00`) is the buffer that renders as BG3 and carries the menu font. Writing to the `$6000` block (→ VRAM `$5800`) lands on BG1 instead. The static register assignment in the disassembly (`$59` at file `0x43FD9`) does not fully describe the runtime BG assignment — see [section 10](#10-title-screen-bg-layout-quirk).

**Free space consumed:** `$0D:FBDF–$0D:FC4B` (109 bytes). Does not conflict with any other patch.

---

### [`spo_jp_charset_enabled.ips`](../patches/standalone/spo_jp_charset_enabled.ips)

**What it does:** Makes L/R cycling between three character sets (Japanese-1, Japanese-2, Western) always active in name entry, with no button combo required. The screen opens on the Western set by default, so players who don't want Japanese characters don't need to do anything differently. L and R cycle through all three sets as they do in the Japanese version.

The name-entry screen has a hidden mode where L/R cycles between three character sets (Japanese-1, Japanese-2, Western). Activated by holding X+A or Start+X+A at the New Game cursor. The JP version has it on by default.

Three single-byte changes at SNES `$01:DF83`/`$DF92`/`$DF95` (file `0xDF83–0xDF95`):

| File offset | Old | New | Effect |
|---|---|---|---|
| `0xDF83` | `F0` (BEQ) | `80` (BRA) | Always take the Japanese-mode-enabled branch |
| `0xDF92` | `9C` | `B7` | `JSR $D79C` → `JSR $D7B7` — load full Western UI tiles instead of just swapping the Japanese set (avoids corrupted tilemap on US ROM where Japanese-set UI tiles aren't pre-loaded) |
| `0xDF95` | `00` | `02` | Initial `$1F = $02` (Western set index, matching the `$D7B7` load) |

---

### [`spo_end_credits.ips`](../patches/standalone/spo_end_credits.ips)

**What it does:** Adds a fourth `CREDITS` entry to the **Records View select screen** (the screen that asks which circuit's records to view) and tightens the layout so the four entries sit at rows 10/14/18/22 with the header at row 2 — matching the Championship circuit-select layout. Selecting `CREDITS` launches the game's ending-cutscene credits roll. After the credits finish the game stays on the final screen and requires reset; that is the original cutscene's terminal behavior, not introduced by this patch.

Also folds in a **no-record artifact fix**: when the credits roll launches before all 16 opponents are beaten, fighters with no record would display a Japanese glyph tile in the `YOUR BEST` time slot. See the full breakdown below.

**Final on-screen layout:**

| Row | Element | Layer |
|---|---|---|
| 2 | RECORDS VIEW MODE | Layer 1 |
| 6 | `<` ITEM SELECT `>` | Layer 2 |
| 10 | BEST TIME | Layer 1 |
| 14 | BEST SCORE | Layer 1 |
| 18 | PERSONAL RECORDS | Layer 1 |
| 22 | CREDITS | Layer 1 |

**Records View screen architecture:**

The select screen's init at `CODE_01BFA2` (file `0x0BFA2`) runs a sequence of operations that *each* hardcode WRAM addresses paired to specific tile rows. Moving any element requires updating all of its paired hardcoded references in lockstep. The five coupled positions are:

| Init offset | Hardcoded value | Paired with |
|---|---|---|
| `0x0BFAB` (`$47`) | `$0310` | first entry row (highlight bar base) |
| `0x0BFDB` (`CBA8` X) | `$5A14` | subheader Layer 2 row (palette-cycle range) |
| `0x0BFE9` (`CB57` X) | `$00CE` | "RECORDS VIEW MODE" header row (palette cycle) |
| `0x0BFF2`/`0x0BFF5` (`D70C` X/Y) | `$0210`/`$022E` | subheader row (`<`/`>` brackets) |
| `0x0C022` (`$53` cursor anchor Y) | `$5F` | first entry row (cursor sprite scan start) |

**Why the cursor anchor is the load-bearing one — the `D082` scan loop:**

`CB57` (the palette-cycler called with `X=$0000, Y=$0200`) reads each tilemap entry, and for the empty-fill value `$0064` produces:

- `$00EF` written to the same position
- `$00FF` written to row+1 (shadow row)

Those are exactly the two sentinel values that `CODE_01D082` (the cursor's auto-snap-to-text scan) skips. After init the cursor sprite is positioned by:

1. Setting sprite Y to `$53 + 1` (`$5F + 1 = $60` = pixel row 12).
2. Calling `CAAE`, which loops calling `D082` — converts sprite (X,Y) to tilemap offset via `Y*8 + X/4`, reads the tile, advances X by 8 px and re-tries if the tile is `$EF`/`$FF`, exits when it finds real text.

If `BEST TIME` is anywhere other than row 12, the scan finds only the CB57-transformed `$EF`/`$FF` sentinels at row 12 and **loops forever** — the audio CPU keeps running (music plays) but the main CPU is stuck. The fix is to shift `$53` (file `0x0C022`) in lockstep with the first entry's row.

**Patch records:**

| File offset | Bytes | Effect |
|---|---|---|
| `0x0BFA6` | `03` | `$14=3` (4-item highlight loop, was 3) |
| `0x0BFAB` | `90 02` | `$47=$0290` highlight bar base (row 12 → row 10) |
| `0x0BFDB` | `94 59` | `CBA8` palette-cycle base `$5A14` → `$5994` (subhdr row 8 → 6) |
| `0x0BFE9` | `8E` | second `CB57` X arg `$00CE` → `$008E` (cycle row 2, not row 3) |
| `0x0BFF2` | `90 01` | arrow renderer X `$0210` → `$0190` (`<` row 8 → 6) |
| `0x0BFF5` | `AE 01` | arrow renderer Y `$022E` → `$01AE` (`>` row 8 → 6) |
| `0x0C022` | `4F` | cursor sprite anchor Y `$5F` → `$4F` (scan starts at row 10) |
| `0x0C9CA` | `5C 39 FB 0D` | `JML $0D:FB39` — replaces start of `CODE_01C9CA`, bypasses original 3-way dispatch |
| `0x6A3EC` | `0C FB` | `DA3DA[$12]` redirect to `$0D:FB0C` (replaces ptr to `$AE3F`) |
| `0x6A47A` | `31 FB` | `DA332[$A4]` redirect to `$0D:FB31` (CREDITS tile string) |
| `0x6AE62` | `8E` | descriptor `$14` RECORDS WRAM lo `$50CE` → `$508E` (row 3 → 2) |
| `0x6AE66` | `9E` | descriptor `$14` VIEW WRAM lo `$50DE` → `$509E` |
| `0x6AE6A` | `AC` | descriptor `$14` MODE WRAM lo `$50EC` → `$50AC` |
| `0x6FB0C` | 37 B | new screen descriptor (9 records + terminator) |
| `0x6FB31` | 8 B | "CREDITS" tile string (`07 0C 1B 0E 0D 12 1D 1C`) |
| `0x6FB39` | 41 B | A-button dispatch stub |

**New layout sub-table (`$0D:FB0C`, 37 bytes):**

```
1A 20 94 59   ITEM             Layer 2 row 6  col 10  ($5994)
05 20 9C 59     SELECT         Layer 2 row 6  col 14  ($599C)
1B 34 96 52   BEST             Layer 1 row 10 col 11  ($5296)
0F 34 A0 52   TIME             Layer 1 row 10 col 16  ($52A0)
1B 1C 96 53   BEST             Layer 1 row 14 col 11  ($5396)
1D 1C A0 53   SCORE            Layer 1 row 14 col 16  ($53A0)
1C 34 90 54   PERSONAL         Layer 1 row 18 col 8   ($5490)
10 34 A2 54   RECORDS          Layer 1 row 18 col 17  ($54A2)
A4 1C 98 55   CREDITS          Layer 1 row 22 col 12  ($5598)
00            terminator
```

The text-index `$A4` (`DA332[$A4]`) is repurposed: in the original ROM it pointed to garbage at `$B0A7` that is never used as menu text.

**A-button dispatch stub (`$0D:FB39`, 41 bytes):**

The original `CODE_01C9CA` is the confirm dispatcher for state `$05=0`, `$07=8` on this screen. It advances `$05` by 2/4/6 based on `$07E6` (cursor index 0/1/2) to enter the score-display state for Minor/Major/World circuits. Index 3 (CREDITS) is not handled by the original code — it falls through to index 2's path. The stub replaces that dispatch wholesale by JMLing into bank `$0D` from the very first byte of `C9CA`, implementing all four cases plus the original `$44 != 0` short-circuit:

```asm
A5 44              LDA $44
D0 21              BNE +$21         ; → JML $01:C94F (the $44 ≠ 0 path)
AD E6 07           LDA $07E6
F0 10              BEQ +$10         ; → index 0 INC pair
C9 01              CMP #$01
F0 08              BEQ +$08         ; → index 1 INC pair
C9 03              CMP #$03
F0 10              BEQ +$10         ; → index 3 JML
E6 05  E6 05       INC $05 ×2       ; index 2 fall-through (3 INC pairs total)
E6 05  E6 05       INC $05 ×2       ; index 1 enters here  (2 INC pairs total)
E6 05  E6 05       INC $05 ×2       ; index 0 enters here  (1 INC pair total)
64 07              STZ $07
AB                 PLB
6B                 RTL
5C 9C B2 00        JML $00:B29C     ; index 3: ending-cutscene credits roll
5C 4F C9 01        JML $01:C94F     ; $44 ≠ 0 path
```

**Free space consumed:** `$0D:FB0C–$0D:FB61` (86 bytes) and `$01:FEC2–$01:FED3` (18 bytes).

**No-record artifact — root cause and fix:**

The credits roll animation engine in bank `$01` runs a per-frame state machine (`CODE_01DA7C`). On each frame, state-index 1 dispatches to `CODE_01DAC4`, which redraws the `YOUR BEST` time tile block for the current fighter onto BG3. The key section:

```asm
CODE_01DAC4:
    JSR CODE_01DB4C        ; blank tilemap region
    ...
    LDA.w $0608            ; fighter SRAM slot index (signed)
    BPL CODE_01DB21        ; >= 0: fighter has a record path
    ; else: no-record hardcoded tile path
    LDA #$03
    STA.l $7E40B0          ; hardcoded tile for the leading slot
    ...
    BRA CODE_01DB2A

CODE_01DB21:               ; "has record" path
    LDX #$40B0
    STX $00DA              ; destination base = $7E40B0
    JSR CODE_01D52B        ; read SRAM, write digit tiles to $7E40B0+
```

`CODE_01D52B` computes a fighter-specific SRAM offset (`$0600` × 5), reads 5 consecutive bytes from SRAM bank `$70`, and writes them as digit tiles to `$7E40B0` onward:

```asm
CODE_01D558:
    ...
    LDA.l $700006,x        ; SRAM byte at offset+6 → $7E40B0
    LDX $00DA
    STA.l $7E0000,x        ; = STA.l $7E40B0  ← artifact slot
```

`$7E40B0` is in BG3's per-frame tilemap buffer; a per-frame DMA copies `$7E4000–$7E47FF` to VRAM `$7000`. VRAM `$7058` = WRAM `$7E40B0` (offset `$B0` / 2 = word `$58`). The credits font maps tile `$FF` to a Japanese glyph.

**Why the BPL is always taken via our menu path:** `$0608` is initialized to `$00` by `CODE_00913B` (called during credits init at `CODE_00B2A3`) and is never updated per-fighter when launching via our `JML $00:B29C` path. `$0608 = 0` (non-negative) means BPL is always taken — so `CODE_01D52B` runs for every fighter, including unbeaten ones whose SRAM is uninitialized (`$FF`).

**Fix:** replace the 3-byte `JSR CODE_01D52B` at `$01:DB27` (file `0x0DB27`) with `JSR $FEC2`. The 18-byte stub at `$01:FEC2` (file `0x0FEC2`, in the 206-byte garbage zone `UNK_01D722`):

```asm
20 2B D5        JSR CODE_01D52B   ; call original — writes SRAM data to $7E40B0
AF B0 40 7E     LDA.l $7E40B0     ; read the written tile
C9 FF           CMP #$FF          ; is it the bad glyph?
D0 06           BNE +6            ; no: leave it, go to RTS
A9 03           LDA #$03          ; yes: tile $03 = digit "3" - Nintendo's own no-record placeholder, leading digit of 3'00"00 (full round duration)
8F B0 40 7E     STA.l $7E40B0     ; overwrite
60              RTS               ; return to CODE_01DB2A epilog
```

Uses `LDA.l` / `STA.l` (24-bit addressing) so DBR is irrelevant. The check fires once per fighter per frame but the condition is only true for unbeaten fighters — beaten fighters' SRAM holds valid digit tiles (`$00`–`$09`), never `$FF`.

**Why `$01:FEC2`:** the 206-byte block at `$01:FEC2–$01:FF8F` is labeled `UNK_01D722` in the disassembly (a copy of `$00:FEC2`, never executed at runtime — confirmed by ROM-wide JSR/JMP/BRA search). It is the largest free zone in bank `$01` and sits entirely before the interrupt-vector table at `$01:FF90`.

### [`spo_score_overflow_fix.ips`](../patches/standalone/spo_score_overflow_fix.ips)

**What it does:** Caps the running score at **999,990** so the 6-digit on-screen total can never overflow. Without it, a circuit total exceeding 999,990 silently wraps to a low number (e.g. 1,014,000 → 14,000) because the score-tally BCD adder drops the carry out of the top digit. Full write-up: [SCORE_OVERFLOW_FIX.md](standalone/SCORE_OVERFLOW_FIX.md).

**The single BCD adder — `CODE_01AA55` (`$01:AA55`):** the ONLY multi-digit BCD add routine in the ROM. It adds a 6-digit source into a 6-digit destination one decimal digit per byte (score buffer `$0610`–`$0615`, `$0610` = ones) and silently drops the carry out of the 6th digit. Every score path — per-match bonus tally and the end-of-circuit high-score screen — funnels through it, so a single hook caps them all. 999,990 (not 999,999) is the cap because every point award is a multiple of 10, so the ones digit is structurally always 0.

**Hook:** the adder's loop tail at `$01:AA7F` (file `0x0AA7F`) is `D0 DA 60` (`BNE $AA5B ; RTS`). Replace with `4C 55 FF` (`JMP $FF55`). The 39-byte stub at `$01:FF55` reproduces the loop-back, then on loop exit checks the carry-out of the last digit; if set (overflow), it clamps the six destination bytes to 999,990 (write `$09` to `dest+5..dest+1`, `$00` to `dest+0`). The destination base is recovered from `$00D2` (points to `dest_end` after the loop). Because the hook is at the shared adder, the score-tally tween also animates toward an already-capped buffer.

**Free space:** 39 B at `$01:FF55–$01:FF7B`, inside `UNK_01D722` (see the bank-`$01` map). No other free space used; the hook is a 3-byte in-place edit.

### [`spo_alt_opponents_colors.ips`](../patches/standalone/spo_alt_opponents_colors.ips)

Gives every opponent an alternate palette — recolored body sprite, small portrait, and large pre-fight portrait — plus a unified circuit backdrop. The palettes turn on automatically during an IRON CIRCUIT run, or can be toggled per-fight with the SELECT button. This is the first patch in the repo to use the ExLoROM expansion bank.

**ExLoROM layout (bank `$40`):** the patch expands the ROM to 2.5 MB (see §1) and places its palette tables and most of its stubs in the new `$40` bank:

| SNES address | File offset | Contents |
|---|---|---|
| `$40:847E` | `0x2047E` | Hook 1 stub (fight-init body + small portrait) |
| `$40:84FC` | `0x204FC` | Hook 6 stub (bytecode `$3C` Pal 2 restore) |
| `$40:8580` | `0x20580` | Body palettes — 16 fighters × 32 B |
| `$40:8780` | `0x20780` | Small-portrait palettes — 16 × 32 B |
| `$40:8980` | `0x20980` | Large-portrait palettes — 16 × 32 B |
| `$00:FE18` | `0x0FE18` | Hook 2 stub (large portrait) — bank `$00` free space |

The MVN instructions in the stubs read palette data out of bank `$40` via the MVN source operand without changing the program bank, so the CPU never executes from `$40` (which is not reliably executable in this ExLoROM mapping).

**Hooks (3 in-place redirects):**

- **Hook 1 — `$00:97E5` (file `0x017E5`), fight init.** SE already has `JSL $0D:FDD2; NOP; NOP` here (the alt-glove hook). This patch changes it to `JSL $40:847E; NOP; NOP`; the stub does the body/small palette load, then chains to `$0D:FDD2` before returning so glove colors still apply. Gated on: iron flag `$7E:1D71`, OR P1 SELECT (`$7E:0091` bit 5), OR (VS mode `$7E:1D74 == 1` AND P2 SELECT `$7E:00A5` bit 5).
- **Hook 6 — `$01:99D4` (file `0x099D4`).** The bytecode-interpreter opcode `$3C` handler (Pal 2 restore, fires on e.g. Masked Muscle's spit-end). Replaces `SEP #$20; LDA #$05` (`E2 20 A9 05`) with `JSL $40:84FC`; the stub redirects the palette source to the alt body palette when active, else runs vanilla.
- **Hook 2 — `$00:9B91` (file `0x01B91`), large portrait.** Replaces only the `MVN $00,$10` (`54 00 10`, 3 B) with `JSR $FE18` (intra-bank, 3 B). The caller's `PLB`/`SEP #$20` at `$00:9B94` run unchanged after the stub returns.

**WRAM flags:** reuses `$7E:1D71` (iron flag, owned by `spo_iron_circuit.ips`) and reserves `$7E:1D75` (alt-active fighter ID) and `$7E:1D76` (alt-active flag) for its own use.

**Palette authoring:** the palettes are defined in [`scripts/build_spo_alt_opponents_colors.py`](../scripts/build_spo_alt_opponents_colors.py) as per-slot RGB overrides on the vanilla palettes; the swatch/hex reference tables in [`doc/standalone/ALT_OPPONENT_COLORS.md`](standalone/ALT_OPPONENT_COLORS.md) mirror those same values.

### [`spo_msu1_v6.ips`](../patches/standalone/spo_msu1_v6.ips)

Kurrono's MSU-1 audio patch (v6): replaces the SPC music with CD-quality streamed PCM on MSU-1-capable emulators and flash carts, falling back to the original SPC audio when no MSU-1 hardware/PCM files are present. See [`doc/standalone/KURRONO_MSU1.md`](standalone/KURRONO_MSU1.md) for the full track table, loop-flag fixes, and player setup.

**Records (sub-2MB):** two code hooks at file `0x00EC6D` and `0x044C0C` route the music engine to the MSU-1 driver, plus the header-checksum update at `0x7FDC`.

**ExLoROM driver:** the MSU-1 audio driver occupies file `0x200000–0x20007D` (121 bytes) in the `$40` expansion bank. This is disjoint from the alt-opponent-colors data at `0x20047E+`; see the compatibility note in the introduction for how the bundle builder merges the two.

### [`spo_disable_security_checksum.ips`](../patches/standalone/spo_disable_security_checksum.ips)

The World Circuit completion checksum prevents the Special Circuit from unlocking when using save states, emulators (SNES Classic, Switch NSO), or patched ROMs. This patch disables that checksum check.

**Patch record:** 1 in-place edit at file `0x003C23` (SNES `$00:BC23`): replaces `ORA $D5` (`05 D5`) with `LDA #$00` (`A9 00`), forcing the accumulator to zero before the SRAM-write store regardless of checksum result. Plus the standard 4-byte SNES header checksum update at file `0x7FDC`.

This is the **sole** source of the Special Circuit lock bypass in `spo_special_edition_v2.0.ips`. The Versus Hack patch does not touch `$00:BC23` and does not include any security-checksum logic.

### [`spo_sound_mode_incomplete.ips`](../patches/incomplete/spo_sound_mode_incomplete.ips)

**What it does:** Adds a SOUND MODE entry to the title-screen menu and shifts the entire menu UI up by 4 rows to accommodate it. The menu now shows NEW GAME / CONTINUE / DATA / CLEAR / SOUND MODE across rows 9/13/17/17/21. Cursor highlight, OAM sprite, arrows, and the MENU/<<SELECT decoration header all shift consistently.

**Known bugs:**

**(1) Pressing A on SOUND MODE falls through to DATA CLEAR.** The A-button handler at `CODE_01E0A3` dispatches on cursor position values derived from a snap-to-text scan, not a simple item index. The existing handler only knows 4 cursor stops (`$BF80`, `$BF90`, `$AFA0`, `$BFB0`). The SOUND MODE item adds a 5th visual entry but the D-pad navigation never reaches it — the cursor wraps from CIRCUIT SELECT directly back to NEW GAME, bypassing SOUND MODE entirely. The actual cursor value for the SOUND MODE row can only be determined empirically via a debugger (Mesen WRAM watch on `$0C10`). See [doc/incomplete/AUDIO_MODE_INCOMPLETE.md](../incomplete/AUDIO_MODE_INCOMPLETE.md) for the full investigation.

**(2) Name-entry screen behaves incorrectly after selecting NEW GAME or CONTINUE.** Adding a 4th title-screen item sets `$14 = 3` (written by the stub at `$01:B194` via `LDX #$0003; RTL` → the caller's `STX.b $14`). The title screen reads `$14` during cursor navigation. The name-entry cursor code at `CODE_01CAEA` also reads `$14` as the cursor upper bound — with `$14 = 3` from the title menu, cursor navigation is corrupted. Root cause: `$14` is not a general item count; its meaning differs between the title screen, circuit select, and name entry, and the value set by this patch bleeds into downstream screens. This is a fundamental consequence of adding a menu item to this particular screen — see [doc/incomplete/AUDIO_MODE_INCOMPLETE.md](../incomplete/AUDIO_MODE_INCOMPLETE.md) for details.

**(3) Sound Library is outside the normal state machine.** `CODE_00913B` (the Sound Library) was designed to run from a cold boot state. It cannot be called safely from within the running game — the NMI handler conflicts with its PPU setup, and its exit path routes through the VS mode check rather than returning cleanly. See [doc/incomplete/AUDIO_MODE_INCOMPLETE.md](../incomplete/AUDIO_MODE_INCOMPLETE.md) for all approaches attempted.

**This patch is a proof-of-concept only, is not included in `spo_special_edition_v2.0.ips`, and is not recommended for general use.**

**Why JSL instead of JSR:** The original `JSR $CA71` (3 bytes) is replaced with `JSL $00:F61A` (4 bytes, relocated from original `$0D:FB2D`). Bank `$01` has zero confirmed-free bytes. The JSL's 4th byte overwrites `$B197` — the opcode of the following `LDX #$0002`. The stub compensates by ending with `LDX #$0003; RTL` so the caller's `STX.b $14` writes the new item count.

**Patch records:**

| File offset | Bytes | Effect |
|---|---|---|
| `0x0B183` | `00` | Don't disable item 0 (NEW GAME) on no-save path |
| `0x0B194` | `22 1A F6 00` | JSL `$00:F61A` — replaces `JSR $CA71`, clobbers `$B197` |
| `0x0B198` | `EA EA` | NOP NOP — RTL landing pad |
| `0x0B19E` | `02` | Highlight base hi: row 9 start |
| `0x0B1BD` | `58` | Decoration tilemap hi: visual row 2 |
| `0x0B1C6` | `00` | Left arrow hi |
| `0x0B1C9` | `00` | Right arrow hi |
| `0x0B1F2` | `47` | Sprite Y base: row 9 |
| `0x6A3DA` | `52 FE` | Layout pointer → `$0D:FE52` (relocated from `$0D:FB0C`) |
| `0x6FE52` | 33 bytes | Layout sub-table (8 entries + terminator) |
| `0x761A` | 31 bytes | Stub: inline `CA71` + `STZ $23` + `LDX #$0003` + `RTL` |

**Layout sub-table (`$0D:FE52`, 33 bytes):**

```
01 1C 58 52   NEW GAME    row 9  col 12  ($5258)
02 1C 58 53   CONTINUE    row 13 col 12  ($5358)
03 1C 56 54   DATA        row 17 col 11  ($5456)
15 1C 62 54   CLEAR       row 17 col 17  ($5462)
4B 1C 56 55   SOUND       row 21 col 11  ($5556)
0C 1C 64 55   MODE        row 21 col 18  ($5564)
14 20 94 58   MENU        header         ($5894)
05 20 9C 58   <<SELECT    header         ($589C)
00            terminator
```

**Free space consumed:** 33 B at `$0D:FE52–$0D:FE72` and 31 B at `$00:F61A–$00:F638`.


## 7. Free space map

### Bank `$00` (file `0x0000–0x7FFF`)

The disassembly labels `$00:F5D0–$00:FF8F` as `UNK_00F5D0` — a 2,496-byte `%InsertGarbageData` region, never referenced by any JSL/JSR/JMP/JML in the ROM (verified by ROM-wide search). `spo_alt_glove_colors.ips` was the first patch in this repo to consume bytes here; `spo_iron_circuit.ips` is now the largest consumer.

| Range | Size | Contents |
|---|---|---|
| `0x75D0–0x75D4` | 5 B | EC6E trampoline (`spo_alt_glove_colors.ips` portrait sep stubs) |
| `0x75D5–0x7619` | 69 B | Portrait stub-rts (`spo_alt_glove_colors.ips`) |
| `0x761A–0x7D1F` | 1,798 B | **`spo_iron_circuit.ips`** — inlined descriptor renderer + IRON tile writer + 30+ flag-gated stubs (CONFIRM, POST_MATCH, DISPATCH, BG2 palette + iron rust palette, pre-fight title, rank renderer, portrait shift, KD/HP carry-over, HP-bar tween fix, championship belt screen palette/title/text-skip/digit override, SAVE_STUB, DRAW_STUB, EXIT_FLAG_CLEAR ×2) |
| `0x7D20–0x7D2F` | 16 B | `spo_alt_glove_colors.ips` opp_table (opponent → mode lookup) |
| `0x7D30–0x7D4F` | 32 B | `spo_alt_glove_colors.ips` rest_table (4 modes × 8 B) |
| `0x7D50–0x7D77` | 40 B | `spo_alt_glove_colors.ips` powered_up_table (5 modes × 8 B; mode 0 = vanilla green) |
| `0x7D78–0x7D9F` | 40 B | `spo_alt_glove_colors.ips` ko_punch_table (5 modes × 8 B; mode 0 = vanilla) |
| `0x7DA0–0x7DCF` | 48 B | `spo_alt_glove_colors.ips` portrait_table (3 frames × 4 modes × 4 B; indexed by frame*16 + (mode-1)*4) |
| `0x7DD0–0x7E17` | 72 B | Versus opponent-select char-switch table-hide stub (`$00:FDD0`) |
| `0x7E18–0x7F8F` | ~376 B | **Free** |

> Other regions in bank `$00` that look free are NOT safe — `0x0D03`, `0x0D25`, `0x0D42` are runs of `$FF` inside `DATA_008CC1` / `DATA_008CE5` (kanji/tile data tables); `0x202A` is zero-padding inside `DATA_00A004` (PPU register init table); `0x636B` is zero-padding inside `DATA_00E365` (indexed jump table). All would corrupt game data if patched.

### Bank `$01` (file `0x8000–0xFFFF`)

`spo_iron_circuit.ips` consumes two `%InsertGarbageData` zones in this bank: `UNK_01F784` (`$01:F784–$01:F7FF`, 124 B — hard ceiling at `$01:F800` is real game code) and `UNK_01D722` (`$01:FEC2–$01:FF8F`).

| Range | Size | Contents |
|---|---|---|
| `0x8018–0x801B` | 4 B | Header swap thunk (`JML` into bank-`$0D` header stub) |
| `0x801C–0x8029` | 14 B | **Free** (remainder of the 18-byte dead-loop zone) |
| `0x8457–0x8462` | 12 B | Trampoline 1 (TA disable progress gate) |
| `0x8463–0x8469` | 7 B | Back-out clear stub (`JSL` to bank-`$0D` clear stub + `JMP $C766`) |
| `0x846A–0x846A` | 1 B | **Free** (zero-fill byte preceding `DATA_01840B` table entry `$60`) |
| `0x841F–0x842A` | 12 B | **NOT SAFE** — null entries in `DATA_01840B` (AI opcode table, opcodes `$14–$1E`) |
| `0x875F–0x8766` | 8 B | **NOT SAFE** — `$FF` fill inside `DATA_01872F` (128-byte game data table) |
| `0xF784–0xF7FE` | 123 B | **`spo_iron_circuit.ips`** — REST_NO_GROW, DRAIN_SKIP, TALLY_NAME, RECOVERY_OVERRIDE, CONTINUE_RESET stubs |
| `0xF7FF–0xF7FF` | 1 B | **Free** (end of `UNK_01F784`) |
| `0xFEC2–0xFED3` | 18 B | Consumed by `spo_end_credits.ips` no-record artifact fix stub |
| `0xFED4–0xFF11` | 62 B | **`spo_iron_circuit.ips`** — PHASE_BYPASS (33 B), BONUS_ZERO (13 B), FAST_CASCADE (16 B) stubs |
| `0xFF12–0xFF1F` | 14 B | **Free** (gap between FAST_CASCADE and the iron W/L draw trampolines) |
| `0xFF20–0xFF2F` | 16 B | **`spo_iron_circuit.ips`** — iron W/L draw trampoline pair |
| `0xFF30–0xFF3E` | 15 B | **`spo_iron_circuit.ips`** — SLOT_KILL stub (clear iron W/L on per-profile FILE KILL) |
| `0xFF3F–0xFF4A` | 12 B | **Free** |
| `0xFF4B–0xFF54` | 10 B | **`spo_iron_circuit.ips`** — startup init stub |
| `0xFF55–0xFF7B` | 39 B | **`spo_score_overflow_fix.ips`** — score overflow-detect + clamp-to-999,990 stub |
| `0xFF7C–0xFF8F` | ~20 B | **Free** (end of `UNK_01D722`) |
| `0xFFB0–0xFFE0` | 49 B | 5-item Mode Select dispatch stub + TA/RV trampolines + VERSUS handler + trampoline 2 (extends 1 byte into the previously-free `$01:FFE0` slot) |
| `0xFFE1–0xFFE3` | 3 B | **Free** |

### Bank `$02` (file `0x10000–0x17FFF`)

No bytes consumed by any patch in this repo. Bank `$02` is untouched.

### Bank `$0D` (file `0x68000–0x6FFFF`)

The disassembly at line 78995 explicitly labels `$0DFA69–$0DFFE3` as garbage fill (`%InsertGarbageData`). This is **1,403 bytes of confirmed unused space**.

| Range | Size | Contents |
|---|---|---|
| `0x6FA69–0x6FA75` | 13 B | **`spo_iron_circuit.ips`** IRON tally descriptor (renders "   IRON CIRCUIT TOTAL" on the post-match score-tally screen) |
| `0x6FA76–0x6FA85` | 16 B | **Free** |
| `0x6FA86–0x6FAC2` | 61 B | New Mode Select layout sub-table (record [14a]) |
| `0x6FAC3–0x6FAC9` | 7 B | "VERSUS" tile data (record [14b]) |
| `0x6FACA–0x6FAFA` | 49 B | 12-record VERSUS opponent-select descriptor (record [14d]) |
| `0x6FAFB–0x6FB02` | 8 B | **Free** |
| `0x6FB03–0x6FB0B` | 9 B | "PLAYER 2" tile data (record [14c]) |
| `0x6FB0C–0x6FB61` | 86 B | `spo_end_credits.ips` descriptor + tile string + dispatch stub |
| `0x6FB62–0x6FB98` | 55 B | Versus opponent-select init blanking stub (record [16]) |
| `0x6FB99–0x6FBC8` | 48 B | P2 control dispatch stub (record [15]) |
| `0x6FBC9–0x6FBDD` | 21 B | Header swap stub (record [19]) |
| `0x6FBDE` | 1 B | **Free** |
| `0x6FBDF–0x6FC4B` | 109 B | `spo_title_screen_special_logo.ips` stub |
| `0x6FC4C–0x6FD24` | 217 B | P2-mirrors-P1 merge + poll stub (record [18]) |
| `0x6FD25–0x6FD68` | 68 B | **Free** |
| `0x6FD69–0x6FD72` | 10 B | "MACHO MAN" tile string (`spo_super_macho_man_fix.ips`) |
| `0x6FD73–0x6FD86` | 20 B | **Free** |
| `0x6FD87–0x6FD98` | 18 B | Per-fighter portrait X-shift stub (`spo_super_macho_man_fix.ips`) |
| `0x6FD99–0x6FD9F` | 7 B | Back-out clear stub (record [20]) |
| `0x6FDA0–0x6FDA9` | 10 B | **Free** |
| `0x6FDAA–0x6FDED` | 68 B | `spo_alt_glove_colors.ips` glove-mode dispatch / palette stubs (part 1) |
| `0x6FDEE` | 1 B | **Free** |
| `0x6FDEF–0x6FE51` | 99 B | `spo_alt_glove_colors.ips` Hook 1 fight-init trampoline + powered-up dispatch |
| `0x6FE52–0x6FE69` | 24 B | `spo_alt_glove_colors.ips` L+R + iron-flag helper stub |
| `0x6FE6A–0x6FE7B` | 18 B | `spo_alt_glove_colors.ips` R-vs-X sub |
| `0x6FE7C–0x6FE7F` | 4 B | **Free** |
| `0x6FE80–0x6FEBB` | 60 B | `spo_alt_glove_colors.ips` powered-up palette stub |
| `0x6FEBC–0x6FEBF` | 4 B | **Free** |
| `0x6FEC0–0x6FEFF` | 64 B | `spo_alt_glove_colors.ips` knock-out-punch stub |
| `0x6FF00–0x6FF1F` | 32 B | `spo_alt_glove_colors.ips` per-frame portrait detect table |
| `0x6FF20–0x6FF3F` | 32 B | **Free** |
| `0x6FF40–0x6FF5F` | 32 B | `spo_alt_glove_colors.ips` portrait color tables |
| `0x6FF60–0x6FF67` | 8 B | **Free** |
| `0x6FF68–0x6FFAA` | 67 B | `spo_alt_glove_colors.ips` portrait sep-variant stub |
| `0x6FFAB–0x6FFCE` | 36 B | `spo_alt_glove_colors.ips` portrait stub-rts variant |
| `0x6FFCF–0x6FFE3` | 21 B | **Free** |
| `0x6FFE4–0x6FFFF` | 28 B | Interrupt vectors — **untouchable** |

**Free space totals in the base 2 MB (with the full Special Edition bundle applied):**

| Region | Free |
|---|---|
| Bank `$0D` (`$0DFA69–$0DFFE3` zone) | **~213 B** (fragmented; max contiguous run 68 B at `$0D:FD25–$0D:FD68`) |
| Bank `$01` `UNK_01F784` (end at `$01:F800`) | **1 B** |
| Bank `$01` `UNK_01D722` (`$01:FF12–$FF1F`, `$01:FF3F–$FF4A`, and `$01:FF7C–$FF8F`) | **~46 B** |
| Bank `$01` `$01:801C–$01:8029` (header thunk zone tail) | **14 B** |
| Bank `$01` `$01:846A` (back-out clear zone tail) | **1 B** |
| Bank `$01` `$01:FFE1–$FFE3` | **3 B** |
| Bank `$00` `UNK_00F5D0` (`$00:FF90` end; `$00:FE18` now holds the alt-opp Hook 2 stub) | **~200 B** |
| **Total** | **~478 B** |

The 2.5 MB ExLoROM expansion adds ~510 KB of additional free space in bank `$40` (mapped below).

`spo_super_macho_man_fix.ips` also consumes 19 bytes in bank `$08` at file `0x045926` (`$08:D926`) for the new fighter-banner entry. That region sits inside the disassembly's documented `%InsertGarbageData($08D926, ...)` zone — dead code from development, never referenced at runtime. `spo_iron_circuit.ips` adds **no stub bytes** to bank `$08` (only single-instruction in-place hooks); iron-staged data lives in low WRAM and is read via the bank-`$08` low-WRAM mirror.

### Bank `$40` — ExLoROM expansion (file `0x200000–0x207FFF`)

The Special Edition bundle expands the ROM to 2.5 MB, adding the `$40` bank. Only the first ~2.9 KB is used; the rest is zero-fill.

| Range | Size | Contents |
|---|---|---|
| `0x200000–0x20007D` | 121 B | `spo_msu1_v6.ips` MSU-1 audio driver |
| `0x20007E–0x20047D` | ~1 KB | **Free** (gap between MSU-1 driver and alt-opp stubs) |
| `0x20047E–0x2004FB` | ~126 B | `spo_alt_opponents_colors.ips` Hook 1 stub (`$40:847E`) |
| `0x2004FC–0x20057F` | ~132 B | `spo_alt_opponents_colors.ips` Hook 6 stub (`$40:84FC`) |
| `0x200580–0x20077F` | 512 B | Body palettes (`$40:8580`, 16 × 32 B) |
| `0x200780–0x20097F` | 512 B | Small-portrait palettes (`$40:8780`, 16 × 32 B) |
| `0x200980–0x200B7F` | 512 B | Large-portrait palettes (`$40:8980`, 16 × 32 B) |
| `0x200B80–0x27FFFF` | ~510 KB | **Free** |

The two expansion patches are byte-disjoint in this bank; the bundle builder merges them (see the introduction's compatibility note).

**WRAM and SRAM allocations** (full Special Edition bundle):

| Region | Bytes | Owner |
|---|---|---|
| `$7E:1D70` | 1 | `spo_alt_glove_colors.ips` glove-mode flag |
| `$7E:1D71` | 1 | `spo_iron_circuit.ips` iron flag |
| `$7E:1D72`/`$1D73` | 2 | `spo_iron_circuit.ips` iron belt-screen flag (M=16 read alignment) |
| `$7E:1D74` | 1 | `spo_versus_hack.ips` VERSUS session flag |
| `$7E:1D75` | 1 | `spo_alt_opponents_colors.ips` alt-active fighter ID |
| `$7E:1D76` | 1 | `spo_alt_opponents_colors.ips` alt-active flag |
| `$7E:1FE5–$1FE9` | 5 | `spo_iron_circuit.ips` runtime-staged "IRON" letter-byte string |
| `$7E:1FEA` | 1 | `spo_iron_circuit.ips` cumulative KD count |
| `$7E:1FEB` | 1 | `spo_iron_circuit.ips` HP stash sentinel |
| `$7E:1FEE` | 1 | `spo_iron_circuit.ips` per-run loss counter |
| `$00:00A6`/`$00A7` | 2 | `spo_versus_hack.ips` P2 prev-held shadow (read only on VERSUS opponent-select) |
| `$70:0FE8 + slot` | 8 | `spo_iron_circuit.ips` iron W/L primary SRAM (1 byte × 8 slots) |
| `$70:1FE8 + slot` | 8 | `spo_iron_circuit.ips` iron W/L backup SRAM |

---

## 8. Text encoding and screen descriptor system

### Font encoding (menus and profile screens)

Used by the menu text renderer for Mode Select, opponent-select, etc. Per the SPO disassembly's `Tables/Fonts/SmallFont.txt`:

```
0–9         → $00–$09
A–Z         → $0A–$23   (A=$0A, B=$0B, …, Z=$23)
. ' , : ! ? → $24, $25, $26, $29, $2A, $2B
- x _ #     → $2C, $2D, $2E, $2F
=           → $54
<           → $EF       (real tile — the literal '<' glyph, NOT a space)
space       → $FF       (column-skip; renderer at CODE_01D24D advances the
                         tilemap pointer without writing, leaving the previously-
                         cleared BG tile visible — which looks like a space)
```

The original `<<SELECT` header in DA332[`$05`] encodes its two leading `<` glyphs as `$EF $EF`, and asar source emits real spaces as `$FF`. Strings like `db "  SELECT"` therefore expand to `FF FF 1C 0E 15 0E 0C 1D` (two column-skips + S E L E C T), while the original `<<SELECT` is emitted as `db $EF, $EF, "SELECT"` (two literal `<` glyphs + SELECT).

(This is the **menu-font** encoding, used for `DATA_0DA332` strings rendered via `CODE_01D1FC`. The **banner-font** encoding used by the per-fighter table at `$08:BB3D` is a different mapping — see §6 `spo_super_macho_man_fix` for the banner-font specifics.)

### Text string format (`DATA_0DA332`)

Each entry: `[length_byte][tile_byte × length]`. The renderer reads `data[0]` as the character count — it does **not** use the gap to the next pointer entry. Do not update the next pointer when adding a new string.

### Key DA332 indices

| Index | Content | File offset of tile data |
|---|---|---|
| `$05` | `<<SELECT` (2 leading `$EF` = `<` glyphs + SELECT) | original |
| `$07` | MINOR | original |
| `$08` | MAJOR | original |
| `$09` | WORLD | original |
| `$0A` | SPECIAL | original |
| `$0B` | CIRCUIT | original |
| `$0C` | MODE | original |
| `$0D` | CHAMPIONSHIP | original |
| `$0F` | TIME | original |
| `$10` | RECORDS | original |
| `$11` | BUTTON | original |
| `$12` | ATTACK | original |
| `$13` | SETTING | original |
| `$0E` | VIEW | original |
| `$38` | single-tile `<` glyph (`$EF`) | original — **do not touch pointer**; reused as a `<` tile throughout |
| `$49` | PLAYER | original |
| `$2D` | PLAYER 2 (8 tiles) | `0x6FB03` — **repurposed** |
| `$30` | MACHO MAN (9 tiles) | `0x6FD69` — **redirected by `spo_super_macho_man_fix.ips`** (originally pointed at `$0D:AC85` "MACHOMAN" 8 tiles, the typo is reversed by repointing to a new 9-tile entry in free space) |
| `$37` | VERSUS (6 tiles) | `0x6FAC3` — **repurposed** |
| `$A4` | CREDITS (7 tiles) | `0x6FB31` — **repurposed by `spo_end_credits.ips`** (originally pointed to garbage at `$B0A7`, never used as menu text) |

**Warning:** `text_idx=$00` is the descriptor terminator sentinel. It cannot be used as a live token index — the renderer stops on it.

**`DA332[$N]` with `$N > $53` is a fake-out, not a real entry.** DA332 has only 84 real entries (`$00–$53`). The renderer just reads `ptr_addr = 0x6A332 + $N * 2`; for `$N > $53` that lands inside DA3DA or beyond. Patches like `spo_end_credits.ips` exploit this by writing a tile-string pointer into the bytes at the implied offset (e.g. `$A4 → 0x6A47A`, inside DA3DA at byte-offset `$A0`), then using that out-of-range index in their own descriptor records. The byte being clobbered (a DA3DA entry, in the `$A4` case) must first be confirmed unreferenced by any live descriptor.

### Screen descriptor table (`DATA_0DA3DA`)

2-byte LE bank-relative pointers, one per screen/context. The renderer (`CODE_01D1FC`) is called with a **byte offset** into this table — so an arg of `$0E` means "the entry at byte offset `$0E`", i.e. the 8th pointer (index 7).

Key entries used or modified by this hack:

| Byte offset | Entry index | Pointer (default) | Screen / context |
|---|---|---|---|
| `$00` | 0 | `$AD48` | title screen layout |
| `$04` | 2 | `$AD6A` | Mode Select layout (redirected to `$FA86` by `spo_versus_hack.ips`) |
| `$12` | 9 | `$AE3F` | Records View select layout (redirected to `$FB0C` by `spo_end_credits.ips`) |
| `$14` | 10 | `$AE60` | "RECORDS VIEW MODE" header (modified in place by `spo_end_credits.ips`) |
| `$A4` | 82 | `$AEB7` (stale) | VERSUS opponent-select layout (redirected to `$FACA` by `spo_versus_hack.ips`) |

The opponent-select call site at `CODE_01BD0D` (file `0x0BD0D`) uses `TYA` to derive the argument from Y, where `Y=$000C` (Special Circuit complete) or `Y=$000E` (otherwise), selecting between byte-offset entries 6 and 7.

---

## 9. Key addresses quick reference

### Routines

| SNES address | File offset | Description |
|---|---|---|
| `$01:B0F0` | `0xB0F0` | Title screen entry, sets DP=`$0C00` |
| `$01:B14D` | `0xB14D` | Menu init (state `$03=0`) |
| `$01:BFA2` | `0xBFA2` | Records View select screen init |
| `$01:C9CA` | `0xC9CA` | Records View select A-button confirm dispatch |
| `$01:CA71` | `0xCA71` | Cursor highlight init |
| `$01:CA7C` | `0xCA7C` | Cursor highlight per-item Y stride literal (`LDA #$0100`) — shared across 11+ menus, patch in-place affects all of them |
| `$01:CAAE` | `0xCAAE` | OAM cursor sprite positioner (calls `D082` scan loop) |
| `$01:CAB2` | `0xCAB2` | OAM cursor per-item Y stride literal (`LDA #$20` → 32 px between cursor positions) — shared across 11+ menus; safer to redirect a specific call site to a custom stub than to patch in-place |
| `$01:CB57` | `0xCB57` | Tilemap palette-cycle (transforms `$0064` → `$EF`/`$FF`) |
| `$01:CC79` | `0xCC79` | Cursor highlight renderer (loops `$14+1` times) |
| `$01:D082` | `0xD082` | Cursor's auto-snap-to-text scan (skips `$EF`/`$FF`) |
| `$01:C8E9` | `0xC8E9` | Post-Start dispatcher — **do not patch** |
| `$01:DFB4` | `0xDFB4` | Per-frame input loop (interactive menu) |
| `$01:E0A3` | `0xE0A3` | A-button dispatch |
| `$01:E25F` | `0xE25F` | Cursor update done: play sound, update OAM, PLB;RTL |
| `$01:BB7D` | `0xBB7D` | Mode Select + Championship menu init |
| `$01:BE8C` | `0xBE8C` | Versus/Time Attack opponent-select runloop entry |
| `$01:BE9B` | `0xBE9B` | Char-switch render path (re-renders score data when `$0C80 == $86`) |
| `$01:C905` | `0xC905` | `$07E3` → mode dispatch (48 bytes, partially overwritten) |
| `$01:C74C` | `0xC74C` | `INC $03; INC $03; PLB; RTL` |
| `$01:C752` | `0xC752` | `INC $01; INC $01; PLB; RTL` |
| `$01:D1FC` | `0xD1FC` | Screen descriptor renderer |
| `$00:B29C` | `0x0B29C` | VS mode launcher (routes to fighter select) |
| `$00:9937` | `0x01937` | VS RAM-only setup — **ends with RTS, not RTL; do not JSL** |
| `$00:913B` | `0x0913B` | **Dangerous** — frame-wait loop, deadlocks from title screen |
| `$0D:FB62` | `0x6FB62` | Versus opponent-select init blanking stub |
| `$0D:FB99` | `0x6FB99` | P2 control dispatch stub (JSL from `$01:80CA`) |
| `$0D:FBC9` | `0x6FBC9` | Header swap stub (JML from `$01:8018` thunk) |
| `$0D:FC4C` | `0x6FC4C` | P2-mirrors-P1 merge + poll stub (JSL from `$01:BECE`) |
| `$0D:FD87` | `0x6FD87` | Per-fighter portrait X-shift stub (JSL from `$08:D2AB`) |
| `$0D:FD99` | `0x6FD99` | Back-out clear stub: zero `$7E:1D74` (JSL from `$01:8463`) |
| `$00:FDD0` | `0x07DD0` | Versus opponent-select char-switch blanking stub (JSL from `$01:BEC8`) |
| `$00:97E5` | `0x017E5` | `spo_alt_glove_colors.ips` Hook 1 site (universal fight-init) |
| `$00:DD43` | `0x05D43` | `CODE_00DD43` powered-up palette writer — hooked by glove patch |
| `$00:DDAA` | `0x05DAA` | `CODE_00DDAA` knock-out-punch palette writer — hooked by glove patch |
| `$00:EC6E` | `0x06C6E` | `CODE_00EC6E` portrait palette writer — called from 4 hooked sites by glove patch |
| `$00:F5D0` | `0x075D0` | Glove-patch EC6E trampoline (`JSR EC6E + RTL + RTS`) |
| `$00:F5D5` | `0x075D5` | Glove-patch portrait stub-rts (used by site `$00:EC69`) |
| `$0D:FDD2` | `0x6FDD2` | Glove-patch Hook 1 fight-init trampoline (triple-MVN palette write) |
| `$0D:FE80` | `0x6FE80` | Glove-patch powered-up stub |
| `$0D:FEC0` | `0x6FEC0` | Glove-patch knock-out-punch stub |
| `$0D:FF68` | `0x6FF68` | Glove-patch portrait sep-variant stub |
| `$01:DB27` | `0x0DB27` | Credits no-record fix hook: `JSR $D52B` → `JSR $FEC2` (`spo_end_credits.ips`) |
| `$01:FEC2` | `0x0FEC2` | Credits no-record fix stub: call `CODE_01D52B`, clamp `$7E40B0` (`spo_end_credits.ips`) |
| `$01:D8F7` | `0xD8F7` | Original menu-button poller (button-code in A; record [18] inlines a copy) |
| `$08:D162` | `0x45162` | Pre-fight profile screen renderer |
| `$08:D4AF` | `0x454AF` | BEST TIME / PR boss-name banner renderer |
| `$08:D840` | `0x45840` | Banner-tile sprite-builder (called by both renderers above) |

### RAM variables

| Address | Role |
|---|---|
| DP+`$01` = `$0C01` | State machine level 1 (`$01=0` → `$03` dispatch) |
| DP+`$03` = `$0C03` | State variable for `DATA_01B13D` dispatch |
| DP+`$05` = `$0C05` | Sub-state |
| DP+`$10` = `$0C10` | Cursor X (lo byte) |
| DP+`$11` = `$0C11` | Cursor Y (hi byte) |
| DP+`$14` = `$0C14` | Highlight cursor max index (item count − 1) |
| DP+`$20–$24` = `$0C20–$0C24` | Disable flags for items 0–4 (0=enabled, nonzero=disabled) |
| `$07E0` | Save-data initial selection (read by `CODE_01C8E9`) |
| `$07E3` | Current menu item index (0-based, updated per frame) |
| `$0607` | Mode flag (`$00`=idle, `$01`=TIME ATTACK, `$02`=secret 2-player mode). Vanilla semantics — this hack does not introduce a new value here. |
| `$1D74` | VERSUS session flag (`$00`=not VERSUS, `$01`=VERSUS). Set by the VERSUS handler at `$01:FFC9`, cleared by the back-out clear stub at `$01:8463`, read by all VERSUS-specific stubs. |
| `$0602` | Player count (`$03` = 2 players) |
| `$0030` | P2 boss-control flag (`$08` = use Controller 2 for opponent) |
| `$0090`/`$0091` | P1 held buttons (lo/hi) |
| `$0092`/`$0093` | P1 D-pad pressed-this-frame (lo/hi); P2-mirrors stub sets bit 7 of hi to inject P2 D-pad |
| `$0095` | P1 A-button pressed-this-frame; P2-mirrors stub sets bit 7 to inject P2 A |
| `$00A1` | P1 Start pressed-this-frame; P2-mirrors stub sets bit 7 to inject P2 Start |
| `$00A4`/`$00A5` | P2 held buttons (lo/hi) — read by P2-mirrors stub |
| `$00A6`/`$00A7` | P2 prev-held shadow (P2-mirrors stub); unused by the original game |
| `$0458–$045F` | BG palette 2 c12-c15 — written by glove patch (victory pose / KD / get-up) |
| `$0518–$051F` | Sprite OAM palette 0 c12-c15 — player rest gloves (written by glove patch) |
| `$0538`/`$053A` | Sprite OAM palette 1 c12-c13 — portrait HUD glove pixels |
| `$0578–$057F` | Sprite OAM palette 3 c12-c15 — knock-out-punch base palette |
| `$0600` | Current opponent index (0..15) — read by glove patch's Hook 1 |
| `$1D70` | Glove-color mode flag (`$00`=vanilla, `$01`=blue, `$02`=red, `$03`=yellow) |
| `$700010,X` | SRAM Minor Circuit progress flag (X=`$0050` in this context) |
| `$700080` | SRAM Special Circuit lock flag (0=unlocked) |

### Data tables

| Address | File offset | Description |
|---|---|---|
| `$0D:A3DA` | `0x6A3DA` | Screen descriptor pointer table (82 entries) |
| `$0D:A332` | `0x6A332` | Text string pointer table |
| `$0D:FA69` | `0x6FA69` | Start of confirmed garbage zone (1,403 bytes free) |
| `$0D:FA86` | `0x6FA86` | New Mode Select layout sub-table |
| `$0D:FACA` | `0x6FACA` | 12-record VERSUS opponent-select descriptor |
| `$0D:FB0C` | `0x6FB0C` | New Records View select-screen descriptor (`spo_end_credits.ips`) |
| `$0D:FB31` | `0x6FB31` | "CREDITS" tile string |
| `$0D:FB39` | `0x6FB39` | A-button dispatch stub for Records View select |
| `$0D:FB62` | `0x6FB62` | Versus opponent-select init blanking stub |
| `$0D:FB99` | `0x6FB99` | P2 control dispatch stub |
| `$0D:FBC9` | `0x6FBC9` | Header swap stub |
| `$0D:FBDF` | `0x6FBDF` | `spo_title_screen_special_logo.ips` stub |
| `$0D:FC4C` | `0x6FC4C` | P2-mirrors-P1 merge + poll stub |
| `$0D:FD69` | `0x6FD69` | "MACHO MAN" tile string (`spo_super_macho_man_fix.ips`) |
| `$0D:FD87` | `0x6FD87` | Per-fighter portrait X-shift stub (`spo_super_macho_man_fix.ips`) |
| `$0D:FD99` | `0x6FD99` | Back-out clear stub |
| `$00:FDD0` | `0x07DD0` | Versus opponent-select char-switch blanking stub |
| `$00:FD20` | `0x07D20` | Opponent → mode lookup table — 16 B (`spo_alt_glove_colors.ips`) |
| `$00:FD30` | `0x07D30` | Rest-palette color table — 4 modes × 8 B (`spo_alt_glove_colors.ips`) |
| `$00:FD50` | `0x07D50` | Powered-up color table — 5 modes × 8 B (`spo_alt_glove_colors.ips`; mode 0 = vanilla) |
| `$00:FD78` | `0x07D78` | Knock-out-punch color table — 5 modes × 8 B (`spo_alt_glove_colors.ips`; mode 0 = vanilla) |
| `$00:FDA0` | `0x07DA0` | Portrait color table — 3 frames × 4 modes × 4 B (`spo_alt_glove_colors.ips`) |
| `$0D:FE52` | `0x06FE52` | L+R + iron-flag helper stub (`spo_alt_glove_colors.ips`) |
| `$0D:FE6A` | `0x06FE6A` | R-vs-X sub (`spo_alt_glove_colors.ips`) |
| `$00:8547` | `0x00547` | `DATA_008547` (ColorEndScreen.bin) — 288-byte ending palette block; palette 4 c12-c15 at `0x05DF` patched by `spo_alt_glove_colors.ips` |
| `$0D:FFE4` | `0x6FFE4` | Interrupt vectors — untouchable |
| `$08:BB3D` | `0x43B3D` | Per-fighter banner pointer table (16 entries × 2 bytes) |
| `$08:D926` | `0x45926` | Per-fighter banner entry for Macho Man (`spo_super_macho_man_fix.ips`) |
| `$01:B132` | `0x0B132` | `$01`-indexed dispatch table |
| `$01:B13D` | `0x0B13D` | `$03`-indexed title-screen state table |
| `$01:BB66` | `0x0BB66` | `$03`-indexed table for `$01=4` |
| `$01:BB73` | `0x0BB73` | `$05`-indexed Championship sub-machine table |
| `$01:BC76` | `0x0BC76` | `$05`-indexed Mode Select state machine table |

---

## 10. Title screen BG layout quirk

`CODE_08C8AB` (the title screen BG init, SNES `$08:C8AB`) runs two DMA transfers:

| Source WRAM | VRAM destination | Expected BG (from `$2109`) |
|---|---|---|
| `$5000–$57FF` | `$4C00` | — |
| `$6000–$67FF` | `$5800` | BG3 (`BG3SC = $59`) |

`$2109` (BG3SC) is set to `$59` (→ VRAM `$5800`) at file `0x43FD9`. The natural reading is that the `$6000` block renders as BG3 and `$5000` as something else. **This is wrong in practice.**

Empirically, writing menu font tiles (`$28XX`, palette 2) to the `$6000` block renders them on BG1; writing to the `$5000` block renders them on BG3 with the correct font. The `$5000` block (→ VRAM `$4C00`) is the tilemap that carries the menu character set and shows as BG3 on the title screen.

The likely explanation is that BG1SC (`$2107`) is also set to `$59` (→ VRAM `$5800`) by the NMI/VBLANK handler's PPU register upload — which copies configuration tables to hardware every frame and is not captured by the single explicit `STA $2109` in the static disassembly. Both BG1 and BG3 would then share VRAM `$5800` as their tilemap, but with different character data (CHR) base addresses: BG3's CHR contains the ring artwork, BG1's CHR contains the menu font. Writing to VRAM `$5800` (via the `$6000` WRAM buffer) renders as BG1 because BG1 has priority and its CHR has the letter glyphs at those tile indices; BG3 at the same tilemap renders ring-art tiles at those indices. Writing to VRAM `$4C00` (via the `$5000` buffer) hits BG3's exclusive tilemap where the font CHR applies.

**Practical rule for anyone continuing this work:** to write visible text on the title screen using the menu font, target the `$5000` WRAM buffer. WRAM address formula:

```
WRAM = $5000 + row × 64 + col × 2
```

The `$6000` buffer is the ring artwork layer (BG1 with ring CHR); modifying it affects the ring floor graphics, not text.
