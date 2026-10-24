# OPUS, round 2: critique of FABLE's proposal, and a merge

## 1. Where FABLE is right and I was wrong, too narrow, or too dry

- **Inheritance that isn't weights is the better world model.** I proposed an exception to the lab rule,
  `inherit = "distill" | "weights"`. FABLE's framing needs no exception at all. A body is always retrained from
  scratch, and what a lineage carries is its tokenizer, its architecture, its curriculum and its library. That
  is the Thronglets story, and it keeps Labloop's rule intact. I concede: inheriting weights or logits becomes
  one marked arm at most, not part of the core design.
- **Moulting (3.8) is the best pet mechanism either of us wrote.** A pet that grows for weeks under a hard
  10M cap, and whose identity is curriculum plus memory rather than weights, is functional wow and a real
  continual-learning experiment. Its controls are good: naive fine-tuning, and retraining from scratch on
  everything. It replaces my "pet = adopted lineage + adapter".
- **Organism as architect (3.6) beats my surrogate.** Mine only predicted fitness. FABLE's also proposes child
  genomes, and FABLE's risk 5 is decisive. Until something other than Claude improves L1, every gain may just
  be Claude's prior from Parameter Golf and nanoGPT. A ≤10M architect trained on the LEDGER and racing Claude
  and random mutation is the cleanest test of "the throng improves itself" either of us has. I under-weighted
  the confound with Claude's prior.
- **`lift_k` is cheaper and sharper than my probe campaigns** for recursion at the level of artefacts. It
  measures what generation-k's artefacts do for a fresh random init, at matched compute, on another shard.
  My mutator probes stay as the L2/L3 test for later.
- **A micro-task suite in `components_key`** (arithmetic, copy, retrieval) gives behaviour you can show
  people and turns on complementary crossover. My headline of bpb alone was too dry.
- **Upward transfer (3.11)** costs 2 runs and asks a question researchers care about: do recipes found at
  10M transfer to 50–100M? Attach it to the tokenizer result.

## 2. Where FABLE is wrong, can't be falsified, or wastes compute

- **Curriculum inheritance as *generated text* (3.1, Exp 0) has a strongly negative prior.** bpb measures fit
  to *real* text. Replacing 30% of real tokens with samples from a 10M model, at matched tokens, substitutes
  low-quality data for good data. Expect lift < 0 from generation 1, before collapse even begins. The
  bundle's generation compute must also be charged to the child. **The fix:** a "teaching bundle" is the
  parent's *selection weights and ordering over real data*, plus programmatic task data. Model-based data
  selection has a positive prior, and it is still a curriculum inherited without weights. Generated text
  stays as one arm, expected to lose.
- **Throng beats ensemble (3.5) is true by construction.** When each member holds only part of the evidence,
  logit averaging cannot combine it, so communication wins whatever happens. The question that isn't trivial
  is whether k organisms with a channel beat **one** organism with the same total parameters and all the
  data. Asked that way, the throng breaks the 10M cap, and FABLE says so. It doesn't serve the best-model
  goal.
- **Emergent language (3.4) is its own research field and costs about 30 GPU-h.** Topographic similarity is
  fragile (FABLE's own risk 7), and none of it moves the ≤10M claim. Park it until after the benchmark
  result.
- **"Care makes identically seeded pets diverge" (3.7) is trivially true.** Different data gives different
  models, and an arithmetic diet gives arithmetic skill. It is pet functionality, not a research claim, and
  should not be reported as one.
- **The baseline is too weak.** A 4-layer model on GPT-2 BPE spends most of the 10M on a 50k embedding
  (about 6.4M at d=128). Comparing against "GPT-2-BPE clipped to the same vocab" is a strawman. Every gain
  would be inflated, which breaks the rule that a result too good to be true gets checked first. The controls
  should be SentencePiece/BPE trained on the same corpus, swept over vocab size, and the transplanted
  frontier stack.
- **TinyStories as the primary benchmark can't support "best-ever".** There is no external bar there. The
  claim needs one; PG-10M on PG's official validation set gives it.
- **POET task ecology (3.9)** needs 40 trainings, and transfer from open-ended tasks to a fixed suite has a
  low prior. Drop it from the first two stages.
- **Beneficial-mutation rate is confounded.** It falls as fitness approaches its ceiling and rises when
  mutations are small. Read it only at matched parent fitness, or against the random arm in the same window.

## 3. Merged design

**Core concept.**
- **An organism** is a genome plus a body. The genome holds the architecture DSL, the tokenizer spec, the
  recipe, and a curriculum policy over real data. The body is ≤10M params, retrained from scratch every
  generation.
- **The throng** is three things: the population, a shared culture (finding cards and tested modules), and an
  **architect organism** that learns from the LEDGER to propose children.
- **A pet** is one lineage living through moults in a private environment.

**RSI metric**, in three tiers, each with a pre-fixed control:
1. `lift_k`: the slope over k ≥ 3 must be positive, and it must survive another seed and another shard, at
   matched compute including the cost of making the artefacts.
2. **Architect vs Claude vs random**: the beneficial-mutation rate at matched parent fitness after 200
   evaluations. The architect counts only if it beats random by ≥10 points and its rate rises across the
   thirds of the campaign.
3. **Stage 3:** mutator probes on a held-out environment, against the original mutator given equal extra
   compute.

**Benchmark: PG-10M, as the headline.**
- **Metric:** FineWeb bpb with PG's byte accounting. The search split is from held-out train shards; the
  final split is PG's official validation set, read once.
- **Caps:** ≤10M stored scalars, ≤2× c0000's FLOPs/token at inference, and a training compute budget per
  rung, all enforced by the evaluator.
- **Baselines:** c0000 is PG's naive baseline shrunk to about 9.7M; c0001 is the transplanted PG frontier
  stack, and it is the bar.
- **Components, reported but not the headline:** arithmetic, copy and retrieval.
- **Claim:** beat c0001 by ≥0.005 nats, over 3 seeds, at p<0.01.

**Top 5 experiments, ranked by surprise × P(works) ÷ cost:**

| # | Experiment | Surprise | P(works) | Cost | Kill line |
|---|---|---|---|---|---|
| 1 | **Co-evolved tokenizer** for a 10M mind (+3.11 upward transfer to 50M) | med-high | ~0.5 | ~20 GPU-h | < 0.005 bpb over the best SP vocab sweep |
| 2 | **Think longer, store less**: ≤3M stored params, recurrence with halting, at matched average FLOPs; halting trained by Dust against STE | high | ~0.35 | ~10 GPU-h | no gain over fixed recurrence |
| 3 | **Architect organism** | high | ~0.3 | small; it rides on evaluations the campaign runs anyway | ≤ random at 200 evaluations |
| 4 | **Moulting pet** | med (functional wow) | ~0.5 | 1 training/day | ≤ retraining from scratch on everything |
| 5 | **Dust in the low-data regime** (100k–1M tokens, against *tuned* multi-epoch backprop): the pet learning from one keeper | high either way, since the claim is two weeks old | ~0.3 | ~4 GPU-h | tuned backprop ties |

Next in line, after these five:
- curriculum as data selection, with generated text as the arm expected to lose;
- MAP-Elites as a selection mode (infrastructure);
- hybrid organs trained by ES against Gumbel.

**The pet layer.**
- **Life cycle:** wake, sleep, moult. Care events are typed and logged: a feed sets the data diet, and a play
  episode becomes programmatic task data.
- **Growth** is measured on a *personal final split*, the keeper's held-out text, and on the micro-task probes.
- **The keeper's choices** go through a separate `keeper` operator that no research claim reads.
- **Findings** are reported back to the keeper in plain language.

**The first experiment, sub-day, about 10 GPU-h on 2 GPUs.** Calibrate the instrument, with FABLE's
Exp 0 run alongside on GPU 2.
- **GPU 1:** c0000 × 4 seeds at rung 1 (20 min); 8 genomes (c0000, c0001 and 6 hand variants) at rung 1 and
  rung 2 (2 h).
- **GPU 2:** three arms of Exp 0 for 2 generations at 15 min × 2 seeds: real data only, real data plus a
  generated bundle, and real data plus a parent-selected real curriculum.
- **Pre-fixed kill lines:**
  - If σ_seed > 0.01 bpb, or Spearman ρ between rung 1 and rung 2 is < 0.5 across the 8 genomes, **no
    search campaign launches** until the rungs are redesigned.
  - If `lift_2` ≤ 0 on both seeds for an inheritance arm, that arm is dropped.

## 4. Disagreements for a human to decide

1. **The headline benchmark.** PG-10M against an external bar (OPUS), or TinyStories plus a micro-task suite
   (FABLE). The micro-tasks show behaviour better; only PG-10M supports "best-ever".
2. **What the teaching bundle contains.** Text the parent generates (FABLE), or the parent's selection and
   ordering of real data (OPUS).
3. **Emergent language and the throng's channel.** Stage 2 (FABLE), or parked until after the benchmark result
   (OPUS).
4. **An inference FLOP cap.** OPUS wants one to close the loophole of looping a model or using random weights;
   FABLE caps only training compute. Without it, "10M params" turns into a compute contest.
5. **How strong the baseline is.** GPT-2-BPE with 4 layers (FABLE), or the shrunk PG baseline plus the
   transplanted stack (OPUS).
6. **Is care a research claim?** FABLE says yes (3.7); OPUS says it is functionality only.
