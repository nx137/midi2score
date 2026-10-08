#!/usr/bin/env python
"""把「地板与参照」表在 **test 折**上重算（与 E1 主表同域），并按标签（DOWN/UP）分列 P/R/F1。

方法：inversion(d_min=0) + always_down + beat_periodic_1/2/4；容差 0/±1/±2 拍。
"""

from __future__ import annotations

import argparse, json, sys
from pathlib import Path
import numpy as np
import sys as _s
_s.path.insert(0, str(Path(__file__).resolve().parent))
from inversion_baselines import f1_of  # 同口径（D-0063）
from inversion_consistency import GRID, cc64_transitions, parse_alignment, parse_score, snap, to_anchor

TOLS = [0.0, 1.0, 2.0]


def per_label(pred, truth, tol):
    out = {}
    for lab in ("DOWN", "UP"):
        p = {x for x in pred if x[1] == lab}; t = {x for x in truth if x[1] == lab}
        m = f1_of(p, t, tol)
        out[lab] = {"n_pred": m["n_pred"], "P": round(m["P"], 4), "R": round(m["R"], 4), "F1": round(m["F1"], 4)}
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dataset", type=Path, default=Path("data/asap-dataset"))
    ap.add_argument("--split", type=Path, default=Path("evidence/R1/G1-split/split_v1.json"))
    ap.add_argument("--fold", default="test")
    ap.add_argument("--out", type=Path, default=Path("results/E1/floor_reference_test.md"))
    args = ap.parse_args()
    D = args.dataset
    split = json.loads(args.split.read_text(encoding="utf-8"))
    from lxml import etree
    main_scores = set(split["main_scores"])
    repeat = {s for s in main_scores if etree.parse(str(D/s)).getroot().xpath(".//*[local-name()='repeat']")}
    cache = {}
    recs = []
    for p in split["per_performance"]:
        xml = p["xml_score"]
        if p["fold"] != args.fold or xml not in main_scores or xml in repeat: continue
        al = D/p["alignment_path"] if p["alignment_path"] else None
        perf = D/p["midi_performance"]
        if not (al and al.is_file() and perf.is_file()): continue
        if xml not in cache: cache[xml] = parse_score(D/xml)
        notes, pedals = cache[xml]
        seq = sorted((o, notes[b][1]) for b, r, o in parse_alignment(al) if b in notes)
        if len(seq) < 2: continue
        truth = {(snap(o), "DOWN" if k == "start" else "UP") for (m, o, k) in pedals}
        if not truth: continue
        inv = set()
        for t, kind in cc64_transitions(perf):
            got = to_anchor(t, seq, [])
            if got: inv.add((snap(got[0]), "DOWN" if kind == "start" else "UP"))
        span = max([x[0] for x in truth], default=0.0)
        methods = {"inversion": inv}
        methods["always_down"] = {(snap(x), "DOWN") for x in np.arange(0, span + 0.25, GRID)}
        for n in (1, 2, 4):
            methods[f"beat_periodic_{n}"] = {(snap(x), "DOWN") for x in np.arange(0, span + 0.25, float(n))}
        recs.append({"truth": truth, "methods": methods})
    lines = [f"# 地板与参照（{args.fold} 折，与 E1 主表同域）\n",
             f"runs = {len(recs)}（域：Main 43 首中不含 repeat 者，fold={args.fold}）\n",
             "## micro（P=tp/(tp+fp)，wrong 不进分母；D-0063）\n",
             "| 方法 | ±0 F1 | ±1 F1 | ±2 F1 |", "|:--|--:|--:|--:|"]
    for name in ("inversion", "always_down", "beat_periodic_1", "beat_periodic_2", "beat_periodic_4"):
        cells = []
        for tol in TOLS:
            tp = sum(f1_of(r["methods"][name], r["truth"], tol)["tp"] for r in recs)
            fp = sum(f1_of(r["methods"][name], r["truth"], tol)["fp"] for r in recs)
            fn = sum(f1_of(r["methods"][name], r["truth"], tol)["fn"] for r in recs)
            p = tp/(tp+fp) if (tp+fp) else 0; rr = tp/(tp+fn) if (tp+fn) else 0
            cells.append(f"{2*p*rr/(p+rr) if (p+rr) else 0:.4f}")
        lines.append(f"| {name} | {cells[0]} | {cells[1]} | {cells[2]} |")
    lines += ["\n## 分标签 P/R/F1（±1 拍）—— 解释 bp2/bp4 为何能打平\n",
              "| 方法 | DOWN P | DOWN R | DOWN F1 | UP P | UP R | UP F1 |", "|:--|--:|--:|--:|--:|--:|--:|"]
    for name in ("inversion", "always_down", "beat_periodic_1", "beat_periodic_2", "beat_periodic_4"):
        agg = {lab: {"tp":0,"fp":0,"fn":0} for lab in ("DOWN","UP")}
        for r in recs:
            for lab in ("DOWN","UP"):
                pr = {x for x in r["methods"][name] if x[1] == lab}; tr = {x for x in r["truth"] if x[1] == lab}
                m = f1_of(pr, tr, 1.0)
                for k in ("tp","fp","fn"): agg[lab][k] += m[k]
        cells = []
        for lab in ("DOWN","UP"):
            tp, fp, fn = agg[lab]["tp"], agg[lab]["fp"], agg[lab]["fn"]
            p = tp/(tp+fp) if (tp+fp) else 0; rr = tp/(tp+fn) if (tp+fn) else 0
            cells += [f"{p:.3f}", f"{rr:.3f}", f"{2*p*rr/(p+rr) if (p+rr) else 0:.4f}"]
        lines.append(f"| {name} | " + " | ".join(cells) + " |")
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("\n".join(lines))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())