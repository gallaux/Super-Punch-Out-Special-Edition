# `spo_title_screen_special_ring.ips` — Summary

Cosmetic: replaces the title-screen ring logo and background color palette with the Special Circuit variants for some extra flair. The SUPER PUNCH-OUT!! logo itself is unchanged; only the ring artwork and the colors behind/around it are swapped. All in-game circuit screens are unaffected — only the title screen is altered.

<img width="256" height="224" alt="Super Punch-Out!! (USA) Title Screen Special Ring_001" src="https://github.com/user-attachments/assets/7e26111e-4097-4381-aee4-4e556a50880b" />

## Patch records

2 records, 4 bytes total (plus the SNES header checksum) — both in the title-screen frame handler `CODE_008EE4`:

| File offset | Old | New | Effect |
|---|---|---|---|
| `0x0F25` | `02` | `08` | `LDX #$8002` → `LDX #$8008` — loads Special Circuit ring logo GFX instead of Minor Circuit |
| `0x0F68-0F6A` | `AE 18 80` | `A2 B6 99` | `LDX DATA_088000+$18` → `LDX #$99B6` — reads Special Circuit palette directly instead of via the pointer table, leaving the table entry (and all in-game Minor Circuit references) unchanged |

The bank `$0E` header table maps circuit graphics by offset: `+$00` = MainMenu font, `+$02` = MinorCircuit, `+$04` = MajorCircuit, `+$06` = WorldCircuit, `+$08` = SpecialCircuit.

## Free space consumed

None. Both records are in-place edits.

## Patch in asm form

```asm
; spo_title_screen_special_ring
; Replaces the title-screen ring logo and background color palette
; with the Special Circuit variants. Both patches are in CODE_008EE4
; (the title-screen frame handler).
; Bank $0E header table: +$00=MainMenu, +$02=Minor, +$04=Major,
;                        +$06=World, +$08=Special.

org $008F25
    db $08          ; was: $02 — LDX #$8008 instead of #$8002 → Special ring GFX

org $008F68
    LDX #$99B6      ; was: LDX DATA_088000+$18 — read Special Circuit palette
                    ; directly instead of via the pointer table; the table entry
                    ; (and all in-game Minor Circuit references) stays unchanged
```

(Plus the standard 4-byte SNES header checksum update at file `0x7FDC`.)

## Compatibility

- **Apply on top of**: original `Super Punch-Out!! (USA).sfc` ROM (MD5 `97fe7d7d2a1017f8480e60a365a373f0`)
- **Bundled into**: `spo_special_edition_v2.0.ips`
- **Conflicts with**: nothing in this repo
- **Cheat-code compatibility**: unaffected

## See also

For the bank `$0E` header-table layout and the rationale for reading the palette directly (vs through the pointer table), see the `spo_title_screen_special_ring.ips` entry in [doc/TECHNICAL.md § 6](../TECHNICAL.md).
