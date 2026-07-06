# `spo_title_screen_special_logo.ips` — Summary

Cosmetic: writes the text **SPECIAL EDITION** into the title screen below the main game logo. Uses the standard menu font (palette 2, priority 1) and renders every time the title screen background is initialized.

<img width="256" height="224" alt="Super Punch-Out!! (USA) Title Screen Special Logo_001" src="https://github.com/user-attachments/assets/e6adfd00-0eed-4e74-94f2-821417450772" />

## What it does

Hooks the title-screen BG init routine `CODE_08C8AB` to call a stub that writes 14 tiles into the BG3 tilemap buffer at row 12, cols 6-22 (with a one-tile gap between SPECIAL and EDITION).

## Patch records

2 records, 115 bytes total (plus the SNES header checksum):

| File offset | Bytes | Effect |
|---|---|---|
| `0x44906` | 6 | Hook in `CODE_08C8AB`: `LDY #$1801; STY $4300` → `JSL $0D:FBDF; NOP; NOP` (the 2 displaced instructions are re-executed at the top of the stub) |
| `0x6FBDF` | 109 | Stub at `$0D:FBDF` — writes "SPECIAL EDITION" tile-by-tile into the BG3 tilemap buffer at WRAM `$5000`+ |

Tile entry format: `$28XX` = priority 1, palette 2, tile index XX. The space between SPECIAL and EDITION (col 13) is left unwritten — the background fill tile at that position acts as the gap.

## Free space consumed

- **Bank `$0D`**: 109 bytes at `$0D:FBDF-FC4B` (inside the disassembly's `%InsertGarbageData($0DFA69, ...)` zone)

## Patch in asm form

```asm
; spo_title_screen_special_logo
; Writes "SPECIAL EDITION" into the title-screen BG3 tilemap buffer
; at row 12, cols 6-22.  Hooks the end of CODE_08C8AB (the title-screen
; BG init routine) to call the stub below.
; Tile entry format: $28XX = priority 1, palette 2, tile index XX.
; WRAM target = $5000 + row*64 + col*2.  Note: despite $2109 (BG3SC)
; pointing to VRAM $5800, empirically the $5000 block renders as BG3 on
; the title screen (see TECHNICAL.md §10 for the BG layout quirk).

; --- Hook (file 0x44906, SNES $08:C906) ---
org $08C906
    JSL $0DFBDF     ; was: LDY #$1801; STY $4300 (2 displaced instrs, re-executed in stub)
    NOP
    NOP

; --- Stub at $0D:FBDF (109 bytes) ---
org $0DFBDF
    LDY.w #$1801    ; displaced instr 1
    STY.w $4300     ; displaced instr 2
    REP #$20        ; 16-bit A
    ; SPECIAL
    LDA.w #$281C : STA.l $7E530C   ; S col 6
    LDA.w #$2819 : STA.l $7E530E   ; P col 7
    LDA.w #$2805 : STA.l $7E5310   ; E col 8
    LDA.w #$2803 : STA.l $7E5312   ; C col 9
    LDA.w #$2809 : STA.l $7E5314   ; I col10
    LDA.w #$2801 : STA.l $7E5316   ; A col11
    LDA.w #$280C : STA.l $7E5318   ; L col12
    ; col 13 intentionally unwritten (background gap tile = space)
    ; EDITION
    LDA.w #$2805 : STA.l $7E531A   ; E col14
    LDA.w #$2804 : STA.l $7E531C   ; D col15
    LDA.w #$2809 : STA.l $7E531E   ; I col16
    LDA.w #$2814 : STA.l $7E5320   ; T col17
    LDA.w #$2809 : STA.l $7E5322   ; I col18
    LDA.w #$280F : STA.l $7E5324   ; O col19
    LDA.w #$2817 : STA.l $7E5326   ; N col20
    SEP #$20        ; restore 8-bit A
    RTL
```

Font encoding (tile indices): A=`$0A`, B=`$0B`, ..., Z=`$23` (A-Z sequential from `$0A`).

(Plus the standard 4-byte SNES header checksum update at file `0x7FDC`.)

## Compatibility

- **Apply on top of**: original `Super Punch-Out!! (USA).sfc` ROM (MD5 `97fe7d7d2a1017f8480e60a365a373f0`)
- **Bundled into**: `spo_special_edition_v2.0.ips`
- **Conflicts with**: nothing in this repo
- **Cheat-code compatibility**: unaffected

## See also

For the full stub assembly, the BG3 tilemap address formula, and a discussion of the title-screen BG layout quirk (the `$5000` block renders as BG3 despite `$2109` settings suggesting otherwise), see the `spo_title_screen_special_logo.ips` entry in [doc/TECHNICAL.md § 6](../TECHNICAL.md) and [§ 10 (Title screen BG layout quirk)](../TECHNICAL.md#10-title-screen-bg-layout-quirk).
