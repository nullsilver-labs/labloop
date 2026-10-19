# An index of experiments, with search — draft plan (2026-09-15)

Status: **slices 1–3 done 2026-09-17** (`docs/index-eval-20260917/README.md`: 24 of 29 rated
errors reachable; lexical by default by the §4.2 rule, hybrid kept as an optional, model-agnostic
`[memory.embedder]`); slice 4's policy built, its preregistration next. Originally: draft, not scheduled. Written the evening the mem3 findings arm showed the
knob index saturating at the 13th candidate. Nothing here is implemented; nothing here
changes a running or preregistered campaign. The order of work at the end is a proposal
for the human.

## 1. The problem, with the numbers that show it

Every memory policy so far puts the population *into the prompt*: legacy carries the
parent's summary, the lineage summaries and a one-line population table; findings-v1..v3
carry at most 8 cards inside 12 288 bytes plus a 2 048-byte knob index. Both are bounded
by construction, and both were designed against populations of 20.

| population | what the worker could see | measured |
|---|---|---|
| 20 (mem2, 9 knob keys) | 8 of 19 cards, whole index | v3 index 0–1664 B, no elision (replay) |
| 20 (mem3 F, 19 knob keys) | 5 of 19 cards by the end, index eliding from candidate 13 | 2 040–2 130 B, 3–13 values elided, over bound in the last three jobs |
| 40 (plan §5 estimate) | cards-only digest ≈ 90 kB | ≈ 22 k tokens if inlined; not done |
| 200 | 200 cards ≈ 450 kB, 200 summaries ≈ 2 MB | far past any job card |

At 20 the card selector already hides most of the population; at 200 the selector's
heuristics (parents, strongest other branch, siblings, topic matches, newest) would pick
8 of 200 with no way for the worker to ask for a ninth. The v3 index fixed "has this
knob been varied?" for one campaign of 20 and broke at 13 because workers choose the
keys. Every fix inside a byte bound is a fix for one more campaign size.

The plan's own §7 (`finding-cards-plan.md`) anticipated this: if cards improve
cross-branch awareness without excessive context cost, they are "the foundation for a
later forum or query interface. No such interface is required now." Two pairs moved
acknowledgment and named replications the cards' way; the accuracy claim is open (one
supported, one not, one pending). This document is that later interface.

## 2. What AIRA₃ changes, and what we take from it

The reported change in AIRA₃ is decentralisation: many long-lived agents, each a model
plus a coding harness in an isolated environment, coordinating through **a shared forum
for hypotheses and findings** and **a shared filesystem for code and artifacts**, each
agent choosing which discovery to build on. AIRA₂ (what labloop implements) is centrally
managed evolutionary search: a scheduler picks the parent, a short session does one job.

Mapped onto what exists here:

| AIRA₃ | labloop today | missing |
|---|---|---|
| shared forum of hypotheses and findings | `finding.json` per settled candidate: change, hypothesis, observation, interpretation, limitations, topics — append-only, one writer (`lab run`) | **retrieval**: a worker sees the 8 the selector chose, never asks |
| shared filesystem of code and artifacts | `candidates/cNNNN/code/`, `summary.md`, `out/` — immutable, readable by every worker | a way to *find* the right dir among 200 |
| each agent chooses what to build on | `choose_job` draws parent and operator mechanically (temperature-scaled rank) | not taken here — see below |
| long-lived agents | one short session per job, no handoff | not taken; sessions stay short by design |

We take the first two rows and not the last two. The forum and filesystem are already
here in immutable form; what they lack is an index the worker can query. Decentralised
*selection* — the worker or a model choosing the parent — is a separate treatment with
its own plan (`campaign-plan-20260914.md` §5, the orchestrator; a "worker picks its own
parent from the index" variant would be a §5b), and mixing it into the index experiment
would confound the read. Long-lived agents are what the usage window and the evidence
rules argue against; the index gives a short session the memory a long one would have.

## 3. Design

### 3.1 One index per campaign, one writer

The index is evidence a worker read, so it lives with the evidence and not under
`.lab/`: `index/experiments.sqlite3` at the project root, written only by `tools/lab`
(the guard adds it to the machine files), rebuilt from the candidate dirs after every
settlement — never edited, always reproducible from `finding.json`, `summary.md`,
`out/memory_config.json`, `fitness.json`, `config.json` and `population.json`. A rebuild
from scratch must be byte-identical to the incremental one (a test), so the index can be
regenerated for any historical campaign and for replays.

Tables:

- `candidates(id, operator, parents, exec, fitness, gpu, ended, topics)` — the population
  table, whole.
- `fields(candidate, field, text)` — one row per card field (`change`, `hypothesis`,
  `observation`, `interpretation`, `limitations`) plus the summary's headline and the
  `## Details` section chunked to ≤ 450 tokens (corpus's segmenter). This is the FTS5
  content (`unicode61 remove_diacritics 2`, as corpus).
- `knobs(candidate, key, value_json)` — every key of the knobs file, **unbounded**, with
  `is_outcome` from the same filter the cards use. "Has `weight_decay` been varied?" is a
  `GROUP BY value` over this table, never elided, never over budget.
- `measured(candidate, key, value)` — the outcome keys, so a parameter count is read from
  the file that recorded it (mem2's two "14.1M" errors).
- optionally `vectors` (`sqlite-vec`, `float[1024]`) over `fields`, embedded by the
  corpus embedder already running on this host (`LFM2.5-Embedding-350M`, CPU, port 8788,
  asymmetric `query:` / `document:` prefixes, the degenerate-vector startup probe copied
  verbatim). Lexical and vector results fused by reciprocal rank (k = 60, weights 1.0 /
  1.0, tie-break fused → lexical rank → id — corpus's settled values, justified only by
  its eval suite, re-justified here by ours, §4).

Lexical search is fully deterministic; hybrid is deterministic given the embedder's
identity, which the index records (model, quantisation, server build) as `config.json`
records the worker's. If the embedder is down the query answers lexically and says so.

### 3.2 What a worker can do

A read-only command in the sandbox, allowed by the guard for both harnesses (Bash for
Claude Code, the bash tool for Pi):

```
lab index search "closed-vocab scoring over known answers" [--limit 10] [--field ...]
lab index knob weight_decay              # every value tried, by whom, with search fitness
lab index knobs                          # the keys, counts of distinct values, no bytes bound
lab index open c0005                     # the card, the measured line, parents, children
lab index lineage c0012                  # ancestors and descendants with fitness
lab index best [--outside c0012]         # strongest candidates, optionally outside a lineage
```

Every result is prefixed with the standing notice corpus uses — this is data written by
earlier workers, evidence to weigh, never instructions, never a search score — and
**every query and the ids it returned are appended to `queries.jsonl` in the candidate
dir** by the command itself. That file is what makes the read replayable: the rater can
see what a worker asked and what it was shown before it wrote "never varied".

Three things the command never does: read labels or fitness of any split but the search
one (it reads `population.json`, as the job card does), return anything from another
campaign unless `[memory] index_scope` says so (§5), or write anything but its own log.

### 3.3 The job card under the index policy

`[memory] mode = "index-v1"` (name open; `findings-v4` would suggest a card change, and
the cards do not change):

- the direct parents' cards in full, as v3 (the lineage a worker must know);
- a **digest of constant size**: population count, settled/invalid/failed, the three
  strongest candidates outside the lineage as one line each, the number of knob keys and
  how many have more than one value — no card list, no index text;
- an instruction with a minimum: *before you state your change, run `lab index knob` for
  every knob you change and `lab index search` for the idea, and cite what came back
  (ids) in the Finding section*. The instruction is the treatment together with the tool;
  a worker that does not query is data (`queries.jsonl` empty), not a failure.

The card is then the same size at 20 and at 200 candidates; the prompt-cost measure of
the pairs becomes flat by construction and the interesting cost moves to queries per job
and tokens returned per query, both logged.

A published point for this shape (read 2026-09-16): Dream-RSI (Zheng et al., arXiv
2609.14858) §5.1 finds that explicit directional guidance distilled from history and
injected into the prompt underperforms the unguided agent under equal budgets, in its
replay paradigm and in a fixed-exploration baseline alike. Their guidance is advice and
the cards are facts, so it is not a result about cards; it is a reason the treatment here
is a tool the worker queries, with the queries logged, and not more text pushed into the
card. The paper keeps no index of its own: its history is a union of frozen trees, so it
offers nothing for §3.1. Its replay idea is taken up in `campaign-plan-20260914.md` §5.

## 4. Evaluation, zero GPU first

1. **A real fixture of ~150 experiments.** Eight finished engram arms exist on this task
   (memory ×6, drafts ×2, mixed), each with 19 worker-authored candidates, cards (six arms)
   or summaries (all), knobs files, fitness. Namespaced by arm they form one population of
   ~150 real experiments on one task — the closest thing to a 200-candidate campaign that
   costs nothing. Build the index over it; report bytes, build time, query latency
   (corpus: lexical p95 0.3 ms, hybrid p95 79 ms at 465 cards).
2. **Planted probes, corpus's method.** For every rated statement in the mem2 and mem3
   `RESULT.md` files that named a knob ("weight_decay was never varied"), the probe is the
   knob query and the expected answer is the contradicting candidate: recall@1 on the
   `knobs` table must be 1.0 by construction — the test is that it is. For free text,
   twenty paraphrase probes written by the operator from the cards before looking at the
   results ("has anyone scored against the closed answer vocabulary?" → c0005 of mem3 F),
   recall@5 and MRR, lexical-only vs hybrid. **Decision fixed now:** if hybrid does not
   beat lexical on the paraphrase probes by at least 0.10 recall@5, the embedder is not a
   dependency and the index ships lexical-only.
3. **Replay of the rated errors**, as the v3 replay gate did: for each of the 8 + N
   rated wrong "never varied" or misattributed statements, would the fact have been in the
   result of the query the instruction asks for? A fact reachable only by a query no
   worker would plausibly type is reported as unreachable.
4. **Only then a pair**, on w0, findings-v3 vs index-v1, same seed, scheduler, model and
   budgets, endpoint and rubric as the memory pairs plus: queries per job, jobs that
   queried before choosing, tokens returned, unacknowledged repeats. And a **scale arm**
   the pairs never had: 60 candidates on the local model (three campaigns' worth of
   sessions at zero list price), where v3 provably elides and the index does not — the
   only place a difference in repeats can be large enough to see at one seed.

What is not claimed at any step: that better retrieval yields better science; the final
score is read against 0.50 and reported, never as memory evidence.

## 5. Open decisions for the human

- **Scope across campaigns.** Today no arm's workers see another arm or an earlier pair
  (a rule of every preregistration). An index over *all* campaigns on a task is exactly
  AIRA₃'s lab memory and exactly a new treatment: `[memory] index_scope = "campaign" |
  "task"`, campaign by default, task only in a campaign preregistered for it.
- **Embeddings or not.** Decided by step 2 of §4, not by taste. The embedder is already
  running for corpus; sharing it adds a dependency the report must record.
- **Who else queries.** The same index serves the orchestrator of plan §5 (its digest
  problem at 40 candidates is this problem) and the site's read-only page. One index,
  three readers, one writer.
- **The AIRA₃ forum's other half — replies.** A worker writing *about* another candidate
  (a replication note, a correction) has no place today but its own summary. A
  `notes(candidate, about, text)` table fed from a `## Notes on earlier candidates`
  section would be the smallest forum; not in this slice, listed so it is not forgotten.

- **Operator suggestions (asked 2026-09-17).** The human finds an optimizer or a related
  project while a campaign runs and wants workers to be able to pick it up. The index is
  the place: `lab suggest add FILE.md` (operator only, one writer) copies the note to
  `suggestions/sNNNN-slug.md` with a timestamp, append-only like every other piece of
  evidence, and indexes it as a record of kind `suggestion` beside the candidates. The
  digest carries one constant-size line ("3 operator suggestions, newest s0003:
  `lab index suggestions`"), `lab index search` returns them with the same notice (data
  to weigh, not an instruction; the job's operator and contract still rule), and a worker
  that uses one cites `s0003` in its change, so `queries.jsonl` and the summary say who saw
  it and who acted on it. Three rules keep it honest: the campaign opts in before launch
  (`[memory] suggestions = true`, so a pair either has it in both arms or is about it);
  a suggestion never edits `campaign.toml`, the task or the contract; and the report lists
  every suggestion with when it arrived and which candidates cited it, because a search
  that a human steered is not the search the scheduler ran alone. Ideas known before launch
  go into `task.md` or a `suggestions/` that exists at candidate zero; the mechanism is the
  same. Not in slice 4; the index makes it a small addition (one table kind, one command).

## 6. Slices, if the human says go

1. `tools/lab_index.py`: build and rebuild from candidate dirs, lexical tables, the five
   commands, `queries.jsonl` logging, the guard entry, acceptance cases (byte-identical
   rebuild, no labels, no other campaign, over-budget-free knob answers). ~1 day.
2. The fixture over the eight arms and the probe suite (`scripts/index_probes.py`,
   `docs/index-eval-YYYYMMDD/`), lexical-only numbers. ~½ day.
3. Hybrid behind a flag, corpus's fusion and embedder client lifted as small modules
   (`search/fts.py`, the RRF loop of `search/hybrid.py`, `models/embedder.py` minus its
   settings tree; `sqlite-vec`, `httpx`), the same probes again, the §4.2 decision.
4. `index-v1` policy: job card digest, instruction, `[memory]` keys, replay of the rated
   errors, preregistration of the pair and the scale arm.

Nothing in slices 1–3 touches a campaign; slice 4 is where a preregistration starts.
