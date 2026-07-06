# `spo_profile_stats_fix.ips` — Summary

Corrects two profile-screen stat errors present in the US/EUR ROM — both classic copy-paste bugs in the original game's data. Both correct values match the US manual and the later-released Japanese version.

<img width="256" height="224" alt="Super Punch-Out!! (USA) Profile Stats Fix_001" src="https://github.com/user-attachments/assets/6918a60c-9e16-4112-97ab-f9060a190419" />
<img width="256" height="224" alt="Super Punch-Out!! (USA) Profile Stats Fix_002" src="https://github.com/user-attachments/assets/b178e2a6-5b4e-4925-bb22-dcabcc993289" />

## What it fixes

- **Mr. Sandman's profile stats**: originally a verbatim copy of Super Macho Man's record (`28-23-29-3`). Restored to the correct values: age 30, weight 270 lbs, record 28-4.
- **Mad Clown's weight**: incorrectly listed as 390 lbs. Restored to 370 lbs.

## Patch records

2 records, 11 bytes total (plus the SNES header checksum):

| File offset | Bytes | Effect |
|---|---|---|
| `0x42CA5` | 1 | Mad Clown weight digit `9` → `7` (390 lbs → 370 lbs) |
| `0x42CD8` | 10 | Mr. Sandman's age / weight / record bytes — Macho Man's stats overwritten with Sandman's correct values |

Stats data format: `[country] $0A [age 2 digits] $0A [weight 2 digits] $0A [record] $00`. Font encoding: digits `0-9` = `$10-$19`, dash = `$F4`. Weight stores 2 digits; the renderer appends a literal "0" (so "27" displays as "270 lbs").

## Free space consumed

None. Both records are in-place edits to existing data.

## Patch in asm form

```asm
; spo_profile_stats_fix
; Corrects two profile-screen stat copy-paste errors in the original ROM.
; Font encoding: digits 0-9 = $10-$19, dash = $F4. Weight stores 2 digits;
; renderer appends a literal "0" (so "27" displays as "270 lbs").

; Fix 1 — Mad Clown weight: 390 lbs → 370 lbs
org $08C2A5
    db $17          ; was: $19 (digit '9' → '7')

; Fix 2 — Mr. Sandman stats: verbatim copy of Macho Man → correct JP values
; Data format: [country] $0A [age d1 d2] $0A [weight d1 d2] $0A [record] $00
; Original (Macho's stats): age 28, weight 230 lbs, record 29-3
; Corrected (Sandman's stats): age 30, weight 270 lbs, record 28-4
org $08C2D8
    db $13,$10      ; age "30"          (was: $12,$18 "28")
    db $0A
    db $12,$17      ; weight "27" (→ "270 lbs")  (was: $12,$13 "23")
    db $0A
    db $12,$18,$F4,$14  ; record "28-4"  (was: $12,$19,$F4,$13 "29-3")
```

(Plus the standard 4-byte SNES header checksum update at file `0x7FDC`.)

## Compatibility

- **Apply on top of**: original `Super Punch-Out!! (USA).sfc` ROM (MD5 `97fe7d7d2a1017f8480e60a365a373f0`)
- **Bundled into**: `spo_special_edition_v2.0.ips`
- **Conflicts with**: nothing in this repo
- **Cheat-code compatibility**: unaffected

## See also

For the full breakdown of the data format and original/replacement byte sequences, see the `spo_profile_stats_fix.ips` entry in [doc/TECHNICAL.md § 6](../TECHNICAL.md).
