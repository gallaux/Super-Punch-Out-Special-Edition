# `spo_versus_hack.ips` — Summary

The core hack of this repo. Adds VERSUS MODE to the Mode Select menu and lets either controller pick on the opponent-select screen.

<img width="256" height="224" alt="Super Punch-Out!! (USA) Versus Hack_001" src="https://github.com/user-attachments/assets/11d6251a-c56d-46ea-a4e4-e26b297e24a0" />
<img width="256" height="224" alt="Super Punch-Out!! (USA) Versus Hack_002" src="https://github.com/user-attachments/assets/195a7883-e233-4066-ad3d-49f829872569" />

## What it adds

- **VERSUS MODE on Mode Select** — 2-player matches launch directly from the menu, no secret button combo required.
- **Player 2 controls the opponent** in Versus matches — the same mechanic as the 2022-discovered secret mode, wired in permanently on the VERSUS path.
- **Correct in-game screen labels** — opponent-select shows "VERSUS MODE" / "< PLAYER 2 SELECT >" when entering from Versus; Time Attack is unchanged.
- **Either controller can pick on opponent-select** — Controller 2's D-pad / A / Start mirror Controller 1 on the Versus opponent-select screen only, so P2 can choose their own fighter.
- **All four circuits always available on the Versus opponent-select screen** regardless of Championship save progress; Time Attack remains progress-gated.

## Design

VERSUS mode is implemented as a routing wrapper around the existing Time Attack code path. A new 1-byte WRAM flag at `$7E:1D74` distinguishes "VERSUS session" from "real TA":

- The VERSUS handler at `$01:FFC9` sets `$7E:1D74 = 1`, then enters the vanilla TA dispatch at `$01:C926`. The fight engine therefore runs unmodified TA code, with vanilla `$0607 = $01` as the in-engine mode flag.
- A handful of hooks (header swap, table-hide, P2-mirrors-P1 input merge, P2-control dispatch, circuit-count override) gate on `$7E:1D74 == 1` to apply VERSUS-only behavior on top of the shared TA path.
- The back-out clear stub at `$01:8463` zeros `$7E:1D74` when the player backs out of opponent-select. Match end intentionally **does not** clear the flag — successive matches stay on the VERSUS path until the player backs out, so rematches don't have to be re-selected.

This means Time Attack runs byte-for-byte vanilla at runtime — no shared mode state, no `$0607=$03` repurposing, no risk of TA-side regressions. The original game's secret 2-player mode (reachable only via a hidden pre-main-menu path, then holding L+SELECT on the secret menu's pre-fight screen) is also unaffected: the dispatch stub at `$0D:FB99` reproduces the original `$0607=$02` + button-combo check verbatim, so the hidden mode triggers exactly when it did in vanilla.

## Free space consumed

Bank `$0D` stubs (all inside the disassembly's `%InsertGarbageData($0DFA69, ...)` zone):

| SNES | Size | Role |
|---|---|---|
| `$0D:FA86–$0D:FAC2` | 61 B | New 5-item Mode Select layout sub-table |
| `$0D:FAC3–$0D:FAC9` | 7 B | "VERSUS" tile data |
| `$0D:FACA–$0D:FAFA` | 49 B | 12-record VERSUS opponent-select descriptor |
| `$0D:FB03–$0D:FB0B` | 9 B | "PLAYER 2" tile data |
| `$0D:FB62–$0D:FB98` | 55 B | Opponent-select init blanking stub |
| `$0D:FB99–$0D:FBC8` | 48 B | P2 control dispatch stub |
| `$0D:FBC9–$0D:FBDD` | 21 B | Header swap stub |
| `$0D:FC4C–$0D:FD24` | 217 B | P2-mirrors-P1 merge + poll stub |
| `$0D:FD99–$0D:FD9F` | 7 B | Back-out clear stub |

Bank `$00` stub (inside `UNK_00F5D0`):

| SNES | Size | Role |
|---|---|---|
| `$00:FDD0–$00:FE17` | 72 B | Opponent-select char-switch blanking stub |

Bank `$01` is touched only in pre-existing free regions:

| SNES | Size | Role |
|---|---|---|
| `$01:8018–$01:801B` | 4 B | Header thunk (`JML` into the bank-`$0D` header stub); lives in the 18-byte dead-loop zone at `$01:8018–$01:8029` |
| `$01:8457–$01:8462` | 12 B | Trampoline 1 (TA-disable progress gate) |
| `$01:8463–$01:8469` | 7 B | Back-out clear stub (`JSL` to bank-`$0D` clear stub + `JMP $C766`) |
| `$01:FFB0–$01:FFE0` | 49 B | 5-item Mode Select dispatch stub + TA/RV trampolines + VERSUS handler + trampoline 2 |

All other edits are in-place 1- to 6-byte modifications to existing routines (item count, highlight base, OAM cursor Y base, disable-flag init, JSR/JMP redirects, etc.).

## Patch in asm form

For reference, the full patch expressed as an asm overlay. Records are grouped by bank and listed in file-offset order, matching the breakdown in [doc/TECHNICAL.md § 5](../TECHNICAL.md#5-versus-hack--patch-by-patch-breakdown).

```asm
;==============================================================================
; spo_versus_hack — full overlay
;------------------------------------------------------------------------------
; Adds VERSUS MODE to the Mode Select menu and lets either controller pick on
; the opponent-select screen. Gated on a new 1-byte WRAM flag at $7E:1D74.
;==============================================================================

;------------------------------------------------------------------------------
; Bank $01 — hooks, thunks, and bank-$01 free-zone stubs
;------------------------------------------------------------------------------

; [1] $01:8018 — Header swap thunk (4 bytes)
;     Lives in the dead-loop jump-table slots at $8018/$801B/$801E.
;     Tail-JMLs into the bank-$0D header stub.
org $018018
    JML $0DFBC9                ; → bank-$0D header swap stub (record [19])

; [2] $01:80CA — P2 control hook (12 bytes)
;     Replaces the original 12-byte CMP $0607; ... BPL $806F sequence.
;     The stub returns A=0 if the P2-control flag should be set (and sets
;     $30/$3D itself), A!=0 otherwise.
org $0180CA
    JSL $0DFB99                ; → P2 control dispatch stub (record [15])
    BNE +
    JMP $80DE                  ; flag was set: continue normally
+   JMP $806F                  ; not set: skip

; [3] $01:8457 — Trampoline 1: conditional TA disable (12 bytes)
;     Disables TIME ATTACK only when no Championship progress.
;     Called via JSR from $01:BBE2 (record [8]).
org $018457
    BNE +          ; if $700010,X != 0 (progress): skip to RTS
    INC $22        ; no progress: disable TIME ATTACK
+   RTS
    NOP : NOP : NOP : NOP : NOP : NOP : NOP   ; padding

; [4] $01:8463 — Back-out clear stub (7 bytes)
;     Reached via the redirect at $01:BEEF (record [10]) when the player
;     backs out of opponent-select. Clears $7E:1D74 and tail-jumps to the
;     original epilog.
org $018463
    JSL $0DFD99                ; → bank-$0D clear stub (record [20], zeroes $7E:1D74)
    JMP $C766

; [5] $01:BB93 — Item count: 4 → 5
org $01BB93 : db $04

; [6] $01:BB99 — Highlight base $024C → $014C (row 9 → row 5)
org $01BB99 : db $01

; [7] Disable flag init (4 in-place bytes across $01:BBA3, $01:BBA7, $01:BBB3-BBB4)
;     Net effect: VERSUS always enabled, TIME ATTACK gated on progress,
;     RECORDS VIEW gated on progress, BUTTON SETTINGS always enabled.

; [8] $01:BBE2 — Progress gate rewrite (17 bytes)
org $01BBE2
    JSR $8457                  ; trampoline 1 (record [3])
    NOP
    STZ $24                    ; BUTTON SETTINGS always enabled
    LDA $700010,X
    BEQ +
    STZ $23                    ; RECORDS VIEW: enabled with progress
+   NOP : NOP : NOP

; [8b] Decoration tilemap + arrow positions for 5-item layout
org $01BBC7 : dw $5854
org $01BBD0 : dw $0050
org $01BBD3 : dw $006E

; [9] $01:BC1D — OAM cursor Y base $47 → $27
org $01BC1D : db $27

;------------------------------------------------------------------------------
; [10] In-place hook redirects (operand-only writes)
;------------------------------------------------------------------------------

org $01BCAA+1 : dw $FFD3       ; JSR $D641 → JSR $FFD3 (circuit count → trampoline 2)
org $01BD0F+1 : dw $8018       ; JSR $D1FC → JSR $8018 (renderer → header thunk)
org $01BE7A+1 : dl $0DFB62     ; JSL $0E:F3DD → JSL $0D:FB62 (init table-hide hook)
org $01BEC8 : db $22 : dl $00FDD0 : db $EA, $EA  ; char-switch table-hide hook
org $01BECE : db $22 : dl $0DFC4C : db $EA       ; P2-mirrors hook
org $01BEEF+1 : dw $8463       ; JMP $C766 → JMP $8463 (back-out → clear stub)
org $01C90E : JMP $FFB0        ; Mode Select confirm → 5-item dispatch stub

;------------------------------------------------------------------------------
; [11] $01:FFB0 — 5-item Mode Select dispatch stub (19 bytes)
;------------------------------------------------------------------------------
org $01FFB0
    CMP #$01
    BEQ versus_handler         ; → $FFC9 (record [12])
    CMP #$02
    BEQ ta_trampoline          ; → $FFC3 (record [12a])
    CMP #$03
    BEQ rv_trampoline          ; → $FFC6 (record [12a])
    LDA #$06                   ; BUTTON SETTINGS fall-through
    STA $03
    JMP $C951

; [12a] $01:FFC3 — TIME ATTACK + RECORDS VIEW trampolines
ta_trampoline:
    JMP $C926

rv_trampoline:
    JMP $C930

; [12] $01:FFC9 — VERSUS handler
versus_handler:
    LDA #$01
    STA.l $7E:1D74             ; raise VERSUS flag
    JMP $C926                  ; enter vanilla TA dispatch
    NOP                        ; padding so trampoline 2 stays aligned at $FFD3

; [12c] $01:FFD3 — Trampoline 2: conditional circuit count (14 bytes)
    LDA.l $7E:1D74
    CMP #$01
    BEQ +                      ; if VERSUS: force 4 circuits
    JMP $D641                  ; else: tail-call SRAM circuit-count reader
+   LDA #$04
    RTS

;------------------------------------------------------------------------------
; Bank $0D — text data, descriptors, and stubs (all inside %InsertGarbageData)
;------------------------------------------------------------------------------

; [13] DA332 + DA3DA pointer redirects
org $0DA38C : dw $FB03         ; DA332[$2D] → "PLAYER 2" tile data (record [14c])
org $0DA3A0 : dw $FAC3         ; DA332[$37] → "VERSUS"  tile data (record [14b])
org $0DA3DE : dw $FA86         ; DA3DA entry 2 → new Mode Select layout (record [14a])
org $0DA47E : dw $FACA         ; DA3DA byte-offset $A4 → VERSUS oppsel descriptor (record [14d])

; [14a] $0D:FA86 — New Mode Select layout sub-table (61 bytes)
org $0DFA86
    db $0D,$1C,$4E,$51    ; CHAMPIONSHIP  row 5  col 7
    db $0C,$1C,$6A,$51    ; MODE          row 5  col 21
    db $37,$1C,$54,$52    ; VERSUS        row 9  col 10
    db $0C,$1C,$64,$52    ; MODE          row 9  col 18
    db $0F,$1C,$50,$53    ; TIME          row 13 col 8
    db $12,$1C,$5A,$53    ; ATTACK        row 13 col 13
    db $0C,$1C,$68,$53    ; MODE          row 13 col 20
    db $10,$1C,$4E,$54    ; RECORDS       row 17 col 7
    db $0E,$1C,$5E,$54    ; VIEW          row 17 col 15
    db $0C,$1C,$6A,$54    ; MODE          row 17 col 21
    db $11,$1C,$4C,$55    ; BUTTON        row 21 col 6
    db $13,$1C,$5A,$55    ; SETTING       row 21 col 13
    db $0C,$1C,$6C,$55    ; MODE          row 21 col 22
    db $0C,$20,$54,$58    ; MODE          header row
    db $05,$20,$5C,$58    ; <<SELECT      header row
    db $00                ; terminator

; [14b] $0D:FAC3 — "VERSUS" tile data
org $0DFAC3
    db $06, $1F,$0E,$1B,$1C,$1E,$1C   ; V,E,R,S,U,S

; [14d] $0D:FACA — 12-record VERSUS opponent-select descriptor (49 bytes)
;        Full circuit rows + VERSUS MODE header + < PLAYER 2 SELECT >
org $0DFACA
    db $0A,$1C,$84,$53    ; SPECIAL   row 14 col 2
    db $0B,$1C,$94,$53    ; CIRCUIT   row 14 col 10
    ; ... full set in TECHNICAL.md record [14d]
    db $37,$0C,$94,$50    ; VERSUS    row 2  col 10
    db $0C,$0C,$A2,$50    ; MODE      row 2  col 17
    db $05,$20,$60,$59    ; <<SELECT  row 37 col 16
    db $2D,$20,$50,$59    ; PLAYER 2  row 37 col 8
    db $00                ; terminator

; [14c] $0D:FB03 — "PLAYER 2" tile data
org $0DFB03
    db $08, $19,$15,$0A,$22,$0E,$1B,$EF,$02   ; P,L,A,Y,E,R,space,2

;------------------------------------------------------------------------------
; [16] $0D:FB62 — Init blanking stub (55 bytes)
;      Calls JSL $0E:F3DD (original work), then if $7E:1D74 == 1,
;      blanks a 30-col × 7-row rectangle on BG1 ($5482) and BG3 ($5C82)
;      by writing $0000. Body byte-identical to the original approach
;      except the gate uses LDA.l $7E:1D74 (8B) instead of LDA $0607 (7B);
;      the BNE-over-body offset is unchanged because both branch and target
;      shift by the same +1 byte.
;------------------------------------------------------------------------------
org $0DFB62
    JSL $0EF3DD
    LDA.l $7E:1D74
    CMP #$01
    BNE skip_to_RTL
    PHP
    REP #$30
    ; (row/col blanking loop — see TECHNICAL.md record [16])
    PLP
skip_to_RTL:
    RTL

;------------------------------------------------------------------------------
; [15] $0D:FB99 — P2 control dispatch stub (48 bytes)
;      Called via JSL $0DFB99 from the hook at $01:80CA (record [2]).
;      Returns A=0 if $30/$3D should be set (and sets them itself),
;      A != 0 otherwise. The caller's A=0 branch is JMP $80DE, which
;      lands PAST the original flag-set instructions — so this stub
;      MUST write $30/$3D itself before returning A=0.
;------------------------------------------------------------------------------
org $0DFB99
    LDA.l $7E:1D74
    CMP #$01
    BNE vanilla_path
    ; VERSUS path: set P2-control flags
    LDA #$08 : STA $30
    LDA #$80 : STA $3D
    LDA #$00 : RTL
vanilla_path:
    LDA $0607
    CMP #$02                   ; secret 2-player mode (pre-main-menu path only)?
    BNE not_combo
    LDA $00AB
    AND $00AF
    BPL not_combo              ; combo not held
    LDA #$08 : STA $30
    LDA #$80 : STA $3D
    LDA #$00 : RTL
not_combo:
    LDA #$01 : RTL

;------------------------------------------------------------------------------
; [19] $0D:FBC9 — Header swap stub (21 bytes)
;      Called via JML from the thunk at $01:8018 (record [1]).
;      On entry: A = caller's descriptor index ($0C or $0E).
;      On exit (via JML to $01:D1FC): A = $A4 if VERSUS, else caller's A.
;------------------------------------------------------------------------------
org $0DFBC9
    PHA                        ; save caller's A
    LDA.l $7E:1D74
    CMP #$01
    BEQ versus_branch
    PLA                        ; non-VERSUS: restore A
    JML $01D1FC                ; tail-call renderer
versus_branch:
    PLA                        ; balance stack
    LDA #$A4                   ; override descriptor index
    JML $01D1FC

;------------------------------------------------------------------------------
; [18] $0D:FC4C — P2-mirrors-P1 merge + poll stub (217 bytes)
;      Gates on $7E:1D74 == 1. Edge-detects P2's newly-pressed buttons via
;      held XOR prev-held AND held (using $00A6/$00A7 as shadow). Merges
;      P2's A / Start / D-pad into P1's pressed-this-frame globals
;      ($0095 / $00A1 / $0092-$0093). Then PEA + JMP into a 122-byte
;      verbatim copy of $01:D8F7's body so its RTS lands inside the stub.
;      Re-issues the displaced CMP #$09 before RTL.
;      Internal refs: PEA pushes $FD21 (post_poll-1); JMP targets $FCA7
;      (D8F7-clone entry).
;------------------------------------------------------------------------------
org $0DFC4C
    ; (full body in TECHNICAL.md record [18])

;------------------------------------------------------------------------------
; [20] $0D:FD99 — Back-out clear stub (7 bytes)
;      Zeroes $7E:1D74. Called via JSL from the back-out clear stub at
;      $01:8463 (record [4]).
;------------------------------------------------------------------------------
org $0DFD99
    LDA #$00
    STA.l $7E:1D74
    RTL

;------------------------------------------------------------------------------
; Bank $00 — char-switch table-hide stub (lives in UNK_00F5D0 zone)
;------------------------------------------------------------------------------

;------------------------------------------------------------------------------
; [17] $00:FDD0 — Char-switch blanking stub (72 bytes)
;      Inlines CODE_01D7BC's body (DMA list setup at $0387 — needed every
;      char-switch in both modes), then conditionally blanks BG3 only when
;      $7E:1D74 == 1. Long-absolute LDA of $01:D7D2 reads the bank-$01
;      lookup table without needing a bank-$01 trampoline.
;      Lives in bank $00 (not $0D) because no single bank-$0D free run is
;      large enough alongside the 217B P2-mirrors stub.
;------------------------------------------------------------------------------
org $00FDD0
    ; (full body in TECHNICAL.md record [17])
```

The `; (full body in TECHNICAL.md record [N])` placeholders cover the three large stubs (records [16], [17], [18]) where the byte-level body is already fully enumerated in TECHNICAL.md and would just duplicate it here.

## Compatibility

- **Apply on top of**: original `Super Punch-Out!! (USA).sfc` ROM (MD5 `97fe7d7d2a1017f8480e60a365a373f0`)
- **Bundled into**: `spo_special_edition_v2.0.ips`
- **Byte-disjoint** with every other standalone patch in this repository — no overlaps, no required apply order.
- **Cheat-code compatibility**: unaffected

## Building

Built by [`scripts/build_spo_versus_hack.py`](../../scripts/build_spo_versus_hack.py):

```
python scripts/build_spo_versus_hack.py <vanilla.sfc> [out.sfc]
```

The builder applies its record set to a vanilla ROM, stamps the SNES header checksum, and writes `patches/standalone/spo_versus_hack.ips`. Pass an optional output path to also emit the patched `.sfc`.

## See also

For the full reverse-engineering reference — every record, the Mode Select state machine architecture, the VERSUS opponent-select reuse strategy, the P2-mirrors-P1 input merge stub, free-space inventory, and key-address quick reference — see [doc/TECHNICAL.md](../TECHNICAL.md), particularly:

- Section 2: The secret 2-player mode
- Section 3: Title screen state machine
- Section 4: Mode Select architecture
- Section 5: Versus Hack — patch-by-patch breakdown
- Section 7: Free space map
