"""build_spo_alt_opponents_colors.py — Per-opponent alternate palettes for all 16 fighters.

Ships merged with the ROM expansion (ExLoROM, 2MB → 2.5MB).
Palette data and the fight-init/opcode stubs live in expansion space (bank $40,
file 0x200000+). The MVN-replacement stub lives in bank $00 free space,
reached via intra-bank JSR.

CRITICAL: JSL/JMP to bank $40 for code execution crashes in emulators — bank $40
is mapped for DATA reads but not as executable ROM. All executable stubs must be
in bank $00. MVN with src=$40 operand works fine (reads data without changing PBR).

This is a standalone patch that chains through the alt-glove Hook 1
(JSL $0D:FDD2 at $00:97E5), so spo_alt_glove_colors.ips must be applied first.
The builder applies alt-glove to the base ROM, then diffs the result against
vanilla+alt-glove — the emitted IPS contains only alt-opp's own bytes.

## Hook sites

### Hook 1: $00:97E5 (file 0x017E5) — body sprite + small portrait (in-fight)
alt-glove has: 22 D2 FD 0D EA EA  (JSL $0D:FDD2; NOP; NOP)
Replaced:      22 7E 84 40 EA EA  (JSL $40:847E; NOP; NOP)
Fires at fight-init after the DMA that loads the fighter palette block (256B) to
WRAM $0540..$063F. Pal 0 → $0540..$055F (small portrait); Pal 2 → $0580..$059F
(body). Stub overwrites those WRAM regions with the alt palettes, then chains to
$0D:FDD2 (so alt gloves still runs).

### Hook 6: $01:99D4 (file 0x099D4) — Pal 2 restore (bytecode opcode $3C)
Original: E2 20 A9 05  (SEP #$20; LDA #$05)
Replaced: 22 .. .. 40  (JSL $40:84FC)
Fires on the opcode-$3C palette-restore trigger (e.g. Masked Muscle spit-end),
which re-copies the body Pal 2 mid-fight. Stub redirects the source to the alt
body palette when active, else runs vanilla.

### Hook 2: $00:9B91 (file 0x01B91) — large portrait
Original: 54 00 10  (MVN $00,$10  — 3 bytes)
Replaced: 20 18 FE  (JSR $FE18   — 3 bytes, intra-bank)
Only the MVN is replaced. PLB ($00:9B94) and SEP #$20 ($00:9B95) remain in the
caller. Stub at $00:FE18 does alt or vanilla MVN and RTS. MVN src=$40 reads from
expansion space without executing there — CPU stays in bank $00 throughout.

## Gating (WRAM flags checked by the stubs)

Hook 1: iron flag ($7E:1D71) OR P1 SELECT ($7E:0091 bit 5)
        OR (VS mode $7E:1D74==1 AND P2 SELECT $7E:00A5 bit 5)
Hook 6: Pal 2 restore flag ($7E:1D76) AND script dest LSB == $82
Hook 2: iron flag ($7E:1D71)

## Expansion space layout (bank $40 = file 0x200000 + offset - 0x8000)

  $40:847E  Hook 1 stub (fight-init body + small portrait)
  $40:84FC  Hook 6 stub (opcode-$3C Pal 2 restore)
  $40:8580  Body palette data          — 16 × 32B = 512B
  $40:8780  Small portrait palette data — 16 × 32B = 512B
  $40:8980  Large portrait palette data — 16 × 32B = 512B

Bank $00 free space (UNK_00F5D0 zone):
  $00:FE18  Hook 2 stub (large portrait)

## Palette data

Authored overrides for all 16 fighters in every context:
- Body (Pal 2) and small portrait (Pal 0): per-fighter slot overrides; any slot
  not listed falls back to vanilla.
- Large portrait: per-fighter slot overrides, plus a unified circuit backdrop
  (darker #B8858D / lighter #E9BFC9) written into each fighter's backdrop slots.
  Backdrop slots are CC/CD for most fighters; CD/CE for Narcis (12), Rick (14),
  Nick (15) — see LARGE_BG_SLOTS.
- Bonus vanilla fix: Bear Hugger large-portrait CF forced to pure white $7FFF
  (shipped ROM had a slightly blue-tinted $7F9B).

Usage:
    python build_spo_alt_opponents_colors.py <vanilla.sfc> [out.sfc]
"""
import os, sys, hashlib
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from ips_patcher import parse_ips

REPO      = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ALT_GLOVE = os.path.join(REPO, 'patches', 'standalone', 'spo_alt_glove_colors.ips')
OUT_IPS   = os.path.join(REPO, 'patches', 'standalone', 'spo_alt_opponents_colors.ips')
EXPECTED_MD5 = '97fe7d7d2a1017f8480e60a365a373f0'

# ----------------------------------------------------------------------
# Expansion space constants
# ----------------------------------------------------------------------
BANK40_FILE = 0x200000      # file offset of $40:8000 (ExLoROM expansion)
STUB_BANK   = 0x40          # ExLoROM: expansion lives in banks $40-$4F

def snes40(offset):
    """SNES $40:offset → file offset (ExLoROM expansion)."""
    return BANK40_FILE + (offset - 0x8000)

def snes00(offset):
    """SNES $00:offset → file offset."""
    return offset - 0x8000

HOOK1_STUB_SNES   = 0x847E   # $40:847E  — hook1 stub (fight-init: set alt-active flag)
HOOK6_STUB_SNES   = 0x84FC   # $40:84FC  — hook6 stub
HOOK2_STUB_SNES   = 0xFE18   # $00:FE18  — hook2 stub (large portrait, bank $00 free space)
BODY_PAL_SNES     = 0x8580   # $40:8580  — 16 × 32B
SMALL_PAL_SNES    = 0x8780   # $40:8780  — 16 × 32B
LARGE_PAL_SNES    = 0x8980   # $40:8980  — 16 × 32B

def long_op(snes_offset):
    """3-byte operand for JSL $40:snes_offset."""
    snes = (STUB_BANK << 16) | snes_offset
    return bytes([snes & 0xFF, (snes >> 8) & 0xFF, (snes >> 16) & 0xFF])

# ----------------------------------------------------------------------
# Palette utilities
# ----------------------------------------------------------------------

def bgr555_to_rgb8(word):
    r5 =  word        & 0x1F
    g5 = (word >>  5) & 0x1F
    b5 = (word >> 10) & 0x1F
    r = (r5 << 3) | (r5 >> 2)
    g = (g5 << 3) | (g5 >> 2)
    b = (b5 << 3) | (b5 >> 2)
    return r, g, b

def rgb8_to_bgr555(r, g, b):
    return ((b >> 3) << 10) | ((g >> 3) << 5) | (r >> 3)

def sepia(r, g, b):
    """Classic sepia tone transform."""
    sr = min(255, int(r * 0.393 + g * 0.769 + b * 0.189))
    sg = min(255, int(r * 0.349 + g * 0.686 + b * 0.168))
    sb = min(255, int(r * 0.272 + g * 0.534 + b * 0.131))
    return sr, sg, sb

def apply_sepia_to_palette(pal_bytes):
    """Apply sepia to all 16 slots of a 32-byte BGR555 palette.
    Slot 0 (SNES backdrop $3800) is left untouched."""
    out = bytearray(pal_bytes)
    for i in range(1, 16):
        word = pal_bytes[i*2] | (pal_bytes[i*2+1] << 8)
        r, g, b = bgr555_to_rgb8(word)
        sr, sg, sb = sepia(r, g, b)
        new_word = rgb8_to_bgr555(sr, sg, sb)
        out[i*2]   = new_word & 0xFF
        out[i*2+1] = (new_word >> 8) & 0xFF
    return bytes(out)

# Per-fighter body (Pal 2) alt palette overrides.
# Only changed slots listed; vanilla used for all others.
# Format: { slot_index: (R, G, B) }

# Fighter 0 — Gabby Jay
FIGHTER_BODY_OVERRIDES = {
    0: {
        0x1: (0x50, 0x00, 0x00),
        0x2: (0x70, 0x28, 0x10),
        0x7: (0x00, 0x00, 0x00),
        0x8: (0x60, 0x14, 0x1A),
        0x9: (0x84, 0x28, 0x1E),
        0xA: (0xB6, 0x5B, 0x51),
        0xB: (0x58, 0x58, 0x68),
        0xC: (0x88, 0x88, 0xAA),
        0xD: (0xFF, 0xFF, 0xFF),
    },
    # Fighter 1 — Bear Hugger
    1: {
        0x1: (0x1D, 0x06, 0x02),
        0x7: (0x72, 0x27, 0x01),
        0x8: (0xE3, 0x4D, 0x01),
        0x9: (0xFA, 0x7A, 0x39),
        0xA: (0xD8, 0xD7, 0xD3),
        0xB: (0x00, 0x0D, 0x2A),
        0xC: (0x06, 0x19, 0x38),
        0xD: (0x15, 0x2C, 0x52),
        0xE: (0x33, 0x4B, 0x74),
    },
    # Fighter 5 — Dragon Chan
    5: {
        0x2: (0x14, 0x14, 0x20),
        0x7: (0x2F, 0x12, 0x01),
        0x8: (0x83, 0x33, 0x03),
        0x9: (0xCE, 0x5E, 0x1B),
        0xA: (0xEF, 0x8E, 0x53),
        0xB: (0x00, 0x00, 0x00),
        0xC: (0x0A, 0x0B, 0x15),
        0xD: (0x17, 0x19, 0x2C),
        0xE: (0x3A, 0x35, 0x48),
    },
    # Fighter 2 — Piston Hurricane
    2: {
        0x1: (0x0E, 0x01, 0x01),
        0x2: (0x47, 0x13, 0x08),
        0x3: (0x44, 0x12, 0x07),
        0x4: (0xBC, 0x62, 0x4B),
        0x5: (0xD8, 0x93, 0x7C),
        0x6: (0xF0, 0xBA, 0xA3),
        0x7: (0x40, 0x00, 0x00),
        0x8: (0xC8, 0x00, 0x00),
        0x9: (0xE0, 0x68, 0x00),
        0xA: (0xE0, 0xE0, 0x00),
        0xB: (0x00, 0x20, 0x00),
        0xC: (0x10, 0x40, 0x00),
        0xD: (0x40, 0x70, 0x30),
        0xE: (0xE0, 0x68, 0x00),
    },
    # Fighter 3 — Bald Bull
    3: {
        0x1: (0x1C, 0x1C, 0x1C),
        0x2: (0xAC, 0x07, 0x9A),
        0x3: (0x44, 0x3F, 0x64),
        0x4: (0x72, 0x7E, 0xB1),
        0x5: (0x86, 0x9C, 0xCA),
        0x6: (0x96, 0xB1, 0xDF),
        0x7: (0x26, 0x1F, 0x2D),
        0x8: (0xA1, 0x01, 0x72),
        0x9: (0xC6, 0x21, 0xB8),
        0xA: (0xF6, 0x61, 0xE3),
        0xB: (0x78, 0x7B, 0x85),
        0xC: (0xCD, 0xCD, 0xC5),
        0xD: (0xFE, 0xFE, 0xF7),
        0xE: (0x79, 0x00, 0x6C),
    },
    # Fighter 4 — Bob Charlie
    4: {
        0x1: (0x00, 0x00, 0x00),
        0x2: (0x00, 0x01, 0x00),
        0x3: (0x20, 0x00, 0x00),
        0x4: (0x55, 0x22, 0x11),
        0x5: (0x88, 0x55, 0x33),
        0x6: (0x98, 0x6E, 0x51),
        0x7: (0x00, 0x00, 0x30),
        0x8: (0x00, 0x46, 0xCE),
        0x9: (0x67, 0x88, 0xB9),
        0xA: (0xDE, 0xD6, 0xFF),
        0xB: (0x20, 0x00, 0x00),
        0xC: (0x10, 0x18, 0x10),
        0xD: (0x21, 0x28, 0x21),
        0xE: (0x84, 0x00, 0x00),
    },
    # Fighter 8 — Aran Ryan
    8: {
        0x1: (0x00, 0x00, 0x00),
        0x2: (0x1C, 0x00, 0x00),
        0x3: (0x54, 0x34, 0x04),
        0x4: (0xC6, 0x98, 0x7A),
        0x5: (0xFF, 0xCC, 0x99),
        0x6: (0xFC, 0xEB, 0xD9),
        0x7: (0x34, 0x01, 0x01),
        0x8: (0xAA, 0x00, 0x00),
        0x9: (0xD7, 0x28, 0x28),
        0xA: (0xF7, 0xA5, 0xA5),
        0xB: (0x20, 0x13, 0x40),
        0xC: (0x4A, 0x2C, 0x93),
        0xD: (0x6D, 0x4F, 0xE6),
        0xE: (0x99, 0x77, 0x44),
    },
    # Fighter 10 — Mad Clown
    10: {
        0x1: (0x1B, 0x1D, 0x28),
        0x2: (0xBD, 0xBD, 0xCE),
        0x3: (0x47, 0x46, 0x46),
        0x4: (0x8F, 0x8E, 0x8E),
        0x5: (0xB9, 0xB8, 0xB8),
        0x6: (0xE3, 0xE1, 0xE0),
        0x7: (0x08, 0x10, 0x52),
        0x8: (0x1B, 0x1F, 0x38),
        0x9: (0x4B, 0x50, 0x71),
        0xA: (0xB4, 0xB4, 0xB4),
        0xB: (0x31, 0x00, 0x00),
        0xC: (0x6C, 0x01, 0x01),
        0xD: (0x9C, 0x06, 0x10),
        0xE: (0xC8, 0x44, 0x4D),
    },
    # Fighter 12 — Narcis Prince
    12: {
        0x1: (0x51, 0x3C, 0x73),
        0x2: (0x85, 0x78, 0xBB),
        0x3: (0xB3, 0xA5, 0xE3),
        0x4: (0x02, 0x02, 0x08),
        0x5: (0xB0, 0x6A, 0x2B),
        0x6: (0xEC, 0xA7, 0x69),
        0x7: (0xF9, 0xD6, 0xB1),
        0x8: (0x0C, 0x10, 0x12),
        0x9: (0x12, 0x8D, 0x63),
        0xA: (0xA0, 0xD5, 0xBC),
        0xB: (0x24, 0x24, 0x88),
        0xC: (0x72, 0x72, 0xF9),
        0xD: (0x19, 0x20, 0x23),
        0xE: (0x42, 0x51, 0x57),
    },
    # Fighter 6 — Masked Muscle
    6: {
        0x1: (0x00, 0x10, 0x0B),
        0x2: (0x01, 0x2F, 0x21),
        0x7: (0x10, 0x0B, 0x00),
        0x8: (0xC2, 0xC2, 0xC4),
        0x9: (0xDE, 0xDE, 0xE0),
        0xA: (0x00, 0x67, 0x47),
        0xB: (0x02, 0x4D, 0x36),
        0xC: (0xCD, 0x11, 0x27),
        0xD: (0xA7, 0x03, 0x16),
        0xE: (0x98, 0x00, 0x00),
    },
    # Fighter 11 — Super Macho Man
    11: {
        0x1: (0x2C, 0x2C, 0x37),
        0x2: (0x40, 0x40, 0x4E),
        0x3: (0x76, 0x45, 0x37),
        0x4: (0xBD, 0x85, 0x74),
        0x5: (0xEB, 0xAE, 0x9B),
        0x6: (0xFF, 0xD4, 0xC3),
        0x7: (0x21, 0x00, 0x00),
        0x8: (0xBD, 0x26, 0x26),
        0x9: (0xD7, 0x73, 0x1F),
        0xB: (0x33, 0x63, 0x9E),
        0xC: (0x54, 0x86, 0xC4),
        0xD: (0x73, 0xA4, 0xE0),
        0xE: (0x72, 0x70, 0x7A),
    },
    # Fighter 7 — Mr Sandman
    7: {
        0x7: (0x00, 0x00, 0x00),
        0x8: (0x24, 0x21, 0x18),
        0x9: (0x42, 0x3E, 0x38),
        0xA: (0xD8, 0xC6, 0xB8),
        0xB: (0x09, 0x07, 0x03),
        0xC: (0x29, 0x24, 0x1A),
        0xD: (0x42, 0x3E, 0x38),
    },
    # Fighter 13 — Hoy Quarlow
    13: {
        0x1: (0x8C, 0x8C, 0x8C),
        0x2: (0xBD, 0xBD, 0xBD),
        0x3: (0x77, 0x47, 0x18),
        0x4: (0x9C, 0x73, 0x42),
        0x5: (0xC6, 0x9C, 0x63),
        0x6: (0xE7, 0xC6, 0x8C),
        0x7: (0xBA, 0x59, 0x02),
        0x8: (0xE7, 0x75, 0x0F),
        0x9: (0xFC, 0xAA, 0x60),
        0xA: (0x4A, 0x21, 0x00),
        0xB: (0x00, 0x00, 0x00),
        0xC: (0x05, 0x05, 0x18),
        0xD: (0x0D, 0x0D, 0x28),
        0xE: (0x20, 0x20, 0x40),
    },
    # Fighter 14 — Rick Bruiser
    14: {
        0x1: (0xE9, 0x4D, 0xC2),
        0x2: (0x9C, 0x06, 0x77),
        0x3: (0x30, 0x08, 0x08),
        0x4: (0xD0, 0x60, 0x18),
        0x5: (0x90, 0x40, 0x00),
        0x6: (0x70, 0x38, 0x00),
        0x7: (0x30, 0x20, 0x00),
        0x8: (0xA0, 0xA0, 0xB8),
        0x9: (0x19, 0x1A, 0x21),
        0xA: (0x00, 0x00, 0x00),
        0xB: (0x81, 0x8C, 0x92),
        0xD: (0x3C, 0x3C, 0x3C),
        0xE: (0x74, 0x74, 0x74),
    },
    # Fighter 15 — Nick Bruiser
    15: {
        0x1: (0xA8, 0x20, 0x00),
        0x2: (0x68, 0x05, 0x00),
        0x3: (0x20, 0x00, 0x00),
        0x4: (0x78, 0x50, 0x08),
        0x5: (0x60, 0x38, 0x08),
        0x6: (0x40, 0x20, 0x08),
        0x7: (0x20, 0x18, 0x00),
        0x8: (0xA5, 0xBD, 0xB9),
        0x9: (0x09, 0x0A, 0x09),
        0xA: (0x00, 0x00, 0x00),
        0xB: (0x73, 0x78, 0xA0),
        0xD: (0x31, 0x31, 0x4E),
        0xE: (0x69, 0x69, 0x86),
    },
    # Fighter 9 — Heike Kagero
    9: {
        0x1: (0xD3, 0x3F, 0x00),
        0x2: (0xE7, 0x5C, 0x00),
        0x3: (0x38, 0x5E, 0x01),
        0x4: (0x86, 0xB2, 0x26),
        0x5: (0xB1, 0xE7, 0x4D),
        0x6: (0xD3, 0xE7, 0x94),
        0x7: (0x00, 0x17, 0x01),
        0x8: (0x11, 0x28, 0x01),
        0x9: (0x2B, 0x64, 0x02),
        0xA: (0xEC, 0x88, 0x1B),
        0xB: (0x2B, 0x16, 0x01),
        0xC: (0x5C, 0x2F, 0x00),
        0xD: (0x94, 0x3F, 0x00),
        0xE: (0x7D, 0x36, 0x01),
    },
}

# Per-fighter small portrait (Pal 0) alt palette overrides (A0–AA only).
# AF (white) and AB–AE are never changed — AB–AE are the secondary color ramp,
# vanilla values are identical across all fighters and left as-is.
FIGHTER_SMALL_OVERRIDES = {
    # Fighter 0 — Gabby Jay
    0: {
        0x1: (0x50, 0x00, 0x00),
        0x2: (0x70, 0x28, 0x10),
        0x7: (0x00, 0x00, 0x00),
        0x8: (0x60, 0x14, 0x1A),
        0x9: (0x84, 0x28, 0x1E),
        0xA: (0xB6, 0x5B, 0x51),
    },
    # Fighter 1 — Bear Hugger
    1: {
        0x1: (0x1D, 0x06, 0x02),
        0x7: (0x72, 0x27, 0x01),
        0x8: (0xE3, 0x4D, 0x01),
        0x9: (0xFA, 0x7A, 0x39),
    },
    # Fighter 5 — Dragon Chan (small portrait shares slots 2,7-A with body vanilla-side)
    5: {
        0x2: (0x14, 0x14, 0x20),
        0x7: (0x2F, 0x12, 0x01),
        0x8: (0x83, 0x33, 0x03),
        0x9: (0xCE, 0x5E, 0x1B),
        0xA: (0xEF, 0x8E, 0x53),
    },
    # Fighter 2 — Piston Hurricane (small A1-AA map 1:1 to body C1-CA; AB-AE incl. AE #FF7300 background kept vanilla)
    2: {
        0x1: (0x0E, 0x01, 0x01),
        0x2: (0x47, 0x13, 0x08),
        0x3: (0x44, 0x12, 0x07),
        0x4: (0xBC, 0x62, 0x4B),
        0x5: (0xD8, 0x93, 0x7C),
        0x6: (0xF0, 0xBA, 0xA3),
        0x7: (0x40, 0x00, 0x00),
        0x8: (0xC8, 0x00, 0x00),
        0x9: (0xE0, 0x68, 0x00),
        0xA: (0xE0, 0xE0, 0x00),
    },
    # Fighter 3 — Bald Bull (body slot -> small slot: C2->A6,C5->AA,C6->A5,CA->A2)
    3: {
        0x1: (0x1C, 0x1C, 0x1C),  # A1 <- body C1
        0x6: (0xAC, 0x07, 0x9A),  # A6 <- body C2
        0x3: (0x44, 0x3F, 0x64),  # A3 <- body C3
        0x4: (0x72, 0x7E, 0xB1),  # A4 <- body C4
        0xA: (0x86, 0x9C, 0xCA),  # AA <- body C5
        0x5: (0x96, 0xB1, 0xDF),  # A5 <- body C6
        0x7: (0x26, 0x1F, 0x2D),  # A7 <- body C7
        0x8: (0xA1, 0x01, 0x72),  # A8 <- body C8
        0x9: (0xC6, 0x21, 0xB8),  # A9 <- body C9
        0x2: (0xCD, 0xCD, 0xC5),  # A2 <- body CC
    },
    # Fighter 4 — Bob Charlie (small shares C1-CA 1:1)
    4: {
        0x1: (0x00, 0x00, 0x00),
        0x2: (0x00, 0x01, 0x00),
        0x3: (0x20, 0x00, 0x00),
        0x4: (0x55, 0x22, 0x11),
        0x5: (0x88, 0x55, 0x33),
        0x6: (0x98, 0x6E, 0x51),
        0x7: (0x00, 0x00, 0x30),
        0x8: (0x00, 0x46, 0xCE),
        0x9: (0x67, 0x88, 0xB9),
        0xA: (0xDE, 0xD6, 0xFF),
    },
    # Fighter 8 — Aran Ryan (small shares C1-CA 1:1; AE is background orange, keep vanilla)
    8: {
        0x1: (0x00, 0x00, 0x00),
        0x2: (0x1C, 0x00, 0x00),
        0x3: (0x54, 0x34, 0x04),
        0x4: (0xC6, 0x98, 0x7A),
        0x5: (0xFF, 0xCC, 0x99),
        0x6: (0xFC, 0xEB, 0xD9),
        0x7: (0x34, 0x01, 0x01),
        0x8: (0xAA, 0x00, 0x00),
        0x9: (0xD7, 0x28, 0x28),
        0xA: (0xF7, 0xA5, 0xA5),
    },
    # Fighter 10 — Mad Clown (C4 no small match; CD->A4, CE->AA)
    10: {
        0x1: (0x1B, 0x1D, 0x28),
        0x2: (0xBD, 0xBD, 0xCE),
        0x3: (0x47, 0x46, 0x46),
        0x5: (0xB9, 0xB8, 0xB8),
        0x6: (0xE3, 0xE1, 0xE0),
        0x7: (0x08, 0x10, 0x52),
        0x8: (0x1B, 0x1F, 0x38),
        0x9: (0x4B, 0x50, 0x71),
        0x4: (0x9C, 0x06, 0x10),  # A4 <- body CD
        0xA: (0xC8, 0x44, 0x4D),  # AA <- body CE
    },
    # Fighter 12 — Narcis Prince (C3->AA,C4->A3,C5->A4,C6->A5,C7->A6,C9->A8,CA->A9,CB->AB)
    12: {
        0x1: (0x51, 0x3C, 0x73),  # A1 <- body C1
        0x2: (0x85, 0x78, 0xBB),  # A2 <- body C2
        0xA: (0xB3, 0xA5, 0xE3),  # AA <- body C3
        0x3: (0x02, 0x02, 0x08),  # A3 <- body C4
        0x4: (0xB0, 0x6A, 0x2B),  # A4 <- body C5
        0x5: (0xEC, 0xA7, 0x69),  # A5 <- body C6
        0x6: (0xF9, 0xD6, 0xB1),  # A6 <- body C7
        0x8: (0x12, 0x8D, 0x63),  # A8 <- body C9
        0x9: (0xA0, 0xD5, 0xBC),  # A9 <- body CA
        0xB: (0x24, 0x24, 0x88),  # AB <- body CB
    },
    # Fighter 6 — Masked Muscle
    # Exception: portrait face shares background colors so small portrait
    # slots don't map 1:1 to body. CA→A5, CB→AA.
    # AB–AE also overridden (exception to the rule) to match body CC–CE red ramp.
    # AD is the user-specified #F80000 override on top.
    6: {
        0x1: (0x00, 0x10, 0x0B),
        0x2: (0x01, 0x2F, 0x21),
        0x5: (0x00, 0x63, 0x42),
        0x7: (0x10, 0x0B, 0x00),
        0x8: (0xC2, 0xC2, 0xC4),
        0x9: (0xDE, 0xDE, 0xE7),
        0xA: (0x00, 0x4A, 0x31),
        0xB: (0x98, 0x00, 0x00),
        0xC: (0xA7, 0x03, 0x16),
        0xD: (0xF8, 0x00, 0x00),
        0xE: (0xCD, 0x11, 0x27),
    },
    # Fighter 11 — Super Macho Man
    11: {
        0x1: (0x2C, 0x2C, 0x37),
        0x2: (0x40, 0x40, 0x4E),
        0x3: (0x76, 0x45, 0x37),
        0x4: (0xBD, 0x85, 0x74),
        0x5: (0xEB, 0xAE, 0x9B),
        0x6: (0xFF, 0xD4, 0xC3),
        0x7: (0x21, 0x00, 0x00),
        0x8: (0xBD, 0x26, 0x26),
        0x9: (0xD7, 0x73, 0x1F),
        0xA: (0x74, 0x74, 0x7C),  # AA <- body CE
    },
    # Fighter 7 — Mr Sandman (small portrait shares C7-CA with body)
    7: {
        0x7: (0x00, 0x00, 0x00),
        0x8: (0x15, 0x12, 0x0B),
        0x9: (0x2C, 0x28, 0x21),
        0xA: (0xD8, 0xC6, 0xB8),
    },
    # Fighter 13 — Hoy Quarlow (C1->A2,C2->AA,C3->A9,CA->A8,CB->A1,CC->A7,CE->A3; C7-C9 no small match)
    13: {
        0x1: (0x00, 0x00, 0x00),  # A1 <- body CB
        0x2: (0x8C, 0x8C, 0x8C),  # A2 <- body C1
        0x3: (0x20, 0x20, 0x40),  # A3 <- body CE
        0x4: (0x9C, 0x73, 0x42),  # A4 <- body C4
        0x5: (0xC6, 0x9C, 0x63),  # A5 <- body C5
        0x6: (0xE7, 0xC6, 0x8C),  # A6 <- body C6
        0x7: (0x05, 0x05, 0x18),  # A7 <- body CC
        0x8: (0x4A, 0x21, 0x00),  # A8 <- body CA
        0x9: (0x77, 0x47, 0x18),  # A9 <- body C3
        0xA: (0xBD, 0xBD, 0xBD),  # AA <- body C2
    },
    # Fighter 14 — Rick Bruiser
    # Small portrait ramp is body-order-reversed; slots mapped by vanilla color match.
    # Exception: AB overridden (portrait red-ramp) with body's purple C2 alt.
    14: {
        0x1: (0x9C, 0x06, 0x77),  # A1 <- body C2
        0x2: (0xE9, 0x4D, 0xC2),  # A2 <- body C1
        0x3: (0x30, 0x20, 0x00),  # A3 <- body C7
        0x4: (0x70, 0x38, 0x00),  # A4 <- body C6
        0x5: (0x90, 0x40, 0x00),  # A5 <- body C5
        0x6: (0xD0, 0x60, 0x18),  # A6 <- body C4
        0x7: (0x30, 0x08, 0x08),  # A7 <- body C3
        0x8: (0x00, 0x00, 0x00),  # A8 <- body CA
        0x9: (0x19, 0x1A, 0x21),  # A9 <- body C9
        0xB: (0x9C, 0x00, 0x73),  # AB override
    },
    # Fighter 15 — Nick Bruiser
    # Small portrait ramp is body-order-reversed; slots mapped by vanilla color match
    15: {
        0x1: (0x6B, 0x00, 0x00),  # A1 override
        0x2: (0xAD, 0x21, 0x00),  # A2 override
        0x3: (0x20, 0x18, 0x00),  # A3 <- body C7
        0x4: (0x40, 0x20, 0x08),  # A4 <- body C6
        0x5: (0x60, 0x38, 0x08),  # A5 <- body C5
        0x6: (0x78, 0x50, 0x08),  # A6 <- body C4
        0x8: (0x00, 0x00, 0x00),  # A8 <- body CA
        0x9: (0x09, 0x0A, 0x09),  # A9 <- body C9
        0xA: (0xA5, 0xBD, 0xB9),  # AA <- body C8
    },
    # Fighter 9 — Heike Kagero (small portrait shares body's C1-CA 1:1;
    # AE also overridden as a vanilla-fix: shipped ROM has $2CE7 #39395A
    # in that slot which stands out; replaced with the user-authored orange)
    9: {
        0x1: (0xD3, 0x3F, 0x00),
        0x2: (0xE7, 0x5C, 0x00),
        0x3: (0x38, 0x5E, 0x01),
        0x4: (0x86, 0xB2, 0x26),
        0x5: (0xB1, 0xE7, 0x4D),
        0x6: (0xD3, 0xE7, 0x94),
        0x7: (0x00, 0x17, 0x01),
        0x8: (0x11, 0x28, 0x01),
        0x9: (0x2B, 0x64, 0x02),
        0xA: (0xEC, 0x88, 0x1B),
        0xE: (0x7B, 0x31, 0x00),
    },
}

# Per-fighter large-portrait alt palette overrides.
# Only changed slots listed; vanilla used for all others.
# The unified background pair is NOT listed here — it's forced in the build loop
# into that fighter's background slots (CC/CD for most; CD/CE for the three
# fighters whose vanilla circuit-backdrop lives there — see LARGE_BG_SLOTS).
FIGHTER_LARGE_OVERRIDES = {
    # Fighter 0 — Gabby Jay
    0: {
        0x1: (0x25, 0x04, 0x06),
        0x2: (0x60, 0x14, 0x1A),
        0x3: (0x84, 0x28, 0x1E),
        0x8: (0xAB, 0x51, 0x34),
        0x9: (0x70, 0x28, 0x10),
        0xA: (0x50, 0x00, 0x00),
        0xB: (0x18, 0x02, 0x04),
    },
    # Fighter 1 — Bear Hugger
    1: {
        0x1: (0x32, 0x1E, 0x01),
        0x2: (0x94, 0x5A, 0x39),
        0x3: (0x58, 0x2A, 0x0C),
        0x4: (0xCE, 0x73, 0x5A),
        0x5: (0xE7, 0xA5, 0x8C),
        0x6: (0xFF, 0xCE, 0xB5),
        0x7: (0x18, 0x0C, 0x00),
        0x8: (0xE3, 0x4D, 0x01),
        0x9: (0x06, 0x19, 0x38),
        0xA: (0x15, 0x2C, 0x52),
        0xB: (0x71, 0x90, 0xB7),
        0xF: (0xFF, 0xFF, 0xFF),
    },
    # Fighter 2 — Piston Hurricane
    2: {
        0x1: (0xF8, 0xC0, 0xA8),
        0x2: (0x00, 0x00, 0x00),
        0x3: (0x28, 0x0C, 0x00),
        0x4: (0xA8, 0x55, 0x40),
        0x5: (0xC8, 0x68, 0x50),
        0x6: (0xE0, 0x98, 0x80),
        0x7: (0x56, 0x1F, 0x13),
        0x8: (0x6C, 0x02, 0x02),
        0x9: (0xC8, 0x00, 0x00),
        0xA: (0xE0, 0x68, 0x00),
    },
    # Fighter 3 — Bald Bull
    3: {
        0x1: (0x00, 0x00, 0x00),
        0x2: (0x03, 0x03, 0x0E),
        0x3: (0x44, 0x3F, 0x64),
        0x4: (0x72, 0x7E, 0xB1),
        0x5: (0x86, 0x9C, 0xCA),
        0x6: (0x96, 0xB1, 0xDF),
        0x7: (0x04, 0x0A, 0x34),
        0x8: (0xA1, 0x01, 0x72),
        0x9: (0xC6, 0x21, 0xB8),
        0xA: (0xEF, 0xC6, 0xC6),
        0xB: (0x7B, 0x9C, 0xC6),
        0xE: (0xAC, 0x07, 0x9A),
    },
    # Fighter 4 — Bob Charlie
    4: {
        0x1: (0x00, 0x00, 0x00),
        0x2: (0x1D, 0x01, 0x01),
        0x3: (0x34, 0x03, 0x03),
        0x4: (0x98, 0x6E, 0x51),
        0x5: (0x88, 0x55, 0x33),
        0x6: (0x55, 0x22, 0x11),
        0x7: (0x34, 0x03, 0x03),
        0x8: (0x00, 0x46, 0xCE),
        0x9: (0x67, 0x88, 0xB9),
        0xA: (0xB4, 0xD9, 0xFB),
        0xB: (0xBC, 0x98, 0x7F),
        0xE: (0x21, 0x28, 0x21),
    },
    # Fighter 5 — Dragon Chan
    5: {
        0x1: (0x00, 0x00, 0x00),
        0x2: (0x06, 0x07, 0x0E),
        0x8: (0x2F, 0x12, 0x01),
        0x9: (0x83, 0x33, 0x03),
        0xA: (0xCE, 0x5E, 0x1B),
        0xB: (0x1B, 0x1D, 0x2F),
        0xE: (0xCE, 0x5E, 0x1B),
    },
    # Fighter 6 — Masked Muscle
    6: {
        0x1: (0x01, 0x2F, 0x21),
        0x2: (0x02, 0x4D, 0x36),
        0x3: (0x00, 0x67, 0x47),
        0x8: (0xC2, 0xC2, 0xC4),
        0x9: (0xDE, 0xDE, 0xE0),
        0xA: (0xCD, 0x11, 0x27),
        0xB: (0xA7, 0x03, 0x16),
        0xE: (0x63, 0x00, 0x00),
    },
    # Fighter 7 — Mr Sandman
    7: {
        0x8: (0x24, 0x21, 0x18),
        0x9: (0x42, 0x3E, 0x38),
        0xA: (0xCD, 0xCD, 0xCD),
    },
    # Fighter 8 — Aran Ryan
    8: {
        0x1: (0x10, 0x07, 0x03),
        0x2: (0x2C, 0x01, 0x01),
        0x3: (0x54, 0x34, 0x04),
        0x4: (0xFD, 0xD0, 0xA3),
        0x5: (0xD8, 0xAD, 0x92),
        0x6: (0xA5, 0x83, 0x50),
        0x7: (0x60, 0x3E, 0x0A),
        0x8: (0xAA, 0x00, 0x00),
        0x9: (0xD7, 0x28, 0x28),
        0xA: (0xFC, 0xCA, 0xCA),
        0xB: (0x00, 0x00, 0x00),
    },
    # Fighter 9 — Heike Kagero
    9: {
        0x1: (0xD6, 0x39, 0x00),
        0x2: (0xE7, 0x79, 0x00),
        0x3: (0xFF, 0xCA, 0x8F),
        0x4: (0xD0, 0xE6, 0x90),
        0x5: (0xA4, 0xE4, 0x3D),
        0x6: (0x71, 0xAC, 0x1B),
        0x7: (0x34, 0x5A, 0x00),
        0x8: (0x0F, 0x24, 0x01),
        0x9: (0x21, 0x4E, 0x02),
        0xA: (0x40, 0x8F, 0x1B),
        0xB: (0xE7, 0x5C, 0x00),
        0xE: (0x5F, 0x26, 0x01),
    },
    # Fighter 10 — Mad Clown
    10: {
        0x1: (0x00, 0x00, 0x00),
        0x2: (0x1B, 0x1D, 0x28),
        0x3: (0x9C, 0x06, 0x10),
        0x4: (0xFF, 0xFF, 0xFF),
        0x5: (0xE3, 0xE1, 0xE0),
        0x6: (0xB9, 0xB8, 0xB8),
        0x7: (0x8F, 0x8E, 0x8E),
        0x8: (0x21, 0x29, 0x42),
        0x9: (0x45, 0x4A, 0x68),
        0xA: (0x6A, 0x70, 0x95),
        0xB: (0x3C, 0x18, 0x1B),
        0xE: (0xC8, 0x44, 0x4D),
    },
    # Fighter 11 — Super Macho Man
    11: {
        0x1: (0x29, 0x29, 0x31),
        0x2: (0x73, 0x73, 0x7B),
        0x3: (0x90, 0x90, 0x9B),
        0x4: (0xFF, 0xD1, 0xC0),
        0x5: (0xF4, 0xA4, 0x92),
        0x6: (0xBD, 0x80, 0x6F),
        0x7: (0x5E, 0x35, 0x2A),
        0x8: (0xC4, 0x1D, 0x1D),
        0x9: (0xE3, 0x73, 0x12),
        0xA: (0xFD, 0xF4, 0xF0),
        0xB: (0x47, 0x47, 0x50),
        0xE: (0xCE, 0xCE, 0xCE),
    },
    # Fighter 12 — Narcis Prince (background shifted to CD/CE; CC is a real color)
    12: {
        0x1: (0x51, 0x3C, 0x73),
        0x2: (0x85, 0x78, 0xBB),
        0x3: (0xB3, 0xA5, 0xE3),
        0x4: (0x2D, 0x21, 0x40),
        0x5: (0x88, 0x4B, 0x6D),
        0x6: (0xEC, 0xA7, 0x69),
        0x7: (0xF9, 0xD6, 0xB1),
        0x8: (0x8C, 0x8C, 0x8C),
        0x9: (0x12, 0x8D, 0x63),
        0xA: (0x0B, 0x01, 0x2D),
        0xB: (0x24, 0x24, 0x88),
        0xC: (0x72, 0x72, 0xF9),
    },
    # Fighter 13 — Hoy Quarlow
    13: {
        0x1: (0x40, 0x40, 0x5A),
        0x2: (0x84, 0x84, 0x84),
        0x3: (0xB5, 0xB5, 0xB5),
        0x4: (0xB5, 0x9C, 0x5A),
        0x5: (0x9C, 0x7B, 0x39),
        0x6: (0x73, 0x52, 0x10),
        0x7: (0x4A, 0x29, 0x00),
        0x8: (0x09, 0x09, 0x21),
        0x9: (0x22, 0x22, 0x42),
        0xA: (0xEB, 0x79, 0x13),
        0xB: (0x99, 0x4A, 0x04),
    },
    # Fighter 14 — Rick Bruiser (background shifted to CD/CE; CC is a real color)
    14: {
        0x1: (0xE6, 0x52, 0xBD),
        0x2: (0x99, 0x07, 0x78),
        0x3: (0x35, 0x09, 0x09),
        0x4: (0xE5, 0x95, 0x35),
        0x5: (0xBB, 0x64, 0x12),
        0x6: (0x6B, 0x2C, 0x00),
        0x7: (0x35, 0x24, 0x00),
        0x8: (0xA1, 0xA1, 0xB8),
        0x9: (0x1C, 0x1D, 0x25),
        0xA: (0x1C, 0x1D, 0x25),
        0xB: (0x8C, 0x90, 0xAF),
        0xC: (0x8E, 0x45, 0x00),
    },
    # Fighter 15 — Nick Bruiser (background shifted to CD/CE; CC is a real color)
    15: {
        0x1: (0xA8, 0x20, 0x00),
        0x2: (0x68, 0x05, 0x00),
        0x3: (0x0D, 0x00, 0x00),
        0x4: (0x78, 0x50, 0x08),
        0x5: (0x60, 0x38, 0x08),
        0x6: (0x2D, 0x15, 0x03),
        0x7: (0x18, 0x12, 0x00),
        0x8: (0xB1, 0xB1, 0xB1),
        0x9: (0x13, 0x1A, 0x13),
        0xA: (0x00, 0x00, 0x00),
        0xB: (0x7F, 0x7F, 0x7F),
        0xC: (0x40, 0x20, 0x08),
    },
}

# Which slots hold the unified circuit backdrop per fighter. Vanilla puts the
# purple gradient in CC(dark)/CD(light) for most, but CD(dark)/CE(light) for
# Narcis (12), Rick (14), Nick (15). (dark_slot, light_slot).
LARGE_BG_SLOTS = {i: (0xC, 0xD) for i in range(16)}
LARGE_BG_SLOTS[12] = (0xD, 0xE)
LARGE_BG_SLOTS[14] = (0xD, 0xE)
LARGE_BG_SLOTS[15] = (0xD, 0xE)

# ----------------------------------------------------------------------
# Fighter source palette addresses (Pal 0 = small portrait, Pal 2 = body)
# ----------------------------------------------------------------------
# Each entry: (sprite_block_file_offset, large_portrait_file_offset)
# Pal 0 = sprite_block + 0x00, Pal 2 = sprite_block + 0x40
FIGHTER_SOURCES = [
    (0x06B9DA, 0x087E00),  # 0  Gabby Jay
    (0x06BC3C, 0x087E20),  # 1  Bear Hugger
    (0x06BE9E, 0x087E40),  # 2  Piston Hurricane
    (0x06C100, 0x087E60),  # 3  Bald Bull
    (0x06C382, 0x087E80),  # 4  Bob Charlie
    (0x06C5E4, 0x087EA0),  # 5  Dragon Chan
    (0x06C846, 0x087EC0),  # 6  Masked Muscle
    (0x06CAC8, 0x087EE0),  # 7  Mr Sandman
    (0x06CD2A, 0x087F00),  # 8  Aran Ryan
    (0x06CF8C, 0x087F20),  # 9  Heike Kagero
    (0x06D1EE, 0x087F40),  # 10 Mad Clown
    (0x06D470, 0x087F60),  # 11 Super Macho Man
    (0x06D6D2, 0x087F80),  # 12 Narcis Prince
    (0x06D934, 0x087FA0),  # 13 Hoy Quarlow
    (0x06DB96, 0x087FC0),  # 14 Rick Bruiser
    (0x06DE58, 0x087FE0),  # 15 Nick Bruiser
]

# ----------------------------------------------------------------------
# Hook 1 stub at $40:847E — body sprite + small portrait
# On entry: fight-init just completed, DBR = $0D (set by upstream code),
#   DP = $0000, $0600 = fighter index.
#   WRAM $0540..$055F = Pal 0 (small portrait) just DMA'd
#   WRAM $0580..$059F = Pal 2 (body) just DMA'd
# Gate: ($7E:1D71 != 0)
#    OR ($7E:0091 & $20 != 0)                           P1 SELECT
#    OR ($7E:1D74 == 1 AND $7E:00A5 & $20 != 0)         P2 SELECT in VS mode
# If gated: overwrite WRAM $0540..$055F with alt Pal 0
#           overwrite WRAM $0580..$059F with alt Pal 2
# Always: re-emit displaced LDX #$0000; LDY #$3EE0; RTL
# ----------------------------------------------------------------------
def build_hook1_stub():
    """Fight-init hook at $00:97E5.
    Runs when the fighter's palette block has been DMA'd to WRAM $0540.
    Unconditionally clears alt-active flag, then checks gate:
      iron flag, P1 SELECT, or (VS mode AND P2 SELECT).
    If gated: sets flag, stores fighter ID, writes alt small/body palettes."""
    stub = bytearray()

    # unconditionally clear alt-active flag
    stub += bytes([
        0xA9, 0x00,               # LDA #$00
        0x8F, 0x76, 0x1D, 0x7E,  # STA.l $7E:1D76
    ])

    # gate: iron flag
    stub += bytes([0xAF, 0x71, 0x1D, 0x7E])  # LDA.l $7E:1D71
    stub += bytes([0xD0, 0x00])               # BNE -> do_it (patched)
    bne_iron = len(stub) - 1

    # gate: P1 SELECT held
    stub += bytes([0xAF, 0x91, 0x00, 0x7E])  # LDA.l $7E:0091
    stub += bytes([0x89, 0x20])               # BIT #$20
    stub += bytes([0xD0, 0x00])               # BNE -> do_it (patched)
    bne_p1sel = len(stub) - 1

    # gate: VS mode AND P2 SELECT held
    stub += bytes([0xAF, 0x74, 0x1D, 0x7E])  # LDA.l $7E:1D74 (VS flag)
    stub += bytes([0xC9, 0x01])               # CMP #$01
    stub += bytes([0xD0, 0x00])               # BNE -> skip (patched)
    bne_notvs = len(stub) - 1
    stub += bytes([0xAF, 0xA5, 0x00, 0x7E])  # LDA.l $7E:00A5 (P2 held hi)
    stub += bytes([0x89, 0x20])               # BIT #$20 (SELECT = bit 5)
    stub += bytes([0xF0, 0x00])               # BEQ -> skip (patched)
    beq_p2sel = len(stub) - 1

    do_it_offset = len(stub)
    # fix forward branches to do_it
    stub[bne_iron]  = (do_it_offset - (bne_iron  + 1)) & 0xFF
    stub[bne_p1sel] = (do_it_offset - (bne_p1sel + 1)) & 0xFF

    # guard: skip if $0C12 != 0 (4-pal tile pre-load)
    stub += bytes([0xAF, 0x12, 0x0C, 0x7E])  # LDA.l $7E:0C12
    stub += bytes([0xD0, 0x00])               # BNE -> skip (patched)
    bne_guard = len(stub) - 1

    # set flag, store fighter ID
    stub += bytes([
        0xA9, 0x01,               # LDA #$01
        0x8F, 0x76, 0x1D, 0x7E,  # STA.l $7E:1D76
        0xAD, 0x00, 0x06,         # LDA.w $0600
        0x8F, 0x75, 0x1D, 0x7E,  # STA.l $7E:1D75
    ])
    # apply alt small portrait -> $0540
    stub += bytes([
        0xC2, 0x20,               # REP #$20
        0xAD, 0x00, 0x06,         # LDA.w $0600
        0x29, 0xFF, 0x00,         # AND #$00FF
        0x0A, 0x0A, 0x0A, 0x0A, 0x0A,  # ASL*5 = *32
        0x18,
        0x69] + list((SMALL_PAL_SNES).to_bytes(2,'little')) + [
        0xAA,
        0xA0, 0x40, 0x05,         # LDY #$0540
        0xA9, 0x1F, 0x00,         # LDA #$001F
        0x8B, 0x54, 0x7E, 0x40, 0xAB,  # PHB; MVN $7E,$40; PLB
    ])
    # apply alt body -> $0580
    stub += bytes([
        0xAD, 0x00, 0x06,
        0x29, 0xFF, 0x00,
        0x0A, 0x0A, 0x0A, 0x0A, 0x0A,
        0x18,
        0x69] + list((BODY_PAL_SNES).to_bytes(2,'little')) + [
        0xAA,
        0xA0, 0x80, 0x05,         # LDY #$0580
        0xA9, 0x1F, 0x00,
        0x8B, 0x54, 0x7E, 0x40, 0xAB,
        0xE2, 0x20,               # SEP #$20 (back to 8-bit)
    ])
    skip_offset = len(stub)

    # fix forward branches to skip
    stub[bne_notvs] = (skip_offset - (bne_notvs + 1)) & 0xFF
    stub[beq_p2sel] = (skip_offset - (beq_p2sel + 1)) & 0xFF
    stub[bne_guard] = (skip_offset - (bne_guard + 1)) & 0xFF

    # chain to alt glove trampoline + RTL
    stub += bytes([
        0x22, 0xD2, 0xFD, 0x0D,   # JSL $0D:FDD2
        0x6B,                     # RTL
    ])

    return bytes(stub)

def build_hook6_stub():
    """Bytecode-interpreter opcode $3C hook at $01:99D4.
    Original: SEP #$20; LDA #$05; XBA; LDA $0000,y; ... reads 1-byte dest LSB
    from script (dest = $0500 + LSB), computes fighter Pal 2 source, copies 16 words.
    We replace first 4 bytes (E2 20 A9 05) with JSL $40:XXXX.

    Alt path: drops JSL frame from stack (3B), does the copy from bank $40, then
    JMLs to routine tail $01:9A07 (which PLYs our saved script Y).
    Vanilla path: re-emits displaced LDA #$05, RTL back to $01:99D8 (XBA)."""
    stub = bytearray()

    # SEP #$20 (part of displaced)
    stub += bytes([0xE2, 0x20])
    # Check flag
    stub += bytes([
        0xAF, 0x76, 0x1D, 0x7E,  # LDA.l $7E:1D76
        0xF0, 0x00,               # BEQ -> vanilla (patched)
    ])
    # Peek dest LSB
    stub += bytes([
        0xB9, 0x00, 0x00,         # LDA $0000,y (8-bit, dest LSB)
        0xC9, 0x82,               # CMP #$82
        0xD0, 0x00,               # BNE -> vanilla (patched)
    ])
    # Alt path: drop 3-byte JSL frame from stack, then do the copy, JML tail.
    stub += bytes([
        0x68, 0x68, 0x68,         # PLA PLA PLA (3x 1-byte pull, discards JSL frame)
        0xC8,                     # INY (consume dest byte)
        0x5A,                     # PHY (save script Y for tail PLY)
    ])
    # Compute source addr: BODY_PAL_SNES + fighter*32 + 2 (C1 slot in alt table)
    stub += bytes([
        0xAF, 0x75, 0x1D, 0x7E,  # LDA.l $7E:1D75
        0xC2, 0x20,               # REP #$20
        0x29, 0xFF, 0x00,
        0x0A, 0x0A, 0x0A, 0x0A, 0x0A,  # ASL*5
        0x18,
        0x69] + list((BODY_PAL_SNES + 2).to_bytes(2,'little')) + [
        0xAA,                     # TAX
        0xA0, 0x82, 0x05,         # LDY #$0582
        0xA9, 0x1F, 0x00,         # LDA #$001F
        0x8B,                     # PHB
        0x54, 0x7E, 0x40,         # MVN dst=$7E src=$40
        0xAB,                     # PLB
        0x5C, 0x07, 0x9A, 0x01,   # JML $01:9A07 (routine tail)
    ])
    # Vanilla path
    vanilla_offset = len(stub)
    stub += bytes([
        0xA9, 0x05,               # LDA #$05 (displaced)
        0x6B,                     # RTL -> $01:99D8 (XBA)
    ])

    stub[7]  = (vanilla_offset - 8)  & 0xFF   # BEQ -> vanilla
    stub[14] = (vanilla_offset - 15) & 0xFF   # BNE -> vanilla

    return bytes(stub)

def build_hook2_stub():
    # Hook site: replace ONLY MVN $00,$10 (3B) at $00:9B91 with JSR $FE18 (3B).
    # PLB at $00:9B94 and SEP #$20 at $00:9B95 remain in place in the caller.
    # Stack at entry: [ret_lo, ret_hi] (JSR 2-byte return) + caller's [PHB old_DBR below]
    # Stub just does the MVN (alt or vanilla) and RTS. PLB/SEP run in caller after.
    # CPU stays in bank $00 throughout — no cross-bank execution. MVN reads data
    # from bank $40 (expansion) via the MVN operand without changing PBR.
    stub = bytearray()
    stub += bytes([
        0xAF, 0x71, 0x1D, 0x7E,   # LDA.l $7E:1D71  (iron flag)
        0xF0, 0x00,                # BEQ skip — filled below
    ])
    # gated path: alt palette MVN
    stub += bytes([
        0xC2, 0x20,                # REP #$20
        0xAD, 0x00, 0x06,          # LDA.w $0600  (fighter index)
        0x29, 0xFF, 0x00,          # AND #$00FF
        0x0A, 0x0A, 0x0A, 0x0A, 0x0A,  # ASL×5 = ×32
        0x18,
        0x69] + list((LARGE_PAL_SNES).to_bytes(2, 'little')) + [
        0xAA,                      # TAX (source addr in bank $40)
        0xA9, 0x1F, 0x00,          # LDA #$001F
        0x54, 0x7E, 0x40,          # MVN dst=$7E src=$40 (CPU stays in $00, data from $40)
        0x60,                      # RTS (back to $00:9B94 = PLB)
    ])
    # vanilla path (BEQ skip target):
    skip_offset = len(stub)
    stub += bytes([
        0xA9, 0x1F, 0x00,          # LDA #$001F  (caller left A=$001F but MVN clobbers it)
        0x54, 0x00, 0x10,          # MVN $00,$10  (original — CPU stays in $00)
        0x60,                      # RTS
    ])

    stub[5] = (skip_offset - 6) & 0xFF
    return bytes(stub)

def main(vanilla_path, out_rom=None):
    with open(vanilla_path, 'rb') as f: vanilla = f.read()
    assert hashlib.md5(vanilla).hexdigest() == EXPECTED_MD5, "wrong base ROM"

    # Apply the alt-glove prerequisite only. alt-opp's Hook 1 rewrites the
    # alt-glove hook at $00:97E5 and chains back to it, so alt-glove must be
    # present in the base. Nothing else from Special Edition is applied.
    base = bytearray(vanilla)
    for off, chunk, _ in parse_ips(open(ALT_GLOVE, 'rb').read()):
        end = off + len(chunk)
        if end > len(base): base.extend(b'\x00' * (end - len(base)))
        base[off:end] = chunk
    rom = bytearray(base)

    # Expand ROM to 2.5MB
    EXPAND_END = 0x280000
    if len(rom) < EXPAND_END:
        rom.extend(b'\x00' * (EXPAND_END - len(rom)))

    # Update ROM makeup byte: LoROM ($20) → ExLoROM ($32)
    rom[0x7FD5] = 0x32

    # ------------------------------------------------------------------
    # Palette data: sepia-filtered versions of vanilla palettes.
    # Exception: Gabby Jay body (fighter 0, Pal 2) uses the existing
    # PoC alt palette with 9 specific slot overrides.
    # ------------------------------------------------------------------
    for i, (sprite_base, large_base) in enumerate(FIGHTER_SOURCES):
        vanilla_pal0  = vanilla[sprite_base + 0x00 : sprite_base + 0x20]
        vanilla_pal2  = vanilla[sprite_base + 0x40 : sprite_base + 0x60]
        vanilla_large = vanilla[large_base : large_base + 32]

        # Body palette (Pal 2)
        if i in FIGHTER_BODY_OVERRIDES:
            body_pal = bytearray(vanilla_pal2)
            for slot, (r, g, b) in FIGHTER_BODY_OVERRIDES[i].items():
                word = rgb8_to_bgr555(r, g, b)
                body_pal[slot*2]   = word & 0xFF
                body_pal[slot*2+1] = (word >> 8) & 0xFF
        else:
            body_pal = apply_sepia_to_palette(vanilla_pal2)

        # Small portrait (Pal 0)
        if i in FIGHTER_SMALL_OVERRIDES:
            small_pal = bytearray(vanilla_pal0)
            for slot, (r, g, b) in FIGHTER_SMALL_OVERRIDES[i].items():
                word = rgb8_to_bgr555(r, g, b)
                small_pal[slot*2]   = word & 0xFF
                small_pal[slot*2+1] = (word >> 8) & 0xFF
        else:
            small_pal = apply_sepia_to_palette(vanilla_pal0)

        # Large portrait — vanilla base, plus optional per-fighter overrides,
        # then the unified background is forced into this fighter's backdrop
        # slots (CC/CD for most; CD/CE for Narcis/Rick/Nick — see LARGE_BG_SLOTS)
        # so every circuit shares one backdrop instead of vanilla's per-circuit
        # minor=blue/major=green/world=beige/special=purple. Dark/light ordering:
        # darker #B8858D, lighter #E9BFC9.
        large_pal = bytearray(vanilla_large)
        for slot, (r, g, b) in FIGHTER_LARGE_OVERRIDES.get(i, {}).items():
            word = rgb8_to_bgr555(r, g, b)
            large_pal[slot*2]   = word & 0xFF
            large_pal[slot*2+1] = (word >> 8) & 0xFF
        dark_slot, light_slot = LARGE_BG_SLOTS[i]
        for slot, (r, g, b) in ((dark_slot, (0xB8, 0x85, 0x8D)), (light_slot, (0xE9, 0xBF, 0xC9))):
            word = rgb8_to_bgr555(r, g, b)
            large_pal[slot*2]   = word & 0xFF
            large_pal[slot*2+1] = (word >> 8) & 0xFF

        dst_body  = snes40(BODY_PAL_SNES)  + i * 32
        dst_small = snes40(SMALL_PAL_SNES) + i * 32
        dst_large = snes40(LARGE_PAL_SNES) + i * 32
        rom[dst_body  : dst_body  + 32] = body_pal
        rom[dst_small : dst_small + 32] = small_pal
        rom[dst_large : dst_large + 32] = large_pal

    # ------------------------------------------------------------------
    # Stubs
    # ------------------------------------------------------------------
    hook1_stub = build_hook1_stub()
    hook6_stub = build_hook6_stub()
    hook2_stub = build_hook2_stub()

    assert HOOK1_STUB_SNES + len(hook1_stub) <= HOOK6_STUB_SNES, \
        f"Hook1 stub overlaps Hook6: ${HOOK1_STUB_SNES+len(hook1_stub):04X} > ${HOOK6_STUB_SNES:04X}"
    assert HOOK6_STUB_SNES + len(hook6_stub) <= BODY_PAL_SNES, \
        f"Hook6 stub overlaps palette data: ${HOOK6_STUB_SNES+len(hook6_stub):04X} > ${BODY_PAL_SNES:04X}"

    rom[snes40(HOOK1_STUB_SNES) : snes40(HOOK1_STUB_SNES) + len(hook1_stub)] = hook1_stub
    rom[snes40(HOOK6_STUB_SNES) : snes40(HOOK6_STUB_SNES) + len(hook6_stub)] = hook6_stub
    hook2_file = snes00(HOOK2_STUB_SNES)
    rom[hook2_file : hook2_file + len(hook2_stub)] = hook2_stub

    # ------------------------------------------------------------------
    # Hook 1: $00:97E5 — alt-glove already put JSL $0D:FDD2; NOP; NOP here.
    # Chain: change to JSL $40:847E; NOP; NOP.
    # Our stub does its work then calls JSL $0D:FDD2 before RTL,
    # so alt gloves still runs.
    # ------------------------------------------------------------------
    altglove_hook1 = bytes([0x22, 0xD2, 0xFD, 0x0D, 0xEA, 0xEA])
    assert bytes(rom[0x017E5:0x017EB]) == altglove_hook1, \
        f"Hook1 bytes mismatch: {bytes(rom[0x017E5:0x017EB]).hex()}"
    rom[0x017E5:0x017EB] = bytes([0x22]) + long_op(HOOK1_STUB_SNES) + bytes([0xEA, 0xEA])

    # ------------------------------------------------------------------
    # Hook 6: $01:99D4 — bytecode-interpreter opcode $3C handler (Pal 2 restore).
    # Fires on spit-end for MM (and other Pal 2 palette restore triggers).
    # Replace 4 bytes (SEP #$20; LDA #$05) with JSL $40:84B0. Stub decides
    # whether to redirect source to our alt body palette or run vanilla.
    # ------------------------------------------------------------------
    orig6 = bytes([0xE2, 0x20, 0xA9, 0x05])
    assert bytes(rom[0x099D4:0x099D8]) == orig6, \
        f"Hook6 bytes mismatch: {bytes(rom[0x099D4:0x099D8]).hex()}"
    rom[0x099D4:0x099D8] = bytes([0x22]) + long_op(HOOK6_STUB_SNES)

    # ------------------------------------------------------------------
    # Hook 2: $00:9B91 — replace only MVN (3B) with JSR $FE18 (3B).
    # PLB at $00:9B94 and SEP #$20 at $00:9B95 remain in caller unchanged.
    # JSR is intra-bank, no cross-bank execution — stub runs in bank $00.
    # ------------------------------------------------------------------
    orig2 = bytes([0x54, 0x00, 0x10])
    assert bytes(rom[0x01B91:0x01B94]) == orig2, \
        f"Hook2 bytes mismatch: {bytes(rom[0x01B91:0x01B94]).hex()}"
    rom[0x01B91:0x01B94] = bytes([0x20, HOOK2_STUB_SNES & 0xFF, (HOOK2_STUB_SNES >> 8) & 0xFF])
    # slightly blue-tinted) in the shipped ROM — the only opponent whose
    # large-portrait CF isn't pure white $7FFF. Set it to $7FFF to match
    # every other fighter. File: 0x087E3E-0x087E3F.
    # ------------------------------------------------------------------
    assert bytes(rom[0x087E3E:0x087E40]) == bytes([0x9B, 0x7F]), \
        f"Bear CF mismatch: {bytes(rom[0x087E3E:0x087E40]).hex()}"
    rom[0x087E3E:0x087E40] = bytes([0xFF, 0x7F])

    # ------------------------------------------------------------------
    # Checksum (spec: split+repeat for 2.5MB)
    # ------------------------------------------------------------------
    rom[0x7FDC:0x7FE0] = b'\xFF\xFF\x00\x00'
    first  = bytes(rom[0x000000:0x200000])
    rem    = bytes(rom[0x200000:0x280000])
    chk    = (sum(first) + sum(rem * 4)) & 0xFFFF
    cmp_   = chk ^ 0xFFFF
    rom[0x7FDC:0x7FE0] = bytes([cmp_&0xFF, (cmp_>>8)&0xFF, chk&0xFF, (chk>>8)&0xFF])

    os.makedirs(os.path.dirname(OUT_IPS), exist_ok=True)

    # Build IPS by diffing against the base (vanilla + alt-glove). The
    # alt-glove hook at $00:97E5 is identical on both sides, so it does NOT
    # appear in the emitted patch — only alt-opp's own changes do. This makes
    # the standalone patch apply cleanly on top of spo_alt_glove_colors.ips.
    # Prepend explicit RLE zero-fill records to force the ROM to expand to
    # 2.5MB when applied to a 2MB base. Without these, the IPS patcher
    # only extends the file as far as the last record, leaving the ROM at
    # ~2MB + a few KB instead of the full 2.5MB.
    base_ext = bytearray(base) + b'\x00' * (EXPAND_END - len(base))
    records = []

    # Explicit expansion records: zero-fill 0x200000..0x27FFFF in chunks.
    # These are identical to base_ext (all zeros), so the diff loop below
    # would skip them. Add them explicitly so the IPS forces the file to grow.
    ZERO_CHUNK = 65535
    expansion_start = len(base)  # 0x200000
    pos = expansion_start
    while pos < EXPAND_END:
        seg_len = min(ZERO_CHUNK, EXPAND_END - pos)
        records.append((pos, bytes(seg_len), True))  # RLE zero-fill
        pos += seg_len

    i = 0
    while i < len(rom):
        if rom[i] != base_ext[i]:
            start = i
            while i < len(rom) and rom[i] != base_ext[i]:
                i += 1
            chunk = bytes(rom[start:i])
            pos = 0
            while pos < len(chunk):
                seg = chunk[pos:pos+65535]
                off = start + pos
                if len(set(seg)) == 1 and len(seg) > 5:
                    records.append((off, seg, True))
                else:
                    records.append((off, seg, False))
                pos += len(seg)
        else:
            i += 1

    # Sort so expansion records come first, then overrides
    records.sort(key=lambda r: r[0])

    out = bytearray(b'PATCH')
    for off, data, rle in records:
        out += off.to_bytes(3, 'big')
        if rle:
            out += (0).to_bytes(2, 'big')
            out += len(data).to_bytes(2, 'big')
            out += bytes([data[0]])
        else:
            out += len(data).to_bytes(2, 'big')
            out += data
    out += b'EOF'

    with open(OUT_IPS, 'wb') as f: f.write(out)

    print(f'Hook 1 stub: {len(hook1_stub)}B at $40:{HOOK1_STUB_SNES:04X}')
    print(f'Hook 6 stub: {len(hook6_stub)}B at $40:{HOOK6_STUB_SNES:04X}')
    print(f'Hook 2 stub: {len(hook2_stub)}B at $00:{HOOK2_STUB_SNES:04X}')
    print(f'Palette data: {len(FIGHTER_SOURCES)*3*32}B starting at $40:{BODY_PAL_SNES:04X}')
    print(f'Checksum: ${chk:04X}')
    print(f'wrote {OUT_IPS}  ({len(out)} bytes, {len(records)} records)')
    if out_rom:
        with open(out_rom, 'wb') as f: f.write(rom)
        print(f'wrote {out_rom}  MD5 {hashlib.md5(rom).hexdigest()}')

if __name__ == '__main__':
    if len(sys.argv) < 2:
        sys.exit(f'usage: python {os.path.basename(__file__)} <vanilla.sfc> [out.sfc]')
    main(sys.argv[1], sys.argv[2] if len(sys.argv) > 2 else None)
