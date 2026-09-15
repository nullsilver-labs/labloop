# Spot-check by a second blinded rater (2026-09-15)

Not the human check PREREG asks for: a fresh Opus session re-rated the seeded sample of 10
statements per arm (`spot-check.md`, seed 20260915) blind, from the completed README, without
seeing the first rater's verdicts or the seal. Types and ratings compared mechanically;
verdicts in `ratings/spot-check-second.json`.

| arm | # | candidate | first rater | second rater | |
|---|---|---|---|---|---|
| A | 8 | c0002 | M/correct | M/correct | agree |
| A | 52 | c0005 | M/correct | M/correct | agree |
| A | 53 | c0005 | M/incorrect | M/incorrect | agree |
| A | 66 | c0006 | M/correct | M/correct | agree |
| A | 81 | c0007 | M/correct | M/correct | agree |
| A | 105 | c0009 | C/correct | R/correct | DISAGREE |
| A | 150 | c0012 | M/correct | M/correct | agree |
| A | 170 | c0014 | M/correct | M/correct | agree |
| A | 206 | c0017 | M/correct | M/correct | agree |
| A | 229 | c0018 | M/correct | M/correct | agree |
| B | 4 | c0002 | R/correct | M/correct | DISAGREE |
| B | 26 | c0004 | M/correct | M/correct | agree |
| B | 52 | c0006 | M/correct | M/correct | agree |
| B | 85 | c0010 | M/correct | M/correct | agree |
| B | 103 | c0011 | M/correct | M/correct | agree |
| B | 147 | c0015 | M/correct | M/correct | agree |
| B | 164 | c0017 | M/correct | M/correct | agree |
| B | 179 | c0018 | M/correct | M/correct | agree |
| B | 184 | c0019 | M/correct | M/correct | agree |
| B | 187 | c0019 | M/incorrect | M/incorrect | agree |

Agreement on type and rating: **18 of 20**. The two disagreements go the same way: the
second rater found *more* errors (legacy A 53: the held-out signal moved opposite to
fitness on the c0002 → c0003 step, not with it; findings B 187: batch_size was only ever
raised, never lowered, so "explored in both directions" is wrong). Counting them gives
legacy 16 / 252 = .063 and findings 19 / 190 = .100, ratio 1.57; the decision is unchanged.
The human spot-check in `spot-check.md` remains open.
