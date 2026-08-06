# <exp_id> — trial <trial_id>

- **Date / duration**: …
- **Spec**: `runs/rNNN/specs/expNN_<slug>.md`
- **Status**: completed | killed (why) | crashed (why, and whether the partial
  results are usable) | invalidated (what bug, and where the rerun is)
- **Verdict vs the pre-registered gate**: GO | NO-GO | INCONCLUSIVE | n/a (pilot)

## Headline table

| arm | metric | value | baseline | delta |
|---|---|---|---|---|

## Reading

Two to five sentences: what the numbers say, whether anything smells like a bug or
leakage, what this changes. If the result looks too good, say what you checked.

## Caveats

Everything that limits the conclusion: sample size, single seed, early stop, any
drift from the spec. List every deviation.
