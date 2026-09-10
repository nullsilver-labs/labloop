# NEXT — replace the phase machine with AIRA₂'s loop

labloop today is a six-phase state machine with human approval gates, protocol
revisions, handoffs and per-phase prompts. This plan **replaces** that with the search
loop published in AIRA₂ (Meta FAIR, arXiv 2603.26499), adding only what a local box
with 1–2 RTX 3090s and a Claude Max subscription requires. Nothing from the phase
machine is kept "alongside".

Reference design: **AIRA₂ only.** It is published, its predecessor is open source
(aira-dojo), and its results are measured. AIRA₃'s forum is unreleased and unmeasured
outside Meta; we do not build a hybrid we cannot validate against anything.

Written 2026-09-09. Supersedes the first draft of this file, which still carried
gates, phases, protocol ceremony and a forum. See §7 for what was dropped and why.

**Status (2026-09-09): M0 done** on branch `aira2-loop` — `tools/lab_campaign.py`
registers `lab campaign|candidate|eval|job|run`; `scripts/acceptance_campaign.sh`
drives it with a scripted worker (50 checks, all passing, no LLM). The phase machine is
untouched until M5. Known gap: two free slots in one tick may dispatch the same
(operator, parent) pair; harmless with seeded real workers, wasteful with a
deterministic one.

**M1 done (2026-09-09, live).** Project `/mnt/data/projects/nullsilver/labloop-m1`:
MNIST, one RTX 3090, Sonnet workers, greedy draft/improve, 5 candidates. Baseline 0.1172;
draft 0.9864 on the hidden search split at the first attempt; three improves 0.9863 /
0.9862 / 0.9870; frozen c0004 scored **0.9875 on the final split, claim supported**
against the pre-fixed 0.985. Sessions: 12–17 turns, 83–134 s, median list-price
equivalent $0.29 on subscription; GPU 0.13 h; wall clock 8.5 min. Both kill criteria
cleared: a Sonnet worker produces a runnable candidate well inside 40 turns, and a
candidate costs a small fraction of a phase session. Caveats: five candidates is a probe,
not a search; MNIST improvements sit at the noise floor after 5 epochs; privilege
separation was off. Two bugs found and fixed by the run: children inherited parent
weights, and headless sessions in an untrusted directory ignore the project allow-list
(docs/campaign-setup.md). Next: M2 (crossover, temperature > 0, 24 h on a task with
headroom) and M3 (usage governor) before any unattended run.

**M3 built (2026-09-10), not yet run unattended.** `[usage]` in `campaign.toml`; the
governor lives in `tools/lab_campaign.py` (`usage_state`, `govern`, `defer_job`).
Rolling-window estimate from each session's `total_cost_usd` plus a reservation per
running session; `soft` stops dispatch (campaign status `waiting_usage`, with reason
and next-eligible time), `hard` kills running sessions and defers their jobs; a
rate-limit message in a session result defers the job, blocks until the stated reset,
and re-dispatches it (`redispatch_of` in provenance). `lab campaign usage` is the
calibration view; `REPORT.md` gains a usage section with the idle share of wall clock
that M3's kill criterion reads. Acceptance section E covers soft pause/resume with
restart, rate-limit deferral and re-dispatch, hard kill (288 checks). Open before the
weekend run: `usage.window_budget` must be calibrated against `/usage` by hand (no
non-interactive read exists), and the headless CLI's exact wording on a spent window
is undocumented, so the first deferred candidate's `session.json` is to be checked.

---

## 1. The loop

```
campaign.toml ──► lab run ──► [ select parent → worker → evaluate → add to population ] ──► report
                    ▲                                                                      │
                    └──────────────── until a stop condition ───────────────────────────────┘
```

One process, `lab run`, runs the whole campaign. Every tick:

1. **Reap** finished jobs: read the candidate's `fitness.json`, add it to the
   population, write its LEDGER row. Killed or crashed → status `failed`, kept.
2. **Enforce** budgets (§4). Over any hard limit → stop launching; running jobs finish
   or are killed at their own wall-clock cap. No prompt, no wait.
3. **Dispatch** while a GPU slot and a usage slot are free:
   - empty population → `draft` (one per free GPU, different seeds);
   - otherwise sample a parent by temperature-scaled rank over search fitness
     (AIRA₂ §3), then `improve` with p = 0.85 or `crossover` (two parents) with p = 0.15;
   - a `failed` candidate under its retry cap → `debug` on it instead.
4. **Stop** when a stop condition fires: GPU-hours, candidate count, wall clock,
   or no improvement in the best search fitness for N settled candidates.
5. **Finish**: freeze the best candidate by search fitness, evaluate it **once** on the
   untouched final split, write `REPORT.md`, exit.

The human writes `campaign.toml`, starts `lab run`, and can `lab stop` it. The human
is not a dependency inside the loop.

---

## 2. What the human writes once

`campaign.toml` replaces `PROTOCOL.md`, its frontmatter, revisions and `plan.json`.

```toml
[campaign]
id          = "ns-tinyft-01"
task        = "prompt.md"              # the task statement workers receive verbatim
kind        = "research"

[data]
train       = "data/train"             # workers may read
search      = "$LAB_PRIVATE/ns-tinyft-01/search"   # only `lab eval` may read
final       = "$LAB_PRIVATE/ns-tinyft-01/final"    # read once, at the end
evaluator   = "eval/score.py"          # pure: (predictions, labels) -> number, higher is better
baseline    = "eval/baseline.py"       # the trivial solution; always in the population as c0000

[resources]
gpus              = [0, 1]
gpu_hours_total   = 40
job_wall_clock    = "3h"
worker_max_turns  = 40
worker_model      = "claude-sonnet-5"
usage_soft        = 0.70               # fraction of the Max 5-hour window, stop dispatching
usage_hard        = 0.90               # pause everything

[stop]
max_candidates     = 60
no_improvement_for = 12
wall_clock         = "48h"

[report]
success_threshold = 0.85               # a reporting criterion, never a blocker
```

`success_threshold` is a scientific threshold, fixed before the campaign, reported
against at the end. It does not block anything. The words "gate" and "approval" do
not appear in the new CLI.

---

## 3. Data model

```
campaign.toml                 # the human's, read-only to lab after `lab run` starts
population.json               # lab-owned index: id, parents, operator, status, fitness, cost
LEDGER.md                     # one row per candidate, append-only (kept from today)
candidates/c0042/
  config.json                 # parent(s), operator, seed, commit, command, gpu, hardware,
                              # requested/served model — today's provenance contract, extended
  code/                       # the candidate's own copy; the worker edits nothing else
  console.log                 # tee of the worker session + training run
  results.jsonl               # append-only, the run's own records
  summary.md                  # the worker's one page: what changed, what happened
  fitness.json                # written only by `lab eval`: {"search": 0.81, "n": 1234}
REPORT.md                     # written once by `lab run` at the end
events.jsonl                  # public feed, same contract as today (§5)
```

**Memory** is AIRA₂'s, not a forum: when a worker gets a parent it also gets the
parent's `summary.md`, the summaries of the parent's lineage, and a one-line entry per
member of the current population (id, operator, fitness). That is all the "what has
been tried" context there is, and it is generated by `lab`, not written by anyone.

**Evidence is still immutable.** Candidate dirs, LEDGER rows and `events.jsonl` are
never edited or deleted; `guard.sh` keeps blocking that. A misleading result gets a
line in the next candidate's summary, not a deletion.

---

## 4. Plumbing — invisible during research, non-negotiable

These are the four things labloop insists on. None of them asks a human anything.

**Trustworthy evaluation.** `search` and `final` labels live under `$LAB_PRIVATE`,
owned by a second Unix user `labeval`. `lab eval` is a wrapper that runs the
evaluator as that user through one sudoers line. Workers run as you and cannot read
the labels even if they try; `guard.sh` also blocks the path pattern so an attempt is
visible in the feed. Workers see scores, never labels. `final` is read exactly once,
by `lab run`, after the search has stopped — the Hidden Consistent Evaluation split
from AIRA₂.

**Bounded resources.** Every job runs under the existing `lab watch` supervisor with
`--budget-min` from `job_wall_clock`, `--stall-min`, and a GPU pinned through
`CUDA_VISIBLE_DEVICES`. Free VRAM is checked with `nvidia-smi` before launch. The
campaign's `gpu_hours_total` is enforced by not dispatching. Prohibited operations
(network writes, package installs outside the candidate's venv, paths outside the
candidate dir, `$LAB_PRIVATE`) are **rejected** by `guard.sh` and Claude Code's
permission mode, not escalated.

**Restart-safe bookkeeping.** `lab run` is idempotent from disk: `population.json`
plus each candidate's `config.json`/`fitness.json` is the whole state. Kill it and
start it again and it reaps, re-evaluates anything measured but not settled, and
continues. There is no SQLite ledger; the filesystem is the ledger.

**Immutable results.** As above. Plus every `config.json` carries seed, git commit,
command, hardware, library versions, and requested/served models, as today.

### The Claude Max window

Max is a rolling 5-hour usage allowance, not money. It is the second scarce resource
and gets the same treatment as GPUs:

- Only `claude -p` (Claude Code itself) touches the subscription. No Agent SDK, no
  raw API, no third-party harness on the OAuth token. Any API key in the environment
  is a `lab validate` error under this profile. *Confirm current Anthropic terms for
  unattended Claude Code use before the first overnight run and record that in
  `REPORT.md`.*
- `lab usage` already sums tokens from session transcripts. `lab run` keeps a rolling
  5-hour estimate and applies `usage_soft` / `usage_hard`. A rate-limit message in a
  worker's console marks the job `deferred` (re-dispatched after the window turns),
  never `failed`.
- Sessions are short by construction: one job, `worker_max_turns`, no handoff
  document. A worker that cannot finish writes its `summary.md` and exits; the job is
  re-dispatched once with that summary as extra context, then marked `failed`.
- Interleave GPU and model time: while c0041 trains on GPU 0 for two hours, a worker
  drafts c0042 for GPU 1. The governor should aim for an even trickle of sessions
  across the window.

---

## 5. What is kept from today, and why

Kept because it is plumbing, not governance:

- `tools/lab` as the single writer of `population.json`, `LEDGER.md`, `events.jsonl`,
  and the hook that blocks hand edits.
- `lab watch` as the only legal way to run something detached.
- `lab trial new/done` semantics, renamed `lab candidate`, with the same `config.json`
  provenance and the killed-stub summary.
- `lab usage` token accounting, now feeding the usage governor.
- The public feed contract: one-line `msg` ≤ 140 chars, mechanical redaction, feed
  classes, `FORMAT.json` generated. nullsilver.com renders the campaign; that is a
  consumer, not a control. Event vocabulary becomes `campaign.start|stop`,
  `candidate.launch|done|failed`, `eval.done`, `run.paused`, `report.written`,
  `metric`, `note`, `error`. Phase, gate, prediction, protocol and session events go.
- `scripts/acceptance.sh` as the no-LLM end-to-end test, rewritten for the loop.

Removed outright: the six phases and their prompts, `supervise.md`, `HANDOFF.md`
and the Stop hook that demands it, `PROTOCOL.md` and `protocol/rev*`, `plan.json`,
`lab gate`, `lab protocol`, `lab state set`, `loop.sh`'s phase loop, `/orchestrate`,
`prediction` and `surprise` events, `autonomy: gated`. `CLAUDE.md` shrinks to the
values that still apply to a worker: report what happened, the baseline is in the
population, spend context like compute, never touch another candidate's dir.

---

## 6. Milestones

Smallest thing that can kill the idea first. Each has a kill criterion; if it trips,
stop and write it down.

**M0 — Loop with a scripted worker, no LLM (≈ 2 days). DONE.**
`campaign.toml` parsing, `population.json`, `lab candidate`, `lab eval` with the
`labeval` user and `$LAB_PRIVATE`, rank selection, stop conditions, restart from disk,
`REPORT.md`. A toy task (fit `y = x²` on an integer grid is fine) with a shell
"worker" that emits a fixed candidate. `scripts/acceptance.sh` covers: labels
unreadable to the worker, readable to `lab eval`; kill mid-job → `failed`, kept;
kill `lab run` mid-settle → restart settles once, no double count; `final` read once.
*Kill if:* the privilege separation cannot be made to work on stock Ubuntu without
root at run time.

**M1 — Real worker, one GPU (≈ 3 days). DONE, see status above.**
`draft` and `improve` only, greedy selection, one slot, a sub-hour task with a known
answer and a natural held-out split. Run for one Max window.
*Kill if:* a Sonnet worker cannot reliably produce a runnable candidate from the task
statement in ≤ 40 turns, or median cost per candidate exceeds a phase session's today
(`lab usage`).

**M2 — Full AIRA₂ operators and selection (≈ 2 days).**
`debug`, `crossover`, temperature-scaled rank, lineage summaries as memory. Same task,
24 h.
*Kill if:* best search fitness after 24 h is not better than M1's greedy run at equal
GPU-hours. A tie is a tie; report it.

**M3 — Usage governor, unattended (≈ 2 days). BUILT 2026-09-10, weekend run pending.**
Rolling-window estimate, soft/hard thresholds, `deferred`, rate-limit detection.
Run over a weekend.
*Kill if:* the loop idles more than 20 % of wall clock on usage, or a worker ever
continues past a rate-limit message.

**M4 — Two GPUs (≈ 2 days).**
Slot leasing, VRAM check, concurrent dispatch.
*Kill if:* settled candidates per GPU-hour fall below M2's single-GPU figure.

**M5 — Delete the phase machine and republish the format (≈ 2 days).**
Remove everything in §5's "removed" list, bump `FORMAT.json` to 2.0, update the
site's renderer to draw a population instead of a phase strip.

Then the first real campaign and its `REPORT.md`: baseline, best-by-search, final
score, the pre-fixed `success_threshold`, GPU-hours, Max usage.

About three weeks, with the runs that decide whether to continue interleaved.

---

## 7. Dropped from the first draft, and why

- **Approval gates.** They made the human a dependency inside the loop. Money is not
  in the loop (Max is prepaid), irreversible actions are rejected by permission mode
  and `guard.sh`, and a protocol change is a new campaign. Nothing is left to approve.
- **Phases "for now".** Adding the loop beside them would have kept both alive.
- **PROTOCOL.md, revisions, `plan.json`.** One `campaign.toml` written once.
- **The AIRA₃ forum.** Unreleased, unmeasured. AIRA₂'s lineage summaries are the
  published, tested memory mechanism.
- **Mandatory predictions and `prediction` events.** Bureaucracy inside `improve`.
  A worker's `summary.md` states what it changed and what happened; that is enough.
- **A periodic `analyze` operator.** Not in AIRA₂. If lineage summaries prove too thin
  for workers, this is the first thing to revisit, with a measurement.
- **The aira-adj SQLite ledgers, leases and packets.** The filesystem plus `lab watch`
  is the restart-safe ledger. Only its `scripts/acceptance.sh` fixes are cherry-picked
  onto `main`; the branch is closed.

## 8. Adopted from the 2026-09-06 "budget-aware autonomous discovery" proposal

That proposal is the design behind `aira-adj`. Most of it is spending governance for
providers this setup does not have (see the assessment in the session log); these
parts are right and are folded in here:

- **Four separate statuses, never one GO/NO-GO.** Trial execution
  (`completed|failed|killed|invalid`), candidate (`queued|running|evaluated|failed|
  frozen`), claim (`untested|supported|not_supported|inconclusive`, written only by
  `lab run` from the final split against `success_threshold`), campaign
  (`running|waiting_usage|finished`). `population.json` carries the first two,
  `REPORT.md` the last two.
- **Auth preflight before the first session.** An API key or other credential source
  overrides subscription login in Claude Code, and `--bare` bypasses it. `lab run`
  refuses to start if `ANTHROPIC_API_KEY` or an endpoint override is set, and never
  passes `--bare`. Checked once at campaign start and recorded in `REPORT.md`.
- **Waiting is a state, not an error.** `waiting_usage` carries a reason and the next
  eligible time; no worker is asked to poll.
- **Measure the loop against a baseline of its own.** M1/M2 report, per task: human
  interventions and minutes, verified final score, GPU-hours, Max window usage,
  invalid-candidate rate. Compare against (a) the phase machine on `main` and (b) one
  plain interactive Claude Code session given the same task and evaluator. Adoption
  criterion: fewer human interventions with no worse verified outcome at equal
  authorized resources. Small samples prove engineering usefulness, not superiority.
- **Tests from its §12** that apply without a paid provider: subscription exhausted
  mid-session → deferred, no polling; turn ceiling → summary and re-dispatch, not a
  gate; worker alters evidence or `$LAB_PRIVATE` → denied by the OS, not a prompt;
  secret planted in a log → not in `events.jsonl`; restart mid-settle → no duplicate.
- **aira-dojo is CC BY-NC 4.0; labloop is MIT.** Implement AIRA₂'s ideas, vendor
  nothing.

Not adopted: multi-pool/multi-provider ledger, prepaid-credit route, hash-bound
approvals, discovery/verification modes, "keep legacy operation available",
per-campaign caps of three candidates, one checkpointed researcher. Reasons in §7
and in the assessment.

## 9. Two decisions that are still yours

1. **First task for M1.** Sub-hour on a 3090, known answer, natural held-out split.
   Pick it before M0 so the fixture matches.
2. **Public feed during search.** Publish every candidate live, or only the final
   report? Same contract either way; the difference is how much half-finished work
   is on nullsilver.com. Default: live, because that was the point of the site.
