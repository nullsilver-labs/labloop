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
| M2 | Full operators and selection implemented | CIFAR-10: 40 settled, final 0.9472 ≥ 0.90; greedy control running since 2026-09-12T11:40Z | Read the control's report, compare at equal GPU-hours (see "Live now"); original 24 h criterion untested |
| M3 | Governor and fake-CLI tests implemented; live rate-limit enforcement by the watcher (2026-09-12, section E2b) | M2 had pacing OFF; no observed deferrals | Calibrate budget, then unattended validation |
| M4 | Slots, VRAM checks and fake-GPU tests implemented | Reviewed campaigns used one GPU | Real two-GPU throughput comparison |
| M5 | Phase removal and format 2.0 complete locally | Site renderer completion recorded historically | External deployment not independently audited in this review |
| Finding cards | Implemented and tested (opt-in `[memory]`, format 2.1, section G); prompt-size pilot run 2026-09-12 (`docs/finding-cards-pilot.md`) | None | Fix the preregistration values from the pilot, then the legacy-vs-findings comparison (plan §7) |

Current no-LLM acceptance result: **373 passed, 0 failed** (2026-09-12, after finding cards).
Counts in dated entries below describe historical suites, not today's coverage.
Passing synthetic tests does not establish OS isolation, exact crash recovery or live
subscription behavior. Both reviewed live reports disclose label separation OFF.

M2's immutable report exists at `../labloop-m2/REPORT.md`, written
2026-09-10T16:16:02Z. Do not rerun final evaluation or rewrite historical reports to
complete this roadmap.

### Live now (written 2026-09-12, for the next session)

The **M2 greedy control** is running in `../labloop-m2-greedy` (campaign
`m2-cifar10-greedy`, launched 2026-09-12T11:40Z under `lab watch --op campaign`,
budget 1500 min, GPU 0, governor OFF like the search, tools synced from commit
`9ff609a`, format 2.1; legacy job cards render byte-identically under the 1.4 copy the
search used, and the selection code is unchanged). Expect roughly 7 h. Check with
`tools/lab campaign status` there; nothing in that directory is to be edited while it runs.

When it has finished (`REPORT.md` exists there):

1. Read `../labloop-m2-greedy/REPORT.md` next to `../labloop-m2/REPORT.md`. M2's kill
   criterion reads the search's best search fitness against the control's **at equal
   GPU-hours** (search: best 0.9498 by c0032, 40 settled, 7.11 GPU-h, final 0.9472):
   take the control's best-so-far at the search's GPU-hours from its LEDGER and
   population, and the search's at the control's if the control ran shorter. Both runs
   sit inside the ~0.4-point noise floor (n = 5000): a difference under that is a tie,
   and a tie is reported as a tie. Record the comparison in this file's status table,
   not in either report. Neither run is the prescribed 24-hour comparison; say so.
2. Read the control's usage section. If any job was deferred, open that candidate's
   `session.stderr` and `session.json` and confirm the headless CLI's wording matched
   `usage.rate_limit_regex` (docs/campaign-setup.md, "The first real rate limit"); note
   the wording here. Zero deferrals leaves M3's live evidence still pending.
3. `scripts/sync-project.sh ../labloop-m1` and `../labloop-m2` when convenient: both
   finished projects still carry 1.4 tool copies with phase-era `.claude/commands`,
   `.claude/prompts` and `loop.conf`; their evidence is untouched by a sync.
4. Then, in order: fix the finding-card preregistration values
   (`docs/finding-cards-pilot.md`, proposals table) and write them into the two
   comparison `campaign.toml`s before either starts; the two-GPU run (M4); next-work
   item 1 below. Push `aira2-loop` and merge to `main`.

### Next work, in priority order

1. Harden the evaluation boundary (the documented unrestricted sudo Python rule is
   not worker isolation), settlement recovery and interrupted-final handling. Add
   fault injection; prefer an explicit inconclusive interrupted final over a silent
   second read. Cover direct editing tools as well as Bash guardrails.
2. ~~Test rate-limit detection against a worker that emits a limit message and keeps
   running; enforce termination rather than relying on CLI exit.~~ Done 2026-09-12:
   `lab-worker` echoes the CLI's stderr under a prefix into the watcher log and every
   worker job carries a kill pattern scoped to that prefix (`session_kill_regex`);
   acceptance E2b kills a fake CLI that retries forever and re-dispatches the job.
   The wording of the real headless CLI is still to be confirmed on the first live
   deferral (docs/campaign-setup.md).
3. Complete the greedy comparison and calibrated unattended governor evidence on
   prospectively fixed configurations. Define comparable resource accounting before
   launch; preserve the original milestone criteria and report deviations explicitly.
4. ~~Implement finding cards as a separate opt-in change~~ (done 2026-09-12), ~~run the
   prompt-size pilot~~ (done 2026-09-12: facts-only cards +26 %, cards at their limits
   +79 % over the legacy job card on M2's 39 jobs; `docs/finding-cards-pilot.md`), then
   fix the preregistration values and compare memory policies without changing
   scheduler/model/budgets. Run the real two-GPU comparison separately.

The missing comparative and unattended evidence is **pending**, not a pass, tie or
failed kill criterion. Subscription renewal alone does not validate the governor.
