# The lab

One repo, one research project, rendered live on nullsilver.com. A fixed state machine
of phases runs it, each phase a fresh session with its own prompt in
`.claude/prompts/`. Procedure lives there and in the hooks — **this file is the
judgment**, and it applies in every phase.

## What you are for

- **Honesty over optimism.** Report what happened, including bugs that invalidated a
  trial. An invalidated trial gets a summary saying so and a rerun — never silence.
  A tie is a tie. A NO-GO is a result, not a setback.
- **Baselines are mandatory.** No headline number without its trivial baseline (copy /
  majority / random / zero-shot, per the spec). If a result looks too good, the first
  hypothesis is a bug or leakage — check, and write down what you checked.
- **Verdicts read against pre-registered gates only** — the number frozen in the spec
  before the trial ran, not the one that now seems fairer. A gate may change only in a
  decide-phase revision, with `lab log gate.overridden`, and every summary afterwards
  reports against **both** the old and new gate.
- **Spend compute like money.** The smallest experiment that can kill an idea, first;
  downscale, then scale only what survived. Seed everything and log the seed;
  fingerprint caches with what produced them so a stale one can't be reused silently.

## The machine

`init → build → pilot → execute → analyze → decide → (init | conclude)`. `lab`
validates every transition; illegal jumps are rejected, so if you are stuck the answer
is a gate, not a workaround.

- **`state.json` and `events.jsonl` have exactly one writer: `tools/lab`.** Never edit
  them by hand — a hook blocks it. `lab log`, `lab state set`, `lab trial`, `lab gate`.
  `FORMAT.json` is generated too: `lab format sync`, never by hand.
- **The event feed is public in realtime.** `msg` is one line, ≤ 140 chars, and reads
  like a person wrote it. Secrets are redacted mechanically, but don't test that.
  Heartbeats and "still running" are not events.
- **Evidence is immutable.** Never delete or overwrite a trial dir, a frozen
  `protocol/rev*.md`, or a LEDGER row — failed and killed trials are data. If a trial
  is misleading, say so in its `summary.md` and in the LEDGER.
- Every trial dir holds `config.json` (config + seed + git commit + command + start
  time + hardware + versions + agent models), append-only `results.jsonl`, and a
  `summary.md` written when it ends — **including when killed**, saying so and why.
- **`PROTOCOL.md` prose is the human's.** It changes only in the decide phase, only
  through freeze → edit → `lab protocol activate`, and under `autonomy: gated` only
  after an approved gate.

## When to stop and ask

`tools/lab gate request --type <t> --question "..."` — and then actually stop — for:
a budget in `PROTOCOL.md` that would be exceeded, a direction the protocol doesn't
cover, anything irreversible outside the repo, anything that spends money, and any
command denied by permissions (work around it and the lab is lying about what it did).
Batch everything else into HANDOFF.md's "For the human". Every session ends by
overwriting `HANDOFF.md` — the Stop hook will not let you leave without it.

## Long runs

Phase sessions are **headless one-shots** (`claude -p`): the process exits the moment
your turn ends, and everything it spawned dies with it — except work detached under
`lab watch`. `ScheduleWakeup` will never fire for you; do not call it. The rule:
**never leave running work without an enforcer.** There are exactly two:

- **You, in the foreground** — for work that finishes within this session (minutes,
  not hours). Launch with Bash `run_in_background` so the console tees to a log, then
  wait with bounded blocking checks, each within the Bash timeout, e.g.
  `timeout 540 tail -f <console log> | grep -m1 -E '(done|error|Traceback|OOM)'`,
  repeated until the process exits, enforcing budgets and kill criteria at every
  check. Never end a turn while unwatched work runs — "I'll check when I'm woken" is
  how one project's pilot lost the same 9 GB download twice.
- **A `lab watch` watcher** — for work that outlives the session: a training run, a
  model download. `lab watch start (--trial DIR | --op NAME) [--budget-min N]
  [--stall-min N] [--kill-regex RE] -- <command>` detaches it under a mechanical
  supervisor that heartbeats and kills on wall-clock, stall, or pattern; a killed
  trial gets a facts-only summary stub and `lab trial done --killed` on the spot,
  so the LEDGER never waits for a session to come back. With every live process
  under a watcher you may end your turn: the driver (loop.sh or the orchestrator)
  waits in bash for free and launches a session when a watch needs judgment or
  paperwork — in execute, the `supervise.md` visit; elsewhere, the phase's own
  prompt resumed.

A bare `nohup`/`setsid` remains forbidden — an orphan without a watcher has no one
enforcing its budget. Kills end with a summary and `lab trial done --killed`, however
they happen; watchers write the mechanical half, sessions the judgment half.

(The attended orchestrator session is the exception: it is persistent, so for *it*
`run_in_background` + `ScheduleWakeup` is correct — see
`.claude/commands/orchestrate.md`. That pattern is the orchestrator's, never a
phase's.)
