# mem2 comparison — status

Bundle `../labloop-mem2-20260914` (PREREG.md there), arms `../labloop-mem2-legacy-20260914`
(finished 2026-09-14 16:45Z) and `../labloop-mem2-findings-20260914` (finished 20:46Z).
Both 20/20 settled; legacy final .699, findings final .873 (not memory evidence: the drafts
differ, as in the first pair).

**Mechanical pass done** (`mechanical.md`, `mechanical.json`, from `scripts/mem_mechanical.py
--prompt-bound 2.2` with the prompt-size JSONs `prompt-size-*.json` from
`scripts/pilot_prompt_size.py`, tiktoken 0.14.0 `cl100k_base`; read-only on both arms).
Re-run 2026-09-15 morning after two notes from the first pass on 2026-09-14 evening:

- Coverage under findings-v2 is **18 of 19** jobs. The miss is `c0004` (parent c0003 ←
  c0001): when it was dispatched the population held three non-baseline cards, two of them
  its own ancestors, so a second out-of-lineage card did not exist. The PREREG rule says a
  violation is a tooling failure; this one is the single-draft opening, not the selector,
  and the read says so explicitly. It is exactly what `initial_drafts = 4` changes (the
  drafts pair, `docs/drafts-comparison-20260915/`).
- The first pass reported "served models differ between the arms" because the legacy
  arm's deferred `c0008` session never ran and carried an empty model list.
  `mem_mechanical.py` now counts such records apart ("sessions that never ran") and
  compares served models over the sessions that ran: 19 and 19, identical
  (`claude-sonnet-5` plus the CLI's `claude-haiku-4-5-20251001` helper). **Mechanical
  pending reasons: none.**
- Prompt cost: findings mean 5229 tokens vs legacy 2825, ratio **1.85 ≤ 2.2**, within the
  preregistered bound (the ledger's ~2 kB shows: 1.74 in the first pair).

Mechanical preconditions of the decision: ≥ 10 settled non-baseline per arm (19 and 19),
neither arm ended early (both `max_candidates 20 reached`), served models identical. The
legacy arm's c0008 was deferred by the usage window before its session started and
re-dispatched as c0009 (the first live deferral, 0 failed).

**Rating pack built 2026-09-15** by `scripts/mem_rating_pack.py --keep-finding` at
`../labloop-mem2-20260914/rating/` (copies here: `rating-README.md`,
`rating-MANIFEST.sha256`, 275 files): the `## Finding` section is **kept** in every summary
and rated as prose about earlier candidates (the one preregistered change). Pack A: 20
candidate records, pack B: 19 (one arm carries the deferred record); 13 and 9 verbatim
job-card sentences flagged. Letters drawn with `secrets`, `SEAL.json` mode 600, read only
after both `ratings/*.json` exist. Rater: a fresh Opus session given only the pack README.

**A procedural defect, found after the first rating pass.** `mem_rating_pack.py` copies
the rubric out of the PREREG it is given; this PREREG carries the unit, types and ratings
forward *by reference* to the 2026-09-13 file, so the README told the rater that types
M/R/C exist but not what they are. The first rater (a fresh Opus session, 2026-09-15
morning) said so in its difficulties and improvised close definitions (M = checkable
against records/config/code, R = a claim about what an earlier summary says, C =
interpretation or inference). That pass is kept, unsealed by nobody, at
`../labloop-mem2-20260914/rating-first-pass/` (A: 177 rated M+R, 9 bad, .0508; B: 155
rated, 16 bad, .1032) as evidence of how the rating behaves without the definitions; it is
**not** the preregistered read. The builder now inlines the carried-forward paragraphs
(`--rubric-from`, auto-detected) and refuses a rubric without a **Types** paragraph; the
README of this pack was completed in place with the verbatim 2026-09-13 paragraphs, the
manifest regenerated (275 entries; `pack/` and `SEAL.json` untouched, same letters), and
a second fresh Opus session rated from the completed README. Its ratings are the ones
`RESULT.md` decides on; the first pass is reported beside them.

**Result: see `RESULT.md`** once written; until then the comparison is *pending*.
