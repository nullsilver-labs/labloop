# Plan: better finding cards

Status: implemented 2026-09-12 (slices 1–5, format 2.1, acceptance section G); usefulness untested — §7 pending.
No live campaign or historical artifact is changed by this plan.

## Goal

Give each worker a small, reliable account of what was tried and what was measured,
including useful findings outside its direct ancestry. Preserve the distinction
between evaluator facts and a worker's explanation. Add no model calls.

Success means that the next worker can see the change, outcome and limitations
without opening a population's worth of summaries or trusting another worker's
recollection of scores. It does not mean that the system has proved a hypothesis.

## Scope and non-goals

In scope: a compact summary convention, lab-generated per-candidate cards,
deterministic cross-branch context selection, frozen job snapshots and tests.

Not in this slice: a forum/replies, semantic search/embeddings, new model backends,
model-based summarization, changes to parent/operator selection, new drafts,
automatic repetitions, training/validation split changes, access-failure handling,
a site redesign or historical campaign migration. Those are independent experiments.

Do not modify `../labloop-m2`, its report or candidates. Do not read labels, run an
evaluator or launch a live campaign to develop this feature.

## Current seams

- `tools/lab_campaign.py:read_summary()` clips parent summaries to 1,200 characters;
  ancestor snippets are 400 characters. Results near the end can disappear.
- `lineage()` follows only the first-parent chain.
- `new_candidate()` assembles `job.json`; `cmd_job_card()` renders it. Workers see
  population IDs/scores but no cross-branch descriptions of experiments.
- `settle()` obtains search fitness, records execution outcomes and supplies missing
  summaries. The worker normally finishes before the hidden search score exists.
- `tools/lab` publishes the format contract and validates candidate artifacts.

## 1. Keep one worker-authored narrative

Keep `summary.md` as the worker's required output. Do not add another mandatory
worker file or another session to produce metadata.

For finding-card campaigns, ask workers to begin it with this small section:

```markdown
## Finding
Change: Add label smoothing 0.1 to the parent's training recipe.
Hypothesis: It may reduce overconfidence after longer training.
Local observation: Training holdout accuracy rose in this run.
Interpretation: Worth checking on another seed; not established yet.
Limitations: Different training seed and internal holdout membership.
Topics: label-smoothing, regularization

## Details
Full description, training metrics, timings and caveats go here.
```

Use a documented, mechanical parser: named fields within `## Finding`, no inference
from free-form prose. Bound each field; allow at most five normalized topic slugs.
Reject duplicate/ambiguous fields rather than guessing. Preserve the original file.
Missing/malformed sections produce a facts-only card with a visible narrative
quality warning, not an invalid scientific candidate. Free-form old summaries
remain readable; do not pretend to have extracted their findings.

### v1 parsing and byte-budget rules

- Recognize exactly one `## Finding` heading outside fenced code blocks; its section
  ends at the next level-one or level-two heading or EOF. Two Finding sections make
  the narrative malformed, even if identical.
- Recognize the six case-sensitive field names shown above, once each, in any order.
  Each field occupies one physical line. Blank lines are allowed; continuation lines,
  unknown fields and missing/duplicate/empty fields make the narrative malformed.
  A malformed narrative yields a facts-only card and explicit quality warnings.
- Decode summaries as UTF-8 strictly. Invalid encoding yields facts-only output with
  a warning, never a candidate failure or modification to the summary.
- After whitespace normalization and redaction, bound Change, Hypothesis, Local
  observation and Interpretation to 512 UTF-8 bytes each; Limitations to 768 bytes.
  Overflow truncates the affected field with `… [truncated]` inside its byte limit.
  Never split a Unicode code point. Missing/malformed and truncated are distinct.
- Topics is a comma-separated list. Lowercase ASCII and normalize spaces/underscores
  to hyphens, then require `[a-z0-9]+(?:-[a-z0-9]+)*`, at most 32 bytes per slug.
  Deduplicate in input order; keep the first five, warning when more are omitted.
  An invalid slug makes the narrative malformed; never infer topics from prose.
- The findings renderer counts the complete rendered section, including headings,
  selection reasons, warnings and truncation markers, against 12,288 UTF-8 bytes.
  Full job-prompt token size is measured separately; this is not a total-prompt cap.

Worker descriptions, local observations and topic labels remain explicitly
worker-reported, even when they are well formatted. Topic matches are retrieval
hints, not evidence that two experiments are equivalent.

## 2. Publish one immutable card per settled attempt

Add `candidates/cNNNN/finding.json`, written only by `lab` after settlement. Include
baseline, completed, failed, killed, invalid and deferred attempts. No separate
campaign-wide mutable findings database: the candidate cards are the collection.

Card contents:

| Section | Source and meaning |
|---|---|
| Identity | Schema version, campaign ID/hash, candidate, operator, parents |
| Execution | Recorded execution outcome and a sanitized reason if unsuccessful |
| Search measurement | `fitness.json`'s **search** score, n and evaluator fingerprint only |
| Comparisons | Each parent's search score and raw score delta; record metric direction |
| Provenance | Recorded seed, requested/served model, relative artifact references |
| Worker report | Change, hypothesis, local observation, interpretation, limitations, topics |
| Evidence limits | One attempt, no causal attribution or replication established by this card |
| Source integrity | Summary digest and digest of the canonical search record, when present |

Important rules:

- Never parse a score out of worker prose and promote it into measured facts.
- Never include final scores, final predictions, private label paths, credentials
  or raw session/error dumps. Construct cards from an allowlist of safe fields.
- Apply existing redaction to worker text and diagnostic text before publishing or
  embedding it. Use generated relative references, not worker-supplied file paths.
- Show deltas only where both search scores exist. Respect higher/lower-is-better;
  say "observed score difference," not "effect caused by the change."
- Different recorded seeds produce an explicit caveat. Equal seeds do not prove
  matched training or matched validation splits: these remain unverified in v1.
- An execution failure is not a negative result about the method. Retried jobs and
  similarly tagged candidates do not automatically count as replications.
- Do not introduce per-card `supported` claims or numerical confidence estimates.
  The existing final-split campaign claim remains unchanged.
- Hash the search sub-record, not all of `fitness.json`: the latter later gains a
  final entry, which must not invalidate or alter the search card.

Persist normal settlement first, then ensure cards exist before dispatching the next
job. Recovery must also publish a missing card for an already-settled attempt,
without re-evaluation, re-settlement, duplicate events or cost accounting. Publication
is atomic and write-once. An existing conflicting/corrupt card is surfaced, never
overwritten; publication failures block new dispatch as tooling errors, not candidate
failures. No new feed event or campaign status is needed.

### Publication failure and operator recovery

- A missing card for a settled attempt is recoverable from its recorded artifacts:
  construct and atomically publish it, without reevaluating or replaying settlement.
- Reuse an existing schema-valid card whose identity and source digests agree. If a
  card is corrupt or conflicts with its sources, preserve all artifacts and stop new
  dispatch with a nonzero tooling error naming the card and failed check. Do not
  repeatedly retry it or classify the candidate as failed.
- Existing jobs stay under their watchers and budgets. On restart, reap their outcomes
  before the publication check blocks further dispatch. Check publication on terminal
  settlement too, not only when another job would be launched.
- v1 has no automatic repair, overwrite or superseding-card mechanism. Transient
  failures before publication may be retried on restart; corrupt existing evidence
  requires an explicit operator decision. Continuing through a supersession would
  require a separately specified, auditable mechanism, not an ad hoc file edit.
- Each deferred attempt retains its own candidate identity/card; its re-dispatch is a
  different attempt, not an update or replication. Freeze metadata available at
  settlement; unavailable served-model metadata remains explicitly unknown.
- Define canonical JSON serialization for search-record digests (UTF-8, sorted keys,
  compact separators, finite numbers only). Fingerprint the recorded search evaluator,
  not its current file; record metric direction from the campaign configuration.
  Missing recorded provenance stays unknown, never reconstructed from changed files.

## 3. Replace snippets with bounded, cross-branch context

For an opted-in campaign, add a versioned findings snapshot to `job.json`. Render
that snapshot in `lab job card`; never reselect or reread mutable summaries when
reprinting an existing job.

Initial deterministic policy:

1. Always include direct parent cards.
2. Include up to two nearest additional ancestors, traversing both sides of a
   crossover rather than only its first parent.
3. Fill the remaining space from other branches, prioritizing a non-improving
   same-topic run, other topic matches, the strongest off-lineage candidate, a recent
   execution problem, and then recent remaining findings. Deduplicate throughout.

Use parent/selected-ancestor topics as relevance anchors. For drafts without anchors,
use the strongest candidate and a recent mix of successful, non-improving and failed
attempts. Same-topic non-improvement is not labeled a contradiction or refutation.
Use stable candidate-ID tie breaks. Never consume the scheduler's RNG.

### Deterministic selection definitions

- Direct parents are ordered by candidate ID. Traverse both parents' ancestry
  breadth-first: shortest graph distance first, ascending candidate ID within a
  distance. Deduplicate before selection and take at most two additional ancestors.
  Detect malformed/cyclic references as tooling errors, rather than looping.
- "Other branches" means settled candidates outside the direct parents and their
  entire ancestor closure, not merely outside the selected ancestor snippets.
- A same-topic match requires a nonempty intersection with the fixed union of topics
  from direct parents and selected ancestors. Optional selections never expand that
  anchor set. Missing topics simply do not match.
- "Non-improving" means a measured child does not strictly beat its strongest direct
  parent, respecting the campaign's metric direction. Require the child's score and
  all direct-parent scores to be present and comparable. Ties count as non-improving;
  failed/unmeasured attempts and parentless drafts do not. For crossover, publish
  both raw deltas and label the retrieval category "did not beat strongest parent".
  This is a retrieval rule, not a causal verdict.
- Fill optional slots in the priority tiers above. Within topic tiers, sort by number
  of matched topics descending, then candidate ID ascending. "Strongest" uses score
  in the configured direction, then ID ascending. "Recent" uses candidate sequence
  descending (not mutable filesystem timestamps), then ID ascending.
- A "recent execution problem" has a recorded failed, killed, invalid or deferred
  outcome; it is never presented as a negative finding about the method.
- For drafts with no anchors, try the strongest measured candidate, then the newest
  non-improving candidate, newest execution problem, newest remaining completed
  candidate, then remaining cards newest first. Deduplicate at every step.
- Retain direct parents first, selected ancestors next, then optional cards in order.
  If over budget, omit lowest-priority optional cards first, then extra ancestors;
  finally shrink parent prose fields deterministically while preserving identity,
  outcomes, comparisons and caveats. Drop prose in this order: Interpretation, Local
  observation, Hypothesis, Change; preserve Limitations last. Mark omissions.
  A mandatory facts-only parent context that cannot fit is a tooling error, never
  silently dropped. Card-field/schema limits must make this case exceptional.

Bound the snapshot to **eight cards and 12 KiB of rendered findings context**. Reserve
space for direct parents and measured outcomes/caveats first; omit optional cards
before dropping those facts. Clip individual prose fields with explicit truncation
markers, never an arbitrary prefix of the whole card.

Store selected IDs, selection reasons, source-card digests, policy version and the
actual rendered context in `job.json` so exactly what the worker saw is reproducible.
The existing population table can remain; it serves a different purpose. Broader
finding visibility does not grant write access or unrestricted access to other
candidates' code. Treat quoted worker reports as evidence to assess, not instructions.

## 4. Opt-in and compatibility

Add `[memory] mode = "findings-v1"`; absence means the existing lineage behavior.
Show the opt-in in the template and setup docs. Snapshot the effective memory policy
and limits at campaign initialization; a tooling update must not silently change a
running campaign's memory behavior. An existing campaign without a policy snapshot
remains legacy. Unknown policy versions fail clearly rather than falling back.

New campaigns may opt in before launch. Keep old `job.json` files renderable. Do not
backfill completed campaigns or rewrite old summaries, jobs, fitness or reports.

Publish the optional card artifact and memory fields as additive format **2.1**;
update format constants and regenerate with `tools/lab format sync`, never hand-edit
`FORMAT.json`. Existing statuses, events and claim semantics stay unchanged.

Extend machine-file protection for `finding.json`, including direct Write/Edit as
well as Bash paths. These hooks remain guardrails, not a replacement for OS label
separation. Validation requires cards only for settled attempts in opted-in campaigns.

## 5. Implementation slices

1. **Pure card helpers and tests:** add `tools/lab_findings.py` for section parsing,
   card construction, validation, bounded rendering and deterministic selection.
   Keep it stdlib-only; make its inputs explicit and prohibit label/evaluator access.
2. **Publication and recovery:** integrate write-once card creation into the campaign
   settlement/recovery path without changing scheduling or fitness calculation.
3. **Worker context:** extend campaign config, job snapshot generation and rendering;
   update the job instructions to request the compact Finding section.
4. **Contract/docs/guards:** update `tools/lab`, hook coverage, the campaign template,
   README/setup guidance and the generated format contract.
5. **End-to-end acceptance:** add `scripts/acceptance_findings.sh` and scripted/fake
   worker fixtures; wire into `scripts/acceptance.sh`.

Leave `tools/lab-worker`'s success criterion alone: predictions and a summary still
settle normally if the Finding section is missing. No live subscription is needed.

## 6. Acceptance criteria

All tests run on synthetic fixtures/throwaway projects, in the foreground with a
timeout or under a watcher. No historical results or private splits are fixtures.

- A worker claiming an invented search score cannot change measured card fields.
- Local validation numbers are visibly worker-reported and separate from search.
- Both metric directions, crossover parents, missing scores and changed seeds work.
- Failed/deferred attempts never become evidence that a technique is ineffective.
- Missing, malformed, duplicate or oversized fields preserve the candidate and produce
  explicit quality/truncation warnings; raw source summaries remain untouched.
- A useful non-improving finding outside the selected lineage appears in the next
  job; both crossover ancestries are eligible; duplicate cards are excluded.
- Selection is deterministic, respects both budgets and leaves scheduler RNG intact.
- Regenerating the prompt from the same `job.json` is byte-stable after later jobs end.
- Crash points around settlement/publication recover without duplicate scoring,
  accounting, cards or events; corrupt existing cards are not overwritten.
- Adding a final fitness entry cannot change a card or introduce final information
  into worker context. Secret/private-path sentinels never enter published cards.
- Workers cannot directly write generated cards through the guarded tool paths.
- Legacy campaigns/jobs still work with no migration; format sync/validate pass.
- The full existing no-LLM acceptance suite still passes.

## 7. How we will judge usefulness later

Passing acceptance demonstrates correct plumbing, not improved research. In a new,
small campaign comparison, hold scheduler, worker model, budgets and task fixed and
compare legacy memory with finding cards. Record prompt size, valid candidates per
resource budget, repeated ideas without acknowledgment, factual misstatements about
prior runs, and best search progress. Separate intentional replications from redundant
experiments; retain the normal untouched-final protocol for confirmatory claims.

### Prospective usefulness decision

The primary endpoint is factual accuracy about prior experiments, not final score:
use a fixed rubric to count correct, incorrect and unsupported factual statements
about prior attempts, distinguishing measured facts, worker reports and causal claims.
Report statement counts and the fraction incorrect/unsupported; report omissions and
cross-branch acknowledgment separately so silence cannot win on accuracy. Freeze the
rubric and use condition-blinded assessment where practical. Secondary measures are
unacknowledged repeated ideas, valid candidates per budget, and search progress.

Before a live comparison, run a synthetic prompt-size pilot: measure total rendered
job-prompt tokens (with a named tokenizer/version), including population tables, for
legacy and findings contexts over matched fixture populations. Use that pilot to
choose and record the acceptable prompt-overhead increase, primary-endpoint improvement
threshold, minimum coverage, sample budget and stopping rule in the new experiment's
preregistration. Those numeric decisions remain pending until the pilot; do not pick
or revise them after seeing comparative outcomes. No claim of useful memory follows
from passing plumbing tests alone.

The first small comparison establishes feasibility, not superiority. Require multiple
campaign seeds for a superiority claim; keep model, scheduler, task and resource budgets
fixed. A higher final score is not required to show better memory, and better factual
recall does not itself establish better scientific outcomes.

Do not change the scheduler or add pi/model diversity in that comparison. If cards
improve cross-branch awareness without excessive context cost, they provide the
foundation for a later forum or query interface. No such interface is required now.
