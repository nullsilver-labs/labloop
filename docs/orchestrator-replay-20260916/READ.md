# Orchestrator replay with Jev — the read (2026-09-16)

Plan §5's "smallest experiment that can kill it, zero GPU", run with TypeSafe's Jev as the
decision model instead of a CPU-hosted open model. `scripts/orchestrator_replay.py` replays
the recorded selection ticks of three finished campaigns on engram w0 and asks Jev, at each
tick, for the parent, the operator and (for a crossover) the partner, from the population
as it stood at dispatch. Counterfactual children are never run; nothing here is a claim
about search quality. Raw answers per tick: `replay-*.json`; the table: `REPLAY.md`; the
ablation with every search score removed: `hide-scores/`; the console lines: `ticks.log`.

## What was run

| | |
|---|---|
| campaigns | `engram-drafts4-w0` (D4, 15 ticks), `engram-mem2-findings-w0` (18), `engram-mem3-findings-w0` (18) |
| ticks | 51 improve/crossover jobs; opening drafts, debug retries and re-dispatches excluded |
| calls | 105 with scores, 105 with scores hidden; **0 errors** in both |
| backend | `POST api.typesafe.ai/v1/systemone`, `model: jev-latest`, served **`jev-1.13.0`** in every reply |
| state per tick | task head (2 500 chars), population table (id, operator, parents, search score), knob index rebuilt from the settled candidates' knobs files, best so far; criteria = one finding card per eligible candidate (≤ 1 500 chars) |
| state size | median 19 kB, max 34 kB; 10 555 / 11 974 / 10 996 input tokens at the largest tick, under the 32 k shared budget |
| latency | median 0.72 s, p95 0.97 s per call |
| cost | ≈ 466 k input tokens over both runs, ≈ $0.02 at the blog's $0.042 per million |
| decisions | argmax and a draw from the returned distribution with seed 0 (the design samples, it never argmaxes) |
| instructions | fixed text, stored in every `replay-*.json`; no examples |

## Plan §5's kill criteria

- **Parse failures above 10 % of ticks**: 0 %. The schema is enforced by the service; the only
  failure class left is HTTP, and there was none in 210 calls.
- **Median latency above 3 minutes**: 0.72 s.
- **Reasons wrong about the population in more than 1 of 10**: not applicable, Jev returns no
  reason. Substituted by the two reads below (what the distribution tracks, and calibration).

The gate is passed. What follows is what the replay says about the decisions themselves.

## What Jev's distribution is

| | D4 | mem2 F | mem3 F | rank selection, τ = 0.3, n = 11 |
|---|---|---|---|---|
| argmax = best search score so far | .93 | .78 | 1.00 | (.29 = p(best) of the sampled rule) |
| p(best), median | .38 | .45 | .54 | .29 |
| mass on the top 3 by score, median | .72 | .69 | .72 | .65 |
| Spearman ρ(p, score), median (min) | .88 (.61) | .55 (.26) | .68 (.48) | 1 by construction |
| normalised entropy, median | .73 | .69 | .62 | .83 |
| confidence, median | .33 | .45 | .50 | — |
| crossover chosen, argmax / sampled | 0 / .07 | 0 / .06 | 0 / .06 | .15 nominal |

With the scores in view, Jev is a slightly sharper rank selection: the same ordering, a
little more mass on the leader, and never a crossover at argmax. Its median confidence of
.3–.5 means the sampled decision stays exploratory; the sampled parent agreed with chance's
in 7–33 % of ticks, the argmax in 27–33 %, which is about how often chance itself took the
leader (.27 / .39 / .28).

**Scores hidden** (`hide-scores/`): ρ(p, hidden score) is still .70 / .50 / .72. The cards
carry each candidate's held-out numbers and its delta over the parent, so the score ordering
is readable from the prose, which is as it should be. The argmax is **sticky**: D4 picked
c0004 at ten consecutive ticks, then c0006 at four; mem2 F picked c0001 at nine of the
first ten; mem3 F picked c0005 at the last twelve. The population table listed every
candidate's parents, so the number of jobs already spent on a line was derivable at every
tick; the instruction asked for it to be weighed and it was not. Total variation between
the with-scores and hidden-scores distributions: .15 / .30 / .14 median.

**Frozen lineage.** Argmax inside the lineage that produced the frozen candidate: .33 / .67
/ .67 with scores, .73 / 1.00 / .67 without, against chance's .53 / .61 / .22. On mem3 F it
would have fed c0005's line at two thirds of the ticks; chance fed it at one in five and
still froze c0005.

**Calibration** against agreement with chance, by confidence tercile: .40 / .40 / .00 (D4),
.33 / .17 / .50 (mem2 F), .17 / .00 / .67 (mem3 F). No monotone relation, and none was
expected: agreement with a random rule is not correctness. A calibration read needs a
notion of a right choice, which only a run with counterfactual children gives.

## What this says

1. As a scheduler, Jev in this form is a **ranker**: it reads quality off the cards and the
   scores and puts its mass on the leader, more sharply than the rank rule. It does not do
   the bookkeeping the instruction asked for (jobs already spent on a line, knobs already
   covered under that line), or not visibly. That is the opposite of what the memory reads
   wanted from an orchestrator: two of three campaigns already over-fed the frozen lineage
   under chance.
2. It is **cheap, fast and reliable** enough to be one `[selection] mode = "model"` backend:
   two cents and 90 seconds of wall clock for a whole 20-candidate campaign's decisions, a
   pinned served version in every reply to record in `config.json`, no parse failures by
   construction. Pricing and retention are not in the public docs; the population digest
   (cards, scores, knobs; no labels, no code) leaves the machine.
3. The cheapest next step is not a campaign. It is a **second replay with the bookkeeping
   made explicit in the state**: per candidate, the number of children it already has and
   the number of jobs in its line, and per line, the knobs its last change touched. If the
   argmax stays on the leader, Jev is a ranker and the instruction cannot move it, and a
   campaign pair would only measure "sharper hill-climbing vs chance". If it moves, the pair
   as preregistered in plan §5 (chance vs model, D4 configuration, one seed, kill on
   fallbacks > 20 % and on the frozen final) is worth its zero extra GPU cost.

Not claimed: anything about search outcomes; anything about examples in the instructions
(none were given, by design, so the treatment stays Jev's judgment on the evidence and not
the operator's heuristics); anything beyond `jev-1.13.0` on this task at these three seeds.

## Second replay: the bookkeeping made explicit (same day, `bookkeeping/`, `bookkeeping-hide-scores/`)

Step 3 above, run: every candidate's row in the population table and its card now carry
`children` (jobs already built directly on it), `jobs_in_line` (its whole subtree) and
`changed_vs_parent` (the knobs its own change moved, old → new), with a note in the state
saying what they mean. 210 more calls, 0 errors, 0.73 s median, state max 38 kB (still
under the budget).

| | with scores | + bookkeeping | scores hidden | hidden + bookkeeping |
|---|---|---|---|---|
| argmax = leader, D4 / mem2 F / mem3 F | .93 / .78 / 1.00 | .87 / .72 / .94 | .53 / .22 / 1.00 | .27 / .22 / 1.00 |
| longest run on one parent (ticks) | 10 / 6 / 12 | 10 / 5 / 12 | 10 / 9 / 12 | 8 / 12 / 12 |
| distinct parents chosen, of 15 / 18 / 18 ticks | 3 / 4 / 3 | 5 / 5 / 3 | 3 / 3 / 3 | 4 / 3 / 3 |
| p(best), median | .38 / .47 / .56 | .31 / .33 / .46 | .28 / .17 / .67 | .23 / .12 / .58 |
| crossover at argmax | 0 | 0 | 0 | 0 |
| crossover sampled (one seed) | .07 / .06 / .06 | .20 / .17 / .33 | — | .27 / .00 / .17 |

The bookkeeping softened the leader's mass a little and added one or two distinct parents
in two campaigns; it did not move the argmax off the leader and did not shorten the long
runs (mem3 F: twelve consecutive ticks on c0005 in all four variants, a candidate with
eleven jobs already in its line by the end). Crossover never reaches argmax in any
variant.

**Conclusion.** By the rule written before this run, Jev in this form is a ranker: it
orders candidates by apparent quality and the instruction cannot make it trade quality
for coverage. A chance-vs-Jev pair would measure sharper hill-climbing against rank
selection, which is not what the memory reads say the search lacks (two of three
campaigns over-fed the frozen lineage under chance already). **No pair is proposed.** Jev
stays what the user asked it to be: one optional `[selection]` backend, cheap, fast,
schema-safe, recorded per decision if ever used, never a dependency. What could change
this read, if wanted later: a decision that is not "which parent" but a Score primitive
per candidate ("how much headroom does this line have?", ordered levels), so coverage is
asked for directly instead of hoped for inside a ranking; that is a different treatment
and would start with the same two-cent replay.

## Third replay: a per-candidate headroom judgment (`headroom/`, `headroom-9/`, `scripts/headroom_replay.py`)

The formulation proposed at the end of the second replay, run the same afternoon. Instead of
"which parent", every eligible candidate gets two questions at every tick, in one batched
request over a shared state (task, a written definition of *exhausted* and *open*, the
population table with bookkeeping, the knob index, one card per candidate): a **Noul**, "is
this candidate's line exhausted?", returning p(exhausted), and a **Score** over four ordered
headroom levels. The recorded history supplies a label the Choice replay never had: a
candidate is *exhausted* at tick t if it received at least one later descendant and none
beat its search score, *open* if a later descendant did; unfed candidates are unlabeled.
Beside the model: a mechanical rule from the same bookkeeping, the child counts, and the
score itself. Nine finished arms on engram w0 (the three above plus both arms of the first
memory pair, both legacy arms of mem2 and mem3, drafts-1 and mixed; the legacy arms'
summaries stand in for cards). 157 ticks, 157 calls, 0 errors, 0.95 s median per call,
state up to 49 kB (≈ 12 k tokens), 1.55 M input tokens ≈ $0.06.

| signal, AUC vs the hindsight label | pooled, 827 (tick, candidate) pairs | one row per candidate at its first eligible tick, 87 candidates, 30 exhausted |
|---|---|---|
| Jev Noul p(exhausted) | **.73** | **.62** |
| Jev Score, inverted | .67 | .61 |
| mechanical rule | .62 | .59 |
| search score (high = hard to beat) | .70 | .68 |
| children so far / jobs in line | .40 / .37 | .50 / .50 |

Mean Noul: .25 on open lines, .39 on exhausted ones, so the model rarely says "exhausted"
outright and the separation is modest. Within a tick, on pairs where the score already
orders exhausted above open, the Noul agrees 81 % of the time; on the 172 pairs where the
score orders them the wrong way, the Noul is right **79 %**. Split by score: among the
lower-scoring half of candidates the Noul reads .70 against the score's .64; among the
higher half .54 against .66. So the judgment carries information the score does not, mostly
about which of the weaker lines are dead; among leaders it cannot tell.

**What a multiplier would do to selection.** Rank selection, restricted to labeled candidates,
puts 50 % of its mass on exhausted lines at the average tick (mean over nine arms). Multiplied
by 1 − p(exhausted): 46 %. By exp(−3 p): 42 %. Gated at p > .4: 41 %, but the gate makes
mem3 F worse (.61 → .69). The mechanical rule: 48 %. A plain multiplier moves four points of
selection mass; a sharp transform eight or nine, at one seed's worth of hindsight labels that
chance's own allocation produced (child counts read *below* .5 because chance kept feeding
the lines that kept improving).

**Read.** The Noul is a real but modest signal: better than the bookkeeping rule and the
child counts, on a par with the score as a predictor, and complementary to it on the pairs
the score gets wrong. As a scheduler input it would shift a few points of selection mass
off dead lines per tick. Whether that is worth a campaign pair is a cost question: the pair
costs no extra GPU and the same worker sessions as any twenty-candidate campaign, and one
seed would not separate a four-point shift in allocation from draft-roll noise (the drafts
pair moved the final by .15 at one seed). The honest expectation for such a pair is
"not distinguishable at one seed", and the preregistration would have to say so. Not
proposed as the next campaign; recorded as the best-understood orchestrator signal so far,
with the numbers to size a multi-seed test if the search ever has the budget for one.

**The variable is not Jev's.** If it is ever used, it enters the scheduler as `headroom` per
candidate in [0, 1] from a named source (`none`, `rule`, or a model backend, Jev being one),
multiplied into the rank weight and logged per decision; the scheduler never knows where it
came from, and the rule is the control.
