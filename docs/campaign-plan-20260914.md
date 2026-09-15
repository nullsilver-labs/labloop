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

## Amended after the drafts pair (2026-09-15)

**The drafts pair ran** on two GPUs, D1 then D4 as drawn (`docs/drafts-comparison-20260915/RESULT.md`).
Both arms **supported** against the fixed 0.50 (D1 frozen c0016 final .998, D4 frozen c0017
final .846); the kill criterion for `initial_drafts > 1` does **not** fire (three of D4's
four drafts beat the first on the search split); the −.152 gap is descriptive and, more to
the point, D1 was not a one-approach arm: rank selection drew the baseline as an improve
parent at job 3 and that candidate introduced the canonicalising approach both arms ended on.
Realised opening approaches were 3 vs 4, not 1 vs 4. Coverage under findings-v2 was full in
both arms (the mem2 miss was the single-draft opening, as predicted). Two tooling findings:
with two slots the candidate cap overshot by one in D1 (21 settled; fixed the same day with an
acceptance case), and **the M4 kill criterion fired** (4.19 and 4.60 settled per GPU-hour
against 4.72 / 5.45 on one GPU) because `gpu_seconds` is the sum of slot leases and a lease
holds the worker's whole session; the growth is entirely in the non-training part of the
lease (≈ 90–135 s at the median), most plausibly host contention, not measured.

**What changes in the plan.**

- **The mixed arm runs next, on two GPUs, as a single arm against D4.** D4 is its
  preregistered control and ran on two GPUs, so matching D4 (same cards, same slots, same
  tools contract apart from the overshoot guard) matters more for that comparison than the
  M4 rule's "not again until the cause is understood". This is a deliberate exception to a
  fired rule and is written into the mixed bundle's amendment with the diagnosis it rests
  on; the human can revert to one GPU with a one-line change per file before launch, at the
  price of an unmatched control. The mixed arm adds a reported-only throughput read that
  separates the two (settled per wall-hour, and per-candidate non-training lease seconds
  against D4 and mem2), which is the cheapest next look at the M4 cause.
- **One arm, not a pair, when only one thing changes and the control already exists.**
  The mixed arm was designed that way; the drafts pair shows why a second run buys little:
  at the same seed, with everything else identical, a single rank draw moved the final by
  .15. What turns a descriptive gap into evidence is more seeds of the same pair, not a
  fresh control beside every new arm. The rule for this plan: a new arm that differs from a
  finished arm by one setting is compared against that arm as its control, provided the task,
  labels, evaluator, worker model, tools contract, GPUs and slots are identical and the
  control's `population.json` is unchanged; anything else is a new pair.
- **Baseline out of the parent pool** once any non-baseline candidate is evaluated: a
  scheduler change to make *after* the mixed arm (which must keep D4's selection rule to be
  comparable), preregistered with the next pair that uses it, since it changes the random
  stream.
- **A throughput measure for M4** that does not charge agent time as GPU time (settled per
  wall-hour beside settled per lease-hour, and lease − training seconds per candidate) goes
  into every following preregistration; the fired M4 read stands as written.
- **The mem2 read is `not_supported`** (`docs/mem2-comparison-20260914/RESULT.md`): findings
  fraction_bad .095 vs legacy .060 at seed 2, ratio 1.59 against the ≤ .50 rule; the first
  pair's `supported` stands and the two seeds disagree. Eleven of the findings arm's eighteen
  bad statements are "never varied" claims made against a knob ledger that had dropped the
  relevant rows (2 KiB bound), never carried list-valued knobs, and truncated every row on
  outcome keys before the knob keys. **Before any third memory pair the ledger changes**:
  knob keys only, list knobs rendered, a per-knob index instead of per-candidate diff rows.
  That is a `findings-v3` and its own preregistration; the mixed arm (which uses v2 like its
  control) is not affected, and its report will read its own novelty claims against the
  same defect.
- The Opus arm stays shelved. Item 5 below (a model orchestrator) is recorded, not
  scheduled.

## 5. `orchestrator`: a local model chooses the parent and operator (added 2026-09-15, future)

Not scaffolded, not scheduled; recorded here so the idea and what it needs are not lost.

**What "the chance one" is.** After the opening drafts, every job is drawn by
`choose_job` in `tools/lab_campaign.py`: with probability `crossover_p` a crossover of two
parents, otherwise an improve of one, parents drawn by temperature-scaled rank selection
over search fitness (AIRA₂). It reads nothing but the fitness column and the random
stream; it cannot know that a lineage is exhausted, that two candidates differ by one
knob already covered by the ledger, or that a low-fitness draft carries an idea worth one
more slot. The knob ledger and the cards give that information to the *worker*, after the
parent is already chosen.

**The idea.** A small open model, CPU-hosted so it costs no GPU and no Claude usage, with a
context large enough to hold the whole population, chooses `(operator, parents)` at each
tick from the same evidence the cards hold: every settled candidate's card, the knob
ledger, fitness and exec status, the lineage graph. Never labels, never a final score,
never the search split. Measured 2026-09-15 on D4: the 20 cards plus 20 summaries are
205 kB, ≈ 51 k tokens by the 4-bytes rule, so a 128 k-context model holds a 20-candidate
population whole; at 40 candidates it needs the digest to be cards-only (≈ 90 kB). The
machine has 20 cores and 62 GB; MoE GGUFs already on disk (`/mnt/fast-data/models/ggufs`:
`gemma-4-26B-A4B`, `gpt-oss-20b-mxfp4`) are the natural first candidates for CPU
decoding of a few hundred output tokens per decision. A llama.cpp server is not installed
yet; that is a prerequisite, and its build, model file, quantisation and sampler settings
are recorded in every candidate's `config.json` and in `REPORT.md`.

**Smallest experiment that can kill it, zero GPU: replay.** Before any campaign, replay
the recorded ticks of D4 (`engram-drafts4-w0`) and mem2-findings offline: at each tick,
give the orchestrator the population as it stood at dispatch (the `job.json` snapshots
already store the cards each job saw; the full digest is rebuilt from `finding.json` of
the candidates settled by then) and ask for `(operator, parents)` plus a one-line reason.
Report: parse failures (an answer that is not valid JSON or names a candidate that did not
exist yet), agreement with the chance choice, how often it would have chosen a parent
outside the lineage that chance kept feeding, decision latency on CPU, and a blind read of
the reasons by the operator (sensible / not). Kill criterion for going further: parse
failures above 10 % of ticks, or median latency above 3 minutes (a decision would then
cost a quarter of a candidate's wall clock), or reasons that are wrong about the population
in more than 1 of 10 spot-checked ticks. Nothing about search quality is claimed from a
replay: the counterfactual children are never run.

**Tooling if the replay passes.** `[selection] mode = "model"` with
`[selection.model] endpoint, model, context_tokens, temperature = 0, seed, timeout`;
`choose_job` unchanged for the baseline, the opening drafts, debug retries and deferred
re-dispatches (the orchestrator takes over only where rank selection would draw a parent);
its prompt, raw answer, parse result, latency and a fallback flag stored per decision in
the candidate's `job.json` (`selection` block) and summarised in `REPORT.md` ("selection:
model X, N decisions, M fallbacks"). Any unparsable or invalid answer falls back to rank
selection for that tick and is counted; the random stream is consumed only on fallback.
Variant A (first) only picks; variant B also writes its one-line reason into the job card,
which changes the worker prompt and is a second treatment, so it is preregistered apart.
Fake-endpoint acceptance cases like the fake-CLI ones of M3.

**The campaign, if it comes.** A matched pair on w0: chance (the D4 configuration:
`initial_drafts` 4, findings-v2, seed 3, two GPUs) vs orchestrator, identical except
`[selection] mode`. Preregistered reads as in the drafts bundle (final vs 0.50 per arm,
gap descriptive, one seed) plus: best search fitness after 8 and 20, slots spent on the
frozen candidate's lineage, unacknowledged repeats (the orchestrator sees the ledger, so
it should never re-dispatch a covered knob), fallback count, decision latency as a share of
wall clock, and cost: zero Claude usage for selection against the same worker cost. Kill
criterion: the orchestrator arm's frozen final below chance's by more than .05 and its
best-after-8 not above chance's; or fallbacks above 20 % of decisions. What it cannot
show: that model selection beats chance in general; one seed, one world, and D1 vs D4 have
already shown that a single draft roll moves the final by .15 at the same seed, so a gap
between two single arms is descriptive until more seeds exist.

## 6. `mem3`: knob ledger v3, then a third memory seed (decided 2026-09-15, next after the mixed arm)

Decided with the human after the mem2 read, while the mixed arm was running (launched
2026-09-15 09:12Z, two Opus drafts in flight on both GPUs). What the cards were for is on
record in `docs/finding-cards-plan.md`: a small reliable account of what was tried and
measured, including findings outside the ancestry, so that workers repeat less and see
more of the population. Both pairs moved those secondary measures the cards' way
(unacknowledged repeats 3 / 6 and 1 / 4, named replications 0 / 1 and 4 / 1, candidates
naming an out-of-lineage candidate 1 / 2 and 12 / 3, findings first). What failed at seed 2
is the accuracy endpoint, and the rated errors trace to the ledger, not the cards.

**Kept on purpose.** The card stays derived from the summary's `## Finding` section (one
worker-authored narrative; the duplication on disk is cheap). The prompt carries cards and
the ledger and a pointer to the parent's summary, as now. The side effect is known and
accepted: workers write about the population in card style, short and categorical, so a
gap in the ledger becomes a rated error. v3 fixes the facts behind those claims, not the
style; the rubric stays as in mem2 (`## Finding` rated).

**Ledger v3, the change.** One preregistered change to `tools/lab_findings.py`:
1. knob keys only — outcome keys (`epochs_started`, `examples_seen`, `final_loss`,
   `holdout_*`, `steps`, `wall_seconds`, `trainable_params`, `seed`) never enter a ledger
   row; they live in the card's measured fields;
2. list-valued knobs rendered compactly (`orders [1,2,3]→[1,2]`), not dropped;
3. a **per-knob index** in place of per-candidate diff rows: for every knob key seen in any
   settled candidate's file, the values tried and who tried them
   (`weight_decay: 0.0 (c0001–c0008, c0010–c0013, c0015–c0018) · 0.01 (c0009, c0014)`),
   so the question "has this knob been varied?" is answered in one line per knob, and no
   candidate is ever dropped for age. The 2 KiB bound stays; if the index exceeds it the
   oldest *values* are elided, never whole knobs, and the elision is written into the row.
The card selector, the byte caps and everything else stay as in v2, so the pair isolates
the ledger.

**Replay before any GPU.** Rebuild c0008's and c0019's v3 ledgers from the recorded mem2
findings population (as `scripts/mem_replay_selector.py` does for the selector) and check
that each rated "never varied" claim in `docs/mem2-comparison-20260914/RESULT.md` would
have had its contradicting fact in the worker's context; report the v3 ledger's bytes for
every mem2 job. If any of the eleven facts is still absent, v3 is not ready.

**The pair.** `mem3`: legacy vs findings-v3, seed 4, order drawn once, two GPUs, everything
else as mem2 (Sonnet, 20 candidates, `initial_drafts` 1 so the pair stays comparable with
the first two; coverage's single-draft miss is reported as such). Endpoint, rule and rubric
as mem2's PREREG, with the rubric paragraphs inlined (`mem_rating_pack.py` now does this).
Reported beside it: the three-seed description (supported, not supported, and this one),
never pooled. Expectation written down now: not a win. The base rates are low and one seed
moved the ratio from .37 to 1.59; a third seed can land anywhere. If v3 is not supported
again, the cards are kept for what they demonstrably do (acknowledgment, named
replications) and the accuracy claim is dropped for this task.

Order now: mixed arm (running) → replay → `mem3` pair → then the baseline-out-of-the-pool
scheduler change and item 5 as before.

## Amended after the mixed arm (2026-09-15, afternoon)

**The mixed arm ran** (`../labloop-mixed-20260914-arm`, 09:12–11:38Z, two GPUs, D4 as its
control; `docs/mixed-comparison-20260915/RESULT.md`). Read 1: **supported**, frozen c0016
final .997 vs .50, 20/20 completed, every session served the model requested for its
operator (4 Opus drafts, 15 Sonnet). Read 2: **$0.79 vs $0.69 per settled candidate**
(ratio 1.14); the four Opus drafts cost $1.02 each against D4's Sonnet drafts at $0.85 —
1.2×, not the 5× the governor reserved, because the Opus sessions were short (9–15 turns);
the larger part of the gap is on the Sonnet side and is unexplained. Read 3: final .997 vs
.846, descriptive. Read 4: drafts .572 / .597 / .696 / **.965** vs D4's .587 / .373 / .677 /
.710; the one Opus draft above D4's best (c0004, hashing only tokens inside a known
person-name span) is the ancestor of the frozen candidate and took 11 of 15 later slots. No
disguised draft in either arm. **The kill criterion does not fire on either half.** Coverage
full; the v2 knob ledger dropped 46 rows in 7 of 20 jobs (D4: 33 in 6), the same defect the
mem2 read found. Leakage checks clean. Throughput: 4.19 settled per lease-hour (D4 4.60,
one-slot arms 4.72 / 5.45) and 8.23 per wall-hour (D4 8.76, one-slot 4.17 / 5.41); the
non-training part of the lease is again where the extra time sits (median 346 s vs 300 s
two-slot, 226 / 181 s one-slot), with one confound of this arm's own (its workers trained
540 s where D4's trained 480 s). The M4 read stands as written; the cause is still not
measured. Governor: no pause, peak 34 % of $48.

**What follows.** The idea is not killed and not shown to pay; the all-Opus reference that
would bracket it is shelved, so the question "how much of an all-Opus arm does the split
buy" is not measurable from what exists and is not pursued now. The per-operator model
knob stays available; the next campaigns need no Opus (the `mem3` pair is Sonnet-only by
design). The plan's order is unchanged: replay gate → `mem3` pair → the baseline-out-of-
the-pool scheduler change → item 5.

**Ledger v3 and the replay gate (same afternoon).** `findings-v3` is implemented
(`docs/finding-cards-plan.md` §3c, acceptance cases in `scripts/acceptance_findings.sh`):
knob keys only, list knobs rendered, a per-knob index that never drops a candidate, oldest
values elided under the 2 KiB bound with the elision written into the row. The first replay
over the mem2 findings arm found the 8 knob-novelty facts present and the other three of the
eleven absent — two parameter counts and one search-delta superlative, which are outcomes
and which §6 had assumed "live in the card's measured fields" while the rendered card never
printed them. Two additions closed that, both outside the index and both disclosed in the
mem3 preregistration: a v3 card renders a measured line from its own knobs file, and the
job card's population table lists parents beside scores for every policy (so both arms of
a pair get it). The replay then reads **11 of 11 present**
(`docs/mem2-comparison-20260914/ledger-v3-replay.md`; v3 index 0–1664 B per job, no
elision, all 18 earlier candidates named in the last job against v2's 8): **the gate
passes as written.** The `mem3` pair is scaffolded (`../labloop-mem3-20260915`, arms
`../labloop-mem3-{findings,legacy}-20260915`, seed 4, two GPUs, Sonnet only, order drawn:
findings first) and waits for the human's launch.
