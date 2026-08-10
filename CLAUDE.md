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
your turn ends, and everything it spawned dies with it — background tasks, monitors,
pending wakeups. `ScheduleWakeup` will never fire for you; do not call it. Never end a
turn while a trial, download, or server you still need is running — "I'll check when
I'm woken" is how one project's pilot lost the same 9 GB download twice.

Instead: launch with Bash `run_in_background` so the console tees to a log, then wait
in the **foreground** — bounded blocking checks, each within the Bash timeout, e.g.
`timeout 540 tail -f <console log> | grep -m1 -E '(done|error|Traceback|OOM)'`, then
inspect `results.jsonl` — repeated until the process exits. Enforce budget deadlines
and kill criteria at every check: kill what is over, write its summary, close it with
`lab trial done --killed`. Work that cannot finish within one session is a gate, not a
`nohup` — a detached orphan has no one enforcing its budget.

(The attended orchestrator session is the exception: it is persistent, so for *it*
`run_in_background` + `ScheduleWakeup` is correct — see
`.claude/commands/orchestrate.md`. That pattern is the orchestrator's, never a
phase's.)
