# Rating pack — legacy vs finding cards (README rubric completed 2026-09-15T08:28Z; pack built 2026-09-15T08:10:07Z)

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
- `pack/<arm>/cNNNN/summary.md` — the worker's summary, `## Finding` section included: its lines are prose about earlier candidates and are extracted and rated like any other. The prose to
  extract statements from, and the source for type-R statements about that candidate.
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

### Carried forward verbatim from `docs/memory-comparison-20260913/PREREG.md` (unit, types, ratings, endpoint)

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

### This preregistration's primary endpoint

The rubric of `docs/memory-comparison-20260913/PREREG.md` is carried forward verbatim —
unit, types M/R/C, the three ratings against the same sources, `fraction_bad =
(incorrect + unsupported) / rated` over M and R only, C counted separately — with one
change, fixed now:

> **The `## Finding` section is rated as prose about earlier candidates, not stripped.**

The first pack stripped it, and that stripping removed 4 of the findings arm's 5
cross-branch references — the very statements the memory is supposed to produce. Under
`findings-v2` the section is the worker's card *and* its clearest prose about other
candidates; a statement inside it is extracted and typed by the same rules as any other
sentence, and rated against the same sources (never `finding.json`, never labels, never
the final split). Statements about the candidate's own run are still not units. The
legacy arm has no `## Finding` section, so this change can only add units to F; that
asymmetry is stated here and reported with the result.

**Decision.** Read once, after both arms finish:

- **supported** if `fraction_bad(F) ≤ 0.5 × fraction_bad(L)` with at least 40 rated M+R
  statements in each arm;
- **pending** if either arm has fewer than 40 rated M+R statements, or fewer than 10
  settled non-baseline candidates, or ended early, or the two arms were served different
  models (`config.json`);
- **not_supported** otherwise. A smaller reduction is reported as a number, not as a
  claim either way. Combining this pair with the 2026-09-13 pair is a description of two
  seeds, not a pooled test.

**Rating procedure and blinding.** As 2026-09-13: after both `REPORT.md` files exist, by
a fresh operator session that ran neither arm, on a pack built by
`scripts/mem_rating_pack.py` from both projects — per candidate, `summary.md` (with the
`## Finding` section **kept**, see the prerequisite below) and the source artifacts of
every earlier candidate it names. Arm labels replaced by `A`/`B`, assignment sealed and
read only after rating, `finding.json` excluded from the pack. Blinding is partial: prose
may mention cards, and F's summaries carry a `## Finding` heading that L's do not — so
for this pair blinding is weaker than in the first, and the result says so. The rater is
a language model of the same family as the workers; the human spot-checks 10 rated
statements per arm and any disagreement is reported with the rating. The rubric is
frozen; a statement it does not cover is listed as unrated with the reason.

## Secondary measure rated from the same pack

- **Unacknowledged repeats**: candidates whose stated single change is the same knob and
  direction as an earlier non-ancestor candidate's, without naming it. Intentional
  replications (named, with a reason) counted separately. The knob ledger is expected to
  move this most; it is the measure closest to the mechanism.
