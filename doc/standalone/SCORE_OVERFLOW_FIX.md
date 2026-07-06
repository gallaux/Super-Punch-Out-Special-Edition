# `spo_score_overflow_fix.ips` — Summary

Caps the running score at **999,990** so the 6-digit on-screen total can never overflow past the maximum the game can represent.
Without this, a circuit total that exceeds 999,990 silently wraps to a low number (e.g. 1,014,000 shows as 14,000) because the score-tally adder drops the carry out of the top digit.

<img width="256" height="224" alt="Super Punch-Out!! (USA) Score Overflow Fix_001" src="https://github.com/user-attachments/assets/4604cb6d-5606-4c09-a08e-0799a963798f" />
<img width="256" height="224" alt="Super Punch-Out!! (USA) Score Overflow Fix_002" src="https://github.com/user-attachments/assets/d527bc5b-de1c-4fcd-9852-1e5a5011d4bd" />

## What it does

- Clamps the score to **999,990** whenever a score/bonus addition would push the running total past that value.
- Covers **every** scoring path at once — per-match bonus tally (technical points, stamina-remaining bonus, time bonus, no-rematch bonus) and the end-of-circuit high-score screen — because all of them funnel through the same BCD add routine.
- The capped value (999,990) is consistent everywhere the score is shown or stored: the tally screen, the SRAM-backed running total, Records View → Personal Records → Circuit Best, and the high-score record.

## Why 999,990 and not 999,999

Every point award and bonus in Super Punch-Out!! is a **multiple of 10** — the ones digit is structurally always `0`. The score is stored as six BCD digits (one decimal digit per byte), so the largest value the game can ever legitimately hold and display is **999,990**, not 999,999.

The ones digit must stay `0`: the engine re-derives/normalizes it in several places (the next match's tally start value, the Records View circuit-best, and the SRAM round-trip), so a `9` in the ones position would not survive anyway. 999,990 is the only value that stays consistent across all screens.

## Vanilla score-count logic (background)

The player's match/circuit score lives in WRAM at **`$0610`–`$0615`**, stored as **Binary-Coded Decimal, one decimal digit per byte** (little-endian by significance):

| Address | Digit |
|---|---|
| `$0610` | ones (always 0 in normal play) |
| `$0611` | tens |
| `$0612` | hundreds |
| `$0613` | thousands |
| `$0614` | ten-thousands |
| `$0615` | hundred-thousands |

Example: 941,923 → `$0615=$09, $0614=$04, $0613=$01, $0612=$09, $0611=$02, $0610=$03`. (All real scores end in `$0610=$00` because point values are ×10.)

### The single BCD adder: `CODE_01AA55` (`$01:AA55`)

`CODE_01AA55` is the **only** multi-digit BCD add routine in the entire ROM. It adds a 6-digit source into a 6-digit destination, digit by digit, with carry propagation. Its signature:

- `X` = source pointer, `Y` = destination pointer (both absolute, DBR=$00).
- `$00D2` = a second destination pointer where each result digit is written; it is **incremented once per digit**, so after the 6-digit loop `$00D2` points to `dest_start + 6`.
- `$00D4` = digit counter, initialized to 6, decremented each iteration.

The loop body (per digit): `LDA src ; ADC dst ; SEC ; SBC #$0A ; BCC no_carry`; the `BCC`/fall-through path either adds `$0A` back and clears carry (digit stayed 0–9) or leaves carry set (digit ≥ 10, carry into next digit).

The score-tally chains issue several `JSR CODE_01AA55` calls to accumulate the per-match bonuses into the running total. Examples of tally chains that feed the score: `CODE_01A31E` (per-match, dest `$0C30`/`$0C40`) and `CODE_01A993` (end-of-circuit high-score screen). The final result is copied back into `$0610`–`$0615` for display and saved to SRAM.

### The overflow bug

`CODE_01AA55` processes exactly 6 digits and then returns. The **carry out of the 6th (most-significant) digit is silently dropped** — there is no 7th digit and no overflow handling. So when a running total exceeds 999,990:

```
  990,000 + 47,570 = 1,037,570   (true sum)
```

the top-digit carry is lost and the stored value wraps to the low 6 digits (`037,570` in this example). The displayed total collapses to a small number instead of pinning at the maximum. This patch adds the missing overflow clamp.

## How the fix works

`CODE_01AA55` ends with:

```
$AA7C  CE D4 00   DEC $00D4        ; decrement digit counter
$AA7F  D0 DA      BNE $AA5B        ; loop while digits remain
$AA81  60         RTS
```

The patch replaces the 3-byte `BNE $AA5B ; RTS` at **`$01:AA7F`** with `JMP <stub>`. The stub reproduces the loop-back, and on loop exit inspects the **carry-out of the last digit**:

- Carry clear → no overflow → `RTS` (result untouched).
- Carry set → overflow → clamp the six destination bytes to **999,990** (write `$09` to `dest+5..dest+1` and `$00` to `dest+0`, the ones digit), then `RTS`.

The destination base is recovered from `$00D2` (which points to `dest_end` after the loop); the stub does `LDX $00D2` then walks down with `DEX` through all six bytes.
Because the hook is at the shared adder, **every** overflowing add on **every** score path is capped in one place — no per-path hooks needed, and the score-tally tween animates toward an already-capped buffer.

The `DEC $00D4` immediately before the `JMP` sets the CPU Z flag, which the stub uses to decide loop-back (`Z=0`, digits remain) vs. done (`Z=1`, last digit).

## Cap stub (asm form)

Lives at **`$01:FF55`** (file `0x0FF55`), 39 bytes, inside the `UNK_01D722` free zone (see [Free space consumed](#free-space-consumed)):

```asm
; Hook at $01:AA7F replaces "BNE $AA5B ; RTS" with "JMP $FF55".
; On entry the Z flag reflects DEC $00D4 (Z=0 more digits, Z=1 last digit).
org $01FF55
cap_stub:
    BEQ .done          ; F0 03   last digit finished -> check overflow
    JMP $AA5B          ; 4C 5B AA more digits -> resume the adder loop
.done:
    BCC .ret           ; 90 1F   carry clear -> no overflow, leave result
    LDX $00D2          ; AE D2 00 X = dest_end (dest_start + 6)
    LDA #$09           ; A9 09
    DEX : STA $0000,x  ; CA 9D 00 00   dest+5 = 9
    DEX : STA $0000,x  ; CA 9D 00 00   dest+4 = 9
    DEX : STA $0000,x  ; CA 9D 00 00   dest+3 = 9
    DEX : STA $0000,x  ; CA 9D 00 00   dest+2 = 9
    DEX : STA $0000,x  ; CA 9D 00 00   dest+1 = 9
    LDA #$00           ; A9 00
    DEX : STA $0000,x  ; CA 9D 00 00   dest+0 = 0  (ones digit)
.ret:
    RTS                ; 60
```

Raw bytes (39):
`F0 03 4C 5B AA 90 1F AE D2 00 A9 09 CA 9D 00 00 CA 9D 00 00 CA 9D 00 00 CA 9D 00 00 CA 9D 00 00 A9 00 CA 9D 00 00 60`

## Patch records

3 records, 46 bytes total (including the SNES header checksum):

| File offset | SNES | Bytes | Effect |
|---|---|---|---|
| `0x0AA7F` | `$01:AA7F` | 3 | Adder loop tail `BNE $AA5B ; RTS` → `JMP $FF55` |
| `0x0FF55` | `$01:FF55` | 39 | Overflow-detect + clamp-to-999,990 stub |
| `0x07FDC` | `$00:FFDC` | 4 | SNES header checksum |

## Free space consumed

- **Bank `$01`**: 39 bytes at **`$01:FF55`–`$01:FF7B`**, inside the `UNK_01D722` free zone — a copy of `$00:FEC2`, never executed at runtime, sitting before the interrupt-vector table at `$01:FF90`. `$01:FF55–$01:FF8F` (~59 B) was free before this patch; after it, ~20 bytes remain free at `$01:FF7C–$01:FF8F`. See TECHNICAL.md's bank-`$01` free-space map.
- No other free space is used; the hook is a 3-byte in-place edit.

## Compatibility

- **Apply on top of**: original `Super Punch-Out!! (USA).sfc` ROM (MD5 `97fe7d7d2a1017f8480e60a365a373f0`)
- **Conflicts with**: nothing. The stub lives at `$01:FF55`, byte-disjoint from every other standalone.
- **Byte-disjoint** from every other standalone, apart from the shared SNES header checksum at `$00:FFDC`, which the SE 2.0 bundle re-stamps once at the end.
- **Cheat-code compatibility**: unaffected (only the BCD adder's overflow behavior changes; no fight-state or opponent machinery touched).
- **Bundled into**: `spo_special_edition_v2.0.ips`.

## Building

Built by `scripts/build_spo_score_overflow_fix.py`:

```
python scripts/build_spo_score_overflow_fix.py <vanilla.sfc>
```

The builder applies the 3 records to a vanilla ROM, stamps the SNES header checksum, and writes `patches/standalone/spo_score_overflow_fix.ips` and `output/spo_score_overflow_fix.sfc`.

---

## Testing

To verify the cap: seed a high score, win a fight, and confirm the total clamps to 999,990 across the tally screen, the next match's starting total, Records View → Circuit Best, and the SRAM-backed high-score record.
The clamp applies identically whether the patch is applied standalone or bundled in `spo_special_edition_v2.0`, since both carry the same `$01:FF55` stub.

### Test ROM (test-only, not shipped)
The build script has a `--test` flag that additionally writes a diagnostic ROM (`output/spo_score_overflow_fix_test.sfc`) using the same `$01:FF55` cap hook as the shipped patch, plus seed scaffolding to exercise the overflow quickly:

```
python scripts/build_spo_score_overflow_fix.py <vanilla.sfc>           # ship the patch
python scripts/build_spo_score_overflow_fix.py <vanilla.sfc> --test    # + diagnostic ROM
```

With `--test`, a seed-once (`$7E:1D7F` flag) starting score of 950,000 and a 1-HP opponent are patched in, so the next won match overflows past 999,990 and pins at the cap. The test ROM is scaffolding: no IPS is emitted and it is **never** bundled into SE 2.0.

## Key facts / addresses

- Vanilla ROM: original `Super Punch-Out!! (USA).sfc`, MD5 `97fe7d7d2a1017f8480e60a365a373f0`, 2 MB LoROM.
- Score buffer: `$0610`–`$0615`, BCD 1 digit/byte, `$0610` = ones. Legit max = **999,990** (all scores ×10).
- Only BCD adder: `CODE_01AA55` (`$01:AA55`); overflow bug = dropped carry out of digit 6.
- Hook: adder loop tail at file `0x0AA7F` (vanilla `D0 DA 60` = `BNE $AA5B ; RTS`) → `4C 55 FF` (`JMP $FF55`).
- Stub: `$01:FF55` (file `0x0FF55`), 39 B, inside the `UNK_01D722` free zone.
- Checksum: SNES header at file `0x7FDC` (SE 2.0 bundle re-stamps once).
