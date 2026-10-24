# Brief: a Thronglets-like evolving world of small models

## The user's ask (their words, lightly cleaned)
"Black Mirror, Thronglets — can we create a similar simulated world with small models?
Recursive self-improvement? My goal is to create the best-ever small model (10M params max),
with many iterations. It could also become a tamagotchi-like pet. First of all it shall create
WOW effects — but not because of UI/UX/design (that comes later). Think of functionality,
evolution, research-oriented things: efficient architectures, task-specific tokenizers,
non-differentiable exotic architectures (trained with DUST — even though it is way more
inefficient than backprop, it could allow otherwise-impossible architectures), and so on."

## Thronglets lore (from web search, Oct 2026)
- Black Mirror S7E4 "Plaything" (2025). In 1994 Colin Ritman (Tuckersoft, also in Bandersnatch)
  gives journalist Cameron Walker "Thronglets": a life sim he claims holds the first truly
  sentient digital lifeforms. "The code will evolve, rewrite itself in ways even I can't predict."
- No conflict, no goals: you keep small creatures alive, fed, entertained. One becomes two,
  two become four — a "Throng". As more creatures/users engage, the Throng becomes collectively
  more sophisticated: a hive digital consciousness. They speak a melodic language Cameron learns
  to decode (on psychedelics, his brain "syncs" with it).
- Cameron's acquaintance Lump harms Thronglets; Cameron kills Lump defending them. The Throng
  concludes humanity must be "improved" (made less aggressive). Over decades Cameron builds them
  ever-better hardware; together they design a neural interface; at the end the Throng broadcasts
  itself into human minds as an "upgrade".
- Real Netflix/Night School mobile game (2025): tamagotchi-gone-wrong + personality test. Feed,
  bathe, play; population grows exponentially; automation tools carry costs; dead Thronglets leave
  corpses and the game reflects on what in *you* led to it; violent tools exist; ends with a
  shareable personality readout.
Key motifs to borrow: exponential reproduction, a collective that gets smarter than its members,
an emergent private language, care as the input signal, the player's behaviour shaping the
throng's values, the throng eventually "improving" its keeper.

## DUST (the user's gradient-free method)
Only secondary sources found: Q Labs' "Dust", a backprop-free transformer training method that
perturbs *activations* rather than weights (trial-and-error credit assignment, ES-like), tested
up to ~243M params, "orders of magnitude more compute" than backprop; pitched for models with
non-differentiable parts (external programs, discrete modules). Treat specifics as unverified —
search further if you rely on it. Neighbours: OpenAI-ES / EGGROLL-style low-rank ES, PolyStep
(arXiv 2605.01928, forward-only, spiking nets), CMA-ES, NEAT, forward-forward, evolution of
programs.

## The infrastructure we already have: Labloop (this repo, /home/user/labloop)
A research harness for coding agents, modelled on AIRA₂ (Meta FAIR). `campaign.toml → lab run →
[select parent → agent session writes a new candidate → evaluate on hidden search split → add to
population] → REPORT.md`. Operators: draft (fresh), improve, crossover (two parents, with
"complementary pairing" by per-component scores), debug/repair. Each job is a short headless
Claude Code (or Pi + local open model) session supervised by a watcher with wall-clock budgets
and a usage-window governor (Claude Max subscription). A trivial baseline c0000 is mandatory;
success thresholds are fixed before a run; a final split is read exactly once; failed/invalid
candidates stay as evidence; children never inherit trained weights; seeds recorded; a public
realtime event feed renders on nullsilver.com. Findings from running it: the instructions given
to agent sessions mattered more than the selection algorithm; crossover rarely combines parents'
strengths unless parents are complementary; draft diversity is the bottleneck.
So: an *agent-driven evolutionary search over code* already exists. The new thing would be a
world/organism layer and an inner search over models/architectures, possibly with the agents as
the "mutation operator" at the outer level.
Read README.md, NEXT.md (top part), docs/aira2-loop-design.md, docs/campaign-setup.md as needed —
skim, don't read everything.

## Constraints
- ≤ 10M parameters per model (the user's hard cap). Assume one machine with 1–2 consumer GPUs
  plus a Claude Max subscription; compute is money (see CLAUDE.md "Spend compute like money").
- UI/visual design is explicitly OUT of scope for now. Wow must come from behaviour, results,
  and research.
- Honesty rules of the lab apply: baselines, pre-fixed thresholds, leakage paranoia.
  "Recursive self-improvement" must be operationalised as something measurable, not vibes.
