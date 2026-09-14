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
| M3 | Governor and fake-CLI tests implemented; live rate-limit enforcement by the watcher (2026-09-12, section E2b) | M2 had pacing OFF; no observed deferrals | Calibrate budget, then unattended validation |
| M4 | Slots, VRAM checks and fake-GPU tests implemented | Reviewed campaigns used one GPU | Real two-GPU throughput comparison |
| M5 | Phase removal and format 2.0 complete locally | Site renderer completion recorded historically | External deployment not independently audited in this review |
| Finding cards | Implemented and tested (opt-in `[memory]`, format 2.1, section G); prompt-size pilot run 2026-09-12 (`docs/finding-cards-pilot.md`); comparison preregistered 2026-09-13 and run 2026-09-13/14 (`docs/memory-comparison-20260913/`, engram w0, 20 candidates per arm, findings first) | Both arms 20/20 completed; blinded rating 2026-09-14: fraction_bad findings .017 (2/115) vs legacy .047 (9/191), ratio .37 ≤ .50 → **supported** (feasibility, one seed); prompt ratio 1.74 ≤ 2.0; coverage NOT full (8/16 jobs under two cross-branch cards) | Human spot-check (`spot-check.md`); fix the selector's eviction order and cross-branch floor before any second comparison; superiority needs more seeds (`RESULT.md`, `opus-review.md`) |

Current no-LLM acceptance: **388 passed, 0 failed** (2026-09-12, including the
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
   calibrated unattended governor evidence is still pending. A Sonnet-vs-Opus
   `worker_model` pair on the engram task would exercise it: run the Sonnet arm first
   and calibrate `usage.window_budget` from its cost before the Opus arm.
4. ~~Implement finding cards as a separate opt-in change~~ (done 2026-09-12), ~~run the
   prompt-size pilot~~ (done 2026-09-12: facts-only cards +26 %, cards at their limits
   +79 % over the legacy job card on M2's 39 jobs; `docs/finding-cards-pilot.md`), ~~then
   fix the preregistration values and compare memory policies without changing
   scheduler/model/budgets~~ (done 2026-09-14: supported on one seed, "Memory
   comparison settled"). Next for memory: fix the selector (eviction order,
   cross-branch floor, the baseline in the strongest-outside slot) and add a
   machine-readable knob ledger per `opus-review.md`, each behind its own small
   preregistered campaign; then more seeds. Run the real two-GPU comparison separately.

The missing comparative and unattended evidence is **pending**, not a pass, tie or
failed kill criterion. Subscription renewal alone does not validate the governor.
