# FABLE, round 2 — critique of OPUS and a merged design

## 1. Where OPUS is right and I was wrong or vague

- **Benchmark.** I waved at "TinyStories or FineWeb-edu". OPUS found the arena next door: Parameter Golf (openai/parameter-golf, verified today: 16 MB artifact, 10 min on 8×H100, tokenizer-agnostic BPB on FineWeb val, naive baseline 1.2244; the 1.0565 record I could not re-verify). A number a PG participant recognises beats ten nobody can place. Concede.
- **Two caps.** I named compute leakage but only for training. The inference cap (FLOPs/token) closes the loophole I left: a 1M model looped 1000×. Concede, with "seeded weights and tables count as stored scalars".
- **c0001, the transplanted SOTA as the bar.** My baseline was the naive one; beating GPT-2-BPE + AdamW at 10M says nothing in 2026. The most important correction. Concede.
- **Evaluator.** In LM the inputs are the labels; my "write predictions on search inputs" leaks the search text to every worker. OPUS's checkpoint + `score(text)` under `labeval`, offline, scalar out, is the only honest shape. Concede.
- **Dust.** OPUS read the primary (node perturbation, per-token population, 243M at fixed tokens, non-differentiable claims untested); "data-starved regime and small organs" is sharper than my "organs only". Concede.
- **My architect organism** writing child genomes is a Stage-3 fantasy; OPUS's surrogate (predict rung-2 BPB from genome diff + early loss curve; rising ρ, falling GPU-h per gain) is the achievable form. Surrogate first, proposer only if ρ ≥ 0.7.
- **Rungs with `promote`, lineage-compute accounting, the quarantined `keeper` operator, the personal final split.** All better-specified than mine. Concede.
- **My Experiment 0 was aimed at the wrong regime.** At 0.5B FineWeb tokens per rung, 30 % of data written by a 10M parent will lose BPB. Text inheritance can only pay where data, not compute, is the limit: OPUS's data-starved environment.

## 2. Where OPUS is wrong, too conservative, or kills the wow

- **PG-10M as spine turns the world into a speedrun.** OPUS's "where to spend the search" is vocab size, depth/width, TTT variants, data ordering: agent-driven NAS with a leaderboard. The motifs become metaphors. "The private language is an evolved tokenizer" is false: a tokenizer is one organism's reading habit, not something two organisms say to each other. "The collective is smarter" as a logit average is known to work and is PG-illegal. An ensemble plus a findings library is a PG retry, not a world.
- **Can the Nursery sit on top of PG? Yes, as floor, not spine.** PG supplies metric, caps, baseline, bar. The world supplies what PG cannot measure: **lineage** (what passes down that isn't weights), **collective** (what k organisms do that no ensemble does), **self-judgment** (the surrogate). Each is its own pre-registered claim; none is read as "best ≤10M".
- **Parking the emergent language is a mistake,** for a narrower reason than I gave. It adds nothing to the best-model claim, agreed. But it is the one mechanism where the collective does what no member or ensemble can (evidence split across shards, ≤8 symbols to share), where gradient-free is *necessary*, and where ≤2M models suffice. Merge it with the throng-vs-ensemble test so it earns its place by a measured collective advantage with a kill line.
- **OPUS's only inheritance is logit distillation,** which needs the `inherit` exception and can never go near the headline. A deduped text bundle lives inside `inherit = "none"`; a lineage can compound without touching the weight rule.
- **The FLOP cap as a hard wall kills a species.** "Think longer, store less" is an organism beyond 2× c0000 FLOPs/token. Make FLOPs/token a QD-archive axis with the 2× cell as the PG-comparable headline.
- **The Tier-2 RSI probe is right, expensive and likely null** (OPUS says so; A3/A4 agree). Put a cheaper tier under it.

## 3. The merged design

**Core concept.** A population of ≤10M-parameter language organisms under Labloop, scored in BPB on FineWeb under two caps (≤10M stored scalars; FLOPs/token as an archive axis, 2×-c0000 cell as headline), against a shrunk naive c0000 and a hand-transplanted c0001. Bodies are always regrown from the genome. The throng is lineage, collective and self-judgment, measured separately from the PG number.

**RSI metric, two tiers.** Tier 1, cheap: *artefact lift* — a fresh random-init organism trained with generation-k artefacts (tokenizer, bundle, recipe) minus the same organism with generation-0 artefacts, matched compute, different seed and shard; recursion claims a positive slope over ≥3 generations against a random-mutation control. Tier 2, OPUS's: mutator snapshots probed on held-out E′, S(M_K) − S(M₀) > 2σ_probe, beating compute-matched M₀, vanishing under library ablation, system-written. Tier 1 may be supported while Tier 2 is null; the report says which.

**Benchmark.** PG-10M primary (search = held-out train shard; final = PG val first 50k docs, read once). E′ = data-starved: a BabyLM-strict-small-style 10M-word corpus, ≤2–4M params, 5-minute rungs. E′ serves Dust, text inheritance and the Tier-2 probes at once.

**Top 5 wow, by surprise × P(works) ÷ cost.**
1. **Think longer, store less**: looped body, learned halting trained by ES/Dust on the head only, Gumbel/STE control. A ≤3M-stored organism matching 10M c0001 at equal average FLOPs/token. Kill: worse than fixed-depth recurrence at equal FLOPs.
2. **Co-evolved tokenizer**: GA over merges and bijective transforms on a fixed c0001 body. ≥0.01 BPB over the best SP vocab; kill < 0.005.
3. **Throng communicates**: shard-split QA, ≤2M organisms, 64-symbol channel, REINFORCE/ES. Claim: throng ≥ calibrated ensemble + 5 points *and* topographic similarity > shuffled control by 0.15; kill: either fails on 2 seeds. Cheapest, most surprising, P ≈ 0.3.
4. **QD frontier**: MAP-Elites over stored params × FLOPs/token × vocab. Claim: a constant ≥2× compute multiplier over c0000's scaling curve across sizes; kill: inconsistent across sizes. Rides along.
5. **Surrogate self-judgment**: ρ ≥ 0.7 by generation 40, equal final at half the GPU-h when the predicted-bottom half is dropped; kill ρ < 0.4. Near-free, and the first mechanical rung of recursion.
Behind them: Dust replication in E′ (informative, not wow), text inheritance in E′, genomic bottleneck, Tier-2 probes.

**Pet layer.** OPUS's frame: a species phenotype plus personal state, fed by the keeper's text and a GPU-minute ration, measured on a personal final split and a skill battery; `keeper` never feeds a claim. Add my **moult**: every N days a child is regrown from scratch on the pet's accumulated personal data and bundle and replaces the parent only if it beats it on hidden probes. The cap holds, forgetting is measured against naive continual fine-tuning, and identity is curriculum, language and memory. Dust/TTT live here, where tokens are scarce.

**First sub-day experiment (two GPUs, ~6 GPU-h each, ~10 Sonnet sessions).** GPU 1, OPUS's Stage 0 unchanged: c0000 × 4 seeds for σ_seed; c0000 and c0001 at rungs 1 and 2; 6 candidates from c0001; promote top 3. Pre-fixed: rung ρ < 0.5 kills multi-fidelity; agents not beating c0001 by 3σ_seed says agent mutation is the bottleneck. GPU 2, the premise in its proper regime: in E′, a 2M body, 5-minute rungs, 2 seeds; arm A = real words + a 30 % teaching bundle from a generation-1 parent, arm B = same token count of real words. **Kill line:** A − B ≤ 0 on both seeds on E′'s final ends text inheritance; A − B > 2σ_seed opens Tier 1 for Stage 2. Alongside: Dust vs tuned backprop at 100k and 1M tokens.

**Roadmap.** Stage 1 (weeks 1–2): evaluator, caps, `promote`, 60-candidate PG-10M campaign + tokenizer GA; the bar, read once. Stage 2 (weeks 3–5): QD archive, looped halting, throng communication, surrogate, Dust organs. Stage 3 (month 2+): Tier-2 probes, pets with moults, inheritance lineage in E′.

## 4. Remaining disagreements, for a human to decide

1. **Emergent language: research (FABLE) or theme to park (OPUS).** ~20 GPU-h of ≤2M models; does a measured collective advantage over an ensemble count as a result?
2. **Inheritance.** OPUS: logit distillation under an `inherit = "distill"` exception. FABLE: ban weight and logit inheritance from research campaigns; allow only deduped text artefacts, no exception needed.
3. **FLOPs/token: hard wall at 2× (OPUS) or archive axis with 2× as headline cell (FABLE).** Clean PG comparison versus a living "think longer" species.
4. **Budget split.** OPUS puts every world mechanism behind the Stage-1 bar; FABLE wants one world claim per stage from Stage 0. The user asked for wow; a PG number alone may not be it.
5. **Whether a ≤10M model ever becomes the mutator.** OPUS: surrogate only. FABLE: proposer if ρ ≥ 0.7, as the one place an organism joins its own evolution.
