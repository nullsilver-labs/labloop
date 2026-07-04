# expNN — <title>

- **Status**: specced
- **Hypothesis under test**: (link to PLAN.md hypothesis, e.g. H2)
- **Question**: one sentence — what will we know after this runs that we don't now?

## Design

- **Setup**: model / data / procedure, in enough detail to reimplement.
- **Arms**: every condition, including all baselines. A headline arm without its
  trivial baseline is not a valid design.
- **Primary metric**: exactly one, precisely defined (dataset split, aggregation).
- **Secondary metrics**: observed but not gated on.

## Pre-registration (fill BEFORE running — this section is frozen once the run starts)

- **GO gate**: primary metric condition, as a number. E.g. "arm A beats baseline B by
  ≥ 0.05 nats on the val split".
- **NO-GO / kill criteria**: what stops the run early (divergence, no signal by step
  N, budget exceeded).
- **Prediction**: what I expect to happen, with confidence (e.g. "GO, 60%").

## Budget

- Max wall-clock: ... (must respect CONSTRAINTS.md)
- Hardware: ...

## Result (fill after)

- **Verdict**: GO | NO-GO | INCONCLUSIVE — against the gate above.
- **Runs**: links to `logs/<exp_id>/<run_id>/`.
- **One-paragraph interpretation** (full discussion goes in RESEARCH_NOTES.md).
