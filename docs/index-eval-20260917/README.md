# `lab index`, measured without a GPU (2026-09-17)

Slices 1–3 of `docs/experiment-index-plan.md`: the tool, a fixture of real experiments,
the replay of the rated errors, and the embeddings decision. No campaign ran and no
worker has used the index yet; what is measured here is whether the facts are *there to
be found*, not whether a worker looks.

## What was built

`tools/lab_index.py`, registered as `lab index`: `build`, `search`, `knob [--with KEY]`,
`knobs`, `open`, `lineage`, `best [--outside]`. One sqlite file with FTS5, rebuilt from
scratch from `population.json`, `finding.json`, `summary.md` and the candidate's knobs
file; two builds of the same campaign are byte-identical. The knobs table takes the whole
file, not the card's bounded copy (the first build used the card's copy and showed
`table_rows` as `{}` for five mem3 candidates: the card flattens nested values). A worker's
queries are appended to `queries.jsonl` in its own candidate dir. Nothing of a final split
is read. `build --as-of TS` keeps what had settled by then, which is what the replay uses.

## The fixture

`scripts/index_fixture.sh`: the nine finished Sonnet arms on engram w0 (three memory
pairs, the two drafts arms, the mixed arm) as one namespaced population. The plan said
eight arms and ~150 experiments; there are nine and **182 candidates** (173 without the
baselines), 1 575 text rows, 155 knob keys, 2 022 knob values. 2.5 MB, built in 0.3 s.
Lexical search p50 1.5 ms / p95 2.1 ms, `knob` p50 0.26 ms. The Pi arm is left out: another
model, and a lineage that keys its memory on metadata (`docs/pi-engram-20260916/READ.md`).

## Replay of the rated errors

`scripts/index_probes.py replay`, table in `replay.md`. From the 81 statements the mem2
and mem3 raters marked incorrect or unsupported, the 29 that are about a fact a lookup
returns (a knob's history, another candidate's recorded number, who is best) — not the
hedged mechanisms, the held-out-template misreading repeated nine times in mem3 legacy, or
arithmetic. For each, the arm's index is built as of the stating worker's launch and the
query is the one the instruction would ask for: the knob it changes or names, the candidate
it names, `best`, or a search for the idea.

| | |
|---|---|
| the contradicting fact is in what comes back | **24 of 29** |
| could not have been known at launch (the better candidate had not settled) | 5 |
| not reachable by the asked query | 0 |

Read with its limits. The 29 were chosen by the operator who wrote the tool, after
reading the raters' notes; "reachable" means the id and the value are in the output, not
that a worker would have read them; two verdicts lean on the output being short enough to
read (`batch_size`: the values and who, the direction needs the lineage; the 540-second
`heads` error needs two knob queries side by side). One error (mem3 F #190) became
reachable only with `--with holdout_wording_acc`, added because of it. The five
unknowable ones are all mem3 legacy "best in the population" statements on two slots:
true when the job card was written, false in the lab's final record. The index would not
have fixed them and the rating arguably should not count them.

All 16 errors replayed from the two findings arms are in the 24, the "never varied" and
"only recorded for c0005" ones among them: the bounded ledger elided or never held those
values, the table answers a knob in 150–450 bytes.

## Paraphrase probes, and the embeddings decision

24 questions (`paraphrase-probes.json`) written by a Sonnet session that saw the card
heads and no search tool: 12 easy, 12 hard ("almost no content words shared"), nine arms,
each with the set of candidates that genuinely tried the idea. A hit is any of them in
the top *k*.

| system | recall@1 | recall@5 | recall@10 | MRR |
|---|---|---|---|---|
| lexical (FTS5, `unicode61`, OR of terms, bm25) | 0.50 | 0.75 | 0.88 | 0.61 |
| lexical + porter stemming | 0.38 | 0.75 | 0.79 | 0.53 |
| vector only (bge-small-en-v1.5, 33 M, CPU) | 0.58 | 0.75 | 0.83 | 0.66 |
| hybrid (lexical + vector, RRF k = 60) | 0.54 | **0.83** | 0.96 | 0.67 |

Hard and easy probes score alike (0.75 / 0.75 lexical, 0.83 / 0.83 hybrid): the workers'
prose is long enough that a paraphrase still shares words with it somewhere.

**The rule fixed in the plan (§4.2): hybrid must beat lexical by at least 0.10 recall@5 or
the embedder is not a dependency. It beat it by 0.08 (two probes of 24). The index is
lexical by default.** Stemming is off: it lost three first places and won none.

Hybrid is kept, as an option and not a dependency (the human, 2026-09-17): a campaign names
an embedder in `[memory.embedder]` the way it names its worker model — any OpenAI-compatible
`/v1/embeddings` endpoint — and an unset embedder means lexical search. The numbers above
are reproduced through that path (`lab index build --embed-url …`, then
`index_probes.py paraphrase`): same table, 37 ms per hybrid query in pure Python over 1 575
vectors, vectors cached by content hash so the rebuild stays byte-identical (0.16 s), a dead
endpoint answers lexically and says so. Trying another model is a rebuild of the fixture
with another `--embed-model` and the same 24 probes.

What that does not settle. Two of hybrid's four misses returned a candidate that does the
asked thing and is missing from the expected set (`mixed:c0004` for "only inject at the
name tokens"), so the labels undercount both systems. 24 probes cannot separate 0.75 from
0.83. The embedder tried is a small general English model; the one the plan names
(LFM2.5-Embedding-350M) does not load in either llama.cpp image on this host
(`unknown model architecture: 'lfm2-bidir'`) and corpus's own quantised copy is in a volume
this user cannot read. And the fixture is 182 experiments of nine campaigns; inside one
campaign of 20–60 the lexical search has less to confuse. Embedding 1 575 rows took 112 s
on CPU, so a per-settlement update costs about a second.

## Next: slice 4

`[memory] mode = "index-v1"`: parents' cards in full, a digest of constant size, the
instruction to query before stating a change, `lab run` rebuilding the index after each
settlement, the guard naming the index file a machine file. Then the preregistration of
the pair (findings-v3 vs index-v1) and of the 60-candidate scale arm. The scale arm on the
local model needs the new world files first: on w0 Qwen3.8 reaches .997 at the draft
through the record-id shortcut, and nothing can be read off a ceiling.
