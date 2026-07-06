"""build_spo_msu1_v6.py — build spo_msu1_v6.ips from scratch.

Fixes two bugs in Kurrono's original v5:
  1. Loop-flag bug: tracks $60 (Win), $63 (Opponent Down), $6F (Circuit Clear)
     were missing from the non-looping list and would incorrectly loop.
  2. Checksum: original had an incorrect SNES header checksum.

The stub is built from the known-good v5 bytes (hardcoded below from the
original IPS) with the loop-flag block replaced and the mutedemo JSL operand
updated to reflect the stub's new size (+12B from 3 new CMP/BEQ pairs).

Usage:
    python build_spo_msu1_v6.py <vanilla.sfc> [out.sfc]

Output: patches/standalone/spo_msu1_v6.ips
"""
import hashlib, os, sys

REPO    = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT_IPS = os.path.join(REPO, 'patches', 'standalone', 'spo_msu1_v6.ips')

# Original v5 stub at $40:8000 (114 bytes), from the original IPS.
V5_STUB = bytes.fromhex(
    "488a08e220ad0220c953f0072868a622e4396b"  # +00..+12: PHA/TXA/PHP/.../RTL (spc fallback)
    "28684808e220a6228a9c06208d04209c0520"    # +13..+25: msufound entry
    "2c002070fb"                               # +26..+2A: loop: BIT $2000 / BVS loop
    "48ad00202908d02a"                         # +2B..+32: PHA / LDA $2000 / AND #$08 / BNE spcFallback
    # Loop-flag decision block (+32..+4C, 27B) — REPLACED below
    "68"                                       # +32: PLA
    "c961f014c962f010c96cf00cc971f008c970f004"# +33..+46: 5x CMP/BEQ noloop
    "a9038002"                                 # +47..+4A: LDA #$03 / BRA endroutine
    "a901"                                     # +4B..+4C: LDA #$01 (noloop)
    # Continuation (+4D..+71)
    "8d0720a9ff8d0620"                         # +4D..+54: STA $2007 / LDA #$FF / STA $2006
    "2868a200e4396b"                           # +55..+5B: PLP / PLA / LDX #$00 / CPX $39 / RTL
    "682868a622e4396b"                         # +5C..+63: spcFallback: PLA/PLP/PLA/LDX/CPX/RTL
    # mutedemo at +$64 in v5
    "2200f80148c9009c0720686b"                 # +64..+6F: JSL $01F800 / PHA / CMP #$00 / STZ $2007 / PLA / RTL
    "686b"                                     # +70..+71: padding RTLs (end of stub)
)
assert len(V5_STUB) == 114, f"V5_STUB length {len(V5_STUB)}"

# Build new loop-flag block: 8 non-looping tracks instead of 5.
# All tracks in ascending order; BEQ offsets decrease by 4 per entry.
# noloop label is at: 1(PLA) + 8×4(pairs) + 2(LDA#03) + 2(BRA) = 37 bytes from block start.
# For pair i: BEQ PC-after = 1 + i*4 + 4; offset to noloop = 37 - (1+i*4+4) = 32 - i*4.
NOLOOP_TRACKS = [0x60, 0x61, 0x62, 0x63, 0x6C, 0x6F, 0x70, 0x71]
new_block = bytearray([0x68])  # PLA
for i, track in enumerate(NOLOOP_TRACKS):
    new_block += bytes([0xC9, track, 0xF0, 32 - i * 4])
new_block += bytes([0xA9, 0x03, 0x80, 0x02, 0xA9, 0x01])  # LDA #$03 / BRA +2 / LDA #$01
assert len(new_block) == 39  # 27B original + 12B for 3 new pairs

# Build v6 stub: replace the loop-flag block (+0x32..+0x4C, 27B) with new_block (39B)
BLOCK_START = 0x32
BLOCK_END   = BLOCK_START + 27  # +0x4D
v6_stub = bytearray(V5_STUB[:BLOCK_START]) + new_block + bytearray(V5_STUB[BLOCK_END:])
assert len(v6_stub) == 126  # 114 + 12

# Fix the BNE spcFallback offset at stub +0x31.
# In v5: BNE at +0x30, offset $2A → jumps from PC +0x32 to spcFallback at +0x5C.
# In v6: spcFallback shifted +12 to +0x68. New offset = $2A + 12 = $36.
assert v6_stub[0x30] == 0xD0, f"Expected BNE at +0x30, got {v6_stub[0x30]:02X}"
assert v6_stub[0x31] == 0x2A, f"Expected old BNE offset $2A, got {v6_stub[0x31]:02X}"
v6_stub[0x31] = 0x36  # 0x32 + 0x36 = 0x68 = spcFallback in v6

# Fix mutedemo JSL operand: was $40:8064, now $40:8070 (+0x6C in v6_stub = $40:8070? let's verify)
# mutedemo was at v5 stub offset +0x64. After +12B shift: v6 offset = 0x64 + 12 = 0x70.
# SNES address = $40:8000 + 0x70 = $40:8070. Operand bytes: 70 80 40.
# In v6_stub, mutedemo JSL is at offset 0x70:
assert v6_stub[0x70] == 0x22, f"Expected JSL opcode at +0x70, got {v6_stub[0x70]:02X}"
# Update the JSL operand at +0x71..+0x73
# Currently it has the address from v5 (00 F8 01 = JSL $01F800), which is CORRECT —
# this is what mutedemo calls internally, NOT the hook address.
# The hook at file 0x44C0C points TO mutedemo's entry point: was 64 80 40, needs 70 80 40.
MUTEDEMO_HOOK_ADDR = 0x44C0C  # file offset of the 3-byte operand in the mutedemo hook


def main(vanilla_path, out_rom=None):
    with open(vanilla_path, 'rb') as f:
        vanilla = f.read()

    rom = bytearray(vanilla)

    # Hook 1: msu entry at $01:EC6D → JSL $40:8000
    rom[0x0EC6D:0x0EC71] = bytes([0x22, 0x00, 0x80, 0x40])

    # Hook 2: mutedemo at $08:CC0B → JSL $40:8070 (mutedemo's NEW address in v6)
    # File 0x44C0B = opcode (22), 0x44C0C = operand lo/mid/bank
    rom[0x44C0B] = 0x22
    rom[0x44C0C:0x44C0F] = bytes([0x70, 0x80, 0x40])

    # Stub at $40:8000 (file 0x200000), 126B
    rom_len = 0x280000
    if len(rom) < rom_len:
        rom.extend(b'\x00' * (rom_len - len(rom)))
    rom[0x200000:0x200000 + len(v6_stub)] = v6_stub

    # Stamp checksum per SNES ROM header spec for non-power-of-2 ROMs:
    # First half = largest power-of-2 portion (2MB = 0x000000-0x1FFFFF).
    # Second half = remainder (512KB = 0x200000-0x27FFFF) repeated until
    # same size as first half (4× to fill 2MB). Sum both halves and add.
    # Source: SnesLab SNES ROM Header documentation.
    rom[0x7FDC:0x7FE0] = b'\xFF\xFF\x00\x00'
    first_half  = bytes(rom[0:0x200000])
    remainder   = bytes(rom[0x200000:0x280000])
    second_half = remainder * 4                  # 512KB × 4 = 2MB
    chk  = (sum(first_half) + sum(second_half)) & 0xFFFF
    cmp_ = chk ^ 0xFFFF
    rom[0x7FDC:0x7FE0] = bytes([cmp_ & 0xFF, (cmp_ >> 8) & 0xFF, chk & 0xFF, (chk >> 8) & 0xFF])

    # Build IPS by diffing against vanilla (with zero-fill RLE for padding)
    records = []
    i = 0
    while i < len(rom):
        if i >= len(vanilla) or rom[i] != vanilla[i]:
            start = i
            while i < len(rom) and (i >= len(vanilla) or rom[i] != vanilla[i]):
                i += 1
            chunk = bytes(rom[start:i])
            pos = 0
            while pos < len(chunk):
                seg = chunk[pos:pos + 65535]
                off = start + pos
                if len(set(seg)) == 1 and len(seg) > 5:
                    records.append((off, seg, True))
                else:
                    records.append((off, seg, False))
                pos += len(seg)
        else:
            i += 1

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

    os.makedirs(os.path.dirname(OUT_IPS), exist_ok=True)
    with open(OUT_IPS, 'wb') as f:
        f.write(out)

    print(f'Stub: {len(v6_stub)}B  hook1: JSL $40:8000  hook2 (mutedemo): JSL $40:8070')
    print(f'Checksum: cmp=${cmp_:04X} chk=${chk:04X}')
    print(f'Wrote {OUT_IPS} ({len(out)} bytes, {len(records)} records)')

    # Verify non-looping tracks
    block_start = 0x200000 + 0x33  # first CMP after PLA
    for i in range(8):
        track = rom[block_start + i * 4 + 1]  # CMP opcode is at +0, track operand at +1
        assert track == NOLOOP_TRACKS[i], f"track {i}: expected ${NOLOOP_TRACKS[i]:02X}, got ${track:02X}"
    print(f'Non-looping tracks verified: {[f"${t:02X}" for t in NOLOOP_TRACKS]}')
    print(f'mutedemo hook: JSL ${rom[0x44C0C]:02X}{rom[0x44C0E]:02X}{rom[0x44C0D]:02X} '
          f'(expect $408070)')

    if out_rom:
        with open(out_rom, 'wb') as f:
            f.write(rom)
        print(f'Wrote {out_rom} ({len(rom)} bytes, MD5 {hashlib.md5(rom).hexdigest()})')


if __name__ == '__main__':
    if len(sys.argv) < 2:
        sys.exit(f"usage: python {os.path.basename(__file__)} <vanilla.sfc> [out.sfc]")
    main(sys.argv[1], sys.argv[2] if len(sys.argv) > 2 else None)
