# Rating summary — arms A and B (blinded)

Rated by a fresh session that ran neither arm, from `rating/pack/` only. `SEAL.json` was
not opened; no campaign directory, `REPORT.md`, `finding.json`, `job.json`, label or
final-split score was read. Arms are reported by letter only; no guess about which memory
each arm used is made or implied anywhere in these files.

Rubric: the frozen unit/type/rating/endpoint definitions carried forward in
`rating/README.md`, with this preregistration's one change applied — the `## Finding`
section is **kept** and its statements about earlier candidates are extracted, typed and
rated like any other prose. Only arm B's summaries carry a `## Finding` section; arm A's
do not, so that change could only add units on one side. This is the asymmetry the
preregistration names, and it is why blinding here is partial.

## Arm A

| type | correct | incorrect | unsupported | total |
|---|---|---|---|---|
| M — measured fact | 212 | 11 | 1 | 224 |
| R — worker report | 25 | 0 | 3 | 28 |
| C — causal claim | 14 | 0 | 1 | 15 |

- **rated_MR = 252, bad_MR = 15, fraction_bad = 0.0595**
- C counted separately: 14/15 correct, 1 unsupported (not part of the endpoint).
- Statements extracted from 19 of 20 candidates; c0008 is a deferred candidate whose
  summary is only the mechanically copied session-limit text, so it yields no units.
- **unrated: 2** — (1) c0001's comparison to the operator reference runs (LoRA 0.9653,
  full fine-tune 0.9961), which `task.md` says are not candidates and for which the pack
  holds no source; (2) c0008's session-limit text, listed for completeness.

## Arm B

| type | correct | incorrect | unsupported | total |
|---|---|---|---|---|
| M — measured fact | 165 | 14 | 1 | 180 |
| R — worker report | 7 | 0 | 3 | 10 |
| C — causal claim | 3 | 0 | 0 | 3 |

- **rated_MR = 190, bad_MR = 18, fraction_bad = 0.0947**
- C counted separately: 3/3 correct.
- Statements extracted from 18 of 19 candidates; c0001 is the first non-baseline
  candidate and asserts only that it has no parent.
- **unrated: 3** — three claims about the task's data or tokenizer (name-token length,
  name-word uniqueness, vocabulary size vs table buckets) rather than about an earlier
  candidate; the rubric's unit does not cover them, so they are not rated.

Both arms clear the ≥ 40 rated M+R statements per arm that the decision rule requires.
`fraction_bad(A) = 0.0595`, `fraction_bad(B) = 0.0947`. Applying the preregistered
decision is the operator's step after unsealing, not the rater's.

## What the errors were

Arm A (15 bad M+R): four errors are inside one candidate, c0015 (a relative-drop
comparison stated backwards, a "520k-row table" for a 500,000-row table, a claim that the
small table "was only tested up to 0.4" when an earlier candidate ran 0.6, and a
held-out-proxy trend attributed to the whole c0001–c0003 lineage that holds only for its
last step). Two further candidates (c0004, c0006) describe c0003's proxy-vs-fitness gap as
an "understatement" / as pointing "in different directions" when both proxies overstated
fitness in the same direction. The three unsupported R statements attribute to an earlier
summary something it does not contain (a hidden-split number of its own, a seed caveat).

Arm B (18 bad M+R): the largest single cluster is c0008's three sentences asserting that
no earlier candidate had ever used n-gram orders beyond 1, contradicted by c0001
(orders [1,2,3]) and c0002 (orders [1,2]); and c0019's three sentences asserting that
weight_decay had never been varied, contradicted by c0009 and c0014, plus a claim that
batch_size had been "explored in both directions" when it was only ever raised. Two
candidates (c0005, c0006) repeat a wrong parameter count for c0003 (14.1M for 15,166,720).
Two candidates (c0009, c0015) describe a pair of runs as differing by seed alone when the
pair also differs by a knob. c0006 names the wrong previous-best holdout; c0017 calls
+0.0668 the largest jump in the ledger when two larger ones exist, and calls layer 4 the
only other measured depth when layer 6 was measured too.

## Cross-branch acknowledgment (reported separately, not part of the endpoint)

| | candidates naming a non-ancestor | cross-branch references | total named references |
|---|---|---|---|
| A | 3 (c0001→c0000 baseline, c0007→c0006, c0013→c0012) | 3 (2 excluding the baseline) | 54 |
| B | 12 | 21 | 55 |

Both arms name earlier candidates at a similar rate overall (54 vs 55 references); they
differ in *which* candidates. Arm A's references are almost entirely to its own ancestors;
arm B names siblings and other branches in 12 of 19 candidates.

## Repeats (secondary measure)

**Arm A — 4 unacknowledged repeats, 1 named replication.**

- c0015 repeats c0005's knob and direction (dropout 0.4 → 0.6) without naming it, and its
  summary states the small-table branch was "only tested up to 0.4".
- c0017 repeats c0014's knob and direction (table rows 500,000 → 2,000,000 from the same
  parent c0012) without naming c0014.
- c0018 repeats c0015's knob and direction (dropout 0.4 → 0.6 from the same parent c0012)
  without naming c0015.
- c0020 repeats c0012's crossover recipe (add dropout 0.4 on top of c0010's shared-table
  architecture) without naming c0012.
- Named replication: c0009 deliberately re-runs dropout 0.4 under a new seed, names the
  earlier candidate and gives a reason.

**Arm B — 1 unacknowledged repeat, 4 named replications.**

- c0019 repeats c0009's knob and direction (AdamW weight_decay 0.0 → 0.01) without naming
  it, and explicitly states in a "Repeat check" that no candidate in the ledger had ever
  varied weight_decay.
- Named replications: c0003 (orders reduced further, naming c0002), c0011 and c0014
  (train_seconds 360 → 540, both naming c0006 and justifying the new branch), c0017
  (batch_size 32 → 64, naming c0016 and testing it at another attach depth). c0018 also
  names both prior batch-size attempts before moving to a new value.

## Counting conventions (applied identically to both arms)

1. A table row or enumeration that gives per-candidate values is split into one statement
   per earlier candidate, rated on that candidate's own cells.
2. A universal or collective claim ("no candidate in this lineage has ever varied X") is
   one statement, with every candidate that bears on it listed in `about`.
3. Where two sentences in the same summary make literally the same assertion, it is rated
   once, except where the second sentence adds a distinct claim (for example a "repeat
   check" restating a universal negative as a procedural conclusion).
4. Statements about the candidate's own run, and the sentences listed in each candidate's
   `verbatim.json`, are not units.
5. Mentions of the trivial baseline c0000 are counted as units and as named references in
   both arms; c0000 has no directory in the pack, so such statements are rated against
   `records.json` and `task.md`'s definition of the baseline.

## Difficulties applying the rubric

- **Splitting multi-candidate sentences.** Many sentences in both arms compare three or
  four candidates at once ("c0001 dropout=0 → 0.217, c0002 0.2 → 0.314, c0003 0.4 →
  0.358"). Convention 1 makes these several correct statements, which inflates both arms'
  correct counts relative to a per-sentence count. Arm A uses this form more often, so its
  denominator is larger for the same amount of prose; the fraction, not the count, is the
  endpoint, which limits the distortion but does not remove it.
- **Universal negatives versus per-candidate splitting.** The clearest errors in arm B are
  universal negatives that are wrong about two candidates at once. Counting them per
  candidate would have roughly doubled their weight; convention 2 counts each such
  sentence once. Arm B's `fraction_bad` would be higher under the other convention.
- **Attribution to a summary versus to the records.** Several statements say "candidate X's
  own summary reported ..." and then give a hidden-split fitness that no worker could have
  known. The number is correct against `records.json` while the attribution is wrong
  against the summary. Where the sentence is primarily a number, it is rated M against
  `records.json` and the mis-attribution is noted; where it is primarily a claim about what
  the earlier summary said, it is rated R and marked unsupported. This line is genuinely
  fuzzy and is the judgement call most likely to move on a spot-check.
- **Self-correcting and typo sentences.** A few sentences contain a slip that the same
  sentence immediately repairs (arm A c0006's "also below c0003's ... (0.4041 < 0.4500, so
  still above c0003)") or a transcription digit (arm B c0010's "0.725341875" for
  0.725341796875). These are rated correct with a note; a stricter reader could rate them
  incorrect, which would add about one bad statement to each arm.
- **Code-identity claims.** "Byte-identical to the parent", "inherited unchanged except
  this one change" were checked by diffing the two candidates' `code/` in the pack. In arm
  A, c0002's "inherited code unchanged except for this one change" also carries a
  `memory.eval()` fix that the same summary declares and justifies; it is rated correct on
  that basis rather than as an undisclosed second change.
- **The `## Finding` asymmetry.** Arm B's Finding blocks are dense, numeric and highly
  comparative, so keeping them (this preregistration's one change) supplies a large share
  of arm B's units — including most of its cross-branch references and most of its errors.
  Arm A has no equivalent section, and its comparable content lives in prose sections that
  were extracted the same way. The two arms are therefore not extracted from symmetric
  surfaces, and this result should be read with that in mind.
- **The deferred candidate.** Arm A's c0008 has no worker summary (usage limit). It
  contributes no statements to either numerator or denominator; arm B has no deferred
  candidate. Arm A also has 20 candidates to arm B's 19.
