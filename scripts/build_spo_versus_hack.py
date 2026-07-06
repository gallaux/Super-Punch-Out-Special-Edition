"""build_spo_versus_hack.py — VERSUS MODE.

Reads the vanilla ROM and emits the standalone IPS (and optionally the ROM).

Usage:
    python build_spo_versus_hack.py <vanilla.sfc> [out.sfc]

Design notes:
  - Uses $7E:1D74 (1B WRAM) as the VS mode flag. TIME ATTACK and the
    secret L+SELECT VS combo are byte-identical to vanilla at runtime —
    no shared mode-flag state.
  - The Special Circuit lock bypass is sourced from
    spo_disable_security_checksum.ips, which is bundled into Special
    Edition alongside this patch.
  - VERSUS runs through the TA codepath, so the engine's natural TA
    post-match flow handles routing; the flag intentionally persists
    across matches so rematches stay VS. Back-out from opponent-select
    clears the flag.
  - All bank-$0D stubs live in free space so the patch is byte-compatible
    with every other standalone.

Apply on top of: Super Punch-Out!! (USA).sfc  MD5 97fe7d7d2a1017f8480e60a365a373f0
"""
import os
import sys
import hashlib

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT_IPS  = os.path.join(REPO, "patches", "standalone", "spo_versus_hack.ips")
EXPECTED_BASE_MD5 = "97fe7d7d2a1017f8480e60a365a373f0"


# ----------------------------------------------------------------------
# Bank-$0D allocation map (within the VS-hack-vacated free space):
#   $0D:FB62..$0D:FB98  (55B)  init table-hide stub
#   $0D:FB99..$0D:FBC8  (48B)  P2 control dispatch stub
#   $0D:FBC9..$0D:FBDD  (21B)  header swap stub
#   $0D:FC4C..$0D:FD24 (217B)  P2-mirrors-P1 stub
#   $0D:FD99..$0D:FD9F  ( 7B)  clear stub (back-out)
# Plus one stub in bank-$00 free space (UNK_00F5D0 zone):
#   $00:FDD0..$00:FE17  (72B)  char-switch table-hide stub
# ----------------------------------------------------------------------
P2_DISPATCH_SNES   = 0x0DFB99
HEADER_STUB_SNES   = 0x0DFBC9
INIT_STUB_SNES     = 0x0DFB62
CHAR_STUB_SNES     = 0x00FDD0
P2_MIRRORS_SNES    = 0x0DFC4C
CLEAR_STUB_SNES    = 0x0DFD99


def snes_to_file(snes):
    return ((snes >> 16) & 0x7F) * 0x8000 + (snes & 0xFFFF) - 0x8000


def long_operand(snes):
    return bytes([snes & 0xFF, (snes >> 8) & 0xFF, (snes >> 16) & 0xFF])


# ----------------------------------------------------------------------
# 5-item Mode Select menu records (file 0x00BB93..0x06FAC9).
# ----------------------------------------------------------------------
MENU_RECORDS = [
    # [3] Trampoline 1 at $01:8457 (12B) + back-out stub at $01:8463 (6B
    #     — overwritten below by BACKOUT_CLEAR_STUB).
    # Trampoline 1: BNE +2 / INC $22 / RTS / NOP×7.
    (0x08457, bytes.fromhex("d002e62260eaeaeaeaeaeaea9c07064c66c7")),  # 18B
    # [6] Item count 4 → 5
    (0x0BB93, bytes.fromhex("04")),
    # [7] Highlight base address
    (0x0BB99, bytes.fromhex("01")),
    # [8] Disable flag init (4 separate bytes)
    (0x0BBA3, bytes.fromhex("00")),
    (0x0BBA7, bytes.fromhex("00")),
    (0x0BBB3, bytes.fromhex("0001")),
    # [9b] Decoration tilemap + arrow positions for 5-item layout
    (0x0BBC7, bytes.fromhex("5458")),
    (0x0BBD0, bytes.fromhex("5000")),
    (0x0BBD3, bytes.fromhex("6e00")),
    # [9] Progress gate rewrite (calls trampoline 1)
    (0x0BBE2, bytes.fromhex("205784ea6424bf100070f0036423eaeaea")),
    # [10] OAM cursor Y base
    (0x0BC1D, bytes.fromhex("27")),
    # [14] Mode Select confirm: JMP $FFB0
    (0x0C90E, bytes.fromhex("4cb0ff")),
    # [15]-[18] dispatch stub at $01:FFB0 (48B):
    #   CMP #$01 / BEQ +$15 → VERSUS handler at $FFC9
    #   CMP #$02 / BEQ +$0B → TA tramp at $FFC3
    #   CMP #$03 / BEQ +$0A → RV tramp at $FFC6
    #   else: BUTTON SETTINGS fall-through
    # VERSUS handler at $FFC9 (10B) — overwritten below with the flag-setting variant.
    # Trampoline 2 at $FFD3 (13B) — overwritten below with the 14B $7E:1D74-gated version.
    (0x0FFB0, bytes.fromhex(
        "c901f015c902f00bc903f00aa90685034c51c9"          # $FFB0 dispatch
        "4c26c9"                                          # $FFC3 TA tramp
        "4c30c9"                                          # $FFC6 RV tramp
        "a9038d070664054c4cc7"                            # $FFC9 VERSUS handler (replaced below)
        "ad0706c903f0034c41d6a90460"                      # $FFD3 trampoline 2 (replaced below)
    )),
    # [19] DA332[$2D] redirect → PLAYER 2 tile data
    (0x6A38C, bytes.fromhex("03fb")),
    # [20] DA332[$37] redirect → "VERSUS" tile data
    (0x6A3A0, bytes.fromhex("c3fa")),
    # [21] DA3DA entry 2 → new Mode Select layout
    (0x6A3DE, bytes.fromhex("86fa")),
    # [22] DA3DA[$A4] redirect → VERSUS opponent-select descriptor
    (0x6A47E, bytes.fromhex("cafa")),
    # [23] new Mode Select layout (61B) + [24] "VERSUS" tile data (7B) = 68B
    (0x6FA86, bytes.fromhex(
        "0d1c4e510c1c6a51371c54520c1c64520f1c5053121c5a530c1c6853101c4e54"
        "0e1c5e540c1c6a54111c4c55131c5a550c1c6c550c20545805205c5800"
        "061f0e1b1c1e1c"
    )),
    # [25] VERSUS opponent-select descriptor (49B at $0D:FACA)
    (0x6FACA, bytes.fromhex(
        "0a1c84530b1c9453091c08530b1c1453"
        "081c88520b1c9452071c08520b1c1452"
        "370c94500c0ca250052060592d205059"
        "00"
    )),
    # [26] "PLAYER 2" tile data (9B at $0D:FB03)
    (0x6FB03, bytes.fromhex("0819150a220e1bef02")),
]


# ----------------------------------------------------------------------
# Hook records and stubs added on top of the menu records
# ----------------------------------------------------------------------

# Hook at $01:80CA (12B): JSL P2 control dispatch + branch scaffold.
# Replaces original 12B sequence `C9 02 D0 A1 AD AB 00 2D AF 00 10 99`.
HOOK_80CA = bytes([0x22]) + long_operand(P2_DISPATCH_SNES) + bytes([
    0xD0, 0x03,                # BNE +3
    0x4C, 0xDE, 0x80,          # JMP $80DE
    0x4C, 0x6F, 0x80,          # JMP $806F
])

# Thunk at $01:8018 (4B): JML to header stub in bank $0D.
# Lives in the 18B dead-loop region $01:8018..$8029.
THUNK_8018 = bytes([0x5C]) + long_operand(HEADER_STUB_SNES)

# Back-out clear stub at $01:8463 (7B) — overwrites the 6B back-out stub
# inherited from MENU_RECORDS' 18B block at $01:8457. Extends 1 byte into
# the zero-fill at file 0x08469 (the 18B block ends at file 0x08468).
BACKOUT_CLEAR_STUB = bytes([0x22]) + long_operand(CLEAR_STUB_SNES) + bytes([
    0x4C, 0x66, 0xC7,          # JMP $C766
])

# Trampoline 2 at $01:FFD3 (14B): gates on $7E:1D74. Extends 1 byte into
# the previously-free $01:FFE0..$01:FFE3 zone.
TRAMP2 = bytes([
    0xAF, 0x74, 0x1D, 0x7E,    # LDA.l $7E:1D74
    0xC9, 0x01,                # CMP #$01
    0xF0, 0x03,                # BEQ +3
    0x4C, 0x41, 0xD6,          # JMP $D641
    0xA9, 0x04,                # LDA #$04
    0x60,                      # RTS
])

# VERSUS handler at $01:FFC9 (10B) — overwrites the 10B inherited from
# MENU_RECORDS. Sets $7E:1D74=1 then JMP $C926 (vanilla TA dispatch).
VERSUS_HANDLER_FFC9 = bytes([
    0xA9, 0x01,                # LDA #$01
    0x8F, 0x74, 0x1D, 0x7E,    # STA.l $7E:1D74
    0x4C, 0x26, 0xC9,          # JMP $C926
    0xEA,                      # NOP (padding so $FFD3 stays aligned)
])

# Trampoline 2 redirect: $01:BCAA JSR target $D641 → $FFD3.
REDIRECT_BCAA = bytes([0xD3, 0xFF])

# Renderer redirect: $01:BD0F JSR target $D1FC → $8018.
REDIRECT_BD0F = bytes([0x18, 0x80])

# Init table-hide hook: $01:BE7A JSL target $0E:F3DD → init stub.
REDIRECT_BE7B = long_operand(INIT_STUB_SNES)

# Char-switch table-hide hook: $01:BEC8 replaces 6 bytes
# `A2 0F 00 20 BC D7` (LDX #$000F / JSR $D7BC) with
# `22 XX XX XX EA EA` (JSL <char stub> / NOP / NOP).
HOOK_BEC8 = bytes([0x22]) + long_operand(CHAR_STUB_SNES) + bytes([0xEA, 0xEA])

# P2-mirrors hook: $01:BECE replaces 5 bytes `20 F7 D8 C9 09`
# (JSR $D8F7; CMP #$09) with `22 XX XX XX EA` (JSL <P2 stub>; NOP).
HOOK_BECE = bytes([0x22]) + long_operand(P2_MIRRORS_SNES) + bytes([0xEA])

# Back-out redirect: $01:BEEF JMP target $C766 → $8463.
REDIRECT_BEEF = bytes([0x63, 0x84])

# ----------------------------------------------------------------------
# Bank-$0D stubs
# ----------------------------------------------------------------------

# P2 control dispatch stub at $0D:FB99 (48B). Reads $7E:1D74:
#   * If =1 → set $30=$08, $3D=$80, return A=0 (caller's BNE +3 falls
#     through to JMP $80DE which continues into the post-flag-set body).
#   * Else → reproduce vanilla $0607=$02 + L+SELECT combo check.
P2_DISPATCH_STUB = bytes([
    # offset 0
    0xAF, 0x74, 0x1D, 0x7E,    # LDA.l $7E:1D74
    0xC9, 0x01,                # CMP #$01
    0xD0, 0x0B,                # BNE +11 → vanilla path (offset 19)
    # offset 8: VERSUS branch
    0xA9, 0x08, 0x85, 0x30,    # LDA #$08; STA $30
    0xA9, 0x80, 0x85, 0x3D,    # LDA #$80; STA $3D
    0xA9, 0x00, 0x6B,          # LDA #$00; RTL
    # offset 19: vanilla path
    0xAD, 0x07, 0x06,          # LDA $0607
    0xC9, 0x02,                # CMP #$02
    0xD0, 0x13,                # BNE +19 → not_combo (offset 45)
    # offset 26
    0xAD, 0xAB, 0x00,          # LDA $00AB
    0x2D, 0xAF, 0x00,          # AND $00AF
    0x10, 0x0B,                # BPL +11 → not_combo (offset 45)
    # offset 34: secret-VS combo branch
    0xA9, 0x08, 0x85, 0x30,
    0xA9, 0x80, 0x85, 0x3D,
    0xA9, 0x00, 0x6B,
    # offset 45: not_combo
    0xA9, 0x01, 0x6B,          # LDA #$01; RTL
])
assert len(P2_DISPATCH_STUB) == 48

# Header swap stub at $0D:FBC9 (21B). Called via JML from $01:8018.
# On entry: A = caller's descriptor index ($0C or $0E).
# On exit: JML to $01:D1FC with A=$A4 if VERSUS, else caller's A unchanged.
HEADER_STUB = bytes([
    0x48,                       # PHA
    0xAF, 0x74, 0x1D, 0x7E,     # LDA.l $7E:1D74
    0xC9, 0x01,                 # CMP #$01
    0xF0, 0x05,                 # BEQ +5 → versus branch
    0x68,                       # PLA (non-VERSUS: restore A)
    0x5C, 0xFC, 0xD1, 0x01,     # JML $01:D1FC
    # versus branch:
    0x68,                       # PLA (balance stack)
    0xA9, 0xA4,                 # LDA #$A4
    0x5C, 0xFC, 0xD1, 0x01,     # JML $01:D1FC
])
assert len(HEADER_STUB) == 21

# Back-out clear stub at $0D:FD99 (7B). Zero $7E:1D74; RTL.
CLEAR_STUB = bytes([
    0xA9, 0x00,
    0x8F, 0x74, 0x1D, 0x7E,
    0x6B,
])
assert len(CLEAR_STUB) == 7

# Init table-hide stub at $0D:FB62 (55B). Gate reads $7E:1D74 (LDA.l, 4B).
# The BNE +42 offset accounts for the branch site and target.
INIT_TABLE_HIDE_STUB = bytes([
    # 0..3: JSL $0E:F3DD (do real work first)
    0x22, 0xDD, 0xF3, 0x0E,
    # 4..11: gate
    0xAF, 0x74, 0x1D, 0x7E,
    0xC9, 0x01,
    0xD0, 0x2A,                 # BNE +42 → RTL at offset 54
    # 12..54: body
    0x08, 0xC2, 0x30,
    0xA2, 0x82, 0x54,
    0xA9, 0x07, 0x00,
    0x48,
    # row_loop:
    0xA0, 0x1E, 0x00,
    0xA9, 0x00, 0x00,
    # inner:
    0x9F, 0x00, 0x00, 0x7E,
    0x9F, 0x00, 0x08, 0x7E,
    0xE8, 0xE8, 0x88,
    0xD0, 0xF3,                 # BNE inner
    0x8A, 0x18, 0x69, 0x04, 0x00, 0xAA,
    0x68, 0x3A, 0x48,
    0xD0, 0xE2,                 # BNE row_loop
    0x68, 0x28, 0x6B,           # PLA / PLP / RTL
])
assert len(INIT_TABLE_HIDE_STUB) == 55

# Char-switch table-hide stub at $00:FDD0 (72B). Lives in bank $00 because
# no single bank-$0D free run is large enough alongside the 217B P2-mirrors
# stub and the other bank-$0D stubs. Body is bank-independent (only relative
# branches and one LDA.l $01:D7D2,x), so relocation is mechanical.
CHAR_SWITCH_TABLE_HIDE_STUB = bytes([
    # 0..25: CODE_01D7BC inline (DMA list setup at $0387)
    0x08,                       # PHP
    0xE2, 0x30,                 # SEP #$30
    0xA2, 0x0F,                 # LDX #$0F
    0xA0, 0x08,                 # LDY #$08
    # d7bc_loop:
    0xBF, 0xD2, 0xD7, 0x01,     # LDA.l $01:D7D2,x  ← bank-independent long absolute
    0x99, 0x87, 0x03,           # STA $0387,y
    0xCA, 0x88,                 # DEX; DEY
    0xD0, 0xF5,                 # BNE d7bc_loop
    0xA9, 0x80,                 # LDA #$80
    0x8D, 0x7D, 0x03,           # STA $037D
    0x8D, 0x87, 0x03,           # STA $0387
    # 26..33: gate
    0xAF, 0x74, 0x1D, 0x7E,
    0xC9, 0x01,
    0xD0, 0x24,                 # BNE +36 → PLP at offset 70
    # 34..68: body
    0xC2, 0x30,
    0xA2, 0x82, 0x5C,
    0xA9, 0x07, 0x00,
    0x48,
    # row_loop:
    0xA0, 0x1E, 0x00,
    0xA9, 0x00, 0x00,
    # inner:
    0x9F, 0x00, 0x00, 0x7E,
    0xE8, 0xE8, 0x88,
    0xD0, 0xF7,                 # BNE inner
    0x8A, 0x18, 0x69, 0x04, 0x00, 0xAA,
    0x68, 0x3A, 0x48,
    0xD0, 0xE6,                 # BNE row_loop
    0x68,                       # PLA
    # 69..71: PLP / RTL (PHP at offset 0 always runs, so PLP balances on both paths)
    0x28, 0x6B,
])
assert len(CHAR_SWITCH_TABLE_HIDE_STUB) == 72


def _build_p2_mirrors_stub():
    """Build the 217B P2-mirrors-P1 stub.

    Gate at offset 0..7 uses LDA.l $7E:1D74 (8B). The PEA operand (at
    offset 0x55) pushes (post_poll - 1) and the JMP target (at offset
    0x58) points at the D8F7-clone entry, both at this stub's address.

    All branches in the body are PC-relative and resolve correctly; all
    $00xx reads are absolute and bank-independent (DBR=$00 at this code
    path).
    """
    # Stub body verbatim (216B).
    vs_body = bytes.fromhex(
        "ad0706c903f0089ca6009ca7008045ad"
        "a400484da6002da4002980f008a9800d"
        "95008d9500688da600ada500484da700"
        "2da500aa2910f008a9800da1008da100"
        "8a290ff00b8d9200a9800d93008d9300"
        "688da700f465fd4cebfca20000ad9500"
        "302bad9700302dad9900302fad9b0030"
        "31ad9d003033ad9f003035ada3003037"
        "ada1003039ad9300303ba90060297f8d"
        "9500803e297f8d97008036297f8d9900"
        "802e297f8d9b008026297f8d9d00801e"
        "297f8d9f008016297f8da300800e297f"
        "8da1008006297f8d9300e8e8e8e8e8e8"
        "e8e8e88a60c9096b"
    )
    assert len(vs_body) == 216

    # 8B gate replaces the 7B gate at offset 0..6
    new_gate = bytes([0xAF, 0x74, 0x1D, 0x7E, 0xC9, 0x01, 0xF0, 0x08])
    body_after_gate = bytearray(vs_body[7:])  # 209B

    # Sanity-check the bytes we're about to relocate
    assert body_after_gate[0x4D:0x50] == bytes([0xF4, 0x65, 0xFD]), \
        "unexpected PEA bytes in body"
    assert body_after_gate[0x50:0x53] == bytes([0x4C, 0xEB, 0xFC]), \
        "unexpected JMP bytes in body"

    # Recompute internal addresses for the stub location.
    #   offset 0xD5  → RTS (60)
    #   offset 0xD6  → post_poll (CMP #$09)
    #   offset 0x5B  → D8F7 clone entry (after PEA + JMP at 0x55..0x5A)
    post_poll_snes = P2_MIRRORS_SNES + 0xD6
    d8f7_clone_snes = P2_MIRRORS_SNES + 0x5B
    pea_target = post_poll_snes - 1   # PEA pushes (target-1), RTS adds 1

    body_after_gate[0x4D:0x50] = bytes([0xF4, pea_target & 0xFF, (pea_target >> 8) & 0xFF])
    body_after_gate[0x50:0x53] = bytes([0x4C, d8f7_clone_snes & 0xFF, (d8f7_clone_snes >> 8) & 0xFF])

    stub = new_gate + bytes(body_after_gate)
    assert len(stub) == 217
    return stub


P2_MIRRORS_STUB = _build_p2_mirrors_stub()


# ----------------------------------------------------------------------
# Build records, IPS, ROM
# ----------------------------------------------------------------------

def build_records():
    """Compose the final record list."""
    records = list(MENU_RECORDS)

    # Hooks
    records.append((0x080CA, HOOK_80CA))
    records.append((0x08018, THUNK_8018))
    records.append((0x08463, BACKOUT_CLEAR_STUB))             # overlays MENU end of [4]
    records.append((0x0BCAA, REDIRECT_BCAA))
    records.append((0x0BD0F, REDIRECT_BD0F))
    records.append((0x0BE7B, REDIRECT_BE7B))
    records.append((0x0BEC8, HOOK_BEC8))
    records.append((0x0BECE, HOOK_BECE))
    records.append((0x0BEEF, REDIRECT_BEEF))
    records.append((0x0FFC9, VERSUS_HANDLER_FFC9))             # overlays MENU [17]
    records.append((0x0FFD3, TRAMP2))                          # overlays MENU [18]

    # Bank-$0D stubs
    records.append((snes_to_file(INIT_STUB_SNES),   INIT_TABLE_HIDE_STUB))
    records.append((snes_to_file(P2_DISPATCH_SNES), P2_DISPATCH_STUB))
    records.append((snes_to_file(HEADER_STUB_SNES), HEADER_STUB))
    records.append((snes_to_file(P2_MIRRORS_SNES),  P2_MIRRORS_STUB))
    records.append((snes_to_file(CLEAR_STUB_SNES),  CLEAR_STUB))

    # Bank-$00 stub
    records.append((snes_to_file(CHAR_STUB_SNES),   CHAR_SWITCH_TABLE_HIDE_STUB))

    records.sort(key=lambda r: r[0])
    return records


def build_ips(records):
    out = bytearray(b"PATCH")
    for off, data in records:
        out += off.to_bytes(3, "big")
        out += len(data).to_bytes(2, "big")
        out += data
    out += b"EOF"
    return bytes(out)


def stamp_checksum(rom):
    """SNES header checksum at $00:FFDC..$00:FFDF."""
    rom[0x07FDC:0x07FDE] = b"\xFF\xFF"
    rom[0x07FDE:0x07FE0] = b"\x00\x00"
    chk = sum(rom) & 0xFFFF
    cmp_ = chk ^ 0xFFFF
    rom[0x07FDC:0x07FE0] = bytes([
        cmp_ & 0xFF, (cmp_ >> 8) & 0xFF,
        chk & 0xFF, (chk >> 8) & 0xFF,
    ])
    return chk


def main(vanilla_path, out_rom=None):
    with open(vanilla_path, "rb") as f:
        rom = bytearray(f.read())

    md5 = hashlib.md5(rom).hexdigest()
    assert md5 == EXPECTED_BASE_MD5, \
        f"base ROM MD5 mismatch: got {md5}, expected {EXPECTED_BASE_MD5}"

    records = build_records()
    for off, data in records:
        rom[off:off + len(data)] = data
    chk = stamp_checksum(rom)
    print(f"SNES header checksum: ${chk:04X}")

    # IPS includes the header-checksum record at $00:FFDC..$00:FFDF so
    # the patched ROM is self-consistent when applied to a vanilla ROM.
    records.append((0x07FDC, bytes(rom[0x07FDC:0x07FE0])))
    records.sort(key=lambda r: r[0])

    os.makedirs(os.path.dirname(OUT_IPS), exist_ok=True)
    with open(OUT_IPS, "wb") as f:
        f.write(build_ips(records))

    total = sum(len(d) for _, d in records)
    print(f"wrote {OUT_IPS}  ({len(records)} records, {total}B patched)")

    if out_rom:
        with open(out_rom, "wb") as f:
            f.write(rom)
        print(f"wrote {out_rom}  MD5 {hashlib.md5(rom).hexdigest()}")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        sys.exit(f"usage: python {os.path.basename(__file__)} <vanilla.sfc> [out.sfc]")
    main(sys.argv[1], sys.argv[2] if len(sys.argv) > 2 else None)
