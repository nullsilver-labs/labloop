# ADR-0000 — adopt the labloop conventions

- **Date**: (project start date)
- **Status**: accepted
- **Driven by**: repo bootstrap

## Context

This project is run by AI agents across many sessions, with a human steering via
PLAN.md and CONSTRAINTS.md. Without fixed conventions, each session reinvents its own
logging and the paper trail degrades.

## Decision

Follow AGENTS.md as written: pre-registered specs with numeric gates, the run-dir
contract (config.json / results.jsonl / summary.md), an append-only LEDGER, ADRs for
direction changes, and a RESUME.md overwritten every session.

## Alternatives considered

- Free-form notes only — rejected: not reconstructible for publication.
- Heavy experiment-tracking platforms (W&B, MLflow) as the source of truth — allowed
  as a supplement, rejected as the primary record: the repo must be self-contained.

## Consequences

Slight per-experiment overhead (a spec before code); in exchange, any session — or a
human writing a paper — can reconstruct the full history from the repo alone.
