# Starting a campaign

What a new project needs before `lab run` works. Learned on the first live run (M1,
MNIST, 2026-09-09). The design is in [aira2-loop-design.md](aira2-loop-design.md), the
status in [../NEXT.md](../NEXT.md).

1. **A project directory** with the template's `tools/`, `.claude/`, `templates/`,
   `CLAUDE.md` and `.lab-redact` copied in, and `git init`, because candidate provenance
   records the commit. Ignore `.lab/`, `.venv/`, raw data and weights in `.gitignore`.
2. **`campaign.toml`** from `templates/campaign.toml`, plus the task statement, the
   evaluator and the baseline command. The evaluator is stdlib-only Python:
   `score.py <predictions> <labels_dir>` printing `{"score": x, "n": k}`.
   `tools/lab campaign check` validates the file.
3. **Data splits.** `data/train` is readable; the `data/search` and `data/final` inputs
   sit in the repo, their labels outside it under `$LAB_PRIVATE/<campaign>/…`. The final
   split is read once, at the end. Export `LAB_PRIVATE` only in the shell that runs
   `lab run`; workers never receive it.
4. **A Python environment for candidates.** The worker's `code/run.sh` must name an
   interpreter that has what the task needs, torch, numpy and so on. The system `python3`
   is used only by `lab` itself and the evaluator. Say the path in the task statement.
5. **Trust the project directory once** for Claude Code, or headless sessions ignore the
   project's `permissions.allow`; the hooks still run. Either open `claude` interactively
   there once and accept the trust dialog, or set
   `projects["<abs path>"].hasTrustDialogAccepted: true` in `~/.claude.json`. Pi workers
   need no trust: the wrapper passes `--no-approve` and loads only the lab's extension.
6. **Subscription login only**, for Claude workers. `claude auth status` must say
   `loggedIn: true`, with no `ANTHROPIC_API_KEY` or endpoint override in the environment.
   `lab run` and `lab-worker` refuse to start otherwise. Pi workers instead need their
   provider's endpoint to serve the model, see "Pi workers" below.
7. Optional but recommended: the **`labeval` user** ([labeval.md](labeval.md)), so hidden
   labels are hidden by the OS rather than by convention. REPORT.md states which.
8. **Refreshing tooling** in an existing project: `scripts/sync-project.sh <project>`
   copies `tools/`, `.claude/`, `templates/`, `CLAUDE.md` and `.lab-redact` from this repo
   and touches nothing else. Never during a run.
9. **Two GPUs**: list both in `resources.gpus` and set `max_parallel_jobs = 2`.
   `min_free_vram_mb` skips a GPU that something else is using, checked with `nvidia-smi`
   before every lease and noted in the feed once per episode.

Then:

```sh
export LAB_PRIVATE=~/.local/share/labloop-private
tools/lab campaign check
tools/lab run campaign.toml --poll-sec 10        # or under: lab watch start --op campaign --budget-min N -- tools/lab run …
tools/lab campaign status                        # live view from another shell; --once one frame, --plain text
tools/lab serve                                  # read-only page for a phone on the LAN (port 8791)
tools/lab campaign stop [--now]                  # stop dispatching (and kill running jobs)
```

## Selection and worker models

**`[selection] initial_drafts`** (default 1) is how many independent first approaches the
loop dispatches after the baseline, before any `improve` or `crossover` is drawn. With
the default, the whole search hangs off one draft's luck: if that draft picks a weak
approach, every later candidate is a tweak of it. `selection.draft_p` is the other and
weaker remedy, since it only sprinkles fresh drafts later. Three drafts buy three
independent starts and cost two improve slots out of the campaign's candidate budget, so
raise it on a task where the approach matters more than the tuning. Drafts still never
outnumber `max_parallel_jobs` at once, and a draft that failed or was deferred counts as
dispatched; its re-dispatch counts with it, not again.

**`[resources.worker_model_by_operator]`** names a model per operator, overriding
`worker_model` for that operator only:

```toml
[resources.worker_model_by_operator]
draft = "claude-opus-5"          # keys: draft | improve | crossover | debug (never baseline)
```

The approach choice happens in `draft`; `improve` executes one stated change on code it
inherits. So the expensive model can be spent where it decides the search's ceiling and
the cheap one on the many jobs that follow, which also makes the Max window go further.
An unknown operator key is a `campaign.toml` error, never a silent fall back to the
default. `config.json` records which key was used (`agent.requested_source`), REPORT.md's
usage section lists the requested models, and `lab campaign check` prints them.

## Pi workers (local and hosted open models)

The worker model id names the harness. `claude-…` is Claude Code through
`tools/lab-worker`. Pi's own `provider/model[:thinking]` form runs through
`tools/lab-worker-pi`, which `lab-worker` hands over to at the top, so `[worker] command`
stays `tools/lab-worker` and `worker_model_by_operator` can mix harnesses: a Claude
draft, local improves. Pi is configured the way Pi documents it, never by labloop.
`~/.pi/agent/models.json` (or `PI_CODING_AGENT_DIR`) names the providers, so a fork can
point workers at any OpenAI-compatible server or hosted API.

1. **A model server, started outside the campaign.** `scripts/llm-server.sh start
   gpt-oss-20b 0 32768` runs llama.cpp's CUDA image under docker with one GGUF, pinned to
   GPU 0, bound to `127.0.0.1:8083`, reporting the alias as its model id. It is a service
   for every client on the host, not a job: no `lab watch`, and `lab run` never starts or
   stops it. List the candidates' GPU in `resources.gpus` and leave the server's out.
2. **A provider in Pi's models.json**, with `baseUrl`, `api = "openai-completions"`, a
   placeholder `apiKey`, `compat.supportsDeveloperRole = false` for llama.cpp, and one
   entry per alias the server may run. `pi --list-models` shows them.
3. **`worker_model = "local/gpt-oss-20b"`** in campaign.toml. `lab campaign check` prints
   the backend per model and asks the endpoint. `lab run` refuses to start when the
   endpoint is down or serves another id (`refusing to start: Pi model …`). A provider
   without a `baseUrl`, a built-in one, is checked with `pi auth check` instead.
4. **The context window is set in two places and recorded, never in campaign.toml.** The
   server's `-c`, the start script's third argument, default 32768, is the real window.
   `contextWindow` on the model in Pi's models.json is what Pi compacts against, and it
   must not exceed the real one, or Pi sends a request the server refuses; the first probe
   lost two sessions that way. The preflight reads the served window from llama.cpp's
   `/props`, records both numbers with the population and in REPORT.md (`context declared
   32768, served 32768`), and refuses to start when declared exceeds served. A hosted API
   has only the declared number, recorded as such. A run at 32k and one at 128k on the
   same model id are different experiments, and the report says which.

What a Pi session gets that `claude -p` has from flags and hooks comes entirely from
`tools/pi/lab-worker.js`, loaded explicitly with `-e` and nothing else discovered
(`--no-extensions --no-skills --no-prompt-templates --no-themes --no-approve`): the turn
budget (`worker_max_turns`, a countdown in the last five tool results, after which every
tool call is refused and the run ends), the evidence guard (`.claude/hooks/guard.sh`, fed
the same JSON Claude Code's hook gets, for bash, write and edit), a refusal to read label
paths, and a bash timeout inside the remaining job budget. Pi has no background execution
of its own, and `lab_process.py` contains detached descendants as it does for Claude.

Provenance: `session.stream.jsonl`, Pi's event stream, and `session-pi/*.jsonl`, Pi's
session file, sit in the candidate dir. `session.json` is built from the stream in the
`claude -p` shape: turns, cost as Pi computes it from its models.json prices,
`modelUsage` keyed `provider/model`, the last assistant text, `error`, `stop_reason`,
`turns_capped`, `session_started`. `config.json` records `agent.backend`. Pi exits 0 even
when the model call failed, so the wrapper reads the stream: no completed model turn is
exit 3, a failed candidate with one debug retry; a completed session without predictions
is exit 2, invalid. A provider's rate-limit message is matched by the same regex, on
`[pi stderr]` lines, and defers the job like a spent Max window. `lab usage` reads the Pi
session file for tokens.

What to expect from an open model: slower sessions, since a 27B Q4 on a 24 GB card
generates tens of tokens per second and the card is long; more invalid candidates; and
tool calling that depends on the chat template llama.cpp renders (`--jinja`). That is
data. Run the smallest campaign first: [pi-probe-20260915.md](pi-probe-20260915.md)
records the first one.

## Supervising the campaign controller

Use a wall-clock-only outer watcher for `lab run`, for example:

```sh
tools/lab watch start --op campaign --budget-min 60 -- tools/lab run campaign.toml --poll-sec 10
```

Do **not** add an outer `--stall-min` to this command with the current generic watcher.
The controller quietly updates state files while candidate watchers and workers run in
separate sessions with separate logs, so its own log and session CPU can look idle during
useful training. A ten-minute outer stall setting killed a progressing sustained smoke on
2026-09-12. The absolute outer budget remains the enforcer, and candidate watchers retain
their own wall and stall checks. A future campaign-aware stall check must measure actual
campaign progress, not just the controller log. Set the outer wall cap with room for
final execution and scoring; an outer timeout is an interruption, not a completed
campaign.

## Worker lifetime (Linux)

The default `tools/lab-worker` disables Claude Code's explicit and automatic background
tasks with `CLAUDE_CODE_DISABLE_BACKGROUND_TASKS=1`. This control and
`BASH_DEFAULT_TIMEOUT_MS` / `BASH_MAX_TIMEOUT_MS` were verified in the locally installed
Claude Code **2.1.269** binary, including the Bash auto-background branch, not assumed to
be CLI flags. Both Bash timeouts are set to the job wall-clock cap; a worker should
request a smaller timeout within its remaining budget. The outer watcher remains the
deadline authority. Check these controls when upgrading the CLI.

Workers run `code/run.sh` synchronously, wait for its exit, check the exit code and the
predictions, then write `summary.md` before ending the session. No `run_in_background`,
shell `&`, `nohup`, `setsid` or nested `lab watch`: the candidate already has its watcher.
The Bash hook rejects common detach attempts at simple command positions, not mentions in
quoted prose, and skips conventional heredoc payloads. It is a shallow heuristic, not a
full shell parser: wrappers, complex quoting and delimiters, and commands embedded in
scripts can evade it. CLI background controls and owned process containment are the
lifetime enforcement, not perfect shell detection. `lab watch start/_run` also refuses
worker invocations. Operator watchers remain available.

Linux subreapers contain the CLI lifetime and each candidate watch, including baseline and
final execution. On CLI return, owned live descendants are terminated and reaped **before**
the wrapper checks predictions: pending work makes the candidate invalid even if the CLI
returned success. There is no grace period to await missing predictions or to salvage late
outputs. On job completion or watcher kill, detached and double-forked descendants are
likewise drained before the watcher publishes a terminal entry, releases its resource
lease, or permits settlement. Cleanup uses pidfds with direct-child ownership checks,
never broad process-name or UID kills. TERM has one second, then KILL and reaping have
five seconds. If the kernel cannot kill a process, the watcher retains the lease, records
`cleanup_error`, and retries visibly.

This is lifecycle containment, **not OS security isolation**. Hooks are guardrails, a
same-user adversarial process can bypass them, and killing the watcher itself from
outside (especially with SIGKILL), host failure, or external service delegation is
outside this guarantee. Kernel I/O can delay teardown indefinitely, so do not claim
compute has stopped while the watcher is running with `cleanup_error`. Linux `/proc`,
`prctl` and Python/kernel pidfd support are required; unsupported systems fail before
candidate execution. Do not update tools or resume the tainted historical control for
comparison: use a fresh campaign identity and freshly trained candidates after a bounded
smoke test.

## The usage governor (the Claude Max window)

Max is a rolling 5-hour allowance, not money, and `lab run` treats it like a GPU: a
resource with a budget, enforced by not dispatching. Configure it in `[usage]`:

```toml
[usage]
window_budget = 12.0   # list-price USD per 5 h window the plan tolerates; see below
soft = 0.70            # of window_budget: dispatch nothing new, status waiting_usage
hard = 0.90            # also kill running sessions (a session cannot be paused);
                       # their jobs are deferred and come back when the window has room
```

Two signals feed it. The **estimate** sums `total_cost_usd` of every worker session that
ended inside the window, the list-price figure `claude -p` reports for a subscription
session, the subscription itself being prepaid, plus one reservation per running session,
and compares it with `window_budget`. The **fact** is a usage-limit message in a session's
result ("You've hit your limit · resets 3pm"): that job is marked `deferred`, never
`failed`, dispatch is blocked until the stated reset or `usage.retry` later, and the job
is re-dispatched as a new candidate whose `config.json` says `redispatch_of`.
`lab campaign status` and `lab campaign usage` show the governor's view. REPORT.md reports
the peak window estimate, the pauses, time waiting as a share of wall clock (M3's kill
criterion is 20 %), and the deferrals.

**Calibrating `window_budget`.** Anthropic publishes no token figure for the window, and
headless Claude Code has no non-interactive `/usage`. So the budget is empirical: run a
short campaign, read `lab campaign usage` (spend per session, sessions per window) next
to `/usage` in an interactive session, and set `window_budget` to the list-price spend at
which the plan sat near 100 %. Without a `window_budget` the loop only reacts to
rate-limit messages and cannot pace itself, and `lab campaign check` warns.

**The first real rate limit.** The headless CLI's output on a spent window is not formally
documented. The default `usage.rate_limit_regex` matches the interactive wording and a 429.
After the first unattended run, open the deferred candidate's `session.json` and
`session.stderr`, confirm they matched, and tighten the regex in `campaign.toml` if the
wording differs.

**A session that keeps running past the message.** `lab run` does not rely on the CLI
exiting. `lab-worker` echoes the CLI's stderr, line by line under a `[claude stderr]`
prefix, into the job's watcher log, and every worker job is launched with a kill pattern
that is the rate-limit regex scoped to that prefix. A CLI that prints the message and then
waits or retries is killed by the watcher within one poll, 15 s by default, the job is
settled as `deferred` with the watcher named in its reason, and it is re-dispatched after
the stated reset. Nothing a training run prints can match the pattern, because only the
CLI's stderr carries the prefix: in `-p` mode a tool's output never passes through it. A
message with no trailing newline is enforced just the same, because the echo is unbuffered
and the watcher searches the unterminated tail of its log on every poll. A transient
message that the CLI would have retried through is deferred too: one re-dispatch, never a
failed candidate. When you tighten `usage.rate_limit_regex`, remember it is embedded after
that prefix, so use scoped flags such as `(?i:…)`, not `^` or `$`. `lab campaign check`
compiles the combination.

## Finding cards (opt-in memory)

By default a worker sees the first-parent lineage of clipped summaries. `[memory] mode =
"findings-v1"` in `campaign.toml`, set **before the first `lab run`**, replaces that with
finding cards. The policy and its limits are frozen into `population.json` when the
campaign starts, so a tooling update cannot change a running campaign's memory, and a
campaign started without the key stays legacy for its whole life; `lab run` warns if the
file asks for cards under a legacy population. The design is
[finding-cards-plan.md](finding-cards-plan.md).

**What the worker is asked to write.** Its job card requests a `## Finding` section at the
top of `summary.md`: `Change`, `Hypothesis`, `Local observation`, `Interpretation`,
`Limitations` and `Topics`, each exactly one physical line, each exactly once, at most five
topic slugs. A worker does not know the hidden search score and never states one; local
numbers stay its own. The parser is mechanical: a missing, duplicated or malformed field
costs the candidate nothing and produces a facts-only card with the reasons. Nothing is
inferred from prose and `summary.md` is never modified.

**What the lab publishes.** `candidates/cNNNN/finding.json`, written once by `lab run`
after the candidate settles, completed, failed, killed, invalid or deferred alike, and
never overwritten. It is built only from `fitness.json`'s **search** record,
`population.json`, `config.json` and the parsed Finding section: identity, execution
outcome, the search score with n and evaluator fingerprint, the raw delta to each parent,
seed and model provenance, the worker's six lines marked worker-reported, the caveats and
the source digests. A number in worker prose is never promoted into a measured field, and
nothing from the final split ever enters a card.

**What the next worker sees.** At dispatch, `lab run` selects up to 8 cards and 12 KiB of
rendered context, deterministically and without touching the scheduler's RNG: the direct
parents, up to two nearest ancestors traversed across both sides of a crossover, then
other branches (a same-topic run that did not beat its strongest parent, other topic
matches, the strongest off-lineage candidate, a recent execution problem, then recent
findings). Selected ids, reasons, card digests and the rendered text are stored whole in
`job.json`, so `lab job card` prints byte for byte what the worker saw, however many
candidates have ended since.

A `finding.json` that already exists when a candidate settles was written by the worker,
not by `lab`: it is renamed `finding.worker.json` and kept as evidence, the attempt is
recorded `invalid` with that reason, and the real card is published from the sources as
usual. On every tick each existing card must be valid, agree with its sources and equal
the card `lab` rebuilds from them, so a restart from a shell whose `.lab-redact` secrets
differ can stop on a card whose redaction differs.

**When `lab run` stops with a card error.** A card that fails validation or disagrees with
its sources blocks dispatch as a tooling error, naming the card and the failed check.
Nothing is repaired, overwritten or superseded automatically, and the candidate is not
marked failed: inspect the candidate dir and decide. v1 has no supersession mechanism.

**`mode = "findings-v2"`** (the plan's §3b) keeps all of that and changes what is selected,
after the first live comparison showed the v1 window freezing on old weak candidates. The
trivial baseline is never a cross-branch card, the strongest candidate outside the lineage
is chosen before the topic matches, other children of this job's parents get two slots of
their own, topic matches are ordered newest-first, and at least two cross-branch cards
survive the byte budget, ancestors being dropped for them. Cards are schema
`finding-card/2`.

```toml
[memory]
mode  = "findings-v2"
knobs = "out/memory_config.json"   # optional; relative to the candidate dir
```

**`knobs`** names a small JSON object the candidate's own code writes, whatever it
configured for this attempt. Each card then carries a `knobs` field: top-level scalars
only, at most 32 sorted keys, values of at most 64 bytes, redacted like any other worker
text, and `null` with a `knobs file missing` caveat when the file is absent or unreadable.
Every job card ends with a **knob ledger**: one line per settled non-baseline candidate,
newest first, with its search score, its Δ to its first parent and the keys whose value
differs from that parent's file, plus a `card not shown` marker where the snapshot has no
card for it. It is bounded at 2 KiB on top of the card budget and dropped oldest-first,
because its point is that a worker can see *that* a knob was already moved in this
direction even when the card that moved it did not fit. Nothing in it is parsed from
prose, and a campaign whose workers write no such file simply gets a ledger of ids, scores
and deltas. The path is frozen into `population.json` with the rest of the policy, and
`knobs` under `findings-v1` is refused, because v1 is frozen so its jobs stay reproducible
byte for byte.

**`mode = "findings-v3"`** (the plan's §3c, 2026-09-15) keeps v2's selector, caps and card
schema and replaces the ledger with a **per-knob index**: one line per knob key any settled
non-baseline candidate configured, with each value tried and the ids that tried it
(`weight_decay: 0.01 (c0009, c0014) · not in the file of 16 other(s)`), so "has this knob
been varied?" is one line and no candidate is ever dropped for age. Outcome keys (`steps`,
`final_loss`, `trainable_params`, `wall_seconds`, `seed`, `holdout_*` …) never enter the
index; under v3 each card instead ends with a measured line listing them from the
candidate's own file. List-valued knobs are rendered, not dropped. Under the same 2 KiB
bound the oldest values of a knob are elided, never a knob or an id of a value still shown,
and the elision is written into the row. The job card's population table lists parents
beside scores for every policy since the same day. `knobs` is required under v3.

Passing the acceptance suite shows that the plumbing is correct, not that the memory is
useful. The comparison that would show that is `finding-cards-plan.md` §7.
`scripts/mem_replay_selector.py <project>` replays a finished campaign's dispatches under
both policies and reports cross-branch coverage, cards shown to nobody, and whether a
repeated idea was visible to the job that repeated it. It is read-only, with no LLM.

## The read-only page

`tools/lab serve` renders the campaign on `http://<host>:8791/`: the header and usage
line, the population newest first, the timeline, one page per candidate with its summary,
and REPORT.md once written. It re-reads the files on every request, writes nothing,
answers only GET, and redacts displayed text with the feed's rules. There is no stop
button by design; stopping stays `tools/lab campaign stop`. It has no authentication, so
bind it to a LAN interface, never a public one. To keep it up across sessions, run it
under a watcher with a long budget:

```sh
tools/lab watch start --op serve --budget-min 100000 -- tools/lab serve
```
