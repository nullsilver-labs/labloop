# CONSTRAINTS.md — the rules (human-curated)

> Hard rules the agent must obey. This file **overrides PLAN.md**. Delete sections you
> don't need; an empty file means "use good judgment". Keep entries concrete — a
> number the agent can check beats an adjective.

## Compute budget

- Max wall-clock per run: e.g. **3 h** (kill anything longer unless a spec, approved
  by the human, says otherwise).
- Progress-check cadence for running jobs: e.g. every **25 min**.
- Total budget for the project (GPU-hours / $ / calendar time): ...
- GPU allocation rules (e.g. "cuda:0 is shared, prefer cuda:1"): ...
- Kill redundant runs: if two runs answer the same question, kill the worse one.

## Scientific constraints

> Non-negotiables of the method. Examples from the project this template came from:
- e.g. **The base LLM stays frozen** — its weights never enter an optimizer; assert
  this in code.
- e.g. Evaluation metric X is defined as ... and may not be redefined without an ADR
  *and* human sign-off.

## Directions that are off-limits

> Things the agent must not spend time on, even if promising. Examples:
- e.g. No fine-tuning models larger than N params.
- e.g. Don't explore approach Y — already tried, see decision/paper Z.

## Data rules

- Allowed datasets / licenses: ...
- Anything that must not leave the machine (private data, keys): ...

## Ask-the-human-first

The agent must stop and ask before:
- spending money or calling paid APIs beyond: ...
- pushing to any remote / publishing anything externally;
- exceeding any budget above;
- (add your own).

## Anything else

> House rules: coding language, framework preferences, style, ...
