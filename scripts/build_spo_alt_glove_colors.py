"""Build spo_alt_glove_colors.ips — the player-glove runtime palette selector.

Diffs a self-contained set of records against the vanilla ROM and emits the
standalone IPS.

Usage:
    python build_spo_alt_glove_colors.py <vanilla.sfc> [out.sfc]

Modes:
  0 = vanilla green (default for Minor circuit; opp_table early-exits)
  1 = blue          (L held — default for Major circuit)
  2 = red           (R held — default for World circuit)
  3 = yellow        (X held — default for Special circuit)
  4 = white         (L+R held, OR iron-circuit flag $7E:1D71 set)

Manual button beats SELECT beats iron flag (priority).

Each mode controls:
  - rest pose gloves     (sprite OAM palette 0 c12-c15)
  - victory/KD/get-up    (BG layer 1 palette 2 c12-c15; written at fight-init from rest_table)
  - knock-out-punch base (sprite OAM palette 3 c12-c15)
  - powered-up animation (per-frame; pwr_table)
  - knock-out-punch flash (per-frame; ko_table)
  - portrait HUD c12-c13 (per-frame; portrait_table)

ROM layout:
  - Hook 1 at $00:97E5 -> $0D:FDD2 trampoline (128 B)
  - End-credits palette edits at $00:85DF-$00:85E6 (8 B)
  - Powered-up/KO/portrait write hooks at $00:DD43/$00:DDAA/$00:EB1F-EC6E
  - Bank $00 stubs at $00:F5D0-$00:F619 (EC6E trampoline + portrait rts stub)
  - Bank $0D stubs at $0D:FDD2-$0D:FFCE (trampoline + helper + powered-up + KO + portrait sep)
  - Color tables (relocated to bank $00 free zone):
      opp_table        $00:FD20 (16 B)
      rest_table       $00:FD30 (32 B, 4 modes × 8 B, indexed by (mode-1)*8)
      pwr_table        $00:FD50 (40 B, 5 modes × 8 B, indexed by mode*8)
      ko_table         $00:FD78 (40 B, 5 modes × 8 B, indexed by mode*8)
      portrait_table   $00:FDA0 (48 B, 3 frames × 4 modes × 4 B, frame*16 + (mode-1)*4)
  - SELECT/iron helper stub at $0D:FE52 (22 B, in free fragment)
"""
import os, sys

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

OUT_IPS = os.path.join(REPO, "patches", "standalone", "spo_alt_glove_colors.ips")

# ============================================================================
# Constants — table addresses (bank $00 relocated layout)
# ============================================================================
NEW_OPP  = 0x00FD20
NEW_REST = 0x00FD30
NEW_PWR  = 0x00FD50
NEW_KO   = 0x00FD78
NEW_PORT = 0x00FDA0
HELPER   = 0x0DFE52
RX_SUB   = 0x0DFE6A  # R-vs-X sub-stub (18B), in gap between helper and pwr stub
TRAMP    = 0x0DFDD2  # trampoline base (for computing commit address)

def lorom(snes):
    return ((snes >> 16) & 0x7F) << 15 | (snes & 0x7FFF)

# ============================================================================
# Color tables (frozen — extracted from the original alt_glove design plus
# mode 4 additions: white rest, steel-blue powered-up, vibrant red KO punch)
# ============================================================================

# 16-byte opp -> default-mode lookup (4 opponents per circuit, modes 0/1/2/3)
opp_table = bytes.fromhex("00000000010101010202020203030303")

# rest_table — 4 modes × 8 bytes (c12 c13 c14 c15)
# Indexed by (mode - 1) * 8 (mode 0 early-exits via trampoline's BEQ).
rest_table = bytes.fromhex(
    "e360e369a86a506b"   # mode 1 (blue)
    "27042e04740cfc1c"   # mode 2 (red)
    "ca00f805dd12bf23"   # mode 3 (yellow)
    "ce39b5567b6fff7f"   # mode 4 (white gray-ramp -> pure white)
)
assert len(rest_table) == 32

# pwr_table — 5 modes × 8 bytes (mode 0 = vanilla green powered-up; preserved).
# Indexed by mode * 8 (no decrement).
pwr_table = bytes.fromhex(
    "870167022c27f447"   # mode 0 (vanilla green)
    "6b71ab7ec87f507f"   # mode 1 (blue)
    "af14f61c9b315f4a"   # mode 2 (red)
    "5211bf1efd37bf4f"   # mode 3 (yellow)
    "c4288a41906a987f"   # mode 4 (steel blue / electric)
)
assert len(pwr_table) == 40

# ko_table — 5 modes × 8 bytes (mode 0 = vanilla; preserved).
# Indexed by mode * 8.
ko_table = bytes.fromhex(
    "a87d887e4d7ff57f"   # mode 0 (vanilla)
    "1c01bf097f125f23"   # mode 1 (blue -> orange flash)
    "5c02ff027f13ff33"   # mode 2 (red -> gold flash)
    "121819209f28df39"   # mode 3 (yellow -> crimson flash)
    "1008d8189f315f4a"   # mode 4 (vibrant lighter red flash)
)
assert len(ko_table) == 40

# portrait_table — 3 frames × 4 modes × 4 bytes (c12 word, c13 word).
# Indexed by frame*16 + (mode-1)*4. Mode 0 early-exits (no row stored).
# Layout per frame: [mode 1 (4 B) | mode 2 (4 B) | mode 3 (4 B) | mode 4 (4 B)]
portrait_table = bytes.fromhex(
    # Frame 0 (rest)
    "e369a86a"     # mode 1 (blue)
    "2e04740c"     # mode 2 (red)
    "f805dd12"     # mode 3 (yellow)
    "5a6bff7f"     # mode 4 (white: off-white + pure white)
    # Frame 1 (blinkA)
    "a86a506b"     # mode 1
    "740cfc1c"     # mode 2
    "dd12bf23"     # mode 3
    "ff7fff7f"     # mode 4 (pure white)
    # Frame 2 (blinkB)
    "9273d47b"     # mode 1
    "3e257f2d"     # mode 2
    "ff2bff33"     # mode 3
    "ff7fff7f"     # mode 4 (pure white)
)
assert len(portrait_table) == 48

# ============================================================================
# Hook 1 trampoline at $0D:FDD2 — 128 bytes
#
# Layout (annotated):
#   +0   PHP / PHB / REP #$30 / SEP #$20             (setup, 6 B)
#   +6   LDA.l $7E0090 / AND #$70                    (held L/R/X mask)
#   +12  BEQ no_LRX (fallback path at +50)
#   +14  CMP #$30 ; BNE ; LDA #$04 ; BRA commit      (L+R → mode 4 white)
#   +22  BIT #$20 ; BEQ ; LDA #$01 ; BRA commit      (L → mode 1 blue)
#   +30  JMP $0D:FE6A (R-vs-X sub → mode 2 red or mode 3 yellow)
#   +38  LDA.l $7E0091 / AND #$40 / BEQ / LDA #$00  (Y → mode 0 vanilla)
#   +48  BRA commit
#   +50  no_LRX: AND #$0F / REP #$20 / AND #$00FF / TAX / SEP #$20
#   +60  JSL $0D:FE52 (helper — checks SELECT, iron-flag, else opp_table[X])
#   +64  STA.l $7E1D70 (commit mode)
#   +68  BEQ exit (mode 0)
#   +70  DEC A (mode - 1)
#   +71  REP #$20 / AND #$00FF / ASL ASL ASL (mode * 8)
#   +79  CLC ; ADC #$FD30 (rest_table base in bank $00)
#   +83  PHA ; TAX
#   +85  LDY #$0518 ; LDA #$0007 ; MVN $7E,$00 (rest gloves)
#   +94  LDA $01,S ; TAX
#   +97  LDY #$0458 ; LDA #$0007 ; MVN $7E,$00 (victory/KD BG tiles)
#   +106 LDA $01,S ; TAX
#   +109 LDY #$0578 ; LDA #$0007 ; MVN $7E,$00 (KO-punch base)
#   +118 PLA ; PLB ; PLP
#   +121 LDX #$0000 ; LDY #$3EE0 (displaced vanilla)
#   +127 RTL
# ============================================================================
TRAMPOLINE_HEX = (
    "088bc230e220af90007e2970f014c930d004a904802a8920f004a90180224c6a"
    "feeaaf91007e2940f004a9008012af00067e290fc22029ff00aae2202252fe0d"
    "8f701d7ef0313ac22029ff000a0a0a186930fd48aaa01805a90700547e00a301"
    "aaa05804a90700547e00a301aaa07805a90700547e0068ab28a20000a0e03e6b"
)
trampoline = bytes.fromhex(TRAMPOLINE_HEX)
assert len(trampoline) == 128

# Helper stub at $0D:FE52 (24 B)
helper_stub = bytes.fromhex(
    "af90007e"   # +0  LDA.l $7E0090 (P1 held lo)
    "2930"       # +4  AND #$30 (L+R mask)
    "c930"       # +6  CMP #$30 (both held?)
    "f00b"       # +8  BEQ return_4 (-> +21)
    "af711d7e"   # +10 LDA.l $7E1D71 (iron flag)
    "d005"       # +14 BNE return_4 (-> +21)
    "bf20fd00"   # +16 LDA.l $00FD20,X (opp_table default)
    "6b"         # +20 RTL
    "a904"       # +21 return_4: LDA #$04
    "6b"         # +23 RTL
)
assert len(helper_stub) == 24

# R-vs-X sub at $0D:FE6A (18B). Called via JMP from trampoline [30-32].
# Checks R (bit 4 of $0090): R held → A=2 (red), else → A=3 (yellow/X).
# Jumps directly to trampoline commit ($0D:FE12 = tramp+64) — no stack games.
_commit = (TRAMP + 64) & 0xFFFF
rx_sub = bytes([
    0xAF, 0x90, 0x00, 0x7E,          # LDA.l $7E0090
    0x89, 0x10,                       # BIT #$10 (R?)
    0xF0, 0x05,                       # BEQ +5 → LDA #$03
    0xA9, 0x02,                       # LDA #$02 (R: red)
    0x4C, _commit & 0xFF, (_commit >> 8) & 0xFF,  # JMP commit
    0xA9, 0x03,                       # LDA #$03 (X: yellow)
    0x4C, _commit & 0xFF, (_commit >> 8) & 0xFF,  # JMP commit
])
assert len(rx_sub) == 18
assert RX_SUB + len(rx_sub) <= 0x0DFE80, "rx_sub overflows into pwr stub"

# ============================================================================
# Bank-$00 portrait rts stub at $00:F5D0 (74 B)
# EC6E trampoline (5 B) + Portrait stub-rts (69 B).
# Modified: refs to portrait_table now point at $00:FDA0 (instead of $0D:FFAB),
# and frame-offset constants updated from $0C/$18 to $10/$20 for the 4-mode layout.
# ============================================================================
PORT_RTS_BYTES_HEX = (
    "206eec6b60"                              # +0  JSR $EC6E ; RTL ; RTS (trampoline)
    "206eec"                                  # +5  JSR $EC6E (port rts stub start)
    "af701d7e"                                # +8  LDA.l $7E1D70 (mode)
    "f038"                                    # +12 BEQ exit (mode 0)
    "3a"                                      # +14 DEC A
    "c220"                                    # +15 REP #$20
    "29ff00"                                  # +17 AND #$00FF
    "0a0a"                                    # +20 ASL ASL (mode*4)
    "48"                                      # +22 PHA
    "af38057e"                                # +23 LDA.l $7E0538 (frame indicator)
    "a20000"                                  # +27 LDX #$0000 (rest frame offset)
    "c94a"                                    # +30 CMP #$4A
    "0dd003"                                  # +32 (?) ; BNE +3
    "a21000"                                  # +35 LDX #$0010 (blinkA frame offset, was $0C)
    "c9b1"                                    # +38 CMP #$B1
    "14d003"                                  # +40 (?) ; BNE +3
    "a22000"                                  # +43 LDX #$0020 (blinkB frame offset, was $18)
    "8a"                                      # +46 TXA
    "18"                                      # +47 CLC
    "6301"                                    # +48 ADC $01,S
    "aa"                                      # +50 TAX
    "68"                                      # +51 PLA
    "bfa0fd00"                                # +52 LDA.l $00FDA0,X (c12 from new portrait_table)
    "8f38057e"                                # +56 STA.l $7E0538
    "bfa2fd00"                                # +60 LDA.l $00FDA2,X (c13)
    "8f3a057e"                                # +64 STA.l $7E053A
    "e220"                                    # +68 SEP #$20
    "686868"                                  # +70 PLA × 3 (drop JSL frame)
    "60"                                      # +73 RTS (return to bank-$00 caller)
)
port_rts_stub = bytes.fromhex(PORT_RTS_BYTES_HEX)
assert len(port_rts_stub) == 74

# ============================================================================
# Bank-$0D stubs (verified-working bytes from v3 build)
# ============================================================================

# Powered-up stub at $0D:FE80 (60 B) — refs to $00:FD50
PWR_STUB_HEX = (
    "08c230e220af701d7ec22029ff000a0a"
    "0aaabf50fd008f18057ebf52fd008f1a"
    "057ebf54fd008f1c057ebf56fd008f1e"
    "057ee220a9808f48007e286b"
)
pwr_stub = bytes.fromhex(PWR_STUB_HEX)
assert len(pwr_stub) == 60

# KO-punch stub at $0D:FEC0 (64 B, truncated — old embedded pwr_table dropped)
KO_STUB_HEX = (
    "08c230e220a9048521af701d7ec22029"
    "ff000a0a0aaabf78fd008f78057ebf7a"
    "fd008f7a057ebf7cfd008f7c057ebf7e"
    "fd008f7e057ee220a9808f48007e286b"
)
ko_stub = bytes.fromhex(KO_STUB_HEX)
assert len(ko_stub) == 64

# Portrait sep stub at $0D:FF68 (67 B, truncated — old embedded portrait_table dropped)
# Frame-offset constants $10 / $20 (was $0C / $18) for 4-mode layout
PORT_SEP_HEX = (
    "22d0f500af701d7ef0383ac22029ff00"
    "0a0a48af38057ea20000c94a0dd003a2"
    "1000c9b114d003a220008a186301aa68"
    "bfa0fd008f38057ebfa2fd008f3a057e"
    "e2206b"
)
port_sep_stub = bytes.fromhex(PORT_SEP_HEX)
assert len(port_sep_stub) == 67

# ============================================================================
# Vanilla bytes we need to restore at old table locations (since tables moved)
# ============================================================================
def build_records(van):
    records = [
    # End-credits palette edits at $00:85DF (DATA_008547 palette 4 c12-c15 → yellow)
    {"offset": "0x0005DF", "bytes": "ca", "comment": "end-credits pal4 c12 low (yellow)"},
    {"offset": "0x0005E1", "bytes": "f805dd", "comment": "end-credits pal4 c12-c14"},
    {"offset": "0x0005E5", "bytes": "bf23", "comment": "end-credits pal4 c15"},

    # Hook 1 site at $00:97E5 (universal fight-init)
    {"offset": "0x0017E5", "bytes": "22d2fd0deaea", "comment": "Hook 1: JSL $0D:FDD2 + 2×NOP"},

    # Powered-up writer hook at $00:DD43
    {"offset": "0x005D43", "bytes": "2280fe0d60", "comment": "Powered-up writer: JSL $0D:FE80 + RTS"},

    # KO-punch writer hook at $00:DDAA
    {"offset": "0x005DAA", "bytes": "22c0fe0d60", "comment": "KO writer: JSL $0D:FEC0 + RTS"},

    # Portrait sep-variant hooks at $00:EB1F, $00:EB9B, $00:EC68
    {"offset": "0x006B1F", "bytes": "2268ff0dea", "comment": "Portrait sep hook 1"},
    {"offset": "0x006B9B", "bytes": "2268ff0dea", "comment": "Portrait sep hook 2"},
    {"offset": "0x006C64", "bytes": "eaea", "comment": "NOP-out BEQ that aimed into our hook"},
    {"offset": "0x006C68", "bytes": "2268ff0dea", "comment": "Portrait sep hook 3"},

    # Portrait rts-variant hook at $00:ECE9
    {"offset": "0x006CE9", "bytes": "22d5f500", "comment": "Portrait rts hook: JSL $00:F5D5"},

    # Bank-$00 EC6E trampoline + portrait rts stub at $00:F5D0
    {"offset": "0x0075D0", "bytes": port_rts_stub.hex(), "comment": f"$00:F5D0 EC6E tramp + port rts stub ({len(port_rts_stub)} B)"},

    # === Bank $00 relocated color tables ===
    {"offset": f"0x{lorom(NEW_OPP):06X}",  "bytes": opp_table.hex(),       "comment": f"opp_table @ ${NEW_OPP:06X} ({len(opp_table)} B)"},
    {"offset": f"0x{lorom(NEW_REST):06X}", "bytes": rest_table.hex(),      "comment": f"rest_table @ ${NEW_REST:06X} (4 modes × 8 B)"},
    {"offset": f"0x{lorom(NEW_PWR):06X}",  "bytes": pwr_table.hex(),       "comment": f"pwr_table @ ${NEW_PWR:06X} (5 modes × 8 B)"},
    {"offset": f"0x{lorom(NEW_KO):06X}",   "bytes": ko_table.hex(),        "comment": f"ko_table @ ${NEW_KO:06X} (5 modes × 8 B)"},
    {"offset": f"0x{lorom(NEW_PORT):06X}", "bytes": portrait_table.hex(),  "comment": f"portrait_table @ ${NEW_PORT:06X} (3 frames × 4 modes × 4 B)"},

    # Vanilla-restore old opp+rest table locations (40 B) + modified trampoline first 28 B
    {"offset": "0x06FDAA", "bytes": (bytes(van[0x06FDAA:0x06FDAA+40]) + trampoline[:28]).hex(),
     "comment": "Vanilla-restore old opp+rest (40 B) + tramp first 28 B"},

    # Trampoline last 99 B (with 1-byte vanilla gap at 0x06FDEE skipped)
    {"offset": "0x06FDEF", "bytes": trampoline[29:128].hex(),
     "comment": "Trampoline last 99 B ($0D:FDEF-FE51)"},

    # Helper stub at $0D:FE52 (L+R / iron-flag check)
    {"offset": f"0x{lorom(HELPER):06X}", "bytes": helper_stub.hex(),
     "comment": f"Helper stub @ ${HELPER:06X} ({len(helper_stub)} B)"},

    # R-vs-X sub at $0D:FE6A
    {"offset": f"0x{lorom(RX_SUB):06X}", "bytes": rx_sub.hex(),
     "comment": f"R-vs-X sub @ ${RX_SUB:06X} ({len(rx_sub)} B)"},

    # Powered-up stub (60 B)
    {"offset": "0x06FE80", "bytes": pwr_stub.hex(), "comment": "Powered-up stub (60 B)"},

    # KO-punch stub (64 B, truncated)
    {"offset": "0x06FEC0", "bytes": ko_stub.hex(), "comment": "KO-punch stub (64 B; old embedded pwr_table dropped)"},

    # Vanilla-restore old powered_up_table location
    {"offset": "0x06FF00", "bytes": van[0x06FF00:0x06FF20].hex(), "comment": "Vanilla-restore old pwr_table loc"},

    # Vanilla-restore old ko_punch_table location
    {"offset": "0x06FF40", "bytes": van[0x06FF40:0x06FF60].hex(), "comment": "Vanilla-restore old ko_table loc"},

    # Portrait sep stub (67 B, truncated)
    {"offset": "0x06FF68", "bytes": port_sep_stub.hex(), "comment": "Portrait sep stub (67 B; old embedded portrait_table dropped)"},

    # Vanilla-restore old portrait_table location
    {"offset": "0x06FFAB", "bytes": van[0x06FFAB:0x06FFAB+36].hex(), "comment": "Vanilla-restore old portrait_table loc"},
    ]
    return records


def emit_ips(vanilla_path, out_rom=None):
    with open(vanilla_path, "rb") as f:
        van = bytearray(f.read())

    records = build_records(van)

    # Apply records to a working ROM, then compute the SNES header checksum.
    rom = bytearray(van)
    for r in records:
        off = int(r["offset"], 16)
        data = bytes.fromhex(r["bytes"])
        rom[off:off+len(data)] = data
    rom[0x7FDC:0x7FDE] = b"\xFF\xFF"
    rom[0x7FDE:0x7FE0] = b"\x00\x00"
    chk = sum(rom) & 0xFFFF
    inv = chk ^ 0xFFFF
    csum = bytes([inv & 0xFF, (inv >> 8) & 0xFF, chk & 0xFF, (chk >> 8) & 0xFF])
    rom[0x7FDC:0x7FE0] = csum
    records.append({"offset": "0x007FDC", "bytes": csum.hex(),
                    "comment": f"SNES header checksum ${chk:04X}"})

    # Emit IPS directly from the records list.
    out = bytearray(b"PATCH")
    for r in records:
        off = int(r["offset"], 16)
        data = bytes.fromhex(r["bytes"])
        out += off.to_bytes(3, "big")
        out += len(data).to_bytes(2, "big")
        out += data
    out += b"EOF"

    os.makedirs(os.path.dirname(OUT_IPS), exist_ok=True)
    with open(OUT_IPS, "wb") as f:
        f.write(bytes(out))

    print(f"\n{'='*60}")
    print(f"spo_alt_glove_colors.ips built")
    print(f"{'='*60}")
    print(f"IPS: {OUT_IPS}")
    print(f"Records: {len(records)}")
    print(f"Checksum: ${chk:04X}")

    if out_rom:
        with open(out_rom, "wb") as f:
            f.write(bytes(rom))
        print(f"ROM: {out_rom}")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        sys.exit(f"usage: python {os.path.basename(__file__)} <vanilla.sfc> [out.sfc]")
    emit_ips(sys.argv[1], sys.argv[2] if len(sys.argv) > 2 else None)
