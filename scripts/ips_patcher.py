"""IPS apply / build helper.

Usage:
    python ips.py apply <base.sfc> <patch.ips> <out.sfc>
    python ips.py build <patch.ips> <records.json>
    python ips.py inspect <patch.ips>
    python ips.py readbytes <rom.sfc> <file_offset_hex> <length>

IPS format:
    Header: b"PATCH"
    Records: [3-byte BE offset][2-byte BE size][size bytes data]
        if size == 0: RLE record [2-byte BE rle_size][1-byte fill_byte]
    Trailer: b"EOF"
"""

import sys
import json
import struct

def parse_ips(data: bytes):
    assert data[:5] == b"PATCH", "bad IPS header"
    i = 5
    records = []
    while True:
        if data[i:i+3] == b"EOF":
            break
        offset = int.from_bytes(data[i:i+3], "big")
        size = int.from_bytes(data[i+3:i+5], "big")
        i += 5
        if size == 0:
            rle_size = int.from_bytes(data[i:i+2], "big")
            fill = data[i+2]
            i += 3
            records.append((offset, bytes([fill]) * rle_size, True))
        else:
            chunk = data[i:i+size]
            i += size
            records.append((offset, chunk, False))
    return records


def apply_ips(base_path: str, patch_path: str, out_path: str):
    with open(base_path, "rb") as f:
        rom = bytearray(f.read())
    with open(patch_path, "rb") as f:
        patch = f.read()
    records = parse_ips(patch)
    for offset, chunk, _rle in records:
        end = offset + len(chunk)
        if end > len(rom):
            rom.extend(b"\x00" * (end - len(rom)))
        rom[offset:end] = chunk
    with open(out_path, "wb") as f:
        f.write(rom)
    print(f"applied {len(records)} records, wrote {out_path} ({len(rom)} bytes)")


def build_ips(patch_path: str, records_path: str):
    with open(records_path) as f:
        records = json.load(f)
    out = bytearray(b"PATCH")
    for r in records:
        offset = int(r["offset"], 16) if isinstance(r["offset"], str) else r["offset"]
        if "bytes" in r:
            data = bytes.fromhex(r["bytes"].replace(" ", ""))
        elif "text" in r:
            data = r["text"].encode("ascii")
        else:
            raise ValueError(f"record missing bytes/text: {r}")
        if offset >= 0x1000000:
            raise ValueError(f"offset {offset:x} out of IPS range")
        out += offset.to_bytes(3, "big")
        out += len(data).to_bytes(2, "big")
        out += data
    out += b"EOF"
    with open(patch_path, "wb") as f:
        f.write(out)
    print(f"built {patch_path} ({len(out)} bytes, {len(records)} records)")


def inspect_ips(patch_path: str):
    with open(patch_path, "rb") as f:
        data = f.read()
    records = parse_ips(data)
    total = 0
    for off, chunk, rle in records:
        total += len(chunk)
        tag = " RLE" if rle else ""
        preview = chunk[:32].hex()
        print(f"  0x{off:06X}  {len(chunk):4d} B{tag}  {preview}{'...' if len(chunk) > 32 else ''}")
    print(f"{len(records)} records, {total} total bytes patched")


def read_bytes(rom_path: str, file_offset_hex: str, length_str: str):
    offset = int(file_offset_hex, 16)
    length = int(length_str, 0)
    with open(rom_path, "rb") as f:
        rom = f.read()
    chunk = rom[offset:offset+length]
    print(f"0x{offset:06X}  {chunk.hex()}")


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)
    cmd = sys.argv[1]
    if cmd == "apply" and len(sys.argv) == 5:
        apply_ips(sys.argv[2], sys.argv[3], sys.argv[4])
    elif cmd == "build" and len(sys.argv) == 4:
        build_ips(sys.argv[2], sys.argv[3])
    elif cmd == "inspect" and len(sys.argv) == 3:
        inspect_ips(sys.argv[2])
    elif cmd == "readbytes" and len(sys.argv) == 5:
        read_bytes(sys.argv[2], sys.argv[3], sys.argv[4])
    else:
        print(__doc__)
        sys.exit(1)


if __name__ == "__main__":
    main()
