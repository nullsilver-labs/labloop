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

## Scaffolded (2026-09-14)

All four bundles exist; **nothing has been launched**. Each arm is a clone of
`../labloop-engram` at `c31d39b` with `tools/`, `.claude/`, `templates/`, `CLAUDE.md` and
`.lab-redact` synced from labloop `7af836c`, and a `.venv` symlink to labloop-engram's
venv. Bundle dirs hold `PREREG.md`, `LAUNCH.md`, `SHA256SUMS` and, where applicable,
`ORDER.json`; the shared GPU lock is `/mnt/data/projects/nullsilver/gpu0.lock` (created,
empty) and every launch line holds it.

| bundle | arm dir | campaign id | arm commit | `campaign check` | ORDER draw |
|---|---|---|---|---|---|
| `../labloop-mem2-20260914` | `../labloop-mem2-legacy-20260914` | `engram-mem2-legacy-w0` | `7365686` | pass (no-`window_budget` warning) | no draw — legacy first, fixed |
| `../labloop-mem2-20260914` | `../labloop-mem2-findings-20260914` | `engram-mem2-findings-w0` | `c3154b9` | pass (no-`window_budget` warning) | second |
| `../labloop-drafts-20260914` | `../labloop-drafts-1-20260914` | `engram-drafts1-w0` | `35a303e` (was `4c80456`; two GPUs, armed governor, tools `e464135`) | pass, **no warnings** | `secrets.randbits(1)` = **0** at 2026-09-14T11:39:02Z → first |
| `../labloop-drafts-20260914` | `../labloop-drafts-4-20260914` | `engram-drafts4-w0` | `666e3c9` (was `ecd2147`; same) | pass, **no warnings** | second |
| `../labloop-opus-20260914` | `../labloop-opus-20260914-arm` | `engram-opus-w0` | `0c1dd93` | pass, **no warnings** | none (single arm) |
| `../labloop-mixed-20260914` | `../labloop-mixed-20260914-arm` | `engram-mixed-w0` | `ce9fa4c` | pass, **no warnings** | none (single arm) |

Two settings were chosen here where §3 and §4 gave only an intent, and both are written
into the bundles' `PREREG.md`:

- **Usage calibration (opus and mixed).** `session_cost = 2.55` (5 × the Sonnet median of
  $0.51, list-price equivalent), `window_budget = 48.0`, `soft = 0.70`, `hard = 0.90`.
  The soft gate is $33.60, so `floor(33.60 / 2.55) = 13` sessions fit in a rolling 5 h
  window and the remaining 8 of the 21 are deferred and re-dispatched. The mixed arm
  keeps the same numbers on purpose (only 4 of its sessions are Opus, so the flat
  reservation over-reserves and it will rarely gate; that is reported, not tuned).
- **`[stop].wall_clock` 9h → 12h and watcher budget 600 → 720 min** for the opus and
  mixed arms only, so a job deferred by the window waits for the window to roll instead
  of expiring the campaign.

### Prerequisites before launch (also at the end of each `PREREG.md`)

1. **`scripts/mem_rating_pack.py --keep-finding`** — landed in `fd6a298` (2026-09-14). The
   `mem2` rubric rates the `## Finding` section as prose about earlier candidates instead
   of stripping it (the 2026-09-13 pack's stripping removed 4 of the findings arm's 5
   cross-branch references); build the pack with the flag. The Opus bundle's accuracy
   read uses it too.
2. Each arm dir trusted in Claude Code once (open `claude` there, accept).
3. `claude auth status` says loggedIn.
4. GPU 0 idle (`nvidia-smi`).
5. No running watchers in any sibling project (`tools/lab watch list` in each).
6. `LAB_PRIVATE=/srv/labloop-private tools/lab campaign check` passing in the arm.
7. `/mnt/data/projects/nullsilver/gpu0.lock` in place, held by every launch line.
8. For the opus arm only: check `/usage` in an interactive session first, so the
   governor's first read is not of someone else's spending; and run it after `mem2`,
   whose findings arm is its control. The mixed arm runs last, after `drafts` and `opus`.

## Amended after the mem2 pair (2026-09-14, evening)

**mem2 ran.** Legacy arm finished 16:45Z: claim supported, best c0014 final 0.699 vs 0.50,
20/20 settled, 4.72 settled candidates per GPU-hour, one live deferral (c0008: usage-limit
message, deferred not failed, re-dispatched after 30.5 min, 0 failed). Findings arm
followed on the same GPU: finished 20:46Z: claim supported, best c0016 final .873 vs .50, 20/20 settled, 5.45 settled candidates per GPU-hour, 3.70 h wall, no deferral (the memory read itself waits for the blinded rating). The rating pack and the blinded read are
still to do (`PREREG.md` in the bundle; pack with `--keep-finding`).

**The order changes: two GPUs from the drafts pair on, and the Opus arm is shelved.**

- **Why two GPUs now.** GPU 1 (RTX PRO 4000 Blackwell, 24 GB) has been idle through every
  campaign; a candidate is ≈ 9 min of training in ≈ 11.5 min of wall clock, so the arm is
  GPU-bound and two slots should roughly halve it. The tooling already leases per GPU
  (`[resources] gpus = [0, 1]`, `max_parallel_jobs`, `CUDA_VISIBLE_DEVICES` per job, VRAM
  check, no duplicate `(operator, parents)` across free slots). What it did not do right:
  with two slots and `initial_drafts = 1` the idle slot drafted again while the first draft
  ran, which would have turned D1 into a two-draft arm. Fixed in labloop `e464135`
  (the second-slot draft rule; acceptance cases in `scripts/acceptance_slots.sh`).
- **How.** Two slots inside one arm; never two arms at once (no cross-campaign GPU
  arbitration, per-campaign governors blind to each other, one shared usage window). The
  drafts bundle's `PREREG.md` carries the amendment: both arms on both GPUs, GPU recorded
  per candidate and reported as a covariate, the M4 read (settled per GPU-hour vs mem2's
  single-GPU 4.72, M4's kill criterion), `[usage] window_budget = 20.0` armed with
  `session_cost` 0.48 from the 37 mem2 sessions. The hardware confound (two different cards
  under a 10-minute wall-clock training cap) is gated by a reference run of c0014's code on
  both cards at once: GPU 1 is the *faster* card (4115 vs 3228 steps in 540 s, 127 %; concurrency costs the
  3090 ≈ 1 %). The one-sided gate passes; mirrored it would fail at 78 %, and that is
  disclosed in the amendment. Decision: two GPUs, GPU as a recorded covariate. Evidence in
  `../labloop-drafts-20260914/gpu-reference/`.
- **Why the Opus arm is shelved.** Its two purposes were the governor at Opus prices and
  all-Opus quality against cost. The deferral path the M3 evidence needed was exercised
  live in mem2-legacy (reactive path: limit message → deferred → re-dispatched, 0 failed);
  the predictive gate is now armed in the drafts arms at a calibrated budget and will fire
  only on an overrun, which is what it is for. The quality-versus-cost question is the
  most expensive in this plan and the mixed arm answers its cheaper half (Opus at the draft
  only). The Opus bundle stays scaffolded, unlaunched, as data; it is reconsidered only if
  the mixed arm shows draft quality matters.
- **Order now:** drafts (D1 then D4, two GPUs) → mixed (two GPUs; amend its `PREREG.md` the
  same way before launch, including its own `[usage]` numbers) → Opus only if warranted.
- **Not two campaigns at once.** Tempting with two GPUs, and wrong for a matched pair: it
  confounds the arm with the card, and each governor would see half the spend on one
  window. If it is ever done, it needs cross-campaign GPU leasing and a shared usage ledger
  in `tools/lab` first, plus a port per `lab serve`.
