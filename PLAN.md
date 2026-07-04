# PLAN.md — the research plan (human-curated)

> **This is the one file the human must write.** The agent treats it as the source of
> scientific truth. Replace every section below; delete the guidance quotes. Length is
> up to you — a page can be enough, but the more precise the hypotheses and success
> criteria, the less the agent has to guess. (The project this template came from had
> a ~30-page PLAN.md; that precision paid for itself.)

## 1. Research question

> One paragraph. What are you trying to find out? What would the one-sentence result
> be if everything works?

## 2. Background and intuition

> Why you believe this might work. Prior work, analogies, back-of-envelope arguments.
> The agent will extend this with its own literature notes in RESEARCH_NOTES.md.

## 3. Hypotheses

> Numbered, falsifiable statements. H1, H2, ... Each should be testable by one or a
> few experiments. Mark which are load-bearing (if false, the project dies) vs nice-
> to-have.

## 4. Proposed approach

> The method you have in mind: architecture, data, training recipe, evaluation.
> Flag what is fixed ("we always do X") vs open ("agent may explore Y vs Z").

## 5. Phases and gates

> Break the work into phases, each with a GO/NO-GO gate — a concrete, numeric
> criterion decided now, not after seeing results. Example:
>
> - **Phase 0 — feasibility**: metric M on task T beats baseline B by ≥ X. If not,
>   stop and report.
> - **Phase 1 — end-to-end**: ...
>
> The agent will refine each phase into pre-registered experiment specs, but the
> phase gates are yours.

## 6. Baselines that must be beaten (or at least run)

> The trivial and strong baselines any reviewer would demand. Be explicit — the agent
> is required to run these before claiming anything.

## 7. What "publishable" looks like

> Which results, at which strength, would justify writing a paper? Target venue or
> style if you have one. This drives paper/CLAIMS.md.

## 8. Known risks and dead ends to avoid

> Things you already suspect won't work, pathologies to watch for (metric blind
> spots, leakage risks, off-manifold effects...). Saves the agent from rediscovering
> them expensively.
