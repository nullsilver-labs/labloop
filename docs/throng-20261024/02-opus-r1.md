# OPUS, round 1: THRONG, an evolving world of ≤10M-parameter language models

Status: independent proposal, nothing built or run. Each number is either cited (source in brackets),
marked *estimate*, or marked *unverified*.

## 0. Three facts that shape everything else

1. **There is already a public, falsifiable arena next door: OpenAI Parameter Golf** (Mar 18 to Apr 30 2026,
   github.com/openai/parameter-golf, README read 2026-10-24). The task: the best LM in a 16 MB artifact,
   trained in 10 min on 8×H100, scored in **bits-per-byte on FineWeb val (first 50k docs), which doesn't
   depend on the tokenizer**. Naive baseline 1.2244 (9L×512, vocab 1024, MLP×2, about 17M params *computed*,
   7.2B tokens). Final record **1.0565** (PR #2135, 3-seed mean). The non-record track lists a Universal
   Transformer (3 blocks ×4 loops, 4.95 MB) at **1.2249**, i.e. the baseline's score at about a third of the
   bytes; Mamba-3 hybrid 1.147; MDLM diffusion 1.147; H-Net byte-level 1.360. Records need +0.005 nats at
   p<0.01 over 3 seeds. These are the numbers to beat, and the significance rule to borrow.
2. **The user's cap is parameters, not bytes, and that changes which tricks matter.** Much of the PG frontier
   is compression: int6 GPTQ, AWQ, LQER, lrzip. Under a 10M-*parameter* cap, quantization buys nothing.
   What a param cap rewards is **reuse of each parameter**: depth recurrence, weight sharing, generated
   weights, test-time training, more compute per parameter. A pure param cap also has an obvious loophole
   (a 1M-param model looped 1000× per token). So the benchmark needs **two caps: ≤10M stored scalars and
   ≤F FLOPs/token at inference**. I propose F = 2× c0000's FLOPs/token, fixed in campaign.toml. Seed-generated
   "random" weights, n-gram tables and hash tables all count as stored scalars. That rule is written down
   before any run, because agents *will* find the loophole (PG's own top entry carries an n-gram component).
3. **Dust is real, fresh and narrow** (Q Labs, Dahal, Mandal, Gülbahar, Vegesna, Oct 2026, qlabs.sh/research/dust;
   code github.com/qlabs-eng/dust). It is node perturbation: Gaussian noise on the output of every linear layer,
   independent per token, so a 2048-token sequence is 2048 virtual population members. The credit for each
   token is its decayed future loss reduction, the reward-weighted noise gives the error at each layer's output,
   and the outer product with that layer's input gives the weight gradient. It was tested up to 243M params,
   **always at fixed *tokens*, never at fixed compute**. The headlines: below backprop at 100k and 1M tokens;
   at 20M tokens backprop's 4.633 is still better, and the authors' fitted *limit* of 4.431 is an extrapolation.
   About 10³–10⁴× more population-efficient than EGGROLL (arXiv 2511.16652, ICML 2026, low-rank ES; also did
   integer pretraining). Non-differentiable architectures (looped nets, external programs) are argued for
   and **not tested**. My reading: Dust buys sample efficiency and freedom from differentiability, and it pays
   in compute, about one forward pass per draw with populations of 256 to 16k. At ≤10M params, compute is the
   one resource we have plenty of *per sample*. So Dust fits a **data-starved** regime (a pet learning from
   its keeper) and **small discrete modules**. Pretraining the dense body with it would sink the compute.

## 1. Core concept

The world is **a population of language organisms competing to predict text they have never seen**.
- **Genome** = a candidate's code: tokenizer spec, architecture, training recipe, data policy, seed.
  Labloop already treats this as a candidate.
- **Phenotype** = the trained ≤10M model. It is always re-grown from the genome, never inherited.
- **Environment** = a data stream (FineWeb, plus later niches: code, TinyStories, a keeper's own text) and a
  compute ration (GPU-minutes per life).
- **Fitness** = bpb on hidden text, under the param and FLOP caps.
- **Reproduction** = an agent session that mutates or crosses genomes (the outer level), plus ES or Dust inside
  a genome for the parts backprop can't reach.
- **The throng** is more than the population. It has (a) **culture**: the shared library of finding cards and
  tested modules, which is inherited as text, not weights; (b) **a collective**: the ensemble of living
  organisms, which predicts better than any member; and (c) **its own mutator**: operator texts, library and
  tools, which the throng is allowed to rewrite. The motifs from the show map onto this directly. One becomes
  two is a mutation; the collective is smarter than its members, and that is measurable; the private
  language is an evolved tokenizer; care is the compute ration and the data diet; and the throng improves
  its keeper through findings written in plain language.

## 2. Recursive self-improvement, made measurable

| Level | What changes | Who changes it | Measured by |
|---|---|---|---|
| L0 | weights | SGD / Dust / ES inside a run | val bpb |
| L1 | genome (code) | agent workers (draft/improve/crossover) | search bpb |
| L2 | mutator = operator texts + library + tool modules + surrogate fitness model | a "reflect" job every N generations, written by the system, not the human | probe score (below) |
| L3 | the reflect policy itself | human only, for now | n/a |

Ordinary hill-climbing improves the *artifact*. RSI improves the *rate*, and on environments it was not tuned on.
**The metric:** freeze mutator snapshots M₀, M₁ … M_k. Each probe is a fresh, small campaign on a **held-out
environment** E′: a different corpus (e.g. code, or TinyStories), a different cap (≤2M params), its own c0000,
a fixed budget of 12 candidates × 10 GPU-min, and r ≥ 4 seeds. S(M_k) is the mean final-split gain over E′'s
baseline. The pre-registered claim reads **"RSI supported"** only if, at once:
(a) S(M_K) − S(M₀) > 2·σ_probe, with σ_probe measured on M₀ beforehand;
(b) S(M_K) beats **M₀ given extra budget equal to the compute it took to produce M_K**, the compute-matched control;
(c) the gain vanishes when M_K's library is ablated or shuffled, so we know the content carries it;
(d) the edits to L2 were written by the system.

Second signal, which is mechanical and cheap: the **surrogate**. A small model (≤10M, of course) predicts
rung-2 bpb from the genome diff plus the first 2 minutes of the loss curve. It is retrained on the
population as the population grows. **Recursion shows up as rising Spearman ρ against the true rung-2 score
and falling GPU-hours per unit of bpb improvement.** Here the throng learns to judge its own children, and
it is the only place where the small models do real work inside the improvement loop.
**Caveat from this repo:** across arms, labloop's harness-level finals had sd .121 (docs/meta-loop-plan.md §0),
and A3/A4 read not_supported. A null result is the likely first outcome, which is why the probes have to be cheap.

## 3. The "best ≤10M model" target

**Primary benchmark: PG-10M.** FineWeb bpb under PG's byte accounting.
- **Search split** = about 10k docs from a held-out FineWeb train shard.
- **Final split** = PG's official val, the first 50k docs. It is read once, so the result can be compared with
  PG directly.
- **Caps:** ≤10.0M stored scalars, counted by the evaluator from the checkpoint and not reported by the
  candidate; ≤2× c0000 FLOPs/token; score-first TTT allowed (PG-legal), anything else at test time is not.
- **c0000** = the PG naive baseline shrunk to fit: 9L × d384, KV-heads 2, MLP×2, vocab 1024, tied. That is
  about 9.7M params (*computed*), same recipe, rung-1 budget.
- **c0001 (reference, declared, not searched)** = the PG frontier stack transplanted to ≤10M with an agent's
  help: Muon, value embeddings, SmearGate, attention gates, U-Net skips, depth recurrence, score-first TTT,
  SP-k tokenizer. **This is the honest bar.** Beating the naive baseline says nothing new. Beating the
  transplanted SOTA at equal params and equal compute is what makes a claim.
- **Budget per candidate:** rung 1 is 20 min on the RTX 3090, about 0.4–0.8B tokens for a 10M model (*estimate*,
  around 40% MFU). Rung 2 (top 5 per campaign) is 2 h. Rung 3 (the champion) is 12–24 h, retrained from
  scratch. Our 24 h on one 3090 is roughly 1/4 to 1/6 of PG's 4-hour non-record budget (*estimate*).
- **Claims, pre-fixed:**
  - (i) Champion < c0001 by ≥0.005 nats/token-equivalent on the final split, 3 seeds, p<0.01. This is the
    "best ≤10M" claim.
  - (ii) Headline: the **effective-compute multiplier**, the factor of compute c0000 needs to match the
    champion. This is the modded-nanogpt-style way to say "evolved recipe = N× compute".
  - (iii) Stretch: ≤1.15 bpb at ≤10M params on PG val. That is better than PG's Mamba-3/MDLM entries with
    half or less of their params, a number a PG participant would find surprising.
- **Secondary, data-limited: BabyLM-strict-small-10M.** 10M words and ≤10M params, scored on BLiMP and the
  rest of the pipeline. 2024 strict-small leader was GPT-BERT (BLiMP ~81, the column reading is mine,
  *unverified*); the 2025 winner's numbers are *unverified*. This is where Dust's fixed-token advantage
  could matter.

**Where to spend the search** (prior from the PG and speedrun record histories): the optimizer and recipe
transplant takes most of the easy gain, and it should be done *once, by hand*, as c0001, not rediscovered
for 60 candidates. The search should go to what **depends on scale and is unknown at 10M**:
- vocab size vs. embedding share; at d384 an 8192 vocab is 3.1M of the 10M;
- depth / width / recurrence allocation under the FLOP cap;
- the tokenizer transform (PG's CaseOps bijection was worth about 0.002–0.01; a bigger search may find more);
- TTT variants;
- data ordering and selection.

Gradient-free compute goes only to §4 items 5–7.

## 4. Wow mechanisms

Every item has a kill criterion read on the final split, and its compute is in rung-1 units (20 GPU-min).

1. **The throng's own language: co-evolved tokenizers.**
   - *Mechanism:* GA over merge lists and bijective transforms (case, whitespace, digit splitting,
     morphological pre-splits). The fitness of a tokenizer is the rung-1 bpb of a *fixed* c0001 body
     sized to the cap.
   - *Why surprising:* the best vocabulary for a 10M mind is not the best for a 1B mind, and bpb lets
     us show it honestly.
   - *Claim:* the evolved tokenizer beats the best of SP{1024, 2048, 4096, 8192} by ≥0.01 bpb at equal
     params. *Kill:* below 0.005.
   - *Cost:* about 60 evals, about 20 GPU-h.
   - *Gradient-free:* yes, but GA over discrete specs. Dust is not needed.
2. **Think longer, store less.**
   - *Mechanism:* a looped transformer with per-token learned halting. Halting is discrete; train it with
     ES/Dust or REINFORCE, with backprop for the body.
   - *Claim:* a ≤3M-stored model at matched *average* FLOPs/token equals the 10M c0001. *Kill:* worse than
     fixed-depth recurrence at equal FLOPs.
   - *Cost:* about 30 rung-1 units.
   - *Dust:* honest, on the halting head only. **Required control:** a straight-through or Gumbel halting
     variant at equal compute.
3. **The collective outthinks its members, then gets distilled.**
   - *Measure:* the throng ensemble's bpb against the best member. PG never had an ensemble axis, because
     an ensemble breaks the cap.
   - *Then:* distil the ensemble into one ≤10M organism (logits on train data only).
   - *Claim:* the distilled child beats a from-scratch organism given the **lineage's total compute**,
     teachers included. *Kill:* the compute-matched from-scratch run ties.
   - This is the lab's weight-inheritance rule under test; see §6.
4. **A quality-diversity throng instead of one leaderboard.**
   - *Mechanism:* a MAP-Elites archive over (stored params 1–10M, FLOPs/token, vocab). It attacks
     labloop's own finding that draft diversity is the bottleneck (NEXT.md, A4).
   - *Claim:* the evolved Pareto frontier of bpb against params sits below c0000's scaling curve by a
     constant compute multiplier ≥2× across the whole range, not only at 10M. *Kill:* the multiplier is
     not consistent across sizes, which would be overfitting at one point.
   - *Cost:* rides along with the main search, plus about 20%.
5. **Dust in the data-starved regime, the pet's regime, replicated fairly.**
   - *Setup:* 100k / 1M / 10M tokens, a 2–8M model, Dust (public code) against *tuned* backprop with many
     epochs, heavy weight decay and dropout (the Slowrun lesson, github.com/qlabs-eng/slowrun). Q Labs
     compared at fixed tokens and does not say how well backprop was regularised (*unverified* detail).
   - *Claim:* Dust < tuned backprop at ≤1M tokens. *Kill:* tuned backprop ties or wins.
   - *Cost:* 1M tokens × pop 1k ≈ about 1B token-forwards, a few GPU-hours.
   - *Payoff:* it would be the first independent replication of a 2-week-old claim, and it decides
     whether a pet can learn from one person's text better with Dust.
6. **Non-differentiable organs.**
   - *Mechanism:* hard top-1 product-key memory or a hash-routed MoE inside the 10M, trained by Dust on the
     router and the lookups.
   - *Claim:* a gain at equal stored params and equal FLOPs over the dense model *and* over the STE-trained
     equivalent. *Kill:* STE matches Dust, in which case Dust adds nothing.
   - *Cost:* 50–300× a backprop step for the Dust-trained module only (*estimate* from 256 draws
     ≈ 256 forwards); keep the module small.
7. **ES on the exact metric.**
   - *Mechanism:* EGGROLL-style rank-1 ES over the few thousand scalars that backprop serves poorly: TTT
     learning-rate schedules, QK-gains, per-layer residual mixes (Dust itself uses weight-space ES for its
     residual scalars), halting thresholds. The fitness is post-TTT bpb on a calibration slice of train.
   - *Claim:* ≥0.003 bpb over the tuned values. *Kill:* below the noise floor.
   - *Cost:* cheap, forward passes only.
8. **The throng predicts its own children** (the §2 surrogate).
   - *Claim:* by generation 40, the surrogate's ρ ≥ 0.7 against rung 2, and using it to drop the
     predicted-bottom 50% of candidates before rung 1 gives an equal final at half the GPU-h.
     *Kill:* ρ < 0.4.
9. **The mutator rewrites itself** (the §2 probe). This is the actual RSI claim; its cost is the probes,
   about 4 seeds × 12 × 10 min per snapshot ≈ 8 GPU-h.
10. **Genomic bottleneck.**
    - *Mechanism:* a 1M-param "g-network" generates the 10M phenotype's weights. This follows the Zador
      line ("Encoding innate ability through a genomic bottleneck", bioRxiv 2021; PNAS version
      *unverified*). PG's LegendreGPT, where weights are a polynomial in depth, scored 1.2266.
    - *Rule:* under our counting, the *genome's* params count. The FLOP cap stops the abuse.
    - *Claim:* a 1M genome matches a 3M direct model. *Kill:* worse than a 1M direct model with equal
      FLOPs, via recurrence.
    - *Gradient-free:* backprop works through a hypernet; ES only if the generator is discrete
      (a CPPN/NEAT-style generator).
11. **Theme only: an emergent private language.** Two organisms solve a referential game over a discrete
    channel, and we measure topographic similarity. It is cheap and fun, it adds **nothing** to the best-model
    claim, and it is a pet feature, not research. I'd park it.

## 5. The tamagotchi layer as functionality

A pet is **one adopted lineage plus a private environment**. It is never a node in a research campaign.
- **Species** are the frozen genomes from research campaigns. A **pet** is an instance: a species phenotype
  plus a personal adapter, or Dust/TTT state, that learns from its keeper's text.
- **Feeding** means contributing text and choosing the diet (data shards). **Care** means a GPU-minute
  ration: neglect stops growth, and a killed run is a corpse, kept as evidence with its reason.
- **Growth is measured, not animated:** "your pet predicts *your* writing at X bpb; the generic champion
  predicts it at Y". This is read on a personal final split, the last 10% of the keeper's text, which is
  never trained on. There is also a small skill battery (copying, counting, BLiMP-style pairs) that the pet
  passes as it grows.
- **Budding:** at a milestone, the pet requests an agent mutation of its genome. The child grows from
  scratch in the keeper's environment, so the keeper's lineage evolves.
- **The keeper's selection is a separate operator, `keeper`,** with its own provenance. Any campaign that
  uses it is a different arm, and no research claim is read on it. That one rule keeps human preference
  from leaking into the claims.
- **The throng improves its keeper:** every settled finding card is turned into plain language
  ("at 10M params, a 4096 vocab beats 8192 by .012 bpb; here's the run").

## 6. Mapping onto Labloop

- **Campaign** = one epoch of the world (environment, caps, thresholds). **Candidate** = organism genome.
  **c0000** = the shrunk PG baseline; **c0001** = the declared transplant reference.
- **New tooling, in order of need:**
  1. **A model-artifact evaluator.** In language modeling the inputs *are* the labels, so labloop's split
     model breaks: no worker may see search or final text at all. The candidate exports a checkpoint and a
     `score(text)` entry point; the evaluator, run as `labeval` in the Docker sandbox with no network and
     no writable shared directory, counts stored scalars, measures FLOPs/token with a profiler, and computes
     bpb with PG's byte accounting. Candidate code running over hidden text could exfiltrate it, so the
     evaluator's outputs are limited to one score and the logs are scrubbed.
  2. **A `promote` operator.** Same genome, larger budget, new candidate dir, retrained **from scratch**.
     Multi-fidelity this way needs no exception to the weight rule.
  3. **Lineage-compute accounting**, so a distilled child carries its teachers' GPU-hours.
  4. **A frozen, tested `throng.es` module** (Dust, EGGROLL, a GA over discrete specs) that candidates
     import, so 60 agents don't each write a buggy ES.
  5. **Mutator snapshots and probe campaigns.** The labbench and meta-loop plan in the repo already sketch
     this; reuse them.
  6. **A MAP-Elites selection mode** next to rank and complementary pairing.
- **The weight-inheritance exception.** The rule exists so that no parent gets scored twice and so that
  fitness measures the genome. The world needs Lamarckian inheritance only for item 3 (distillation) and
  for pets. Make it a campaign key, `inherit = "none" | "distill" | "weights"`, frozen into
  population.json:
  - the claims of an inheriting campaign always read against a **from-scratch control given the full
    lineage compute**;
  - REPORT.md states the mode;
  - the research headline (§3 claim i) runs only under `inherit = "none"`.

  Selection on the search split over many generations of inherited weights overfits that split
  indirectly. The single final read stays the guard, and the search split is rotated between campaigns.
- **Honesty traps specific to this world:**
  - param-count loopholes: seeded random weights, tables, a TTT cache filled with data;
  - FineWeb val is public, so a worker with network access could fetch it (keep workers offline);
  - short-rung bias, where high learning rates win at 20 min;
  - "too good" TTT that is really leakage from overlapping documents.

## 7. The smallest first experiment, and the roadmap

**Stage 0, sub-day, about 6 GPU-h and about 10 Sonnet sessions:** calibrate the instrument before searching.
- Prepare PG's sp1024 FineWeb shards (cached in PG) and the search/final splits.
- Run c0000 at rung 1 with 4 seeds, giving σ_seed.
- Run c0000 and a hand-transplanted c0001 at rung 1 and rung 2.
- Run a 6-candidate Sonnet campaign (1 draft, 5 improves) from c0001 at rung 1, then promote the top 3.
- **Read three numbers:**
  - σ_seed, the noise floor (*my guess:* 0.002–0.005 bpb);
  - the transplant gap c0000 − c0001 (*guess:* 0.05–0.1);
  - Spearman ρ between rung 1 and rung 2.
- **Pre-fixed decision:** if ρ < 0.5, multi-fidelity is dead and rungs get redesigned before any search. If
  the 6 agents can't beat c0001 by more than 3σ, then agent mutation at this budget is the bottleneck, and we
  learn that for about $5 of usage.

In parallel on GPU 2: the Dust low-data replication at 100k and 1M tokens (item 5), about 4 GPU-h.

**Stage 1, about 1 week: the bar.** Build the evaluator, `promote` and the caps. Main campaign: 60
candidates from c0001, plus the tokenizer GA (item 1). Output: an honest ≤10M frontier number on PG val,
claim (i) read once, and the effective-compute multiplier.

**Stage 2, weeks 2–4: the throng.** MAP-Elites archive (item 4), recurrence with halting (item 2), Dust organs
(item 6), ES on scalars (item 7), and the surrogate (item 8). Every item has its own pre-registered threshold;
the population is one shared archive.

**Stage 3, month 2 and after: recursion and pets.** Mutator snapshots with probes on held-out environments
(item 9); the distillation lineage under `inherit = "distill"` (item 3); the pet layer on a frozen species
with a personal final split; BabyLM-10M/10M as the second environment.

## 8. Risks and doubts about this proposal

- **Transplant may already be the result.** The "best ≤10M" number may come almost entirely from c0001, the
  hand-ported PG tricks, with the agents adding noise-level gains. I'd count that as a valid finding, but not
  the wow the user wants. Stage 0 measures this first.
- **The RSI claim is likely to read not_supported** for a long time. Labloop's own harness experiments
  (A3/A4) were nulls at sd .121. Probes on held-out environments are the honest test and an expensive one.
  I'm not confident the effect is large enough to see on 1–2 GPUs.
- **Rung bias.** 20-minute rungs select fast learners, not the best 24-hour models, and ρ may be poor.
- **The caps are my invention.** A FLOP cap of 2× c0000 is arbitrary, and the user may only care about
  "10M params". If so, recurrence and TTT become nearly unbounded and the benchmark turns into a compute
  contest. That has to be decided before the run.
- **The Dust evidence is 2 weeks old, from the authors only, and at fixed tokens.** Its non-differentiable
  promise is untested. Items 5 and 6 may simply confirm that Dust is a compute sink at our scale. Both have
  STE / tuned-backprop controls so a null is informative.
- **The usage window.** 60+ sessions per campaign, plus probes. Pi with local models for improve jobs may be
  necessary.
- **The theme pulls toward spectacle.** The emergent language and pet features could absorb effort that
  belongs to the benchmark; I'd keep them behind Stage 1.
- **Unverified:** the 2025 BabyLM numbers; the PNAS status of the genomic-bottleneck paper; the current
  modded-nanogpt record (about 2–3 min for 124M to 3.28 loss, per secondary sources); and every throughput
  figure marked *estimate*.
