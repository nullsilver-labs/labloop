# Spot-check by a second blinded rater (2026-09-17)

A fresh Opus session re-rated the seeded sample of 10 statements per arm (`spot-check.md`,
seed 20260916, drawn before unsealing) blind: it was given the quotes, the pack and the
rubric, and neither the first rater's verdicts, nor the seal, nor the `ratings/` directory.
Types and ratings compared mechanically; verdicts in `ratings/spot-check-second.json`.

**This stands in for the human check.** The PREREG asks for a human spot check; on
2026-09-17 the human decided to have Opus do it instead, for this pair and for the two
earlier ones (whose second-rater files already exist). That is a deviation from the
preregistration, stated here and in `RESULT.md`; the unchecked boxes in `spot-check.md`
stay as they are.

| arm | # | candidate | first rater | second rater | |
|---|---|---|---|---|---|
| A | 10 | c0002 | M/correct | M/correct | agree |
| A | 27 | c0004 | M/correct | M/correct | agree |
| A | 40 | c0005 | M/correct | M/correct | agree |
| A | 61 | c0007 | M/correct | M/correct | agree |
| A | 94 | c0009 | M/correct | M/correct | agree |
| A | 97 | c0009 | M/correct | M/correct | agree |
| A | 129 | c0011 | M/correct | M/correct | agree |
| A | 164 | c0015 | M/correct | M/correct | agree |
| A | 169 | c0015 | M/correct | M/correct | agree |
| A | 174 | c0016 | M/correct | M/correct | agree |
| B | 88 | c0008 | M/incorrect | M/incorrect | agree |
| B | 124 | c0010 | M/correct | M/correct | agree |
| B | 127 | c0011 | M/correct | M/correct | agree |
| B | 137 | c0011 | M/correct | M/correct | agree |
| B | 210 | c0016 | M/correct | M/correct | agree |
| B | 213 | c0016 | M/correct | M/correct | agree |
| B | 223 | c0017 | M/correct | M/correct | agree |
| B | 224 | c0017 | M/correct | M/correct | agree |
| B | 232 | c0017 | M/correct | M/correct | agree |
| B | 256 | c0019 | R/correct | M/correct | DISAGREE |

Agreement on type and rating: **19 of 20**; on the rating alone, **20 of 20**. The one
disagreement is a type (B 256: R for the first rater, M for the second, `correct` for both;
the second rater named the M / R boundary itself). The one statement rated bad by
both is B 88 (both deltas right, the comparison "roughly matching or slightly exceeding"
is wrong: +0.0805 < +0.1101). The second rater's three judgment calls, none changing a
rating: A 27 "a third of table capacity" is a third by table count, 11 % by parameters;
B 224 quotes 480.1 s where c0013 recorded 480.3 s; several statements sit on the M / R
boundary and rate the same either way. The decision in `RESULT.md` is unchanged.
