# `spo_how_to_typo_fix.ips` — Summary

Fixes a single-letter typo in the in-game tutorial demo. The HOW-TO-PLAY demo describes the Knock Out Punch with the line:

> *Knock Out Punches can be highly **devestating**!*

The correct spelling is **devastating**. This patch flips one byte to fix the spelling.

**Note:** as far as we can tell, this typo has not been documented anywhere prior to this patch — not on TCRF, not in any known FAQ, not on the fan wiki. It's easy to miss because the HOW-TO-PLAY demo is a quick attract sequence most players skip. The string lives deep inside the tutorial animation data and the single misspelled letter (`e` instead of `a` at the third character of "devestating") is subtle enough that it went unnoticed for 30 years.

<img width="256" height="224" alt="Super Punch-Out!! (USA) How To Typo Fix_001" src="https://github.com/user-attachments/assets/1720fc5a-e952-4bb4-a013-30f6a45b7063" />

## What it fixes

- The word `devestating` → `devastating` in the UPPERCUT lesson string shown during the in-game tutorial demo.

## Patch records

1 record, 1 byte total (plus the SNES header checksum):

| File offset | Bytes | Effect |
|---|---|---|
| `0x43876` | 1 | Tutorial-text font index `$0A` (`e`) → `$10` (`a`) — the third letter of `devestating` |

The tutorial demo's text strings live in `DATA_08B83E` (SNES `$08:B83E`) and use a custom run-length-like font encoding where each byte is a single character tile index. The relevant 12-character segment encodes `devestating!` as:

```
8C 1C 0A 3C 0A 24 08 10 08 1E 06 20 16
   d  e  v  e  s  t  a  t  i  n  g  !
```

`$8C` is the run length (12 chars); the bytes that follow are the per-character tile indices. Patching the 4th byte from `$0A` (`e`) to `$10` (`a`) re-spells the word as `devastating!`.

## Free space consumed

None. The patch is a single in-place byte edit.

## Patch in asm form

For reference, the patch expressed as an asm overlay:

```asm
; Fix "devestating!" -> "devastating!" in the UPPERCUT tutorial-demo string.
; The text lives in DATA_08B83E and uses a custom font where each byte after a
; $8X length prefix is one character tile index. In this encoding 'e' = $0A
; and 'a' = $10. We patch the 4th character byte of the 12-char run.

org $08B876
    db $10        ; was $0A ('e'), now $10 ('a')
```

(Plus the standard 4-byte SNES header checksum update at file `0x7FDC`, which every patch in this repo carries.)

## Compatibility

- **Apply on top of**: original `Super Punch-Out!! (USA).sfc` ROM (MD5 `97fe7d7d2a1017f8480e60a365a373f0`)
- **Conflicts with**: nothing in this repo
- **Cheat-code compatibility**: unaffected
- **Bundled into**: `spo_special_edition_v2.0.ips`

## See also

- [`PROFILE_STATS_FIX.md`](PROFILE_STATS_FIX.md) — another small text/data correction bundled into Special Edition.
