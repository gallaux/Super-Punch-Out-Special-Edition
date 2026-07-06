# `spo_end_credits.ips` — Summary

Adds a fourth **CREDITS** entry to the Records View select screen. Selecting CREDITS launches the game's ending-cutscene credits roll. After the credits finish the game stays on the final screen and requires reset — that's the original cutscene's terminal behavior, not introduced by this patch.

<img width="256" height="224" alt="Super Punch-Out!! (USA) End Credits_001" src="https://github.com/user-attachments/assets/e59979cc-804c-4110-aa88-6570d4b3b9b8" />
<img width="256" height="224" alt="Super Punch-Out!! (USA) End Credits_002" src="https://github.com/user-attachments/assets/557ab8f1-570d-424a-b87c-9dbf27e0e27c" />

## What it does

The Records View select screen originally has three entries: BEST TIME, BEST SCORE, PERSONAL RECORDS — which list the three Championship circuits' records (Minor, Major, World). This patch:

- Adds a fourth entry **CREDITS** at row 22.
- Tightens the layout so the four entries sit at rows 10/14/18/22 with the header at row 2 (matching the Championship circuit-select layout).
- Hooks the A-button confirm dispatch so selecting CREDITS launches the ending credits cutscene (`JML $00:B29C`).
- **Fixes a no-record artifact** (see below) so the credits roll looks correct even when launched before all opponents have been beaten.

## No-record artifact fix

When the credits roll is launched before all 16 opponents have been beaten, fighters with no saved record would display a garbage Japanese glyph in the `YOUR BEST` time slot instead of a valid time. This is a cosmetic artifact only.

**Root cause:** The credits animation engine in bank `$01` runs a per-frame state machine (`CODE_01DAC4`) that reads each fighter's time digits from SRAM via `CODE_01D52B`. `CODE_01D52B` reads 5 SRAM bytes at fighter index × 5 and writes them as digit tiles to `$7E40B0`–`$7E40BE` (BG3 tilemap, DMA'd to VRAM `$7000`+ each frame). For an unbeaten fighter those SRAM bytes are uninitialized (`$FF`), and tile `$FF` in the credits font is a Japanese glyph. In the original game this path is only reached after World Circuit completion (all fighters beaten), so it was never a problem.

**Fix:** a 3-byte hook at `$01:DB27` (file `0x0DB27`) redirects `JSR CODE_01D52B` to a stub at `$01:FEC2` (file `0x0FEC2`). The stub calls `CODE_01D52B` normally, then checks whether `$7E40B0` is `$FF` and replaces it with `$03` (tile "3") if so. Tile `$03` is the value Nintendo's own no-record path writes at `CODE_01DAC4` — the leading digit of the hardcoded placeholder time `3'00"00`, which is the duration of a full round.

## Patch records

12 records, 137 bytes total (plus the SNES header checksum):

| File offset | Bytes | Effect |
|---|---|---|
| `0x0BFA6`, `0x0BFAB`, `0x0BFDB`, `0x0BFE9`, `0x0BFF2`, `0x0BFF5`, `0x0C022` | 1-2 | Init-routine bytes: highlight bar base, palette-cycle bases, arrow positions, cursor sprite anchor — all shifted in lockstep to move the layout from rows 12/16/20/24 → rows 10/14/18/22 |
| `0x0C9CA` | 4 | Replace start of confirm dispatcher `CODE_01C9CA` with `JML $0D:FB39` (per-fighter dispatch stub) |
| `0x0DB27` | 3 | Hook: `JSR CODE_01D52B` → `JSR $FEC2` (no-record artifact fix) |
| `0x0FEC2` | 18 | Stub: call `CODE_01D52B`, check `$7E40B0 == $FF`, overwrite with `$03` if so |
| `0x6A3EC` | 2 | DA3DA[`$12`] redirect to `$0D:FB0C` (new screen descriptor) |
| `0x6A47A` | 2 | DA332[`$A4`] redirect to `$0D:FB31` (CREDITS tile string) |
| `0x6AE62`, `0x6AE66`, `0x6AE6A` | 1 each | Header descriptor row shifts (RECORDS / VIEW / MODE) |
| `0x6FB0C` | 37 | New screen layout sub-table |
| `0x6FB31` | 8 | "CREDITS" tile string |
| `0x6FB39` | 41 | A-button dispatch stub (handles 4 cursor indices, including the new CREDITS path) |

## Free space consumed

- **Bank `$0D`**: 86 bytes at `$0D:FB0C–$0D:FB61` (descriptor + tile string + dispatch stub)
- **Bank `$01`**: 18 bytes at `$01:FEC2–$01:FED3` (no-record artifact fix stub)

## Patch in asm form

```asm
; spo_credits
; Adds a CREDITS entry to the Records View select screen and fixes the
; no-record artifact (garbage glyph for unbeaten fighters in the credits roll).

;==============================================================================
; Layout adjustments (Records View select screen init, file 0x0BFA2)
; All shifted in lockstep to move entries from rows 12/16/20 → rows 10/14/18/22.
;==============================================================================

org $01BFA6
    db $03          ; item count (4 items, 0-indexed), was $02 (3 items)

org $01BFAB
    dw $0290        ; highlight bar base (row 10), was $0310 (row 12)

org $01BFDB
    dw $5994        ; CBA8 palette-cycle base (subheader row 6), was $5A14 (row 8)

org $01BFE9
    db $8E          ; CB57 header X arg → row 2, was $CE (row 3)

org $01BFF2
    dw $0190        ; arrow renderer X ($01:D70C) — '<' bracket row 6, was $0210 (row 8)

org $01BFF5
    dw $01AE        ; arrow renderer Y ($01:D70C) — '>' bracket row 6, was $022E (row 8)

org $01C022
    db $4F          ; cursor sprite anchor Y — scan starts at row 10, was $5F (row 12)

;==============================================================================
; A-button confirm dispatch: redirect CODE_01C9CA → stub in bank $0D
;==============================================================================

org $01C9CA
    JML $0DFB39     ; bypass original 3-way dispatch

;==============================================================================
; Screen descriptor pointer: DA3DA[$12] → new 9-record layout at $0D:FB0C
;==============================================================================

org $0DA3EC
    dw $FB0C        ; was: $AE3F (original 3-item Records View layout)

;==============================================================================
; Tile string pointer: DA332[$A4] → "CREDITS" tile data at $0D:FB31
; (DA332[$A4] originally pointed to garbage — repurposed)
;==============================================================================

org $0DA47A
    dw $FB31        ; was: stale garbage pointer

;==============================================================================
; Header descriptor (text-index $14, RECORDS VIEW MODE row): shift to row 2
;==============================================================================

org $0DAE62
    db $8E          ; RECORDS WRAM-lo → $508E (row 2 col 7), was $CE (row 3 col 7)

org $0DAE66
    db $9E          ; VIEW WRAM-lo    → $509E (row 2 col 15), was $DE

org $0DAE6A
    db $AC          ; MODE WRAM-lo    → $50AC (row 2 col 22), was $EC

;==============================================================================
; New screen descriptor at $0D:FB0C (37 bytes, 9 records + terminator)
; Format: [text_idx][attr][WRAM_lo][WRAM_hi] — attr $34=selectable, $1C=selectable,
;          $20=always-visible, $0C=always-visible-Layer2
;==============================================================================

org $0DFB0C
    db $1A,$20,$94,$59   ; ITEM      Layer 2 row 6  col 10  ($5994)
    db $05,$20,$9C,$59   ;  SELECT   Layer 2 row 6  col 14  ($599C)
    db $1B,$34,$96,$52   ; BEST      Layer 1 row 10 col 11  ($5296)
    db $0F,$34,$A0,$52   ; TIME      Layer 1 row 10 col 16  ($52A0)
    db $1B,$1C,$96,$53   ; BEST      Layer 1 row 14 col 11  ($5396)
    db $1D,$1C,$A0,$53   ; SCORE     Layer 1 row 14 col 16  ($53A0)
    db $1C,$34,$90,$54   ; PERSONAL  Layer 1 row 18 col 8   ($5490)
    db $10,$34,$A2,$54   ; RECORDS   Layer 1 row 18 col 17  ($54A2)
    db $A4,$1C,$98,$55   ; CREDITS   Layer 1 row 22 col 12  ($5598)
    db $00               ; terminator

;==============================================================================
; "CREDITS" tile string at $0D:FB31
; Format: [length][tile_bytes] — tile encoding: A=$0A … Z=$23
;==============================================================================

org $0DFB31
    db $07, $0C,$1B,$0E,$0D,$12,$1D,$1C
    ;       C   R   E   D   I   T   S

;==============================================================================
; A-button dispatch stub at $0D:FB39 (41 bytes)
; Handles 4 cursor indices: 0=BEST TIME, 1=BEST SCORE, 2=PERSONAL RECORDS,
; 3=CREDITS. Also preserves the original $44≠0 short-circuit path.
;==============================================================================

org $0DFB39
    LDA $44
    BNE @44path         ; $44 ≠ 0 → skip to C94F path
    LDA $07E6           ; cursor index
    BEQ @idx0
    CMP #$01
    BEQ @idx1
    CMP #$03
    BEQ @idx3
    ; index 2 fall-through (3 INC $05 pairs total)
    INC $05
    INC $05
@idx1:                  ; index 1 enters here (2 INC $05 pairs)
    INC $05
    INC $05
@idx0:                  ; index 0 enters here (1 INC $05 pair)
    INC $05
    INC $05
    STZ $07
    PLB
    RTL
@idx3:
    JML $00B29C         ; launch ending-cutscene credits roll
@44path:
    JML $01C94F         ; $44 ≠ 0 path

;==============================================================================
; No-record artifact fix: hook JSR CODE_01D52B → JSR $FEC2 stub
;==============================================================================

org $01DB27
    JSR $FEC2           ; was: JSR CODE_01D52B

; Stub at $01:FEC2 — call original, then clamp $FF tile to $03
org $01FEC2
    JSR $D52B           ; call CODE_01D52B (writes SRAM digit tiles to $7E40B0+)
    LDA.l $7E40B0       ; read the leading tile
    CMP #$FF            ; is it the Japanese garbage glyph?
    BNE +6              ; no: leave it
    LDA #$03            ; yes: replace with tile $03 ("3" — Nintendo's own
    STA.l $7E40B0       ;      no-record placeholder, leading digit of 3'00"00)
    RTS
```

(Plus the standard 4-byte SNES header checksum update at file `0x7FDC`.)

## Compatibility

- **Apply on top of**: original `Super Punch-Out!! (USA).sfc` ROM (MD5 `97fe7d7d2a1017f8480e60a365a373f0`)
- **Bundled into**: `spo_special_edition_v2.0.ips`
- **Conflicts with**: nothing in this repo
- **Cheat-code compatibility**: unaffected

## See also

For the full layout-shift rationale (why the cursor anchor `$53` is the load-bearing one — the `D082` text-snap scan loop), the descriptor sub-table layout, and the A-button dispatch stub assembly, see the `spo_end_credits.ips` entry in [doc/TECHNICAL.md § 6](../TECHNICAL.md).
