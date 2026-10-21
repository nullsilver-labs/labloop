#!/usr/bin/env python3
"""lab graph — the claims graph across studies, built from their claim.json files.

A campaign answers one question with one final read. A study (a hub dir: PREREG.md,
READ.md, the campaigns it scaffolded) answers a question with several campaigns, and the
studies build on each other. `claim.json`, written once by the operator next to READ.md,
is the machine-readable part of a study: its lines with their verdicts, the campaigns it
ran, the studies it follows from and the defaults it changed.

    lab graph build [--root DIR] [--out FILE]   check every claim.json, write ROOT/graph.json
    lab graph show  [--root DIR]                      the same check, as text

The verdicts are not tags. A line names the keys of its numbers file (read.json) for its
verdict and its values, and the build resolves them: a claim.json whose verdict disagrees
with the read it points to fails the build. A value written as a number instead of a key
was transcribed from READ.md by hand, and the graph marks it so.

Records only. The build reads claim.json, the numbers file it names and each campaign's
population.json, never a `-private` dir, and writes ids relative to the root, so the graph
can be served from somewhere other than the machine that ran the campaigns. Two builds of
the same files are byte-identical.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

SCHEMA = "claim/1"
GRAPH_SCHEMA = "claim-graph/1"
VERDICTS = ("supported", "not_supported", "inconclusive", "untested")
LINE_ROLES = ("primary", "secondary")
CAMPAIGN_ROLES = ("arm", "snapshot", "interrupted", "aborted")
LINK_RELS = ("follows", "replicates", "builds_on")
DECISION_BASES = ("supported_line", "pooled_line", "mechanism", "judgement")
# The plain-language layer: what a reader who never saw the PREREG needs, in the order they need it.
# The hypothesis is a paraphrase of the PREREG's prediction, fixed before the run as that was.
PLAIN_STUDY = ("question", "hypothesis", "method", "answer", "meaning")
PLAIN_LINE = ("measure", "result")
PROJECT_FIELDS = ("id", "name", "question", "context")
PROJECT_EXTRA = ("loop", "glossary", "kind")  # optional: the steps of its loop, and its words, for a reader
# The fields of population.json the graph carries; everything else stays with the campaign.
POP_FIELDS = ("campaign", "status", "claim", "stop_reason")


def default_root() -> Path:
    # tools/ → the labloop repo → the dir that holds every campaign and hub
    return Path(__file__).resolve().parents[2]


def _json(p: Path):
    try:
        return json.loads(p.read_text())
    except (OSError, ValueError):
        return None


def _key(obj, dotted: str):
    for part in dotted.split("."):
        if not isinstance(obj, dict) or part not in obj:
            raise KeyError(dotted)
        obj = obj[part]
    return obj


def _private(name: str) -> bool:
    return "-private" in name


def find_claims(root: Path) -> list[Path]:
    """A hub's claim.json, or, for a hub that holds several studies, each file in its claims/."""
    found = [*root.glob("*/claim.json"), *root.glob("*/claims/*.json")]
    return sorted(p for p in found if not any(_private(part) for part in p.relative_to(root).parts))


def hub_of(path: Path) -> Path:
    return path.parent.parent if path.parent.name == "claims" else path.parent


def _values(spec: dict, numbers, where: str, errors: list[str]) -> tuple[dict, list[str]]:
    """A string is a key into the numbers file; a number is transcribed by hand."""
    out, transcribed = {}, []
    for name, v in (spec or {}).items():
        if isinstance(v, str):
            try:
                out[name] = _key(numbers, v)
            except (KeyError, TypeError):
                errors.append(f"{where}: value {name!r} names {v!r}, not in the numbers file")
        elif isinstance(v, (int, float)) and not isinstance(v, bool):
            out[name] = v
            transcribed.append(name)
        else:
            errors.append(f"{where}: value {name!r} must be a key or a number")
    return out, sorted(transcribed)


def load_study(path: Path, root: Path, errors: list[str], warnings: list[str]) -> dict | None:
    hub = hub_of(path)
    c = _json(path)
    where = str(path.relative_to(hub.parent))
    if not isinstance(c, dict):
        errors.append(f"{where}: not a JSON object")
        return None
    if c.get("schema") != SCHEMA:
        errors.append(f"{where}: schema must be {SCHEMA!r}")
    for k in ("study", "title", "question", "prereg", "read", "lines", "campaigns"):
        if k not in c:
            errors.append(f"{where}: missing {k!r}")
    if any(k not in c for k in ("study", "lines", "campaigns")):
        return None
    for k in ("prereg", "read"):
        f = (c.get(k) or {}).get("file")
        if f and not (hub / f).is_file():
            errors.append(f"{where}: {k} file {f} does not exist")
    nfile = (c.get("read") or {}).get("numbers")
    numbers = _json(hub / nfile) if nfile else None
    if nfile and numbers is None:
        errors.append(f"{where}: numbers file {nfile} is missing or not JSON")

    lines = []
    for i, ln in enumerate(c["lines"]):
        lw = f"{where} line {ln.get('id', i)}"
        if ln.get("role") not in LINE_ROLES:
            errors.append(f"{lw}: role must be one of {LINE_ROLES}")
        if ln.get("verdict") not in VERDICTS:
            errors.append(f"{lw}: verdict must be one of {VERDICTS}")
        checked = None
        if ln.get("verdict_key"):
            try:
                # a read's boolean (supported or not), or a campaign's own claim word
                supported = _key(numbers, ln["verdict_key"])
                checked = (supported == ln.get("verdict")) if isinstance(supported, str) \
                    else (supported is True) == (ln.get("verdict") == "supported")
                if not checked:
                    errors.append(f"{lw}: verdict {ln.get('verdict')!r} but {nfile} "
                                  f"{ln['verdict_key']} is {supported!r}")
            except (KeyError, TypeError):
                errors.append(f"{lw}: verdict_key {ln['verdict_key']!r} not in the numbers file")
        values, transcribed = _values(ln.get("values"), numbers, lw, errors)
        plain = ln.get("plain") or {}
        if not all(plain.get(k) for k in PLAIN_LINE):
            warnings.append(f"{lw}: no plain {'/'.join(PLAIN_LINE)}")
        lines.append({
            "id": f"{c['study']}/{ln.get('id', i)}",
            "plain": {k: plain.get(k, "") for k in PLAIN_LINE},
            "role": ln.get("role"),
            "statement": ln.get("statement", ""),
            "predicted": ln.get("predicted", ""),
            "rule": ln.get("rule", ""),
            "verdict": ln.get("verdict"),
            "verdict_checked": bool(checked),
            "values": values,
            "transcribed": transcribed,
        })

    observations = []
    for j, ob in enumerate(c.get("observations", [])):
        values, transcribed = _values(ob.get("values"), numbers, f"{where} observation {j}", errors)
        observations.append({"text": ob.get("text", ""), "values": values,
                             "transcribed": transcribed})

    campaigns = []
    for cp in c["campaigns"]:
        d = cp.get("dir", "")
        cw = f"{where} campaign {d}"
        if not d or "/" in d or d.startswith("."):
            errors.append(f"{cw}: dir must be a sibling dir name")
            continue
        if _private(d):
            errors.append(f"{cw}: a -private dir is never part of the graph")
            continue
        if cp.get("role") not in CAMPAIGN_ROLES:
            errors.append(f"{cw}: role must be one of {CAMPAIGN_ROLES}")
        entry = {"dir": d, "role": cp.get("role"), "arm": cp.get("arm"), "present": False}
        pop = _json(root / d / "population.json")
        if pop is None:
            if cp.get("role") != "aborted":
                warnings.append(f"{cw}: no population.json")
        else:
            entry["present"] = True
            entry.update({k: pop.get(k) for k in POP_FIELDS})
            entry["candidates"] = len(pop.get("candidates") or {})
            final = pop.get("final") or {}
            entry["final_score"] = final.get("score")
            src = (pop.get("seeded") or {}).get("from")
            entry["seeded_from"] = Path(src).name if src else None
            # its solutions, for a reader who zooms in: how each was made, from which, and its
            # search score (never a final-split number: only the campaign's one final read is)
            entry["solutions"] = [
                {"id": k, "op": v.get("operator"), "parents": v.get("parents") or [],
                 "fitness": v.get("fitness"), "status": v.get("status")}
                for k, v in sorted((pop.get("candidates") or {}).items())]
        campaigns.append(entry)

    links = []
    for lk in c.get("links", []):
        if lk.get("rel") not in LINK_RELS:
            errors.append(f"{where}: link rel must be one of {LINK_RELS}")
        links.append({"rel": lk.get("rel"), "study": lk.get("study"), "note": lk.get("note", "")})

    decisions = []
    for dc in c.get("decisions", []):
        if dc.get("basis") not in DECISION_BASES:
            errors.append(f"{where}: decision basis must be one of {DECISION_BASES}")
        decisions.append({k: dc.get(k) for k in ("repo", "commit", "date", "what", "basis")})

    plain = c.get("plain") or {}
    missing = [k for k in PLAIN_STUDY if not plain.get(k)]
    if missing:
        warnings.append(f"{where}: no plain {', '.join(missing)}")
    project = c.get("project") or {}
    if project and not all(project.get(k) for k in PROJECT_FIELDS):
        errors.append(f"{where}: project needs {', '.join(PROJECT_FIELDS)}")

    return {
        "id": c["study"],
        "hub": hub.name,
        "project": {k: project.get(k) for k in (*PROJECT_FIELDS, *PROJECT_EXTRA) if k in PROJECT_FIELDS or k in project} if project else None,
        "plain": {**{k: plain.get(k, "") for k in PLAIN_STUDY}, "arms": plain.get("arms") or {}},
        "title": c.get("title", ""),
        "question": c.get("question", ""),
        "scope": c.get("scope", ""),
        "plan": c.get("plan", ""),
        "prereg": c.get("prereg"),
        "read": c.get("read"),
        "deviations": c.get("deviations", []),
        "lines": lines,
        "observations": observations,
        "campaigns": campaigns,
        "links": links,
        "decisions": decisions,
    }


def build(root: Path) -> tuple[dict, list[str], list[str]]:
    errors: list[str] = []
    warnings: list[str] = []
    studies = [s for s in (load_study(p, root, errors, warnings) for p in find_claims(root)) if s]
    ids = [s["id"] for s in studies]
    for dup in sorted({i for i in ids if ids.count(i) > 1}):
        errors.append(f"study id {dup!r} is claimed by more than one hub")

    nodes: dict[str, dict] = {}
    edges: list[dict] = []
    for s in studies:
        pj = s.pop("project")
        if pj:
            pid = f"project:{pj['id']}"
            if pid in nodes and {k: nodes[pid].get(k) for k in pj if k != 'kind'} != {k: v for k, v in pj.items() if k != 'kind'}:
                errors.append(f"study {s['id']}: project {pj['id']!r} is described differently "
                              f"from another study's")
            # a project's own `kind` (research, artifacts, writing) is the ground its figures stand on
            nodes.setdefault(pid, {**{k: v for k, v in pj.items() if k != "kind"}, "ground": pj.get("kind"), "kind": "project"})
            edges.append({"from": f"study:{s['id']}", "to": pid, "rel": "part_of"})
        nodes[f"study:{s['id']}"] = {
            "kind": "study", **{k: v for k, v in s.items() if k not in ("lines", "campaigns")}}
        for ln in s["lines"]:
            nodes[f"line:{ln['id']}"] = {"kind": "line", "study": s["id"], **ln}
            edges.append({"from": f"study:{s['id']}", "to": f"line:{ln['id']}", "rel": "tests"})
        for cp in s["campaigns"]:
            nid = f"campaign:{cp['dir']}"
            node = nodes.setdefault(nid, {"kind": "campaign", "studies": [],
                                          **{k: v for k, v in cp.items() if k not in ("role", "arm")}})
            node["studies"] = sorted(set(node["studies"]) | {s["id"]})
            edges.append({"from": f"study:{s['id']}", "to": nid, "rel": "ran",
                          "role": cp["role"], "arm": cp["arm"]})
        for lk in s["links"]:
            tid = f"study:{lk['study']}"
            edges.append({"from": f"study:{s['id']}", "to": tid, "rel": lk["rel"], "note": lk["note"]})
        for dc in s["decisions"]:
            did = f"decision:{dc['repo']}@{dc['commit']}"
            nodes[did] = {"kind": "decision", **dc}
            edges.append({"from": did, "to": f"study:{s['id']}", "rel": "based_on"})

    # A seeded campaign points at its source, when the source is in the graph too.
    for nid, n in list(nodes.items()):
        src = n.get("seeded_from") if n["kind"] == "campaign" else None
        if src and f"campaign:{src}" in nodes:
            edges.append({"from": nid, "to": f"campaign:{src}", "rel": "seeded_from"})

    # A link to a study with no claim.json yet stays in the graph as a stub, not an error:
    # the reference is real, its claim.json just has not been written.
    for e in edges:
        if e["to"].startswith("study:") and e["to"] not in nodes:
            nodes[e["to"]] = {"kind": "study", "id": e["to"][6:], "stub": True}
            warnings.append(f"{e['from']} {e['rel']} {e['to']}, which has no claim.json")

    graph = {
        "schema": GRAPH_SCHEMA,
        "nodes": [{**{f: v for f, v in nodes[k].items() if f != "id"}, "id": k}
                  for k in sorted(nodes)],
        "edges": sorted(edges, key=lambda e: (e["from"], e["rel"], e["to"])),
    }
    return graph, errors, warnings


def render(graph: dict) -> list[str]:
    nodes = {n["id"]: n for n in graph["nodes"]}
    out_edges: dict[str, list[dict]] = {}
    for e in graph["edges"]:
        out_edges.setdefault(e["from"], []).append(e)
    lines = []
    for n in graph["nodes"]:
        if n["kind"] != "study" or n.get("stub"):
            continue
        lines.append(f"{n['id']}  {n['title']}  ({n['hub']})")
        for e in out_edges.get(n["id"], []):
            if e["rel"] == "tests":
                ln = nodes[e["to"]]
                vals = ", ".join(f"{k} {v:.3g}" if isinstance(v, float) else f"{k} {v}"
                                 for k, v in ln["values"].items())
                mark = "checked" if ln["verdict_checked"] else (
                    "transcribed" if ln["transcribed"] else "unchecked")
                lines.append(f"  {ln['role']:9} {ln['verdict']:13} [{mark}] "
                             f"{ln['id'].split('/', 1)[1]}: {vals}")
        ran = [e for e in out_edges.get(n["id"], []) if e["rel"] == "ran"]
        roles: dict[str, int] = {}
        for e in ran:
            roles[e["role"]] = roles.get(e["role"], 0) + 1
        claims: dict[str, int] = {}
        for e in ran:
            if e["role"] == "arm":
                cl = nodes[e["to"]].get("claim") or "absent"
                claims[cl] = claims.get(cl, 0) + 1
        lines.append("  campaigns " + ", ".join(f"{v} {k}" for k, v in sorted(roles.items()))
                     + ("; arm claims " + ", ".join(f"{v} {k}" for k, v in sorted(claims.items()))
                        if claims else ""))
        for e in out_edges.get(n["id"], []):
            if e["rel"] in LINK_RELS:
                stub = " (no claim.json)" if nodes[e["to"]].get("stub") else ""
                lines.append(f"  {e['rel']} {e['to'][6:]}{stub}")
        for nid, nd in nodes.items():
            if nd["kind"] == "decision" and any(
                    e["to"] == n["id"] for e in out_edges.get(nid, [])):
                lines.append(f"  decided {nd['repo']}@{nd['commit']} ({nd['basis']}): {nd['what']}")
    return lines


def cmd_graph(args) -> None:
    root = Path(args.root).resolve() if args.root else default_root()
    graph, errors, warnings = build(root)
    if args.graph_cmd == "show":
        print("\n".join(render(graph)))
    for w in warnings:
        print(f"lab graph: warning: {w}", file=sys.stderr)
    for e in errors:
        print(f"lab graph: error: {e}", file=sys.stderr)
    if errors:
        sys.exit(1)
    if args.graph_cmd == "build":
        text = json.dumps(graph, indent=1, sort_keys=True, ensure_ascii=False) + "\n"
        # Beside the hubs by default, never inside the (public) labloop repo by accident.
        out = Path(args.out) if args.out else root / "graph.json"
        if args.out == "-":
            sys.stdout.write(text)
        else:
            out.write_text(text)
            kinds: dict[str, int] = {}
            for n in graph["nodes"]:
                kinds[n["kind"]] = kinds.get(n["kind"], 0) + 1
            print(f"{out}: " + ", ".join(f"{v} {k}" for k, v in sorted(kinds.items()))
                  + f", {len(graph['edges'])} edges")


def register(sub) -> None:
    sp = sub.add_parser("graph", help="the claims graph across studies, from their claim.json")
    gsub = sp.add_subparsers(dest="graph_cmd", required=True)
    for name, hlp in (("build", "check every claim.json and write the graph"),
                      ("show", "check every claim.json and print the graph as text")):
        g = gsub.add_parser(name, help=hlp)
        g.add_argument("--root", help="the dir holding the hubs and campaigns "
                                      "(default: the labloop repo's parent)")
        if name == "build":
            g.add_argument("--out", help="output file, or - for stdout (default: ROOT/graph.json)")
        g.set_defaults(func=cmd_graph)


if __name__ == "__main__":  # pragma: no cover
    p = argparse.ArgumentParser(prog="lab graph")
    register(p.add_subparsers(dest="cmd", required=True))
    a = p.parse_args(["graph", *sys.argv[1:]])
    a.func(a)
