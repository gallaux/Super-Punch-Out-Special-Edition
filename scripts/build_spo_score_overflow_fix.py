"""build_spo_score_overflow_fix.py — Cap the in-game score at 999,990.

The score is stored as 6 BCD digits, one digit per byte, at $0610-$0615
($0610 = ones ... $0615 = hundred-thousands). Every point/bonus value in the
game is a multiple of 10, so the ones digit is always 0 and the true maximum
representable score is 999,990.

CODE_01AA55 ($01:AA55) is the ONLY multi-digit BCD add routine in the ROM. It
adds a 6-digit source into a 6-digit destination and silently drops the carry
out of the 6th (most-significant) digit, so a running total that exceeds
999,990 wraps to a low value.

This patch caps the score by wrapping AA55's loop tail. AA55 ends with:
    $AA7C  CE D4 00   DEC $00D4        ; decrement remaining-digit count
    $AA7F  D0 DA      BNE $AA5B        ; loop while digits remain
    $AA81  60         RTS
We replace the `BNE $AA5B ; RTS` (3 bytes at $AA7F) with `JMP $FF55`. The stub
reproduces the loop-back, then on loop exit checks the carry-out of the last
digit. If set (the add overflowed past 999,990), it clamps the 6 destination
bytes to 999,990 (top five digits = 9, ones digit = 0).

Because every score add flows through AA55, this caps every path at once:
the per-match bonus tally, the end-of-circuit high-score screen, and any
SRAM-backed running total.

Apply on top of: Super Punch-Out!! (USA).sfc  MD5 97fe7d7d2a1017f8480e60a365a373f0

Free space: stub lives at $01:FF55-$01:FF7B (39 bytes) in the never-executed
copy of $00:FEC2 code at the tail of bank $01, clear of the interrupt vectors
at $01:FF90.

Usage:
    python build_spo_score_overflow_fix.py <vanilla.sfc>          # ship the patch
    python build_spo_score_overflow_fix.py <vanilla.sfc> --test   # + diagnostic ROM

--test additionally writes output/spo_score_overflow_fix_test.sfc with a
seed-once 950,000 starting score and a 1-HP opponent so a single won match
overflows past 999,990. That ROM is test-only: no IPS, never bundled into SE 2.0.
"""
import hashlib
import os

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT_IPS  = os.path.join(REPO, "patches", "standalone", "spo_score_overflow_fix.ips")
OUT_ROM  = os.path.join(REPO, "output", "spo_score_overflow_fix.sfc")
EXPECTED_BASE_MD5 = "97fe7d7d2a1017f8480e60a365a373f0"

# ── Hook: AA55 loop tail ─────────────────────────────────────────────────────
# $01:AA7F (file 0x0AA7F): D0 DA 60 (BNE $AA5B ; RTS) → 4C 55 FF (JMP $FF55)
HOOK_FILE = 0x00AA7F
HOOK_ORIG = bytes([0xD0, 0xDA, 0x60])
HOOK_NEW  = bytes([0x4C, 0x55, 0xFF])   # JMP $FF55

# ── Cap stub at $01:FF55 (file 0x0FF55) ──────────────────────────────────────
# The DEC $00D4 at $AA7C set Z right before our JMP:
#   Z=0 → more digits → JMP $AA5B (loop back)
#   Z=1 → last digit done → check carry-out (C); if set, clamp to 999,990
# Clamp writes 9 to dest+5..dest+1 and 0 to dest+0 (ones). $00D2 = dest_end after
# the loop (dest_start + 6); we DEX down through all six bytes.
STUB_SNES = 0xFF55
STUB_FILE = 1 * 0x8000 + (STUB_SNES - 0x8000)   # 0x0FF55
STUB = bytes([
    0xF0, 0x03,          # [0]  BEQ +3 → done (offset 5)
    0x4C, 0x5B, 0xAA,   # [2]  JMP $AA5B  (loop back)
    # done (offset 5):
    0x90, 0x1F,          # [5]  BCC +0x1F → RTS (offset 38)  (no overflow)
    0xAE, 0xD2, 0x00,   # [7]  LDX $00D2  (X = dest_end)
    0xA9, 0x09,          # [10] LDA #$09
    0xCA, 0x9D, 0x00, 0x00,   # [12] DEX; STA $0000,x  (dest+5 = 9)
    0xCA, 0x9D, 0x00, 0x00,   # [16] (dest+4 = 9)
    0xCA, 0x9D, 0x00, 0x00,   # [20] (dest+3 = 9)
    0xCA, 0x9D, 0x00, 0x00,   # [24] (dest+2 = 9)
    0xCA, 0x9D, 0x00, 0x00,   # [28] (dest+1 = 9)
    0xA9, 0x00,          # [32] LDA #$00   (ones digit)
    0xCA, 0x9D, 0x00, 0x00,   # [34] DEX; STA $0000,x  (dest+0 = 0)
    0x60,                # [38] RTS
])
assert len(STUB) == 39
assert STUB[6] == 0x1F, "BCC offset wrong"     # BCC at [5], PC after=7, 7+0x1F=38
assert STUB[38] == 0x60, "RTS missing"
assert STUB[2:5] == bytes([0x4C, 0x5B, 0xAA]), "JMP target wrong"
assert STUB_SNES + len(STUB) <= 0xFF90, "stub overflows into interrupt vectors"

# ── Test-only scaffolding (--test) ───────────────────────────────────────────
# NOT part of the shipped patch. --test additionally patches a seed-once starting
# score of 950,000 and a 1-HP opponent so a single won match overflows past
# 999,990, exercising the cap. Writes output/spo_score_overflow_fix_test.sfc
# (no IPS). Never bundled into SE 2.0.
#
# Seed: guarded by WRAM flag $7E:1D7F (0 on boot; clear of iron $1D71 / VS $1D74).
# First fight-init seeds score buffer $0610-$0615 and accumulator $0C58-$0C5D to
# 950,000 ($0615=9, $0614=5, rest 0), then sets the flag; later fights skip it so
# the score accumulates normally.
SEED_STUB_FILE = 0x3F0C2   # $07:F0C2 (126 B zone)
_seed_hdr = bytes([
    0xAF, 0x7F, 0x1D, 0x7E,   # LDA.l $7E1D7F  (seeded-flag)
    0xD0, 0x00,                # BNE → displaced  (offset patched below)
    0xA9, 0x01,                # LDA #$01
    0x8F, 0x7F, 0x1D, 0x7E,   # STA.l $7E1D7F  (mark seeded)
])
_seed_body = bytes([
    0x9C, 0x10, 0x06,   # STZ $0610
    0x9C, 0x11, 0x06,   # STZ $0611
    0x9C, 0x12, 0x06,   # STZ $0612
    0x9C, 0x13, 0x06,   # STZ $0613
    0x9C, 0x58, 0x0C,   # STZ $0C58
    0x9C, 0x59, 0x0C,   # STZ $0C59
    0x9C, 0x5A, 0x0C,   # STZ $0C5A
    0x9C, 0x5B, 0x0C,   # STZ $0C5B
    0xA9, 0x05,          # LDA #$05  ten-thousands
    0x8D, 0x14, 0x06,   # STA $0614
    0x8D, 0x5C, 0x0C,   # STA $0C5C
    0xA9, 0x09,          # LDA #$09  hundred-thousands
    0x8D, 0x15, 0x06,   # STA $0615
    0x8D, 0x5D, 0x0C,   # STA $0C5D
])
_seed_disp = bytes([
    0xA2, 0x00, 0x00,   # LDX #$0000   (displaced fight-init)
    0xA0, 0xE0, 0x3E,   # LDY #$3EE0
    0x6B,                # RTL
])
_disp = len(_seed_hdr) + len(_seed_body)
_seed_hdr = _seed_hdr[:5] + bytes([_disp - 6]) + _seed_hdr[6:]  # BNE operand
SEED_STUB = _seed_hdr + _seed_body + _seed_disp
assert SEED_STUB[_disp] == 0xA2 and SEED_STUB[_disp + 3] == 0xA0
assert SEED_STUB[-1] == 0x6B
assert SEED_STUB_FILE + len(SEED_STUB) <= 0x3F140

FIGHT_HOOK_FILE = 0x017E5
FIGHT_HOOK_ORIG = bytes([0xA2, 0x00, 0x00, 0xA0, 0xE0, 0x3E])
FIGHT_HOOK_NEW  = bytes([0x22, 0xC2, 0xF0, 0x07, 0xEA, 0xEA])   # JSL $07:F0C2 + 2×NOP

# Dev one-hit: opp HP = 1. $00:96AA (file 0x016AA): STA $099F; STZ $089C.
OPP_HOOK_FILE = 0x016AA
OPP_HOOK_ORIG = bytes([0x8D, 0x9F, 0x09, 0x9C, 0x9C, 0x08])
OPP_HOOK_NEW  = bytes([0x22, 0xB0, 0xFF, 0x02, 0xEA, 0xEA])   # JSL $02:FFB0 + 2×NOP
OPP_STUB_FILE = 0x17FB0   # $02:FFB0
OPP_STUB = bytes([
    0xA9, 0x01,          # LDA #$01
    0x8D, 0x9F, 0x09,   # STA $099F   opp HP = 1
    0xA9, 0x02,          # LDA #$02
    0x8D, 0x9D, 0x09,   # STA $099D   opp KD count = 2
    0x9C, 0x9C, 0x08,   # STZ $089C   (displaced)
    0x6B,                # RTL
])
assert len(OPP_STUB) == 14
assert OPP_STUB_FILE + len(OPP_STUB) <= 0x17FE4
OUT_TEST_ROM = os.path.join(REPO, "output", "spo_score_overflow_fix_test.sfc")


def snes_checksum(rom):
    rom[0x7FDC:0x7FDE] = b"\xFF\xFF"
    rom[0x7FDE:0x7FE0] = b"\x00\x00"
    chk = sum(rom) & 0xFFFF
    cmp_ = chk ^ 0xFFFF
    rom[0x7FDC:0x7FE0] = bytes([cmp_ & 0xFF, (cmp_ >> 8) & 0xFF,
                                 chk  & 0xFF, (chk  >> 8) & 0xFF])
    return chk


def build_ips(records):
    out = bytearray(b"PATCH")
    for off, data in sorted(records, key=lambda r: r[0]):
        out += off.to_bytes(3, "big")
        out += len(data).to_bytes(2, "big")
        out += data
    out += b"EOF"
    return bytes(out)


def main():
    import argparse
    ap = argparse.ArgumentParser(description="Build spo_score_overflow_fix.")
    ap.add_argument("base", help="vanilla ROM path")
    ap.add_argument("--test", action="store_true",
                    help="also build a test ROM (output/spo_score_overflow_fix_test.sfc) "
                         "with a seed-once 950,000 score + 1-HP opponent so a win "
                         "overflows; not shipped, no IPS emitted")
    args = ap.parse_args()

    with open(args.base, "rb") as f:
        rom = bytearray(f.read())

    md5 = hashlib.md5(rom).hexdigest()
    assert md5 == EXPECTED_BASE_MD5, \
        f"base ROM MD5 mismatch: got {md5}, expected {EXPECTED_BASE_MD5}"

    assert bytes(rom[HOOK_FILE:HOOK_FILE+3]) == HOOK_ORIG, \
        f"Hook site mismatch: {bytes(rom[HOOK_FILE:HOOK_FILE+3]).hex()}"

    rom[HOOK_FILE:HOOK_FILE+3]     = HOOK_NEW
    rom[STUB_FILE:STUB_FILE+len(STUB)] = STUB

    chk = snes_checksum(rom)
    print(f"Checksum: ${chk:04X}")

    records = [
        (HOOK_FILE, HOOK_NEW),
        (STUB_FILE, STUB),
        (0x7FDC, bytes(rom[0x7FDC:0x7FE0])),
    ]

    os.makedirs(os.path.dirname(OUT_IPS), exist_ok=True)
    os.makedirs(os.path.dirname(OUT_ROM), exist_ok=True)
    with open(OUT_IPS, "wb") as f:
        f.write(build_ips(records))
    with open(OUT_ROM, "wb") as f:
        f.write(rom)

    total = sum(len(d) for _, d in records)
    print(f"wrote {OUT_IPS}  ({len(records)} records, {total}B)")
    print(f"wrote {OUT_ROM}  MD5 {hashlib.md5(rom).hexdigest()}")

    if args.test:
        assert bytes(rom[FIGHT_HOOK_FILE:FIGHT_HOOK_FILE+6]) == FIGHT_HOOK_ORIG
        assert bytes(rom[OPP_HOOK_FILE:OPP_HOOK_FILE+6]) == OPP_HOOK_ORIG
        rom[SEED_STUB_FILE:SEED_STUB_FILE+len(SEED_STUB)] = SEED_STUB
        rom[FIGHT_HOOK_FILE:FIGHT_HOOK_FILE+6]            = FIGHT_HOOK_NEW
        rom[OPP_HOOK_FILE:OPP_HOOK_FILE+6]                = OPP_HOOK_NEW
        rom[OPP_STUB_FILE:OPP_STUB_FILE+len(OPP_STUB)]    = OPP_STUB
        snes_checksum(rom)
        with open(OUT_TEST_ROM, "wb") as f:
            f.write(rom)
        print(f"wrote {OUT_TEST_ROM}  (test-only: seed 950,000 + 1-HP opponent)")


if __name__ == "__main__":
    main()
