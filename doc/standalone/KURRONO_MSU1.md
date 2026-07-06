# `spo_msu1_v6.ips` — MSU-1 Audio Patch

> This patch was originally authored by **Kurrono** and published at
> [zeldix.net/t1951-super-punch-out](https://www.zeldix.net/t1951-super-punch-out).
> This document exists for update, preservation and compatibility purposes —
> to record what the patch does, how it interacts with Special Edition, and
> what is needed to make full use of it.
>
> `patches/standalone/spo_msu1_v6.ips` is a fixed version of the original v5
> with three corrections applied:
> 1. **Loop-flag bug fix** — three non-looping tracks (Win `$60`, Opponent Down
>    `$63`, Circuit Clear `$6F`) were missing from the stub's hardcoded
>    no-loop list and would incorrectly loop. The fix adds the three missing
>    `CMP/BEQ` pairs, growing the stub from 114B to 126B.
> 2. **`BNE spcFallback` offset fix** — inserting 12 bytes into the loop-flag
>    block shifted `spcFallback` by +12, but the branch offset was not updated.
>    Without this fix, the track-missing SPC fallback jumps to mid-function
>    garbage code and deadlocks, making the patch non-functional on any setup
>    without PCM files (including plain vanilla SNES).
> 3. **Checksum correction** — the original release had an incorrect SNES
>    header checksum at `0x7FDC`. Now computed correctly per the SNES ROM
>    header spec for non-power-of-2 ROMs: the 2MB base is summed normally,
>    and the 512KB remainder is repeated 4× (to match the 2MB base size)
>    before being summed and added. Reference:
>    [SnesLab — SNES ROM Header](https://sneslab.net/wiki/SNES_ROM_Header).
>
> No other bytes were changed.

## YouTube clip

[![Watch the video](https://img.youtube.com/vi/a1BCDnfIPiA/mqdefault.jpg)](https://www.youtube.com/watch?v=a1BCDnfIPiA)

---

## What it does

Hooks the game's SPC700 music-trigger routine and redirects playback through
the **MSU-1** co-processor when MSU-1 hardware is present. MSU-1 is a custom
SNES co-processor specification (by Near/byuu) that allows a ROM to stream
CD-quality 44.1 kHz stereo PCM audio, replacing the game's native SPC700
music entirely. If MSU-1 hardware is not detected at runtime, the patch falls
back to the original SPC700 audio transparently — vanilla music plays normally.

The patch does **not** include PCM audio files. Those must be sourced from
the original thread at [zeldix.net/t1951-super-punch-out](https://www.zeldix.net/t1951-super-punch-out),
which contains links to the PCM pack.

---

## Hardware and software requirements

| Platform | Support |
|---|---|
| Emulators (Mesen, bsnes, Snes9x 1.60+) | ✅ MSU-1 supported natively |
| MiSTer FPGA | ✅ MSU-1 supported |
| Real SNES + repro cart (no MSU-1) | ✅ SPC fallback plays vanilla audio |
| Real SNES + SD2SNES / FXPak Pro | ✅ MSU-1 supported via firmware |

**Note on real hardware:** the MSU-1 stub lives at SNES `$40:8000`
(file `0x200000`). The patch expands the ROM from 2MB to 2.5MB to
accommodate the stub and its zero-fill padding. On a repro cart the stub
bytes are burned onto the chip at that address and execute correctly — the
stub checks `$2002` for the MSU-1 signature and falls back to SPC audio if
it is not present. A repro cart on a standard SNES without MSU-1 hardware
will play vanilla SPC audio normally. An MSU-1 patched rom on SD2SNES / FXPak Pro
with MSU-1 firmware will play the PCM audio. The patch is real-hardware
compatible on any cart that holds the full 2.5 MB ROM image.

---

## Patch records

4 real records (the remainder are zero-fill padding):

| File offset | Size | Effect |
|---|---|---|
| `0x00EC6D` | 4 B | Hook: `JSL $40:8000` — replaces the music-trigger call at SNES `$01:EC6D` |
| `0x044C0C` | 3 B | Hook: `JSL $40:8070` — mutes the demo/intro at SNES `$08:CC0C` (updated from `$40:8064` to match stub's new size) |
| `0x200000` | 126 B | MSU-1 stub at SNES `$40:8000` (114B original + 12B loop-flag fix) |
| `0x20007E–0x27FFFF` | ~512 KB | Zero-fill — pads the file so the IPS patcher can write the stub at `0x200000`; contains no executable or data content |
| `0x007FDC` | 4 B | SNES header checksum |

---

## Assembler source

Original source by Kurrono, reproduced verbatim with the loop-flag fix applied.
Lines marked `; [FIXED]` are additions not present in the original v5 source:

```asm
; Super Punch-Out!!
; Date: 2019.08.16
;
; Changelog:
;	- (2019.08.16) added spc fallback, hopefully it is good, PeV
;	- (2019.08.16) added LDX #$22 and TXA before JSL msuRoutine so correct track values write to STA $2004


lorom

org $01EC6d ; do msu1 and mutes the game
JSL msu


org $08cc0b
JSL mutedemo

org $408000
msu:
PHA
TXA
PHP ;save processor status
SEP #$20
lda $2002
CMP #$53
BEQ msufound
PLP ;restore processor status
PLA ;native code if no msu
LDX $22
CPX $39
RTL

msufound:
PLP ;restore processor status
PLA ;get track number from stack

PHA
PHP ;save processor status again
SEP #$20
LDX $22 ; <----- i moved this here to get msu-1 to play correctly, PeV
TXA ; <----- i moved this here to get msu-1 to play correctly, PeV
STZ $2006
STA $2004
STZ $2005
loop:
BIT $2000
BVS loop
PHA
; -- PCM PRESENT CHECK, FOR SPC FALLBACK --
	LDA $2000 ; load msu status register value to check if track is present or missing
	AND #$08 ; isolate track missing bit
	BNE spcFallback ; [FIXED] offset updated (+12) to account for the 3 new CMP/BEQ pairs above
; -- PCM PRESENT CHECK, FOR SPC FALLBACK --
PLA
cmp #$60    ; [FIXED] Win — was missing, incorrectly looped in v5
BEQ noloop
cmp #$61
BEQ noloop
cmp #$62
BEQ noloop
cmp #$63    ; [FIXED] Opponent Down — was missing, incorrectly looped in v5
BEQ noloop
cmp #$6C
BEQ noloop
cmp #$6F    ; [FIXED] Circuit Clear — was missing, incorrectly looped in v5
BEQ noloop
cmp #$71
BEQ noloop
cmp #$70
BEQ noloop
LDA #$03
BRA endroutine
noloop:
LDA #$01
endroutine:
STA $2007
LDA #$FF
STA $2006

PLP ;restore processor status
PLA
LDX #$00
CPX $39
RTL

spcFallback:
PLA
PLP
PLA
LDX $22
CPX $39
RTL



mutedemo:
JSL $01f800
PHA
CMP #$00
STZ $2007
PLA
RTL

;------------------------------------------
;org $01EC75
;db $2F

;org $01F174 ;full mute
;STZ $24;20

;org $01ECF8 ;do msu1 with values correctly..but it dont mute
```

---

## Track mapping

| SPC hex | PCM track | Loop | Title |
|---|---|---|---|
| `$00` | 96 | no | Win |
| `$01` | 97 | no | Lose |
| `$02` | 98 | yes | Player Down |
| `$03` | 99 | yes | Opponent Down |
| `$04` | 100 | yes | Minor Circuit |
| `$05` | 101 | yes | Major Circuit |
| `$06` | 102 | yes | World Circuit |
| `$07` | 103 | yes | Special Circuit |
| `$08` | 104 | yes | Gabby Jay |
| `$09` | 105 | yes | Bear Hugger |
| `$0A` | 106 | yes | Piston Hurricane |
| `$0B` | 107 | yes | Bald Bull |
| `$0C` | 108 | no | Title |
| `$0D` | 109 | yes | Menu |
| `$0E` | 110 | yes | Tutorial |
| `$0F` | 111 | no | Circuit Clear |
| `$10` | 112 | no | Staff Roll |
| `$11` | 113 | no | Press Start Jingle |
| `$12` | 114 | yes | Bob Charlie |
| `$13` | 115 | yes | Dragon Chan |
| `$16` | 116 | yes | Masked Muscle |
| `$17` | 117 | yes | Mr. Sandman |
| `$1C` | 118 | yes | Aran Ryan |
| `$1D` | 119 | yes | Heike Kagero |
| `$1E` | 120 | yes | Mad Clown |
| `$64` | 121 | yes | Super Macho Man |
| `$67` | 122 | yes | Narcis Prince |
| `$6A` | 123 | yes | Hoy Quarlow |
| `$6E` | 124 | yes | Rick Bruiser |
| `$73` | 125 | yes | Nick Bruiser |
| `$77` | 232 | no | Unknown (possibly Title + Press Start Jingle combined) |

**Loop flags:** the stub marks these tracks as non-looping: 96 (Win), 97 (Lose), 98 (Player Down), 99 (Opponent Down), 108 (Title), 111 (Circuit Clear), 112 (Staff Roll), 113 (Press Start Jingle). All other tracks loop. Tracks 96, 99, and 111 were incorrectly looping in the original v5 — this is the fix.

---

## Compatibility with Special Edition

`spo_msu1_v6.ips` is bundled into `spo_special_edition_v2.0.ips`. Its
sub-2MB hooks (`0x00EC6D` and `0x044C0C`) are byte-disjoint from every
other SE patch. Its audio driver stub lives in the ExLoROM expansion
region at `0x200000..0x20007D`.

One patch shares that expansion region: `spo_alt_opponents_colors.ips`,
whose stubs and palette tables occupy `0x20047E..0x200B7F`. The two
data ranges do not overlap, but each patch's standalone IPS blankets the
whole `0x200000..0x27FFFF` window with zeros around its own data, so
applying one naively on top of the other would zero-wipe it. The
bundle builder resolves this by writing only each patch's non-zero
expansion bytes, then expanding and zero-filling the window once.

**Standalone apply order (MSU-1 only, no alt-opponent colors):**
```
vanilla → spo_msu1_v6.ips
```
Applied to a plain vanilla ROM, the MSU-1 patch stamps a valid checksum
on its own.

To combine MSU-1 with the full Special Edition, build the bundle with
`scripts/build_spo_se20_bundle.py`, which applies every patch in the correct
order and stamps the ExLoROM split+repeat checksum for the 2.5MB ROM.

---

## Setup

> The following instructions are adapted from the original documentation by Kurrono.

### Requirements

- Non-headered US ROM (`Super Punch-Out!! (U).sfc`). If your file has a `.smc`
  extension it likely has a 512-byte header and must be de-headered first.
- PCM audio files (sourced separately — see original thread).
- An MSU-1 capable emulator or flash cart (see hardware table above).

### Step 1 — Patch the ROM

Apply `spo_msu1_v6.ips` to the vanilla non-headered US ROM.

To combine with Special Edition, don't stack the IPS files by hand — build
the bundle with `scripts/build_spo_se20_bundle.py`, which merges MSU-1 with the
other patches and stamps the correct 2.5MB ExLoROM checksum.

### Step 2 — Name the ROM

The patched ROM can be named anything, but **the PCM files and `.msu` marker
file must share the same base name as the ROM**. The PCM pack distributed by
Kurrono uses the base name `spo_msu1`, so if you are using those files rename
the ROM to `spo_msu1.sfc`. If you are providing your own PCM files, any name
works as long as ROM and PCMs match.

### Step 3 — Assemble the folder

Create a folder and place all of the following inside it:

```
spo_msu1.sfc          ← patched ROM (from steps 1 and 2)
spo_msu1.msu          ← empty marker file (not included; create an empty file with this name)
spo_msu1-96.pcm       ← Win
spo_msu1-97.pcm       ← Lose
spo_msu1-98.pcm       ← Player Down
... (all PCM files)
```

### Step 4 — Play

Launch `spo_msu1.sfc` in your emulator. For **higan**, import the ROM first,
then navigate to `%USERPROFILE%\Emulation\Super Famicom\spo_msu1.sfc\` and
copy an empty `spo_msu1.msu` and all PCM files into that folder.

---

## Compatibility

- **Apply on top of**: original `Super Punch-Out!! (USA).sfc` ROM (MD5 `97fe7d7d2a1017f8480e60a365a373f0`)
- **Conflicts with**: nothing in this repo
- **Cheat-code compatibility**: unaffected

## Building

Built by [`scripts/build_spo_msu1_v6.py`](../../scripts/build_spo_msu1_v6.py):

```
python scripts/build_spo_msu1_v6.py <vanilla.sfc> [out.sfc]
```

The builder assembles the corrected v6 stub (loop-flag fix + `spcFallback` offset fix), applies it and the two hooks to a vanilla ROM, stamps the SNES header checksum, and writes `patches/standalone/spo_msu1_v6.ips`. Pass an optional output path to also emit the patched `.sfc`. It does **not** include or require the PCM audio files.

## Credits

- **Original patch author:** Kurrono
- **Source thread:** [zeldix.net/t1951-super-punch-out](https://www.zeldix.net/t1951-super-punch-out)

## See also

- [`ALT_OPPONENT_COLORS.md`](ALT_OPPONENT_COLORS.md) — the other patch that lives in the ExLoROM expansion region; the two share the `0x200000+` window with disjoint data.
