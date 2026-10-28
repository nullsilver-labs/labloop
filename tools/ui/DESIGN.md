# labloop's campaign view

**Frame**: DesignRefs 77641cfbec32, the light research workspace, followed closely in layout. A sidebar on the
window's ground (it folds to its icons), then one recessed desk with rounded corners that holds everything else: a
small toolbar at its top right (Ask, Report, reset the layout, the tone), and the panels side by side under it. Ask,
the local model, is a column of its own that opens and closes, pushing the rest. Then the viewer, over the hours.
Then the inspector. The gaps between columns, and between the viewer and the hours, drag to resize: a double-click
or the reset button puts them back, and the sizes are remembered.
Every panel has the same head: an icon, a title, a quiet subtitle, its commands and a close. Then a breadcrumb row
on the panel's own surface, with the time or the status on the right.

**Skin**: Recall's (recall/src/lib/styles/bench.css), so the app register of the Nullsilver design system, in both
tones. The desk mixes the rail with the fill. Panels are a step lighter than paper by day, with a hairline and a
soft shadow. Sheets inside them (stat cells, the table head, notes) are tinted fills with no edge of their own.
The type is Satoshi throughout: 13px to read and press, 14/500 for a block's head, 17–19/500 for a panel's one
title. Figures use tabular digits, not mono. Mono is kept for code, paths and commands.

**Mark**: labloop's plate, only beside the word "labloop" in the sidebar (and as the favicon).

## What it adds to the app register

- **No control draws an edge against its panel's edge.** A pill is a fill. A switcher is a fill track with 3px of
  room, so a chosen or pointed-at segment never touches the track's edge or its neighbour. A table or a figure
  sheet has one real border all round, so its tinted head sits inside it.
- **Markers on the first line** (Recall's rule): a marker sits in a box one line tall, and wrapped lines hang.
- **Scrollers fade** at an edge only while something is hidden past it: the history, every panel body, the
  long figures.
- **How a candidate was made is a series colour and a shape**: improve `--color-series-1` ●, draft `-2` ■,
  crossover `-3` ◆, the baseline an ink ring, failed a ×, deferred a dashed square.
- **Search fitness, four ways**, each named by the question it answers:
  - *New bests* (the default): a ledger with one row per candidate that set a new best on search, in
    settled-job order rather than hours, since a campaign waiting on the usage window is mostly empty time. Each row
    shows what it came from, its job number, its fitness, its gain on the best before split into what each weighted
    part of the score gave (a bar runs left where a part fell; a step off the baseline is cut at the scale's end),
    how many tries came between, and its distance to the threshold. The final read is a row of its own under a
    rule, set against the search score it was read for. A best won on a noisy part shows as one.
  - *By operator*: a swarm per operator on one fitness axis, with a median tick, the best labelled, and median,
    best and "beat its parent" as figures.
  - *On parent*: a dumbbell per child, from its parent (or, for a draft built on another's code, that code's
    source) to itself, green when better and red when worse. Sorted by the gain.
  - *Top*: a ranked dot plot on a scale that fits the top, with the final read as a ring and the margin to the
    threshold.
- **The hours**: each job a mark in the hour it settled. Failed and deferred jobs sit under the line, and a job
  deferred many times counts once. The usage waits are bands. Then a full-width goal card at the panel's foot.
- **Evidence under the headline**: the margin to the threshold, final against search, the runner-up, when the
  last best came, and why the campaign ended.
- **Everything shareable is in the hash**: the place, the selection (`#/c/<id>` over the figures,
  `#/candidates/<id>` over the list), the figure, the list's filter, sort and query, the inspector's tab.
  Keys: `/` find, `j`/`k` next and previous in the current order, `[` `]` tabs, `Esc` close.
- **A candidate against what it came from**: a Diff tab beside Summary compares its `code/` with a parent's, with
  the candidate whose code it started from, or with the best (`/api/candidate/<id>/diff?against=<id>`), file by
  file, with + and − counted.
- **The first paint is the frame**: before the campaign is read, the page draws its own panels with grey bars
  where the words will be, and one status pill in the figure: reading, still reading, or not reaching the server.
- **The Documents reader is set justified and hyphenated**, at about 76 characters a line. Nothing else is
  justified: in the panels' narrow columns, justified text opens uneven gaps.
- `--color-signal` marks only now: a running job, the live lamp.
- **Markers are small squares rounded to a quarter of their size**: the lamp at 6px (1.5px corners), a swatch at 6
  to 8px. Lamp and swatch are one family; no circles beside words. nullsilver.com's lamp is still sharp.
