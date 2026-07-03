# `spo_iron_circuit.ips` — Summary

Adds a fifth entry, **IRON CIRCUIT**, to the Championship Mode → Circuit Select screen, below SPECIAL CIRCUIT. IRON CIRCUIT is a 16-opponent gauntlet that runs every fighter in order, from Gabby Jay to Nick Bruiser, without HP recovery between fights. Player stamina and cumulative knockdown count carry across every match.

<img width="256" height="224" alt="Super Punch-Out!! (USA) Iron Circuit_001" src="https://github.com/user-attachments/assets/a005e3ff-08a1-4835-b0f0-2491063453b7" />
<img width="256" height="224" alt="Super Punch-Out!! (USA) Iron Circuit_002" src="https://github.com/user-attachments/assets/e0ea490b-b416-480f-b68a-e84b5171c406" />
<img width="256" height="224" alt="Super Punch-Out!! (USA) Iron Circuit_003" src="https://github.com/user-attachments/assets/7c76f6fa-4ab5-441a-8996-d27526d97959" />
<img width="256" height="224" alt="Super Punch-Out!! (USA) Iron Circuit_004" src="https://github.com/user-attachments/assets/99b270df-257b-402d-b6b7-6b95b4aa1dd4" />
<img width="256" height="224" alt="Super Punch-Out!! (USA) Iron Circuit_005" src="https://github.com/user-attachments/assets/a10bcd41-bb2d-4a66-aba9-129f950a5871" />

## What it does

- **IRON CIRCUIT entry on Circuit Select** — always selectable, regardless of save state. The Circuit Select layout shifts up 4 rows so all five circuits fit; all decorations (brackets, subtitle, per-circuit W/L digits) move in lockstep.
- **16-opponent gauntlet** — fights proceed in opponent order from Gabby Jay through Nick Bruiser. The game routes directly to the next opponent after each win.
- **HP carry-over with +16 recovery** — player stamina carries from one fight to the next, capped at `$50` (max). The HP bar at fight start renders at the carry-over value immediately, with no tween.
- **Cumulative knockdown tracking** — a per-run knockdown counter accumulates across all fights. Stamina recovery on get-up degrades with each cumulative knockdown (1st: full recovery; 2nd: zero recovery; 3rd: forced KO).
- **Continue resets the run** — spending a continue resets the cumulative KD counter and the HP stash. The player gets a fresh 3-KD allowance and full HP for the next fight; the run's loss counter is incremented for the SRAM record.
- **REST counter frozen at 3** — the player's REST count does not increase during iron. The visible tile stays at 3 for the entire run.
- **Iron-specific presentation**:
  - Deep red (rust) BG2 palette on all iron fights and the pre-fight title screen.
  - `IRON⋆CIRCUIT` pre-fight title, centered, using the shared `⋆CIRCUIT` suffix already in ROM.
  - Iron rank display counting down from `#15` (Gabby Jay) to `#1` (Rick Bruiser), then `CHAMP` banner for Nick Bruiser (fight 16).
  - `IRON CIRCUIT TOTAL` label on the per-fight score-tally screen.
  - Stamina bonus omitted from the score-tally total (carry-over is the reward instead). The tally screen runs at accelerated speed on iron.
- **Celebration animation on the final fight** — the champion-defeated jump-and-turn animation fires after beating Nick Bruiser, matching the behavior of every other circuit's final fight.
- **Championship belt screen at iron-complete**:
  - `IRON CIRCUIT CLEAR` big-font title (replaces the SPECIAL CIRCUIT CLEAR text that would otherwise render).
  - Rust BG2 palette + steel-blue belt graphic.
  - Opponent records list and TOTAL SCORE line suppressed.
  - W/L line reads `16 Wins {N} Loss`.
  - Vanilla championship belt screens (MINOR/MAJOR/WORLD/SPECIAL) are unaffected.
- **Per-slot iron W/L persistence** — after completing iron for the first time on a save slot, the Circuit Select screen shows `16 WIN N LOSS` next to the IRON CIRCUIT entry on subsequent visits. `N` is the best (lowest) loss count achieved on that slot. Slot-independent. Never-completed slots show nothing.
- **No contamination of vanilla circuits** — all iron-specific hooks are gated on the iron flag. MINOR/MAJOR/WORLD/SPECIAL W/L digits, max-circuit records, and best-circuit scores are not affected by iron runs.
- **SPECIAL CIRCUIT always visible** — the SPECIAL CIRCUIT slot is always rendered on the Championship Mode and Time Attack circuit-select screens, even before the vanilla unlock condition is met. The slot remains greyed-out and unselectable until earned; only visibility changes.

## Gauntlet flow

1. From Championship Mode → Circuit Select, select **IRON CIRCUIT**.
2. The game enters a full 16-fight gauntlet: Gabby Jay (fight 1) through Nick Bruiser (fight 16).
3. Each fight ends with a BEST TIME screen (fights 1–15). Fight 16 plays the celebration animation, then renders the BEST TIME for Nick Bruiser, then the IRON CIRCUIT CLEAR belt screen, then credits.
4. A loss and continue resets cumulative KD and HP stash — the gauntlet continues from the next fight, not from fight 1.

## Technical architecture

Iron mode is implemented as a single byte at WRAM `$7E:1D71` (the **iron flag**), set to `$01` when the player confirms IRON CIRCUIT in the championship circuit-select, cleared to `$00` at iron-complete or on any post-fight exit (game-over or retire). Every iron-specific hook checks this flag and falls through to vanilla behavior when it is zero.

The patch hijacks Special Circuit's circuit identity (`$0601 = $03`) at iron entry, so all downstream circuit-themed asset loads (BG, ring, palette, announcer voice) reuse Special's data without per-asset hooks. Two additional flag-gated stubs override the BG2 palette (`$00:9C18`) and the pre-fight title (`$08:D19D`) to give iron its own deep-red look while leaving Special's purple intact.

The 16-opponent chain is driven by **POST_MATCH** at `$00:B250`, which on iron writes `$0602 = $0600 EOR $0F` between fights — nonzero for fights 1–15 (so the natural "circuit complete" branch never fires), zero for the transition into fight 16 (so the engine's celebration animation fires after the win). When `$0600` reaches `$10` (one past the 16th fighter), POST_MATCH clears the iron flag and routes through the **DISPATCH** stub at `$00:B270` to **CHAMP_SCREEN** at `$00:F9B6`, which restores `$0600 = $0F` and `$0601 = $03`, renders the BEST TIME (`JSR $C045`) and championship belt screen (`JSR $BEE8`), saves the iron W/L record to SRAM, and JMLs to credits at `$00:B29C`.

**Iron flag address note:** The iron flag lives at `$7E:1D71`. The vanilla confirm dispatch at `$01:B9C5` (shared by both the championship circuit-select and the Time Attack / VS opponent-select) reads `$07E5` and stores it into `$0601`. The CONFIRM stub at `$00:F702` is the sole writer of `$7E:1D71`: it checks `$07E5 == $04` (IRON cursor), sets the flag to `$01` on iron and leaves it `$00` on all other circuits. The belt-screen flag lives at `$7E:1D72`. The hook at `$01:B0F3` (inside `CODE_01B0F0`, the startup DP-set routine) is a no-op trampoline that replicates the eaten bytes — it does not write any WRAM flags, because `CODE_01B0F0` also fires during gameplay via `CODE_01802D` and writing flags there would clear them mid-execution.

### WRAM map

| Address | Role |
|---|---|
| `$7E:1D71` | Iron flag (`$01` = inside gauntlet, `$00` = not active) |
| `$7E:1FE5–$1FE9` | Runtime-staged `IRON\0` letter-byte string for the pre-fight title |
| `$7E:1FEA` | Cumulative KD count for the current run |
| `$7E:1FEB` | HP stash (sentinel `$FF` = no stash, else carry-over stamina value) |
| `$7E:1D72`/`$1D73` | Iron belt-screen flag (set by CHAMP_SCREEN_STUB before `JSR $BEE8`, cleared after; M=16 read requires both bytes clear) |
| `$7E:1FEE` | Per-run loss counter (cleared on iron entry, incremented on each continue) |

### Hook sites

Bank `$00` unless otherwise noted. Each hook is gated on the iron flag — vanilla circuits take the original code path.

| Hook site | Purpose |
|---|---|
| `$01:B94D` | Descriptor render trampoline — replaces `JSR $D1FC` with `JSL` to a bank-`$00` stub that inlines the renderer and writes the IRON tile row |
| `$01:B9CD` | Confirm hook — JSLs CONFIRM_RESET wrapper; on iron sets flag=1, `$0600=0`, `$0601=$03`; on non-iron writes flag=0 and vanilla `$0601`/`$0600` |
| `$00:B250` (POST_MATCH) | 16-opponent chain driver; iron-complete trigger when `$0600 == $10`; celebration encoding (`$0602 = $0600 EOR $0F`) for fight 16 |
| `$00:B270` (DISPATCH) | Iron-final-fight path: clears iron flag, JMLs to CHAMP_SCREEN (which renders BEST TIME + championship belt + credits) |
| `$00:B231` (B231_INIT) | Clears `$7E:1D72`+`$1D73` after every fight for all circuits |
| `$00:B226` / `$00:B24A` | Stamina-stash hooks — capture `$089F` to `$7E:1FEB` before bonus screen drains it, on both KO and TKO post-match paths |
| `$00:96A5` | Stamina-init override — reads HP stash, applies +16 recovery (cap `$50`), writes to `$089F` at fight start |
| `$00:E9F7` | HP-bar tween fix — pre-fills tile positions 1–9 with empty-bar tile `$38`; sets `$0B14` to carry value so the bar snaps without animating on iron carry-over fights |
| `$00:9C18` | BG2 palette override — MVNs the iron rust palette when iron flag `$7E:1D71` is set OR belt-screen flag `$7E:1D72` is set; original Special purple on vanilla |
| `$00:BF81` | Belt-screen palette override — MVNs rust BG2 + steel-blue belt + sprite palette into the championship screen on iron |
| `$00:C6A6` | KD-increment hook — INCs cumulative `$7E:1FEA`; forces `$089D = 3` (instant TKO) when cumulative reaches 3 |
| `$08:C0D8` | Belt-screen title hook — stages "IRON" letter bytes into low WRAM, points the title renderer at them, centers `+1` col |
| `$08:C09B`, `$08:C0AE`, `$08:C0C7` | Belt-screen TEXT_SKIP hooks — suppress opponent records, TOTAL SCORE label, and TOTAL SCORE numerals on iron |
| `$08:D19D` | Pre-fight title override — substitutes `IRON⋆CIRCUIT` for `SPECIAL⋆CIRCUIT` at the LARGE-FONT renderer |
| `$08:D1C5` | Pre-fight rank renderer — draws `#15..#1` for fights 1–15 (BG1 hash + BG3 small-font digits), CHAMP banner for fight 16 |
| `$08:D2AB` | Pre-fight portrait shift — handles iron+opp2 (Piston Hurricane +4px) and inlines `spo_super_macho_man_fix`'s opp11 portrait shift |
| `$08:D74E`, `$08:D755` | Belt-screen W/L digit override — write "16" instead of "4" in the championship "X Wins Y Loss" line |
| `$01:9EBB` | Continue hook — resets cumulative KD `$7E:1FEA`, sentinel `$7E:1FEB`, INCs loss counter `$7E:1FEE` |
| `$01:9EEC` | Score-tally circuit-name override — substitutes `IRON CIRCUIT TOTAL` for `SPECIAL CIRCUIT TOTAL` on iron |
| `$01:9F72` | Phase-bypass hook — skips the stamina drain/recovery animation phase entirely on iron |
| `$01:A0C7` | Fast-cascade hook — score-tally per-iter delay shrinks from 8 frames to 1 frame on iron |
| `$01:A27E` | Recovery formula override — feeds cumulative KD `$7E:1FEA` to the engine's stamina recovery math |
| `$01:A416` | Aggregate BEST TIME suppression — defeats the gate that would render a SPECIAL CIRCUIT BEST TIME aggregate after every 4th iron fight |
| `$01:A99C` | Stamina-bonus zero — returns `A=0` on iron so stamina-bonus contribution to score is 0 |
| `$01:AAF2` | REST +1 award suppression — freezes `$0606` and the visible REST tile on iron |
| `$01:A2EC`, `$01:A381` | Champion-bonus drain suppression — defeats the `$0600 mod 4 == 3` gate so iron's champion-position fights skip the drain |
| `$01:B0F3` | No-op trampoline inside `CODE_01B0F0` (startup DP-set routine) — replicates the eaten `LDA #$0C; XBA` bytes and returns. `CODE_01B0F0` also fires during gameplay via `CODE_01802D`, so no flag writes are safe here. |
| `$01:B93C`, `$01:BCDB` | Show-special hooks — force the SPECIAL CIRCUIT slot to render on Championship Mode and Time Attack circuit-select even when not unlocked |
| `$01:B959`, `$01:BD29` | Iron W/L draw trampolines — call DRAW_STUB after the vanilla circuit-select renderer to overlay `16 WIN N LOSS` on iron-completed slots |
| `$01:B7D6` | Slot-kill hook — also zeros iron W/L bytes at `$700FE8 + slot` and `$701FE8 + slot` on per-profile FILE KILL |
| `$00:B202` / `$00:B216` | Exit-iron-flag-clear hooks — fire on game-over and retire paths; clear `$7E:1D71` and zero BG2 palette WRAM `$7E:0440–$045F` |

### Stub layout

| Stub | Location | Purpose |
|---|---|---|
| `$00:F61A` | bank `$00` | Inlined `$D1FC` body + IRON tile-row writer |
| `$00:F702` | bank `$00` | CONFIRM stub — CMP #$04: iron sets flag=1, `$0600=0`, `$0601=$03`; non-iron writes vanilla `$0601`/`$0600` |
| `$00:F724` | bank `$00` | POST_MATCH stub — 16-opp chain driver, celebration encoding, iron-complete trigger |
| `$00:F747` | bank `$00` | DISPATCH stub — iron-final-fight credits path |
| `$00:F75A` | bank `$00` | BG2 palette swap (gated on `$7E:1D71` OR `$7E:1D72`) |
| `$00:F781` | bank `$00` | 16-color iron rust palette (BGR15 LE) |
| `$00:F7A1` | bank `$00` | Pre-fight title stub |
| `$00:F7D6` | bank `$00` | Iron rank renderer |
| `$00:F8B9` | bank `$00` | Portrait shift (iron+opp2 and SMM) |
| `$00:F8E0` | bank `$00` | Cumulative KD + force-KO on 3rd cumulative |
| `$00:F903` | bank `$00` | CONFIRM_RESET wrapper — clears cumulative KD / HP stash / loss counter on iron entry |
| `$00:F917` | bank `$00` | Stamina init override (carry-over restore + +16 recovery) |
| `$00:F948` | bank `$00` | Stamina stash (shared by KO and TKO post-match paths) |
| `$00:F959` | bank `$00` | HP-bar tween fix (carry-over fights) |
| `$00:F9B6` | bank `$00` | CHAMP_SCREEN — belt-screen flag, BEST TIME + belt screen calls, SAVE_STUB, credits |
| `$00:F9E1` | bank `$00` | CHAMP_PAL — iron belt-screen palette MVNs |
| `$00:FA53` | bank `$00` | B231_INIT — clears `$7E:1D72`+`$1D73` every post-fight |
| `$00:FA61` | bank `$00` | CHAMP_TITLE — `SPECIAL` → `IRON` in belt-screen title |
| `$00:FA96` | bank `$00` | TEXT_SKIP — suppresses opponent records on iron belt screen (3 call sites) |
| `$00:FAA5` | bank `$00` | W/L digit override — writes "16" instead of "4" |
| `$00:FAF5` | bank `$00` | SAVE_STUB — writes iron W/L to SRAM at iron-complete |
| `$00:FB2A` | bank `$00` | DRAW_STUB — renders `16 WIN N LOSS` on Circuit Select |
| `$00:FCDA` | bank `$00` | EXIT_FLAG_CLEAR (B202 / game-over) — clears `$7E:1D71` + zeros BG2 palette WRAM |
| `$00:FCFD` | bank `$00` | EXIT_FLAG_CLEAR (B216 / retire) — same cleanup |
| `$01:F784` | bank `$01` | REST_NO_GROW |
| `$01:F7A5` | bank `$01` | DRAIN_SKIP |
| `$01:F7B2` | bank `$01` | TALLY_NAME |
| `$01:F7D0` | bank `$01` | RECOVERY_OVERRIDE |
| `$01:F7E0` | bank `$01` | CONTINUE_RESET |
| `$01:FED4` | bank `$01` | PHASE_BYPASS |
| `$01:FEF5` | bank `$01` | BONUS_ZERO |
| `$01:FF02` | bank `$01` | FAST_CASCADE |
| `$01:FF20` | bank `$01` | Iron W/L draw trampolines (2 × 8 B) |
| `$01:FF30` | bank `$01` | SLOT_KILL |
| `$01:FF4B` | bank `$01` | STARTUP_TRAMPOLINE — replicates eaten `LDA #$0C; XBA` from `$01:B0F3` hook, returns immediately (RTS). No flag writes — safe to call mid-gameplay. |
| `$0D:FA69` | bank `$0D` | IRON tally descriptor |

## SRAM persistence

Iron W/L data is stored at `$700FE8 + slot` (primary) and `$701FE8 + slot` (backup), 1 byte per slot, 8 slots. These addresses sit past the engine's per-slot record table and outside the engine's checksum sweep.

Encoding (offset-by-1, `$00` = never completed):

| Encoded value | Meaning |
|---|---|
| `$00` | Never completed |
| `$01` | 16-0 (perfect) |
| `$02` | 16-1 |
| `$03` | 16-2 |

Only runs with 2 or fewer losses are saved. The W/L line renders only when the encoded byte is non-zero.

- **ALL CLEAR** — zeros all SRAM including iron's bytes.
- **FILE KILL (per-profile delete)** — extended by a hook at `$01:B7D6` to also zero `$700FE8 + slot` and `$701FE8 + slot`.

## Compatibility

- **Apply on top of**: original `Super Punch-Out!! (USA).sfc` ROM (MD5 `97fe7d7d2a1017f8480e60a365a373f0`).
- **Conflicts with**: one address overlap at file `0x0452AB` (`$08:D2AB`) with `spo_super_macho_man_fix.ips` — iron's stub handles both Piston Hurricane and Super Macho Man portrait shifts, so both patches work regardless of apply order.
- **Cheat-code compatibility**: all known Action Replay / Game Genie codes for the original ROM remain unaffected.

## See also

- [TECHNICAL.md](../TECHNICAL.md) — full reverse-engineering notes, stub bodies at byte level, free-space inventory, and the Mode Select / Championship Mode state machine architecture.
- [VERSUS_HACK.md](VERSUS_HACK.md) — the core hack iron builds on indirectly.
