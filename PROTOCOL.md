---
id: ns-REPLACE-ME             # project id; matches the repo and site slug
title: "REPLACE-ME: one line"
kind: research                # research | artifact | writing (this template: research)
revision: 1                   # bumped only by the decide phase, via lab protocol activate
status: active                # active | concluded
autonomy: gated               # gated = protocol revisions need your approval; auto = they don't
budgets:
  max_wall_clock_per_trial: "3h"
  total_gpu_hours: 0
  money_usd: 0
created: 2026-01-01
updated: 2026-01-01
---

# REPLACE-ME — project title

## Idea

What you are actually curious about, in plain language. Two or three paragraphs. Why
it might be true, why it matters if it is, and what the world looks like if it isn't.

## Questions

The open questions this project exists to answer. Numbered, concrete.

1. …
2. …

## Hypotheses

Each one falsifiable, each one testable by an experiment you can afford. These are
what verdicts get reported against.

- **H1**: …
- **H2**: …

## Success criteria

One pre-registered numeric gate per hypothesis. A gate is a number and a direction —
"better" is not a gate. These are frozen before any trial runs; changing one after
results exist requires `lab log gate.overridden` and reporting against both.

- **H1**: e.g. "arm A beats the copy baseline by ≥ 2.0 accuracy points on the held-out
  split, n ≥ 500".
- **H2**: …

## Prior & related work

What already exists, what it found, and where this differs. Links.

## Experiment sketch

The experiments you expect to need, at the level of "what would kill the idea
cheapest first". The `init` phase compiles this into `plan.json` and spec files, so
name the arms, the baselines, and the primary metric for each.

- **exp01** — question, arms (including the trivial baseline), primary metric, budget.
- **exp02** — …

## Guardrails

Hard rules the lab may not break. Off-limits directions. What must come to you as a
gate rather than being decided autonomously. Anything that costs money.

- Never …
- Always …
- Ask (gate) before …

## Out of scope

What this project explicitly is not doing, so a later revision does not quietly
expand into it.

## Changelog

One entry per revision: what changed, and *which result motivated it*.

- **rev1** (YYYY-MM-DD) — initial protocol.
