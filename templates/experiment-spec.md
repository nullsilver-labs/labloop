# expNN — <title>

- **Run**: rNNN
- **Hypothesis under test**: H1 (from PROTOCOL.md rev N)
- **Question**: one sentence — what will we know after this runs that we don't now?

## Design

- **Setup**: model / data / procedure, in enough detail to reimplement from this file.
- **Arms**: every condition, *including* the trivial baseline (copy / majority /
  random / zero-shot). A headline arm without its baseline is not a valid design.
- **Primary metric**: exactly one, precisely defined — dataset split, aggregation,
  n. This is the only metric the verdict is read against.
- **Secondary metrics**: observed, never gated on.

## Pre-registration — frozen once the first trial launches

- **GO gate**: the number, copied from `plan.json`. E.g. "arm A − baseline B ≥ 2.0
  accuracy points on the val split, n ≥ 500".
- **Kill criteria**: what stops a trial early — divergence, no signal by step N,
  wall-clock over budget, NaNs.
- **Budget**: max wall-clock per trial, hardware, how many trials.
- **Prediction**: what you expect, with a confidence — e.g. "NO-GO, 65%". Log it as a
  `prediction` event *before* launching. Calibration is data too.

## Trials

| trial | config delta | status | headline number |
|---|---|---|---|

## Result — filled by the analyze phase

- **Verdict**: GO | NO-GO | INCONCLUSIVE, against the gate above and nothing else.
- **Evidence**: links to trial dirs.
- **One-paragraph interpretation**. The full discussion goes in NOTES.md.
