#!/usr/bin/env python3
"""Unit tests for tools/lab_findings.py — the pure part of the finding cards.

Stdlib only, no filesystem, no campaign, no labels: every card here is synthetic and
built through build_card, exactly as `lab` builds a real one. Run directly; a failed
assertion exits non-zero and names the check.

    python3 scripts/fixtures/findings/test_findings.py
"""
import copy
import json
import os
import random
import sys
from pathlib import Path

TOOLS = os.environ.get("LAB_TOOLS") or str(Path(__file__).resolve().parents[3] / "tools")
sys.path.insert(0, TOOLS)
import lab_findings as F   # noqa: E402

FAILED = []
CHECKED = 0


def check(desc, cond):
    global CHECKED
    CHECKED += 1
    if not cond:
        FAILED.append(desc)


def check_eq(desc, got, want):
    check(f"{desc} (got {got!r}, want {want!r})", got == want)


def raises(desc, fn):
    try:
        fn()
    except F.ToolingError:
        check(desc, True)
        return
    except Exception as e:            # noqa: BLE001 — any other error is a failure
        check(f"{desc} (raised {e.__class__.__name__}: {e})", False)
        return
    check(f"{desc} (nothing raised)", False)


# ---------------------------------------------------------------------------
# fixtures
# ---------------------------------------------------------------------------

EXAMPLE = """# c0004 (improve)

## Finding
Change: Add label smoothing 0.1 to the parent's training recipe.
Hypothesis: It may reduce overconfidence after longer training.
Local observation: Training holdout accuracy rose in this run.
Interpretation: Worth checking on another seed; not established yet.
Limitations: Different training seed and internal holdout membership.
Topics: label-smoothing, regularization

## Details
Full description, training metrics, timings and caveats go here.
"""


def section(change="a change", hypothesis="a hypothesis", local="a local observation",
            interpretation="an interpretation", limitations="a limitation",
            topics="alpha", tail="\n## Details\n\nbody\n"):
    return ("## Finding\n"
            f"Change: {change}\n"
            f"Hypothesis: {hypothesis}\n"
            f"Local observation: {local}\n"
            f"Interpretation: {interpretation}\n"
            f"Limitations: {limitations}\n"
            f"Topics: {topics}\n" + tail).encode("utf-8")


CAMPAIGN = {"id": "unit", "sha256": "f" * 64, "higher_is_better": True}


def search_record(score, n=20):
    return {"score": score, "n": n, "evaluator": "eval/score.py",
            "evaluator_sha256": "a" * 64, "privilege_separation": False,
            "ts": "2026-09-12T00:00:00Z", "error": None}


def make_card(cid, parents=(), *, score=None, exec_="completed", seed=1, hib=True,
              parent_facts=None, summary=None, fail_reason=None, fitness=None,
              config=None, redact=F._identity, private_paths=(), operator="improve",
              redispatch_of=None):
    """A card built the way `lab` builds one: evaluator facts apart from worker prose."""
    if fitness is None and score is not None:
        fitness = {"search": search_record(score)}
    if parent_facts is None:
        parent_facts = [{"id": p, "score": None, "seed": seed} for p in parents]
    if config is None:
        config = {"seed": seed, "git_commit": "abc1234",
                  "agent": {"requested": "claude-sonnet-5", "served": [], "served_source": "none"}}
    return F.build_card(
        campaign=dict(CAMPAIGN, higher_is_better=hib),
        candidate={"id": cid, "operator": operator if parents else ("baseline" if cid == "c0000" else "draft"),
                   "parents": list(parents), "exec": exec_, "fail_reason": fail_reason,
                   "redispatch_of": redispatch_of, "defers": 1 if redispatch_of else 0},
        config=config, fitness=fitness, parents=parent_facts,
        summary=section() if summary is None else summary,
        created_at="2026-09-12T00:00:00Z", redact=redact, private_paths=private_paths)


# ---------------------------------------------------------------------------
# 1. parse_summary
# ---------------------------------------------------------------------------

r = F.parse_summary(EXAMPLE.encode("utf-8"))
check_eq("the plan's example section parses ok", r["status"], "ok")
check_eq("example: Change", r["fields"]["change"],
         "Add label smoothing 0.1 to the parent's training recipe.")
check_eq("example: Local observation", r["fields"]["local_observation"],
         "Training holdout accuracy rose in this run.")
check_eq("example: Limitations", r["fields"]["limitations"],
         "Different training seed and internal holdout membership.")
check_eq("example: topics", r["fields"]["topics"], ["label-smoothing", "regularization"])
check_eq("example: nothing truncated", r["truncated"], [])
check_eq("example: no warnings", r["warnings"], [])

check_eq("no summary at all is missing", F.parse_summary(None)["status"], "missing")
check_eq("a summary without the section is missing",
         F.parse_summary(b"# c0001\n\nsome prose\n")["status"], "missing")
check("a missing section warns instead of failing the candidate",
      F.parse_summary(b"# c0001\n")["warnings"] and
      F.parse_summary(b"# c0001\n")["fields"] is None)

two = section() + b"\n## Finding\nChange: again\n"
r = F.parse_summary(two)
check_eq("two Finding sections are malformed", r["status"], "malformed")
check("the reason names 2 sections", any("2 `## Finding` sections" in w for w in r["warnings"]))
check_eq("a malformed report carries no fields", r["fields"], None)

fenced = b"# c0001\n\n```\n## Finding\nChange: not a real section\n```\n\n" + section()
r = F.parse_summary(fenced)
check_eq("a `## Finding` inside a fenced block is ignored", r["status"], "ok")
check_eq("the real section is the one parsed", r["fields"]["change"], "a change")

only_fenced = b"# c0001\n\n~~~\n## Finding\nChange: fenced\n~~~\n"
check_eq("a section that exists only inside a fence is missing",
         F.parse_summary(only_fenced)["status"], "missing")

dup = section().replace(b"Hypothesis: a hypothesis\n",
                        b"Hypothesis: a hypothesis\nChange: twice\n")
r = F.parse_summary(dup)
check_eq("a duplicate field is malformed", r["status"], "malformed")
check("the reason names the duplicate field", any("duplicate field Change" in w for w in r["warnings"]))

cont = section().replace(b"Topics: alpha\n", b"Topics: alpha\n  continued prose\n")
r = F.parse_summary(cont)
check_eq("a continuation line is malformed", r["status"], "malformed")
check("the reason names the offending line",
      any("is not a `Field: value` line" in w for w in r["warnings"]))

unknown = section().replace(b"Topics: alpha\n", b"Topics: alpha\nEvidence: strong\n")
check_eq("an unknown field is malformed", F.parse_summary(unknown)["status"], "malformed")

missing_field = section().replace(b"Limitations: a limitation\n", b"")
r = F.parse_summary(missing_field)
check_eq("a missing field is malformed", r["status"], "malformed")
check("the reason names the missing field", any("missing field Limitations" in w for w in r["warnings"]))

empty = section(change="   ")
r = F.parse_summary(empty)
check_eq("an empty field is malformed", r["status"], "malformed")
check("the reason names the empty field", any("empty field Change" in w for w in r["warnings"]))

r = F.parse_summary(b"## Finding\nChange: \xff\xfe not utf-8\n")
check_eq("invalid UTF-8 is undecodable", r["status"], "undecodable")
check("the undecodable warning explains itself", any("UTF-8" in w for w in r["warnings"]))
check_eq("an undecodable summary yields no fields", r["fields"], None)

long_change = "é" * 600                       # 1200 bytes
r = F.parse_summary(section(change=long_change))
check_eq("an oversized field still parses ok", r["status"], "ok")
check_eq("the oversized field is named as truncated", r["truncated"], ["change"])
check("the truncated field ends with the marker", r["fields"]["change"].endswith(F.TRUNCATED))
check("the truncated field fits its byte bound",
      len(r["fields"]["change"].encode("utf-8")) <= F.FIELD_BYTES["change"])
check("truncation never splits a code point", "�" not in r["fields"]["change"])
check("the other fields are untouched", r["fields"]["hypothesis"] == "a hypothesis")
check("truncation is warned about", any("truncated" in w for w in r["warnings"]))

r = F.parse_summary(section(limitations="字" * 400))     # 1200 bytes
check_eq("Limitations gets its own, larger bound", r["truncated"], ["limitations"])
check("Limitations fits 768 bytes",
      len(r["fields"]["limitations"].encode("utf-8")) <= F.FIELD_BYTES["limitations"])
check("a 768-byte Limitations is still whole text",
      r["fields"]["limitations"].endswith(F.TRUNCATED) and "字" in r["fields"]["limitations"])

r = F.parse_summary(section(limitations="字" * 200))      # 600 bytes: under 768, over 512
check_eq("a 600-byte Limitations is not truncated", r["truncated"], [])

s, cut = F.truncate_utf8("字" * 10, 24)
check("truncate_utf8 honours the limit", len(s.encode("utf-8")) <= 24 and cut)
check("truncate_utf8 never splits a code point", "…" in s and "\ufffd" not in s)
check_eq("truncate_utf8 leaves a short string alone", F.truncate_utf8("abc", 10), ("abc", False))

r = F.parse_summary(section(topics="Label smoothing, label_smoothing, A B"))
check_eq("topics are normalised and deduplicated", r["fields"]["topics"], ["label-smoothing", "a-b"])
r = F.parse_summary(section(topics="t1, t2, t3, t4, t5, t6, t7"))
check_eq("at most five topics are kept", r["fields"]["topics"], ["t1", "t2", "t3", "t4", "t5"])
check("the omitted topics are warned about", any("beyond the first 5" in w for w in r["warnings"]))
r = F.parse_summary(section(topics="good, bad!"))
check_eq("an invalid slug is malformed", r["status"], "malformed")
check("the reason names the bad slug", any("not a slug" in w for w in r["warnings"]))
check_eq("an empty Topics list is malformed", F.parse_summary(section(topics="  "))["status"], "malformed")
check_eq("an over-long slug is malformed", F.parse_summary(section(topics="x" * 33))["status"], "malformed")
slugs, warns, errs = F.parse_topics("a, a, b")
check_eq("parse_topics dedupes in input order", slugs, ["a", "b"])
check_eq("parse_topics reports no error for a clean list", errs, [])

ends = section(tail="\n## Details\n\nTopics: ignored, here\nChange: also ignored\n")
r = F.parse_summary(ends)
check_eq("the section ends at the next heading", r["status"], "ok")
check_eq("fields after the next heading are not parsed", r["fields"]["topics"], ["alpha"])
ends1 = section(tail="\n# Appendix\n\nChange: ignored\n")
check_eq("a level-one heading ends the section too", F.parse_summary(ends1)["status"], "ok")
check_eq("a section running to EOF parses", F.parse_summary(section(tail=""))["status"], "ok")

# --- headings as CommonMark reads them, and what one physical line is ---------

def with_heading(head, tail="\n## Details\n\nbody\n"):
    return (head + "\n"
            "Change: a change\n"
            "Hypothesis: a hypothesis\n"
            "Local observation: a local observation\n"
            "Interpretation: an interpretation\n"
            "Limitations: a limitation\n"
            "Topics: alpha\n" + tail).encode("utf-8")


check_eq("`## Finding#` is text, not a heading",
         F.parse_summary(with_heading("## Finding#"))["status"], "missing")
check_eq("a heading indented three spaces is still a heading",
         F.parse_summary(with_heading("   ## Finding"))["status"], "ok")
check_eq("a heading indented four spaces is code, not a heading",
         F.parse_summary(with_heading("    ## Finding"))["status"], "missing")
check_eq("closing hashes are allowed", F.parse_summary(with_heading("## Finding ##"))["status"], "ok")
check_eq("a tab after the hashes is allowed",
         F.parse_summary(with_heading("##\tFinding"))["status"], "ok")
indented_end = section(tail="\n  ## Details\n\nChange: ignored after the heading\n")
r = F.parse_summary(indented_end)
check_eq("an indented heading ends the section too", r["status"], "ok")
check_eq("nothing after that heading is parsed", r["fields"]["change"], "a change")
not_a_fence = b"# c0001\n\n    ```\n\n" + section()
check_eq("a four-space-indented fence is code, not a fence",
         F.parse_summary(not_a_fence)["status"], "ok")

r = F.parse_summary(section().replace(b"\n", b"\r\n"))
check_eq("CRLF line endings parse", r["status"], "ok")
check_eq("CRLF leaves no carriage return in a field", r["fields"]["topics"], ["alpha"])
r = F.parse_summary("\ufeff".encode("utf-8") + section())
check_eq("a UTF-8 BOM parses", r["status"], "ok")
check_eq("the BOM does not leak into the first field", r["fields"]["change"], "a change")

for name, sep in (("a vertical tab", "\x0b"), ("U+2028", "\u2028")):
    joined = ("## Finding\n"
              f"Change: a change{sep}Hypothesis: a hypothesis\n"
              "Local observation: a local observation\n"
              "Interpretation: an interpretation\n"
              "Limitations: a limitation\n"
              "Topics: alpha\n").encode("utf-8")
    r = F.parse_summary(joined)
    check_eq(f"{name} does not start a new physical line", r["status"], "malformed")
    check(f"{name} leaves Hypothesis missing, not smuggled in",
          any("missing field Hypothesis" in w for w in r["warnings"]))

r = F.parse_summary(section(topics="a, b,"))
check_eq("a trailing comma in Topics is malformed", r["status"], "malformed")
check("the reason names the empty element", any("empty element" in w for w in r["warnings"]))
r = F.parse_summary(section(topics="K"))
check_eq("the Kelvin sign is not a slug", r["status"], "malformed")
check("it is refused, not case-folded to k", any("not a slug" in w for w in r["warnings"]))

noisy = section().replace(b"Topics: alpha\n",
                          b"Topics: alpha\n" + b"".join(b"stray prose %d\n" % i for i in range(50)))
r = F.parse_summary(noisy)
check_eq("fifty stray lines are malformed", r["status"], "malformed")
check_eq("the warnings are bounded to eight plus a count", len(r["warnings"]), F.MAX_WARNINGS + 1)
check("the count says how many were not listed",
      r["warnings"][-1] == "and 42 more problem(s) not listed")
check("every warning is bounded in bytes",
      all(len(w.encode("utf-8")) <= 200 for w in r["warnings"]))
noisy_card = make_card("c0002", ["c0001"], score=3.0, summary=noisy,
                       parent_facts=[{"id": "c0001", "score": 2.0, "seed": 1}])
check_eq("a noisy report still builds a valid card", F.validate_card(noisy_card), [])
check("the card carries the bounded warnings, not the flood",
      len(noisy_card["report"]["warnings"]) == F.MAX_WARNINGS + 1)

# ---------------------------------------------------------------------------
# 2. build_card / validate_card
# ---------------------------------------------------------------------------

card = make_card("c0001", ["c0000"], score=-0.5,
                 parent_facts=[{"id": "c0000", "score": -1.0, "seed": 1}])
check_eq("a built card is valid", F.validate_card(card), [])
check_eq("the card carries its schema", card["schema"], F.SCHEMA)
check_eq("the card carries its sequence", card["sequence"], 1)
check_eq("measured search score comes from fitness.json", card["search"]["score"], -0.5)
check_eq("search n comes from fitness.json", card["search"]["n"], 20)
check_eq("the card records the evaluator fingerprint", card["search"]["evaluator_sha256"], "a" * 64)
check_eq("artifacts are relative references", card["provenance"]["artifacts"]["summary"],
         "candidates/c0001/summary.md")

invented = section(change="halved the loss — search fitness -0.001 measured by me",
                   local="search score -0.0001 (I measured the hidden split myself)")
card = make_card("c0001", ["c0000"], score=-0.5, summary=invented,
                 parent_facts=[{"id": "c0000", "score": -1.0, "seed": 1}])
check_eq("a worker's invented score never becomes the measured score", card["search"]["score"], -0.5)
check("the invented number stays in the worker's own words",
      "-0.001" in card["report"]["change"])
check("the local observation is labelled worker-reported",
      "worker-reported" in card["report"]["source"])
check_eq("the comparison uses the measured scores only", card["comparisons"][0]["delta"], 0.5)

hi = make_card("c0002", ["c0001"], score=3.0, hib=True,
               parent_facts=[{"id": "c0001", "score": 2.0, "seed": 1}])
check_eq("higher-is-better: delta", hi["comparisons"][0]["delta"], 1.0)
check_eq("higher-is-better: the metric direction is recorded", hi["metric"]["higher_is_better"], True)
check_eq("higher-is-better: a gain is improving", F.non_improving(hi), False)
lo = make_card("c0002", ["c0001"], score=3.0, hib=False,
               parent_facts=[{"id": "c0001", "score": 2.0, "seed": 1}])
check_eq("lower-is-better: the same delta", lo["comparisons"][0]["delta"], 1.0)
check_eq("lower-is-better: the same delta is non-improving", F.non_improving(lo), True)
tie = make_card("c0002", ["c0001"], score=2.0, hib=True,
                parent_facts=[{"id": "c0001", "score": 2.0, "seed": 1}])
check_eq("a tie is non-improving", F.non_improving(tie), True)
check("a delta is never called an effect", "not an effect attributed" in hi["comparison_note"])

xo = make_card("c0003", ["c0001", "c0002"], score=2.5, operator="crossover",
               parent_facts=[{"id": "c0001", "score": 2.0, "seed": 1},
                             {"id": "c0002", "score": 3.0, "seed": 1}])
check_eq("crossover parents produce two comparisons", len(xo["comparisons"]), 2)
check_eq("crossover: both raw deltas are published",
         [c["delta"] for c in xo["comparisons"]], [0.5, -0.5])
check_eq("crossover: not beating the strongest parent is non-improving", F.non_improving(xo), True)

nos = make_card("c0002", ["c0001"], score=3.0,
                parent_facts=[{"id": "c0001", "score": None, "seed": 1}])
check_eq("a missing parent score gives no delta", nos["comparisons"][0]["delta"], None)
check_eq("a missing parent score is not non-improving", F.non_improving(nos), False)
check_eq("a card is valid with a null delta", F.validate_card(nos), [])
unmeasured = make_card("c0002", ["c0001"], score=None,
                       parent_facts=[{"id": "c0001", "score": 2.0, "seed": 1}])
check_eq("an unmeasured attempt has no score", unmeasured["search"]["measured"], False)
check_eq("an unmeasured attempt is not non-improving", F.non_improving(unmeasured), False)
check("an unmeasured completion says so",
      any("no search measurement" in c for c in unmeasured["caveats"]))

diff = make_card("c0002", ["c0001"], score=3.0, seed=7,
                 parent_facts=[{"id": "c0001", "score": 2.0, "seed": 5}])
check("a different seed is an explicit caveat",
      any("seed 7 differs from c0001's seed 5" in c for c in diff["caveats"]))
same = make_card("c0002", ["c0001"], score=3.0, seed=7,
                 parent_facts=[{"id": "c0001", "score": 2.0, "seed": 7}])
check("an equal seed still leaves matched runs unverified",
      any("still unverified" in c for c in same["caveats"]))
noseed = make_card("c0002", ["c0001"], score=3.0, config={"seed": None},
                   parent_facts=[{"id": "c0001", "score": 2.0, "seed": None}])
check("an unrecorded seed says so",
      any("unrecorded" in c for c in noseed["caveats"]))

for bad in F.PROBLEM_EXEC:
    c = make_card("c0002", ["c0001"], score=None, exec_=bad, fail_reason="exit 3",
                  parent_facts=[{"id": "c0001", "score": 2.0, "seed": 1}])
    check(f"exec {bad} is not evidence about the method",
          any("not evidence about the method" in x for x in c["caveats"]))
    check_eq(f"exec {bad} is never non-improving", F.non_improving(c), False)
    check_eq(f"exec {bad} is recorded as such", c["execution"]["exec"], bad)
raises("an unsettled exec is a tooling error",
       lambda: make_card("c0002", ["c0001"], exec_="running"))
raises("a parent that is not earlier is a tooling error",
       lambda: make_card("c0002", ["c0003"]))
raises("parent facts that disagree with the population are a tooling error",
       lambda: F.build_card(campaign=CAMPAIGN,
                            candidate={"id": "c0002", "operator": "improve", "parents": ["c0001"],
                                       "exec": "completed", "fail_reason": None,
                                       "redispatch_of": None, "defers": 0},
                            config=None, fitness=None,
                            parents=[{"id": "c0000", "score": 1.0, "seed": 1}],
                            summary=section(), created_at="2026-09-12T00:00:00Z"))

with_final = make_card("c0002", ["c0001"], score=3.0,
                       fitness={"search": search_record(3.0),
                                "final": {"score": 9.99, "n": 5, "evaluator": "eval/score.py"}},
                       parent_facts=[{"id": "c0001", "score": 2.0, "seed": 1}])
keys = set(F._keys_recursive(with_final))
check("no `final` key anywhere in a card", "final" not in keys)
check("no final score leaks into a card", "9.99" not in json.dumps(with_final))
check_eq("the search score is still the measured one", with_final["search"]["score"], 3.0)
check_eq("a fitness.json with a final entry hashes only the search record",
         with_final["integrity"]["search_record_sha256"], F.digest(search_record(3.0)))
injected = copy.deepcopy(with_final)
injected["search"]["final"] = {"score": 1.0}
check("validate_card rejects an injected final key",
      any("forbidden key" in p for p in F.validate_card(injected)))

SECRET = "sk-ant-api03-DEADbeef1234567890"
PRIV = "/var/private/labloop/search"


def redact(s):
    return s.replace(SECRET, "[REDACTED]")


leaky = section(hypothesis=f"token {SECRET} and path {PRIV}/labels.json in prose")
card = make_card("c0002", ["c0001"], score=None, summary=leaky, redact=redact,
                 private_paths=(PRIV,), fail_reason=f"crashed reading {PRIV}/labels.json with {SECRET}",
                 exec_="failed", parent_facts=[{"id": "c0001", "score": 2.0, "seed": 1}])
blob = json.dumps(card, ensure_ascii=False)
check("the secret never reaches the card", SECRET not in blob)
check("the private path never reaches the card", PRIV not in blob)
check("the redaction marker is visible in the report", "[REDACTED]" in card["report"]["hypothesis"])
check("the private path is marked in the report", "[private path]" in card["report"]["hypothesis"])
check("the sanitized failure reason is kept", card["execution"]["reason"])
check("the failure reason is scrubbed too",
      SECRET not in card["execution"]["reason"] and PRIV not in card["execution"]["reason"])

summary = section()
fitness = {"search": search_record(3.0)}
candidate = {"id": "c0002", "operator": "improve", "parents": ["c0001"], "exec": "completed"}
card = make_card("c0002", ["c0001"], score=3.0, summary=summary,
                 parent_facts=[{"id": "c0001", "score": 2.0, "seed": 1}])
src = dict(campaign_id="unit", campaign_sha256="f" * 64, candidate=candidate,
           summary=summary, fitness=fitness)
check_eq("a card agrees with its own sources", F.check_card_sources(card, **src), [])
check("a changed summary is detected",
      any("summary_sha256" in p for p in F.check_card_sources(
          card, **dict(src, summary=section(change="edited")))))
check("a changed search record is detected",
      any("search_record_sha256" in p for p in F.check_card_sources(
          card, **dict(src, fitness={"search": search_record(3.5)}))))
check("a changed score is detected",
      any("search.score does not match" in p for p in F.check_card_sources(
          card, **dict(src, fitness={"search": search_record(3.5)}))))
check("a changed exec is detected",
      any("execution.exec" in p for p in F.check_card_sources(
          card, **dict(src, candidate=dict(candidate, exec="failed")))))
check("a changed campaign is detected",
      any("campaign" in p for p in F.check_card_sources(card, **dict(src, campaign_id="other"))))
check("an added final entry does not disturb the source check",
      F.check_card_sources(card, **dict(src, fitness=dict(fitness, final={"score": 1.0}))) == [])

check("a changed n is detected",
      any("search.n does not match" in p for p in F.check_card_sources(
          card, **dict(src, fitness={"search": search_record(3.0, n=21)}))))
check("a changed evaluator fingerprint is detected",
      any("search.evaluator_sha256 does not match" in p for p in F.check_card_sources(
          card, **dict(src, fitness={"search": dict(search_record(3.0), evaluator_sha256="b" * 64)}))))
check("a changed evaluator is detected",
      any("search.evaluator does not match" in p for p in F.check_card_sources(
          card, **dict(src, fitness={"search": dict(search_record(3.0), evaluator="other.py")}))))
check("a changed evaluation timestamp is detected",
      any("search.ts does not match" in p for p in F.check_card_sources(
          card, **dict(src, fitness={"search": dict(search_record(3.0), ts="2020-01-01T00:00:00Z")}))))
check("a card measured against a fitness.json with no search record is detected",
      any("no search record" in p for p in F.check_card_sources(card, **dict(src, fitness={}))))
check("validate_card refuses a non-object", F.validate_card("nope"))
check("validate_card refuses a card with no schema", F.validate_card({"candidate": "c0001"}))
broken = copy.deepcopy(card)
broken["report"]["topics"] = ["Alpha!"]
check("validate_card refuses a non-slug topic", F.validate_card(broken))
broken = copy.deepcopy(card)
broken["provenance"]["artifacts"]["code"] = "/etc/passwd"
check("validate_card refuses an absolute artifact path", F.validate_card(broken))
broken = copy.deepcopy(card)
broken["sequence"] = 99
check("validate_card refuses a sequence that disagrees with the id", F.validate_card(broken))

raw_bin = section() + b"\n\xff\xfe not utf-8\n"
bincard = make_card("c0002", ["c0001"], score=3.0, summary=raw_bin,
                    parent_facts=[{"id": "c0001", "score": 2.0, "seed": 1}])
check_eq("a non-UTF-8 summary yields a facts-only card", bincard["report"]["status"], "undecodable")
check_eq("a facts-only card is still valid", F.validate_card(bincard), [])
check_eq("the measured facts survive an unreadable summary", bincard["search"]["score"], 3.0)
check_eq("the card fingerprints the exact bytes on disk",
         bincard["integrity"]["summary_sha256"], F.digest_bytes(raw_bin))
check("the card says the report could not be read",
      any("undecodable" in c for c in bincard["caveats"]))
check_eq("no prose is invented from unreadable bytes", bincard["report"]["change"], None)

good = make_card("c0002", ["c0001"], score=3.0,
                 parent_facts=[{"id": "c0001", "score": 2.0, "seed": 1}])


def rejects(desc, mutate, expect=None):
    c = copy.deepcopy(good)
    mutate(c)
    problems = F.validate_card(c)
    check(f"{desc} ({problems})", bool(problems) and (expect is None or any(expect in x for x in problems)))


rejects("validate_card refuses an extra top-level key", lambda c: c.update({"final_score": 1.0}))
rejects("validate_card refuses an extra key inside search",
        lambda c: c["search"].update({"leaked": 1}))
rejects("validate_card refuses a missing top-level key", lambda c: c.pop("caveats"))
rejects("validate_card refuses a string search.n", lambda c: c["search"].update({"n": "20"}))
rejects("validate_card refuses a score that is not measured",
        lambda c: c["search"].update({"measured": False}), "must be null when not measured")
rejects("validate_card refuses a measured score on a failed attempt",
        lambda c: c["execution"].update({"exec": "failed"}), "requires execution.exec completed")
rejects("validate_card refuses a delta with no parent score",
        lambda c: c["comparisons"][0].update({"parent_score": None}),
        "delta needs both a measured score and a parent score")
rejects("validate_card refuses a repeated parent", lambda c: c.update({"parents": ["c0001", "c0001"]}))
rejects("validate_card refuses a multi-line caveat", lambda c: c["caveats"].append("two\nlines"))
rejects("validate_card refuses an unbounded warning",
        lambda c: c["report"].update({"warnings": ["x" * 300]}))
check_eq("the good card itself stays valid", F.validate_card(good), [])

failed_measured = copy.deepcopy(tie)
failed_measured["execution"]["exec"] = "failed"
check_eq("a problem exec is never non-improving, even with a score",
         F.non_improving(failed_measured), False)
check("and the schema refuses that combination in the first place",
      any("requires execution.exec completed" in x for x in F.validate_card(failed_measured)))

WPRIV = "/p/private labels"
spaced = section(hypothesis="path /p/private\tlabels/x in prose")
card = make_card("c0002", ["c0001"], score=3.0, summary=spaced, private_paths=(WPRIV,),
                 parent_facts=[{"id": "c0001", "score": 2.0, "seed": 1}])
check("collapsing whitespace cannot re-form a private path",
      WPRIV not in json.dumps(card, ensure_ascii=False))
check("the re-formed path is marked instead", "[private path]" in card["report"]["hypothesis"])

check_eq("canonical_json sorts keys and stays compact",
         F.canonical_json({"b": 1, "a": [1, 2]}), b'{"a":[1,2],"b":1}')
check("digest is a prefixed sha256", F.digest({"a": 1}).startswith("sha256:"))
check_eq("digest is stable across key order", F.digest({"a": 1, "b": 2}), F.digest({"b": 2, "a": 1}))

# --- a search record on an attempt that did not complete ----------------------
stray = make_card("c0002", ["c0001"], exec_="failed", fail_reason="worker exited 3",
                  fitness={"search": search_record(3.0)},
                  parent_facts=[{"id": "c0001", "score": 2.0, "seed": 1}])
check_eq("a stray search record does not fail the card build", F.validate_card(stray), [])
check_eq("a stray search record is not a measurement", stray["search"]["measured"], False)
check_eq("and carries no score", stray["search"]["score"], None)
check("the card says the record exists but is not carried",
      any("although it did not complete" in c for c in stray["caveats"]))
check("the execution outcome caveat is still there",
      any("not evidence about the method" in c for c in stray["caveats"]))
check_eq("a stray record leaves the comparison without a delta", stray["comparisons"][0]["delta"], None)
check_eq("a stray record is never non-improving", F.non_improving(stray), False)
check_eq("the card still fingerprints the record it saw",
         stray["integrity"]["search_record_sha256"], F.digest(search_record(3.0)))
check_eq("a card built over a stray record agrees with its sources",
         F.check_card_sources(stray, campaign_id="unit", campaign_sha256="f" * 64,
                              candidate={"id": "c0002", "operator": "improve",
                                         "parents": ["c0001"], "exec": "failed"},
                              summary=section(), fitness={"search": search_record(3.0)}), [])

# --- deferred attempts and their re-dispatch ----------------------------------
dfr1 = make_card("c0002", ["c0001"], exec_="deferred", fail_reason="usage limit: 5-hour window",
                 parent_facts=[{"id": "c0001", "score": 2.0, "seed": 1}])
dfr2 = make_card("c0003", ["c0001"], exec_="deferred", fail_reason="usage limit: 5-hour window",
                 redispatch_of="c0002", parent_facts=[{"id": "c0001", "score": 2.0, "seed": 1}])
check("a first deferral carries no re-dispatch caveat",
      not any("re-dispatch" in c for c in dfr1["caveats"]))
check("a re-dispatch says it is a new attempt, not a replication",
      any("re-dispatch of deferred c0002: a new attempt, not a replication" in c for c in dfr2["caveats"]))
check_eq("the re-dispatch records what it re-dispatches", dfr2["execution"]["redispatch_of"], "c0002")
check_eq("neither deferral is non-improving",
         (F.non_improving(dfr1), F.non_improving(dfr2)), (False, False))
DEF = {"c0000": make_card("c0000", [], score=1.0), "c0002": dfr1, "c0003": dfr2}
dsel = F.select_context(DEF, [])
dreasons = {c["id"]: c["reason"] for c in dsel["cards"]}
check_eq("the strongest tier goes to the one measured card",
         dreasons["c0000"], "strongest measured candidate")
check("a deferred attempt is never the strongest",
      not any("strongest" in dreasons[k] for k in ("c0002", "c0003")))
check("a deferred attempt is offered as an execution problem",
      any("execution problem" in dreasons[k] for k in ("c0002", "c0003")))

# ---------------------------------------------------------------------------
# 3. select_context
# ---------------------------------------------------------------------------

LONG = ("a fairly long line of worker prose so that the byte budget has something to "
        "bite on when the renderer has to shrink the mandatory parent cards ")

POP = [
    # cid,     parents,            score, topics,          exec
    ("c0000", [],                   1.0,  "baseline",      "completed"),
    ("c0001", ["c0000"],            2.0,  "alpha, shared", "completed"),
    ("c0002", ["c0001"],            3.0,  "alpha",         "completed"),
    ("c0003", ["c0002"],            4.0,  "alpha",         "completed"),
    ("c0004", ["c0000"],            2.5,  "beta, shared",  "completed"),
    ("c0005", ["c0004"],            2.4,  "beta",          "completed"),
    ("c0006", ["c0000"],            0.5,  "alpha",         "completed"),
    ("c0007", ["c0006"],            None, "gamma",         "failed"),
    ("c0008", ["c0006"],            5.0,  "gamma",         "completed"),
    ("c0009", ["c0008"],            1.5,  "delta",         "completed"),
    ("c0010", ["c0009"],            1.2,  "epsilon",       "completed"),
    ("c0011", ["c0010"],            1.1,  "zeta",          "completed"),
]
SCORES = {cid: sc for cid, _, sc, _, _ in POP}
CARDS = {}
for cid, parents, score, topics, ex in POP:
    CARDS[cid] = make_card(
        cid, parents, score=score, exec_=ex,
        fail_reason="exit 3" if ex == "failed" else None,
        summary=section(change=LONG + cid, hypothesis=LONG + "hypothesis",
                        local=LONG + "local", interpretation=LONG + "interpretation",
                        limitations=LONG + "limitations", topics=topics),
        parent_facts=[{"id": p, "score": SCORES[p], "seed": 1} for p in parents],
        operator="crossover" if len(parents) > 1 else "improve")

res = F.select_context(CARDS, ["c0003", "c0005"])
ids = [c["id"] for c in res["cards"]]
reasons = {c["id"]: c["reason"] for c in res["cards"]}
check_eq("the policy version is recorded", res["policy"], F.POLICY)
check_eq("direct parents come first, in id order", ids[:2], ["c0003", "c0005"])
check_eq("the first parent is named a direct parent", reasons["c0003"], "direct parent")
check_eq("the second parent is named a direct parent", reasons["c0005"], "direct parent")
check_eq("the nearest ancestors of both sides follow", ids[2:4], ["c0002", "c0004"])
check("an ancestor reachable only through the second parent is selected", "c0004" in ids)
check("ancestors are labelled with their distance", reasons["c0002"].startswith("ancestor at distance 1"))
check_eq("at most two extra ancestors", sum(1 for r in reasons.values() if r.startswith("ancestor")), 2)
check("a non-improving same-topic run from another branch is included", "c0006" in ids)
check("it is labelled a non-improvement, not a refutation",
      reasons["c0006"].startswith("did not beat its strongest parent"))
check("its shared topic is named", "alpha" in reasons["c0006"])
check("the strongest off-lineage candidate is included", "c0008" in ids)
check("a recent execution problem is included", "c0007" in ids)
check("an execution problem is not called a negative finding",
      "not evidence about the method" in reasons["c0007"])
closure = {"c0000", "c0001", "c0002", "c0003", "c0004", "c0005"}
check_eq("no ancestor-closure candidate is picked as another branch",
         sorted(set(ids[4:]) & closure), [])
check_eq("no duplicate ids", len(ids), len(set(ids)))
check("at most max_cards", len(ids) <= F.MAX_CARDS)
check("the rendered context fits the byte budget", res["bytes"] <= F.MAX_BYTES)
check_eq("the reported byte count is the rendered size",
         res["bytes"], len(res["rendered"].encode("utf-8")))
check_eq("the anchors are the lineage's topics", res["anchors"], ["alpha", "beta", "shared"])
check_eq("every selected card carries its digest",
         [c["digest"] for c in res["cards"]], [F.digest(CARDS[i]) for i in ids])
check("the rendered context names its heading", "## Findings from earlier candidates" in res["rendered"])
check("the rendered context says the prose is worker-reported", "worker-reported" in res["rendered"])
check("the rendered context carries a parent's measured score", "search 4" in res["rendered"])
check("no card is silently dropped without a record",
      isinstance(res["omitted"], list))

again = F.select_context(CARDS, ["c0003", "c0005"])
check_eq("selection is byte-identical when repeated", again["rendered"], res["rendered"])
check_eq("the whole snapshot is identical when repeated",
         F.canonical_json(again), F.canonical_json(res))
check_eq("parent order does not matter", [c["id"] for c in F.select_context(CARDS, ["c0005", "c0003"])["cards"]], ids)

rng = random.Random(1234)
before = rng.getstate()
F.select_context(CARDS, ["c0003", "c0005"])
check_eq("selection consumes no randomness", rng.getstate(), before)

few = F.select_context(CARDS, ["c0003", "c0005"], max_cards=5)
check_eq("max_cards is respected", len(few["cards"]), 5)
check_eq("the mandatory cards survive a small max_cards",
         [c["id"] for c in few["cards"]][:4], ["c0003", "c0005", "c0002", "c0004"])

# shrinking the byte budget: optional cards, then ancestors, then parent prose
states = []
errored = False
within = True
mb = res["bytes"]
while mb > 0:
    try:
        r = F.select_context(CARDS, ["c0003", "c0005"], max_bytes=mb)
    except F.ToolingError:
        errored = True
        break
    within = within and r["bytes"] <= mb
    st = (tuple(c["id"] for c in r["cards"]), tuple(r["cards"][0]["omitted_fields"]))
    if not states or states[-1] != st:
        states.append(st)
    mb -= 4
check("the rendered context never exceeds max_bytes, at any budget", within)
check("an impossible byte budget is a tooling error, never a silent drop", errored)
picked_counts = [len(s[0]) for s in states]
check("optional cards are shed one at a time as the budget shrinks",
      picked_counts == sorted(picked_counts, reverse=True) and picked_counts[0] == len(ids))
check_eq("the mandatory parents are the last cards standing", picked_counts[-1], 2)
check("ancestors are shed only after every optional card",
      all(len(s[0]) > 2 or s[0] == ("c0003", "c0005") for s in states))
DROP_ALL = list(F.PROSE_DROP_ORDER) + ["limitations"]
drops = [list(s[1]) for s in states]
check_eq("prose is kept whole while cards can still be dropped", drops[0], [])
check("prose fields are dropped in the specified order",
      all(d == DROP_ALL[:len(d)] for d in drops))
check_eq("every prose field is eventually dropped", drops[-1], DROP_ALL)
check("Limitations is dropped last of all",
      all("limitations" not in d for d in drops[:-1]) and drops[-1][-1] == "limitations")
shrunk = None
for mb in range(res["bytes"], 0, -4):
    try:
        r = F.select_context(CARDS, ["c0003", "c0005"], max_bytes=mb)
    except F.ToolingError:
        break
    if r["cards"][0]["omitted_fields"] == ["interpretation"]:
        shrunk = r
check("a budget exists where only Interpretation is omitted", shrunk is not None)
if shrunk is not None:
    check("an omitted prose field is marked in the rendering", F.OMITTED in shrunk["rendered"])
    check("the omission is recorded per card",
          all(c["omitted_fields"] == ["interpretation"] for c in shrunk["cards"] if c["id"] in ("c0003", "c0005")))
    check("the parents' measured facts survive the shrinking",
          "c0003" in shrunk["rendered"] and "search 4" in shrunk["rendered"])

bare = None
for mb in range(res["bytes"], 0, -4):
    try:
        r = F.select_context(CARDS, ["c0003", "c0005"], max_bytes=mb)
    except F.ToolingError:
        break
    if r["cards"][0]["omitted_fields"] == DROP_ALL:
        bare = r
check("a budget exists where the parents are facts only", bare is not None)
if bare is not None:
    check_eq("a facts-only parent omits all five prose fields",
             bare["cards"][0]["omitted_fields"], DROP_ALL)
    check_eq("the rendering marks every omitted field",
             bare["rendered"].count(F.OMITTED), 5 * len(bare["cards"]))
    check("a facts-only parent keeps its identity and outcome",
          "c0003" in bare["rendered"] and "completed" in bare["rendered"])
    check("a facts-only parent keeps its measured comparison",
          "Parents' search scores:" in bare["rendered"])
    check_eq("only the mandatory parents are left", len(bare["cards"]), 2)
raises("a budget below even the facts-only parents is a tooling error",
       lambda: F.select_context(CARDS, ["c0003", "c0005"], max_bytes=200))

dup = F.select_context(CARDS, ["c0003", "c0003"])
check_eq("a repeated direct parent is selected once",
         [c["id"] for c in dup["cards"] if c["reason"] == "direct parent"], ["c0003"])
check_eq("a repeated direct parent is rendered once", dup["rendered"].count("### c0003 ·"), 1)
raises("max_cards below the number of direct parents is a tooling error",
       lambda: F.select_context(CARDS, ["c0003", "c0005"], max_cards=1))
exact = F.select_context(CARDS, ["c0003", "c0005"], max_cards=2)
check_eq("max_cards equal to the parents admits no ancestor",
         [c["id"] for c in exact["cards"]], ["c0003", "c0005"])
one_more = F.select_context(CARDS, ["c0003", "c0005"], max_cards=3)
check_eq("one slot beyond the parents admits exactly one ancestor",
         [c["id"] for c in one_more["cards"]], ["c0003", "c0005", "c0002"])
check("that one slot goes to an ancestor, not another branch",
      one_more["cards"][2]["reason"].startswith("ancestor at distance 1"))

draft = F.select_context(CARDS, [])
did = [c["id"] for c in draft["cards"]]
check_eq("a draft with no parents starts from the strongest measured candidate", did[0], "c0008")
check_eq("the draft policy says why", draft["cards"][0]["reason"], "strongest measured candidate")
check("a draft also sees a non-improving run",
      any(c["reason"].startswith("newest candidate that did not beat") for c in draft["cards"]))
check("a draft also sees a recent execution problem",
      any("execution problem" in c["reason"] for c in draft["cards"]))
check_eq("a draft has no anchors", draft["anchors"], [])
check_eq("a draft has no duplicates", len(did), len(set(did)))
check("a draft fits both budgets", len(did) <= F.MAX_CARDS and draft["bytes"] <= F.MAX_BYTES)
check_eq("an empty population renders an honest placeholder",
         "_No earlier candidate has a finding card yet._" in F.select_context({}, [])["rendered"], True)

# --- the metric direction runs through selection too --------------------------
LOW = {}
for cid, parents, score, topics, ex in POP:
    LOW[cid] = make_card(
        cid, parents, score=score, exec_=ex, hib=False,
        fail_reason="exit 3" if ex == "failed" else None,
        summary=section(change=LONG + cid, hypothesis=LONG + "hypothesis",
                        local=LONG + "local", interpretation=LONG + "interpretation",
                        limitations=LONG + "limitations", topics=topics),
        parent_facts=[{"id": p, "score": SCORES[p], "seed": 1} for p in parents],
        operator="crossover" if len(parents) > 1 else "improve")

measured_low = [c for c in LOW.values() if c["search"]["measured"]]
check_eq("lower-is-better: the strongest card is the lowest scoring",
         min(measured_low, key=F._strength_key)["candidate"], "c0006")
check_eq("higher-is-better: the strongest card is the highest scoring",
         min((c for c in CARDS.values() if c["search"]["measured"]), key=F._strength_key)["candidate"],
         "c0008")
check_eq("lower-is-better: a higher score than the parent does not beat it",
         F.non_improving(LOW["c0008"]), True)
check_eq("higher-is-better: the same pair is an improvement",
         F.non_improving(CARDS["c0008"]), False)
check_eq("lower-is-better: a lower score than the parent beats it",
         F.non_improving(LOW["c0005"]), False)
check_eq("higher-is-better: the same pair did not beat its parent",
         F.non_improving(CARDS["c0005"]), True)
dlow = F.select_context(LOW, [])
check_eq("a lower-is-better draft starts from the lowest score",
         dlow["cards"][0]["id"], "c0006")
check_eq("and says it is the strongest", dlow["cards"][0]["reason"], "strongest measured candidate")
check_eq("a higher-is-better draft starts from the highest score",
         F.select_context(CARDS, [])["cards"][0]["id"], "c0008")
plow = F.select_context(LOW, ["c0003", "c0005"])
check_eq("lower-is-better selection still leads with the direct parents",
         [c["id"] for c in plow["cards"]][:2], ["c0003", "c0005"])
plow_reasons = {c["id"]: c["reason"] for c in plow["cards"]}
check("under lower-is-better the same card is an improvement, not a non-improvement",
      plow_reasons["c0006"].startswith("shares topics"))
check("under higher-is-better it was the non-improving pick",
      reasons["c0006"].startswith("did not beat its strongest parent"))
check_eq("the direction is carried in every card",
         all(c["metric"]["higher_is_better"] is False for c in LOW.values()), True)

# --- what was dropped for space is said, not silently lost --------------------
shed = None
for mb in range(res["bytes"], 0, -8):
    r = F.select_context(CARDS, ["c0003", "c0005"], max_bytes=mb)
    if r["omitted"]:
        shed = r
        break
check("a tight budget records what it omitted", shed is not None)
if shed is not None:
    check("the rendering says cards were omitted for space", "Omitted for space" in shed["rendered"])
    check("it names the card it dropped", shed["omitted"][0]["id"] in shed["rendered"])
    check("it says where the full cards are",
          "Omitted for space (cards in candidates/" in shed["rendered"])
    check("the omission line names ids, not reasons",
          all(o["reason"] not in shed["rendered"].split("Omitted for space")[1].split("\n")[0]
              for o in shed["omitted"]))
    check("the reason it was dropped is kept in the snapshot",
          all(o["reason"] and o["why"] for o in shed["omitted"]))
    check_eq("the omission line is counted against the budget",
             shed["bytes"], len(shed["rendered"].encode("utf-8")))
    check("the whole rendering, omission line included, fits the budget",
          shed["bytes"] <= shed["limits"]["max_bytes"])
    check("an omitted card is not also listed as chosen",
          not ({o["id"] for o in shed["omitted"]} & {c["id"] for c in shed["cards"]}))
check("a comfortable budget says nothing about omissions",
      "Omitted for space" not in res["rendered"])

warn_card = make_card("c0002", ["c0001"], score=3.0,
                      summary=section(topics="t1, t2, t3, t4, t5, t6"),
                      parent_facts=[{"id": "c0001", "score": 2.0, "seed": 1}])
check_eq("six topics keep the report ok", warn_card["report"]["status"], "ok")
check_eq("only the first five topics are carried", len(warn_card["report"]["topics"]), 5)
check("the omitted sixth topic is warned about", bool(warn_card["report"]["warnings"]))
warn_txt = F.render_card(warn_card)
check("an ok report shows its warnings in the rendered card", "- Report warnings: " in warn_txt)
check("the warning names what was omitted", "beyond the first 5" in warn_txt)
check("and the worker's prose is still rendered", "- Change: " in warn_txt)
check("a clean report renders no warning line",
      "- Report warnings: " not in F.render_card(CARDS["c0000"]))

raises("a parent with no card is a tooling error",
       lambda: F.select_context(CARDS, ["c0099"]))
orphan = copy.deepcopy(CARDS)
del orphan["c0002"]
raises("a missing ancestor card is a tooling error",
       lambda: F.select_context(orphan, ["c0003"]))
cyclic = copy.deepcopy(CARDS)
cyclic["c0003"]["parents"] = ["c0009"]
raises("a parent that is not an earlier candidate is a tooling error",
       lambda: F.select_context(cyclic, ["c0003"]))
selfref = copy.deepcopy(CARDS)
selfref["c0003"]["parents"] = ["c0003"]
raises("a self-referential card is a tooling error",
       lambda: F.select_context(selfref, ["c0003"]))

anc = F.ancestors_bfs(CARDS, ["c0003", "c0005"])
check_eq("ancestors are breadth-first, ascending id within a distance",
         anc, [("c0002", 1), ("c0004", 1), ("c0000", 2), ("c0001", 2)])
check_eq("the start set is excluded from its own ancestry",
         [a for a, _ in anc if a in ("c0003", "c0005")], [])
check_eq("a parentless start has no ancestors", F.ancestors_bfs(CARDS, ["c0000"]), [])

# ---------------------------------------------------------------------------

if FAILED:
    print(f"test_findings: {len(FAILED)} of {CHECKED} checks failed", file=sys.stderr)
    for d in FAILED:
        print(f"  FAIL {d}", file=sys.stderr)
    sys.exit(1)
print(f"test_findings: {CHECKED} checks passed")
