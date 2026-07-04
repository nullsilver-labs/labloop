# CLAIMS.md — claim → evidence map (agent-maintained)

Each row is a claim the eventual paper might make. Updated whenever a verdict lands
(AGENTS.md §7). Statuses: `untested | supported | refuted | weakened | mixed`.
A claim is *supported* only by experiments whose pre-registered gate passed. Refuted
claims stay — negative results are reportable.

| # | claim | status | evidence (exp ids → run dirs) | caveats |
|---|---|---|---|---|
| C1 | *(example)* Method X beats baseline B on task T | untested | | |

## Paper-readiness checklist

- [ ] Every `supported` claim traces to committed `results.jsonl` + `config.json`.
- [ ] Every headline number has its baseline in the same table.
- [ ] Seeds / variance reported (or single-seed limitation stated).
- [ ] HW.md and package versions recorded for the runs that matter.
- [ ] Negative results and dead ends listed (from LEDGER + ADRs).
- [ ] All gate changes documented via ADRs.
