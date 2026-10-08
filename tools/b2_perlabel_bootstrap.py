#!/usr/bin/env python
"""B2 收尾：按 score 重采样的分标签配对 bootstrap（读 B2_perf.csv 的逐 run 计数）。

不重跑 B2 点估计；只对已有逐 run 计数做重采样。基线预测逐字复用
tools/b2_harmony_segments.py 的 baseline_predictions；匹配计数逐字保持 f1_of 的 wrong 口径。
"""
from __future__ import annotations

import argparse, csv, json, random, sys
from pathlib import Path
import numpy as np
from scipy.optimize import linear_sum_assignment

sys.path.insert(0, str(Path(__file__).resolve().parent))
from b2_harmony_segments import baseline_predictions  # noqa: E402
from inversion_consistency import GRID, parse_alignment, parse_score, snap  # noqa: E402


def per_label_counts(pred, truth, tol):
    pl, tl = sorted(pred), sorted(truth)
    out = {lab: {"n_pred": 0, "n_truth": 0, "tp": 0, "fp": 0, "fn": 0, "wrong": 0} for lab in ("DOWN", "UP")}
    matched_pred, matched_truth = set(), set()
    for lab in ("DOWN", "UP"):
        pi = [i for i, x in enumerate(pl) if x[1] == lab]
        ti = [j for j, x in enumerate(tl) if x[1] == lab]
        out[lab]["n_pred"] = len(pi)
        out[lab]["n_truth"] = len(ti)
        if pi and ti:
            cost = np.full((len(pi), len(ti)), 1e6)
            for a, i in enumerate(pi):
                for b, j in enumerate(ti):
                    d = abs(pl[i][0] - tl[j][0])
                    if d <= tol:
                        cost[a, b] = d
            ra, cb = linear_sum_assignment(cost)
            for a, b in zip(ra, cb):
                if cost[a, b] <= tol:
                    out[lab]["tp"] += 1
                    matched_pred.add(pi[a]); matched_truth.add(ti[b])
        out[lab]["fp"] = len(pi) - sum(1 for i in pi if i in matched_pred)
        out[lab]["fn"] = len(ti) - sum(1 for j in ti if j in matched_truth)
    for lab, other in (("DOWN", "UP"), ("UP", "DOWN")):
        pi = [i for i, x in enumerate(pl) if x[1] == lab]
        ti_other = [j for j, x in enumerate(tl) if x[1] == other]
        for i in pi:
            if i in matched_pred:
                continue
            for j in ti_other:
                if j in matched_truth:
                    continue
                if abs(pl[i][0] - tl[j][0]) <= tol:
                    out[lab]["wrong"] += 1
                    break
    return out


def counts_for(x, side, method, lab):
    return x["b2"][lab] if side == "b2" else x["base"][method][lab]


def f1_from_label_rows(rows, side, method, lab):
    tp = sum(counts_for(x, side, method, lab)["tp"] for x in rows)
    fp = sum(counts_for(x, side, method, lab)["fp"] for x in rows)
    fn = sum(counts_for(x, side, method, lab)["fn"] for x in rows)
    return 2 * tp / (2 * tp + fp + fn) if (2 * tp + fp + fn) else 0.0


def f1_micro(rows, side, method):
    tp = sum(counts_for(x, side, method, lab)["tp"] for x in rows for lab in ("DOWN", "UP"))
    fp = sum(counts_for(x, side, method, lab)["fp"] for x in rows for lab in ("DOWN", "UP"))
    fn = sum(counts_for(x, side, method, lab)["fn"] for x in rows for lab in ("DOWN", "UP"))
    return 2 * tp / (2 * tp + fp + fn) if (2 * tp + fp + fn) else 0.0


def bootstrap(rows, side_a, method_a, side_b, method_b, lab, boot, seed):
    scores = sorted({x["score"] for x in rows})
    by = {s: [x for x in rows if x["score"] == s] for s in scores}
    rng = random.Random(seed)
    diffs = []
    for _ in range(boot):
        sample = [scores[rng.randrange(len(scores))] for _ in scores]
        chosen = [x for s in sample for x in by[s]]
        if lab == "micro":
            a = f1_micro(chosen, side_a, method_a); b = f1_micro(chosen, side_b, method_b)
        else:
            a = f1_from_label_rows(chosen, side_a, method_a, lab); b = f1_from_label_rows(chosen, side_b, method_b, lab)
        diffs.append(a - b)
    return {
        "label": lab,
        "n_scores": len(scores),
        "n_runs": len(rows),
        "mean_diff": float(np.mean(diffs)),
        "ci95_low": float(np.percentile(diffs, 2.5)),
        "ci95_high": float(np.percentile(diffs, 97.5)),
        "p_gt_0": float(np.mean([d > 0 for d in diffs])),
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dataset", type=Path, default=Path("data/asap-dataset"))
    ap.add_argument("--split", type=Path, default=Path("evidence/R1/G1-split/split_v1.json"))
    ap.add_argument("--b2-perf", type=Path, default=Path("results/E1/B2_perf.csv"))
    ap.add_argument("--out", type=Path, default=Path("results/E1/B2_bootstrap_perlabel.json"))
    ap.add_argument("--boot", type=int, default=10000)
    ap.add_argument("--seed", type=int, default=20260101)
    args = ap.parse_args()
    split = json.loads(args.split.read_text(encoding="utf-8"))
    perf_by_key = {(p["xml_score"], p["midi_performance"]): p for p in split["per_performance"]}
    notes_cache = {}
    rows = []
    with args.b2_perf.open(encoding="utf-8", newline="") as fh:
        for r in csv.DictReader(fh):
            if r["K"] != "3" or r["tol"] != "1.0":
                continue
            key = (r["score"], r["perf"])
            p = perf_by_key[key]
            xml = Path(r["score"]); perf = Path(r["perf"])
            notes, pedals = notes_cache.setdefault(str(xml), parse_score(args.dataset / xml))
            truth = {(snap(o), "DOWN" if k == "start" else "UP") for (_, o, k) in pedals}
            al = args.dataset / p["alignment_path"] if p["alignment_path"] else None
            if not (al and al.is_file() and (args.dataset / perf).is_file()) or not truth:
                continue
            seq = sorted((o, notes[b][1]) for b, _, o in parse_alignment(al) if b in notes)
            if len(seq) < 2:
                continue
            span = max(t for t, _ in truth)
            base = baseline_predictions({"perf_path": args.dataset / perf}, seq, span)
            base_counts = {m: per_label_counts(pred, truth, 1.0) for m, pred in base.items()}
            b2_counts = {lab: {
                "n_pred": int(r[f"{lab}_n_pred"]), "n_truth": int(r[f"{lab}_n_truth"]),
                "tp": int(r[f"{lab}_tp"]), "fp": int(r[f"{lab}_fp"]),
                "fn": int(r[f"{lab}_fn"]), "wrong": int(r[f"{lab}_wrong"]),
            } for lab in ("DOWN", "UP")}
            rows.append({"score": r["score"], "fold": r["fold"], "b2": b2_counts, "base": base_counts})
    result = {"tol": 1.0, "boot": args.boot, "seed": args.seed, "domains": {}}
    for domain, sel in (("test", [x for x in rows if x["fold"] == "test"]), ("full", rows)):
        result["domains"][domain] = {
            "n_scores": len({x["score"] for x in sel}), "n_runs": len(sel),
            "DOWN_B2_minus_beat_periodic_4": bootstrap(sel, "b2", "DOWN", "base", "beat_periodic_4", "DOWN", args.boot, args.seed),
            "UP_B2_minus_inversion": bootstrap(sel, "b2", "UP", "base", "inversion", "UP", args.boot, args.seed),
            "micro_B2_minus_inversion": bootstrap(sel, "b2", None, "base", "inversion", "micro", args.boot, args.seed),
            "micro_B2_minus_beat_periodic_4": bootstrap(sel, "b2", None, "base", "beat_periodic_4", "micro", args.boot, args.seed),
        }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
