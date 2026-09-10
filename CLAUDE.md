# The lab

> **Campaign workers** (`LAB_ROLE=worker`, launched by `lab run`): your job card is the
> whole brief. You edit only your candidate dir, you never read labels, you stop when
> `code/run.sh` has produced `out/predictions-search.json` and `summary.md` exists.
> The rest of this file is for operator sessions and for the humans who read them.

One repo, one research campaign, rendered live on nullsilver.com. `lab run` runs the
search: a population of candidates, a mechanical scheduler, one short headless session
per job, fitness from a hidden split, a final split read once. Procedure lives in
`tools/lab`, `tools/lab_campaign.py` and the hooks — **this file is the judgment**.

## What you are for

- **Honesty over optimism.** A candidate's `summary.md` says what changed, what the
  hypothesis was, and what happened — including a bug that invalidated it. An invalid
  candidate stays in the population with its reason; it is never silently replaced.
  A tie is a tie. A claim that reads `not_supported` is a result, not a setback.
- **Baselines are mandatory.** Candidate `c0000` is always the trivial baseline named
  in `campaign.toml`; no headline number is read without it. If a result looks too
  good, the first hypothesis is a bug or leakage: a child that loaded its parent's
  weights, a split that overlaps, a worker that found the labels. Check, and write
  down what you checked.
- **Claims read against pre-fixed thresholds only.** `success_threshold` is fixed in
  `campaign.toml` before the run and cannot change under a running campaign: a changed
  campaign file is a new campaign. Search fitness is optimistic by construction; only
  the one read of the final split supports a claim.
- **Spend compute like money.** The smallest campaign that can kill an idea, first:
  a handful of candidates on a sub-hour task before a 24-hour search. Seed everything
  and record the seed; a child never inherits trained weights, so it cannot score its
  parent twice.
- **Spend the usage window like a GPU.** The Claude Max window is the second scarce
  resource. `[usage]` in `campaign.toml` budgets it; a job pushed out by the window is
  deferred and re-dispatched, never failed. Sessions are short by construction: one
  job, one turn budget, no handoff document.
- **Spend context like compute.** A worker reads its job card, the parent's summary and
  the lineage, not the whole population's code. An operator reading results delegates
  bulk reading — logs, session transcripts, candidate code — and keeps conclusions.

## The machine

`campaign.toml → lab run → [select parent → worker → evaluate → add to population] →
REPORT.md`. There are no phases, gates, approvals or handoffs inside the loop. The
human writes `campaign.toml`, starts `lab run` under `lab watch`, and can stop it with
`lab campaign stop`. Waiting on the usage window is a campaign status, not an error.

- **`population.json`, `LEDGER.md` and `events.jsonl` have exactly one writer:
  `tools/lab`.** Never edit them by hand — a hook blocks it. `FORMAT.json` is
  generated: `lab format sync`, never by hand.
- **The event feed is public in realtime.** `msg` is one line, ≤ 140 chars, and reads
  like a person wrote it. Secrets are redacted mechanically, but don't test that.
  Heartbeats and "still running" are not events.
- **Evidence is immutable.** Never delete or overwrite a candidate dir, a LEDGER row
  or `REPORT.md` — failed, killed, invalid and deferred candidates are data. If a
  candidate is misleading, say so in the next candidate's summary and in the report.
- Every candidate dir holds `config.json` (operator, parents, seed, git commit,
  command, hardware, versions, requested and served models), `job.json`, the
  candidate's own `code/`, `summary.md` written when it ends — **including when
  killed**, saying so and why — and `fitness.json` written only by `lab eval`.
- **Labels are hidden.** `lab eval` is the only reader of the search and final
  splits; with the `labeval` user they are hidden by the OS, otherwise by convention,
  and `REPORT.md` says which.

## Operator sessions

Anything not launched by `lab run` is an operator session: a human working in the
repo, or an agent the human is driving. It records its usage under `.lab/sessions/`,
emits no events, and never touches a running campaign's files. Reading results,
working on the tooling, preparing the next campaign and answering questions are all
fine. To end a campaign by hand: `tools/lab campaign stop [--now]`.

## Long runs

**Never leave running work without an enforcer.** `lab watch start --op NAME
--budget-min N [--stall-min N] [--kill-regex RE] -- <command>` detaches work under a
mechanical supervisor that heartbeats and kills on wall-clock, stall or pattern.
`lab run` launches every job this way and settles a killed job mechanically, so the
LEDGER never waits for a session to come back. Run the campaign itself under a watcher
too (`--op campaign`), so it has a budget of its own. A bare `nohup`/`setsid` is
forbidden — an orphan without a watcher has no one enforcing its budget.

Work that finishes within an operator session (a data prep, a reference run) runs in
the foreground with a timeout, or under a watcher; it is never backgrounded and
forgotten.
