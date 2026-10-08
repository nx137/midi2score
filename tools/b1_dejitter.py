#!/usr/bin/env python
"""B1 = 阈值 + 抖动抑制规则（§5.2）。只新增两个函数：dejitter / labels；其余全部复用既有实现。

域（D-0061①）：
  全量 271 runs / 36 scores  -> 回归锚 #pred=132,116 与三档曲线
  train 折内 5 折            -> CV 选 d_min
  val / test                 -> 各跑一次（val 仅健全性；test 是 E1 主表来源）
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

D_MIN_GRID = [0, 1, 2, 4, 8]          # = 0 / 0.25 / 0.5 / 1.0 / 2.0 拍
TOLS = [0.0, 1.0, 2.0]                # 拍


def dejitter(states: list[bool], dmin: int) -> list[bool]:
    """长度 < dmin 的连续同态段并入前一段；首段被后一段吸收。"""
    if dmin <= 0 or not states:
        return list(states)
    runs = []
    for s in states:
        if runs and runs[-1][0] == s:
            runs[-1][1] += 1
        else:
            runs.append([s, 1])
    out_runs = []
    for i, (v, ln) in enumerate(runs):
        if ln < dmin:
            if i == 0:
                continue                    # 首段被后一段吸收
            if out_runs:
                out_runs[-1][1] += ln        # 并入前一段
                continue
        out_runs.append([v, ln])
    res = []
    for v, ln in out_runs:
        res.extend([v] * ln)
    return res


def labels(states: list[bool], cells: list[float]) -> set[tuple[float, str]]:
    """跳变格标 DOWN/UP；首格为 ON 则首格标 DOWN。"""
    out = set()
    if states and states[0]:
        out.add((snap(cells[0]), "DOWN"))
    for i in range(1, len(states)):
        if states[i] != states[i - 1]:
            out.add((snap(cells[i]), "DOWN" if states[i] else "UP"))
    return out


def f1(pred, truth, tol):
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
    p = tp / (tp + fp) if (tp + fp) else 0.0
    r = tp / (tp + fn) if (tp + fn) else 0.0
    return {"n_pred": len(pl), "tp": tp, "fp": fp, "fn": fn, "P": p, "R": r,
            "F1": 2 * p * r / (p + r) if (p + r) else 0.0}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dataset", type=Path, default=Path("data/asap-dataset"))
    ap.add_argument("--split", type=Path, default=Path("evidence/R1/G1-split/split_v1.json"))
    ap.add_argument("--out-dir", type=Path, default=Path("results/E1"))
    args = ap.parse_args()
    D = args.dataset
    split = json.loads(args.split.read_text(encoding="utf-8"))
    from lxml import etree
    main_scores = set(split["main_scores"])
    repeat = {s for s in main_scores if etree.parse(str(D/s)).getroot().xpath(".//*[local-name()='repeat']")}
    fold_of = {p["xml_score"]: p["fold"] for p in split["per_performance"]}
    group_of = {s: split["score_meta"][s]["group"] for s in split["main_scores"]}
    cache = {}
    runs = []
    for p in split["per_performance"]:
        xml = p["xml_score"]
        if xml not in main_scores or xml in repeat:
            continue
        al = D/p["alignment_path"] if p["alignment_path"] else None
        perf = D/p["midi_performance"]
        if not (al and al.is_file() and perf.is_file()):
            continue
        if xml not in cache:
            cache[xml] = parse_score(D/xml)
        notes, pedals = cache[xml]
        seq = sorted((onset, notes[b][1]) for b, r, onset in parse_alignment(al) if b in notes)
        if len(seq) < 2:
            continue
        truth = {(snap(o), "DOWN" if k == "start" else "UP") for (m, o, k) in pedals}
        if not truth:
            continue
        ev = []
        for t, kind in cc64_transitions(perf):
            got = to_anchor(t, seq, [])
            if got:
                ev.append((snap(got[0]), "DOWN" if kind == "start" else "UP"))
        if not ev:
            continue
        ev.sort()
        lo, hi = ev[0][0], ev[-1][0]
        cells = [round(lo + i*GRID, 6) for i in range(int(round((hi-lo)/GRID)) + 1)]
        st, ei = [], 0
        cur = False
        for c in cells:
            while ei < len(ev) and ev[ei][0] <= c:
                cur = ev[ei][1] == "DOWN"; ei += 1
            st.append(cur)
        runs.append({"score": xml, "perf": p["midi_performance"], "fold": fold_of.get(xml),
                     "group": group_of.get(xml), "truth": truth, "states": st, "cells": cells})
    print(f"可用 runs = {len(runs)}")

    def eval_dmin(dmin):
        per = []
        for r in runs:
            pred = labels(dejitter(r["states"], dmin), r["cells"])
            rec = {"score": r["score"], "perf": r["perf"], "fold": r["fold"], "group": r["group"]}
            for tol in TOLS:
                rec[f"tol{tol}"] = f1(pred, r["truth"], tol)
            per.append(rec)
        return per

    def agg(sel, tol):
        tp = sum(x[f"tol{tol}"]["tp"] for x in sel); fp = sum(x[f"tol{tol}"]["fp"] for x in sel)
        fn = sum(x[f"tol{tol}"]["fn"] for x in sel); npd = sum(x[f"tol{tol}"]["n_pred"] for x in sel)
        p = tp/(tp+fp) if (tp+fp) else 0; rr = tp/(tp+fn) if (tp+fn) else 0
        return {"n_pred": npd, "P": p, "R": rr, "F1": 2*p*rr/(p+rr) if (p+rr) else 0}

    out = args.out_dir; out.mkdir(parents=True, exist_ok=True)
    # 全量回归锚
    full0 = eval_dmin(0)
    print("=== 全量回归锚（d_min=0）===")
    for tol in TOLS:
        a = agg(full0, tol)
        print(f"  ±{tol} 拍: #pred={a['n_pred']} P={a['P']:.4f} R={a['R']:.4f} F1={a['F1']:.4f}")
    # CV（train 内 5 折，按曲目组）
    tr = [r for r in runs if r["fold"] == "train"]
    groups = sorted({r["group"] for r in tr})
    fold_id = {g: i % 5 for i, g in enumerate(groups)}
    cv_rows = []
    for dmin in D_MIN_GRID:
        per = [x for x in eval_dmin(dmin) if x["fold"] == "train"]
        cell = {"d_min_grid": dmin, "d_min_beats": dmin*GRID}
        for tol in TOLS:
            a = agg(per, tol); cell[f"tol{tol}"] = a
        # 每折 micro F1@±1
        f1s = []
        for k in range(5):
            sel = [x for x in per if fold_id.get(x["group"]) == k]
            f1s.append(agg(sel, 1.0)["F1"] if sel else 0.0)
        cell["fold_f1_at_1"] = f1s
        cell["mean_f1_at_1"] = float(np.mean(f1s))
        cv_rows.append(cell)
        print(f"CV d_min={dmin} 格({dmin*GRID}拍): " +
              " ".join(f"±{t}: #pred={cell[f'tol{t}']['n_pred']} P={cell[f'tol{t}']['P']:.3f} R={cell[f'tol{t}']['R']:.3f} F1={cell[f'tol{t}']['F1']:.4f}" for t in TOLS) +
              f" | mean_foldF1@1={cell['mean_f1_at_1']:.4f}")
    best = max(cv_rows, key=lambda c: (c["mean_f1_at_1"], -c["d_min_grid"]))
    print(f"\n选中 d_min = {best['d_min_grid']} 格 = {best['d_min_beats']} 拍")
    (out/"B1_cv.json").write_text(json.dumps(cv_rows, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    # val / test（用选中档，各一次）
    sel_all = eval_dmin(best["d_min_grid"])
    summary = {"selected_d_min_grid": best["d_min_grid"], "selected_d_min_beats": best["d_min_beats"],
               "full_dmin0": {f"±{t}": agg(full0, t) for t in TOLS},
               "cv": cv_rows, "val": {}, "test": {}}
    for f in ("val", "test"):
        s = [x for x in sel_all if x["fold"] == f]
        summary[f] = {f"±{t}": agg(s, t) for t in TOLS}
        print(f"{f}: " + " ".join(f"±{t}: #pred={summary[f][f'±{t}']['n_pred']} P={summary[f][f'±{t}']['P']:.3f} R={summary[f][f'±{t}']['R']:.3f} F1={summary[f][f'±{t}']['F1']:.4f}" for t in TOLS))
    (out/"B1_summary.json").write_text(json.dumps(summary, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())