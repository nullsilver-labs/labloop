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
  time + hardware + versions + agent model), append-only `results.jsonl`, `summary.md`
  when it ends — **including when it was killed**, saying so and why.
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

Launch with Bash `run_in_background`; you are woken when a process exits. While any
trial is live, also `ScheduleWakeup` at `min(55 min, time to the nearest budget
deadline)` — that wake enforces budgets and kill criteria. Kill what is over, write its
summary, close it with `lab trial done --killed`.
