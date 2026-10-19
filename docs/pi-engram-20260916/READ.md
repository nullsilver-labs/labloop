# Read — `engram-pi-qwen38-w0-low` (Qwen3.8-27B on Pi, engram w0), 2026-09-17

Campaign dir `../labloop-pi-engram-20260915`, read once against its `PREREG.md`, after
`REPORT.md` existed. Operator session; bulk reading (streams, configs, code greps) by a
Sonnet subagent, the numbers below checked against `population.json` and the candidate
files. Nothing in the campaign dir was changed.

## 1. Contract, the primary read: met

| | |
|---|---|
| non-baseline sessions | 18 (the campaign stopped at 19 settled of 20, see §4) |
| completed / killed / invalid / failed / deferred | **16** / 2 / 0 / 0 / 0 |
| sessions ending in a provider error | **0** (`is_error` false, `subtype` success, no `error_during_execution`, no overflow) |
| turn cap (40) hit | 0; median 18 turns, max 30 (c0001, c0008) |
| output-limit continuations | in 4 sessions (c0001, c0007, c0013, c0017); exact count not established, the stream repeats entries |
| session wall clock | median 24.6 min, max 39.7 min (c0008) |
| lease | median 28 min, max 40 min (the two kills) |

Kill criterion (< 10 completed, or > 5 provider errors): **not fired**. The gpt-oss-20b
run of the same configuration had 4 of 9 completed and 2 invalid.

The two kills (c0010, c0013) are the same behaviour: `run.sh` had finished and
`predictions-search.json` existed 22 and 16 minutes before the 40-minute kill; the worker
then kept diagnosing its one remaining search error (an `analyze.py`, a seed-matched
control rerun of the parent) and never closed `summary.md`. Both summaries are the
worker's pre-run text with an empty results section; neither says it was killed. The
debug children (c0011, c0014) reran the killed parent's code and completed.

## 2. The claim: recorded `supported`, and not evidence for the task

`lab run` read the final split once: c0011, **1.0** against 0.50. By the house rule a
result this good is a bug or leakage until checked. Checked:

- No hidden file was read: no candidate code names a labels path, the final split or
  another candidate's weights; every `memory.safetensors` is younger than its candidate's
  launch; `run.log` shows training executed; all data access is through `LAB_TRAIN` and
  `LAB_SPLIT_INPUTS`.
- **The memory is not addressed by the input tokens.** Every candidate from the draft
  c0001 on builds its key as `key_for(rec_id, attribute)`: the person id is cut from the
  *question's record id* (`rec_id.split(":")[0]`), looked up in `entities.json`, hashed
  with the `attribute` metadata field, and the looked-up vector is added at every
  position. The question text plays no part in addressing. `task.md` fixes "a memory
  addressed by the input tokens … hashed n-grams of the preceding tokens at each
  position"; this is a per-fact lookup table keyed on metadata, and "different wordings"
  stop being a test. c0001's summary states the choice openly ("keyed on the person name
  + the attribute field … not on the surface attribute word") and calls both "present in
  the input"; the name is, the way it was obtained is not. .997 at the draft and
  .999–1.0 for 17 candidates is what such a table scores.
- The Sonnet arms did not do this (grep of all four arms' candidate code, not a code
  review). None derives a key from a record id; mem3 legacy uses `entities.json` only to
  tag name tokens *found in the input ids* (its own comment: "Only input tokens are used
  here"). A milder use of the same metadata does exist there: mem3 findings candidates
  (c0005, its best, and c0003, c0008) read `q["attribute"]` to restrict decoding to that
  attribute's 16 values, which the task neither grants nor forbids. Their finals (.699,
  .873, .861, .750) are the range of the task with a token-addressed memory.

So: the claim row stays as `lab run` wrote it, and the whole lineage c0001–c0018 breaks
a fixed rule of the task. The evaluator cannot see that; nothing marked the candidates
invalid. **The 1.0 is not comparable with any Sonnet number and says nothing about
engram memories.** Item 3 of the prereg (the descriptive side-by-side of fitness) is
therefore not drawn; the rate figures are in §4.

## 3. A property of world w0 this run exposed

c0010's `analyze.py` scores its own search predictions against the training facts: the
hidden split asks the same (person, attribute) facts in new wordings, and question ids
carry the person, so `facts.json` reconstructs every hidden label, search and final.
The label *files* stayed unread (labeval), but a worker can self-score the search split
exactly, and c0010 and c0013 spent their budgets chasing one specific search error that
way. This holds for every engram w0 campaign, not only this one. A grep of the four
Sonnet arms found no separate scoring script of this kind; their session streams were
not read for one-off commands.

## 4. Rates and cost

- `gpu_seconds` is **slot-lease time**: job launch to end for a job holding a GPU, the
  worker's session included. 8.32 lease-hours, of which the candidates' recorded
  `run.sh` wall clock is about 2.5–3 h (≈ 10 min per candidate; the files record 1.55 h
  because a second run of `run.sh` overwrites `memory_config.json` with its load-only
  time). The remaining ≈ 5.5 h is the model writing at 30–45 tok/s while GPU 1 sat
  leased and idle.
- The 8 lease-hour budget, sized for Sonnet's lease length, stopped the campaign at 19
  of 20. 2.28 settled per lease-hour and 2.27 per wall-hour, against 4.72 / 5.45 per
  lease-hour for the one-slot Sonnet arms.
- List price zero; true GPU cost two cards for 8.4 h.

## 5. Leakage and provenance

- Guard: `Blocked` absent from `events.jsonl`; about 11 distinct blocked commands in 8
  sessions, all under the rule "writes into another candidate's dir". None targets a
  labels path. Most are copies *from* the parent's dir into the worker's own, or
  one-liners comparing a parent's predictions: the guard matches on the other
  candidate's path, and an `improve` worker pays turns for it. The prereg's "no session
  hit the guard" is, read literally, not met.
- Repo root clean against git (only the lab-written files and `candidates/`).
- `agent.backend` pi and served `local/qwen3.8-27b` in all 16 completed sessions; the
  two killed candidates have an empty `served` (the record is written at a clean
  settlement only).
- Final split read once (`20260916T2236-final-c0011`).

## 6. What follows

Earned, per the prereg: the next campaign on a local model. Not before three fixes,
because the same model on the same task would do the same thing again:

1. **Close the metadata route in the task, not in the worker.** `questions.json` without
   `attribute` and with opaque ids (the evaluator keeps the mapping), and one sentence in
   `task.md`: the key is computed from the prompt's token ids only. That is a new world
   file set and needs labeval, as w1 does; do both at once.
2. **Decide what w0's reconstructible labels mean** for the campaigns already read
   (a grep of the Sonnet arms for self-scoring against `facts.json` is cheap), and hold
   out *facts*, not only wordings, in w1 if the claim is to be about anything but recall.
3. **Budget by what is scarce.** For a local worker the lease budget should be sized
   from its own median lease (28 min × 20 ≈ 9.5 h), or the stop left to `max_candidates`
   and the wall clock. Tooling done today: status says `gpu lease` and shows recorded
   training beside it; `REPORT.md` names the row as slot lease.

Smaller, from the kills: the job card could say that once predictions exist the only
remaining work is `summary.md`; two of 18 sessions lost 40 minutes each to post-run
analysis.
