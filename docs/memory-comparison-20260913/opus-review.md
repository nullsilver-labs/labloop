# Critical review — legacy vs finding-card memory, engram w0 (2026-09-13)

Read-only analysis by an operator session that ran neither arm and is not the blinded
rater. Sources: both arms' `population.json`, `candidates/c*/{summary.md,job.json,
finding.json,out/memory_config.json}`; labloop `tools/lab_findings.py`
(`select_context`, `render_card`), `tools/lab_campaign.py` (`new_candidate`,
`read_summary`, `lineage`, `render_job_card`), and this directory's PREREG/STATUS/
mechanical. No labels, no split data, no `rating/`.

Both arms ran strictly sequentially (`max parallel 1`): every candidate had settled
before the next was dispatched (`population.json` `ended` timestamps, 11–15 min apart).
So **every repeat below is an information failure, never a dispatch race.**

Both arms' `contract.may_read` lists only `data/train`, `data/search`, `task.md` and the
*parents'* dirs (e.g. `candidates/c0013/job.json`). A worker is contractually unable to
read any non-parent candidate. The memory snapshot is therefore the **only** channel for
cross-branch information — and the legacy arm has none, only ids and numbers.

---

## 1. Redundancy audit

### Legacy arm (`labloop-engram-mem-legacy-20260913`)

| later | change | repeats | same knob+direction | named it? | in its lineage? | outcome |
|---|---|---|---|---|---|---|
| c0003 | AdamW `weight_decay` 0.0→0.01 | c0002 (wd 0.0→0.05) | yes | no | no (sibling, same parent c0001) | .3748 vs .3893 |
| c0004 | lr 3e-3→1e-3 **and** wd 0.0→0.01 (two changes) | c0002, c0003 | yes | no | no (sibling) | .0914 |
| c0008 | per-epoch held-out early stop + best checkpoint | c0005 (best-ckpt by periodic held-out eval) | yes | no | no (sibling, same parent c0002) | .3540 vs .4774 |
| c0013 | cosine LR decay over the budget | c0006 (cosine decay, from c0005) | yes | no | no (uncle) | .3395 vs parent .4443 |
| c0016 | canonicalize token ids before hashing | c0014 (word-canonicalized hashing) | yes | no | no (sibling, same parent c0001) | .3273 after c0014's .1492 |
| c0017 | cosine LR decay over the budget | c0006 **and** c0013 | yes | no | no (uncle, sibling) | .3568 |
| c0018 | table size ×4 | c0015 (table ×4, from c0005) | yes, other architecture | no | no | .5779 (arm best) |

**6 clearly wasted candidates (c0003, c0004, c0008, c0013, c0016, c0017), 1 borderline
(c0018), 0 deliberate replications.** Cosine LR decay was tried three times, regressed
three times, and no worker ever learned that. **Not one of the 19 legacy summaries names
a non-ancestor candidate** (`scratchpad/xref.py` over all `summary.md`): every `cNNNN`
mention is a parent or a first-parent ancestor. c0004 says so explicitly:

> "…in the same direction as the two other `improve` attempts on this parent (which also
> landed below c0001's fitness, per the population table on my job card; **I did not read
> their code or summaries, only their recorded fitness**)."
> — `labloop-engram-mem-legacy-20260913/candidates/c0004/summary.md:59-61`

That is the legacy memory in one sentence: it knows siblings exist, and nothing about them.

**Wrong conclusion the memory could have prevented.** legacy c0014 opens:

> "Parent: c0001 (fitness 0.3958740234375 in the population table; c0001's own held-out
> number was 0.5532 — **the population fitness is presumably from a different, later
> evaluation pass**…)"
> — `…/candidates/c0014/summary.md:3-5`

It is not: 0.3959 is `lab eval` on the hidden search split and 0.5532 is c0001's own
held-out-wording proxy. A finding card states this structurally (`search 0.395874 (n=…)`
in the header, and the prose line labelled "Local observation (**worker-reported, not the
search score**)", `lab_findings.render_card`). Legacy c0018 had to re-derive the same
distinction from scratch at candidate 18.

### Findings arm (`labloop-engram-mem-findings-20260913`)

| later | change | repeats | same knob+direction | named it? | in lineage? | card in its snapshot? |
|---|---|---|---|---|---|---|
| c0016 | second zero-init gate bias at non-name positions | c0015 (identical, same parent c0010) | **yes, verbatim** | no | no (sibling) | **no — `job.json` `findings.omitted` lists c0015 "over the byte budget"** |
| c0017 | dropout p=0.1 inside the projection MLP | c0011 (dropout p=0.1 on the projected memory) | same knob family, different site | no | no | no (c0011 not selected at all) |

**1 clearly wasted candidate + 1 borderline, 0 deliberate replications.** c0015 and c0016
are the same hypothesis word for word (both `finding.json` `report.change`: a symmetric
zero-init learned non-name gate bias), dispatched 11 minutes apart, .7067 vs .5692.
**The selector had chosen c0015's card and then evicted it for space** — the byte cap,
not the policy, produced the duplicate.

Repeat rate: **legacy 6–7 / 19 (32–37 %), findings 1–2 / 19 (5–11 %)**.

---

## 2. What the memory got right and wrong, mechanically

From the 20 stored `job.json` `findings` snapshots (`scratchpad/b.py`):

| | |
|---|---|
| mean snapshot size | 8832 B of 12288 (cap); 4–5 cards, never 8 |
| share of snapshot bytes spent on lineage cards (tier 0/1) | **56.6 %** |
| selection reasons, all jobs | 20 "direct parent", 27 "ancestor at distance …", 16 "did not beat its strongest parent; shares topics", 8 "shares topics", **4 "strongest measured candidate outside this lineage"**, 1 "strongest measured candidate" |
| legacy memory content for comparison | mean 1149 B parent summary (clipped at 1200) + 549 B lineage (400 B/ancestor, ≤4) = **1.7 kB**; population table 451 B in both arms |

**The "strongest measured candidate outside this lineage" slot did no useful work.** It
fired 4 times — jobs c0002, c0003, c0004, c0005 — and every time it selected **c0000, the
trivial baseline at 0.0625**, because `take(measured, …)` runs after the topical takes
have already consumed the stronger candidates. From c0006 onward it never fires at all.
Across the whole campaign the "strongest" slot surfaced exactly one card, the baseline.

**The cross-branch window froze on early, weak candidates.** Counting how often each
card appeared in a slot outside the reader's lineage: c0008 **9 times** (0.5679 — the
*weakest* non-baseline candidate), c0003 6×, c0000 5×, c0004 5×, c0010 3×, c0005 1×.
Two mechanisms cause this. (a) `select_context` sorts topical candidates by
`(-len(matched(c)), c["sequence"])`; topic sets are near-identical across this campaign
(every card carries 4–5 of `engram-memory, hashed-ngrams, gated-residual,
frozen-backbone, canonicalization/regularization`), so the tie-break is *lowest sequence*
— **oldest first, forever**. (b) The byte-budget loop pops the **last** tier-2 entry
(`idx = next(i for i in reversed(range(len(chosen))) if tier == 2)`), i.e. the most
recent/most topical picks, keeping the oldest. c0017's job is the clean illustration: the
selector chose c0016, c0015, c0014, c0010 and dropped all four, keeping only c0008.

**Strong results nobody ever saw.** Eight of twenty cards were shown to **no job at all**:
c0006, c0011, c0012, c0014, c0015, c0016, c0017, c0019 — including c0014 (0.8042,
context-free gate), c0012 (0.7502, scoped weight decay), c0011 (0.7391, dropout). The
three best cross-branch results of the second half of the campaign were invisible to
everybody, while a 0.5679 candidate was shown nine times.

**Defect:** every card's footer reads `Full summary: candidates/cNNNN/summary.md · code:
candidates/cNNNN/code/` (`lab_findings.render_card`), but `contract.may_read` grants only
the parents' dirs. For 3 of the 4–5 cards per job the card advertises a path the contract
forbids.

---

## 3. Idea quality

The Finding sections did carry information that could not be re-derived from code, and
at least two workers used it:

> "…but this lineage has already shown the held-out-wording proxy can move in the
> opposite direction from the hidden search score (**c0009 itself scored far better on
> search than on this same proxy, c0010 scored far worse**), so this is weak evidence at
> best."
> — findings c0018, `finding.json` `report.interpretation`

That requires two candidates' measured scores *and* their self-reported local numbers
side by side — what a card pairs and what neither arm's code contains. c0016 used its
snapshot correctly and still duplicated c0015, because c0015 was not in it:

> "Hypothesis: c0009's hard mask … scored far higher on actual search fitness than the
> parent's soft name-only bias despite a worse held-out-wording proxy."
> — findings c0016, `finding.json` `report.hypothesis`

The legacy arm re-derived everything from the parent's code, at length: its summaries
average 7.3 kB against the findings arm's 4.6 kB, and c0002, c0005, c0006, c0007, c0010,
c0013, c0015 and c0017 all open by restating the parent's architecture in a
near-identical paragraph — the legacy worker doing by hand what a card does
mechanically, and still learning nothing about siblings.

Where cards fell short: the six prose fields are all *worker rhetoric about one change*.
Nothing in a card says what the candidate's configuration **is**. c0019 had to infer
`TABLE_SIZE` 8192 vs 32768 from its two parents' Change lines; a `memory_config.json`
diff would have stated it. And `Topics` did no discriminating work at all — 19 of 19
cards drew from the same 6 slugs, so "shares topics" matched nearly everything and
degenerated into "oldest first".

---

## 4. Improvement proposals (ranked)

Preregistered measures, per PREREG: **(A)** `fraction_bad` over M+R statements about
prior attempts; **(B)** unacknowledged repeats. Prompt-cost bound: findings ≤ 2.0 × legacy.

**P1 — Evict oldest-first, and reserve a cross-branch floor.** Two changes in
`select_context`: in the byte-shrink loop pop the *lowest-sequence* tier-2 entry instead
of the last; and before any tier-1 ancestor beyond distance 1, reserve slots for ≥2
out-of-lineage cards (the coverage rule PREREG already measures). Effect: **B** directly —
c0016 would have seen c0015 and the one clear findings-arm duplicate disappears; **A**
mildly positive (fresher referents). Prompt cost: **zero** (same cap). Size: ~15 lines,
plus tests. Smallest killing campaign: replay-only — re-run `select_context` offline over
this campaign's 20 stored cards and count how many jobs would have received the card of a
candidate they duplicated. That costs no GPU and no tokens; preregister "≥ 6 of the 16
eligible jobs gain a second out-of-lineage card, and c0016 receives c0015" before running it.

**P2 — A knob ledger: one machine-readable line per settled candidate.** Add to
`build_card` a `knobs` object taken from `out/memory_config.json` (the task already
mandates it) plus a `knob_delta` against each parent, computed mechanically, never from
prose. Render **all** settled candidates as a single compact table above the cards —
`id · exec · search · Δ-vs-parent · knob_delta · topics` — at ~80–110 B each, so 20
candidates cost ~2 kB, roughly what the population table plus one evicted card costs
today. Every worker then sees *that* weight decay / cosine decay / table-size ×4 was
tried and how it scored, even when the full card does not fit. This is the single change
that would have caught all 6 legacy repeats and both findings repeats. Effect: **B**
large; **A** large (numbers come from artifacts, not prose, so a misquote is checkable).
Prompt cost: +2 kB ≈ +500 tokens (~1.85 × legacy, still inside the bound) if it replaces
the population table. Size: ~60 lines in `lab_findings.py` (a `knobs` field in the card
schema, a differ, a renderer) + `FORMAT.json` bump — the card schema is `finding-card/1`,
so this is `finding-card/2` and a new campaign. Smallest killing campaign: 8 candidates on
engram w0, `max_candidates 8`, preregistered on **B** only ("≤ 1 unacknowledged repeat vs
the 2 this arm's first 8 produced"), ~$4 and 1.5 GPU-h.

**P3 — Tier the bytes instead of the cards.** Full six-field prose for direct parents
only; ancestors and cross-branch cards render facts + Change + Topics (~350 B instead of
~1.5 kB). At today's cap that is 4 full cards' worth of room for ~12 short ones, so the
whole population fits from candidate 1. Effect: **B** large, **A** slightly negative
(less context per referent, so more room to misattribute). Prompt cost: neutral or lower.
Size: ~25 lines (a `brief` flag through `render_card`). Test: same replay harness as P1 —
measure cards-per-job and cross-branch coverage over the stored cards, then a preregistered
8-candidate arm if the replay says coverage reaches 100 %.

**P4 — Replace `Topics` slugs with a knob signature.** Topics were worker-chosen, nearly
identical, and therefore inert. Derive the diversity key from the `knob_delta` of P2
(`optimizer.weight_decay↑`, `schedule.cosine+`, `table_size×4`) and enforce **at most one
card per knob key**, negative results first. Effect: **B** large; kills the "oldest first"
degeneracy without any new bytes. Size: ~30 lines, depends on P2. Test: the same replay.

**P5 — Surface siblings and uncles explicitly.** Both arms' failures cluster at the same
shape: a parent with 3–8 children (legacy c0001 ×5, c0005 ×4, c0002 ×3; findings c0002 ×7,
c0009 ×4, c0010 ×2). Give the snapshot a dedicated tier-1.5 "other children of your
parent(s), and other children of your grandparent" slot, in *brief* form (P3), before any
distance-2 ancestor. This is the exact information c0003/c0004, c0005/c0008, c0015/c0016
needed. Effect: **B** large, cheap; **A** positive (it is the referent class workers most
often assert about). Size: ~20 lines. Test: replay, then the 8-candidate arm.

**P6 — Re-render the facts half of the card from artifacts, keep prose for the rest.**
`build_card` already separates measured facts from worker report; extend "measured" to
`out/memory_config.json` and to a mechanical `code/` diffstat against the parent. Two
concrete wins: it would have flagged legacy c0004's *two* simultaneous changes (a protocol
violation nobody noticed), and it makes a "Change:" line falsifiable. Effect: **A** large
— the rater's M-type statements become checkable against a field that was itself built
from the source. Prompt cost: +~120 B/card. Size: ~50 lines; needs a campaign-declared
config path in `campaign.toml`, so it is not free. Test: build cards offline for both
existing arms and count how many `report.change` lines the mechanical diff contradicts —
no campaign needed to kill it.

**P7 — Contradiction flags, not contradiction detection.** Full semantic contradiction
detection between cards needs a model call and breaks `lab_findings`'s stdlib-only,
no-model-calls contract (module docstring). The cheap 90 %: with P2's knob deltas, mark in
the rendered context any knob that has been tried ≥ 2 times with disagreeing direction of
Δ-vs-parent — one line, purely arithmetic. Effect: **A** moderate (workers stop asserting
"X helps" from n=1). Size: ~15 lines on top of P2.

**Not recommended.** Embeddings or a shared "forum" cost a model call per dispatch and a
new failure mode inside the one component whose value is that it is deterministic and
auditable; P2+P4 buy the same diversity for ~2 kB of arithmetic. Raising `max_bytes`
alone (the pilot's open choice) is the *worst* option here: it buys more of the same
oldest-first cards at linear prompt cost and would not have fixed c0016, because the
eviction order, not the cap, decided what was dropped.

Ordering: P1 is free and replay-testable today; P2 has the largest effect per byte and
is the prerequisite for P4/P7; P3 and P5 are cheap and independent; P6 is the only one
that moves **A** structurally rather than by giving workers more to be right about.

---

## 5. Threats to the comparison

1. **The drafts were not comparable, and the gap is mostly draft luck.**
   `candidates/c0001/out/memory_config.json`: findings c0001 is 8192×48 tables, 6,359,040
   trainable params, search .6210; legacy c0001 is 32768×96, 38,045,696 params, search
   .3959. More decisive: the winning insight (`ORDERS=(1,)`, drop orders 2–3) was found by
   findings **c0002** and by legacy **c0011**. Legacy's two best candidates are c0011
   (.5632) and its child c0018 (.5779) — the only order-1 lineage it had, discovered with
   8 candidates left. The findings arm had 17. **0.811 vs 0.644 is largely "when did the
   arm stumble on order-1 hashing", which the memory policy did not decide.** STATUS.md
   already declines to read it as evidence; this is the mechanism.
2. **The Finding format is a second intervention.** `contract.summary_format` is non-null
   only in the findings arm (`lab_findings.SUMMARY_FORMAT`, set in `new_candidate`). It
   instructs workers to state Change/Hypothesis **before running** and to report a local
   observation. That is a research-protocol nudge independent of memory content, and it
   plausibly contributed to the search-fitness gap. The comparison cannot separate "cards
   as input" from "card template as output discipline".
3. **The rating strips the section where the findings arm put its cross-branch claims.**
   PREREG §"Unit" removes `## Finding` before extraction. Of the 5 out-of-lineage
   references in the findings arm, **4 are inside the Finding section** (c0007→c0004,
   c0008→c0003/c0004, c0018→c0010); only c0014→c0010 survives. Distinct ids named: 32 in
   Finding sections vs 28 in Details prose. The findings arm loses over half its
   statements-about-prior-attempts to the strip while the legacy arm loses none —
   affecting the ≥40-statement precondition and the `fraction_bad` denominator. The rule
   is defensible, but it de-powers the arm it was written for in a direction PREREG does
   not flag.
4. **Run-to-run noise is large at the candidate level.** findings c0015 and c0016 are the
   same change with different seeds: **.7067 vs .5692, a spread of .137**, comparable to a
   third of the arms' final-score gap. Legacy c0013/c0017 (also the same change, different
   seeds) spread .0173. One seed per arm cannot separate policy from noise; PREREG says so.
5. **Order and tooling.** The findings arm ran 16:33–20:17Z, legacy 20:19–00:17Z on the
   same GPU, findings first per `ORDER.json`. Every `config.json` in both arms records
   `git_dirty: true` (20/20 each), so the campaign working trees were not clean; only
   `campaign_sha256` and the `tools/` symlink pin the code. `campaign.toml` differs in
   exactly 3 lines (id, `[memory].mode`, header) and `task.md` is byte-identical —
   verified here.
6. **Tree shape is endogenous.** Parent selection is fitness-driven, so the findings arm's
   higher scores produced a different, deeper tree, which in turn caused its 8 coverage
   violations (deep lineage → parent + 2 ancestors eat the budget). Coverage and memory
   policy are confounded through fitness; the coverage number is not a clean property of
   `findings-v1`.
7. **Endpoint asymmetry in the repeats measure.** "Unacknowledged repeats" counts
   candidates whose *stated* change matches an earlier one. Legacy workers state their
   change in free prose of variable precision; findings workers state it in a mandated
   one-line `Change:` field that the strip removes. A rater working from stripped text has
   materially less to match on in the findings arm — biasing **B** against the arm with
   fewer real repeats.
