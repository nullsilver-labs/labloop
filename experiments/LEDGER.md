# Experiment ledger

One row per experiment, ever. Statuses: `planned | specced | running | done | killed | abandoned`.
Verdicts (only when done): `GO | NO-GO | INCONCLUSIVE`. Never delete a row.
The verdict is against the **pre-registered gate** in the spec — see AGENTS.md §2e.

| id | title | spec | status | verdict | headline result | logs |
|---|---|---|---|---|---|---|
| exp00 | *(example)* smoke test | — | planned | | | `logs/exp00_smoke/` |
