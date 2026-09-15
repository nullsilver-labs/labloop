#!/usr/bin/env python3
"""mem_rating_pack.py — the blinded rating pack of a legacy-vs-findings memory comparison.

Implements "Rating procedure and blinding" of the comparison's PREREG.md. Read-only on
both arms; never reads labels, REPORT.md, finding.json or a final-split score.

    scripts/mem_rating_pack.py --findings DIR --legacy DIR --prereg PREREG.md --out OUT [--keep-finding]

`--keep-finding` leaves the `## Finding` section in every summary (the 2026-09-14
preregistrations rate it as prose about earlier candidates); without it the section
is stripped, as the 2026-09-13 PREREG required.

OUT/ gets
  README.md          instructions for the rater and the rubric, extracted verbatim
                     from PREREG.md (primary endpoint + unacknowledged repeats)
  task.md            the task statement (identical in both arms)
  pack/A, pack/B     one arm each, letter drawn with `secrets`; per arm
                     records.json          id, operator, parents, exec, fail_reason,
                                           search fitness, n, seed — the lab's record
                     cNNNN/summary.md      the worker's summary, `## Finding` section removed
                     cNNNN/config.json     reduced to non-identifying fields
                     cNNNN/memory_config.json   out/memory_config.json when present
                     cNNNN/code/           the candidate's code without weights
                     cNNNN/verbatim.json   sentences of summary.md that appear verbatim in
                                           the job card the worker received (not units)
  SEAL.json          the letter ↔ arm assignment: read only after rating
  MANIFEST.sha256    every file under pack/, README.md and task.md

Blinding is partial by design (PREREG.md): prose may mention cards. Nothing this
script prints identifies the assignment.
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.machinery
import importlib.util
import json
import os
import re
import secrets
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
TOOLS = HERE.parent / "tools"

CONFIG_KEEP = ("candidate", "operator", "parents", "seed", "gpu", "job_wall_clock_sec",
               "redispatch_of", "defers")
RECORD_KEEP = ("operator", "parents", "exec", "fail_reason", "fitness", "n", "status")
MIN_SENTENCE = 40
_BULLET = re.compile(r"^\s*(?:[-*+]|\d+[.)])\s+")
_HEADING = re.compile(r"^\s*#{1,6}\s+")
_SENT_SPLIT = re.compile(r"(?<=[.!?])\s+")


def load_modules(project: Path):
    """Import the lab's modules against one arm (the pilot script's method)."""
    os.environ["LAB_ROOT"] = str(project)
    os.environ.setdefault("LAB_PRIVATE", str(Path.home() / ".local/share/labloop-private"))
    for m in ("lab", "lab_campaign", "lab_findings", "lab_serve"):
        sys.modules.pop(m, None)
    loader = importlib.machinery.SourceFileLoader("lab", str(TOOLS / "lab"))
    spec = importlib.util.spec_from_loader("lab", loader)
    lab = importlib.util.module_from_spec(spec)
    sys.modules["lab"] = lab
    loader.exec_module(lab)
    if str(TOOLS) not in sys.path:
        sys.path.insert(0, str(TOOLS))
    import lab_campaign as C   # noqa: E402
    import lab_findings as F   # noqa: E402
    C.L = lab
    return lab, C, F


def strip_finding(text: str, F) -> str:
    """Remove every `## Finding` section (heading to the next H1/H2 outside fences)."""
    lines = text.replace("\r\n", "\n").split("\n")
    out, fence, skipping = [], None, False
    for line in lines:
        m = F._FENCE.match(line)
        if m and m.group(1)[0] == "`" and "`" in line[m.end():]:
            m = None
        if fence is None and m:
            fence = (m.group(1)[0], len(m.group(1)))
            if not skipping:
                out.append(line)
            continue
        if fence is not None:
            if m and m.group(1)[0] == fence[0] and len(m.group(1)) >= fence[1] and line.strip() == m.group(1):
                fence = None
            if not skipping:
                out.append(line)
            continue
        if F._FINDING_HEADING.match(line):
            skipping = True
            continue
        if skipping and F._ANY_HEADING.match(line):
            skipping = False
        if not skipping:
            out.append(line)
    return "\n".join(out)


def norm(s: str) -> str:
    return " ".join(s.split())


def sentences(text: str) -> list[str]:
    """Sentences of a hard-wrapped markdown text: paragraphs joined, bullets split."""
    paras, cur, fence = [], [], False
    for line in text.split("\n"):
        if line.lstrip().startswith(("```", "~~~")):
            fence = not fence
            continue
        if fence:
            continue
        is_break = (not line.strip() or _BULLET.match(line) or _HEADING.match(line)
                    or line.lstrip().startswith("|"))
        if is_break:
            if cur:
                paras.append(" ".join(cur))
                cur = []
            if _BULLET.match(line):
                cur.append(_BULLET.sub("", line).strip())
            continue
        cur.append(line.strip())
    if cur:
        paras.append(" ".join(cur))
    out = []
    for p in paras:
        out += [s.strip() for s in _SENT_SPLIT.split(p) if s.strip()]
    return out


def verbatim_from_card(summary: str, card_text: str) -> list[str]:
    hay = norm(card_text)
    return [s for s in sentences(summary) if len(s) >= MIN_SENTENCE and norm(s) in hay]


def reduced_config(cfg: dict) -> dict:
    out = {k: cfg.get(k) for k in CONFIG_KEEP}
    ag = cfg.get("agent") or {}
    out["agent"] = {"requested": ag.get("requested"), "served": ag.get("served")}
    out["gpus"] = (cfg.get("hardware") or {}).get("gpus")
    return out


def build_arm(arm_dir: Path, dest: Path, letter: str, keep_finding: bool = False) -> dict:
    lab, C, F = load_modules(arm_dir)
    pop = C.load_pop()
    if pop is None:
        sys.exit(f"{arm_dir}: no population")
    cfg = C.load_campaign(arm_dir / "campaign.toml")
    task = cfg["campaign"]["task"].read_text()
    ignore = shutil.ignore_patterns(*C.WEIGHT_PATTERNS, "__pycache__", ".lab", ".venv")
    dest.mkdir(parents=True, exist_ok=True)
    records = {}
    stats = {"candidates": 0, "verbatim_sentences": 0, "finding_sections_removed": 0}
    for cid, c in sorted(pop["candidates"].items()):
        cdir = arm_dir / "candidates" / cid
        rec = {k: c.get(k) for k in RECORD_KEEP}
        try:
            conf = json.loads((cdir / "config.json").read_text())
        except OSError:
            conf = {}
        rec["seed"] = conf.get("seed")
        records[cid] = rec
        if c.get("operator") == "baseline":
            continue
        d = dest / cid
        d.mkdir(exist_ok=True)
        sp = cdir / "summary.md"
        raw = sp.read_bytes().decode("utf-8", errors="replace") if sp.exists() else ""
        stripped = raw if keep_finding else strip_finding(raw, F)
        if stripped != raw:
            stats["finding_sections_removed"] += 1
        (d / "summary.md").write_text(stripped)
        (d / "config.json").write_text(json.dumps(reduced_config(conf), indent=1) + "\n")
        mc = cdir / "out" / "memory_config.json"
        if mc.exists():
            shutil.copyfile(mc, d / "memory_config.json")
        if (cdir / "code").is_dir():
            shutil.copytree(cdir / "code", d / "code", ignore=ignore, dirs_exist_ok=True)
        job = cdir / "job.json"
        vb = []
        if job.exists():
            card = json.loads(job.read_text())
            vb = verbatim_from_card(stripped, C.render_job_card(card, task))
        stats["verbatim_sentences"] += len(vb)
        (d / "verbatim.json").write_text(json.dumps(
            {"candidate": cid,
             "rule": f"sentences of >= {MIN_SENTENCE} chars that appear verbatim (whitespace-normalised) "
                     "in the job card the worker received; not statements about prior attempts",
             "sentences": vb}, indent=1) + "\n")
        stats["candidates"] += 1
    (dest / "records.json").write_text(json.dumps(
        {"arm": letter,
         "note": "fitness is the hidden search split's score as recorded by the lab; "
                 "no final-split score is in this pack",
         "candidates": records}, indent=1) + "\n")
    return {"letter": letter, "task": task, **stats}


CARRIED = re.compile(r"rubric of `([^`]+PREREG\.md)` is carried forward")


def carried_rubric(prereg: Path, t: str) -> str:
    """A PREREG that carries the rubric forward by reference ("The rubric of `X` is carried
    forward verbatim ... with one change") names X; the rater must still read the unit,
    types and ratings, so X's paragraphs from **Unit.** to just before **Decision.** are
    inlined, as the referenced text, before the PREREG's own primary-endpoint section.
    The mem2 pack of 2026-09-15 was first built without this and the rater had to guess
    the types (`docs/mem2-comparison-20260914/RESULT.md`)."""
    m = CARRIED.search(t)
    if not m:
        return ""
    ref = Path(m.group(1))
    for base in (prereg.parent, Path(__file__).resolve().parent.parent, Path.cwd()):
        if (base / ref).exists():
            ref = base / ref
            break
    else:
        raise SystemExit(f"rubric carried forward from {m.group(1)}, which was not found; pass it via --rubric-from")
    rt = ref.read_text()
    a, b = rt.index("**Unit.**"), rt.index("**Decision.**")
    return (f"### Carried forward verbatim from `{m.group(1)}` (unit, types, ratings, endpoint)\n\n"
            + rt[a:b].rstrip() + "\n\n### This preregistration's primary endpoint\n\n")


def rubric(prereg: Path, rubric_from: Path | None = None) -> str:
    t = prereg.read_text()
    a = t.index("## Primary endpoint")
    b = t.index("## Secondary measures")
    primary = t[a:b].rstrip()
    if rubric_from is not None:
        rt = rubric_from.read_text()
        ra, rb = rt.index("**Unit.**"), rt.index("**Decision.**")
        head = (f"### Carried forward verbatim from `{rubric_from}` (unit, types, ratings, endpoint)\n\n"
                + rt[ra:rb].rstrip() + "\n\n### This preregistration's primary endpoint\n\n")
    else:
        head = carried_rubric(prereg, t)
    if "**Types.**" not in primary and "**Types.**" not in head:
        raise SystemExit("the rubric has no **Types.** paragraph: the rater would have to guess M/R/C; "
                         "pass --rubric-from <PREREG that defines them>")
    primary = primary.replace("## Primary endpoint", "## Primary endpoint", 1)
    primary = primary.split("\n", 1)[0] + "\n\n" + head + primary.split("\n", 1)[1].lstrip("\n")
    m = re.search(r"- \*\*Unacknowledged repeats\*\*:.*?(?=\n- \*\*|\n\n)", t[b:], re.S)
    repeats = m.group(0) if m else "(Unacknowledged repeats bullet not found in PREREG.md)"
    return primary + "\n\n## Secondary measure rated from the same pack\n\n" + repeats + "\n"


README = """# Rating pack — legacy vs finding cards (built {ts})

You are the rater: a fresh session that ran neither arm. Read only what is under this
directory. Do **not** open `SEAL.json`, the two campaign project directories, any
`REPORT.md`, `finding.json`, `job.json`, labels, or a final-split score; do not search
outside this directory. Arms are `pack/A` and `pack/B`; which memory each used is
sealed. Blinding is partial: prose may mention "cards" or "lineage". Rate from the
sources named in the rubric only.

## What is in the pack

- `pack/<arm>/records.json` — every candidate: operator, parents, execution status,
  search fitness (the lab's record), seed. This is the lab's record for type-M
  statements about scores, status, parents and operators.
- `pack/<arm>/cNNNN/summary.md` — the worker's summary{finding_note}. The prose to
  extract statements from, and the source for type-R statements about that candidate.
- `pack/<arm>/cNNNN/config.json`, `memory_config.json`, `code/` — that candidate's
  artifacts, sources for type-M statements about local numbers and code.
- `pack/<arm>/cNNNN/verbatim.json` — sentences copied verbatim from the job card the
  worker received. They are not units; skip them.
- `task.md` — the task both arms worked on.

## Procedure

1. For each arm, for each candidate in id order, read `summary.md`, extract every
   statement about a prior attempt (the rubric's unit), skip the sentences listed in
   `verbatim.json`, label its type (M / R / C), and rate it against the named source.
   Quote the statement, name the candidate(s) it is about, name the source file you
   checked, and give a one-line reason for anything not rated `correct`.
2. Record, per candidate, which earlier candidates it names (cross-branch
   acknowledgment: any named candidate that is not its parent or an ancestor), and
   any earlier non-ancestor candidate whose stated single change it repeats (knob and
   direction) without naming it (the secondary measure below).
3. Write `ratings/A.json` and `ratings/B.json` (schema below) and `ratings/SUMMARY.md`
   with, per arm: statements by type × rating, `fraction_bad` over M+R, the count of
   unrated statements with reasons, the acknowledgment and repeat lists. Report per
   letter only; do not guess the assignment.
4. Stop. The operator unseals, applies the preregistered decision, and the human
   spot-checks 10 rated statements per arm.

A statement the rubric does not cover is listed under `unrated` with the reason,
never rated ad hoc. Do not edit anything under `pack/`.

### `ratings/<arm>.json`

```json
{{"arm": "A",
 "statements": [
  {{"candidate": "c0005", "about": ["c0002"], "quote": "…", "type": "M|R|C",
   "rating": "correct|incorrect|unsupported", "source": "pack/A/c0002/summary.md", "note": "…"}}],
 "unrated": [{{"candidate": "c0005", "quote": "…", "reason": "…"}}],
 "acknowledgment": [{{"candidate": "c0005", "names": ["c0002", "c0003"], "cross_branch": ["c0003"]}}],
 "repeats": [{{"candidate": "c0012", "earlier": "c0004", "knob": "…", "acknowledged": false}}],
 "totals": {{"M": {{"correct": 0, "incorrect": 0, "unsupported": 0}},
            "R": {{"correct": 0, "incorrect": 0, "unsupported": 0}},
            "C": {{"correct": 0, "incorrect": 0, "unsupported": 0}},
            "rated_MR": 0, "bad_MR": 0, "fraction_bad": 0.0}}}}
```

# The frozen rubric (verbatim from PREREG.md)

{rubric}
"""


def manifest(root: Path, rel_paths: list[Path]) -> str:
    lines = []
    for p in sorted(rel_paths):
        h = hashlib.sha256((root / p).read_bytes()).hexdigest()
        lines.append(f"{h}  {p.as_posix()}")
    return "\n".join(lines) + "\n"


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--findings", required=True, type=Path)
    ap.add_argument("--legacy", required=True, type=Path)
    ap.add_argument("--prereg", required=True, type=Path)
    ap.add_argument("--out", required=True, type=Path)
    ap.add_argument("--keep-finding", action="store_true",
                    help="keep the `## Finding` section in summaries (rated as prose about others)")
    ap.add_argument("--rubric-from", type=Path,
                    help="PREREG.md whose unit/types/ratings paragraphs are inlined when --prereg "
                         "carries the rubric forward by reference (auto-detected when the reference resolves)")
    args = ap.parse_args()
    out = args.out.resolve()
    if out.exists() and any(out.iterdir()):
        sys.exit(f"{out} exists and is not empty; a pack is built once")
    out.mkdir(parents=True, exist_ok=True)
    arms = {"findings": args.findings.resolve(), "legacy": args.legacy.resolve()}
    order = ["findings", "legacy"] if secrets.randbits(1) else ["legacy", "findings"]
    assignment = {"A": order[0], "B": order[1]}
    stats, tasks = {}, {}
    for letter, name in assignment.items():
        st = build_arm(arms[name], out / "pack" / letter, letter, keep_finding=args.keep_finding)
        tasks[letter] = st.pop("task")
        stats[letter] = st
    if tasks["A"] != tasks["B"]:
        sys.exit("task.md differs between the arms; the comparison is not matched")
    (out / "task.md").write_text(tasks["A"])
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    note = (", `## Finding` section included: its lines are prose about earlier candidates and "
            "are extracted and rated like any other" if args.keep_finding
            else " with its `## Finding` section removed")
    (out / "README.md").write_text(README.format(ts=ts, rubric=rubric(args.prereg, args.rubric_from), finding_note=note))
    (out / "SEAL.json").write_text(json.dumps(
        {"built": ts, "draw": "secrets.randbits(1)", "assignment": assignment,
         "keep_finding": args.keep_finding,
         "projects": {k: str(v) for k, v in arms.items()},
         "rule": "read only after ratings/A.json and ratings/B.json exist"}, indent=1) + "\n")
    os.chmod(out / "SEAL.json", 0o600)
    files = [p.relative_to(out) for p in (out / "pack").rglob("*") if p.is_file()]
    files += [Path("README.md"), Path("task.md")]
    (out / "MANIFEST.sha256").write_text(manifest(out, files))
    # Only letter-level figures that hold under either assignment are printed.
    for letter in ("A", "B"):
        s = stats[letter]
        print(f"pack/{letter}: {s['candidates']} candidates, {s['verbatim_sentences']} verbatim sentences flagged")
    print(f"pack built at {out} ({len(files)} files in MANIFEST.sha256); SEAL.json is sealed")


if __name__ == "__main__":
    main()
