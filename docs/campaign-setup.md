# Starting a campaign

What a new project needs before `lab run` works. Learned on the first live run
(M1, MNIST, 2026-09-09); see NEXT.md for the design.

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
tools/lab campaign stop [--now]                  # stop dispatching (and kill running jobs)
```

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
