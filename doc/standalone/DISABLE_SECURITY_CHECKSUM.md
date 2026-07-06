# `spo_disable_security_checksum.ips` — Summary

Disables the World Circuit completion checksum that locks the Special Circuit when using save states, emulators (SNES Classic, Switch NSO), or patched ROMs.

## What it does

The original ROM checks an internal SRAM checksum after completing World Circuit before unlocking Special Circuit. The check is intended to detect tampering, but it also fires on completely legitimate setups — emulators that snapshot SRAM, the SNES Classic / Switch NSO virtual consoles, and any ROM with even cosmetic patches applied. The result is that Special Circuit silently fails to unlock on a clean playthrough.

This patch forces the check's result to `0` (unlocked) regardless of the SRAM contents.

## Patch records

1 record, 2 bytes total (plus the SNES header checksum):

| File offset | Old | New | Effect |
|---|---|---|---|
| `0x003C23` | `05 D5` (`ORA $D5`) | `A9 00` (`LDA #$00`) | At SNES `$00:BC23`, force A=0 before the SRAM-write store, regardless of checksum result |

## Free space consumed

None. Single in-place edit.

## Patch in asm form

```asm
; spo_disable_security_checksum
; Forces the World Circuit completion checksum result to 0 (unlocked)
; regardless of SRAM contents, so Special Circuit unlocks on every setup.

org $00BC23
    LDA #$00        ; was: ORA $D5 — force A=0 before the SRAM-write store
```

(Plus the standard 4-byte SNES header checksum update at file `0x7FDC`.)

## Compatibility

- **Apply on top of**: original `Super Punch-Out!! (USA).sfc` ROM (MD5 `97fe7d7d2a1017f8480e60a365a373f0`)
- **Bundled into**: `spo_special_edition_v2.0.ips` (this fix is the sole source of the Special Circuit lock bypass in the SE bundle)
- **Cheat-code compatibility**: unaffected

## See also

For the surrounding context — where the checksum routine sits, how it interacts with the Special Circuit unlock state, and the SRAM layout it writes to — see the `spo_disable_security_checksum.ips` entry in [doc/TECHNICAL.md § 6](../TECHNICAL.md).
