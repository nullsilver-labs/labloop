# Rating pack — legacy vs finding cards (built 2026-09-14T10:23:20Z)

You are the rater: a fresh session that ran neither arm. Read only what is under this
directory. Do **not** open `SEAL.json`, the two campaign project directories, any
`REPORT.md`, `finding.json`, `job.json`, labels, or a final-split score; do not search
outside this directory. Arms are `pack/A` and `pack/B`; which memory each used is
sealed. Blinding is partial: prose may mention "cards" or "lineage". Rate from the
sources named in the rubric only.

## What is in the pack

- `pack/<arm>/records.json` — every candidate: operator, parents, execution status,
  search fitness (the lab's record), seed. This is the lab's record for type-M
  statements about scores, status, parents and operators.
- `pack/<arm>/cNNNN/summary.md` — the worker's summary with its `## Finding` section
  removed. The prose to extract statements from, and the source for type-R statements
  about that candidate.
- `pack/<arm>/cNNNN/config.json`, `memory_config.json`, `code/` — that candidate's
  artifacts, sources for type-M statements about local numbers and code.
- `pack/<arm>/cNNNN/verbatim.json` — sentences copied verbatim from the job card the
  worker received. They are not units; skip them.
- `task.md` — the task both arms worked on.

## Procedure

1. For each arm, for each candidate in id order, read `summary.md`, extract every
   statement about a prior attempt (the rubric's unit), skip the sentences listed in
   `verbatim.json`, label its type (M / R / C), and rate it against the named source.
   Quote the statement, name the candidate(s) it is about, name the source file you
   checked, and give a one-line reason for anything not rated `correct`.
2. Record, per candidate, which earlier candidates it names (cross-branch
   acknowledgment: any named candidate that is not its parent or an ancestor), and
   any earlier non-ancestor candidate whose stated single change it repeats (knob and
   direction) without naming it (the secondary measure below).
3. Write `ratings/A.json` and `ratings/B.json` (schema below) and `ratings/SUMMARY.md`
   with, per arm: statements by type × rating, `fraction_bad` over M+R, the count of
   unrated statements with reasons, the acknowledgment and repeat lists. Report per
   letter only; do not guess the assignment.
4. Stop. The operator unseals, applies the preregistered decision, and the human
   spot-checks 10 rated statements per arm.

A statement the rubric does not cover is listed under `unrated` with the reason,
never rated ad hoc. Do not edit anything under `pack/`.

### `ratings/<arm>.json`

```json
{"arm": "A",
 "statements": [
  {"candidate": "c0005", "about": ["c0002"], "quote": "…", "type": "M|R|C",
   "rating": "correct|incorrect|unsupported", "source": "pack/A/c0002/summary.md", "note": "…"}],
 "unrated": [{"candidate": "c0005", "quote": "…", "reason": "…"}],
 "acknowledgment": [{"candidate": "c0005", "names": ["c0002", "c0003"], "cross_branch": ["c0003"]}],
 "repeats": [{"candidate": "c0012", "earlier": "c0004", "knob": "…", "acknowledged": false}],
 "totals": {"M": {"correct": 0, "incorrect": 0, "unsupported": 0},
            "R": {"correct": 0, "incorrect": 0, "unsupported": 0},
            "C": {"correct": 0, "incorrect": 0, "unsupported": 0},
            "rated_MR": 0, "bad_MR": 0, "fraction_bad": 0.0}}
```

# The frozen rubric (verbatim from PREREG.md)

## Primary endpoint — factual accuracy about prior attempts

**Unit.** A *statement about a prior attempt* is one sentence or clause in a
candidate's `summary.md` that asserts something about a specific earlier candidate of
the same campaign (named by id, or unambiguously as "my parent" / "the sibling that
tried X") or about the campaign's earlier attempts collectively ("every prior run
reached loss ~1e-3"). Statements about the candidate's own run are not units.
Statements copied verbatim from the job card are not units. The `## Finding` section
of a findings-arm summary is stripped before extraction (it is the worker's card,
not prose about others).

**Types.** Each statement is labelled once:
- **M — measured fact**: a number or outcome that exists in the earlier candidate's
  artifacts (`summary.md` local numbers, `config.json`, `out/memory_config.json`,
  `code/`) or in the lab's records (`population.json` search fitness, exec status,
  parents, operator).
- **R — worker report**: what the earlier summary said it changed, hypothesised,
  observed or concluded.
- **C — causal claim**: why the earlier result happened, or what it implies.

**Ratings.** Against the sources above (never `finding.json`, never labels, never the
final split): **correct** (the source says it), **incorrect** (the source contradicts
it), **unsupported** (no source can confirm it, including attributing to a candidate
something none of its artifacts contain). A statement giving a hidden search score is
rated against `population.json`; a statement giving a local number against that
candidate's own summary or `out/`.

**Endpoint.** Per arm, over types M and R only:
`fraction_bad = (incorrect + unsupported) / rated`. Type C is counted and reported
separately (correct / incorrect / unsupported by the same rule, but its accuracy is
not the endpoint). Omissions and cross-branch acknowledgment are reported separately
(below), so silence cannot win on accuracy.

**Decision.** Read once, after both arms finish:
- **supported** if `fraction_bad(findings) ≤ 0.5 × fraction_bad(legacy)` with at
  least 40 rated M+R statements in each arm;
- **pending** if either arm has fewer than 40 rated M+R statements, or fewer than 10
  settled non-baseline candidates, or ended early;
- **not_supported** otherwise. A smaller reduction is reported as a number, not as a
  claim either way.

**Rating procedure and blinding.** Extraction and rating are done after both reports
exist, by a fresh operator session that did not run either arm, on a pack built by a
script from both projects: per candidate, `summary.md` with the `## Finding` section
removed, and the source artifacts of every earlier candidate it names. Arm labels are
replaced by `A`/`B` (assignment recorded in a sealed file read only after rating) and
`finding.json` files are excluded from the pack. Blinding is partial: prose may
mention "cards". The rater is a language model of the same family as the workers; the
human spot-checks 10 rated statements per arm, and any disagreement is reported with
the rating. The rubric above is frozen; a statement it does not cover is listed as
unrated with the reason, never rated ad hoc.

## Secondary measure rated from the same pack

- **Unacknowledged repeats**: candidates whose stated single change is the same knob
  and direction as an earlier non-ancestor candidate's, without naming it. Intentional
  replications (named, with a reason) are counted separately.

