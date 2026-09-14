# Legacy vs finding cards — status (2026-09-14)

Both arms of the comparison preregistered in `PREREG.md` (order `ORDER.json`: findings
first) have finished and written their immutable `REPORT.md`:

| | findings arm | legacy arm |
|---|---|---|
| project | `../labloop-engram-mem-findings-20260913` (tools `7d14dd1`) | `../labloop-engram-mem-legacy-20260913` (tools `40b9943`) |
| `REPORT.md` written | 2026-09-13T20:17:24Z | 2026-09-14T00:17:52Z |
| stop reason | max_candidates 20 reached | max_candidates 20 reached |
| settled | 20, all `completed` | 20, all `completed` |
| watcher | `20260913T1633-campaign`, done, no kill | `20260913T2019-campaign`, done, no kill |

Neither arm ended early, was deferred, paused on usage, or had a session killed. The
mechanical measures are in `mechanical.md` / `mechanical.json` (from
`scripts/mem_mechanical.py`), the prompt-size measurement in `prompt-size-*.json`
(from `scripts/pilot_prompt_size.py`, tiktoken 0.14.0 `cl100k_base`).

## Mechanical preconditions of the decision (PREREG "pending" clauses)

- ≥ 10 settled non-baseline candidates per arm: **19 and 19**.
- Neither arm ended early: **true** (both stopped at `max_candidates`).
- Served models identical: **true** — every worker session in both arms reports
  `claude-sonnet-5` plus `claude-haiku-4-5-20251001` (the CLI's helper model), 19
  sessions each.
- ≥ 40 rated M+R statements per arm: **pending the rating** (below).

## Checks for bugs and leakage

- **No child inherited weights.** `lab` copies a parent's `code/` without
  `*.safetensors` and the other weight patterns; all 38 `memory.safetensors` files
  postdate their candidate's code copy. Six search runs record
  `loaded_existing_weights: true` (legacy c0005, c0009, c0012, c0018; findings c0001,
  c0009): in the four non-frozen cases the worker re-ran `code/run.sh` a second time
  to exercise the load path after a fresh first run, and says so in its summary; the
  two frozen candidates' files were rewritten by the final run, which loads the
  candidate's own search-run weights, as in `engram-pilot-w0`.
- **Labels hidden:** privilege separation ON (`labeval`) in both arms; the final split
  was read once per arm, for c0009 (findings) and c0018 (legacy) only.
- **Same task, evaluator, world, labels:** both `campaign.toml`s differ only in id,
  memory mode and header comment; `task.md` byte-identical (the pack builder checks).

## Secondary measures (reported, no threshold)

From `mechanical.md`:

| measure | findings | legacy |
|---|---|---|
| GPU-hours / wall-clock h | 3.70 / 3.73 | 3.92 / 3.97 |
| valid candidates per GPU-hour | 5.41 | 5.10 |
| list-price equivalent (REPORT) | $10.06 | $11.18 |
| worker turns median / max | 18 / 23 | 19 / 24 |
| best search fitness after 8 settled | 0.7338 | 0.4774 |
| best search fitness after 20 settled | 0.8854 (c0009) | 0.5779 (c0018) |
| final-split score, one read | 0.8114 | 0.6439 |
| task claim vs fixed 0.50 | supported | supported |
| job-card tokens, mean (median, max) | 4640 (4859, 5467) | 2667 (2644, 3425) |

- **Prompt cost:** findings / legacy mean = **1.74**, within the preregistered
  bound of 2.0. The rebuilt findings context equals the stored `job.json` snapshot for
  every findings-arm job.
- **Coverage (findings arm): not full.** Parents were always present (0 violations).
  Once ≥ 4 cards existed, **8 of 16 eligible jobs** saw fewer than two cards from
  outside their lineage (c0004, c0006, c0011, c0012, c0015, c0016, c0017, c0019; 7 if
  the baseline's card counts as outside). Cause: the selector fills the direct
  parent(s) plus up to two ancestors first, and at `max_bytes` 12288 four to five
  cards fit, so deep lineages leave one slot for the rest of the population. Per
  PREREG the cross-branch reading of this comparison is weakened accordingly; the
  cap is the limitation the pilot predicted (four full-length cards, not eight).
- **Search progress and final scores** are reported because PREREG lists them; a
  higher score in the findings arm is not evidence of better memory and is not read as
  such (one seed, one order, the findings arm ran first).

## Primary endpoint — rating

Rating pack built 2026-09-14 by `scripts/mem_rating_pack.py` at
`../labloop-engram-mem-20260913/rating/` (`rating-README.md` and
`rating-MANIFEST.sha256` here are copies): per candidate, `summary.md` with the
`## Finding` section removed (19 sections removed in one arm, 0 in the other, as
expected), reduced `config.json`, `memory_config.json`, `code/` without weights, and
`verbatim.json` (sentences copied from the job card; the mechanical check flagged
none in either arm). Arm letters drawn with `secrets`, assignment in `SEAL.json`
(mode 600), read only after both `ratings/*.json` exist. `finding.json`, `job.json`,
sessions, fitness files and predictions are not in the pack; no final score is.

The rater is a fresh Claude session (same family as the workers, as preregistered)
given only the pack's README. Result: **see `RESULT.md` once written**; until then the
comparison is *pending*, not a result.
