#!/usr/bin/env python
"""B1 = 阈值 + 抖动抑制（§5.2）；按 D-0061(a)：去抖插在 cc64_transitions 与 to_anchor 之间，作用于事件段长。

只新增两个函数：dejitter / labels，其余全部复用 inversion_consistency 的映射与匹配。
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
from collections import defaultdict
from pathlib import Path

import numpy as np
from scipy.optimize import linear_sum_assignment

sys.path.insert(0, str(Path(__file__).resolve().parent))
from inversion_consistency import GRID, cc64_transitions, parse_alignment, parse_score, snap, to_anchor  # noqa: E402

D_MIN_GRID = [0, 1, 2, 4, 8]   # 0 / 0.25 / 0.5 / 1.0 / 2.0 拍
TOLS = [0.0, 1.0, 2.0]


def dejitter(events: list[tuple[float, str]], beats: list[float], dmin_beats: float) -> list[tuple[float, str]]:
    """段 = 相邻两事件之间的区间；时长 < dmin 拍的段 → 移除界定它的两个事件；从前向后单遍、不递归。

    首事件之前取反状态、末事件之后保持末状态（两端段不参与移除）。
    """
    if not events or dmin_beats <= 0 or len(beats) < 2:
        return list(events)
    bidx = lambda t: float(np.interp(t, beats, np.arange(len(beats))))
    out, i = [], 0
    while i < len(events):
        if i + 1 < len(events):
            dur = abs(bidx(events[i + 1][0]) - bidx(events[i][0]))
            if dur < dmin_beats:
                i += 2            # 移除界定该短段的两个事件 → 前后段合并
                continue
        out.append(events[i]); i += 1
    return out


def labels(mapped: list[tuple[float, str]]) -> set[tuple[float, str]]:
    return {(snap(p), "DOWN" if k == "start" else "UP") for p, k in mapped}


def f1_of(pred, truth, tol):
    """与 inversion_baselines.py 同口径：P=tp/(tp+fp)、wrong 单列不进分母（D-0063）。"""
    pl, tl = sorted(pred), sorted(truth)
    tp = 0; mp, mt = set(), set()
    for lab in ("DOWN", "UP"):
        pi = [i for i, x in enumerate(pl) if x[1] == lab]
        ti = [j for j, x in enumerate(tl) if x[1] == lab]
        if not pi or not ti:
            continue
        cost = np.full((len(pi), len(ti)), 1e6)
        for a, i in enumerate(pi):
            for b, j in enumerate(ti):
                d = abs(pl[i][0] - tl[j][0])
                if d <= tol:
                    cost[a, b] = d
        ra, cb = linear_sum_assignment(cost)
        for a, b in zip(ra, cb):
            if cost[a, b] <= tol:
                tp += 1; mp.add(pi[a]); mt.add(ti[b])
    fp = len(pl) - len(mp); fn = len(tl) - len(mt)
    wrong = 0
    if tol > 0:
        for i, (pt, lb) in enumerate(pl):
            if i in mp: continue
            for j, (tt, tb) in enumerate(tl):
                if j in mt or tb == lb: continue
                if abs(pt - tt) <= tol:
                    wrong += 1; break
    p = tp/(tp+fp) if (tp+fp) else 0.0
    r = tp/(tp+fn) if (tp+fn) else 0.0
    return {"n_pred": len(pl), "tp": tp, "fp": fp, "fn": fn, "wrong": wrong,
            "P": p, "R": r, "F1": 2*p*r/(p+r) if (p+r) else 0.0}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dataset", type=Path, default=Path("data/asap-dataset"))
    ap.add_argument("--split", type=Path, default=Path("evidence/R1/G1-split/split_v1.json"))
    ap.add_argument("--out-dir", type=Path, default=Path("results/E1"))
    args = ap.parse_args()
    D = args.dataset
    split = json.loads(args.split.read_text(encoding="utf-8"))
    ann = json.loads((D/"asap_annotations.json").read_text(encoding="utf-8"))
    from lxml import etree
    main_scores = set(split["main_scores"])
    repeat = {s for s in main_scores if etree.parse(str(D/s)).getroot().xpath(".//*[local-name()='repeat']")}
    fold_of = {p["xml_score"]: p["fold"] for p in split["per_performance"]}
    group_of = {s: split["score_meta"][s]["group"] for s in split["main_scores"]}
    cache, runs = {}, []
    for p in split["per_performance"]:
        xml = p["xml_score"]
        if xml not in main_scores or xml in repeat: continue
        al = D/p["alignment_path"] if p["alignment_path"] else None
        perf = D/p["midi_performance"]
        if not (al and al.is_file() and perf.is_file()): continue
        beats = ann.get(p["midi_performance"], {}).get("performance_beats")
        if not beats or len(beats) < 2: continue
        if xml not in cache: cache[xml] = parse_score(D/xml)
        notes, pedals = cache[xml]
        seq = sorted((onset, notes[b][1]) for b, r, onset in parse_alignment(al) if b in notes)
        if len(seq) < 2: continue
        truth = {(snap(o), "DOWN" if k == "start" else "UP") for (m, o, k) in pedals}
        if not truth: continue
        runs.append({"score": xml, "perf": p["midi_performance"], "fold": fold_of.get(xml),
                     "group": group_of.get(xml), "truth": truth,
                     "events": cc64_transitions(perf), "beats": beats, "seq": seq})
    print(f"可用 runs = {len(runs)}")

    def eval_dmin(dmin_beats):
        per = []
        for r in runs:
            ev = dejitter(r["events"], r["beats"], dmin_beats)
            mapped = []
            for t, kind in ev:
                got = to_anchor(t, r["seq"], [])
                if got: mapped.append((got[0], kind))
            pred = labels(mapped)
            rec = {"score": r["score"], "perf": r["perf"], "fold": r["fold"], "group": r["group"]}
            for tol in TOLS:
                rec[f"tol{tol}"] = f1_of(pred, r["truth"], tol)
            per.append(rec)
        return per

    def agg(sel, tol):
        tp = sum(x[f"tol{tol}"]["tp"] for x in sel); fp = sum(x[f"tol{tol}"]["fp"] for x in sel)
        fn = sum(x[f"tol{tol}"]["fn"] for x in sel); npd = sum(x[f"tol{tol}"]["n_pred"] for x in sel)
        wr = sum(x[f"tol{tol}"]["wrong"] for x in sel)
        p = tp/(tp+fp) if (tp+fp) else 0; rr = tp/(tp+fn) if (tp+fn) else 0
        return {"n_pred": npd, "tp": tp, "fp": fp, "fn": fn, "wrong": wr,
                "P": p, "R": rr, "F1": 2*p*rr/(p+rr) if (p+rr) else 0}

    out = args.out_dir; out.mkdir(parents=True, exist_ok=True)
    full0 = eval_dmin(0.0)
    print("=== 回归锚（d_min=0，应为 #pred=132,116 / 0.0568 / 0.2766 / 0.3146）===")
    for tol in TOLS:
        a = agg(full0, tol)
        print(f"  ±{tol}: #pred={a['n_pred']} P={a['P']:.4f} R={a['R']:.4f} F1={a['F1']:.4f} wrong={a['wrong']}")
    with (out/"B1_perf.csv").open("w", encoding="utf-8", newline="") as fh:
        w = csv.writer(fh); w.writerow(["d_min_beats","scope","fold","score","perf","tol","n_pred","tp","fp","fn","wrong","P","R","F1"])
        for dmin in D_MIN_GRID:
            for x in eval_dmin(dmin*GRID):
                for tol in TOLS:
                    m = x[f"tol{tol}"]
                    w.writerow([dmin*GRID,"all",x["fold"],x["score"],x["perf"],tol,m["n_pred"],m["tp"],m["fp"],m["fn"],m["wrong"],
                                round(m["P"],6),round(m["R"],6),round(m["F1"],6)])
    tr = [r for r in runs if r["fold"] == "train"]
    groups = sorted({r["group"] for r in tr})
    fold_id = {g: i % 5 for i, g in enumerate(groups)}
    cv_rows = []
    for dmin in D_MIN_GRID:
        per = [x for x in eval_dmin(dmin*GRID) if x["fold"] == "train"]
        cell = {"d_min_grid": dmin, "d_min_beats": dmin*GRID}
        for tol in TOLS: cell[f"tol{tol}"] = agg(per, tol)
        f1s = [agg([x for x in per if fold_id.get(x["group"]) == k], 1.0)["F1"] for k in range(5)]
        cell["fold_f1_at_1"] = f1s; cell["mean_f1_at_1"] = float(np.mean(f1s))
        cv_rows.append(cell)
        print(f"CV d_min={dmin*GRID}拍: " + " ".join(f"±{t}:#pred={cell[f'tol{t}']['n_pred']} P={cell[f'tol{t}']['P']:.3f} R={cell[f'tol{t}']['R']:.3f} F1={cell[f'tol{t}']['F1']:.4f}" for t in TOLS) + f" | meanfoldF1@1={cell['mean_f1_at_1']:.4f}")
    best = max(cv_rows, key=lambda c: (c["mean_f1_at_1"], -c["d_min_grid"]))
    print(f"\n选中 d_min = {best['d_min_beats']} 拍（{best['d_min_grid']} 格）")
    sel = eval_dmin(best["d_min_beats"])
    summary = {"selected_d_min_beats": best["d_min_beats"], "cv": cv_rows,
               "anchor_dmin0": {f"±{t}": agg(full0, t) for t in TOLS}, "val": {}, "test": {}}
    for f in ("val","test"):
        s = [x for x in sel if x["fold"] == f]
        summary[f] = {f"±{t}": agg(s, t) for t in TOLS}
        print(f"{f}: " + " ".join(f"±{t}:#pred={summary[f][f'±{t}']['n_pred']} P={summary[f][f'±{t}']['P']:.3f} R={summary[f][f'±{t}']['R']:.3f} F1={summary[f][f'±{t}']['F1']:.4f}" for t in TOLS))
    (out/"B1_summary.json").write_text(json.dumps(summary, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())