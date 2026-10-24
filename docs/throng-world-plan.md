# Throng: an evolving world of ≤10M-parameter models

Status: a design proposal written 2026-10-24 by an operator session. Nothing is built or run.
Two agents wrote it: FABLE, which leaned toward world-building and open-endedness, and OPUS,
which leaned toward rigour. Each wrote a proposal independently, then read the other's,
critiqued it and proposed a merge. The four rounds are kept verbatim in
[`throng-20261024/`](throng-20261024/). This file is the merge, plus the operator's
tie-breaks on what the two still disagreed about. Numbers marked *(agent-cited)* were read by
one of the agents and not re-checked here.

## The ask

The ask is a world like Black Mirror's *Thronglets*, run with small models, where recursive
self-improvement produces the best-ever model at ≤10M params over many iterations. It might
later become a tamagotchi-like pet. The wow has to come from behaviour and research results,
not from UI.

## The lore, and what each motif becomes

*Plaything* (Black Mirror S7E4, 2025): in 1994, Colin Ritman gives the journalist Cameron
Walker a life sim. He says its creatures are the first sentient digital lifeforms, and that
"the code will evolve, rewrite itself". There are no goals; you keep the creatures fed and
entertained. One becomes two, two become four, and the Throng grows collectively smarter than
any of its members. It speaks a melodic language that Cameron learns to decode. When someone
harms the creatures, the Throng decides humanity needs improving, and it ends up broadcasting
itself into human minds. Netflix's real mobile game adds exponential growth, automation tools
that cost something, corpses that stay, and a personality readout of the player.

| Motif | Mechanism here |
|---|---|
| "The code rewrites itself" | Lineages inherit their **genome** (architecture DSL, tokenizer spec, recipe, curriculum policy). The body is always retrained from scratch. |
| One becomes two, two become four | Labloop's operators: draft, improve, crossover, repair. |
| The Throng is smarter than its members | (a) shared culture (finding cards, tested modules); (b) a communicating collective, tested against a calibrated ensemble; (c) the throng judging and proposing its own children (surrogate → architect). |
| The private melodic language | A discrete channel between organisms, ≤64 symbols, trained gradient-free, with a decoder probe. |
| Care is the input signal | The keeper sets the pet's data diet and GPU ration. This is functionality; no claim is read on it. |
| Corpses stay | Labloop's existing rule: failed and killed candidates stay as evidence. |
| The Throng improves its keeper | Findings in plain language, and upward transfer: a tokenizer or recipe found at 10M, tried at 50–100M. |

## What both agents agreed on

1. **Headline benchmark: PG-10M.** OpenAI Parameter Golf (Mar–Apr 2026) scores bits per byte
   on FineWeb val, a metric that doesn't depend on the tokenizer *(agent-cited: naive baseline
   1.2244 at about 17M params, final record 1.0565)*. Here it is re-capped for parameters
   instead of bytes:
   - **≤10M stored scalars**, counted by the evaluator from the checkpoint. Seeded "random"
     weights, n-gram tables and hash tables all count.
   - **a cap on inference FLOPs per token**, or a 1M-param model looped 1000× wins.
   - **a training-compute budget per rung**.

   The search split comes from held-out train shards. The final split is PG's official val,
   read once. Only an external bar can support "best-ever"; TinyStories has none.
2. **Two baselines.**
   - `c0000`: PG's naive baseline shrunk to about 9.7M (9L × d384, vocab 1024, tied).
   - `c0001`: the PG frontier stack hand-ported to ≤10M, declared and not searched (Muon,
     value embeddings, U-Net skips, depth recurrence, score-first TTT, SP tokenizer). **It is
     the bar.** Beating `c0000` alone says nothing in 2026.

   Headline claim: beat `c0001` by ≥0.005 nats on the final split, over 3 seeds, at p < 0.01.
   It is reported with the effective-compute multiplier: how much more compute `c0000` needs
   to match the champion.
3. **Micro-tasks as components.** Arithmetic, copy and retrieval are reported per component,
   which turns on complementary crossover. They are behaviour you can show; they are not the
   headline.
4. **No weight or logit inheritance in research campaigns.** What passes down is information
   that isn't weights, so Labloop's rule holds with no exception. Distillation can be at most
   one marked arm, compared against a from-scratch control given the whole lineage's compute.
5. **Dust is narrow.** Q Labs, Oct 2026, read from the authors' own page *(agent-cited)*.
   Node perturbation on each linear layer's output, independent per token, tested up to 243M
   params. It was always compared at fixed *tokens*, never at fixed compute. It beats backprop
   only at 100k–1M tokens, and its claims for non-differentiable architectures are untested.
   - **Where it fits:** the data-starved regime (a pet learning from one person's text), and
     small discrete organs: halting heads, hard routers, product-key lookups.
   - **Where it is a compute sink:** pretraining the dense 10M body.
   - Every Dust result needs its control: tuned multi-epoch backprop, or STE/Gumbel at equal
     compute.
6. **Generated-text curricula lose where compute is plentiful.** At 0.5B FineWeb tokens per
   rung, swapping real tokens for a 10M parent's samples lowers bpb before collapse even
   begins. On PG-10M the inherited curriculum is the parent's **selection and ordering of real
   data** plus programmatic task data. Generated text is tested only in the data-starved world
   E′, as an arm expected to lose.
7. **The pet is a lineage living through moults.** Wake (tasks), sleep (train on the day's
   care log), and every N days a moult: a child is regrown from scratch on the pet's personal
   data and curriculum, and replaces the parent only if it beats it on hidden probes.
   - The cap holds, and identity is curriculum plus memory, not weights.
   - Growth is read on a personal final split (the keeper's held-out text) and a skill battery.
   - The keeper's choices go through a separate `keeper` operator that no research claim
     reads. "Care makes identical pets diverge" is trivially true and is never reported as a
     finding.

## Recursive self-improvement, measured

Ordinary hill-climbing improves the artifact. Recursion improves the rate of improvement, and
that improvement transfers. There are three tiers, cheapest first, each with a pre-fixed
control:

1. **Artefact lift.** Take a fresh random-init organism trained with generation-k's inherited
   artefacts (tokenizer, curriculum policy, recipe). Subtract the same organism trained with
   generation-0's artefacts, at matched compute, including the cost of making the artefacts,
   on another seed and another shard. The tier is supported if the slope over k ≥ 3 is
   positive against a random-mutation control.
2. **The throng judges its own children.** A ≤10M surrogate, retrained on the LEDGER as it
   grows, predicts the rung-2 score from the genome diff and the first minutes of the loss
   curve.
   - Supported if: ρ ≥ 0.7 by generation 40, and dropping the predicted-bottom half gives an
     equal final at half the GPU-hours.
   - Kill: ρ < 0.4.
   - Once ρ ≥ 0.7, the same model becomes an **architect** operator that proposes child
     genomes, racing Claude and random mutation. This is the only test that separates the
     throng's own improvement from Claude's prior knowledge of Parameter Golf and nanoGPT. The
     beneficial-mutation rate is read at matched parent fitness.
3. **The mutator rewrites itself.** Freeze snapshots of the operator texts and library, M₀ …
   M_K. Probe each with cheap fresh campaigns on a held-out environment E′.
   - Supported only if S(M_K) − S(M₀) > 2σ_probe, M_K beats M₀ given equal extra compute, and
     the gain vanishes when the library is ablated.
   - Labloop's own harness experiments (A3, A4) read not supported, so expect a null first.

## The top experiments

Ranked by surprise × P(works) ÷ cost. The probabilities are the agents' priors.

| # | Experiment | Claim / kill | Cost | P |
|---|---|---|---|---|
| 1 | **Think longer, store less.** A looped body with per-token learned halting. The halting head is trained by Dust/ES, against an STE control. | A ≤3M-stored organism matches the 10M `c0001` at equal *average* FLOPs/token. Kill: worse than fixed-depth recurrence at equal FLOPs. | ~10 GPU-h | ~.35 |
| 2 | **Co-evolved tokenizer.** A GA over merge lists and bijective transforms (case, whitespace, digits) on a fixed `c0001` body; then one upward-transfer run at 50M. | ≥0.01 bpb over the best of SP{1k, 2k, 4k, 8k}. Kill: < 0.005. | ~20 GPU-h | ~.5 |
| 3 | **The throng talks.** ≤2M organisms, each holding part of the evidence for a QA task, share ≤8 symbols from a 64-symbol channel (REINFORCE/ES), with a decoder probe for the "melody". | Throng ≥ calibrated ensemble + 5 points, *and* topographic similarity > shuffled control by 0.15. Also reported: one organism with the throng's total params and all the data. Kill: either fails on 2 seeds. | ~20 GPU-h | ~.3 |
| 4 | **A quality-diversity throng.** MAP-Elites over stored params × FLOPs/token × vocab, as a selection mode. It attacks Labloop's known bottleneck, draft diversity. | A constant ≥2× compute multiplier over `c0000`'s scaling curve across 1–10M. Kill: inconsistent across sizes. | +20% on any campaign | — |
| 5 | **Surrogate → architect.** Tier 2 above. | ρ ≥ 0.7; then architect > random by ≥10 points at 200 evaluations. Kill: ρ < 0.4. | near-free | ~.3 |
| 6 | **Moulting pet.** | After 14 days, ≤2-point loss on day-1 probes and ≥10-point gain on day-14 probes. Kill: ≤ retraining from scratch on everything at equal compute. | 1 training/day | ~.5 |
| 7 | **Dust replication in the low-data regime.** 100k / 1M / 10M tokens, 2–8M model, against *tuned* multi-epoch backprop. | Dust < tuned backprop at ≤1M tokens. Kill: tie. It decides whether pets learn with Dust. | ~4 GPU-h | ~.3 |

Behind those come: ES on the few thousand scalars backprop serves poorly (TTT schedules, QK
gains, residual mixes); hybrid non-differentiable organs (hard top-1 product-key memory,
hash-routed MoE) trained by Dust against STE; a genomic bottleneck (a 1M generator for the 10M
phenotype, where the genome's params count); and generated-text inheritance in E′. POET-style
task ecology is dropped from the first two stages, because transfer from open-ended tasks to
the fixed suite has a low prior.

## What Labloop needs

1. **A model-artifact evaluator. This is the blocker.** In language modelling the inputs *are*
   the labels, so Labloop's predictions-file contract leaks the search text to every worker.
   - The candidate exports a checkpoint and a `score(text)` entry point.
   - The evaluator runs as `labeval`, offline in the Docker sandbox, and does three things:
     counts stored scalars, profiles FLOPs/token, and computes bpb with PG's byte accounting.
   - It outputs one score and scrubbed logs.
   - Workers stay offline too, because FineWeb val is public.
2. **A `promote` operator.** The same genome on a bigger rung, in a new candidate dir,
   retrained from scratch. This gives multi-fidelity without breaking the weight rule.
3. **Lineage-compute accounting**, so an artefact's or a teacher's compute is charged to the
   child.
4. **A frozen, tested `throng.es` module** (Dust, EGGROLL-style low-rank ES, a GA over
   discrete specs) that candidates import, so sixty agents don't each write their own buggy ES.
5. **A MAP-Elites selection mode**, next to rank and complementary pairing.
6. **An architect operator** whose "session" is a local ≤10M model, not an LLM, through
   `worker_model_by_operator`.
7. **A persistent pet store** outside candidate dirs (care log, memory, curriculum), read-only
   to workers.

Honesty traps specific to this world:
- param-count loopholes: seeded weights, tables, a TTT cache filled with data;
- short-rung bias, where high learning rates win at 20 minutes;
- TTT gains that are really overlap between documents;
- a curriculum bundle that isn't deduped against the search text.

## Stage 0: one sub-day calibration on two GPUs

**GPU 1, the instrument:**
- `c0000` × 4 seeds at rung 1 (20 min), giving σ_seed;
- 8 genomes (`c0000`, `c0001` and 6 hand variants) at rung 1 and rung 2 (2 h);
- a 6-candidate Sonnet campaign from `c0001`, then promote the top 3.

**GPU 2, the premise in its proper regime:**
- E′ (a BabyLM-strict-small-style 10M-word corpus), a 2M body, 5-minute rungs, 2 seeds;
- arm A: real words plus a 30% teaching bundle from a generation-1 parent;
- arm B: the same token count of real words;
- alongside: Dust against tuned backprop at 100k and 1M tokens.

**Kill lines, fixed now:**
- σ_seed > 0.01 bpb, or Spearman ρ between rungs 1 and 2 < 0.5 across the 8 genomes → no
  search campaign launches until the rungs are redesigned.
- The 6 agents fail to beat `c0001` by 3σ_seed → agent mutation is the bottleneck at this
  budget. That's worth knowing for about $5 of usage.
- A − B ≤ 0 on both seeds on E′'s final split → text inheritance is dropped. A − B > 2σ_seed →
  Tier 1 opens for Stage 2.

**Roadmap:**
- **Stage 1 (weeks 1–2):** the evaluator, the caps and `promote`; a 60-candidate PG-10M
  campaign and the tokenizer GA. The bar, read once.
- **Stage 2 (weeks 3–5):** QD archive, looped halting, throng communication, surrogate, Dust
  organs.
- **Stage 3 (month 2+):** architect operator, Tier-3 probes, moulting pets, inheritance
  lineage in E′.

## The disagreements, and the operator's tie-breaks

These are proposals for the human to accept or overturn. Nothing is fixed until a
`campaign.toml` says so.

| Question | FABLE | OPUS | Tie-break |
|---|---|---|---|
| Inference FLOP cap | an archive axis, with 2× as the headline cell | a hard wall at 2× `c0000` | **Archive axis.** The headline reads only the 2× cell, so the PG comparison stays clean, and the "think longer" species survives. |
| Emergent language | research, in Stage 2, merged with the throng-vs-ensemble test | theme only, park it | **Run it, in Stage 2,** as experiment 3 with the added single-organism control. It is the one place the collective does something no member can, it is cheap at ≤2M, and it is the most *Thronglets*-like result available. It never feeds the ≤10M claim. |
| Teaching bundle | generated text | selection and ordering of real data | **Both, by regime.** Selection on PG-10M, generated text only in E′. Already agreed in round 2. |
| Distillation | banned from research campaigns | one marked arm | **One marked arm, outside the headline,** charged with the lineage's compute. |
| Organism as mutator | proposer once ρ ≥ 0.7 | adopted FABLE's architect in round 2 | **Gated: surrogate first, architect at ρ ≥ 0.7.** (In round 2 each agent ended up conceding to the other's original position.) |
| World claims before the bar? | one per stage, from Stage 0 | everything behind Stage 1 | **One cheap world claim from Stage 0** (the E′ inheritance arm), because the ask is wow. Nothing else before the bar is read. |
| Is care a research claim? | yes | no, functionality | **No.** Only the moult's forgetting claim is research. |

## Risks both agents named

- The ported PG tricks in `c0001` may be most of the result, with the agents adding gains at
  the noise level. That is a valid finding, just not the wow.
- The Tier-3 RSI test will probably read not supported for a long time.
- Dust may simply confirm it is a compute sink at this scale; the controls make that null
  informative.
- A lone 10M pet will not impress anyone in conversation. Its wow has to be measured
  trajectories, lineage and the collective.
- The usage window: 60+ sessions per campaign, plus probes. Improve jobs may have to move to
  Pi on local models.
