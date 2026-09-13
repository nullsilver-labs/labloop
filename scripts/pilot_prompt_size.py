#!/usr/bin/env python3
"""pilot_prompt_size.py — the prompt-size pilot of docs/finding-cards-plan.md §7.

Read-only, no LLM. For every dispatched job of a finished (or paused) campaign it
measures the job prompt the worker received — rendered from the job.json snapshot the
way `lab job card` renders it — and, for a legacy campaign, the prompt the same job
would have received under `[memory] mode = "findings-v1"`: cards are built from the
recorded artifacts of the candidates that had settled when the job was dispatched, the
context is selected by the same deterministic policy, and the parents' summaries and
the lineage are replaced by it. Two findings figures are reported:

  findings (facts-only)   the cards as they would be built from this campaign's
                          summaries — legacy workers were not asked for a
                          `## Finding` section, so every card is facts-only: a lower
                          bound on the findings prompt
  findings (filled)       every card's five prose fields at their byte limits and five
                          shared topics, so the selector fills all max_cards and the
                          byte cap does the trimming: the upper bound

On a findings-v1 campaign the rebuilt context is also checked byte for byte against
the snapshot each job.json stores, so the counterfactual builder is validated where
the real thing exists.

Tokens are counted with a NAMED tokenizer (tiktoken, cl100k_base by default). It is a
proxy: Claude's tokenizer is not public. Bytes are reported next to every token count.

    scripts/pilot_prompt_size.py <project-dir> [--tokenizer cl100k_base] [--json OUT]

Never writes into the project. Needs LAB_PRIVATE only so campaign.toml expands; no
label is read.
"""
from __future__ import annotations

import argparse
import contextlib
import copy
import importlib.machinery
import importlib.util
import io
import json
import os
import statistics
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
TOOLS = HERE.parent / "tools"

FILL_WORDS = ("changed the augmentation policy to random-resized crops with color jitter and "
              "raised the weight decay; the validation curve flattened later and the best "
              "epoch moved by three; ")
FILL_TOPICS = ["augmentation", "regularization", "schedule", "architecture", "optimizer"]


def load_modules(project: Path):
    os.environ["LAB_ROOT"] = str(project)
    os.environ.setdefault("LAB_PRIVATE", str(Path.home() / ".local/share/labloop-private"))
    loader = importlib.machinery.SourceFileLoader("lab", str(TOOLS / "lab"))
    spec = importlib.util.spec_from_loader("lab", loader)
    lab = importlib.util.module_from_spec(spec)
    sys.modules["lab"] = lab
    loader.exec_module(lab)
    sys.path.insert(0, str(TOOLS))
    import lab_campaign as C   # noqa: E402
    import lab_findings as F   # noqa: E402
    C.L = lab
    return lab, C, F


def tokenizer(name: str):
    try:
        import tiktoken
    except ImportError:
        return "none — tiktoken is not installed; token columns are bytes/4 (a rough proxy)", \
            (lambda s: round(len(s.encode("utf-8")) / 4))
    enc = tiktoken.get_encoding(name)
    return f"tiktoken {tiktoken.__version__}, encoding {name} (a proxy: Claude's tokenizer is not public)", \
        (lambda s: len(enc.encode(s, disallowed_special=())))


def fill_text(limit: int) -> str:
    s = ""
    while len((s + FILL_WORDS).encode("utf-8")) <= limit:
        s += FILL_WORDS
    return s.rstrip("; ")


def filled_card(F, card: dict) -> dict:
    c = copy.deepcopy(card)
    r = c["report"]
    r["status"] = "ok"
    for f in F.PROSE_FIELDS:
        r[f] = fill_text(F.FIELD_BYTES[f])
    r["topics"] = list(FILL_TOPICS[:F.TOPICS_MAX])
    r["truncated"], r["warnings"] = [], []
    return c


def measure(C, F, count, card: dict, task: str) -> dict:
    """Token and byte figures for one job prompt, split into additive parts."""
    full = C.render_job_card(card, task)
    no_pop = copy.deepcopy(card)
    no_pop["population"] = []
    bare = copy.deepcopy(card)
    for p in bare["parents"]:
        p["summary"] = None
    bare["lineage"], bare["findings"] = [], None
    bare["contract"]["summary_format"] = None
    t_full, t_nopop, t_bare = count(full), count(C.render_job_card(no_pop, task)), count(C.render_job_card(bare, task))
    return {"tokens": t_full, "bytes": len(full.encode("utf-8")),
            "population_table": t_full - t_nopop, "memory": t_full - t_bare,
            "fixed": t_nopop - (t_full - t_bare)}


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("project")
    ap.add_argument("--tokenizer", default="cl100k_base")
    ap.add_argument("--json", help="write the per-job figures here")
    args = ap.parse_args()
    project = Path(args.project).resolve()
    lab, C, F = load_modules(project)
    tok_name, count = tokenizer(args.tokenizer)
    cfg = C.load_campaign(project / "campaign.toml")
    pop = C.load_pop()
    if pop is None:
        sys.exit(f"{project}: no population")
    policy = C.memory_policy(pop)
    limits = {"max_cards": policy.get("max_cards", F.MAX_CARDS), "max_bytes": policy.get("max_bytes", F.MAX_BYTES)}
    task = cfg["campaign"]["task"].read_text()

    # cards of every settled candidate, from the recorded artifacts (never written)
    cards: dict[str, dict] = {}
    for cid, c in pop["candidates"].items():
        if c.get("exec") in F.EXEC_STATUSES:
            cards[cid] = C.build_candidate_card(cfg, pop, cid)
    cards_filled = {k: filled_card(F, v) for k, v in cards.items()}
    ended = {k: pop["candidates"][k].get("ended") or "" for k in cards}

    rows = []
    mismatches = []
    for cid, c in pop["candidates"].items():
        if c["operator"] == "baseline":
            continue
        cdir = project / c["path"]
        card = json.loads((cdir / "job.json").read_text())
        start = (json.loads((cdir / "config.json").read_text()) or {}).get("start_time") or ""
        avail = {k: v for k, v in cards.items() if ended[k] and ended[k] <= start and k != cid}
        for p in card["parents"]:
            if p["id"] not in avail and p["id"] in cards:
                avail[p["id"]] = cards[p["id"]]   # settled in the same tick it was dispatched from
        parents = [p["id"] for p in card["parents"]]
        row = {"id": cid, "operator": c["operator"], "parents": parents,
               "population": len(card["population"]), "cards_available": len(avail),
               "memory": card.get("memory", "legacy"), "as_dispatched": measure(C, F, count, card, task)}
        try:
            ctx = F.select_context(avail, parents, **limits)
        except F.ToolingError as e:
            row["error"] = str(e)
            rows.append(row)
            continue
        if card.get("findings") is not None:
            if card["findings"]["rendered"] != ctx["rendered"]:
                mismatches.append(cid)
        fc = copy.deepcopy(card)
        for p in fc["parents"]:
            p["summary"] = None
            p.setdefault("summary_file", p["path"] + "/summary.md")
        fc["lineage"] = []
        fc["contract"]["summary_format"] = F.SUMMARY_FORMAT
        fc["findings"] = ctx
        row["findings_facts"] = measure(C, F, count, fc, task)
        row["findings_facts"]["cards"] = len(ctx["cards"])
        avail_f = {k: cards_filled[k] for k in avail}
        ctx_f = F.select_context(avail_f, parents, **limits)
        fc["findings"] = ctx_f
        row["findings_filled"] = measure(C, F, count, fc, task)
        row["findings_filled"]["cards"] = len(ctx_f["cards"])
        row["findings_filled"]["omitted"] = len(ctx_f["omitted"])
        rows.append(row)

    def col(rows_, key, sub="tokens"):
        return [r[key][sub] for r in rows_ if key in r]

    ok = [r for r in rows if "error" not in r]
    print(f"# Prompt-size pilot — campaign {pop['campaign']} ({project.name})")
    print()
    print(f"- jobs measured: {len(rows)} (baseline excluded); memory policy as run: {policy['policy']}")
    print(f"- tokenizer: {tok_name}")
    print(f"- findings limits: max_cards {limits['max_cards']}, max_bytes {limits['max_bytes']}")
    if any("findings" in r["memory"] for r in rows):
        print(f"- rebuilt findings context equals the stored snapshot: "
              f"{'yes, for every job' if not mismatches else 'NO — differs for ' + ', '.join(mismatches)}")
    print()
    print("| job | op | pop | cards avail | as dispatched tok (bytes) | pop table | memory | "
          "findings facts-only tok (cards) | findings filled tok (cards/omitted) |")
    print("|---|---|---|---|---|---|---|---|---|")
    for r in rows:
        a = r["as_dispatched"]
        ff = r.get("findings_facts"); fl = r.get("findings_filled")
        print(f"| {r['id']} | {r['operator']} | {r['population']} | {r['cards_available']} | "
              f"{a['tokens']} ({a['bytes']}) | {a['population_table']} | {a['memory']} | "
              + (f"{ff['tokens']} ({ff['cards']})" if ff else f"— {r.get('error', '')}") + " | "
              + (f"{fl['tokens']} ({fl['cards']}/{fl['omitted']})" if fl else "—") + " |")
    print()

    def stats(xs):
        return (f"mean {statistics.mean(xs):.0f}, median {statistics.median(xs):.0f}, "
                f"max {max(xs)}, total {sum(xs)}") if xs else "—"
    print("## Totals (tokens)")
    print()
    print("| prompt | per job | memory part per job | population table per job |")
    print("|---|---|---|---|")
    print(f"| as dispatched ({policy['policy']}) | {stats(col(rows, 'as_dispatched'))} | "
          f"{stats(col(rows, 'as_dispatched', 'memory'))} | {stats(col(rows, 'as_dispatched', 'population_table'))} |")
    print(f"| findings, facts-only cards | {stats(col(ok, 'findings_facts'))} | "
          f"{stats(col(ok, 'findings_facts', 'memory'))} | {stats(col(ok, 'findings_facts', 'population_table'))} |")
    print(f"| findings, cards filled to their limits | {stats(col(ok, 'findings_filled'))} | "
          f"{stats(col(ok, 'findings_filled', 'memory'))} | {stats(col(ok, 'findings_filled', 'population_table'))} |")
    if ok:
        base = sum(col(ok, "as_dispatched"))
        print()
        print(f"Overhead of the findings prompt over the prompt as dispatched, summed over all jobs: "
              f"facts-only {sum(col(ok, 'findings_facts')) / base - 1:+.1%}, "
              f"filled {sum(col(ok, 'findings_filled')) / base - 1:+.1%}.")
    if args.json:
        Path(args.json).write_text(json.dumps({"campaign": pop["campaign"], "project": str(project),
                                               "tokenizer": tok_name, "limits": limits,
                                               "policy": policy["policy"], "mismatches": mismatches,
                                               "rows": rows}, indent=1))


if __name__ == "__main__":
    main()
