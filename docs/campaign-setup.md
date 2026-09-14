# Starting a campaign

What a new project needs before `lab run` works. Learned on the first live run
(M1, MNIST, 2026-09-09); see docs/aira2-loop-design.md for the design and NEXT.md for status.

1. **A project directory** with the template's `tools/`, `.claude/`, `templates/`,
   `CLAUDE.md`, `.lab-redact` copied in, and `git init` (candidate provenance records
   the commit). Ignore `.lab/`, `.venv/`, raw data and weights in `.gitignore`.
2. **`campaign.toml`** from `templates/campaign.toml`, plus the task statement, the
   evaluator (stdlib-only Python: `score.py <predictions> <labels_dir>` printing
   `{"score": x, "n": k}`), and the baseline command. `tools/lab campaign check`
   validates it.
3. **Data splits.** `data/train` (readable), `data/search` and `data/final` inputs in
   the repo; their labels **outside** the repo under `$LAB_PRIVATE/<campaign>/…`.
   The final split is read once, at the end. Export `LAB_PRIVATE` only in the shell
   that runs `lab run`; workers never receive it.
4. **A Python environment for candidates.** The worker's `code/run.sh` must name an
   interpreter that has what the task needs (torch, numpy …); the system `python3` is
   used only by `lab` itself and the evaluator. Say the path in the task statement.
5. **Trust the project directory once** for Claude Code, or headless sessions ignore
   the project's `permissions.allow` (they still run the hooks). Either open
   `claude` interactively there once and accept the trust dialog, or set
   `projects["<abs path>"].hasTrustDialogAccepted: true` in `~/.claude.json`.
6. **Subscription login only.** `claude auth status` must say `loggedIn: true`; no
   `ANTHROPIC_API_KEY` or endpoint override in the environment. `lab run` and
   `lab-worker` refuse to start otherwise.
7. Optional but recommended: the **`labeval` user** (`docs/labeval.md`) so hidden
   labels are hidden by the OS, not by convention. REPORT.md states which.

8. **Refreshing tooling** in an existing project: `scripts/sync-project.sh <project>`
   copies `tools/`, `.claude/`, `templates/`, `CLAUDE.md` and `.lab-redact` from this
   repo and touches nothing else. Never during a run.
9. **Two GPUs**: list both in `resources.gpus` and set `max_parallel_jobs = 2`.
   `min_free_vram_mb` skips a GPU that something else is using (checked with
   `nvidia-smi` before every lease, noted in the feed once per episode).

Then:

```sh
export LAB_PRIVATE=~/.local/share/labloop-private
tools/lab campaign check
tools/lab run campaign.toml --poll-sec 10        # or under: lab watch start --op campaign --budget-min N -- tools/lab run …
tools/lab campaign status                        # any time, from another shell
tools/lab serve                                  # read-only page for a phone on the LAN (port 8791)
tools/lab campaign stop [--now]                  # stop dispatching (and kill running jobs)
```

## Supervising the campaign controller

Use a wall-clock-only outer watcher for `lab run`, for example:

```sh
tools/lab watch start --op campaign --budget-min 60 -- tools/lab run campaign.toml --poll-sec 10
```

Do **not** add an outer `--stall-min` to this command with the current generic
watcher: the controller quietly updates state files while candidate watchers and
workers run in separate sessions with separate logs. Its own log/session CPU can
therefore look idle during useful training. A ten-minute outer stall setting killed
a progressing sustained smoke on 2026-09-12. The absolute outer budget remains the
enforcer; candidate watchers retain their own wall/stall checks. A future
campaign-aware stall check must measure actual campaign progress, not just the
controller log. Set the outer wall cap with room for final execution/scoring; an
outer timeout is an interruption, not a completed campaign.

## Worker lifetime (Linux)

The default `tools/lab-worker` disables Claude Code's explicit **and automatic**
background tasks with `CLAUDE_CODE_DISABLE_BACKGROUND_TASKS=1`. This control and
`BASH_DEFAULT_TIMEOUT_MS` / `BASH_MAX_TIMEOUT_MS` were verified in the locally
installed Claude Code **2.1.269** binary (including the Bash auto-background branch),
not assumed to be CLI flags. Both Bash timeouts are set to the job wall-clock cap;
a worker should request a smaller timeout within its **remaining** budget. The outer
watcher remains the deadline authority. Check these controls when upgrading the CLI.

Workers run `code/run.sh` synchronously, wait for its exit, check the exit code and
predictions, then write `summary.md` before ending the session. No `run_in_background`,
shell `&`, `nohup`, `setsid`, or nested `lab watch`: the candidate already has its
watcher. The Bash hook rejects common detach attempts at simple command positions,
not mentions in quoted prose, and skips conventional heredoc payloads. It is a
shallow heuristic, not a full shell parser: wrappers, complex quoting/delimiters,
and commands embedded in scripts can evade it. CLI background controls and owned
process containment are the lifetime enforcement, not perfect shell detection.
`lab watch start/_run` also refuses worker invocations. Operator watchers remain
available.

Linux subreapers contain the CLI lifetime and each candidate watch (including
baseline/final execution). On CLI return, owned live descendants are terminated and
reaped **before** the wrapper checks predictions; pending work makes the candidate
invalid even if the CLI returned success. There is no grace period to await missing
predictions or to salvage late outputs. On job completion or watcher kill, detached
and double-forked descendants are likewise drained before the watcher publishes a
terminal entry, releases its resource lease, or permits settlement. Cleanup uses
pidfds with direct-child ownership checks, never broad process-name/UID kills.
TERM has one second, then KILL/reaping has five seconds. If the kernel cannot kill a
process, the watcher retains the lease, records `cleanup_error`, and retries visibly.

This is lifecycle containment, **not OS security isolation**: hooks are guardrails,
a same-user adversarial process can bypass them, and externally killing the watcher
itself (especially SIGKILL), host failure, or external service delegation is outside
this guarantee. Kernel I/O can delay teardown indefinitely; don't claim compute has
stopped while the watcher is running with `cleanup_error`. Linux `/proc`, `prctl`, and Python/kernel
pidfd support are required; unsupported systems fail before candidate execution.
Do not update tools or resume the tainted historical control for comparison: use a
fresh campaign identity and freshly trained candidates after a bounded smoke test.

## The usage governor (the Claude Max window)

Max is a rolling 5-hour allowance, not money, and `lab run` treats it like a GPU:
a resource with a budget, enforced by not dispatching. Configure it in `[usage]`:

```toml
[usage]
window_budget = 12.0   # list-price USD per 5 h window the plan tolerates; see below
soft = 0.70            # of window_budget: dispatch nothing new, status waiting_usage
hard = 0.90            # also kill running sessions (a session cannot be paused);
                       # their jobs are deferred and come back when the window has room
```

Two signals feed it. The **estimate** sums `total_cost_usd` of every worker session that
ended inside the window (the list-price figure `claude -p` reports for a subscription
session; the subscription itself is prepaid) plus one reservation per running session,
and compares it with `window_budget`. The **fact** is a usage-limit message in a
session's result ("You've hit your limit · resets 3pm"): that job is marked
`deferred`, never `failed`, dispatch is blocked until the stated reset (or
`usage.retry` later), and the job is re-dispatched as a new candidate whose
`config.json` says `redispatch_of`. `lab campaign status` and `lab campaign usage`
show the governor's view; `REPORT.md` reports the peak window estimate, pauses, time
waiting as a share of wall clock (M3's kill criterion is 20 %), and deferrals.

**Calibrating `window_budget`.** Anthropic publishes no token figure for the window,
and headless Claude Code has no non-interactive `/usage`. So the budget is empirical:
run a short campaign, read `lab campaign usage` (spend per session, sessions per
window) next to `/usage` in an interactive session, and set `window_budget` to the
list-price spend at which the plan sat near 100 %. Without a `window_budget` the loop
only reacts to rate-limit messages and cannot pace itself; `lab campaign check` warns.

**The first real rate limit.** The headless CLI's output on a spent window is not
formally documented; the default `usage.rate_limit_regex` matches the interactive
wording and a 429. After the first unattended run, open the deferred candidate's
`session.json` and `session.stderr`, confirm they matched, and tighten the regex in
`campaign.toml` if the wording differs.

**A session that keeps running past the message.** `lab run` does not rely on the
CLI exiting. `lab-worker` echoes the CLI's stderr, line by line under a
`[claude stderr]` prefix, into the job's watcher log, and every worker job is launched
with a kill pattern that is the rate-limit regex scoped to that prefix. A CLI that
prints the message and then waits or retries is killed by the watcher within one poll
(the default poll is 15 s), the job is settled as `deferred` with the watcher named in
its reason, and it is re-dispatched after the stated reset. Nothing a training run
prints can match the pattern, because only the CLI's stderr carries the prefix (in
`-p` mode a tool's output never passes through it). A message with no trailing newline
is enforced just the same: the echo is unbuffered and the watcher searches the
unterminated tail of its log on every poll. A transient message that the CLI would
have retried through is deferred too: one re-dispatch, never a failed candidate. When
you tighten `usage.rate_limit_regex`, remember it is embedded after that prefix: use
scoped flags such as `(?i:…)`, not `^` or `$`; `lab campaign check` compiles the
combination.

## Finding cards (opt-in memory)

By default a worker sees the first-parent lineage of clipped summaries. `[memory]
mode = "findings-v1"` in `campaign.toml`, set **before the first `lab run`**, replaces
that with finding cards: the policy and its limits are frozen into `population.json`
when the campaign starts, so a tooling update cannot change a running campaign's
memory, and a campaign started without the key stays legacy for its whole life
(`lab run` warns if the file asks for cards under a legacy population). The design is
`docs/finding-cards-plan.md`.

**What the worker is asked to write.** Its job card requests a `## Finding` section at
the top of `summary.md`: `Change`, `Hypothesis`, `Local observation`, `Interpretation`,
`Limitations` and `Topics`, each exactly one physical line, each exactly once, at most
five topic slugs. A worker does not know the hidden search score and never states one;
local numbers stay its own. The parser is mechanical — a missing, duplicated or
malformed field costs the candidate nothing and produces a facts-only card with the
reasons; nothing is inferred from prose and `summary.md` is never modified.

**What the lab publishes.** `candidates/cNNNN/finding.json`, written once by `lab run`
after the candidate settles (completed, failed, killed, invalid or deferred alike) and
never overwritten. It is built only from `fitness.json`'s **search** record,
`population.json`, `config.json` and the parsed Finding section: identity, execution
outcome, the search score with n and evaluator fingerprint, the raw delta to each
parent, seed and model provenance, the worker's six lines marked worker-reported, the
caveats and source digests. A number in worker prose is never promoted into a measured
field, and nothing from the final split ever enters a card.

**What the next worker sees.** At dispatch, `lab run` selects up to 8 cards and 12 KiB
of rendered context, deterministically and without touching the scheduler's RNG: the
direct parents, up to two nearest ancestors traversed across both sides of a crossover,
then other branches — a same-topic run that did not beat its strongest parent, other
topic matches, the strongest off-lineage candidate, a recent execution problem, then
recent findings. Selected ids, reasons, card digests and the rendered text are stored
whole in `job.json`, so `lab job card` prints byte for byte what the worker saw, however
many candidates have ended since.

A `finding.json` that already exists when a candidate settles was written by the
worker, not by `lab`: it is renamed `finding.worker.json` (kept as evidence), the
attempt is recorded `invalid` with that reason, and the real card is published from
the sources as usual. On every tick each existing card must be valid, agree with its
sources and equal the card `lab` rebuilds from them; a restart from a shell whose
`.lab-redact` secrets differ can therefore stop on a card whose redaction differs.

**When `lab run` stops with a card error.** A card that fails validation or disagrees
with its sources blocks dispatch as a tooling error, naming the card and the failed
check. Nothing is repaired, overwritten or superseded automatically and the candidate
is not marked failed: inspect the candidate dir and decide. v1 has no supersession
mechanism.

**`mode = "findings-v2"`** (the plan's §3b) keeps all of that and changes what is
selected, after the first live comparison showed the v1 window freezing on old weak
candidates: the trivial baseline is never a cross-branch card, the strongest candidate
outside the lineage is chosen before the topic matches, other children of this job's
parents get two slots of their own, topic matches are ordered newest-first, and at least
two cross-branch cards survive the byte budget (ancestors are dropped for them). Cards
are schema `finding-card/2`.

```toml
[memory]
mode  = "findings-v2"
knobs = "out/memory_config.json"   # optional; relative to the candidate dir
```

**`knobs`** names a small JSON object the candidate's own code writes — whatever it
configured for this attempt. Each card then carries a `knobs` field (top-level scalars
only: at most 32 sorted keys, values ≤ 64 bytes, redacted like any other worker text;
`null` and a `knobs file missing` caveat when the file is absent or unreadable), and
every job card ends with a **knob ledger**: one line per settled non-baseline candidate,
newest first, with its search score, its Δ to its first parent and the keys whose value
differs from that parent's file, plus a `card not shown` marker where the snapshot has
no card for it. It is bounded at 2 KiB on top of the card budget and dropped
oldest-first, because its point is that a worker can see *that* a knob was already moved
in this direction even when the card that moved it did not fit. Nothing in it is parsed
from prose; a campaign whose workers write no such file simply gets a ledger of ids,
scores and deltas. The path is frozen into `population.json` with the rest of the
policy, and `knobs` under `findings-v1` is refused — v1 is frozen so its jobs stay
reproducible byte for byte.

Passing the acceptance suite shows that the plumbing is correct, not that the memory
is useful; the comparison that would show that is `docs/finding-cards-plan.md` §7.
`scripts/mem_replay_selector.py <project>` replays a finished campaign's dispatches
under both policies and reports cross-branch coverage, cards shown to nobody and
whether a repeated idea was visible to the job that repeated it — read-only, no LLM.

## The read-only page

`tools/lab serve` renders the campaign on `http://<host>:8791/`: header and usage
line, the population newest first, the timeline, one page per candidate with its
summary, and REPORT.md once written. It re-reads the files on every request, writes
nothing, answers only GET, and redacts displayed text with the feed's rules. There is
no stop button by design; stopping stays `tools/lab campaign stop`. It has no
authentication, so bind it to a LAN interface, never a public one. To keep it up
across sessions, run it under a watcher with a long budget:

```sh
tools/lab watch start --op serve --budget-min 100000 -- tools/lab serve
```
