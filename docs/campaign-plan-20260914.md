# Campaign plan — after the memory comparison (2026-09-14)

What to run next, in order, and why. Each item is its own preregistered campaign
or matched pair on the engram world w0 task (`../labloop-engram`, labels under
`/srv/labloop-private/engram-pilot-w0`, `labeval` ON), 20 candidates per arm,
≈ 4 h and ≈ $11 per Sonnet arm on GPU 0, sequential under `gpu0.lock` as before.
Thresholds and rubric values are fixed in each bundle's `PREREG.md` before launch;
nothing here is a result. Prerequisite for all of it: the 2026-09-14 tooling
(`findings-v2` selector and knob ledger, `selection.initial_drafts`,
`resources.worker_model_by_operator`) merged on main with the suite green, and the
selector replay over the recorded findings arm showing full cross-branch coverage.

Why these, in one paragraph each:

- **The fixed memory is the point.** The first comparison (`memory-comparison-20260913/RESULT.md`)
  showed cards reduce wrong statements about earlier work (.017 vs .047) even with a
  selector that hid 8 of 20 cards and never surfaced a real "strongest other branch".
  The v2 selector keeps the newest and strongest cross-branch cards, reserves two
  slots for them, and adds a 2 kB knob ledger that lists every knob and direction
  already tried. In the legacy arm three workers re-tried cosine decay and regressed
  three times; in the findings arm c0016 repeated c0015 because c0015's card was
  evicted. Under v2 both are one ledger line away.
- **One draft is one roll of the dice.** The 0.811 vs 0.644 final gap tracked which
  arm's draft found order-1 hashing early (c0002 vs c0011), not the memory. Several
  drafts at the start give the selector several starting points and give cards
  something cross-branch to say from job 5 on, at the cost of N − 1 improve slots.
- **Model quality matters most at the draft**, where the approach is chosen. An
  Opus arm tests both that and the usage governor at Opus prices.

## 1. `mem2`: legacy vs findings-v2, second seed, legacy first

| | arm L | arm F |
|---|---|---|
| `[memory]` | `mode = "legacy"` | `mode = "findings-v2"`, `knobs = "out/memory_config.json"` |
| `[selection] seed` | 2 | 2 |
| order | **first** (fixed, to counterbalance the first pair) | second |

Everything else as `engram-mem-*-w0` (Sonnet 5, 40 turns, temperature .3,
crossover .15, `initial_drafts` 1, 20 candidates, `wall_clock` 9h, `gpu_hours_total` 8).
Primary endpoint and rule as the first PREREG (fraction_bad findings ≤ ½ legacy over
≥ 40 rated M+R per arm, blinded fresh rater, pack from `scripts/mem_rating_pack.py`)
with one change fixed now: **the `## Finding` section is rated as prose about
earlier candidates**, not stripped (the first pack's stripping removed 4 of the
findings arm's 5 cross-branch references). Secondary: unacknowledged repeats
(expect the ledger to move this most), coverage (must be full under v2, else the
run is reported as a tooling failure), prompt ratio ≤ 2.2 (ledger adds ~2 kB),
valid candidates per GPU-hour, search progress. Two seeds with opposite orders is
the smallest evidence that turns "feasible" into a claim about the mechanism; a
superiority claim still waits for a third.

## 2. `drafts`: initial_drafts 4 vs 1, findings-v2, Sonnet

Two arms differing only in `selection.initial_drafts` (4 vs 1), seed 3, findings-v2
with the ledger in both, order drawn once. Primary endpoint, fixed before launch:
**best search fitness after 20 settled candidates** is not usable as a claim (one
seed, search split is optimistic), so the preregistered read is the final-split
score of each arm's frozen candidate against the task threshold .50 plus a
descriptive comparison: distinct approaches in the population (drafts + their
descendants), and the fraction of the 16/19 improve slots spent on the best draft's
lineage. Kill criterion for the idea: the 4-draft arm's frozen final is below the
1-draft arm's by more than .05 **and** no draft after the first beat the first on
the search split. Cost: 4 drafts ≈ 3 of 20 slots of exploration.

## 3. `opus`: worker_model claude-opus-5, findings-v2, Sonnet arm as control

Same as arm F of item 1 with `worker_model = "claude-opus-5"`, seed 2, and
`[usage]` calibrated from the Sonnet arm's cost (`window_budget` set so the governor
is exercised; this is the M3 evidence NEXT.md still lacks). Preregistered reads:
final vs .50; sessions deferred by the window and re-dispatched (must be 0 failed);
cost per candidate; fraction_bad from a blinded rating of the Opus arm alone against
the Sonnet arm F of item 1 (same seed, same memory). Kill: Opus arm costs > 3× the
Sonnet arm per candidate without a higher final.

## 4. `mixed`: Opus drafts, Sonnet improves

`[resources.worker_model_by_operator] draft = "claude-opus-5"`, everything else as
item 2's 4-draft arm (seed 3). Compared descriptively against item 2's 4-draft arm
(all-Sonnet) and item 3 (all-Opus): cost per candidate and final score. This is the
cheapest way to buy draft quality if item 2 shows drafts matter.

## Order and cost

1 → 2 → 3 → 4, about 7 Sonnet arms plus 2 Opus arms: ≈ 30 GPU-hours sequential
over a week of evenings, ≈ $80 Sonnet list-price plus the Opus arms. Each pair is
launched by the human by hand as before (`LAUNCH.md` in its bundle), under its own
`--op campaign` watcher, one arm at a time on GPU 0. Bundles:
`../labloop-mem2-20260914/`, `../labloop-drafts-20260914/`,
`../labloop-opus-20260914/`, `../labloop-mixed-20260914/`, each with `PREREG.md`,
`ORDER.json` where the order is drawn, `LAUNCH.md`, `SHA256SUMS`, and the arm
projects beside them cloned from `../labloop-engram` at `c31d39b` with `tools/`
synced from labloop main at the merge commit.
