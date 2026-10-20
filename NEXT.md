# NEXT — status and next work

labloop runs the search loop inspired by AIRA₂ (Meta FAIR, arXiv 2603.26499):
`campaign.toml → lab run → [select parent → worker → evaluate → add to population] →
REPORT.md`, with filesystem bookkeeping, bounded jobs and subscription usage
accounting. The design, the milestones with their kill criteria and the dated
implementation notes are in `docs/aira2-loop-design.md`; this file is only what is
true now and what comes next. Milestone criteria are read from the design doc, never
revised here after the fact.

## Resume here: 2026-10-20

Written by the operator session, 2026-10-20. **Nothing of this session's is running.**
- **A4 is done and read** (hub `../labloop-v2a4-20261020/READ.md`, 5ca01c3). Primary **not supported**: 5 combinations per campaign with complementary pairing against 2 with rank, exact p .17 (2 snapshots, 36 arrangements). The mechanism works: 11 of 11 complementary-arm crossovers had complementary parents against 3 of 18 under rank, and per crossover that is 5/11 combined against 2/18. Final g leaned complementary (.615 against .506, reported only), at equal cost. The upstream limit is draft diversity: only 2 of 8 snapshots held any complementary draft pair. Deviations are in hub `DEVIATION.md`: the arms ran on `b075c97`, and the read script had a `frozen`-status bug, fixed in labbench 6afcc64 (primary unchanged). **Human's call:** make complementary pairing the default when an evaluator prints components, and/or run a confirmatory pass with about 16 snapshots or with breadth knobs.
- **A3 is done:** not supported. The post-hoc points at parent pairing. Complementary pairing is built on main (`ced82d8`, acceptance 666/0).
- **DISPLIB (Opus workers, set up by another session):**
  - `../labloop-displib-20261019` finished with claim **inconclusive**. That session reports an evaluator race, and its private logs put c0005's final at 0.874 against a 0.75 threshold. lab's record is unchanged.
  - `../labloop-displib-v2-20261020` (`restart_after` 4) is **running**.
- Main has local commits, none pushed. Grep for labbench details before any push.

Earlier update (2026-10-19 evening):
Written by the operator session. **Update 2026-10-19 ~21:10Z: A3 is done and read; nothing of A3 is running.** All 16 arms settled by 20:07Z; `../labbench` is 775. The read (`../labloop-v2a3-20261019/READ.md`): **primary not supported**, combination rate 2/31 per-target against 1/32 default, exact p .32. Crossover keeps ~90 % of the parents' union and almost never beats the better parent, with either text. The arms ran labloop branch `a3-tools-20261019`, not 5d5354c (hub `DEVIATION.md`). Post-hoc (in READ.md, hub f2d39b6): only 7/63 crossovers had parents with complementary rules; there, per-target combined 2/4 (full union), default 0/3. So the test was nearly blind, and the binding constraint looks like parent pairing. Cheapest next test: complementary pairing + per-target text. 

**Where things stand.**
- `main` is pushed to GitHub as one squashed commit on top of the September history.
- The full local history is on branch `local-history-20261019`. **Never push that branch:** it names labbench generator details, and the repo is public.
- Acceptance is **643/0** on a quiet machine. Under heavy load from running campaigns, 12 loop-timing cases in section C fail; rerun when quiet.
- Format is 2.2.
- The default cards no longer say "Make ONE hypothesised change" or "Prefer simple and runnable".
- The v2 keys are on main: `restart_after`, `seed_from`/`seed_upto`, `same_output_ignore`, `[worker.operator_text]`. The plan is in `docs/labloop-v2-plan.md`.

**Done: A3, the crossover card test** (hub `../labloop-v2a3-20261019`; its PREREG holds the one primary line).
- **Interrupted.** A power cut at about 11:40Z killed phase 1. The first snapshots, `../labloop-a3src-*`, are left as evidence; their dead watchers were repaired with `tools/lab watch check`.
- **Replacements:** `../labloop-a3src2-i{13,14}{a,b}-20261019`, trusted by the human and launched 16:02Z (baselines .3109 on i13, .2852 on i14). 17:00Z: i13b and i14a REPORTs done; i13a in its final read, i14b on its last draft (c0004).

**Steps to finish A3:**
1. ~~**Human:** `bash ../labloop-v2a3-20261019/trust2.sh`.~~ Done.
2. ~~**Session:** `bash ../labloop-v2a3-20261019/launch12.sh`.~~ Done 16:02Z. It refuses if `../labbench` is mode 000 or another unlock watcher is running. The 4 snapshots (c0000 + 4 drafts each, Haiku) take about 45 minutes; check hourly.
3. ~~Phase 2~~ Done, with deviations (hub `DEVIATION.md`). Phase 1 finished 17:26Z. Seeding refused three times, all in the B2 seed check, never a label problem:
   - bytecode caches naming the snapshot;
   - Haiku scratch scripts hardcoding `<snapshot>/data/train/dev/`;
   - nondeterministic learners re-scoring within ±.007 under the Docker evaluator.
   Fixes on main `4802a9d`, `0386c9e`, `25aa790`, `4859c0c` (local, not pushed), cherry-picked onto local branch `a3-tools-20261019` as `ea68be2`, `073f4fd`, `23b598a`, `ed03c69` (the arms use `073f4fd` and `23b598a`, identical but for the tolerance). Branch acceptance 654/0. **Main's acceptance with these commits has not been run** (only the branch's): run it when the machine is quiet. The branch is checked out in a session-scratchpad worktree; if that dir is gone, `git worktree prune`. The original phase 2 notes follow.
   **When all 4 snapshot REPORTs exist and `../labbench` is 775:**
   - from `../labbench`, run `python3 -m tools.make_a3 phase2 20261019 5d5354c`. It scaffolds the 16 seeded arms at paths already trusted by `trust.sh`, reading `plan.json`, which now points at the `a3src2` snapshots.
   - then run `bash ../labloop-v2a3-20261019/launch2.sh`.
   - Each arm re-scores its 4 seeded drafts at start (B2), so the first tick is slow. The arms take about 1–2 hours and about $4.
4. ~~**Read A3:**~~ Done 21:10Z (READ.md, hub commit e747b8b). Main's acceptance ran 2026-10-20 with the seed-check commits and complementary pairing: 666/0. The original notes:
   - from `../labbench`, run `python3 -m tools.a3_read 20261019 > ../labloop-v2a3-20261019/read.json` as a tracked background task (it re-runs learners in Docker).
   - then write `READ.md` in the hub against the PREREG's one primary line.
   - add a dated entry here; keep labbench generator details out of this public repo.
5. **After A3:** the human chose complementary pairing (2026-10-20). Built on main as `[selection] crossover_pairing = "complementary"` with `components_key` (docs/campaign-setup.md). It needs the evaluator to print per-component scores; hrw's evaluator already prints `per_target`. **A4 is scaffolded, not launched** (hub `../labloop-v2a4-20261020`, PREREG 052a3d3; labbench `tools/make_a4.py`, `tools/a4_read.py`, b6c5994). Fresh hrw instances 15 and 16. Human: `bash ../labloop-v2a4-20261020/trust.sh` (24 dirs), then `bash ../labloop-v2a4-20261020/launch1.sh` (8 snapshots, ~45 min). When all 8 REPORTs exist and ../labbench is 775: from ../labbench `python3 -m tools.make_a4 phase2 20261020 d449625` (gate: the first 4 snapshots with a complementary pair at .2), then `bash ../labloop-v2a4-20261020/launch2.sh`; read with `python3 -m tools.a4_read 20261020 > ../labloop-v2a4-20261020/read.json`. Earlier text: crossover earned no new default text. READ.md lists the options. The first is complementary pairing (lab picks parent B by per-target rules A lacks) with the per-target text; the others are a mechanical per-target combination done by lab, a smaller crossover share, or the same test with a stronger worker. Next steps per `docs/labloop-v2-plan.md` §4. If crossover can be made to combine rules, that is a harness change worth a default. If not, check on a second task family that the card change carries over.

**Habits learned this week:**
- Before pushing main, grep the outgoing diff for labbench generator details. The repo is public; the generators are not.
- `../labbench` is mode 000 while workers run. The launch scripts lock it, and a trap-protected unlock watcher restores it.
- **After a power cut:**
  - `tools/lab watch check` in each affected campaign;
  - `chmod 775 ../labbench` only when no worker is running;
  - a campaign whose first draft died mid-run is better replaced than resumed, because the dead draft costs a debug slot.
- Trust is the human's step (`trust*.sh` scripts in each hub). The agent cannot edit `~/.claude.json`.

**For the human:** delete `/tmp/nullsilver-*`, acceptance leftovers from one `KEEP=1` debug run that the agent may not remove.

## Current status — reviewed 2026-09-12

| Milestone | Implemented / tested | Live evidence | Remaining |
|---|---|---|---|
| M0 | Loop and synthetic acceptance implemented | No real OS-isolation proof in the reviewed evidence | Restricted evaluation boundary; fault-injection tests for settlement and final evaluation |
| M1 | Worker contract implemented and tested | MNIST probe: 5 completed, final 0.9875 ≥ 0.985 | Probe demonstrates feasibility, not full-window reliability or superiority over interactive work |
| M2 | Full operators and selection implemented; bounded worker lifecycle live-validated | Frozen matched pair 2026-09-13: search 40/40 completed, final .9464; greedy 40/40 completed, final .9406; lease-matched D = +.0044 at B = 26334 s (one sd, over the .004 band by a hair) | One pair, one order; label separation OFF in both; the 24 h criterion not run |
| M3 | Governor and fake-CLI tests implemented; live rate-limit enforcement by the watcher (2026-09-12, section E2b) | First live deferral 2026-09-14 (mem2-legacy c0008: limit message → deferred, not failed → re-dispatched after 30.5 min; 0 failed); the predictive gate never fired (no `window_budget`) | Predictive gate armed at a calibrated budget in the drafts arms (`window_budget` 20.0, `session_cost` 0.48 from 37 sessions); expected to fire only on an overrun, so unattended validation is still pending |
| M4 | Slots, VRAM checks and fake-GPU tests implemented; second-slot draft rule fixed 2026-09-14 (`e464135`); `max_candidates` guard counts in-flight jobs since 2026-09-15 (two slots overshot the cap by one in D1) | The drafts pair ran on two GPUs 2026-09-14/15: 4.19 and 4.60 settled per GPU-hour vs 4.72 / 5.45 on one GPU — **the M4 kill criterion fired**; `gpu_seconds` is slot-lease time and the growth is in the non-training part of each lease (`docs/drafts-comparison-20260915/RESULT.md` §5); wall clock roughly halved (2.83 h / 2.28 h vs 4.79 h / 3.70 h) | Two-slot dispatch is under the fired rule; the mixed arm used it anyway to match its D4 control (a disclosed exception, `docs/campaign-plan-20260914.md`) and reproduced the pattern (4.19 per lease-hour, 8.23 per wall-hour, non-training lease median 346 s vs 226 / 181 s one-slot; `docs/mixed-comparison-20260915/RESULT.md` §7); the mem3 pair runs on two slots under its own disclosure; the cause (host contention, inferred) is not measured |
| M5 | Phase removal and format 2.0 complete locally | Site renderer completion recorded historically | External deployment not independently audited in this review |
| Finding cards | Implemented and tested (opt-in `[memory]`, format 2.1, section G); prompt-size pilot run 2026-09-12 (`docs/finding-cards-pilot.md`); comparison preregistered 2026-09-13 and run 2026-09-13/14 (`docs/memory-comparison-20260913/`, engram w0, 20 candidates per arm, findings first) | Both arms 20/20 completed; blinded rating 2026-09-14: fraction_bad findings .017 (2/115) vs legacy .047 (9/191), ratio .37 ≤ .50 → **supported** (feasibility, one seed); prompt ratio 1.74 ≤ 2.0; coverage NOT full (8/16 jobs under two cross-branch cards) | Human spot-check (`spot-check.md`); fix the selector's eviction order and cross-branch floor before any second comparison; superiority needs more seeds (`RESULT.md`, `opus-review.md`); second pair (mem2, seed 2, legacy first, findings-v2 selector and knob ledger) run 2026-09-14, mechanical pass clean (coverage 18/19, the miss is the single-draft opening; prompt ratio 1.85 ≤ 2.2), blinded rating with the `## Finding` section kept 2026-09-15: **not_supported** (.095 vs .060, ratio 1.59; `docs/mem2-comparison-20260914/RESULT.md`); the two seeds disagree | Ledger v3 implemented 2026-09-15 (per-knob index, measured line on v3 cards, parents in the job card's population table; `docs/finding-cards-plan.md` §3c) and its replay gate passed 11 of 11 (`docs/mem2-comparison-20260914/ledger-v3-replay.md`); the `mem3` pair (`../labloop-mem3-20260915`, seed 4, two GPUs, Sonnet only, findings first by draw): findings arm finished 2026-09-15 (20/20 completed, final .750 vs .50, coverage full, **v3 knob index saturated at the 13th candidate**, `docs/mem3-comparison-20260915/STATUS.md`), legacy arm finished 2026-09-15 (20/20 completed, final .861 vs .50); blinded rating 2026-09-16 (fresh Opus session, rubric inlined from the 2026-09-13 PREREG): fraction_bad findings **.042** (9/213) vs legacy **.109** (28/258), ratio .39 ≤ .50 → **supported**; prompt ratio 1.93 ≤ 2.2; coverage full but the c0004 opening miss; three seeds now read supported / not_supported / supported and are reported side by side, never pooled (`docs/mem3-comparison-20260915/RESULT.md`); human spot-check sheet drawn (`spot-check.md`); `last_logged_*` joined the outcome prefixes on main; an index-with-search replacement for the byte-bounded context is drafted in `docs/experiment-index-plan.md`; human spot-checks of both earlier pairs still open |

| Pi workers | Second harness implemented 2026-09-15 on branch `pi-workers` (`tools/lab-worker-pi`, `tools/pi/lab-worker.js`, `tools/lab_pi.py`, `scripts/llm-server.sh`); acceptance section P (fake pi) and a node test of the extension; preflight records the declared and served context window; the extension clips tool results and continues a run cut at the output limit | Two MNIST probes 2026-09-15 (`docs/pi-probe-20260915.md`): gpt-oss-20b 5/5 completed, final **0.9888** ≥ 0.985, sessions 22–64 s; Qwen3.8-27B 4/5 completed (one `length` stop, debugged), final **0.9937**, sessions 5–13 min. Both clear M1's kill criteria; quality not compared (noise floor) | Merged to main 2026-09-15 (`2670f06`); the research task with headroom on a local model is scaffolded as `../labloop-pi-engram-20260915` (engram w0, gpt-oss-20b via Pi, the mem2 legacy arm's configuration, `PREREG.md` with a contract kill criterion; the mem3 legacy arm finished 2026-09-15, so its launch is unblocked; human only); `engram-pi-gptoss-w0` ran 2026-09-16 and was stopped by hand at 10 settled (final .3577, not_supported; `runs/engram-pi-gptoss-w0/`); `engram-pi-qwen38-w0` ran 2026-09-16 and was stopped by hand at 3 settled (c0001 invalid, c0002 killed): the model thought ≈ 25k tokens per session at the template's default `xhigh` effort, 23 tok/s, and never wrote code; the server was rebuilt that afternoon (llama.cpp b10991, `--spec-type draft-mtp` from the GGUF's nextn head: 31–44 tok/s; `--reasoning-effort low`: an agent-sized turn in 19 s where `xhigh` was still thinking at 6000 tokens) and the second attempt `engram-pi-qwen38-w0-low` is prepared in the same dir (PREREG *Second attempt*), launch human only after the first run's files are moved to `runs/`; it ran 2026-09-16 and is read in `docs/pi-engram-20260916/READ.md`: **contract met** (16 of 18 completed, 0 provider errors, 2 killed after their predictions existed), claim recorded `supported` at final 1.0 but **not evidence for the task**: every candidate keys its memory on the question's record id and `attribute` field, not on the input tokens (a fixed rule of `task.md` the evaluator cannot see); w0's hidden labels are reconstructible from `facts.json`; 8.32 lease-hours held ≈ 3 h of `run.sh`, the 8 h lease budget stopped it at 19 of 20. Before the next local-model campaign: a world whose questions carry no `attribute` and opaque ids, a lease budget sized from the local worker's lease; then a hosted open model through the same `provider/model` id |

Current no-LLM acceptance: **643 passed, 0 failed** (2026-10-19, main after the v2 merge, the new default cards and the status fixes; on a quiet machine, since 12 loop-timing cases fail under heavy load). Before: **613 passed, 0 failed** (2026-10-18: v0.3 blind card = one-shot card, `[worker.operator_text]`, trust check at launch; run with `ANTHROPIC_BASE_URL` unset). Before: **554 passed, 0 failed** (2026-10-17, guard read scope; run with
`ANTHROPIC_BASE_URL` unset, which the auth preflight refuses). Before: **478 passed, 0 failed** (2026-09-15, branch `pi-workers`: +24 Pi checks in section P and the extension test; before that **413 passed, 0 failed** (2026-09-14 evening, e464135: second-slot draft rule, +3 slot cases; earlier that day 410 with findings-v2, initial_drafts and per-operator models; 2026-09-12: 388 including the
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

### 2026-09-17: guard read scope, training time, spot checks, `lab index`

- Guard: worker reads scoped to its own dir and the job card's parents (Bash, Read/Grep/Glob,
  Pi's read tools); the write rule looks at the destination only, so copying from a parent
  passes (`60aa2b4`). Item 1 below is partly done: read scope and editing tools covered;
  the sudo-Python evaluator boundary, settlement recovery and interrupted finals are not.
- `out/train_stats.json` in new job cards; `lab run` copies `train_seconds` into `config.json`
  at settlement; REPORT separates recorded training from lease time. The M4 criterion can be
  restated per training-hour in the next preregistration.
- Spot checks: on the human's decision a second blinded Opus rater stands in for the human
  check in all three memory pairs (mem3: 20 of 20 ratings agree). A stated deviation.
- `lab index` and `[memory] mode = "index-v1"` (`docs/index-eval-20260917/README.md`): 24 of
  29 rated errors reachable as of the worker's launch, 5 unknowable at launch; hybrid search
  +0.08 recall@5 over lexical, under the 0.10 rule, so lexical-only. **Next, human:** the
  preregistration of the pair findings-v3 vs index-v1 (seed, slots, the queries-per-job and
  cited-ids measures) and of the 60-candidate scale arm, which needs the new world files if it
  runs on the local model. Operator suggestions are designed in the plan (§5), not built.
- Hybrid search kept as an option (`7eccfce`): `[memory.embedder]` url + model, any
  OpenAI-compatible endpoint, frozen and preflighted; unset = lexical. `scripts/embed-server.py`
  serves a local checkpoint on CPU. Another model is a fixture rebuild and the same 24 probes.
- **The pair is scaffolded, not launched:** `../labloop-idx1-20260917/{PREREG,LAUNCH,ORDER}`,
  arms `../labloop-idx1-index-20260917` (first, drawn) and `../labloop-idx1-v3-20260917`, seed 5,
  two slots, lexical, tools from `f952c23`, both pass `campaign check`. Read 1 adoption (≥ 75 %
  of jobs with a parent query the index), primary endpoint better / not worse (+0.03) / worse.
  Launch is the human's: stop the local model server first, both GPUs idle.
- **Compression task** (`../labloop-compress`, world c0 from enwik8 via Hugging Face): hidden 2 MB,
  60 s on one core each way, program size counted, lower is better; the evaluator runs the
  candidate's code in a no-network container as `labeval` (a cheating decompressor, a C build and a
  runaway were tested); xz -9e baseline .2934 search / .2993 final; a four-candidate dry run with a
  scripted worker went baseline → docker eval → index → final. **Probe scaffolded, not launched:**
  `../labloop-compress-probe-20260917` (Qwen3.8 on Pi, index-v1, 8 workers, kill < 5 completed,
  threshold .2544). Needs once: `sudo bash worldgen/install_private.sh` in the base project. After a
  clean probe: findings-v3 vs index-v1 on this task at 40–60 candidates, which replaces the scale arm
  that waited on new engram world files; the idx1 Sonnet pair on engram stays scaffolded.

### 2026-10-17: labloop on labloop, a plan

- `docs/meta-loop-plan.md`: run labloop's loop on its own policy (scheduler, job cards,
  memory, worker tools) against a frozen trusted core. First a benchmark suite, labbench,
  of cheap CPU tasks from hidden generators with headroom for frontier models (admission
  rules and kill criteria K1–K8 in §2–§4), then the frozen commit's noise floor (§6), then
  hand-run single-idea pairs (§9); the outer loop is built only if the suite can see a 0.05
  gain in mean g at k ≤ 3. **For the human before anything runs:** the thresholds, the
  dollars-to-CPU-hours rate and quality floor of the meta-fitness, and whether the sudoers
  fix and the policy refactor (§1) land before the first probe.
- Labbench, same day. Generators live in the private `../labbench` (no remote). hsrc-v0 failed
  K2 (one-shot g .679 against xz). The plan was amended (a70928d): compression K2 is measured
  against a frozen generic compressor. hsrc-v1 passed K2 (best of three one-shots, gauge g
  .441). The v1 admission probe (`../labloop-hsrc1-probe-20261017/READ.md`) does **not admit**
  it: K5 and K6 fire. labloop's default policy (one opening draft, then improves) lost to
  draft-only random restarts, final gauge g .035 vs .307 on the same instance. That is the
  first measured policy effect, against the default. **Guard gap:** a crippled-arm worker read a
  sibling's `summary.md` once before the guard blocked it (its own disclosure, Acrip c0009). Find
  and fix this before any run where read scope matters.
- Guard gap fixed (92a059f, 06340e1: paths resolved, fails closed around `candidates/`; an OS
  wall is designed in docs/campaign-setup.md, not built). Admission rules v0.2 are in the plan
  §4 (8e4d912). `[selection] blind` built for v0.2's crippled arms: no population, best or
  lineage on the card, scoreboard reads refused by the guard. Acceptance **578 passed, 0
  failed**, run in a clean env (an inherited ANTHROPIC_BASE_URL fails the preflight by design).
  Families hrw, popt and pinf are built in `../labbench`, gauges frozen.
- pinf admission probe, the first family under rules v0.2: **fails K2**. The Opus one-shot reached
  gauge g .88 by mining the public tasks for the prior (`../labloop-pinf-probe-20261017/READ.md`). The
  chain launched no short runs. The new guard blocked some legitimate worker commands (false
  positives); see that READ. Next: hrw K2.
- Policy pair 1 (`../labloop-policy-pair1-20261017/READ.md`): `initial_drafts` 4 beat 1 on both fresh hsrc-v1
  instances, as predicted (D_A +.085, D_B +.041 in gauge g), but under the preregistered .10 floor: **not
  supported**. First σ_run: .029. No arm found the decisive hidden structure. Campaign workers use 6–19 turns per job
  against 41 for a one-shot; per-job effort (OPERATOR_TEXT 'prefer simple', 'ONE change') is the next pair's hypothesis.
- hrw and popt probes (v0.2): **neither admitted.** hrw failed K2 (Opus g .73). popt passed K2, but K3, K5
  and K6 fired: instance 2 saturated, found by the frozen arm and independently by one blind draft; instance
  1 sat at the gauge in 22 sessions. Discovery is per instance. Reads: `../labloop-{hrw,popt}-probe-20261017/READ.md`.
  **Rules v0.3 adopted 2026-10-18:** a fixed Sonnet worker, the one-shot as a policy, K2 as a median-session line,
  plus trusted arm dirs. **Confound:** no campaign dir since pinf was trusted (parent trust does not carry over).
  **Next:** the blind-card change (show c0000), the standalone one-shot arm, then hsrc-v1's re-probe and hrw's
  v0.3 probe, both with predictions, and a family design with several graded structures.
- **2026-10-18, after the five-family tally** (plan §4, "Decisions 2026-10-18"; with Fable 5.1). There will be no more planted-key families, and hsrc-v1's re-probe is not run; that was a decision, not a result.
  - **hrw's v0.3 probe** is scaffolded on fresh probe/3 and probe/4 (`../labloop-hrw-probe3-20261018`, six arms, predictions in PREREG). hrw is the one multi-key, graded family.
  - **The Haiku gate** is scaffolded (`../labloop-haiku-gate-20261018`): it decides whether a separate weak-worker programme opens.
  - Tooling f77ea4a: blind card = one-shot card, `[worker.operator_text]`, trust check at launch.
  - **For the human:** trust the 8 new arm dirs, then run the gate's `launch.sh` and, after it, the probe's `launch.sh`. If hrw is not admitted, close labbench v0.3 in writing.
  - **Haiku gate read (`../labloop-haiku-gate-20261018/READ.md`): the gate opens.**
    - The contract held 5/5 and the median session search g was .066, inside [.05, .17].
    - c0001 found two planted rules that no Sonnet session on this instance had found. Its best final g was .271.
    - Per-session sd was .085, at $0.04 per session, about 7× cheaper than Sonnet.
    - The Sonnet card check confirms the v0.3 blind card.
    - Four guard false positives are listed there.
    - **Next:** the hrw v0.3 Sonnet probe can launch (labbench at 775). labbench-haiku needs its rules written before any of its instances is scored.
  - **hrw v0.3 probe read (`../labloop-hrw-probe3-20261018/READ.md`): not admitted; labbench v0.3 closed.**
    - K3, K5 and K6 fired, K6 in the wrong direction: frozen .303 / .058 against blind .383 / .818 final g.
    - **Frozen improves added zero planted forms in 20 jobs** (5–9 turns each), while one blind draft found most of the planted rules.
    - labbench-haiku rules adopted (a142421).
    - **Next: the effort pair** (remove "ONE change" / "prefer simple") on hrw.
  - **Effort pair read (`../labloop-effort-pair-20261018/READ.md`): not supported, but close.**
    - Haiku, hrw instances 5 and 6, 8 paired seeds. Mean D +.096 (default .158, effort .254 final g); t 1.68 against the 1.895 needed.
    - Drafts ran 60 % longer without "prefer simple". No job was killed or invalid. It cost $4.
    - A replication on fresh probe/7 and probe/8 is scaffolded (`../labloop-effort-pair-rep-20261018`), with its own line as primary and the pooled 16-pair read as secondary.
- **2026-10-19 morning:**
  - The human decided to drop the two lines from the default cards (099600f) and to merge `v2` into main (0275840).
  - Status view: `fit` instead of `train`, and a Haiku worker's model is no longer blank (a33f4bc).
  - labbench task statements no longer say "Make ONE hypothesised change".
  - **A2 read (`../labloop-v2a2-20261019/READ.md`): no primary line supported.**
    - `draft_p` .3: +.050, p .14. `initial_drafts` 4: +.041, p .19.
    - The no-op line: forms added per improve .071 against .078, p .58. It removed no-ops (20/90 → 1/99), but final g leans negative (−.092, reported only), so it is not adopted.
    - $13.38 total.
  - **Next:** A3, the crossover line on shared snapshots (B2), with forms added per crossover as the primary.
- **2026-10-19 overnight (autonomous; the user asked for research, Fable/Opus review rounds and a start on labloop v2):**
  - **Effort pair replication** (`../labloop-effort-pair-rep-20261018/READ.md`), hrw 7/8, Haiku:
    - **The primary line is not supported:** D +.121, t 1.80 (needed 1.895). Default .136 against effort .258 final g.
    - **The pooled 16-pair secondary, declared before launch, is supported:** D +.109, t 2.54 ≥ 1.753. All 4 instances are positive.
    - **Improves adding a form:** 4/80 against 11/80; both runs together 4/160 against 21/160.
    - **Crossovers added a form 1 time in 54.**
    - **Recommendation (the human decides):** drop "Make ONE hypothesised change" and "Prefer simple and runnable" from the default cards. This rests on the pooled read plus the mechanism counts, not on a supported primary line.
  - **Branch `v2`** (10 commits ahead of main, not merged). Plan: `docs/labloop-v2-plan.md`, draft 3, after 3 review rounds (Fable 5.1 and Opus 5.5), a literature pass over 11 verified papers, and an Opus code review plus a verification pass.
    - Built, each off by default:
      - **C2** `[selection] restart_after`/`restart_min_step` (stagnation drafts);
      - **B1** `same_output_as_parent` metric (`[data] same_output_ignore`);
      - **B2** `[campaign] seed_from`/`seed_upto` (shared snapshot seeding for operator tests). It re-scores seeded fitness through the evaluator, never copies the source's final read, refuses symlinks, and uses a staged copy.
    - Acceptance **642/0** on v2. Docs are in `docs/campaign-setup.md`.
    - Dropped after review: sibling cards, the offspring penalty, the code-hash no-op gate, and the feedback hook (a leak channel).
  - **A2 factorial scaffolded, NOT launched** (`../labloop-v2a2-20261019`, 32 Haiku campaigns, about $10, pinned f77ea4a):
    - draft_p 0/.3 × initial_drafts 1/4 × a no-op line, on the effort base, blocked by fresh hrw instances 9–12;
    - lines in its PREREG.
    - **For the human:** `bash ../labloop-v2a2-20261019/trust.sh`, then `bash ../labloop-v2a2-20261019/launch.sh`. It refuses while labbench is locked.
  - **Also for the human:**
    - whether to merge `v2`;
    - whether to change the default cards;
    - the stray acceptance dirs under /tmp kept from one `KEEP=1` debug run (`/tmp/nullsilver-*`). They are deletable, but the agent is not allowed to `rm -rf` under /tmp.

- Guard read scope fixed, same day: globs (`*/c0008`, `cand*`), `cd candidates`, `../c0008` from the
  own dir, `c0003/../c0008`, variables, recursive walks over the campaign root and path-less
  Glob/Grep (and Pi find/grep) all got past the textual check; the guard now resolves paths and
  fails closed around `candidates/` (docs/campaign-setup.md, *Read scope*). +44 acceptance cases,
  31 of them failing before (the 13 allow cases pass both ways), plus 3 Pi bridge checks;
  **548 passed, 0 failed**. Not a sandbox: code a worker runs is not inspected,
  and campaigns scaffolded before today carry the old guard.
- Same evening, on the probe operator's findings: +6 cases for its exact forms (`head */*/…`, a
  session cwd already in `candidates/`, Glob/Grep with `path: "."`), all failing on the old guard.
  The rerun caught a flaky pass in 92a059f: a symlink into a sibling was checked by whichever of
  its two forms (lexical, real) a set yielded first; now both must pass.
  docs/campaign-setup.md now calls the guard a deterrent, not a wall, and designs the wall: a
  per-job bubblewrap mount namespace in `lab-worker`/`lab-worker-pi` showing only the own dir, the
  parents, task, data/train and eval. **Not built; the human decides.** This host refuses
  unprivileged bwrap (`apparmor_restrict_unprivileged_userns = 1`): a root step first, and
  `lab index` must be served from outside the wall.
- Guard false positives from the pinf K2 arms fixed. Of the three denials, two were correct
  (`ls candidates/*` in the same compound command; the python heredocs that read `data/train`
  pass on their own). The third, `mkdir -p <own>/code && cd $_ && …`, was a bug: the cwd tracker
  took `$_` from the hook's own environment, its python3, so every later path resolved under it.
  `$_` is now the previous command's last argument, or unknown. The same tracker read `$OLDPWD`
  from the hook too, and modelled `cd -`, `~-`, `~N`, `popd`, a bad `cd` option, extra `cd` args,
  CDPATH, a `cd` that fails and a piped `cd` as moves that happened. Ten of these were live
  bypasses at 953f028 (in a fixture, real bash read a sibling and the guard allowed it); `$OLDPWD`
  is live whenever the worker's persistent shell ran a `cd` in an earlier call. Each now leaves
  the dir unknown, or follows it exactly. Ids built from variables (`X=c000; cd ${X}0`) are
  checked as well. +25 acceptance cases; **603 passed, 0 failed** in a clean env. Still open: a `cd` inside `{ …; }`, `eval`,
  `bash -c`, or after deleting its target is not followed. Campaigns scaffolded before this
  commit carry the old guard.

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
