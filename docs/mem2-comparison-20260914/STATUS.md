# mem2 comparison — status

Bundle `../labloop-mem2-20260914` (PREREG.md there), arms `../labloop-mem2-legacy-20260914`
(finished 2026-09-14 16:45Z) and `../labloop-mem2-findings-20260914` (finished 20:46Z).
Both 20/20 settled; legacy final .699, findings final .873 (not memory evidence: the drafts
differ, as in the first pair).

**Done 2026-09-14 evening: the mechanical pass only** (`mechanical.md`, `mechanical.json`,
from `scripts/mem_mechanical.py --prompt-bound 2.2`, read-only on both arms; the prompt
ratio still needs the `pilot_prompt_size.py` JSONs). Two notes for the reader:

- Coverage under findings-v2 is **18 of 19** jobs. The miss is `c0004` (parent c0003 ←
  c0001): when it was dispatched the population held three non-baseline cards, two of them
  its own ancestors, so a second out-of-lineage card did not exist. The PREREG rule says a
  violation is a tooling failure; this one is the single-draft opening, not the selector,
  and the read should say so explicitly. It is exactly what `initial_drafts = 4` changes.
- The script reports "served models differ between the arms" because the legacy arm's
  deferred `c0008` session never ran and carries an empty model string. Fix
  `mem_mechanical.py` to ignore sessions that never started before the read.

**Still to do (the read itself):** pack with `scripts/mem_rating_pack.py --keep-finding`,
a blinded rater in a fresh session, `scripts/mem_decide.py` against the PREREG rule
(findings fraction_bad ≤ ½ legacy over ≥ 40 rated M+R per arm), then RESULT.md here.
Nothing about the mechanism is claimed until then.
