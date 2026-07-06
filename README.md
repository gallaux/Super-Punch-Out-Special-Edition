# Super Punch-Out!! Special Edition (Hack)

**Repository:** [github.com/gallaux/super-punch-out-special-edition](https://github.com/gallaux/super-punch-out-special-edition)

**Base ROM:** Super Punch-Out!! (USA, SNES) — MD5 `97fe7d7d2a1017f8480e60a365a373f0`
**Apply with:** Lunar IPS, flips, or any standard IPS patcher. Always patch the **original, unmodified ROM**.

<img width="256" height="224" alt="Super Punch-Out!! Special Edition (USA)_000" src="https://github.com/user-attachments/assets/dcd44da3-e7a0-441d-967d-4e4ea2cb5210" />
<img width="256" height="224" alt="Super Punch-Out!! Special Edition (USA)_001" src="https://github.com/user-attachments/assets/20bb0c6e-2d73-4ca2-ba18-6bb9584b7f50" />
<img width="256" height="224" alt="Super Punch-Out!! Special Edition (USA)_002" src="https://github.com/user-attachments/assets/69c1a244-62a4-4a1e-bbcf-620b26aabe52" />
<img width="256" height="224" alt="Super Punch-Out!! Special Edition (USA)_003" src="https://github.com/user-attachments/assets/01be897c-9646-4d94-b14b-6567c13cfb90" />
<img width="256" height="224" alt="Super Punch-Out!! Special Edition (USA)_004" src="https://github.com/user-attachments/assets/2c704d67-b230-4060-ac26-13cc3ef00705" />
<img width="256" height="224" alt="Super Punch-Out!! Special Edition (USA)_005" src="https://github.com/user-attachments/assets/58993886-b8ee-448e-84e2-52097d48c83f" />
<img width="256" height="224" alt="Super Punch-Out!! Special Edition (USA)_006" src="https://github.com/user-attachments/assets/760cbb00-aed1-4e54-b3f8-98602012b131" />
<img width="256" height="224" alt="Super Punch-Out!! Special Edition (USA)_007" src="https://github.com/user-attachments/assets/7df047bd-4246-4d27-b960-3dd721e94d85" />
<img width="256" height="224" alt="Super Punch-Out!! Special Edition (USA)_008" src="https://github.com/user-attachments/assets/25c4f5ad-a370-4fcb-8f48-7fdcc08e0615" />
<img width="256" height="224" alt="Super Punch-Out!! Special Edition (USA)_009" src="https://github.com/user-attachments/assets/df96538c-cf0d-421d-8eae-0a80f0f680a6" />
<img width="256" height="224" alt="Super Punch-Out!! Special Edition (USA)_010" src="https://github.com/user-attachments/assets/f2dcc2ec-4be8-4865-a6ce-c2047b04a73a" />
<img width="256" height="224" alt="Super Punch-Out!! Special Edition (USA)_011" src="https://github.com/user-attachments/assets/f183750a-60e4-46ab-9976-93d8e9635875" />

---

## Background

Super Punch-Out!! (1994, SNES) is one of the best arcade-style boxing games ever made. You play as an up-and-coming boxer fighting your way through four circuits of increasingly absurd opponents, each with their own patterns, tells, and personality. The gameplay is fast, stylish, and deeply satisfying to master — a perfect arcade-like experience that holds up completely.

This hack adds two major features the original game never had.

**VERSUS MODE.** Super Punch-Out!! contains a hidden 2-player mode that was never exposed through the normal menu. In this mode, holding a specific button combination causes Controller 2 to control the opponent — effectively turning a single-player game into a local versus match. This secret was first publicly discovered in 2022. This hack makes it a first-class feature: you select **VERSUS MODE** from the Mode Select menu just like any other mode. No combination, no guesswork.

**IRON CIRCUIT.** A brand-new fifth circuit added to Championship Mode — a 16-fighter gauntlet from Gabby Jay to Nick Bruiser. Stamina and knockdowns carry across every fight with only a small recovery bonus between matches. No extra continues can be earned; 3 losses and the run is over! Per-slot W/L records are saved on completion.

Beyond those two headliners, the hack also ships a collection of fixes and enhancements: alternate per-circuit glove colors with per-match overrides, alternate opponent color palettes, MSU-1 CD-quality audio support, typo corrections in fighter profiles and the tutorial demo, cosmetic title-screen tweaks, and a few quality-of-life additions (Japanese name-entry charset always available, a Credits entry in the Records View screen).

As it stands, this is the definitive version of the game. The Versus mode is inherently unbalanced — but it's the version I wish Nintendo had shipped back in the '90s. They eventually added a proper VS mode in the Wii sequel many years later. The "Special Edition" name is a nod to the original game's ultimate hidden circuit!

---

## What's in the Special Edition

- **VERSUS MODE** added to the Mode Select menu — 2-player matches launch directly, no secret button combo required
  - **Either controller can pick on the opponent-select screen** — P2 can choose their own fighter without handing the controller back
- **IRON CIRCUIT** — a fifth circuit in Championship Mode. A 16-opponent gauntlet through every fighter in the game, from Gabby Jay to Nick Bruiser. HP and Knockdowns carries over between fights with a small recovery bonus. Iron-themed presentation throughout, and per-slot best W/L record saved to SRAM.
- **Alternate glove colors**
  — each circuit has its own default glove color (mirroring Punch-Out!! Wii's per-opponent glove tones)
  - per-match override: hold **L** (blue), **R** (red), **X** (yellow), **Y** (green), or **L+R** (white) before the fight starts — on the opponent-select screen in Time Attack / Versus, or on the pre-fight opponent screen in Championship — and confirm with A or Start to enter the fight in the chosen color. The override applies only to that match; the next fight reseeds from the opponent default.
- **Alternate opponent color palettes** — hold **SELECT** before the fight starts to swap the opponent into an alternate color scheme. Each of the 16 fighters has a hand-authored alternate palette (many nodding to other games and characters). Works alongside the glove-color override.
- **MSU-1 audio support** — when run on MSU-1-capable hardware or emulators, streams CD-quality 44.1 kHz stereo music in place of the native SPC700 soundtrack, falling back to the original audio transparently when MSU-1 is not present. PCM audio files have to be sourced separately (see the MSU-1 doc). Originally authored by **Kurrono**.
- **Typo fixes:**
  - Mr. Sandman's profile stats (originally a verbatim copy of Super Macho Man's; restored to age 30, weight 270 lbs, record 28-4 — the correct values from the manual and Japanese version)
  - Mad Clown's weight (390 lbs → 370 lbs, matching the manual)
  - "SUPER MACHOMAN" → "SUPER MACHO MAN" across every screen in the game
  - "devestating" → "devastating" in the in-game tutorial demo
- **Cosmetic title-screen tweaks** — Special Circuit ring artwork and palette, plus a "SPECIAL EDITION" sub-title
- **Japanese name-entry character set** always available via L/R cycling (no hidden button combo needed)
- **CREDITS entry** added to the Records View screen — replays the ending cutscene's credits roll
- **Score overflow fix** — caps the running score at 999,990 so a high circuit total no longer wraps to a small number
- **Special Circuit always unlocks correctly** — the original ROM's security checksum that locks Special on save states / emulators / patched ROMs is bypassed

---

## Patch files

### [`spo_special_edition_v2.0.ips`](patches/spo_special_edition_v2.0.ips) — Special Edition (recommended)

The full experience: every standalone patch below bundled into a single IPS. The bundle expands the ROM from 2 MB to 2.5 MB (ExLoROM) to hold the alternate-opponent-palette data and the MSU-1 audio driver, and stamps the ExLoROM header checksum to match the combined ROM. Apply directly to the original ROM.

### Standalone patches

These are independent fixes that can be applied alone or mixed and matched, on top of the original ROM. Most are byte-level disjoint and can be applied in any order. Two of them — `spo_alt_opponents_colors.ips` and `spo_msu1_v6.ips` — both live in the ExLoROM expansion region (`0x200000+`) and each blankets that window with zero-fill around its own data; stacking their standalone IPS files by hand would zero-wipe the other. To combine everything, use the bundled `spo_special_edition_v2.0.ips`, which merges them correctly.

| File | What it does | Details |
|---|---|---|
| [`spo_versus_hack.ips`](patches/standalone/spo_versus_hack.ips) **(core hack)** | The core hack of this repo. Adds Versus Mode to the menu and lets either controller pick on the opponent-select screen. | [doc](doc/standalone/VERSUS_HACK.md) |
| [`spo_iron_circuit.ips`](patches/standalone/spo_iron_circuit.ips) | Adds a fifth IRON CIRCUIT entry to Championship Mode → Circuit Select. 16-opponent gauntlet, HP carry-over, cumulative KD tracking, iron-themed pre-fight presentation and championship belt screen, per-slot W/L completion stats SRAM persistence. | [doc](doc/standalone/IRON_CIRCUIT.md) |
| [`spo_alt_glove_colors.ips`](patches/standalone/spo_alt_glove_colors.ips) | Adds a per-circuit glove-color selector. Each circuit gets a different default color (mirroring how Punch-Out!! Wii dressed Little Mac across opponents), and the player can override per-match by holding L/R/X/Y/L+R at fight start. | [doc](doc/standalone/ALT_GLOVE_COLORS.md) |
| [`spo_alt_opponents_colors.ips`](patches/standalone/spo_alt_opponents_colors.ips) | Adds hand-authored alternate color palettes for all 16 opponents. Hold **SELECT** before the fight starts to swap the opponent into its alternate scheme. Lives in the ExLoROM expansion region and chains through the alt-glove hook, so it depends on `spo_alt_glove_colors.ips`. | [doc](doc/standalone/ALT_OPPONENT_COLORS.md) |
| [`spo_profile_stats_fix.ips`](patches/standalone/spo_profile_stats_fix.ips) | Fixes two profile-screen stat errors present in the US/EUR ROM: Mr. Sandman's stats are a verbatim copy of Super Macho Man's (restored to age 30, weight 270 lbs, record 28-4); Mad Clown's weight reads 390 lbs instead of 370 lbs. Both correct values match the US manual and the later-released Japanese version of the game. | [doc](doc/standalone/PROFILE_STATS_FIX.md) |
| [`spo_super_macho_man_fix.ips`](patches/standalone/spo_super_macho_man_fix.ips) | Fixes the "SUPER MACHOMAN" → "SUPER MACHO MAN" typo across all screens in the game. | [doc](doc/standalone/SUPER_MACHO_MAN_FIX.md) |
| [`spo_how_to_typo_fix.ips`](patches/standalone/spo_how_to_typo_fix.ips) | Fixes a single-letter typo in the in-game tutorial demo: "devestating" → "devastating". | [doc](doc/standalone/HOW_TO_TYPO_FIX.md) |
| [`spo_title_screen_special_ring.ips`](patches/standalone/spo_title_screen_special_ring.ips) | Cosmetic: replaces the title-screen ring logo and color palette with the Special Circuit variants for some extra flair. | [doc](doc/standalone/TITLE_SCREEN_SPECIAL_RING.md) |
| [`spo_title_screen_special_logo.ips`](patches/standalone/spo_title_screen_special_logo.ips) | Cosmetic: adds a SPECIAL EDITION text line to the title screen, below the main game logo. | [doc](doc/standalone/TITLE_SCREEN_SPECIAL_LOGO.md) |
| [`spo_jp_charset_enabled.ips`](patches/standalone/spo_jp_charset_enabled.ips) | Makes the Japanese character set L/R-cycling always active in name entry, starting on the Western set. The hidden button combo is no longer needed. | [doc](doc/standalone/JP_CHARSET_ENABLED.md) |
| [`spo_end_credits.ips`](patches/standalone/spo_end_credits.ips) | Adds a **CREDITS** entry to the Records View select screen. Selecting CREDITS launches the game's ending-cutscene credits roll. After the credits finish the game stays on the final screen and requires reset — that matches the original cutscene's behavior, not specific to this patch. | [doc](doc/standalone/END_CREDITS.md) |
| [`spo_score_overflow_fix.ips`](patches/standalone/spo_score_overflow_fix.ips) | Caps the running score at 999,990 so a high circuit total no longer overflows and wraps to a small number. | [doc](doc/standalone/SCORE_OVERFLOW_FIX.md) |
| [`spo_disable_security_checksum.ips`](patches/standalone/spo_disable_security_checksum.ips) | The World Circuit completion checksum prevents the Special Circuit from unlocking when using save states, emulators (SNES Classic, Switch NSO), or patched ROMs. This patch disables that checksum check. | [doc](doc/standalone/DISABLE_SECURITY_CHECKSUM.md) |
| [`spo_msu1_v6.ips`](patches/standalone/spo_msu1_v6.ips) | Adds MSU-1 audio support: streams CD-quality PCM music on MSU-1-capable hardware/emulators, falling back to the native SPC700 soundtrack when MSU-1 is absent. Expands the ROM to ExLoROM. Originally authored by **Kurrono** (loop-flag and checksum fixes applied here). PCM files sourced separately. | [doc](doc/standalone/KURRONO_MSU1.md) |

### Incomplete / experimental patches

These are proof-of-concept patches with known bugs. Not included in the **Special Edition** and not recommended for general use:

| File | What it does | Details |
|---|---|---|
| [`spo_sound_mode_incomplete.ips`](patches/incomplete/spo_sound_mode_incomplete.ips) | Proof-of-concept patch that adds a SOUND MODE entry to the title-screen menu. **Known bugs: pressing A on SOUND MODE triggers DATA CLEAR instead; name-entry screen behaves incorrectly after selecting NEW GAME or CONTINUE.** Wiring the actual Sound Library launch requires further investigation. | [doc](doc/incomplete/AUDIO_MODE_INCOMPLETE.md) |

---

## What's new in Special Edition

### Versus Mode

#### 1. VERSUS MODE on the Mode Select screen

The Mode Select screen gains a new **VERSUS MODE** entry between Championship and Time Attack. Selecting it launches a 2-player match directly, without needing any specific input combination.

- Unlock logic is preserved — Time Attack and Records View require Championship progress; Versus is always available.
- Backing out of opponent select returns to Mode Select cleanly.

#### 2. Player 2 controls the opponent

In Versus matches, **Controller 2 controls the opponent**. This is the same mechanic as the 2022-discovered secret mode, now wired in permanently whenever you enter from Versus.

#### 3. Correct in-game screen labels

The opponent-select screen shows **"VERSUS MODE"** as its header and **"< PLAYER 2 SELECT >"** as the prompt when entering from Versus. Time Attack is completely unaffected — it still shows "TIME ATTACK MODE" and "< OPPONENT SELECT >".

#### 4. Player 2 picks their own fighter

On the VERSUS opponent-select screen, **Controller 2's D-pad, A, and Start mirror Controller 1's** — so Player 2 can pick their own character without handing the controller back.

**How to play:** From the title screen choose **NEW GAME** or **CONTINUE**. At Mode Select choose **VERSUS MODE**. Either controller can drive the opponent-select screen. Once the match starts, **Controller 1 controls the left boxer** and **Controller 2 controls the right boxer**.

---

### Iron Circuit

#### 1. A fifth circuit

**IRON CIRCUIT** appears below SPECIAL CIRCUIT on the Championship Mode → Circuit Select screen. It is always selectable regardless of save state.

#### 2. 16-opponent gauntlet

Every fighter in the game, in order — Gabby Jay through Nick Bruiser. No HP recovery between matches. Winning each fight routes you directly to the next opponent.

#### 3. HP carry-over and cumulative knockdowns

Player stamina and knockdowns carries from one fight to the next with a +16 HP recovery bonus between fights.
Spending a continue resets both the HP stash and the KD counter, giving you a fresh 3-KD allowance and full HP for the next fight.

#### 4. Per-slot W/L records

After completing Iron Circuit for the first time on a slot, the Circuit Select screen shows `16 WIN N LOSS` next to the IRON CIRCUIT entry.

**How to play:** From Championship Mode select **IRON CIRCUIT**. Fight all 16 opponents in order. Manage your stamina — it carries into every fight. Survive all 16 to see the ultimate belt screen and save your record.

---

### Alternate Opponent Colors

Every one of the 16 opponents has a second, hand-authored color palette. Hold **SELECT** before the match starts — on the opponent-select screen in Time Attack / Versus, or on the pre-fight opponent screen in Championship — and the fighter appears in their alternate scheme for that match. Many of the palettes nod to other games and characters. The alternate-color override sits alongside the glove-color override (L/R/X/Y/L+R), so you can recolor both at once.

<img width="290" height="386" alt="Super Punch-Out!! Special Edition (USA)_Large Portraits Vanilla" src="https://github.com/user-attachments/assets/895bd995-a82e-41f0-ae21-4538ecf23bce" />
<img width="290" height="386" alt="Super Punch-Out!! Special Edition (USA)_Large Portraits Alt" src="https://github.com/user-attachments/assets/c25ce0e7-3071-4cd7-b61d-cfe458b6df75" />

---

### MSU-1 Audio

On MSU-1-capable hardware (SD2SNES / FXPak Pro, MiSTer) or emulators (Mesen, bsnes, Snes9x 1.60+), the soundtrack streams from CD-quality 44.1 kHz stereo PCM files instead of the native SPC700 chip. On any setup without MSU-1 — including a plain SNES with a repro cart — the game falls back to the original SPC700 audio transparently. The MSU-1 support was **originally authored by Kurrono**; this repo ships a fixed build (loop-flag and header-checksum corrections). The PCM audio files are not included and must be sourced separately — see [doc/standalone/KURRONO_MSU1.md](doc/standalone/KURRONO_MSU1.md) for setup.

---

## Incomplete implementation

- **"SOUND MODE" menu implementation**: a proof-of-concept UI patch exists (`patches/incomplete/spo_sound_mode_incomplete.ips`) but has three unresolved issues: (1) the cursor snap system uses tilemap-derived position values — the correct cursor value for the SOUND MODE row has not been empirically determined; (2) the `$14` item-count variable bleeds into name-entry and downstream screens; (3) the Sound Library (`CODE_00913B`) lives outside the normal state machine and can only be launched safely from a cold boot state. Full investigation documented in [doc/incomplete/AUDIO_MODE_INCOMPLETE.md](doc/incomplete/AUDIO_MODE_INCOMPLETE.md).

---

## Technical reference

For the full reverse-engineering notes — every patch address, the SNES memory map, the Mode Select state machine architecture, and the free-space inventory — see [doc/TECHNICAL.md](doc/TECHNICAL.md).
Key facts for anyone continuing this work:

- **ROM mapping:** LoROM for the base 2 MB (file offset = bank × 0x8000 + (SNES_addr − 0x8000)); the full Special Edition bundle expands to 2.5 MB **ExLoROM** so banks `$40`+ map to file `0x200000`+ to hold the alternate-opponent palette tables and the MSU-1 audio driver. The header makeup byte at `$00:FFD5` becomes `$32` and the header checksum uses the ExLoROM split+repeat formula.
- **Free space remaining (with the full Special Edition applied):** in the base 2 MB — ~213 bytes free in bank `$0D` (within the `$0DFA69–$0DFFE3` `%InsertGarbageData` zone, fragmented; max contiguous run 68 B at `$0D:FD25–$0D:FD68`), ~64 bytes free across bank `$01` (`UNK_01D722` tail + small zone tails), 1 byte at the end of bank `$01` `UNK_01F784`, and **~200 bytes free in bank `$00`** (the alt-opponent Hook 2 stub now occupies the head of `UNK_00F5D0` at `$00:FE18`). **~478 bytes total** across all base-ROM `%InsertGarbageData` zones. The ExLoROM expansion window (`0x200000–0x27FFFF`, ~512 KB) is almost entirely free apart from the MSU-1 driver (`0x200000–0x20007D`) and the alt-opponent stubs+palettes (`0x20047E–0x200B7F`).

---

## Cheat code compatibility

All known Action Replay / cheat codes for the original ROM remain fully compatible with every patch in this repository. The libretro cheat database for this title ([Super Punch-Out!! (World) (Action Replay).cht](https://github.com/libretro/libretro-database/blob/master/cht/Nintendo%20-%20Super%20Nintendo%20Entertainment%20System/Super%20Punch-Out!!%20(World)%20(Action%20Replay).cht)) contains two categories:

- **ROM-intercepting cheats** (PRO ACTION REPLAY codes that patch ROM reads) target addresses that none of our patches modify, so they apply cleanly on top of any combination of patches.
- **RAM cheats** (codes that write directly to WRAM at runtime) operate entirely independently of ROM content and are unaffected by any ROM patch.

No conflicts exist or are expected.

---

## Links and resources

- [**GitHub Repository**](https://github.com/gallaux/super-punch-out-special-edition) — Source, patch files, and documentation
- [**ROMhacking.net**](https://www.romhacking.net/hacks/9705/) — This rom hack's entry
- [**Super Punch-Out!! Disassembly**](https://github.com/Yoshifanatic1/Super-Punch-Out-Disassembly) — Full disassembly of the game; invaluable reference for this hack
- [**2-Player Mode Discovery**](https://x.com/new_cheats_news/status/1556727895778856960) — The tweet that revealed the hidden VS mode (Aug 8, 2022)
- [**The Cutting Room Floor**](https://tcrf.net/Super_Punch-Out!!_(SNES)) — Unused content and hidden features documentation
- [**GameHacking.org**](https://gamehacking.org/game/44921) — Game Genie / Pro Action Replay codes
- [**Punch-Out!! Wiki**](https://punchout.fandom.com/wiki/Super_Punch-Out!!_(SNES)) — Fan wiki with character, gameplay, and misc info
- [**SPU Sound Library**](https://github.com/RealVMMR/SPU-Sound_Library) — Lua script for manipulating SPC sound effects and music. Not related to this hack, but a cool project
