"""build_spo_se20_bundle.py — Special Edition v2.0 bundle.

Applies every standalone patch on top of the vanilla ROM, expands to
2.5 MB (ExLoROM), stamps the SNES header checksum with the ExLoROM
split+repeat formula, and emits the bundled IPS (and optionally the ROM).

Usage:
    python build_spo_se20_bundle.py <vanilla.sfc> [out.sfc]

Outputs:
  patches/spo_special_edition_v2.0.ips
  <out.sfc>  (optional)

The bundle is every standalone patch in patches/standalone/ combined.

Apply order matters at three documented places:

  1. iron_circuit AND alt_opponents_colors must both come after
     super_macho_man_fix so they win the 3-byte overlap at file
     0x452AC ($08:D2AB). iron and alt-opp agree on the value there.

  2. alt_opponents_colors must come after alt_glove_colors: alt-opp
     re-hooks $00:97E5 (file 0x17E5), replacing the alt-glove
     JSL $0D:FDD2 with JSL $40:847E, and its stub chains back to
     $0D:FDD2 so gloves still run. Glove must be applied first.

  3. alt_opponents_colors and msu1 both live in the ExLoROM expansion
     window. Each patch's IPS records blanket the whole
     0x200000..0x27FFFF window with zeros around its real data
     (an artifact of diffing an expanded ROM), so applying one naively
     zero-wipes the other. Their non-zero data IS disjoint:
       MSU-1 audio driver  0x200000..0x20007D
       alt-opp stubs+pals  0x20047E..0x200B7F
     so both are applied "sparse" (non-zero expansion bytes only) and a
     single expand-and-zero-fill runs once at the end.

Everything else is mutually byte-disjoint apart from the SNES header
checksum at $00:FFDC, which several standalones update and the bundle
re-stamps once at the end.
"""
import hashlib
import os
import sys

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from ips_patcher import parse_ips

OUT_IPS  = os.path.join(REPO, "patches", "spo_special_edition_v2.0.ips")
EXPECTED_BASE_MD5 = "97fe7d7d2a1017f8480e60a365a373f0"

EXPAND_END = 0x280000  # 2.5 MB ExLoROM

# Order is load-bearing — see module docstring.
STANDALONES = [
    "spo_versus_hack.ips",
    "spo_disable_security_checksum.ips",
    "spo_alt_glove_colors.ips",
    "spo_profile_stats_fix.ips",
    "spo_super_macho_man_fix.ips",
    "spo_how_to_typo_fix.ips",
    "spo_title_screen_special_ring.ips",
    "spo_title_screen_special_logo.ips",
    "spo_jp_charset_enabled.ips",
    "spo_end_credits.ips",
    "spo_iron_circuit.ips",
    "spo_score_overflow_fix.ips",
    "spo_alt_opponents_colors.ips",
    "spo_msu1_v6.ips",
]

# Patches whose real data lives in the ExLoROM expansion window and whose IPS
# blankets that window with zeros — applied non-zero-only so they don't wipe
# each other. See docstring point 3.
SPARSE_EXPANSION = {"spo_alt_opponents_colors.ips", "spo_msu1_v6.ips"}


def apply_patch(rom, path, sparse_expansion=False):
    """Apply an IPS patch to rom (bytearray) in place, growing it if a record
    extends past the current end. Returns record count.

    sparse_expansion: for the two ExLoROM patches (alt-opp, msu1), skip any
    ZERO byte at/above 0x200000. Both patches' IPS records blanket the whole
    0x200000..0x27FFFF expansion window with zeros around their real data, so
    applying one naively would zero-wipe the other's (disjoint, non-zero)
    data. Writing only their non-zero expansion bytes lets both coexist; the
    single expand-and-zero-fill happens once in main()."""
    with open(path, "rb") as f:
        records = parse_ips(f.read())
    for off, chunk, _ in records:
        end = off + len(chunk)
        if end > len(rom):
            rom.extend(b"\x00" * (end - len(rom)))
        if sparse_expansion and off >= 0x200000:
            for i, b in enumerate(chunk):
                if b != 0:
                    rom[off + i] = b
        else:
            rom[off:end] = chunk
    return len(records)


def stamp_exlorom_checksum(rom):
    """ExLoROM split+repeat checksum at $00:FFDC..$00:FFDF.
    First 2 MB summed once; the 0.5 MB expansion summed x4."""
    rom[0x7FDC:0x7FE0] = b"\xFF\xFF\x00\x00"
    first = bytes(rom[0x000000:0x200000])
    rem   = bytes(rom[0x200000:0x280000])
    chk   = (sum(first) + sum(rem * 4)) & 0xFFFF
    cmp_  = chk ^ 0xFFFF
    rom[0x7FDC:0x7FE0] = bytes([
        cmp_ & 0xFF, (cmp_ >> 8) & 0xFF,
        chk & 0xFF, (chk >> 8) & 0xFF,
    ])
    return chk


def build_ips(rom, vanilla_ext):
    """Diff rom against the zero-extended vanilla and emit IPS bytes.
    Adds explicit RLE zero-fill records for the whole expansion window so the
    patch grows a 2 MB base to the full 2.5 MB even where the data is zero."""
    records = []

    pos = 0x200000  # expansion window start
    while pos < EXPAND_END:
        seg = min(65535, EXPAND_END - pos)
        records.append((pos, bytes(seg), True))
        pos += seg

    i = 0
    n = len(rom)
    while i < n:
        if rom[i] != vanilla_ext[i]:
            start = i
            while i < n and rom[i] != vanilla_ext[i]:
                i += 1
            chunk = bytes(rom[start:i])
            p = 0
            while p < len(chunk):
                seg = chunk[p:p + 65535]
                off = start + p
                if len(set(seg)) == 1 and len(seg) > 5:
                    records.append((off, seg, True))
                else:
                    records.append((off, seg, False))
                p += len(seg)
        else:
            i += 1

    records.sort(key=lambda r: r[0])

    out = bytearray(b"PATCH")
    for off, data, rle in records:
        out += off.to_bytes(3, "big")
        if rle:
            out += (0).to_bytes(2, "big")
            out += len(data).to_bytes(2, "big")
            out += bytes([data[0]])
        else:
            out += len(data).to_bytes(2, "big")
            out += data
    out += b"EOF"
    return bytes(out), records


def main(vanilla_path, out_rom=None):
    with open(vanilla_path, "rb") as f:
        vanilla = f.read()
    md5 = hashlib.md5(vanilla).hexdigest()
    assert md5 == EXPECTED_BASE_MD5, \
        f"base ROM MD5 mismatch: got {md5}, expected {EXPECTED_BASE_MD5}"

    rom = bytearray(vanilla)
    for name in STANDALONES:
        path = os.path.join(REPO, "patches", "standalone", name)
        sparse = name in SPARSE_EXPANSION
        n = apply_patch(rom, path, sparse_expansion=sparse)
        tag = "  [sparse expansion]" if sparse else ""
        print(f"  applied {name:34s} ({n} records){tag}")

    if len(rom) < EXPAND_END:
        rom.extend(b"\x00" * (EXPAND_END - len(rom)))
    assert len(rom) == EXPAND_END, f"unexpected ROM size {len(rom):#x}"

    rom[0x7FD5] = 0x32  # LoROM ($20) -> ExLoROM ($32) makeup byte
    chk = stamp_exlorom_checksum(rom)
    print(f"\nExLoROM makeup byte $00:FFD5 = $32")
    print(f"ExLoROM header checksum       = ${chk:04X}")

    vanilla_ext = bytearray(vanilla) + b"\x00" * (EXPAND_END - len(vanilla))
    ips, records = build_ips(rom, vanilla_ext)

    os.makedirs(os.path.dirname(OUT_IPS), exist_ok=True)
    with open(OUT_IPS, "wb") as f:
        f.write(ips)

    total = sum(len(d) for _, d, _ in records)
    print(f"\nwrote {OUT_IPS}")
    print(f"      {len(records)} records, {total}B patched, {len(ips)}B IPS")
    if out_rom:
        with open(out_rom, "wb") as f:
            f.write(rom)
        print(f"wrote {out_rom}")
        print(f"      {len(rom)} bytes, MD5 {hashlib.md5(rom).hexdigest()}")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        sys.exit(f"usage: python {os.path.basename(__file__)} <vanilla.sfc> [out.sfc]")
    main(sys.argv[1], sys.argv[2] if len(sys.argv) > 2 else None)