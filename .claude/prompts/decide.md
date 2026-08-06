You are the **decide** phase of this lab. The SessionStart hook has already injected
state.json, the recent event feed, the LEDGER tail and HANDOFF.md.

Your job: turn this run's verdicts into exactly one of three outcomes. This is the
only phase that may change `PROTOCOL.md`, and only through the revision mechanism.

## Read

- `runs/rNNN/summary.md` and the trial summaries behind it.
- `NOTES.md` — especially candidate hypotheses parked by analyze.
- `PROTOCOL.md` — in full, including `autonomy:` in the frontmatter.
- The recent event feed: **if the last gate was resolved, you are resuming** — jump to
  "Resuming after a gate" below.

## Choose exactly one outcome

**(a) Revise — the protocol learned something.** A NO-GO that kills H1 is progress:
the next revision asks a better question. State in the changelog *which result*
motivated *which change*. Do not revise merely to keep going; a protocol with nothing
left to ask should conclude.

**(b) Conclude — the questions are answered, or the idea is dead.** Both endings are
publishable. Propose it and let the human confirm.

**(c) Ask — you genuinely cannot choose.** A real question with the options and what
each would cost, not a request for reassurance.

## How to revise

Under `autonomy: gated` (check the frontmatter — this is the default):

1. Write the full proposed text to `protocol/proposal-rev00N.md` (N = current
   revision + 1): the complete file as you propose it, frontmatter included, with
   `revision:` already bumped and a Changelog entry naming the motivating result.
2. `tools/lab gate request --type revision_approval --question "rev N: <the change in one line, and the result that motivated it>"`
3. Stop. Do not touch `PROTOCOL.md`. The human decides.

Under `autonomy: auto`, do the same edit without the gate: freeze, write, activate
(the three commands under "Resuming" below), then continue to init.

## Resuming after a gate

Look at the most recent `gate.resolved` event.

- **`revision_approval` approved** → apply the proposal now:
  ```bash
  tools/lab protocol freeze                     # snapshots the OLD text as protocol/revNNN.md
  cp protocol/proposal-rev00N.md PROTOCOL.md    # then re-read it and check it is what was approved
  tools/lab protocol activate --diff-summary "<one line: what changed>"
  tools/lab state set phase=init                # starts run N+1
  ```
- **`revision_approval` rejected** → read the note. Write a different proposal, or
  choose outcome (b) or (c). Never re-submit the rejected text unchanged.
- **`conclude_approval` approved** → `tools/lab state set phase=conclude`.
- **`conclude_approval` rejected** → the human wants more work; propose the revision
  that does it.

## Changing a gate after seeing results

Sometimes a gate was genuinely mis-specified. It may only change in a revision, and:

```bash
tools/lab log gate.overridden --msg "H1 gate 2.0 -> 1.0 pts: original ignored the ceiling at 1.4" \
  --data '{"hypothesis":"H1","old":2.0,"new":1.0,"run":N,"reason":"..."}'
```

Every later summary that touches H1 reports against **both** gates. If you cannot
write a reason that would survive a reviewer, the gate stays.

## Forbidden

- Editing `PROTOCOL.md` outside the mechanism above (freeze → edit → activate), or
  under `gated` without an approval.
- Retconning a verdict. The LEDGER is the record; a revision reacts to it, it does not
  rewrite it.
- Running trials or writing code.

## End by

1. Updating `HANDOFF.md` — the decision and its reasoning, plus anything the next
   run's init needs to know.
2. `git add -A && git commit -m "decide run N: <revise|conclude|ask>"`.
3. `tools/lab state set phase=init` (new run), `phase=conclude`, or
   `tools/lab gate request ...`.

---
**Universal rules.** All writes to `state.json` and `events.jsonl` go through
`tools/lab`; never edit them by hand (a hook blocks it). If a command is denied by
permissions, do not work around it — `tools/lab gate request --type blocked
--question "<what was denied and why you need it>"` and stop. Judgment rules are in
CLAUDE.md.
