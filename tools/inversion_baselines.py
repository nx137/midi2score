#!/usr/bin/env python
"""交付 5 ④：反演 vs 基线（always_down / beat_periodic_N）+ bootstrap（逐曲配对，10,000）+ macro。

复用 inversion_consistency 的解析与 ①b 映射；匹配 = 标签内最优指派（与 ③ 同一实现）。
"""

from __future__ import annotations

import argparse
import json
import random
from collections import defaultdict
from pathlib import Path

import numpy as np
from scipy.optimize import linear_sum_assignment

import sys
sys.path.insert(0, str(Path(__file__).resolve().parent))
from inversion_consistency import (GRID, ON_THRESHOLD, cc64_transitions, parse_alignment,
                                   parse_score, snap, to_anchor)  # noqa: E402


def f1_of(pred: set, truth: set, tol: float) -> dict:
    pred_l, truth_l = sorted(pred), sorted(truth)
    tp = 0
    mp, mt = set(), set()
    for lab in ("DOWN", "UP"):
        pi = [i for i, x in enumerate(pred_l) if x[1] == lab]
        ti = [j for j, x in enumerate(truth_l) if x[1] == lab]
        if not pi or not ti:
            continue
        cost = np.full((len(pi), len(ti)), 1e6)
        for a, i in enumerate(pi):
            for b, j in enumerate(ti):
                d = abs(pred_l[i][0] - truth_l[j][0])
                if d <= tol:
                    cost[a, b] = d
        ra, cb = linear_sum_assignment(cost)
        for a, b in zip(ra, cb):
            if cost[a, b] <= tol:
                tp += 1
                mp.add(pi[a]); mt.add(ti[b])
    fp = len(pred_l) - len(mp)
    fn = len(truth_l) - len(mt)
    p = tp / (tp + fp) if (tp + fp) else 0.0
    r = tp / (tp + fn) if (tp + fn) else 0.0
    return {"tp": tp, "fp": fp, "fn": fn, "P": p, "R": r, "F1": 2 * p * r / (p + r) if (p + r) else 0.0}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dataset", type=Path, default=Path("data/asap-dataset"))
    ap.add_argument("--split", type=Path, default=Path("evidence/R1/G1-split/split_v1.json"))
    ap.add_argument("--out-dir", type=Path, default=Path("evidence/R1/G1-inversion"))
    ap.add_argument("--tol", type=float, default=1.0, help="主口径 ±1 拍")
    ap.add_argument("--boot", type=int, default=10000)
    ap.add_argument("--seed", type=int, default=20260101)
    args = ap.parse_args()

    ds = args.dataset
    split = json.loads(args.split.read_text(encoding="utf-8"))
    main_scores = set(split["main_scores"])
    repeat_scores = {s for s in main_scores
                     if (ds / s).exists() and __import__("lxml.etree", fromlist=["etree"])
                     .parse(str(ds / s)).getroot().xpath(".//*[local-name()='repeat']")}
    rows = [p for p in split["per_performance"]
            if p["xml_score"] in main_scores and p["xml_score"] not in repeat_scores]

    cache_scores: dict[str, tuple] = {}
    per_run = []
    for p in rows:
        xml = p["xml_score"]
        if xml not in cache_scores:
            cache_scores[xml] = parse_score(ds / xml)
        notes, pedals = cache_scores[xml]
        align = ds / p["alignment_path"] if p["alignment_path"] else None
        midi = ds / p["midi_performance"]
        if not (align and align.is_file() and midi.is_file()):
            continue
        al = parse_alignment(align)
        seq = sorted((onset, notes[base][1]) for base, rep, onset in al if base in notes)
        if len(seq) < 2:
            continue
        truth = {(snap(o), "DOWN" if k == "start" else "UP") for (m, o, k) in pedals}
        pred = set()
        for t, kind in cc64_transitions(midi):
            got = to_anchor(t, seq, [])
            if got is None:
                continue
            pred.add((snap(got[0]), "DOWN" if kind == "start" else "UP"))
        span = max([x[0] for x in truth], default=0.0)
        baselines = {}
        baselines["always_down"] = {(snap(x), "DOWN") for x in np.arange(0, span + GRID, GRID)}
        for n in (1, 2, 4):
            baselines[f"beat_periodic_{n}"] = {(snap(x), "DOWN") for x in np.arange(0, span + GRID, float(n))}
        rec = {"score": xml, "performance": p["midi_performance"],
               "n_truth": len(truth), "n_pred": len(pred),
               "inversion": f1_of(pred, truth, args.tol)}
        for name, b in baselines.items():
            rec[name] = f1_of(b, truth, args.tol)
        per_run.append(rec)

    scores = sorted({r["score"] for r in per_run})
    by_score = defaultdict(list)
    for r in per_run:
        by_score[r["score"]].append(r)

    def agg(sel) -> dict:
        tp = sum(r["inversion"]["tp"] for r in sel); fp = sum(r["inversion"]["fp"] for r in sel)
        fn = sum(r["inversion"]["fn"] for r in sel)
        inv = 2 * tp / (2 * tp + fp + fn) if (2 * tp + fp + fn) else 0.0
        out = {"n_runs": len(sel), "inversion_F1": inv,
               "macro_inversion_F1": sum(r["inversion"]["F1"] for r in sel) / len(sel) if sel else 0.0}
        for name in ("always_down", "beat_periodic_1", "beat_periodic_2", "beat_periodic_4"):
            tpb = sum(r[name]["tp"] for r in sel); fpb = sum(r[name]["fp"] for r in sel)
            fnb = sum(r[name]["fn"] for r in sel)
            out[name + "_F1"] = 2 * tpb / (2 * tpb + fpb + fnb) if (2 * tpb + fpb + fnb) else 0.0
        return out

    overall = agg(per_run)
    rng = random.Random(args.seed)
    diffs = {name: [] for name in ("always_down", "beat_periodic_1", "beat_periodic_2", "beat_periodic_4")}
    for _ in range(args.boot):
        sel_scores = [scores[rng.randrange(len(scores))] for _ in range(len(scores))]
        sel = [r for s in sel_scores for r in by_score[s]]
        a = agg(sel)
        for name in diffs:
            diffs[name].append(a["inversion_F1"] - a[name + "_F1"])
    boot = {}
    for name, d in diffs.items():
        arr = np.array(d)
        boot[name] = {"mean": round(float(arr.mean()), 4),
                      "ci95_low": round(float(np.percentile(arr, 2.5)), 4),
                      "ci95_high": round(float(np.percentile(arr, 97.5)), 4),
                      "p_gt_0": round(float((arr > 0).mean()), 4)}
    summary = {"tol_beats": args.tol, "n_scores": len(scores), "n_runs": len(per_run),
               "overall": overall, "bootstrap": boot,
               "pass_criterion": "inversion 显著优于基线 = bootstrap CI 下界 > 0"}
    args.out_dir.mkdir(parents=True, exist_ok=True)
    (args.out_dir / "inversion_vs_baselines.json").write_text(
        json.dumps({"summary": summary, "per_run": per_run}, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps(summary, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())