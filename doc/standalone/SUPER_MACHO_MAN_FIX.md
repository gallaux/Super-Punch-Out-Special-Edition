# `spo_super_macho_man_fix.ips` — Summary

Fixes the original ROM's "SUPER MACHOMAN" → "SUPER MACHO MAN" typo across every screen in the game (TIME ATTACK and VERSUS opponent select, PERSONAL RECORDS, BEST TIME table, pre-fight profile...). The corrected spelling matches the US manual and every other appearance of the character — Punch-Out!! (1987, NES) and Punch-Out!! (2009, Wii).

<img width="256" height="224" alt="Super Punch-Out!! (USA) Super Macho Man Fix_001" src="https://github.com/user-attachments/assets/e11a9f9d-ba77-4ba3-9660-79661e0d3b54" />
<img width="256" height="224" alt="Super Punch-Out!! (USA) Super Macho Man Fix_002" src="https://github.com/user-attachments/assets/439a7e56-deb9-4f5f-947b-57fa64ebaf19" />
<img width="256" height="224" alt="Super Punch-Out!! (USA) Super Macho Man Fix_003" src="https://github.com/user-attachments/assets/2fe81707-de9e-419f-99ce-98e5e2328236" />
<img width="256" height="224" alt="Super Punch-Out!! (USA) Super Macho Man Fix_004" src="https://github.com/user-attachments/assets/abe3b1a9-7ae3-4b22-9548-f721c9794d12" />

## What's involved

The fix touches four distinct screens with two text encodings, two pointer tables, and a per-fighter code patch. The pre-fight profile screen has a fixed layout slot that the corrected longer name doesn't fit into — Nintendo originally avoided this by collapsing "MACHO MAN" into "MACHOMAN". The patch resolves it by shifting Super Macho Man's portrait sprite 4 pixels right (only on his profile screen) to give the name the room it needs.

## Patch records

9 records, 59 bytes total (plus the SNES header checksum):

| File offset | Bytes | Purpose |
|---|---|---|
| `0x043B53` | 2 | Banner-table pointer redirect (fighter 11 → `$08:D926`) |
| `0x045926` | 19 | New banner entry "SUPER MACHO MAN" |
| `0x0452AB` | 5 | Profile-renderer hook (`LDX #$38A8; STX $7A` → `JSL $0D:FD87; NOP`) |
| `0x06A392` | 2 | DA332 redirect (entry `$30` → `$0D:FD69`) |
| `0x06AE8F` | 1 | PR descriptor: SUPER WRAM-lo column shift |
| `0x06AE93` | 1 | PR descriptor: MACHO MAN WRAM-lo column shift |
| `0x06AF73` | 1 | TA title card: MACHO MAN WRAM-lo column shift |
| `0x06FD69` | 10 | New menu-font string "MACHO MAN" (length-prefixed) |
| `0x06FD87` | 18 | Per-fighter portrait X-shift stub |

## Free space consumed

- **Bank `$08`**: 19 bytes at `$08:D926`
- **Bank `$0D`**: 28 bytes total (10 at `$0D:FD69`, 18 at `$0D:FD87`)

All allocations sit inside disassembly-documented `%InsertGarbageData` regions, verified unreferenced by ROM-wide search.

## Patch in asm form

```asm
; spo_super_macho_man_fix
; Fixes "SUPER MACHOMAN" → "SUPER MACHO MAN" across all four screen types.
; See the standalone doc's description and TECHNICAL.md §6 for the full
; rationale (two font systems, four screens, layout constraints, portrait shift).

; --- [1] DA332 entry $30: redirect menu-font string pointer → new "MACHO MAN" ---
org $0DA392
    dw $FD69        ; was: $AC85 ("MACHOMAN" 8-tile string at $0D:AC85)

; --- [2] New menu-font string at $0D:FD69 ("MACHO MAN", 9 tiles) ---
; Format: [length_byte][tile_bytes...]  — $FF = column-skip (visible space)
org $0DFD69
    db $09, $16,$0A,$0C,$11,$18,$FF,$16,$0A,$17
    ;       M   A   C   H   O   _   M   A   N

; --- [3] Personal Records descriptor: shift SUPER from col 3→2 ---
org $0DAE8F
    db $04          ; was: $06  (SUPER WRAM-lo: $5C06→$5C04, col 3→2)

; --- [4] Personal Records descriptor: shift MACHO MAN from col 9→8 ---
org $0DAE93
    db $10          ; was: $12  (MACHO MAN WRAM-lo: $5C12→$5C10, col 9→8)

; --- [5] TA title card: shift MACHO MAN from col 21→20 ---
org $0DAF73
    db $28          ; was: $2A  (MACHO MAN WRAM-lo: $542A→$5428, col 21→20)

; --- [6] Banner table: redirect fighter 11 pointer to new entry at $08:D926 ---
org $08BB53
    dw $D926        ; was: original MACHOMAN entry

; --- [7] New banner entry at $08:D926 (19 bytes) ---
; Format: [b0: BEST TIME X-offset][b1: profile X-offset][b2: CHAMP gap]
;         [tile bytes (banner-font)][$00 terminator]
; Banner-font: S=$67, U=$69, P=$64, E=$49, R=$66, M=$61, A=$45, C=$47, H=$4C,
;              O=$63, N=$62, space=$EF
org $08D926
    db $00, $00, $00          ; offsets (0 = leftmost)
    db $67,$69,$64,$49,$66,$EF,$61,$45,$47,$4C,$63,$EF,$61,$45,$62
    ;  S   U   P   E   R  _   M   A   C   H   O  _   M   A   N
    db $00                    ; terminator

; --- [8] Profile-renderer hook: replace LDX #$38A8; STX $7A with JSL stub ---
org $08D2AB
    JSL $0DFD87     ; was: LDX #$38A8; STX $7A (5 bytes → JSL+NOP, 5 bytes)
    NOP

; --- [9] Per-fighter portrait X-shift stub at $0D:FD87 (18 bytes) ---
; Shifts Super Macho Man's portrait +4 px right on his profile screen only,
; giving the longer "CHAMP. SUPER MACHO MAN" line room to fit.
org $0DFD87
    LDA $00         ; fighter index (DP base = $0000 in this context)
    CMP #$0B        ; fighter 11 = Super Macho Man?
    BEQ macho
    LDX #$38A8      ; default portrait Y/X packed word (Y=$38 X=$A8)
    STX $7A
    RTL
macho:
    LDX #$38AC      ; +4 px right (X=$AC instead of $A8)
    STX $7A
    RTL
```

(Plus the standard 4-byte SNES header checksum update at file `0x7FDC`.)

## Compatibility

- **Apply on top of**: original `Super Punch-Out!! (USA).sfc` ROM (MD5 `97fe7d7d2a1017f8480e60a365a373f0`)
- **Bundled into**: `spo_special_edition_v2.0.ips`
- **Conflicts with**: nothing in this repo
- **Cheat-code compatibility**: unaffected

## See also

For the full reverse-engineering details — banner-font letter map, screen-by-screen layout reasoning, profile-renderer flow, the per-fighter portrait stub assembly, and the explanation of why `$EF` and `$FF` behave as different "space" bytes — see [doc/TECHNICAL.md](../TECHNICAL.md) section 6 entry for `spo_super_macho_man_fix.ips`.
