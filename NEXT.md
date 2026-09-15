# NEXT — status and next work

labloop runs the search loop inspired by AIRA₂ (Meta FAIR, arXiv 2603.26499):
`campaign.toml → lab run → [select parent → worker → evaluate → add to population] →
REPORT.md`, with filesystem bookkeeping, bounded jobs and subscription usage
accounting. The design, the milestones with their kill criteria and the dated
implementation notes are in `docs/aira2-loop-design.md`; this file is only what is
true now and what comes next. Milestone criteria are read from the design doc, never
revised here after the fact.

## Current status — reviewed 2026-09-12

| Milestone | Implemented / tested | Live evidence | Remaining |
|---|---|---|---|
| M0 | Loop and synthetic acceptance implemented | No real OS-isolation proof in the reviewed evidence | Restricted evaluation boundary; fault-injection tests for settlement and final evaluation |
| M1 | Worker contract implemented and tested | MNIST probe: 5 completed, final 0.9875 ≥ 0.985 | Probe demonstrates feasibility, not full-window reliability or superiority over interactive work |
| M2 | Full operators and selection implemented; bounded worker lifecycle live-validated | Frozen matched pair 2026-09-13: search 40/40 completed, final .9464; greedy 40/40 completed, final .9406; lease-matched D = +.0044 at B = 26334 s (one sd, over the .004 band by a hair) | One pair, one order; label separation OFF in both; the 24 h criterion not run |
| M3 | Governor and fake-CLI tests implemented; live rate-limit enforcement by the watcher (2026-09-12, section E2b) | First live deferral 2026-09-14 (mem2-legacy c0008: limit message → deferred, not failed → re-dispatched after 30.5 min; 0 failed); the predictive gate never fired (no `window_budget`) | Predictive gate armed at a calibrated budget in the drafts arms (`window_budget` 20.0, `session_cost` 0.48 from 37 sessions); expected to fire only on an overrun, so unattended validation is still pending |
| M4 | Slots, VRAM checks and fake-GPU tests implemented; second-slot draft rule fixed 2026-09-14 (`e464135`); `max_candidates` guard counts in-flight jobs since 2026-09-15 (two slots overshot the cap by one in D1) | The drafts pair ran on two GPUs 2026-09-14/15: 4.19 and 4.60 settled per GPU-hour vs 4.72 / 5.45 on one GPU — **the M4 kill criterion fired**; `gpu_seconds` is slot-lease time and the growth is in the non-training part of each lease (`docs/drafts-comparison-20260915/RESULT.md` §5); wall clock roughly halved (2.83 h / 2.28 h vs 4.79 h / 3.70 h) | Two-slot dispatch is under the fired rule; the mixed arm used it anyway to match its D4 control (a disclosed exception, `docs/campaign-plan-20260914.md`) and reproduced the pattern (4.19 per lease-hour, 8.23 per wall-hour, non-training lease median 346 s vs 226 / 181 s one-slot; `docs/mixed-comparison-20260915/RESULT.md` §7); the mem3 pair runs on two slots under its own disclosure; the cause (host contention, inferred) is not measured |
| M5 | Phase removal and format 2.0 complete locally | Site renderer completion recorded historically | External deployment not independently audited in this review |
| Finding cards | Implemented and tested (opt-in `[memory]`, format 2.1, section G); prompt-size pilot run 2026-09-12 (`docs/finding-cards-pilot.md`); comparison preregistered 2026-09-13 and run 2026-09-13/14 (`docs/memory-comparison-20260913/`, engram w0, 20 candidates per arm, findings first) | Both arms 20/20 completed; blinded rating 2026-09-14: fraction_bad findings .017 (2/115) vs legacy .047 (9/191), ratio .37 ≤ .50 → **supported** (feasibility, one seed); prompt ratio 1.74 ≤ 2.0; coverage NOT full (8/16 jobs under two cross-branch cards) | Human spot-check (`spot-check.md`); fix the selector's eviction order and cross-branch floor before any second comparison; superiority needs more seeds (`RESULT.md`, `opus-review.md`); second pair (mem2, seed 2, legacy first, findings-v2 selector and knob ledger) run 2026-09-14, mechanical pass clean (coverage 18/19, the miss is the single-draft opening; prompt ratio 1.85 ≤ 2.2), blinded rating with the `## Finding` section kept 2026-09-15: **not_supported** (.095 vs .060, ratio 1.59; `docs/mem2-comparison-20260914/RESULT.md`); the two seeds disagree | Ledger v3 implemented 2026-09-15 (per-knob index, measured line on v3 cards, parents in the job card's population table; `docs/finding-cards-plan.md` §3c) and its replay gate passed 11 of 11 (`docs/mem2-comparison-20260914/ledger-v3-replay.md`); the `mem3` pair (`../labloop-mem3-20260915`, seed 4, two GPUs, Sonnet only, findings first by draw) is scaffolded and waits for the human's launch; human spot-checks of both earlier pairs still open |

| Pi workers | Second harness implemented 2026-09-15 on branch `pi-workers` (`tools/lab-worker-pi`, `tools/pi/lab-worker.js`, `tools/lab_pi.py`, `scripts/llm-server.sh`); acceptance section P (fake pi) and a node test of the extension; preflight records the declared and served context window; the extension clips tool results and continues a run cut at the output limit | Two MNIST probes 2026-09-15 (`docs/pi-probe-20260915.md`): gpt-oss-20b 5/5 completed, final **0.9888** ≥ 0.985, sessions 22–64 s; Qwen3.8-27B 4/5 completed (one `length` stop, debugged), final **0.9937**, sessions 5–13 min. Both clear M1's kill criteria; quality not compared (noise floor) | Merge `pi-workers` after the docs pass; then the M2-style task (headroom) on a local model, and a hosted open model through the same `provider/model` id |

Current no-LLM acceptance: **478 passed, 0 failed** (2026-09-15, branch `pi-workers`: +24 Pi checks in section P and the extension test; before that **413 passed, 0 failed** (2026-09-14 evening, e464135: second-slot draft rule, +3 slot cases; earlier that day 410 with findings-v2, initial_drafts and per-operator models; 2026-09-12: 388 including the
new bounded-lifecycle section H). Focused lifecycle tests: **9 passed** (27.4 s).
Counts in dated entries below describe historical suites, not today's coverage.
Passing synthetic tests does not establish OS isolation, exact crash recovery or live
subscription behavior. Both reviewed live reports disclose label separation OFF.

M2's immutable report exists at `../labloop-m2/REPORT.md`, written
2026-09-10T16:16:02Z. Do not rerun final evaluation or rewrite historical reports to
complete this roadmap.

### Historical greedy stopped — lifecycle finding (2026-09-12)

The parent operator confirmed the graceful stop of `m2-cifar10-greedy` in
`../labloop-m2-greedy`: immutable `REPORT.md` written **2026-09-12T13:28:14Z**, stopped
by `lab campaign stop`, **15 settled (8 completed, 7 invalid, including c0014)**.
Frozen c0008 scored **0.947** against the fixed **0.90**: supported for the task
threshold only, not policy superiority or worker reliability. The report records
**1.72 GPU-h, 1.79 h wall**. Campaign and nested c0011 watchers are DONE; the parent
found no active watches. This implementation session did not edit that project,
its labels, candidates, or report, or re-read its final split.

Diagnosis supplied from the live investigation: six earlier invalid candidates
backgrounded training through Claude `-p` and then ended their turn. `lab-worker`,
not a hook, checked missing predictions and returned **2**. c0007's synchronous
foreground run succeeded. c0011's nested training watcher outlived candidate
settlement and wrote predictions about **eight minutes late**. Consequently the
recorded GPU-hours do not bound that candidate's training lifetime. Keep the invalid
rows and late artifacts as evidence; do not salvage them or read the historical
search/control pair as a matched resource comparison. The seventh invalid candidate
is included in the stopped report, not assumed to have the same cause.

Fix in this repo: disable CLI background/auto-background execution, require bounded
synchronous completion, reject worker detach/nested-watch attempts, and drain owned
CLI/candidate descendants before contract checking or settlement. Linux subreapers
and pidfds cover setsid/double-fork without broad kills; operator watchers are
unchanged. Limits and CLI controls are documented in `docs/campaign-setup.md`.
Synthetic tests do not establish real CLI reliability or comparative superiority.

Fresh smoke **finished** in `../labloop-m2-lifecycle-smoke-20260912` at
2026-09-12T14:09:17Z: baseline + two learned candidates completed, no invalids,
foreground results before session return, all watchers done/0. Post-settlement
snapshots found no surviving training processes or late writes. Observed lifecycle
success is bounded evidence, not exhaustive process tracing or long-run reliability.
Final **0.7723 < 0.90**: task accuracy `not_supported`, separate from lifecycle.

**Strict smoke protocol failed:** the operator specified a five-minute final-run cap
in `SMOKE.md` but configured `[eval].timeout`, which limits scoring only. The final
watcher inherited the 15-minute job cap; actual final execution took 15 seconds.
This is a setup error, not cured by short execution. Preserve the preregistration
and report unchanged. Recorded .06278 GPU-h excludes the final 15-second lease;
including it gives .06694 lease-hours, neither measuring GPU utilization. Usage:
$0.55968 list-price equivalent; CLI 2.1.269, served Sonnet-5, governor detection-only.
See `docs/lifecycle-smoke-20260912.md` for evidence, limitations and summary defects.

The sustained smoke in `../labloop-m2-lifecycle-smoke-long-20260912` is
**interrupted/recovered, not strict PASS**: outer watcher
`20260912T1419-campaign` falsely declared a ten-minute stall and killed the controller
at 14:29:37Z, despite both learned candidates doing ~200s of real foreground training.
The outer log/session CPU does not include detached candidate watchers; controller
progress is written to state files rather than its log. The operator's outer
`--stall-min 10` setting was unsuitable for this topology. Keep the wall cap, but
use no outer idle-stall threshold until it measures campaign progress correctly.

All job watchers ended done/0; c0002 finished after the controller died. The stop
marker was requested at 14:30:03Z, after c0002 was already done. User-authorized
recovery under `20260912T1437-recovery` (30-minute wall cap, stall 0) settled c0002
at 14:37:09Z without new candidates, then ran the first final using existing weights.
REPORT was written at 14:37:29Z; recovery ended done/0 at 14:37:39Z. All three
candidates are settled; c0002 search .8676, final .8644 < .90 (`not_supported`).
Recorded search leases total 600s (.16667h), final 15s, combined .17083 lease-hours;
agent usage $0.560563. Training records retain 200.005s/21489 steps and
200.009s/21831 steps. Frozen hashes and the original killed watcher are preserved;
no late writes or visible training processes were found after recovery. No matched
comparison has launched. Further deviations/limits: `docs/lifecycle-smoke-20260912.md`.

Do not present `lab run --once` as settlement-only recovery: with the stop marker,
it reaps/evaluates c0002 and then starts final before the one-tick exit. Any bounded
resume needs explicit approval for that first final and must retain interruption
history, never turn this campaign into a retroactive smoke pass.

Fresh wall-only confirmation smoke **lifecycle PASS**, with evidence limits, in
`../labloop-m2-lifecycle-smoke-wall-20260912`. Controller ran uninterrupted
14:43:50–14:59:01Z (911s); outer `20260912T1443-campaign` done/0 at14:59:05Z.
Baseline + two learned candidates completed; fresh synchronized training intervals
310.0007s and310.0036s exceed the former ten-minute stall point in total. All job/
final watchers done/0, no recovery or visible orphan/late-write evidence. Frozen
hashes unchanged. Search .091/.8564/.8958; final .8914 < .90 (`not_supported`),
separate from lifecycle. Search leases871s + final15s = .24611 combined lease-hours;
agent usage $0.6514438. Minor summary/provenance defects remain documented in
`docs/lifecycle-smoke-20260912.md`; no full-window/security/comparative claim follows.

### Matched pair settled (2026-09-13)

Both arms of the frozen matched pair (`../labloop-m2-matched-20260912` holds protocol,
order draw and provenance) finished without a circuit trip: search arm 40/40 completed,
final .9464, 9.65 lease-h, 9.73 h wall, REPORT 01:15:50Z; greedy arm 40/40 completed,
final .9406, 7.32 lease-h, 7.40 h wall, REPORT 08:49:37Z. No deferrals, no rate-limit
messages, no cleanup errors, every session served sonnet-5 as main model, frozen bundle
hashes unchanged at both terminal audits (`docs/matched-pair-20260912/`).

Preregistered resource-matched read (`scripts/matched_compare.py`, from finished-watcher
leases): **B = 26334 s**; search best eligible c0024 .9528 (cum 20510 s), greedy best
eligible c0029 .9484 (cum 16830 s); **D = +.0044**, one hair over the prospectively fixed
.004 band, so "search advantage within this exploratory pair". Read it as what it is:
one pair, one order, one search-split sd of a difference is about .0044 at n = 5000, so
D is one standard deviation. Automatic finals (search c0035 .9464, greedy c0029 .9406)
are the frozen candidates' task claims, not the cutoff comparison. Greedy candidates
were cheaper (mean learned lease 634 s vs 891 s), which the lease-matched cutoff
absorbs and the count-based headline numbers do not. The M2 design's own 24 h criterion
was not run; this pair stopped at 40 candidates.

The only differences between arms were `selection.temperature`/`crossover_p` (.3/.15 vs
.01/0), so the greedy arm dispatching `improve` only is by design. Greedy c0025's summary
discloses that its worker read eight sibling summaries outside its contract; the guard
blocks writes to other candidate dirs, not reads, and undisclosed reads are not
detectable from the retained evidence. Both arms ran with label separation OFF (frozen
before the `labeval` setup was finished); `labeval` now works (`sudo -n -u labeval
python3` verified 2026-09-13) and the next campaign uses it.

Next campaign scaffolded: `../labloop-engram` (engram-pilot-w0: frozen Qwen3-0.6B,
Engram-style hashed n-gram memory, 4096 fictional facts from cartridge's generator,
8 candidates, threshold .50, labels under `/srv/labloop-private` as `labeval`, uv venv,
tools from `50e312c`). Its README lists the pre-launch steps: install labels, two
reference runs (full FT, LoRA) into `data/train/reference/RESULTS.md`, trust, check.

After a strict smoke pass, fresh matched search and greedy identities with the **same**
fixed lifecycle tools, data, model, seeds, GPU, budgets, memory and usage policy;
change only selection. Fix common resource cutoff and early-stop handling before
launch. Neither historical run establishes the original 24 h criterion. Comparative
validation and calibrated unattended governor evidence remain **pending**.

### Selection findings from the pair and the `draft_p` change (2026-09-13)

The summary titles of both arms show a third of each arm's compute re-testing ideas a
sibling had already tried (search: label smoothing 6×, flip TTA 7×; greedy: mixup 5×,
"raise the training budget" 5×), because legacy memory shows only the first-parent
lineage. That is what finding cards address, so the legacy-vs-findings comparison is
now the highest-value tooling experiment. Separately, `draft` was dispatched only while
the population was empty, and the improve brief forbids changing approach, so
approach-level exploration was structurally off (one accidental exception: search
c0019 improved the trivial baseline into a ResNet9). `selection.draft_p` (default 0,
drawn before crossover, unit-tested; a config without the key consumes the same random
stream as before) is on main since 2026-09-13; a campaign that wants approach
exploration preregisters it. Not applied to engram-pilot-w0, whose tools are frozen.

`selection.initial_drafts` (default 1: today's stream exactly) and
`[resources.worker_model_by_operator]` (a per-operator model, e.g. Opus for `draft`)
landed 2026-09-14, unit-tested only; neither has run in a live campaign yet.

### Memory comparison settled (2026-09-14)

Both arms of the preregistered legacy-vs-findings comparison
(`docs/memory-comparison-20260913/PREREG.md`, findings first by `ORDER.json`) ran to
their 20-candidate cap on 2026-09-13/14 with no deferral, kill or usage pause;
every session served Sonnet 5; no child inherited weights; the final split was read
once per arm under `labeval`. Preregistered read (`RESULT.md`): a fresh blinded
session rated every statement about prior attempts (pack from
`scripts/mem_rating_pack.py`, decision from `scripts/mem_decide.py`): **findings
fraction_bad .017 (2 of 115 M+R) vs legacy .047 (9 of 191), ratio .37 ≤ .50 →
supported** as a feasibility result on one seed, one world, one order. Secondary:
unacknowledged repeats 3 vs 6 (the Opus review counts 1–2 vs 6 wasted candidates),
prompt cost ratio 1.74 (bound 2.0), 5.41 vs 5.10 valid candidates per GPU-hour,
final .811 vs .644 (not evidence about memory; the drafts differed sharply).

What weakens it: the findings arm's cross-branch coverage was **not full** (8 of 16
eligible jobs saw fewer than two out-of-lineage cards), because the selector fills
parent plus two ancestors first and the byte-cap loop evicts the newest cross-branch
card, so the window froze on old weak candidates and 8 of 20 cards were shown to
nobody; the "strongest outside this lineage" slot only ever picked the baseline. The
preregistered stripping of `## Finding` removed 4 of the findings arm's 5
out-of-lineage references and most of its type-R statements (2 rated vs 40), so the
arms' statement mixes differ and the acknowledgment measure is de-powered against the
cards. Both defects are in `opus-review.md` with ranked fixes; a second comparison
uses fixed tools and a rubric that reads the Finding section as prose about others.
The human spot-check of 10 statements per arm (`spot-check.md`) is still to be done.

### mem2 pair and the two-GPU preparation (2026-09-14, evening)

The second memory pair (`../labloop-mem2-20260914`, seed 2, legacy first) ran on GPU 0:
legacy 20/20 settled, final .699 vs .50 (supported), 4.72 settled per GPU-hour, one live
deferral handled as designed (above, M3); findings arm finished 20:46Z: claim supported, best c0016 final .873 vs .50, 20/20 settled, 5.45 settled candidates per GPU-hour, 3.70 h wall, no deferral (the memory read itself waits for the blinded rating). The blinded
rating (pack with `--keep-finding`) is still to do; nothing about the mechanism is read
until it is. The mechanical pass is done (`docs/mem2-comparison-20260914/`): coverage
18 of 19, the miss being c0004, for which a second out-of-lineage card did not yet exist
(single-draft opening, not the selector); `mem_mechanical.py` must learn to ignore the
deferred session that never ran before the read (done 2026-09-15: such records are
listed apart as "sessions that never ran"; pending reasons: none).

Before the drafts pair, the machine changes, not the question (`docs/campaign-plan-20260914.md`,
"Amended after the mem2 pair"): both drafts arms run on GPU 0 and GPU 1 with two slots
inside one arm, never two arms at once. Two things were found while preparing it and are
worth remembering:

- **A second free slot re-drafted.** With `initial_drafts = 1` and two slots the idle
  slot took the old "nothing evaluated yet, so draft" rule and dispatched a second draft
  while the first ran: a one-draft arm on two GPUs was silently a two-draft arm. Fixed in
  `e464135` (the slot waits until a draft is evaluated; a fresh draft goes out only
  when nothing at all is in flight); cases in `scripts/acceptance_slots.sh`.
- **The two cards differ under a wall-clock cap.** GPU 1 is an RTX PRO 4000 Blackwell and
  the task caps training at 10 minutes, so steps per candidate depend on the card. The
  gate written into the drafts `PREREG.md` (GPU 1 ≥ 85 % of GPU 0's steps in 540 s, same
  code, same seed, both cards at once) read: GPU 1 (RTX PRO 4000 Blackwell) is the faster card, 4115 vs 3228 steps in 540 s (127 %; the one-sided gate passes, its mirror would fail at 78 %; disclosed in the drafts PREREG amendment; evidence in `../labloop-drafts-20260914/gpu-reference/`). GPU is recorded per
  candidate and reported as a covariate.

The all-Opus arm is shelved (reasons in the plan amendment); the mixed arm follows the
drafts pair, on two GPUs, after its own PREREG amendment.

### Drafts pair settled, mem2 read (2026-09-15)

The drafts pair (`../labloop-drafts-20260914`, `docs/drafts-comparison-20260915/RESULT.md`)
ran on both GPUs, D1 then D4 as drawn: D1 21/21 completed, frozen c0016 final **.998**;
D4 20/20 completed, frozen c0017 final **.846**; both **supported** vs .50, no deferral,
the armed `window_budget` gate paused each arm once (2.8 % and 7.8 % of wall), 0 failed.
The kill criterion for `initial_drafts > 1` does not fire (three of D4's four drafts beat
the first). The −.152 gap is descriptive; D1's head start was a rank draw of the baseline
as an improve parent at job 3 (a disguised draft that introduced the canonicalising
approach both arms ended on), so the realised contrast was 3 vs 4 opening approaches.
Coverage under findings-v2 was full in both arms. Leakage checks: every weight file
postdates its code copy, all pairwise distinct; D1 c0003's .99 jump is prompt
canonicalisation from split metadata, verified in its code. Found on the way: the
`max_candidates` overshoot with two slots (fixed, see M4 row), the fired M4 criterion and
its diagnosis (RESULT §5), a session reporting 45 turns against a cap of 40 (the SDK's
`num_turns` counts differently from the cap; confirm before relying on the cap as a
budget), and a user-level Claude Code plugin whose SessionEnd hook needs `node`, absent
from the sanitized launch `PATH` (cosmetic; every session's stderr carries one line).

The mem2 memory read is **not_supported** (`docs/mem2-comparison-20260914/RESULT.md`):
findings fraction_bad .095 (18/190) vs legacy .060 (15/252), ratio 1.59 vs the ≤ .50
rule, blinded fresh Opus rater on the `--keep-finding` pack; a first pass rated without
the type definitions (a pack-builder defect, fixed) gave the same direction (.103 vs
.051). Two seeds now disagree; no pooled claim. The cause is mechanical: the knob ledger
dropped 10 of 18 rows for c0019 (2 KiB bound), carries no list-valued knob (`orders`),
and truncates rows on outcome keys before knob keys, so workers wrote "never varied"
about knobs that had been varied. Cross-branch acknowledgment did move the cards' way
(12 vs 3 candidates). Next for memory: `findings-v3` ledger (knob keys only, lists
rendered, a per-knob index) behind its own preregistration, then a third seed.

**The mixed arm ran** (`../labloop-mixed-20260914-arm`, Opus drafts, Sonnet improves,
`initial_drafts` 4, seed 3, two GPUs, 09:12–11:38Z, D4 as its control;
`docs/mixed-comparison-20260915/RESULT.md`): **supported** (frozen c0016 final .997 vs
.50), 20/20 completed, every session served the requested model; cost per settled
candidate $0.79 vs D4's $0.69 (the four Opus drafts $1.02 each vs $0.85, short sessions);
drafts .572 / .597 / .696 / .965 vs .587 / .373 / .677 / .710, the one draft above D4's
best being the frozen candidate's ancestor; the kill criterion does not fire on either
half. Coverage full; the v2 ledger dropped 46 rows in 7 jobs (same defect as mem2).
Throughput 4.19 settled per lease-hour / 8.23 per wall-hour (D4 4.60 / 8.76; one-slot
4.72 / 4.17 and 5.45 / 5.41); the M4 read stands. The all-Opus reference is shelved, so
what the split buys of an all-Opus arm is not measurable; no Opus is needed for the next
campaigns. **Decided next (plan §6): knob ledger v3** — knob keys only, list-valued knobs
rendered, a per-knob index that never drops a candidate — checked first by replaying the
mem2 population against the eleven rated "never varied" claims, then a third memory pair
(`mem3`, seed 4, legacy vs findings-v3). The card shape stays (derived from the summary's
`## Finding` section, one narrative); the plan says why and what it costs. Item 5 there is
the future orchestrator experiment (a CPU-hosted model as the selector, replay first).

### Next work, in priority order

1. Harden the evaluation boundary (the documented unrestricted sudo Python rule is
   not worker isolation), settlement recovery and interrupted-final handling. Add
   fault injection; prefer an explicit inconclusive interrupted final over a silent
   second read. Cover direct editing tools as well as Bash guardrails. Scope worker
   reads to the job card's allowed paths (own dir, parents, data, task): the matched
   greedy arm's c0025 read sibling summaries and the guard only blocks writes.
2. ~~Test rate-limit detection against a worker that emits a limit message and keeps
   running; enforce termination rather than relying on CLI exit.~~ Done 2026-09-12:
   `lab-worker` echoes the CLI's stderr under a prefix into the watcher log and every
   worker job carries a kill pattern scoped to that prefix (`session_kill_regex`);
   acceptance E2b kills a fake CLI that retries forever and re-dispatches the job.
   The wording of the real headless CLI is still to be confirmed on the first live
   deferral (docs/campaign-setup.md).
3. ~~Complete the greedy comparison~~ (done 2026-09-13, "Matched pair settled"); the
   calibrated unattended governor evidence is still pending. First live deferral seen
   2026-09-14 (reactive path); the predictive gate is armed in the drafts arms at
   `window_budget` 20.0 and fires only on an overrun. The all-Opus arm that was to
   exercise it at Opus prices is shelved; if a deliberate exercise is wanted, a tight
   budget on a cheap Sonnet arm is the way, accepting the idle time it costs.
4. ~~Implement finding cards as a separate opt-in change~~ (done 2026-09-12), ~~run the
   prompt-size pilot~~ (done 2026-09-12: facts-only cards +26 %, cards at their limits
   +79 % over the legacy job card on M2's 39 jobs; `docs/finding-cards-pilot.md`), ~~then
   fix the preregistration values and compare memory policies without changing
   scheduler/model/budgets~~ (done 2026-09-14: supported on one seed, "Memory
   comparison settled"). ~~Next for memory: fix the selector (eviction order,
   cross-branch floor, the baseline in the strongest-outside slot) and add a
   machine-readable knob ledger per `opus-review.md`~~ (done 2026-09-14 as
   findings-v2; second seed 2026-09-15 **not_supported**, the ledger itself misled
   workers). ~~Next, decided 2026-09-15 (plan §6): ledger v3 (knob keys only, list-valued
   knobs rendered, a per-knob index that never drops old candidates), a replay over
   the mem2 population as the gate~~ (done 2026-09-15 afternoon: v3 implemented, the
   first replay found the three outcome facts absent, a measured line on v3 cards and a
   parents column in every job card's population table closed that, the replay reads
   11 of 11), then the `mem3` pair at seed 4 (scaffolded, launch lines in
   `../labloop-mem3-20260915/LAUNCH.md`). The two-GPU throughput read came with
   the drafts pair (M4 above): the criterion fired on a metric that charges agent
   time as GPU time; a measure that separates the two goes into the next
   preregistration. After the mixed arm: exclude the baseline from the parent pool once
   a non-baseline candidate is evaluated (a new random stream, so a new campaign).

The missing comparative and unattended evidence is **pending**, not a pass, tie or
failed kill criterion. Subscription renewal alone does not validate the governor.
