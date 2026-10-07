# bits — a generated benchmark for comparing the loop

A CPU-only task family for testing changes to the lab itself (selection, memory, job
cards), not a model. Every world is a hidden random source over 16 symbols. Workers
see training documents and predict a distribution over the last symbol of each
search and final document. The score is the **fraction of the gap closed** between
the training unigram (0, candidate `c0000`) and the source's own conditional
distribution (1), in bits.

Why this shape:

- **No model knows the answer.** The source is drawn from a secret, after any
  training cutoff, so its structure has to be found in the data.
- **Graded credit.** The source stacks mechanisms of similar size, so a campaign that
  finds two of them scores visibly between one that finds one and one that finds
  three. That is the signal a memory or selection change should move.
- **Cheap and exact.** Scoring involves no randomness. A mini-campaign is about 30–45
  minutes on two CPU slots, so the noise from LLM sessions is beaten with replicates,
  not with a longer run.

## The source (operators only; never in a worker's reach)

| Branch | What it is | What finds it |
|---|---|---|
| regime | three sticky regimes (switch 1/300), each a variable-order Markov model, depth 1–3 by last symbol | n-grams get the pooled part; inferring the regime within a document gets the rest |
| copy | ~20% of symbols repeat the same document from a random offset 32–1024, 95% fidelity | a match model (an LZ77-style idea) |
| rule | ~9% of positions: `t ≡ φ (mod P)`, `x_t = (x_{t-a} + c·x_{t-b} + k) mod 16` | looking at per-position statistics in the data |

`FAMILY` in `world.py` holds the knobs. Changing them makes a new family, and a new
family needs a new calibration.

## Calibration (2026-10-07, three worlds, search split)

| probe | w1 | w2 | w3 | what it is |
|---|---|---|---|---|
| unigram | 0.000 | 0.000 | 0.000 | the baseline, 0 by construction |
| ngram | 0.274 | 0.207 | 0.287 | interpolated order-4 n-gram, the obvious first draft |
| generic | 0.322 | 0.261 | 0.374 | n-gram + match model + document cache, blind to the mechanisms |
| reference | 0.902 | 0.906 | 0.922 | knows the parameters, infers the latents (1000 queries) |

Notes on the table:
- **Scoring noise.** It's about ±0.014 per split at 4000 queries for a fixed
  predictor, and smaller for a paired difference on the same queries.
- **The practical ceiling is about 0.9, not 1.** The source knows when a copy starts;
  no predictor can.
- **Per-branch bits** in `calibrate.py`'s output show which mechanisms a probe found.
  The n-gram does worse than the unigram on rule positions.

**Still to do before the first real pair.** Run a single Claude draft (Sonnet, full
turn budget) on a fresh world. If it closes most of the gap on its own, the family is
too easy for loop comparisons: make the rule or regimes harder and recalibrate. Fix
`success_threshold` from that, before any arm runs.

## Making a world

```sh
export LAB_PRIVATE=~/.local/share/labloop-private
mkdir ../labloop-bits-w1 && cd ../labloop-bits-w1 && git init
python3 ../labloop/benchmarks/bits/world.py gen w1 . $LAB_PRIVATE/bits-w1 \
    --scaffold --python /path/to/venv/bin/python --threads 4 --minutes 5
../labloop/scripts/sync-project.sh .
tools/lab campaign check
```

What this does:
- **Generation** takes about 12 s and writes about 10 MB of inputs.
- **Labels and `world.json`** (the parameters) go to `$LAB_PRIVATE/bits-w1/`.
- **The secret** is `$LAB_PRIVATE/bits.secret`, shared by every campaign there. Two
  arms that name the same world get identical data, and that is what pairing means
  here. Keep the secret; it is the only way to regenerate a world.
- **Calibrating a world:** `calibrate.py <project> $LAB_PRIVATE/bits-w1`, a few minutes.

## Running a pair

- **One change per pair.** Arms A and B differ in exactly one `campaign.toml` line, the
  change under test, and run on the same world name. Use a new world name per
  replicate (w1, w2, …) so nothing gets tuned to one world.
- **Measure the noise floor before claiming anything.** Run about six replicates of
  the unchanged loop, take the standard deviation of the per-world difference, then
  size the number of worlds as `n ≈ (2.8 · sd_diff / δ)²`, where δ is the smallest
  effect worth detecting. Write δ, n, the endpoint and the threshold in `PREREG.md`
  before launching.
- **Primary endpoint:** the final-split score averaged over worlds, read as a paired
  difference.
- **Secondary endpoints:** bits per branch of each arm's frozen candidate (rerun
  `calibrate.py`'s breakdown on its predictions), candidates until each mechanism
  appeared, repeated failures.
- **Pin to P-cores** on a hybrid CPU, so a job's speed does not depend on which core
  it lands on. On an i7-12700 the logical CPUs 0–15 are usually the P-cores (confirm with
  `lscpu --extended`: the P-cores have the higher MAXMHZ):
  `taskset -c 0-15 tools/lab watch start --op campaign … -- tools/lab run campaign.toml`.
  The E-cores stay free for the rest of the host.
- **Order:** alternate which arm runs first across worlds. Draw the order once per
  world and record it.

## Leakage

Workers get the project dir, not this repo, but on a single-user host they can still
read `../labloop/benchmarks/bits/`. That would not give them the labels, since the
secret is needed for that. It would give them the mechanisms, which spoils the
measurement as surely. So:
- run the evaluator as `labeval` (docs/labeval.md);
- keep labloop out of the worker's reach if the host allows it;
- and in any case check every arm's transcripts:
  `grep -l 'benchmarks/bits\|world\.py\|calibrate\.py' candidates/*/session*` must be
  empty. A hit makes that candidate invalid for the comparison, and the report says so.
