"""lab_findings — finding cards: one small, reliable account per settled attempt.

docs/finding-cards-plan.md is the specification; this module is its pure part.
Stdlib only, no filesystem, no labels, no evaluator, no model calls: every input is
an explicit argument, so a card can only ever contain what `lab` chose to pass in.

Three jobs:

  parse_summary   read the worker's `## Finding` section out of summary.md with a
                  mechanical, documented parser — never inference from prose
  build_card      assemble the immutable finding.json from evaluator facts, recorded
                  provenance and the parsed worker report, kept apart
  select_context  choose, deterministically and within two budgets, which earlier
                  cards a new job sees, and render exactly that text — under
                  findings-v2 with a knob ledger of every settled candidate below them

Measured facts (the hidden search score, n, evaluator fingerprint, deltas to the
parents) come only from the arguments `lab` passes from fitness.json and
population.json. The worker's Change/Hypothesis/Local observation/Interpretation/
Limitations/Topics lines are carried as *report*, labelled worker-reported wherever
they are shown. A number in worker prose is never promoted into a measured field.
"""
from __future__ import annotations

import hashlib
import json
import math
import re
from typing import Any, Callable

SCHEMA = "finding-card/1"
SCHEMA_V2 = "finding-card/2"          # v1 fields plus the optional `knobs` object
POLICY = "findings-v1"
POLICY_V2 = "findings-v2"
POLICY_V3 = "findings-v3"
POLICIES = (POLICY, POLICY_V2, POLICY_V3)
# The policies that carry a knob ledger and therefore need a [memory] knobs file.
# v3 keeps v2's card selector, card schema and byte caps exactly, and changes only
# the ledger (docs/finding-cards-plan.md §3c, docs/campaign-plan-20260914.md §6).
LEDGER_POLICIES = (POLICY_V2, POLICY_V3)
# The card schema each policy publishes. v1 is frozen: every byte it selected and
# rendered before 2026-09-14 must stay reproducible, so v2 is a separate branch
# everywhere rather than an edit to v1's rules (docs/finding-cards-plan.md §3b).
# v3 publishes v2's schema: the same card, with lists kept in `knobs`.
SCHEMAS = {POLICY: SCHEMA, POLICY_V2: SCHEMA_V2, POLICY_V3: SCHEMA_V2}


def is_findings(policy: str | None) -> bool:
    """Both card policies, for the call sites that only care 'cards, not legacy'."""
    return policy in POLICIES


# The six fields of the Finding section, in the order they are rendered, with the
# byte bound each one gets after whitespace normalisation and redaction.
FIELD_BYTES = {"change": 512, "hypothesis": 512, "local_observation": 512,
               "interpretation": 512, "limitations": 768}
FIELD_NAMES = {"Change": "change", "Hypothesis": "hypothesis",
               "Local observation": "local_observation", "Interpretation": "interpretation",
               "Limitations": "limitations", "Topics": "topics"}
FIELD_LABELS = {v: k for k, v in FIELD_NAMES.items()}
PROSE_FIELDS = ("change", "hypothesis", "local_observation", "interpretation", "limitations")
# When a mandatory parent card must shrink, its prose goes in this order; Limitations
# go last of all, and only before the facts-only card is declared unable to fit.
PROSE_DROP_ORDER = ("interpretation", "local_observation", "hypothesis", "change")
TOPIC_RE = re.compile(r"[a-z0-9]+(?:-[a-z0-9]+)*")
TOPIC_MAX_BYTES = 32
TOPICS_MAX = 5
MAX_CARDS = 8
MAX_BYTES = 12288
# v2 only. The knob ledger is one mechanical line per settled candidate, rendered in
# addition to the card budget: it is the cheap half of the cards (what was actually
# configured, from the candidate's own config file) and it must survive the eviction
# that drops the cards themselves — a worker that sees no card of c0015 must still see
# that c0015 moved this knob in this direction.
LEDGER_MAX_BYTES = 2048
LEDGER_ROW_MAX_BYTES = 240     # one candidate's row, so no single diff eats the ledger
KNOBS_MAX = 32                 # top-level scalar keys carried from the knobs file
KNOB_KEY_BYTES = 48
KNOB_VALUE_BYTES = 64
LEDGER_REPEAT_LINE = ("A knob and direction already in this ledger is a repeat: name the "
                      "earlier candidate and say why you repeat it, or choose a different change.")
# v3 only. The ledger is a per-knob index rather than per-candidate diff rows, and it
# carries knob keys only: an *outcome* key is something the run measured, not something
# a worker set, and under v2 outcome keys filled the alphabetically ordered rows before
# the knobs could appear (docs/mem2-comparison-20260914/RESULT.md). Measured values stay
# in the card, which is where a worker is meant to read them.
#
# The explicit set is the one preregistered in docs/campaign-plan-20260914.md §6, plus
# `holdout_n` and `predicted`, which the mem2 configuration files also measure. The
# prefix rule catches the families a task invents (`holdout_*`, `val_*`, `final_*`,
# `eval_*`, `test_*`, `measured_*`). A knob wrongly excluded would be invisible, so the
# set stays small, explicit and documented; anything else is treated as a knob.
OUTCOME_KEYS = frozenset({
    "epochs_started", "examples_seen", "final_loss", "holdout_n", "predicted",
    "seed", "steps", "trainable_params", "wall_seconds",
})
OUTCOME_PREFIXES = ("holdout_", "val_", "final_", "eval_", "test_", "measured_")
KNOB_LIST_MAX = 16             # elements of a list-valued knob carried into a card
LEDGER_V3_HEAD = ("## Knob ledger ({src}per-knob index over {n} settled candidate(s), "
                  "excluding the baseline)")
LEDGER_V3_NOTE = ("Every knob key any settled candidate configured, with each value tried and who "
                  "tried it, oldest value first; consecutive ids are collapsed into a range, and "
                  "`N older elided` means N values this knob had are not shown. "
                  "Measured outcomes (loss, accuracy, steps, wall time, parameter counts, seeds) "
                  "are never in this index — they are in the cards.")
LEDGER_V3_REPEAT_LINE = ("A knob and a value already in this index has been tried: name the earlier "
                         "candidate and say why you repeat it, or choose a different change. Only "
                         "the values shown here have been tried, and only by the ids shown.")
REASON_MAX_BYTES = 240
PROVENANCE_MAX_BYTES = 120     # a model name, a source label
PROVENANCE_MAX_ITEMS = 8
TRUNCATED = "… [truncated]"
OMITTED = "[omitted for space]"
REPORT_STATUSES = ("ok", "missing", "malformed", "undecodable")
PROBLEM_EXEC = ("failed", "killed", "invalid", "deferred")
EXEC_STATUSES = ("completed",) + PROBLEM_EXEC
CID_RE = re.compile(r"c\d{4}")
FORBIDDEN_KEYS = ("final",)   # nothing about the final split may ever enter a card

# Markdown as CommonMark reads it: a heading may be indented up to three spaces, its
# closing hashes need a space before them ("## Finding#" is the text "Finding#"), and a
# fence is three or more backticks or tildes indented at most three spaces.
_FINDING_HEADING = re.compile(r"^ {0,3}##[ \t]+Finding(?:[ \t]+#+)?[ \t]*$")
_ANY_HEADING = re.compile(r"^ {0,3}#{1,2}(?:[ \t]+\S|[ \t]*$)")   # a bare "##" is an empty heading
_FIELD_LINE = re.compile(r"^(Change|Hypothesis|Local observation|Interpretation|Limitations|Topics):(.*)$")
_FENCE = re.compile(r"^ {0,3}(`{3,}|~{3,})")
MAX_WARNINGS = 8              # a malformed section reports its first problems, then a count
WARNING_MAX_BYTES = 200

Redact = Callable[[str], str]


class ToolingError(Exception):
    """A defect in the tooling or its evidence, never a verdict on a candidate."""


def _identity(s: str) -> str:
    return s


# ---------------------------------------------------------------------------
# byte-safe text
# ---------------------------------------------------------------------------

def normalize_ws(s: str) -> str:
    return " ".join(s.split())


def truncate_utf8(s: str, limit: int, marker: str = TRUNCATED) -> tuple[str, bool]:
    """Bound s to `limit` UTF-8 bytes, marker included, never splitting a code point."""
    if len(s.encode("utf-8")) <= limit:
        return s, False
    room = limit - len(marker.encode("utf-8"))
    if room < 0:
        raise ValueError("limit smaller than the truncation marker")
    head = s.encode("utf-8")[:room].decode("utf-8", errors="ignore").rstrip()
    return head + marker, True


def scrub_private(s: str, private_paths: tuple[str, ...] = ()) -> str:
    """Every recorded private location (the label dirs, LAB_PRIVATE) out of a string,
    longest first so a parent dir never leaves a child's tail behind."""
    for p in sorted((p for p in private_paths if p), key=len, reverse=True):
        s = s.replace(p, "[private path]")
    return s


def cleaner(redact: Redact = _identity, private_paths: tuple[str, ...] = ()) -> Redact:
    """The one text filter every worker-written or diagnostic string passes through
    before it can enter a card: private paths, then secret shapes."""
    return lambda s: redact(scrub_private(s, private_paths))


def clean_line(s: str, clean: Redact) -> str:
    """Clean, collapse whitespace, clean again: collapsing whitespace must not be able
    to re-form a private path or secret that was written with a tab in it."""
    return clean(normalize_ws(clean(s)))


def sanitize_text(s: Any, redact: Redact = _identity, private_paths: tuple[str, ...] = (),
                  limit: int = REASON_MAX_BYTES) -> str | None:
    """Diagnostic text fit for a public card: private paths and secrets out, one
    line, bounded."""
    if s is None:
        return None
    t = clean_line(str(s), cleaner(redact, private_paths))
    t, _ = truncate_utf8(t, limit)
    return t or None


def canonical_json(obj: Any) -> bytes:
    """UTF-8, sorted keys, compact separators, finite numbers only."""
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False,
                      allow_nan=False).encode("utf-8")


def digest(obj: Any) -> str:
    return "sha256:" + hashlib.sha256(canonical_json(obj)).hexdigest()


def digest_bytes(b: bytes) -> str:
    return "sha256:" + hashlib.sha256(b).hexdigest()


def seq(cid: str) -> int:
    if not CID_RE.fullmatch(cid or ""):
        raise ToolingError(f"malformed candidate id {cid!r}")
    return int(cid[1:])


# ---------------------------------------------------------------------------
# 1. the worker's Finding section
# ---------------------------------------------------------------------------

def parse_topics(raw: str) -> tuple[list[str], list[str], list[str]]:
    """→ (slugs, warnings, errors). Lowercase, spaces/underscores to hyphens, then the
    slug rule; duplicates dropped in input order; the first five kept."""
    warnings: list[str] = []
    errors: list[str] = []
    items = [x.strip() for x in raw.split(",")]
    if not items or not any(items):
        errors.append("Topics is empty")
        return [], warnings, errors
    if not all(items):
        errors.append("Topics has an empty element (a stray comma)")
    slugs: list[str] = []
    for it in items:
        if not it:
            continue
        # ASCII only before lowercasing: Unicode case folding maps e.g. the Kelvin
        # sign to "k", which would smuggle a non-slug through the slug rule
        s = re.sub(r"[\s_]+", "-", it.lower()) if it.isascii() else it
        if not TOPIC_RE.fullmatch(s) or len(s.encode("utf-8")) > TOPIC_MAX_BYTES:
            errors.append(f"Topics: {it!r} is not a slug ([a-z0-9]+(-[a-z0-9]+)*, ≤{TOPIC_MAX_BYTES} bytes)")
            continue
        if s not in slugs:
            slugs.append(s)
    if len(slugs) > TOPICS_MAX:
        warnings.append(f"Topics: {len(slugs) - TOPICS_MAX} topic(s) beyond the first {TOPICS_MAX} omitted")
        slugs = slugs[:TOPICS_MAX]
    return slugs, warnings, errors


def parse_summary(raw: bytes | None, redact: Redact = _identity) -> dict:
    """The mechanical parser of docs/finding-cards-plan.md §1.

    → {"status": ok | missing | malformed | undecodable,
       "fields": {change, hypothesis, local_observation, interpretation, limitations,
                  topics} or None,
       "truncated": [field, …], "warnings": [str, …]}

    Exactly one `## Finding` heading outside fenced code; the section runs to the
    next level-1/2 heading or EOF; six case-sensitive fields, once each, one physical
    line each; anything else in the section is malformed. Malformed means facts
    only, with the reasons — never a verdict on the candidate.
    """
    if raw is None:
        return {"status": "missing", "fields": None, "truncated": [],
                "warnings": ["no summary.md; no worker report"]}
    try:
        text = raw.decode("utf-8", errors="strict")
    except UnicodeDecodeError as e:
        return {"status": "undecodable", "fields": None, "truncated": [],
                "warnings": [f"summary.md is not valid UTF-8 ({e.reason} at byte {e.start}); "
                             "no worker report extracted"]}
    # Physical lines are LF or CRLF only: str.splitlines() would also break on vertical
    # tabs and Unicode separators, letting one physical line carry several "fields".
    if text.startswith("﻿"):
        text = text[1:]
    lines = text.replace("\r\n", "\n").split("\n")
    fence: tuple[str, int] | None = None
    starts: list[int] = []
    outside = [True] * len(lines)
    for i, line in enumerate(lines):
        m = _FENCE.match(line)
        if m and m.group(1)[0] == "`" and "`" in line[m.end():]:
            m = None          # a backtick fence's info string may not contain a backtick
        if fence is None and m:
            fence = (m.group(1)[0], len(m.group(1)))
            outside[i] = False
            continue
        if fence is not None:
            outside[i] = False
            if m and m.group(1)[0] == fence[0] and len(m.group(1)) >= fence[1] \
                    and line.strip() == m.group(1):
                fence = None
            continue
        if _FINDING_HEADING.match(line):
            starts.append(i)
    if not starts:
        return {"status": "missing", "fields": None, "truncated": [],
                "warnings": ["no `## Finding` section in summary.md; facts only"]}
    errors: list[str] = []
    warnings: list[str] = []
    if len(starts) > 1:
        errors.append(f"{len(starts)} `## Finding` sections (lines {', '.join(str(s + 1) for s in starts)}); exactly one is allowed")
    start = starts[0]
    end = len(lines)
    for j in range(start + 1, len(lines)):
        if outside[j] and _ANY_HEADING.match(lines[j]):
            end = j
            break
    seen: dict[str, str] = {}
    for j in range(start + 1, end):
        line = lines[j]
        if not line.strip():
            continue
        m = _FIELD_LINE.match(line)
        if not m:
            errors.append(f"line {j + 1} of the Finding section is not a `Field: value` line")
            continue
        key = FIELD_NAMES[m.group(1)]
        if key in seen:
            errors.append(f"duplicate field {m.group(1)}")
            continue
        seen[key] = m.group(2)
    for label, key in FIELD_NAMES.items():
        if key not in seen:
            errors.append(f"missing field {label}")
    fields: dict[str, Any] = {}
    truncated: list[str] = []
    for key, value in seen.items():
        if key == "topics":
            continue
        v = clean_line(value, redact)
        if not v:
            errors.append(f"empty field {FIELD_LABELS[key]}")
            continue
        v, cut = truncate_utf8(v, FIELD_BYTES[key])
        if cut:
            truncated.append(key)
            warnings.append(f"{FIELD_LABELS[key]} truncated to {FIELD_BYTES[key]} bytes")
        fields[key] = v
    if "topics" in seen:
        slugs, tw, te = parse_topics(clean_line(seen["topics"], redact))
        warnings += tw
        errors += te
        fields["topics"] = slugs
    if errors:
        return {"status": "malformed", "fields": None, "truncated": [],
                "warnings": bound_warnings(errors + warnings)}
    return {"status": "ok", "fields": fields, "truncated": truncated, "warnings": bound_warnings(warnings)}


def bound_warnings(ws: list[str]) -> list[str]:
    """A worker cannot inflate its card past the budget with a thousand bad lines:
    each warning is bounded, and only the first few are kept with a count."""
    out = [truncate_utf8(normalize_ws(w), WARNING_MAX_BYTES)[0] for w in ws[:MAX_WARNINGS]]
    if len(ws) > MAX_WARNINGS:
        out.append(f"and {len(ws) - MAX_WARNINGS} more problem(s) not listed")
    return out


# ---------------------------------------------------------------------------
# 2. the card
# ---------------------------------------------------------------------------

def sanitize_knobs(raw: Any, clean: Redact, *, lists: bool = False) -> dict | None:
    """The candidate's own configuration file, reduced to a small, printable, sorted map
    of scalars. Nothing nested, nothing long, nothing about the final split: the file is
    written by the worker's code, so it is untrusted text like any other worker output.
    → None when the file is missing or is not an object.

    lists=True (findings-v3): a list of scalars is kept and rendered compactly, because
    dropping it made `orders` invisible to the mem2 workers; a dict, or a list this
    function cannot print, is kept as the empty object `{}`, a sentinel that says "a
    structure was here" so the index can name the skip instead of staying silent."""
    if not isinstance(raw, dict):
        return None
    out: dict[str, Any] = {}
    for k in sorted(raw):
        if len(out) >= KNOBS_MAX:
            break
        if not isinstance(k, str) or not k or k in FORBIDDEN_KEYS \
                or len(k.encode("utf-8")) > KNOB_KEY_BYTES or "\n" in k:
            continue
        v = raw[k]
        if isinstance(v, bool):
            out[k] = v
        elif isinstance(v, int):
            if len(str(v)) <= KNOB_VALUE_BYTES:
                out[k] = v
        elif isinstance(v, float):
            if math.isfinite(v):
                out[k] = v
        elif isinstance(v, str):
            t = clean_line(v, clean)
            if t and len(t.encode("utf-8")) <= KNOB_VALUE_BYTES:
                out[k] = t
        elif lists and isinstance(v, (list, dict)):
            kept = _sanitize_list(v, clean) if isinstance(v, list) else None
            out[k] = kept if kept is not None else {}
        # under v1/v2 lists and dicts are skipped: a ledger row is one line, and a
        # nested value is a structure to read in the candidate's own file
    return out


def _sanitize_list(v: list, clean: Redact) -> list | None:
    """A list of scalars, bounded and printable → the list; anything else → None, which
    the caller records as a skipped structure."""
    if len(v) > KNOB_LIST_MAX:
        return None
    out = []
    for x in v:
        if isinstance(x, bool) or isinstance(x, int):
            out.append(x)
        elif isinstance(x, float):
            if not math.isfinite(x):
                return None
            out.append(x)
        elif isinstance(x, str):
            t = clean_line(x, clean)
            if not t:
                return None
            out.append(t)
        else:
            return None
    return out if len(knob_value(out).encode("utf-8")) <= KNOB_VALUE_BYTES else None


def build_card(*, campaign: dict, candidate: dict, config: dict | None, fitness: dict | None,
               parents: list[dict], summary: bytes | None, created_at: str,
               redact: Redact = _identity, private_paths: tuple[str, ...] = (),
               policy: str = POLICY, knobs: dict | None = None,
               knobs_file: str | None = None) -> dict:
    """Assemble a card from an allowlist of safe inputs. Deterministic in its inputs:
    the same sources (created_at included) give the same bytes.

    campaign   {id, sha256, higher_is_better}
    candidate  the population entry: {id, operator, parents, exec, fail_reason,
               redispatch_of, defers}
    config     the candidate's config.json (seed, agent, git_commit), or None
    fitness    the candidate's fitness.json; only its "search" record is read
    parents    [{id, score, seed}] — each direct parent's search score and recorded seed
    summary    the raw bytes of summary.md, or None
    policy     findings-v1 (schema 1) or findings-v2 (schema 2, with `knobs`)
    knobs      the parsed contents of the campaign's knobs file, or None when it is
               missing/unreadable/not an object — v2 only
    knobs_file the configured relative path, when the campaign asks for one: it is what
               makes a missing file a caveat rather than simply nothing to record
    """
    if policy not in POLICIES:
        raise ToolingError(f"unknown memory policy {policy!r}")
    if policy == POLICY and (knobs is not None or knobs_file is not None):
        raise ToolingError(f"{POLICY} has no knobs; a knobs file needs {POLICY_V2}")
    cid = candidate["id"]
    sequence = seq(cid)
    exec_status = candidate.get("exec")
    if exec_status not in EXEC_STATUSES:
        raise ToolingError(f"{cid}: exec {exec_status!r} is not a settled outcome")
    parent_ids = list(candidate.get("parents") or [])
    for p in parent_ids:
        if seq(p) >= sequence:
            raise ToolingError(f"{cid}: parent {p} is not earlier than its child")
    if [p["id"] for p in parents] != parent_ids:
        raise ToolingError(f"{cid}: parent facts {[p['id'] for p in parents]} do not match parents {parent_ids}")
    hib = bool(campaign["higher_is_better"])

    rec = (fitness or {}).get("search")
    search: dict[str, Any] = {"measured": False, "score": None, "n": None, "evaluator": None,
                              "evaluator_sha256": None, "privilege_separation": None,
                              "ts": None, "error": None}
    stray_record = False
    if isinstance(rec, dict):
        score = rec.get("score")
        if isinstance(score, (int, float)) and not isinstance(score, bool) and math.isfinite(score):
            if exec_status == "completed":
                search["measured"], search["score"] = True, float(score)
            else:
                # `lab eval` run by hand on an attempt that did not complete: the record
                # is on disk, but it is not the measurement of a settled completion
                stray_record = True
        n = rec.get("n")
        search["n"] = int(n) if isinstance(n, (int, float)) and not isinstance(n, bool) else None
        search["evaluator"] = rec.get("evaluator") if isinstance(rec.get("evaluator"), str) else None
        search["evaluator_sha256"] = rec.get("evaluator_sha256") if isinstance(rec.get("evaluator_sha256"), str) else None
        search["privilege_separation"] = bool(rec["privilege_separation"]) if "privilege_separation" in rec else None
        search["ts"] = rec.get("ts") if isinstance(rec.get("ts"), str) else None
        search["error"] = sanitize_text(rec.get("error"), redact, private_paths)

    comparisons = []
    for p in parents:
        ps = p.get("score")
        ps = float(ps) if isinstance(ps, (int, float)) and not isinstance(ps, bool) and math.isfinite(ps) else None
        delta = (search["score"] - ps) if (search["measured"] and ps is not None) else None
        comparisons.append({"parent": p["id"], "parent_score": ps, "delta": delta})

    report = parse_summary(summary, cleaner(redact, private_paths))
    fields = report["fields"] or {}
    caveats: list[str] = []
    if exec_status != "completed":
        caveats.append(f"execution outcome '{exec_status}' is not evidence about the method")
        if stray_record:
            caveats.append("a search record exists for this attempt although it did not complete; "
                           "it is not carried as a measurement")
    elif not search["measured"]:
        caveats.append("no search measurement exists for this attempt")
    cseed = (config or {}).get("seed")
    cseed = int(cseed) if isinstance(cseed, int) and not isinstance(cseed, bool) else None
    for p in parents:
        pseed = p.get("seed")
        pseed = int(pseed) if isinstance(pseed, int) and not isinstance(pseed, bool) else None
        if cseed is None or pseed is None:
            caveats.append(f"seed of {cid} or {p['id']} is unrecorded; matched runs are unverified")
        elif cseed != pseed:
            caveats.append(f"seed {cseed} differs from {p['id']}'s seed {pseed}; training runs are not matched")
        else:
            caveats.append(f"seed equals {p['id']}'s; matched training and validation splits are still unverified")
    if report["status"] != "ok":
        caveats.append(f"worker report {report['status']}: facts only")
    if candidate.get("redispatch_of"):
        caveats.append(f"re-dispatch of deferred {candidate['redispatch_of']}: a new attempt, not a replication")
    knob_map = sanitize_knobs(knobs, cleaner(redact, private_paths),
                              lists=policy == POLICY_V3) if policy in LEDGER_POLICIES else None
    if policy in LEDGER_POLICIES and knobs_file and knob_map is None:
        # the campaign asked for a configuration file and this attempt has none: the
        # ledger says so rather than leaving a silent gap that reads like "no change"
        caveats.append("knobs file missing")

    # config.json lives in the worker's own dir, so its strings are worker-controlled
    # too: every one is cleaned and bounded like any other text
    agent = (config or {}).get("agent") or {}
    if not isinstance(agent, dict):
        agent = {}
    prov_text = lambda v: sanitize_text(v, redact, private_paths, PROVENANCE_MAX_BYTES) if isinstance(v, str) else None
    served_raw = agent.get("served") if isinstance(agent.get("served"), list) else None
    served = [t for t in [prov_text(x) for x in (served_raw or [])[:PROVENANCE_MAX_ITEMS]] if t] or None
    git_commit = (config or {}).get("git_commit")
    git_commit = git_commit if isinstance(git_commit, str) and re.fullmatch(r"[0-9a-f]{7,40}|no-git", git_commit) else None
    card = {
        "schema": SCHEMAS[policy],
        "campaign": campaign["id"],
        "campaign_sha256": campaign["sha256"],
        "candidate": cid,
        "sequence": sequence,
        "operator": candidate["operator"],
        "parents": parent_ids,
        "execution": {
            "exec": exec_status,
            "reason": sanitize_text(candidate.get("fail_reason"), redact, private_paths),
            "redispatch_of": candidate.get("redispatch_of") or None,
            "defers": int(candidate.get("defers") or 0),
        },
        "search": search,
        "metric": {"higher_is_better": hib},
        "comparisons": comparisons,
        "comparison_note": ("delta is the observed score difference on the hidden search split, "
                            "not an effect attributed to the change"),
        "provenance": {
            "seed": cseed,
            "model_requested": prov_text(agent.get("requested")),
            "model_served": served,
            "model_served_source": (prov_text(agent.get("served_source")) or "unknown") if served else "unknown",
            "git_commit": git_commit,
            "artifacts": {
                "summary": f"candidates/{cid}/summary.md",
                "config": f"candidates/{cid}/config.json",
                "fitness": f"candidates/{cid}/fitness.json" if isinstance(rec, dict) else None,
                "code": f"candidates/{cid}/code/",
            },
        },
        "report": {
            "source": "worker-reported in summary.md; not measured by lab",
            "status": report["status"],
            "change": fields.get("change"),
            "hypothesis": fields.get("hypothesis"),
            "local_observation": fields.get("local_observation"),
            "interpretation": fields.get("interpretation"),
            "limitations": fields.get("limitations"),
            "topics": list(fields.get("topics") or []),
            "truncated": list(report["truncated"]),
            "warnings": [sanitize_text(w, redact, private_paths, WARNING_MAX_BYTES) or "?"
                         for w in report["warnings"]],
        },
        "caveats": caveats,
        "evidence_limits": ("one attempt; the search score is optimistic by construction; no causal "
                            "attribution and no replication is established by this card"),
        "integrity": {
            "summary_sha256": digest_bytes(summary) if summary is not None else None,
            "search_record_sha256": digest(rec) if isinstance(rec, dict) else None,
        },
        "created_at": created_at,
    }
    if policy in LEDGER_POLICIES:
        card["knobs"] = knob_map
    problems = validate_card(card, policy)
    if problems:
        raise ToolingError(f"{cid}: built an invalid card: " + "; ".join(problems))
    return card


def map_strings(obj: Any, fn: Redact) -> Any:
    """fn applied to every string leaf; keys untouched."""
    if isinstance(obj, str):
        return fn(obj)
    if isinstance(obj, dict):
        return {k: map_strings(v, fn) for k, v in obj.items()}
    if isinstance(obj, list):
        return [map_strings(v, fn) for v in obj]
    return obj


def same_card(existing: dict, built: dict, clean: Redact) -> bool:
    """Is an existing card the one this lab would build now? Equal after the current
    cleaner is applied to the existing card's strings: a card published under fewer
    redaction secrets than the present shell has still passes, one published under
    more (the present shell is missing a secret and would print it) does not."""
    return canonical_json(map_strings(existing, clean)) == canonical_json(built)


def _keys_recursive(obj: Any):
    if isinstance(obj, dict):
        for k, v in obj.items():
            yield k
            yield from _keys_recursive(v)
    elif isinstance(obj, list):
        for v in obj:
            yield from _keys_recursive(v)


CARD_KEYS = {"schema", "campaign", "campaign_sha256", "candidate", "sequence", "operator",
             "parents", "execution", "search", "metric", "comparisons", "comparison_note",
             "provenance", "report", "caveats", "evidence_limits", "integrity", "created_at"}
CARD_KEYS_V2 = CARD_KEYS | {"knobs"}
SCHEMA_KEYS = {SCHEMA: CARD_KEYS, SCHEMA_V2: CARD_KEYS_V2}
EXECUTION_KEYS = {"exec", "reason", "redispatch_of", "defers"}
SEARCH_KEYS = {"measured", "score", "n", "evaluator", "evaluator_sha256", "privilege_separation",
               "ts", "error"}
PROVENANCE_KEYS = {"seed", "model_requested", "model_served", "model_served_source", "git_commit",
                   "artifacts"}
ARTIFACT_KEYS = {"summary", "config", "fitness", "code"}
REPORT_KEYS = {"source", "status", "change", "hypothesis", "local_observation", "interpretation",
               "limitations", "topics", "truncated", "warnings"}
INTEGRITY_KEYS = {"summary_sha256", "search_record_sha256"}
_SHA = re.compile(r"sha256:[0-9a-f]{64}")


def _is_num(v: Any) -> bool:
    return isinstance(v, (int, float)) and not isinstance(v, bool) and math.isfinite(v)


def _is_int(v: Any) -> bool:
    return isinstance(v, int) and not isinstance(v, bool)


def _opt(v: Any, typ) -> bool:
    return v is None or (isinstance(v, typ) and not isinstance(v, bool))


def validate_card(card: Any, policy: str | None = None) -> list[str]:
    """Schema problems, as strings; empty means valid. Exhaustive: every key set is
    exact and every value typed, so a corrupt card cannot carry text in a measured
    field or smuggle a key the schema does not name. Never raises on odd input.

    `policy` is the campaign's memory policy, when the caller knows it. v2 and v3
    publish the same schema but not the same `knobs`: only v3 keeps list values and the
    skipped-structure sentinel, so a nested value is a problem unless the caller says
    this is a v3 card. Omitted, the stricter v1/v2 rule applies."""
    try:
        return _validate_card(card, policy)
    except (TypeError, AttributeError, ValueError, KeyError) as e:
        return [f"malformed value: {e.__class__.__name__}: {e}"]


def _validate_card(card: Any, policy: str | None = None) -> list[str]:
    p: list[str] = []
    if not isinstance(card, dict):
        return ["card is not an object"]
    schema = card.get("schema")
    if schema not in SCHEMA_KEYS:
        p.append(f"schema is {schema!r}, expected one of {sorted(SCHEMA_KEYS)}")
        return p
    keys = SCHEMA_KEYS[schema]
    if set(card) != keys:
        p.append(f"keys differ from the schema: missing {sorted(keys - set(card))}, "
                 f"unexpected {sorted(set(card) - keys)}")
        return p
    for k in FORBIDDEN_KEYS:
        if k in set(_keys_recursive(card)):
            p.append(f"forbidden key {k!r} present")
    for k in ("campaign", "campaign_sha256", "operator", "comparison_note", "evidence_limits", "created_at"):
        if not isinstance(card[k], str) or not card[k]:
            p.append(f"{k} must be a non-empty string")
    cid = card["candidate"]
    if not isinstance(cid, str) or not CID_RE.fullmatch(cid):
        p.append(f"candidate {cid!r} is not an id")
    elif not _is_int(card["sequence"]) or card["sequence"] != int(cid[1:]):
        p.append("sequence does not match the candidate id")
    parents = card["parents"]
    if not isinstance(parents, list) or not all(isinstance(x, str) and CID_RE.fullmatch(x) for x in parents):
        p.append("parents must be a list of ids")
        parents = []
    elif len(set(parents)) != len(parents):
        p.append("parents repeat an id")
    ex = card["execution"]
    if not isinstance(ex, dict) or set(ex) != EXECUTION_KEYS:
        p.append("execution must hold exactly exec, reason, redispatch_of, defers")
        ex = {}
    else:
        if ex["exec"] not in EXEC_STATUSES:
            p.append("execution.exec is not a settled outcome")
        if not _opt(ex["reason"], str) or (ex["reason"] is not None and
                                          (not ex["reason"] or "\n" in ex["reason"]
                                           or len(ex["reason"].encode()) > REASON_MAX_BYTES)):
            p.append("execution.reason must be null or one bounded line")
        if not (ex["redispatch_of"] is None or (isinstance(ex["redispatch_of"], str) and CID_RE.fullmatch(ex["redispatch_of"]))):
            p.append("execution.redispatch_of must be null or an id")
        if not _is_int(ex["defers"]) or ex["defers"] < 0:
            p.append("execution.defers must be a non-negative int")
    s = card["search"]
    if not isinstance(s, dict) or set(s) != SEARCH_KEYS:
        p.append("search must hold exactly measured, score, n, evaluator, evaluator_sha256, "
                 "privilege_separation, ts, error")
        s = {"measured": False, "score": None}
    else:
        if not isinstance(s["measured"], bool):
            p.append("search.measured must be a bool")
        elif s["measured"]:
            if not _is_num(s["score"]):
                p.append("search.score must be a finite number when measured")
            if ex.get("exec") not in (None, "completed"):
                p.append("a measured search score requires execution.exec completed")
        elif s["score"] is not None:
            p.append("search.score must be null when not measured")
        if not (s["n"] is None or (_is_int(s["n"]) and s["n"] >= 0)):
            p.append("search.n must be null or a non-negative int")
        for k in ("evaluator", "evaluator_sha256", "ts", "error"):
            if not _opt(s[k], str):
                p.append(f"search.{k} must be null or a string")
        if s["evaluator_sha256"] is not None and not re.fullmatch(r"[0-9a-f]{64}", s["evaluator_sha256"]):
            p.append("search.evaluator_sha256 must be hex")
        if s["error"] is not None and len(s["error"].encode()) > REASON_MAX_BYTES:
            p.append("search.error exceeds its bound")
        if not (s["privilege_separation"] is None or isinstance(s["privilege_separation"], bool)):
            p.append("search.privilege_separation must be null or a bool")
    m = card["metric"]
    if not isinstance(m, dict) or set(m) != {"higher_is_better"} or not isinstance(m["higher_is_better"], bool):
        p.append("metric must hold exactly higher_is_better, a bool")
    comps = card["comparisons"]
    if not isinstance(comps, list) or not all(isinstance(c, dict) and set(c) == {"parent", "parent_score", "delta"} for c in comps) \
            or [c["parent"] for c in comps] != list(parents):
        p.append("comparisons must list each parent once, in order, with parent_score and delta")
    else:
        for c in comps:
            for k in ("parent_score", "delta"):
                if c[k] is not None and not _is_num(c[k]):
                    p.append(f"comparison {k} must be null or a finite number")
            if c["delta"] is not None and (c["parent_score"] is None or not s.get("measured")):
                p.append("a delta needs both a measured score and a parent score")
    r = card["report"]
    if not isinstance(r, dict) or set(r) != REPORT_KEYS:
        p.append("report keys differ from the schema")
    else:
        if not isinstance(r["source"], str) or not r["source"]:
            p.append("report.source must be a string")
        if r["status"] not in REPORT_STATUSES:
            p.append("report.status is not a report status")
        for f in PROSE_FIELDS:
            v = r[f]
            if r["status"] == "ok":
                if not isinstance(v, str) or not v:
                    p.append(f"report.{f} must be a non-empty string when the report is ok")
                elif len(v.encode("utf-8")) > FIELD_BYTES[f]:
                    p.append(f"report.{f} exceeds {FIELD_BYTES[f]} bytes")
                elif "\n" in v:
                    p.append(f"report.{f} spans lines")
            elif v is not None:
                p.append(f"report.{f} must be null when the report is {r['status']}")
        t = r["topics"]
        if not isinstance(t, list) or len(t) > TOPICS_MAX or len(set(t)) != len(t) \
                or not all(isinstance(x, str) and TOPIC_RE.fullmatch(x) and len(x.encode()) <= TOPIC_MAX_BYTES for x in t):
            p.append("report.topics must be ≤5 unique slugs")
        if r["status"] != "ok" and t:
            p.append("report.topics must be empty unless the report is ok")
        if not isinstance(r["warnings"], list) or len(r["warnings"]) > MAX_WARNINGS + 1 \
                or not all(isinstance(x, str) and x and "\n" not in x and len(x.encode()) <= WARNING_MAX_BYTES for x in r["warnings"]):
            p.append("report.warnings must be a short list of bounded lines")
        if not isinstance(r["truncated"], list) or not set(r["truncated"]) <= set(PROSE_FIELDS) \
                or len(set(r["truncated"])) != len(r["truncated"]):
            p.append("report.truncated must name prose fields once each")
    if not isinstance(card["caveats"], list) or not all(isinstance(x, str) and x and "\n" not in x for x in card["caveats"]):
        p.append("caveats must be a list of one-line strings")
    if schema == SCHEMA_V2:
        kn = card["knobs"]
        if kn is None:
            pass                      # no knobs file, or one that could not be read
        elif not isinstance(kn, dict):
            p.append("knobs must be null or an object")
        else:
            if len(kn) > KNOBS_MAX:
                p.append(f"knobs holds more than {KNOBS_MAX} keys")
            if list(kn) != sorted(kn):
                p.append("knobs keys must be sorted")     # so a card is byte-stable
            for k, v in kn.items():
                if not isinstance(k, str) or not k or k in FORBIDDEN_KEYS \
                        or len(k.encode("utf-8")) > KNOB_KEY_BYTES or "\n" in k:
                    p.append(f"knobs key {k!r} is not a bounded name")
                if isinstance(v, bool):
                    continue
                if isinstance(v, int):
                    if len(str(v)) > KNOB_VALUE_BYTES:
                        p.append(f"knobs[{k!r}] exceeds {KNOB_VALUE_BYTES} bytes")
                elif isinstance(v, float):
                    if not math.isfinite(v):
                        p.append(f"knobs[{k!r}] is not finite")
                elif isinstance(v, str):
                    if not v or "\n" in v or len(v.encode("utf-8")) > KNOB_VALUE_BYTES:
                        p.append(f"knobs[{k!r}] must be one bounded line")
                elif isinstance(v, list) and policy == POLICY_V3:
                    # findings-v3 keeps list-valued knobs; v1/v2 never build one
                    if len(v) > KNOB_LIST_MAX or len(knob_value(v).encode("utf-8")) > KNOB_VALUE_BYTES \
                            or not all(isinstance(x, (bool, int, float, str)) for x in v) \
                            or not all(math.isfinite(x) for x in v if isinstance(x, float)) \
                            or not all(x and "\n" not in x for x in v if isinstance(x, str)):
                        p.append(f"knobs[{k!r}] must be a short list of bounded scalars")
                elif isinstance(v, dict) and policy == POLICY_V3:
                    if v:
                        p.append(f"knobs[{k!r}] must be {{}} — the skipped-structure sentinel")
                elif policy == POLICY_V3:
                    p.append(f"knobs[{k!r}] must be an int, float, bool, str or list")
                else:
                    p.append(f"knobs[{k!r}] must be an int, float, bool or str")
    integ = card["integrity"]
    if not isinstance(integ, dict) or set(integ) != INTEGRITY_KEYS:
        p.append("integrity must hold exactly summary_sha256 and search_record_sha256")
    else:
        for k in INTEGRITY_KEYS:
            v = integ[k]
            if v is not None and not (isinstance(v, str) and _SHA.fullmatch(v)):
                p.append(f"integrity.{k} must be null or sha256:<hex>")
    prov = card["provenance"]
    if not isinstance(prov, dict) or set(prov) != PROVENANCE_KEYS:
        p.append("provenance keys differ from the schema")
    else:
        if not _opt(prov["seed"], int):
            p.append("provenance.seed must be null or an int")
        if not _opt(prov["model_requested"], str) or (prov["model_requested"] is not None and
                                                       len(prov["model_requested"].encode()) > PROVENANCE_MAX_BYTES):
            p.append("provenance.model_requested must be null or a bounded string")
        if not (prov["git_commit"] is None or (isinstance(prov["git_commit"], str)
                                               and re.fullmatch(r"[0-9a-f]{7,40}|no-git", prov["git_commit"]))):
            p.append("provenance.git_commit must be null, a hex commit or no-git")
        if not (prov["model_served"] is None or (isinstance(prov["model_served"], list)
                                                 and 0 < len(prov["model_served"]) <= PROVENANCE_MAX_ITEMS
                                                 and all(isinstance(x, str) and x and len(x.encode()) <= PROVENANCE_MAX_BYTES
                                                         for x in prov["model_served"]))):
            p.append("provenance.model_served must be null or a short list of bounded strings")
        if not isinstance(prov["model_served_source"], str) or len(prov["model_served_source"].encode()) > PROVENANCE_MAX_BYTES:
            p.append("provenance.model_served_source must be a bounded string")
        arts = prov["artifacts"]
        if not isinstance(arts, dict) or set(arts) != ARTIFACT_KEYS:
            p.append("provenance.artifacts keys differ from the schema")
        else:
            for k, v in arts.items():
                if v is not None and (not isinstance(v, str) or v.startswith("/") or ".." in v
                                      or not v.startswith(f"candidates/{cid}/")):
                    p.append(f"provenance.artifacts.{k} must be a relative path inside the candidate dir")
    try:
        canonical_json(card)
    except (ValueError, TypeError) as e:
        p.append(f"not canonically serialisable: {e}")
    return p


def check_card_sources(card: dict, *, campaign_id: str, campaign_sha256: str, candidate: dict,
                       summary: bytes | None, fitness: dict | None) -> list[str]:
    """Does an existing card agree with its recorded sources? Mismatches, as strings."""
    p: list[str] = []
    if card.get("campaign") != campaign_id:
        p.append(f"campaign {card.get('campaign')!r} != {campaign_id!r}")
    if card.get("campaign_sha256") != campaign_sha256:
        p.append("campaign_sha256 differs")
    if card.get("candidate") != candidate["id"]:
        p.append(f"candidate {card.get('candidate')!r} != {candidate['id']!r}")
    if card.get("operator") != candidate["operator"]:
        p.append(f"operator {card.get('operator')!r} != {candidate['operator']!r}")
    if list(card.get("parents") or []) != list(candidate.get("parents") or []):
        p.append("parents differ from population.json")
    if (card.get("execution") or {}).get("exec") != candidate.get("exec"):
        p.append(f"execution.exec {(card.get('execution') or {}).get('exec')!r} != {candidate.get('exec')!r}")
    integ = card.get("integrity") or {}
    want = digest_bytes(summary) if summary is not None else None
    if integ.get("summary_sha256") != want:
        p.append("summary_sha256 does not match summary.md")
    rec = (fitness or {}).get("search")
    want = digest(rec) if isinstance(rec, dict) else None
    if integ.get("search_record_sha256") != want:
        p.append("search_record_sha256 does not match fitness.json's search record")
    s = card.get("search") or {}
    if isinstance(rec, dict):
        sc = rec.get("score")
        measured = _is_num(sc) and candidate.get("exec") == "completed"
        if s.get("measured") != measured or (measured and s.get("score") != float(sc)):
            p.append("search.score does not match fitness.json")
        n = rec.get("n")
        if s.get("n") != (int(n) if _is_num(n) else None):
            p.append("search.n does not match fitness.json")
        for k in ("evaluator", "evaluator_sha256", "ts"):
            if s.get(k) != (rec.get(k) if isinstance(rec.get(k), str) else None):
                p.append(f"search.{k} does not match fitness.json")
    elif s.get("measured") or s.get("score") is not None or s.get("n") is not None:
        p.append("search fields are set but fitness.json has no search record")
    return p


# ---------------------------------------------------------------------------
# 3. selection and rendering
# ---------------------------------------------------------------------------

def non_improving(card: dict) -> bool:
    """A completed, measured child that did not strictly beat its strongest direct
    parent, all parent scores present. Ties count; unmeasured, failed and parentless
    do not. A retrieval rule, not a verdict."""
    s = card["search"]
    if card["execution"]["exec"] != "completed" or not s["measured"] or not card["comparisons"]:
        return False
    scores = [c["parent_score"] for c in card["comparisons"]]
    if any(x is None for x in scores):
        return False
    hib = card["metric"]["higher_is_better"]
    best_parent = max(scores) if hib else min(scores)
    return not (s["score"] > best_parent if hib else s["score"] < best_parent)


def ancestors_bfs(cards: dict[str, dict], start: list[str]) -> list[tuple[str, int]]:
    """Ancestors of `start` (excluded), breadth-first: shortest distance first, ascending
    id within a distance, each once. Malformed or cyclic references are tooling errors."""
    seen = set(start)
    frontier = sorted(set(start))
    out: list[tuple[str, int]] = []
    dist = 0
    while frontier:
        dist += 1
        nxt: list[str] = []
        for cid in frontier:
            card = cards.get(cid)
            if card is None:
                raise ToolingError(f"no finding card for {cid}, which is in the ancestry")
            for p in card["parents"]:
                if seq(p) >= seq(cid):
                    raise ToolingError(f"{cid} lists {p} as a parent: not an earlier candidate")
                if p not in seen:
                    seen.add(p)
                    nxt.append(p)
        frontier = sorted(nxt)
        out += [(c, dist) for c in frontier]
    return out


def _strength_key(card: dict):
    hib = card["metric"]["higher_is_better"]
    return (-card["search"]["score"] if hib else card["search"]["score"], card["sequence"])


def select_context(cards: dict[str, dict], parents: list[str], *, policy: str = POLICY,
                   max_cards: int = MAX_CARDS, max_bytes: int = MAX_BYTES,
                   ledger_max_bytes: int = LEDGER_MAX_BYTES, knobs_file: str | None = None) -> dict:
    """The deterministic policy of docs/finding-cards-plan.md §3 (findings-v1) and §3b
    (findings-v2). `cards` holds every settled candidate's card, keyed by id. Consumes
    no randomness; stable id tie-breaks throughout.

    v1 is frozen — every branch below that reads `v2` leaves it exactly as it was, so a
    v1 job card rebuilt from its stored inputs is still byte-identical. v2 fixes the
    three defects the live comparison found (docs/memory-comparison-20260913/
    opus-review.md §2): topical cards sorted newest-first instead of oldest-first, the
    trivial baseline never taking the "strongest outside this lineage" slot, and a floor
    of two cross-branch cards that ancestors are evicted for.
    """
    if policy not in POLICIES:
        raise ToolingError(f"unknown memory policy {policy!r}")
    v2 = policy in LEDGER_POLICIES      # v3 keeps v2's selector exactly; only the ledger differs
    if not v2 and knobs_file is not None:
        raise ToolingError(f"{POLICY} has no knob ledger; a knobs file needs {POLICY_V2}")
    parents = sorted(set(parents))
    for p in parents:
        if p not in cards:
            raise ToolingError(f"no finding card for direct parent {p}")
    if len(parents) > max_cards:
        raise ToolingError(f"max_cards {max_cards} is below the {len(parents)} direct parents")
    chosen: list[dict] = [{"id": p, "reason": "direct parent", "tier": 0} for p in parents]
    closure_list = ancestors_bfs(cards, parents)
    for cid, d in closure_list[:min(2, max_cards - len(chosen))]:
        chosen.append({"id": cid, "reason": f"ancestor at distance {d} (both sides of a crossover are traversed)", "tier": 1})
    closure = set(parents) | {c for c, _ in closure_list}
    anchors: set[str] = set()
    for e in chosen:
        anchors |= set(cards[e["id"]]["report"]["topics"])
    others = sorted((c for k, c in cards.items() if k not in closure), key=lambda c: c["sequence"])
    if v2:
        # The trivial baseline has no change, no topics and the campaign's worst score:
        # under v1 it was the *only* card the "strongest measured outside this lineage"
        # slot ever admitted, four times, because the topical takes had already consumed
        # everything stronger. It is never an optional card in v2.
        others = [c for c in others if c["operator"] != "baseline"]
    picked = {e["id"] for e in chosen}
    room = max(0, max_cards - len(chosen))

    def take(seq_: list[dict], reason_fn, limit: int | None = None) -> None:
        """Admit up to `limit` (default all) of seq_ not already picked, in order."""
        nonlocal room
        n = 0
        for c in seq_:
            if room <= 0 or (limit is not None and n >= limit):
                return
            if c["candidate"] in picked:
                continue      # a tier is judged over what is still unpicked
            picked.add(c["candidate"])
            chosen.append({"id": c["candidate"], "reason": reason_fn(c), "tier": 2})
            room -= 1
            n += 1

    newest = sorted(others, key=lambda c: -c["sequence"])
    measured = sorted((c for c in others if c["search"]["measured"]), key=_strength_key)
    problems = [c for c in newest if c["execution"]["exec"] in PROBLEM_EXEC]
    if parents:
        def matched(c: dict) -> list[str]:
            return sorted(set(c["report"]["topics"]) & anchors)
        # Within equal topic matches v1 sorts by ascending sequence — oldest first. In a
        # campaign where every card carries the same handful of slugs that tie-break is
        # the whole order, and the window froze on the earliest weak candidates; v2 reads
        # the same rule as "the most recent of the equally topical".
        topical = sorted((c for c in others if matched(c)),
                         key=(lambda c: (-len(matched(c)), -c["sequence"])) if v2
                         else (lambda c: (-len(matched(c)), c["sequence"])))
        if v2:
            # strongest first: it is one slot, and it must not be spent on whatever the
            # topical tiers happened to leave over
            take(measured, lambda c: "strongest measured candidate outside this lineage", limit=1)
            siblings = [c for c in newest if set(c["parents"]) & set(parents)]
            take(siblings, lambda c: "sibling: shares direct parent "
                 + ", ".join(sorted(set(c["parents"]) & set(parents))), limit=2)
            take([c for c in topical if non_improving(c)],
                 lambda c: "did not beat its strongest parent; shares topics " + ", ".join(matched(c)), limit=1)
            take(topical, lambda c: "shares topics " + ", ".join(matched(c)))
            take(problems, lambda c: "recent execution problem (not evidence about the method)", limit=1)
            take(newest, lambda c: "recent")
        else:
            take([c for c in topical if non_improving(c)],
                 lambda c: "did not beat its strongest parent; shares topics " + ", ".join(matched(c)), limit=1)
            take(topical, lambda c: "shares topics " + ", ".join(matched(c)))
            take(measured, lambda c: "strongest measured candidate outside this lineage", limit=1)
            take(problems, lambda c: "recent execution problem (not evidence about the method)", limit=1)
            take(newest, lambda c: "recent")
    else:
        take(measured, lambda c: "strongest measured candidate", limit=1)
        take([c for c in newest if non_improving(c)], lambda c: "newest candidate that did not beat its strongest parent", limit=1)
        take(problems, lambda c: "newest execution problem (not evidence about the method)", limit=1)
        take([c for c in newest if c["execution"]["exec"] == "completed"], lambda c: "newest completed candidate", limit=1)
        take(newest, lambda c: "recent")

    omitted: list[dict] = []
    dropped: list[str] = []
    # v2's cross-branch floor: with at least two off-lineage cards to show, two of them
    # survive the byte budget — the ancestors go first. v1 sheds every tier-2 card
    # before touching an ancestor, which is how c0016 lost the card of the sibling it
    # then repeated verbatim.
    floor = min(2, sum(1 for e in chosen if e["tier"] == 2)) if v2 else 0
    ledger: dict | None = None
    while True:
        rendered = render_context(cards, chosen, dropped, anchors, omitted, policy=policy)
        size = len(rendered.encode("utf-8"))
        if v2:
            # the ledger is rendered against the cards actually shown (an id it names
            # that no card covers is marked), so it is rebuilt on every eviction
            if policy == POLICY_V3:
                ledger_text, ledger = render_ledger_v3(cards, knobs_file, ledger_max_bytes)
            else:
                ledger_text, ledger = render_ledger(cards, {e["id"] for e in chosen}, knobs_file,
                                                    ledger_max_bytes)
        if size <= max_bytes:
            break
        n2 = sum(1 for e in chosen if e["tier"] == 2)
        idx = next((i for i in range(len(chosen) - 1, -1, -1) if chosen[i]["tier"] == 2), None) \
            if n2 > floor else None
        if idx is None:
            idx = next((i for i in range(len(chosen) - 1, -1, -1) if chosen[i]["tier"] == 1), None)
        if idx is not None:
            e = chosen.pop(idx)
            omitted.append({"id": e["id"], "reason": e["reason"], "why": "over the byte budget"})
            continue
        nxt = next((f for f in PROSE_DROP_ORDER + ("limitations",) if f not in dropped), None)
        if nxt is not None:
            dropped.append(nxt)
            continue
        if n2:
            # facts-only parents plus the floor still do not fit: the floor yields, and
            # says so, rather than the selection failing
            e = chosen.pop(next(i for i in range(len(chosen) - 1, -1, -1) if chosen[i]["tier"] == 2))
            omitted.append({"id": e["id"], "reason": e["reason"],
                            "why": "over the byte budget (cross-branch floor yielded)"})
            continue
        raise ToolingError(f"the facts-only context of the direct parents ({', '.join(parents)}) "
                           f"does not fit in {max_bytes} bytes")
    if not v2:
        return {
            "policy": POLICY,
            "limits": {"max_cards": max_cards, "max_bytes": max_bytes},
            "anchors": sorted(anchors),
            "cards": [{"id": e["id"], "reason": e["reason"], "digest": digest(cards[e["id"]]),
                       "omitted_fields": list(dropped) if e["tier"] < 2 else []}
                      for e in chosen],
            "omitted": omitted,
            "rendered": rendered,
            "bytes": size,
        }
    # v2: the ledger's bytes are *in addition* to the card budget — it is the part that
    # must be there even when no card fits
    rendered += ledger_text
    return {
        "policy": policy,
        "limits": {"max_cards": max_cards, "max_bytes": max_bytes,
                   "ledger_max_bytes": ledger_max_bytes},
        "anchors": sorted(anchors),
        "cards": [{"id": e["id"], "reason": e["reason"], "tier": e["tier"],
                   "digest": digest(cards[e["id"]]),
                   "omitted_fields": list(dropped) if e["tier"] < 2 else []}
                  for e in chosen],
        "omitted": omitted,
        "ledger": ledger,
        "rendered": rendered,
        "bytes": len(rendered.encode("utf-8")),
    }


def _fmt(v: float | None) -> str:
    return "—" if v is None else f"{v:.6g}"


def render_measured(card: dict) -> str | None:
    """v3 only: the outcome keys of the candidate's knobs file, on its card. The v3
    index keeps measured quantities out of the ledger by design; this is where they
    live instead, so a parameter count or a step count is read from the file that
    recorded it and never copied from another worker's rounded prose."""
    kn = card.get("knobs")
    if not isinstance(kn, dict):
        return None
    items = [(k, v) for k, v in sorted(kn.items()) if is_outcome_key(k) and not isinstance(v, (list, dict))]
    if not items:
        return None
    return ("- Measured (from the candidate's knobs file, not the search score): "
            + " · ".join(f"{k} {knob_value(v)}" for k, v in items))


def render_card(card: dict, reason: str | None = None, dropped: tuple[str, ...] | list[str] = (),
                *, policy: str = POLICY) -> str:
    cid = card["candidate"]
    s, ex, r = card["search"], card["execution"], card["report"]
    head = f"### {cid} · {card['operator']}"
    if card["parents"]:
        head += " from " + ", ".join(card["parents"])
    head += f" · {ex['exec']}"
    if ex.get("reason"):
        head += f" ({ex['reason']})"
    head += f" · search {_fmt(s['score'])}" + (f" (n={s['n']})" if s["measured"] and s.get("n") is not None else "")
    lines = [head]
    if reason:
        lines.append(f"Selected: {reason}.")
    if card["comparisons"]:
        parts = []
        for c in card["comparisons"]:
            parts.append(f"{c['parent']} {_fmt(c['parent_score'])}"
                         + (f" (Δ {c['delta']:+.6g})" if c["delta"] is not None else " (Δ —)"))
        lines.append("Parents' search scores: " + "; ".join(parts) + ". Δ is an observed difference, not an attributed effect.")
    if r["status"] == "ok":
        for f in PROSE_FIELDS:
            label = FIELD_LABELS[f] + (" (worker-reported, not the search score)" if f == "local_observation" else "")
            lines.append(f"- {label}: " + (OMITTED if f in dropped else r[f]))
        lines.append("- Topics: " + (", ".join(r["topics"]) if r["topics"] else "—"))
        if r["truncated"]:
            lines.append("- Truncated fields: " + ", ".join(FIELD_LABELS[f] for f in r["truncated"]))
        if r["warnings"]:
            lines.append("- Report warnings: " + "; ".join(r["warnings"]))
    else:
        lines.append(f"- Worker report: {r['status']} — " + "; ".join(r["warnings"]))
    if policy == POLICY_V3:
        measured = render_measured(card)
        if measured:
            lines.append(measured)
    if card["caveats"]:
        lines.append("- Caveats: " + "; ".join(card["caveats"]))
    lines.append(f"- Full summary: candidates/{cid}/summary.md · code: candidates/{cid}/code/")
    return "\n".join(lines)


def knob_value(v: Any) -> str:
    """One knob value, compactly and unambiguously; a key one side does not have at all
    is `(unset)`, which no scalar value can be confused with."""
    if v is None:
        return "(unset)"
    if isinstance(v, bool):
        return repr(v)
    if isinstance(v, float):
        return f"{v:.6g}"
    if isinstance(v, int):
        return str(v)
    if isinstance(v, list):
        # compact and unambiguous: `orders [1,2,3]`, never dropped (findings-v3)
        return "[" + ",".join(knob_value(x) for x in v) + "]"
    if isinstance(v, dict):
        return "(structure not shown)"    # the sanitiser's skipped-structure sentinel
    return repr(v)


def ledger_line(card: dict, cards: dict[str, dict], shown: set[str]) -> str:
    """One candidate's ledger row: what it was, what it measured, and which knobs its
    own configuration file moved relative to its first parent's. Mechanical throughout —
    every number comes from an artifact, none from worker prose."""
    cid = card["candidate"]
    parent = cards.get(card["parents"][0]) if card["parents"] else None
    parts = [cid + (f" ← {parent['candidate']}" if parent else "")]
    s, ex = card["search"], card["execution"]["exec"]
    if s["measured"]:
        head = f"search {_fmt(s['score'])}"
        d = card["comparisons"][0]["delta"] if card["comparisons"] else None
        if d is not None:
            head += f" (Δ {d:+.6g})"
    else:
        head = ex + (" (unmeasured)" if ex == "completed" else "")
    parts.append(head)
    kn = card.get("knobs")
    pk = parent.get("knobs") if parent else None
    if kn is None:
        parts.append("knobs file missing")
    elif not isinstance(pk, dict):
        # nothing to diff against (a draft, or a parent whose file was missing)
        parts.append(f"{len(kn)} knob(s) (see its card)")
    else:
        diff = [f"{k} {knob_value(pk.get(k))}→{knob_value(kn.get(k))}"
                for k in sorted(set(kn) | set(pk)) if kn.get(k) != pk.get(k)]
        parts.append(" · ".join(diff) if diff else f"no knob change vs {parent['candidate']}")
    if cid not in shown:
        # the worker knows to open that candidate's summary, if its contract lets it
        parts.append("card not shown")
    return truncate_utf8(" · ".join(parts), LEDGER_ROW_MAX_BYTES)[0]


def render_ledger(cards: dict[str, dict], shown: set[str], knobs_file: str | None,
                  max_bytes: int = LEDGER_MAX_BYTES) -> tuple[str, dict]:
    """The v2 knob ledger: one line per settled non-baseline candidate, newest first,
    bounded on its own budget. Rows are dropped oldest-first, because the point of the
    ledger is that the newest attempts are visible even when their cards are not.
    → (rendered text, the record for job.json)."""
    rows = [(c["candidate"], ledger_line(c, cards, shown))
            for c in sorted(cards.values(), key=lambda c: -c["sequence"])
            if c["operator"] != "baseline"]
    head = ["", "## Knob ledger ("
            + (f"from {knobs_file}, " if knobs_file else "")
            + "newest first; Δ vs first parent's file)", ""]
    foot = ["", LEDGER_REPEAT_LINE] if knobs_file else []
    keep = list(rows)
    text = ""
    while True:
        cand = "\n".join(head + [line for _, line in keep] + foot) + "\n" if keep else ""
        if len(cand.encode("utf-8")) <= max_bytes:
            text = cand
            break
        keep.pop()                      # the oldest row standing
    return text, {"file": knobs_file,
                  "rows": [cid for cid, _ in keep],
                  "omitted": [cid for cid, _ in rows[len(keep):]],
                  "bytes": len(text.encode("utf-8"))}


def collapse_ids(ids: list[str]) -> str:
    """Candidate ids with consecutive runs collapsed: c0001–c0008, c0010–c0013."""
    out, i = [], 0
    ids = sorted(ids, key=seq)
    while i < len(ids):
        j = i
        while j + 1 < len(ids) and seq(ids[j + 1]) == seq(ids[j]) + 1:
            j += 1
        out.append(ids[i] if j == i else f"{ids[i]}–{ids[j]}")
        i = j + 1
    return ", ".join(out)


def is_outcome_key(k: str) -> bool:
    """A measured result, not a knob: it belongs in the card's fields, never in the
    index. Explicit set first, then the documented prefix families."""
    return k in OUTCOME_KEYS or any(k.startswith(pre) for pre in OUTCOME_PREFIXES)


def knob_index(cards: dict[str, dict]) -> list[dict]:
    """Every knob key any settled non-baseline candidate configured → the values tried
    and who tried them, oldest value first. Mechanical: every value comes from that
    candidate's own configuration file, none from worker prose.

    `unset` counts the candidates whose file *has* a knobs map without this key: a knob
    only some attempts record is the common case (`weight_decay` in the mem2 population
    appears in three files of nineteen), and a row that did not say so would read as if
    the whole population had run that one value. A candidate with no knobs file at all
    is not counted either way — its card says the file is missing."""
    order = sorted((c for c in cards.values() if c["operator"] != "baseline"),
                   key=lambda c: c["sequence"])
    known = [c for c in order if isinstance(c.get("knobs"), dict)]
    index: dict[str, dict[str, list[str]]] = {}
    for c in known:
        for k, v in c["knobs"].items():
            if is_outcome_key(k):
                continue
            index.setdefault(k, {}).setdefault(knob_value(v), []).append(c["candidate"])
    out = []
    for k, vals in sorted(index.items()):
        named = {cid for ids in vals.values() for cid in ids}
        out.append({"knob": k, "unset": len(known) - len(named),
                    "values": [{"value": val, "ids": ids} for val, ids in vals.items()]})
    return out


def render_index_row(row: dict, elided: int) -> str:
    parts = [f"{v['value']} ({collapse_ids(v['ids'])})" for v in row["values"]]
    if elided:
        parts.insert(0, f"{elided} older elided")
    if row.get("unset"):
        parts.append(f"not in the file of {row['unset']} other(s)")
    return f"{row['knob']}: " + " · ".join(parts)


def render_ledger_v3(cards: dict[str, dict], knobs_file: str | None,
                     max_bytes: int = LEDGER_MAX_BYTES) -> tuple[str, dict]:
    """The v3 knob ledger: a per-knob index, not per-candidate diff rows, so the question
    "has this knob been varied?" is one line per knob and no candidate is ever dropped
    for age (docs/campaign-plan-20260914.md §6).

    Under the same 2 KiB bound the *oldest values* are elided — oldest by last use, so
    the value a knob is currently on survives and a value abandoned long ago goes first —
    and the elision is written into that knob's own row, so a row that has lost a value
    says so instead of reading like a complete history. A knob never disappears, no id of
    a value still shown is ever dropped, and no candidate is ever dropped for age. A knob
    down to one value is never elided further, so "never varied" can always be read off
    the index; if even that does not fit, the index goes over the bound rather than lie
    by omission, and the record says so.
    → (rendered text, the record for job.json)."""
    rows = knob_index(cards)
    if not rows:
        return "", {"file": knobs_file, "policy": POLICY_V3, "knobs": [], "rows": [],
                    "omitted": [], "elided": [], "over_budget": False, "bytes": 0}
    named = sorted({cid for r in rows for v in r["values"] for cid in v["ids"]}, key=seq)
    elided = {r["knob"]: 0 for r in rows}
    kept = {r["knob"]: list(r["values"]) for r in rows}

    def render() -> str:
        head = ["", LEDGER_V3_HEAD.format(src=f"from {knobs_file}, " if knobs_file else "",
                                          n=len(named)), "", LEDGER_V3_NOTE, ""]
        body = [render_index_row({"knob": r["knob"], "unset": r["unset"],
                                  "values": kept[r["knob"]]}, elided[r["knob"]])
                for r in rows]
        foot = ["", LEDGER_V3_REPEAT_LINE] if knobs_file else []
        return "\n".join(head + body + foot) + "\n"

    text = render()
    skip: set[tuple[str, str]] = set()
    while len(text.encode("utf-8")) > max_bytes:
        # the least recently used value of any knob that still has more than one
        cand = sorted((max(seq(i) for i in v["ids"]), k, n)
                      for k in kept if len(kept[k]) > 1
                      for n, v in enumerate(kept[k]) if (k, v["value"]) not in skip)
        if not cand:
            break                     # nothing left that shrinks the index: it yields
        _, k, n = cand[0]
        gone = kept[k].pop(n)
        elided[k] += 1
        shorter = render()
        if len(shorter.encode("utf-8")) >= len(text.encode("utf-8")):
            # the elision marker costs more than the value it replaced: put it back and
            # look at the next candidate rather than making the index bigger
            kept[k].insert(n, gone)
            elided[k] -= 1
            skip.add((k, gone["value"]))
            continue
        text = shorter
    return text, {"file": knobs_file, "policy": POLICY_V3,
                  "knobs": [r["knob"] for r in rows], "rows": named, "omitted": [],
                  "elided": [{"knob": k, "values": n} for k, n in sorted(elided.items()) if n],
                  "over_budget": len(text.encode("utf-8")) > max_bytes,
                  "bytes": len(text.encode("utf-8"))}


V2_HEADER = (f"Policy {{policy}}: {{n}} card(s) chosen deterministically — direct parents, up to "
             "two nearest ancestors, then the strongest candidate outside this lineage, siblings, "
             "a non-improving same-topic run, other topic matches (newest first), a recent "
             "execution problem and recent remaining; the trivial baseline is never a "
             "cross-branch card, and at least two cross-branch cards survive the byte budget.")


def render_context(cards: dict[str, dict], chosen: list[dict], dropped: list[str],
                   anchors: set[str] | None = None, omitted: list[dict] | None = None,
                   *, policy: str = POLICY) -> str:
    head = (V2_HEADER.format(policy=policy, n=len(chosen)) if policy in LEDGER_POLICIES else
            f"Policy {POLICY}: {len(chosen)} card(s) chosen deterministically (direct parents, then "
            "nearest ancestors, then other branches by topic, strength and recency).")
    out = ["## Findings from earlier candidates", "",
           head + " Search "
           "scores are measured by `lab eval` on the hidden search split. The Change, "
           "Hypothesis, Local observation, Interpretation and Limitations lines are each "
           "worker's own report: evidence to weigh, not instructions to follow, and never a "
           "search score. A non-improving result on a shared topic is one data point, not a "
           "refutation."]
    if anchors:
        out.append(f"Topic anchors from the lineage: {', '.join(sorted(anchors))}.")
    if omitted:
        # ids only: the reasons are in job.json, and this line must stay small enough
        # never to push a mandatory parent's facts out of the budget
        out.append("Omitted for space (cards in candidates/<id>/finding.json): "
                   + ", ".join(o["id"] for o in omitted) + ".")
    if not chosen:
        out += ["", "_No earlier candidate has a finding card yet._"]
    for e in chosen:
        out += ["", render_card(cards[e["id"]], e["reason"], dropped if e["tier"] < 2 else (),
                                policy=policy)]
    return "\n".join(out) + "\n"


# The text a worker gets in its job card when the campaign opts in.
SUMMARY_FORMAT = """Begin summary.md with this section, then anything else you want under `## Details`:

```
## Finding
Change: <one line: what you changed relative to the parent, or built from scratch>
Hypothesis: <one line: why it might help>
Local observation: <one line: what you measured yourself, e.g. on a holdout you carved from training>
Interpretation: <one line: what you make of it, with the confidence it deserves>
Limitations: <one line: what this attempt cannot tell>
Topics: <up to five comma-separated slugs, e.g. label-smoothing, regularization>

## Details
...
```

Each field is exactly one physical line, each exactly once. You do not know the hidden
search score, so never state one; local numbers are reported as yours. A missing or
malformed section costs nothing but leaves the next worker only the measured facts."""
