"""build_spo_iron_circuit.py — build spo_iron_circuit.ips from source.

The Iron Circuit patch adds a hidden fifth circuit ("IRON CIRCUIT") to the
Championship Mode / Time Attack circuit-select screens: a 16-opponent gauntlet
with HP carry-over, cumulative-knockdown tracking, a rust/steel palette
treatment, and its own pre-fight title, rank display, score-tally name, and
championship belt screen.

It is a plain 2 MB LoROM patch. All new code lives in bank-$00 and bank-$01
free space; a few hook sites in banks $08 and $0D redirect the engine into
those stubs, and single-byte pokes in bank $01 / bank $0D shift the
circuit-select layout down four rows to fit the fifth entry. Iron mode is
gated on WRAM flag $7E:1D71 (and belt-screen flag $7E:1D72), so vanilla
circuits fall through to the original code path untouched.

This builder is self-contained: the full record set below is the authoritative
byte-level source, annotated per record with its SNES address and role. Each
record's address is documented against the hook-site / stub-layout tables in
doc/standalone/IRON_CIRCUIT.md. The builder applies the records on top of a
vanilla ROM, computes the SNES header checksum, and emits the standalone IPS.
The checksum is derived (not stored), so the emitted patch is reproducible
from the vanilla ROM alone.

Usage:
    python build_spo_iron_circuit.py <vanilla.sfc> [out.sfc]

Output: patches/standalone/spo_iron_circuit.ips
"""
import os, sys, hashlib

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT_IPS = os.path.join(REPO, "patches", "standalone", "spo_iron_circuit.ips")
EXPECTED_BASE_MD5 = "97fe7d7d2a1017f8480e60a365a373f0"

CHK_LO = 0x7FDC   # 2 bytes: complement (LE)
CHK_HI = 0x7FDE   # 2 bytes: checksum   (LE)

# Byte-level record set. Each entry is (file_offset, hex_bytes). The trailing
# comment gives the SNES bank:addr (LoROM: file = bank*0x8000 + (addr-0x8000))
# and the record's role. HOOK = redirect at an engine site; STUB = new code in
# free space; the single-byte pokes shift the circuit-select layout.
RECORDS = [
    (0x0016A5, "2217f900ea"),  # $00:96A5  HOOK stamina-init override (carry-over restore + +16 recovery)
    (0x001C18, "225af7"),  # $00:9C18  HOOK BG2 palette override (iron rust; gated $1D71 or $1D72)
    (0x001C1C, "eaeaeaea"),  # $00:9C1C  (cont) BG2 palette hook tail
    (0x003203, "dafc"),  # $00:B203  HOOK exit-iron-flag-clear (game-over path)
    (0x003217, "fdfc"),  # $00:B217  HOOK exit-iron-flag-clear (retire path)
    (0x003227, "48f9"),  # $00:B227  HOOK stamina-stash (KO post-match)
    (0x003231, "2053fa"),  # $00:B231  HOOK B231_INIT clears belt-screen flag every post-fight
    (0x00324B, "48f9"),  # $00:B24B  HOOK stamina-stash (TKO post-match)
    (0x003250, "5c24f700"),  # $00:B250  HOOK POST_MATCH 16-opp chain driver
    (0x003270, "5c47f700"),  # $00:B270  HOOK DISPATCH iron-final-fight credits path
    (0x003F81, "20e1f9"),  # $00:BF81  HOOK belt-screen palette override (rust BG2 + steel belt)
    (0x0046A6, "20e0f8eaeaea"),  # $00:C6A6  HOOK KD-increment; force-KO on 3rd cumulative
    (0x0069F7, "5c59f900"),  # $00:E9F7  HOOK HP-bar tween fix (carry-over fights)
    (0x00761A, "c22029ff008dd400af"),  # $00:F61A  STUB inlined $D1FC body + IRON tile-row writer
    (0x007624, "800d186dd400aabf00000d8dd400e220aed400bf00000dd002806cc22029ff000a8dd600aed400bf02000d8dd000af28800d186dd600aabf00000daae220bf00000d8570e88ed200"),  # $00:F624  STUB (cont) descriptor renderer inline
    (0x00766D, "d400bf01000debaed200bf00000de88ed200c9ffd005aed0"),  # $00:F66D  STUB (cont)
    (0x007686, "800bc221aed0009f00007ee220e8e88ed000c670d0d0c221add4006904008dd400e22080898b4babc220a28055a9ff009f00007ee8e8e00056d0f5a28c55a00000b9ecf69f00007ee8e8c8c8c00800d003a29855c01600d0e8abe220a90485146424a200006b121c1b1c181c171c0c1c121c1b1c0c1c1e1c121c1d1cade507c904d00fa9018f711d7e9c0006a9038d01066b8d01060a0a8d00066beaeaeace0206af711d7ef00cad0006c910b009490f8d02065cb18800a9008f711d7e5cb6f900af711d7ef00aa9008f711d7e5cb6f9007c75b2e220af711d7ed004af721d7ef00ec220a281f78ba91f00540000ab6bc2208ba91f00540010ab6b27006f004e004d004c0026004b00"),  # $00:F686  STUB CONFIRM/POST_MATCH/DISPATCH/palette-swap/rust-palette/title/rank/portrait/KD
    (0x007790, "0028004b004a002900280002004b004d00e220af711d7ef026a91e8fe51f7ea9488fe61f7ea93c8fe71f7ea9368fe81f7ea9008fe91f7ec220a0e51fe8e86bc220b90000a86be2209c12079c1307ad0f0709018d0f07af711d7ed00ca502f0076868685c0cd2086ba9fd8d1207a9ff8d1307ad0006490ff0ee8502b90000c8c8c80ac22169c2618576aae220ad0006c902f00e2903c903f008a502c90a9002cacac220a9400c9f00007ea9500c9f40007e8a38e90010aaa50229ff00c90a009029a9612c9f02007ea9712c9f42007ea50229ff0038e90a001869602c9f04007e186910009f44007e80101869602c9f02007e186910009f42007ee220686868ad0006c902f00c2903c903d010a502c90a900ac220a576186908008008c220a57618690600aa5c45d208af711d7ef00ca500c902d008a2ac38867a6beaeaeaa500c90bf006a2a838867a6ba2ac38867a6ba59da81a859daf711d7ef014afea1f7e1a8fea1f7ec9039004a903859da59d60a59d60a9008f"),  # $00:F790  STUB (cont) title/rank/portrait/KD/CONFIRM_RESET/stamina/stash/tween
    (0x007907, "1f7e8fee1f7ea9ff8feb1f7e5c02f700af711d7ef025afeb1f7ec9fff00f186910c9509002"),  # $00:F907  STUB CONFIRM_RESET wrapper region
    (0x00792D, "508d9f08a9506ba9508d9f08a9508f"),  # $00:F92D  STUB stamina init override
    (0x00793D, "1f7ea9506ba9508d9f086baf711d7ef007ad9f088feb1f7e2045c060af711d7ef04fafeb1f7ec9fff047186910c9509002a9508514a9388dcc508dce508dd0508dd2508dd4508dd6508dd8508dda508ddc508d0c518d0e518d10518d12518d14518d16518d18518d1a518d1c515cfbe900a95085145cfbe90020f5faa9808d0206a9018d03068f721d7ea90f8d0006a9038d01062045c020e8bea9008f721d7e5c9cb200af721d7ef025a281f7a06004a91f00540000a213faa04004a91f00540000a233faa0c005a91f0054000060a91f0054001060002147088b002d01d305f83e9c47ff7f4741e528a31c83184210c20142026b038410a614ea1c2f09d2115612bf17ff7f4741e528a31c83184210c20142026b039c0306a9008f721d7e8fed1f7e60e220af721d7ef026a90d8fe51f7ea9268fe61f7ea9238fe71f7ea9228fe81f7ea9008fe91f7ec220a0e51fe8e86bc220b90000a86be220af721d7ef0016b220ad8086b"),  # $00:F93D  STUB stash/HP-bar tween/CHAMP_SCREEN/CHAMP_PAL/B231_INIT/CHAMP_TITLE
    (0x007AA5, "48af721d7ef01be05656d016682900ff480961008f54567e680966009f00007e186b689f00007e186b48af721d7ef01ae05656d015682900ff480971008f94567e680976009f40007e6b689f40007e6bdaafee1f7ec9039002fa601a8570c220ad080629ff00aae220bfe80f70f00aa570dfe80f709002fa60a5709fe80f709fe81f70fa60c221ad080629ff00aae220bfe80f70d0016b3ac900d003821101c901d003828500a9018fa85d7ea93c8fa95d7ea9068f"),  # $00:FAA5  STUB TEXT_SKIP/W-L digit override/SAVE_STUB/DRAW_STUB
    (0x007B5B, "5d7ea93c8fab5d7ea99e8fac5d7ea93d8fad5d7ea99f8fae5d7ea93d8f"),  # $00:FB5B  STUB (cont)
    (0x007B79, "5d7ea9808fb05d7ea93d8fb15d7ea9028fb45d7ea93c8fb55d7ea9998fb65d7ea93d8fb75d7ea99a8fb85d7ea93d8fb95d7ea99b8fba5d7ea93d8fbb5d7ea99c8fbc5d7ea93d8fbd5d7ea99d8fbe5d7ea93d8fbf5d7e6ba9018fa85d7ea93c8fa95d7ea9068faa5d7ea93c8fab5d7ea99e8fac5d7ea93d8fad5d7ea99f"),  # $00:FB79  STUB (cont) DRAW_STUB body
    (0x007BF7, "ae5d7ea93d8faf5d7ea9808fb05d7ea93d8fb15d7ea9018fb45d7ea93c8fb55d7ea9998fb65d7ea93d"),  # $00:FBF7  STUB (cont)
    (0x007C21, "b75d7ea99a8fb85d7ea93d8fb95d7ea99b8fba5d7ea93d8fbb5d7ea99c8fbc5d7ea93d8fbd5d7ea99d8fbe5d7ea93d8fbf5d7e6ba9018fa85d7ea9288fa95d7ea9068faa5d7ea9288fab5d7ea99e8fac5d7ea9298fad5d7ea99f8fae5d7ea9298faf5d7ea9808fb05d7ea9298fb15d7ea9008fb45d7ea9288fb55d7ea9998fb65d7ea9298fb75d7ea99a8fb85d7ea9298fb95d7ea99b8fba5d7ea9298fbb5d7ea9ef8fbc5d7ea9008fbd5d7ea9ef8fbe5d7ea9008fbf5d7e6b08e220af711d7ef016a9008f711d7ec230a90000a21e009f40047ecaca10f8284c378808e220af711d7ef016a9008f711d7ec230a90000"),  # $00:FC21  STUB (cont) DRAW_STUB tail
    (0x007D12, "1e009f40047eca"),  # $00:FD12  STUB EXIT_FLAG_CLEAR (game-over)
    (0x007D1A, "10f8284c9588"),  # $00:FD1A  STUB EXIT_FLAG_CLEAR (retire)
    (0x009EBB, "20e0f7"),  # $01:9EBB  HOOK continue reset (cumulative KD / sentinel / loss counter)
    (0x009EEC, "20b2f7eaeaea"),  # $01:9EEC  HOOK score-tally circuit-name override (IRON CIRCUIT TOTAL)
    (0x009F72, "22d4fe01eaeaeaea"),  # $01:9F72  HOOK phase-bypass (skip stamina drain/recovery anim)
    (0x00A0C7, "2002ffea"),  # $01:A0C7  HOOK fast-cascade (score-tally per-iter delay 8->1)
    (0x00A27E, "20d0f7"),  # $01:A27E  HOOK recovery formula override (feed cumulative KD)
    (0x00A2EC, "20a5f7"),  # $01:A2EC  HOOK champion-bonus drain suppression
    (0x00A381, "20a5f7"),  # $01:A381  HOOK champion-bonus drain suppression
    (0x00A416, "20a5f7"),  # $01:A416  HOOK aggregate BEST TIME suppression
    (0x00A99C, "20f5fe"),  # $01:A99C  HOOK stamina-bonus zero (A=0 on iron)
    (0x00AAF2, "2084f7eaeaeaeaeaeaeaeaeaeaeaeaeaeaeaeaea"),  # $01:AAF2  HOOK REST +1 award suppression (freeze $0606 + tile)
    (0x00B0F3, "204bff"),  # $01:B0F3  HOOK no-op trampoline in CODE_01B0F0 (replicate eaten bytes)
    (0x00B7D6, "2030ffea"),  # $01:B7D6  HOOK slot-kill also zeros iron W/L SRAM bytes
    (0x00B8DD, "01"),  # $01:B8DD  HOOK circuit-select support byte
    (0x00B93C, "a903ea"),  # $01:B93C  HOOK show-special (Championship circuit-select)
    (0x00B94D, "221af600eaea"),  # $01:B94D  HOOK descriptor render trampoline (JSL to bank-00 stub)
    (0x00B95A, "20ff"),  # $01:B95A  HOOK iron W/L draw trampoline (Championship)
    (0x00B96A, "00"),  # $01:B96A  HOOK circuit-select support byte
    (0x00B96D, "00"),  # $01:B96D  HOOK circuit-select support byte
    (0x00B999, "2f"),  # $01:B999  HOOK circuit-select support byte
    (0x00B9CD, "2203f900eaeaeaeaeaeaea"),  # $01:B9CD  HOOK confirm (JSL CONFIRM_RESET wrapper)
    (0x00BCDB, "a903"),  # $01:BCDB  HOOK show-special (Time Attack circuit-select)
    (0x00BD2A, "28ff"),  # $01:BD2A  HOOK iron W/L draw trampoline (Time Attack)
    (0x00CF15, "2012ff"),  # $01:CF15  HOOK circuit-select support
    (0x00DD23, "2012ff"),  # $01:DD23  HOOK circuit-select support
    (0x00E5ED, "59"),  # $01:E5ED  Circuit-select digit/layout shift (5-circuit layout, +4 rows)
    (0x00E5F3, "59"),  # $01:E5F3  Circuit-select digit/layout shift (5-circuit layout, +4 rows)
    (0x00E5F8, "59"),  # $01:E5F8  Circuit-select digit/layout shift (5-circuit layout, +4 rows)
    (0x00E5FE, "59"),  # $01:E5FE  Circuit-select digit/layout shift (5-circuit layout, +4 rows)
    (0x00E604, "59"),  # $01:E604  Circuit-select digit/layout shift (5-circuit layout, +4 rows)
    (0x00E609, "59"),  # $01:E609  Circuit-select digit/layout shift (5-circuit layout, +4 rows)
    (0x00E60E, "59"),  # $01:E60E  Circuit-select digit/layout shift (5-circuit layout, +4 rows)
    (0x00E613, "59"),  # $01:E613  Circuit-select digit/layout shift (5-circuit layout, +4 rows)
    (0x00E618, "59"),  # $01:E618  Circuit-select digit/layout shift (5-circuit layout, +4 rows)
    (0x00E628, "59"),  # $01:E628  Circuit-select digit/layout shift (5-circuit layout, +4 rows)
    (0x00E632, "59"),  # $01:E632  Circuit-select digit/layout shift (5-circuit layout, +4 rows)
    (0x00E636, "59"),  # $01:E636  Circuit-select digit/layout shift (5-circuit layout, +4 rows)
    (0x00E63C, "59"),  # $01:E63C  Circuit-select digit/layout shift (5-circuit layout, +4 rows)
    (0x00E640, "59"),  # $01:E640  Circuit-select digit/layout shift (5-circuit layout, +4 rows)
    (0x00E64D, "59"),  # $01:E64D  Circuit-select digit/layout shift (5-circuit layout, +4 rows)
    (0x00E651, "59"),  # $01:E651  Circuit-select digit/layout shift (5-circuit layout, +4 rows)
    (0x00E65B, "59"),  # $01:E65B  Circuit-select digit/layout shift (5-circuit layout, +4 rows)
    (0x00E65F, "59"),  # $01:E65F  Circuit-select digit/layout shift (5-circuit layout, +4 rows)
    (0x00E665, "59"),  # $01:E665  Circuit-select digit/layout shift (5-circuit layout, +4 rows)
    (0x00E669, "59"),  # $01:E669  Circuit-select digit/layout shift (5-circuit layout, +4 rows)
    (0x00E66E, "59"),  # $01:E66E  Circuit-select digit/layout shift (5-circuit layout, +4 rows)
    (0x00E672, "59"),  # $01:E672  Circuit-select digit/layout shift (5-circuit layout, +4 rows)
    (0x00E676, "59"),  # $01:E676  Circuit-select digit/layout shift (5-circuit layout, +4 rows)
    (0x00E67A, "59"),  # $01:E67A  Circuit-select digit/layout shift (5-circuit layout, +4 rows)
    (0x00E67E, "59"),  # $01:E67E  Circuit-select digit/layout shift (5-circuit layout, +4 rows)
    (0x00E682, "59"),  # $01:E682  Circuit-select digit/layout shift (5-circuit layout, +4 rows)
    (0x00F784, "e220af711d7ed016c220ee0606af7c567e1a8f7c567e186910008fbc567ec22060af711d7ef003a90060ad00066008c230af711d7e29ff00d00828bd139f20a6a760a269fa8ed00020bda728af711d7ef005afea1f7e60"),  # $01:F784  STUB REST_NO_GROW/DRAIN_SKIP/TALLY_NAME/RECOVERY_OVERRIDE
    (0x00F7DC, "9d0860"),  # $01:F7DC  STUB (cont)
    (0x00F7E0, "ce0606af711d7ef015a9008fea1f7ea9ff8feb1f7eafee1f7e1a8fee1f7e60"),  # $01:F7E0  STUB CONTINUE_RESET
    (0x00FED4, "af711d7ef00aa90185786868684c52c72059a8f0066868684c98a26868684c7a9faf711d7ef003a90060add00060af711d7ef005a901857860"),  # $01:FED4  STUB PHASE_BYPASS/BONUS_ZERO/FAST_CASCADE
    (0x00FF0E, "08857860af721d7ef003a91060ad090660"),  # $01:FF0E  STUB (cont)
    (0x00FF20, "20c5e5222afb00602057cb222afb0060a9009fe80f709fe81f70af05007060bebd2abbaaeda6bebabc9ba6a90ceb60008f721d7e60"),  # $01:FF20  STUB iron W/L draw trampolines/SLOT_KILL/STARTUP_TRAMPOLINE
    (0x04409C, "96fa00"),  # $08:C09C  HOOK belt-screen TEXT_SKIP (opponent records)
    (0x0440AF, "96fa00"),  # $08:C0AF  HOOK belt-screen TEXT_SKIP (TOTAL SCORE label)
    (0x0440C7, "96fa00"),  # $08:C0C7  HOOK belt-screen TEXT_SKIP (TOTAL SCORE numerals)
    (0x0440D8, "2261fa00"),  # $08:C0D8  HOOK belt-screen title (stage IRON letter bytes)
    (0x04519D, "22a1f700"),  # $08:D19D  HOOK pre-fight title override (IRON*CIRCUIT)
    (0x0451C5, "22d6f700"),  # $08:D1C5  HOOK pre-fight rank renderer (#15..#1 / CHAMP)
    (0x0452AB, "22b9f800ea"),  # $08:D2AB  HOOK pre-fight portrait shift (iron+opp2 / SMM)
    (0x04574E, "22a5fa00"),  # $08:D74E  HOOK belt-screen W/L digit override (write 16)
    (0x045755, "22cefa00"),  # $08:D755  HOOK belt-screen W/L digit override (cont)
    (0x06ADA2, "54"),  # $0D:ADA2  Circuit Select descriptor row shift
    (0x06ADA6, "54"),  # $0D:ADA6  Circuit Select descriptor row shift
    (0x06ADAA, "53"),  # $0D:ADAA  Circuit Select descriptor row shift
    (0x06ADAE, "53"),  # $0D:ADAE  Circuit Select descriptor row shift
    (0x06ADB2, "52"),  # $0D:ADB2  Circuit Select descriptor row shift
    (0x06ADB6, "52"),  # $0D:ADB6  Circuit Select descriptor row shift
    (0x06ADBA, "51"),  # $0D:ADBA  Circuit Select descriptor row shift
    (0x06ADBE, "51"),  # $0D:ADBE  Circuit Select descriptor row shift
    (0x06ADC2, "58"),  # $0D:ADC2  Circuit Select descriptor row shift
    (0x06ADC6, "5800"),  # $0D:ADC6  Circuit Select descriptor row shift
    (0x06FA69, "c6552c07ffffff121b18170000"),  # $0D:FA69  STUB IRON tally descriptor
]


def stamp_checksum(rom):
    """Plain LoROM checksum at $00:FFDC..$00:FFDF (2MB, power-of-2)."""
    buf = bytearray(rom)
    buf[CHK_LO:CHK_LO + 2] = b"\xFF\xFF"
    buf[CHK_HI:CHK_HI + 2] = b"\x00\x00"
    chk = sum(buf) & 0xFFFF
    cmp_ = chk ^ 0xFFFF
    rom[CHK_LO:CHK_LO + 2] = bytes([cmp_ & 0xFF, (cmp_ >> 8) & 0xFF])
    rom[CHK_HI:CHK_HI + 2] = bytes([chk & 0xFF, (chk >> 8) & 0xFF])
    return chk, cmp_


def build_ips(records):
    out = bytearray(b"PATCH")
    for off, chunk in records:
        out += off.to_bytes(3, "big")
        out += len(chunk).to_bytes(2, "big")
        out += chunk
    out += b"EOF"
    return bytes(out)


def main(vanilla_path, out_rom=None):
    with open(vanilla_path, "rb") as f:
        vanilla = f.read()
    md5 = hashlib.md5(vanilla).hexdigest()
    assert md5 == EXPECTED_BASE_MD5, \
        f"base ROM MD5 mismatch: got {md5}, expected {EXPECTED_BASE_MD5}"

    records = [(off, bytes.fromhex(h)) for off, h in RECORDS]

    rom = bytearray(vanilla)
    for off, chunk in records:
        rom[off:off + len(chunk)] = chunk

    chk, cmp_ = stamp_checksum(rom)
    print(f"checksum: ${chk:04X}  complement: ${cmp_:04X}")

    # Insert the checksum record (derived from the patched ROM, not stored) in
    # ascending-offset position so the emitted IPS matches the record order of
    # the shipped artifact.
    all_records = sorted(records + [(CHK_LO, bytes(rom[CHK_LO:CHK_HI + 2]))])
    ips = build_ips(all_records)

    os.makedirs(os.path.dirname(OUT_IPS), exist_ok=True)
    with open(OUT_IPS, "wb") as f:
        f.write(ips)

    total = sum(len(c) for _, c in all_records)
    print(f"wrote {OUT_IPS}  ({len(all_records)} records, {total}B patched, {len(ips)}B IPS)")

    if out_rom:
        with open(out_rom, "wb") as f:
            f.write(rom)
        print(f"wrote {out_rom}  MD5 {hashlib.md5(bytes(rom)).hexdigest()}")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        sys.exit(f"usage: python {os.path.basename(__file__)} <vanilla.sfc> [out.sfc]")
    main(sys.argv[1], sys.argv[2] if len(sys.argv) > 2 else None)
