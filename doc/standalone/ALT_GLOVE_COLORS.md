# `spo_alt_glove_colors.ips` — Summary

Adds a runtime glove-color selector to the player's gloves. By default each circuit gets a per-opponent color (mirroring how Punch-Out!! Wii dressed Little Mac in different glove tones across circuits), and the player can force the glove color for the current match by holding a button before the fight starts: on the opponent-select screen in Time Attack / Versus mode, or on the pre-fight opponent screen in Championship mode. Hold the button and press A or Start to enter the fight with the chosen color.

<img width="256" height="224" alt="Super Punch-Out!! (USA) Alt Glove Colors_001" src="https://github.com/user-attachments/assets/ab78a0d0-9501-48e9-920d-6cf59af7b7f4" />
<img width="256" height="224" alt="Super Punch-Out!! (USA) Alt Glove Colors_002" src="https://github.com/user-attachments/assets/6252da4c-fca4-42a6-baee-6fb14fe95ca7" />
<img width="256" height="224" alt="Super Punch-Out!! (USA) Alt Glove Colors_003" src="https://github.com/user-attachments/assets/aadad097-cf9e-4467-b853-b9e31d3d1a54" />

## What it does

- **No button held** → use the opponent's circuit-default color.
  - **Minor circuit** (opponents 0-3) → vanilla green (Nintendo's original)
  - **Major circuit** (opponents 4-7) → blue
  - **World circuit** (opponents 8-11) → red
  - **Special circuit** (opponents 12-15) → yellow
  - **Iron circuit** (opponents 0-15) → white
- **L** → blue
- **R** → red
- **X** → yellow
- **Y** → force vanilla green (override even on a colored-default opponent)
- **L+R** → white

**Iron Circuit auto-default:** during iron-circuit gauntlet runs (when WRAM byte `$7E:1D71` is non-zero, owned by `spo_iron_circuit.ips`), gloves default to white if no manual button is held. Any manual override still wins. This is a cooperative behavior between the two patches via a shared WRAM byte — neither patch hard-depends on the other.

Override applies only to the current match. The next fight reseeds from the opponent's default (or iron auto-default if in iron circuit). All glove states render in the chosen mode's hue — rest, the powered-up cycling animation, the knock-out-punch / rapid-punch frames, the portrait HUD (rest + both powered-up frames), the BG-tile renders for the victory pose / knockdown / get-up animations, and the player sprite on the ending credits screen.

The "powered up" and "knock-out punch" terms come from the in-game training demo. Internal code symbols (`BLINK_*`, `SUPERARM_*`) keep their historical names; the prose uses the in-game terminology.

## Color reference

Each mode uses a 4-color glove ramp (palette indices 12-15) plus a coordinated 4-color knock-out-punch / rapid-punch ramp. Bytes are little-endian 15-bit BGR words; each 8-byte sequence is c12 c13 c14 c15.

| Mode | State | 8-byte sequence |
|---|---|---|
| **Blue** | Rest gloves | `E3 60 E3 69 A8 6A 50 6B` |
| | Powered-up | `6B 71 AB 7E C8 7F 50 7F` |
| | Knock-out-punch (orange flash) | `1C 01 BF 09 7F 12 5F 23` |
| **Red** | Rest gloves | `27 04 2E 04 74 0C FC 1C` |
| | Powered-up | `AF 14 F6 1C 9B 31 5F 4A` |
| | Knock-out-punch (gold flash) | `5C 02 FF 02 7F 13 FF 33` |
| **Yellow** | Rest gloves | `CA 00 F8 05 DD 12 BF 23` |
| | Powered-up | `52 11 BF 1E FD 37 BF 4F` |
| | Knock-out-punch (crimson flash) | `12 18 19 20 9F 28 DF 39` |
| **White** | Rest gloves (gray ramp to pure white) | `CE 39 B5 56 7B 6F FF 7F` |
| | Powered-up (steel blue) | `C4 28 8A 41 90 6A 98 7F` |
| | Knock-out-punch (vibrant red flash) | `10 08 D8 18 9F 31 5F 4A` |

Mode 0 (vanilla green) is unchanged from the original ROM — the fight-init trampoline early-exits when the chosen mode is 0, so no palette write happens. Each knock-out-punch hue is hand-picked rather than mechanically derived: blue→orange (true complement), red→gold (analogous-warm flare), yellow→crimson (warm-to-warm darkening), white→vibrant red (warm contrast against the cool steel-blue powered-up state).

## How it works

The patch is a runtime WRAM patch, not a ROM-data patch. The original `Layer1_Contender.bin` and per-fighter palette tables stay untouched. At fight init the trampoline writes the chosen mode's palette directly into WRAM, and per-frame hooks at the powered-up writer, the knock-out-punch writer, and the portrait writer apply the matching per-mode palettes for those animation states.

The mode flag at WRAM `$7E:1D70` is reseeded every fight init. There is no persistent state across matches.

### Glove animation state map

The player's glove animations span two rendering systems — sprites (most states) and BG layer 1 tiles (victory pose / knockdown / get-up). Each state has its own WRAM source:

| State | Render system | WRAM target | Source |
|---|---|---|---|
| Rest | sprite OAM palette 0 c12-c15 | `$7E:0518-$051F` | written by Hook 1 trampoline at fight init (MVN 1) |
| Powered-up (cycling charged-up animation) | sprite OAM palette 0 c12-c15 (same slot) | `$7E:0518-$051F` | engine snapshots rest, writes powered-up colors during animation, restores rest after — DD43 hook replaces the hardcoded immediates with a per-mode lookup |
| Knock-out-punch / rapid punches | sprite OAM palette 3 c12-c15 | `$7E:0578-$057F` | DDAA hook replaces the hardcoded immediates with a per-mode lookup; Hook 1 also pre-writes the chosen color into `$0578-$057F` (MVN 3) so the engine's snapshot/restore preserves it across attacks |
| Portrait HUD (rest + both powered-up frames) | sprite OAM palette 1 c12-c13 | `$7E:0538/$053A` | EC6E hooks at all 4 call sites detect frame and apply per-mode portrait color |
| Victory pose / knockdown / get-up | BG layer 1 with BG palette 2 c12-c15 | `$7E:0458-$045F` | Hook 1 trampoline writes per-mode rest colors here at fight init (MVN 2) |
| Ending credits screen (final stats / "THE END") | sprite OAM palette 4 c12-c15 | `$7E:0580-$058F` | Static ROM patch: `DATA_008547` (ColorEndScreen.bin) palette 4 c12-c15 at file `0x05DF` — vanilla green replaced with yellow (mode 3) |

### Hook layout

Five sites in bank `$00` redirect into stubs in bank `$0D` free space, plus one bank-`$00` trampoline + a portrait stub-rts inside the `UNK_00F5D0` garbage zone:

| Hook site | Original | Replaced with | Stub purpose |
|---|---|---|---|
| `$00:97E5` (file `0x017E5`) | `LDX #$0000; LDY #$3EE0` (universal fight-init) | `JSL $0D:FDD2 + 2×NOP` | Fight-init trampoline — read held buttons, decode override, opp-table fallback, write per-mode palette via 3 MVNs |
| `$00:DD43` (file `0x05D43`) | head of `CODE_00DD43` (powered-up palette writer) | `JSL $0D:FE80 + RTS` | Replaces hardcoded immediates with a per-mode lookup into the powered-up table |
| `$00:DDAA` (file `0x05DAA`) | head of `CODE_00DDAA` (knock-out-punch palette writer) | `JSL $0D:FEC0 + RTS` | Re-emits displaced bytes, then per-mode knock-out-punch lookup |
| `$00:EB1F`, `$00:EB9B`, `$00:EC68` (sep variant) | `JSR EC6E + SEP #$20` | `JSL $0D:FF68 + NOP` | Calls EC6E via bank-`$00` trampoline, frame-detects via `$0538`, applies per-mode portrait color |
| `$00:EC69` (rts variant) | `JSR EC6E + RTS` | `JSL $00:F5D5` | Same fixup as sep variant, but exits via intra-bank RTS for the bank-`$00` caller |
| `$00:EC64` | `BEQ +5 → $EC6B` | `NOP NOP` | Disables a BEQ that would land inside our 5-byte EC68 hook |

### L+R + iron-flag helper (`$0D:FE52`)

A small (24 B) helper stub at `$0D:FE52` is called from the trampoline's no-button-held fallback path. It checks two override conditions before falling back to the opp_table default:

1. **L+R held** (`$7E:0090` bits 4+5 both set) → return mode 4 (white)
2. **Iron-circuit flag set** (`$7E:1D71` non-zero, owned by `spo_iron_circuit.ips`) → return mode 4
3. **Else** → return `opp_table[opp_index]` (the circuit default)

The helper is only consulted when no individual L/R/X/Y button combination is resolved first by the trampoline's direct checks. The trampoline checks L+R (both held simultaneously) first at [14], then L alone at [22], then dispatches to the R-vs-X sub (`$0D:FE6A`) at [30] for R/X disambiguation. The helper only handles the auto-default case.

### R-vs-X sub (`$0D:FE6A`)

An 18 B sub at `$0D:FE6A` is reached via a `JMP` from trampoline offset [30] when neither L+R nor L alone was detected. It reads `$7E:0090` and tests bit 4 (R): if set → mode 2 (red), else → mode 3 (yellow, X implicit). It JMPs directly to the trampoline commit address (`$0D:FE12`) rather than returning, so no stack manipulation is needed.

### Cross-bank-RTS trap

`CODE_00EC6E` ends with intra-bank `RTS`, not `RTL`. JSL'ing it directly from bank `$0D` corrupts both the stack (RTS pops 2, JSL pushed 3) and PBR (RTS doesn't restore PBR — it stays at `$00`, so the CPU resumes at `$00:<offset>` instead of `$0D:<offset>`).

The portrait sep-variant stubs work around this with a 5-byte trampoline at `$00:F5D0` (`JSR EC6E + RTL`). The sep stubs `JSL` the trampoline; the trampoline does an intra-bank `JSR EC6E` (RTS-balanced) and then `RTL`s back to bank `$0D`.

The portrait rts-variant stub (site `$00:EC69`) handles a different stack scenario: site `EC69` is `JSR EC6E + RTS` inside `CODE_00EC87`, which itself was JSR'd from a bank-`$00` caller. The rts stub lives in bank `$00` so its closing `RTS` runs with PBR=`$00` and pops the bank-`$00` caller's return cleanly. The stub does `JSR EC6E` directly (intra-bank, balanced), runs the per-mode fixup, then `PLA PLA PLA` to drop our own JSL frame (PCL/PCH/PBR) before falling through to `RTS` to return to EC87's caller.

### MVN clobbers DBR

Hook 1's three MVNs each set DBR to the destination bank (`$7E`). The trampoline does `PHB` early and `PLB` near the exit so the displaced `LDX #$0000; LDY #$3EE0` instructions resume with the original DBR=`$0D`.

## Patch records

28 records, 795 bytes total (plus the SNES header checksum):

| File offset | Bytes | Effect |
|---|---|---|
| `0x05DF`, `0x05E1`, `0x05E5` | 1+3+2 | Ending credits screen: `DATA_008547` palette 4 c12-c15 → yellow (mode 3) (static, no code) |
| `0x017E5` | 6 | Hook 1: `JSL $0D:FDD2 + 2×NOP` (was `LDX #$0000; LDY #$3EE0`) |
| `0x05D43` | 5 | Powered-up hook: `JSL $0D:FE80 + RTS` |
| `0x05DAA` | 5 | Knock-out-punch hook: `JSL $0D:FEC0 + RTS` |
| `0x06B1F`, `0x06B9B`, `0x06C68` | 5 each | Portrait sep-variant hooks: `JSL $0D:FF68 + NOP` |
| `0x06C64` | 2 | NOP out the `BEQ +5` that targets inside our 5-byte EC68 hook |
| `0x06CE9` | 4 | Portrait rts-variant hook: `JSL $00:F5D5` |
| `0x075D0` | 5 | Bank-`$00` EC6E trampoline (`JSR EC6E + RTL + RTS`) |
| `0x075D5` | 69 | Bank-`$00` portrait stub-rts |
| `0x07D20` | 16 | Opponent → default-mode lookup table (`$00:FD20`) |
| `0x07D30` | 32 | Rest-palette color table (4 modes × 8 B, `$00:FD30`) |
| `0x07D50` | 40 | Powered-up color table (5 modes × 8 B, `$00:FD50`; mode 0 = vanilla) |
| `0x07D78` | 40 | Knock-out-punch color table (5 modes × 8 B, `$00:FD78`; mode 0 = vanilla) |
| `0x07DA0` | 48 | Portrait color table (3 frames × 4 modes × 4 B, `$00:FDA0`; indexed by frame*16 + (mode-1)*4) |
| `0x06FDAA` | 68 | Vanilla-restore of old bank-`$0D` table region (40 B) + Hook 1 trampoline first 28 B |
| `0x06FDEF` | 99 | Hook 1 fight-init trampoline last 99 B (button decode → opp-table/SELECT/iron via helper → triple MVN palette write) |
| `0x06FE52` | 24 | L+R + iron-flag helper stub |
| `0x06FE6A` | 18 | R-vs-X sub (R→mode 2, X implicit→mode 3; JMPs to commit at `$0D:FE12`) |
| `0x06FE80` | 60 | Powered-up stub |
| `0x06FEC0` | 64 | Knock-out-punch stub |
| `0x06FF00` | 32 | Vanilla-restore of old powered-up table location |
| `0x06FF40` | 32 | Vanilla-restore of old knock-out-punch table location |
| `0x06FF68` | 67 | Portrait sep-variant stub (frame detection + per-mode portrait writes) |
| `0x06FFAB` | 36 | Vanilla-restore of old portrait table location |

## Free space consumed

- **Bank `$00`** (`UNK_00F5D0` zone): 74 bytes at `$00:F5D0-$00:F619` (EC6E trampoline + portrait stub-rts) plus 176 bytes at `$00:FD20-$00:FDCF` for the relocated color tables. Total **250 B** in `UNK_00F5D0`.
- **Bank `$0D`** (`UNK_0DFA69` zone): 459 bytes used across the Hook 1 trampoline (128 B), L+R/iron helper (24 B), R-vs-X sub (18 B), powered-up stub (60 B), knock-out-punch stub (64 B), portrait sep stub (67 B), and small gaps. Total **459 B**.
- **In-place edits** (no free space consumed): 6 hook sites in bank `$00` (28 B total) and the ending-credits palette edit at `$00:85DF` (6 B).

Total ROM footprint: **~785 B** (including SNES header checksum, excluding vanilla-restore records which return relocated regions to their original vanilla state).

## Compatibility

- **Apply on top of**: original `Super Punch-Out!! (USA).sfc` ROM (MD5 `97fe7d7d2a1017f8480e60a365a373f0`)
- **Bundled into**: `spo_special_edition_v2.0.ips`
- **Conflicts with**: nothing in this repo
- **Cheat-code compatibility**: unaffected (no opponent palettes or fight-state machinery touched)
- **Cooperates with `spo_iron_circuit.ips`** via the shared WRAM byte `$7E:1D71` (iron flag). Either patch can be applied without the other; together they enable iron-circuit auto-default to mode 4 (white).

## Building

Built by [`scripts/build_spo_alt_glove_colors.py`](../../scripts/build_spo_alt_glove_colors.py):

```
python scripts/build_spo_alt_glove_colors.py <vanilla.sfc> [out.sfc]
```

The builder applies its record set to a vanilla ROM, stamps the SNES header checksum, and writes `patches/standalone/spo_alt_glove_colors.ips`. Pass an optional output path to also emit the patched `.sfc`.

## See also

The canonical source for byte-level patch contents is the IPS file itself ([`patches/standalone/spo_alt_glove_colors.ips`](../../patches/standalone/spo_alt_glove_colors.ips)) applied to the original `Super Punch-Out!! (USA).sfc` ROM. Every stub address, table location, and color value can be verified directly against the IPS.
