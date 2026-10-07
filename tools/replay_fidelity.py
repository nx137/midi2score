#!/usr/bin/env python
"""主指标：回放保真度（HC-03 / §6.1）。

比较对象：**渲染侧 CC64′**（乐谱印刷记号 → MuseScore 导出）vs **演奏侧 CC64**。
共同轴：谱面位置（四分音符，全局；演奏侧经 nASAP 分段线性映射，渲染侧经"第 i 个渲染音符 ↔ 第 i 个展开谱面音符"的单调索引映射）。
容差：±1/8 拍（=0.125 四分音符）。基线：按谱面位置每 N 拍一个 DOWN。
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import mido
import numpy as np
from scipy.optimize import linear_sum_assignment

sys.path.insert(0, str(Path(__file__).resolve().parent))
from inversion_consistency import cc64_transitions, parse_alignment, parse_score, snap  # noqa: E402

TOL_Q = 0.125  # ±1/8 拍


def events_to_positions(events, seq):
    """seq = [(t,pos)] 单调；把 (t,kind) 映射成 (snap(pos), kind)。"""
    if len(seq) < 2:
        return set()
    ts = [t for t, _ in seq]
    ps = [p for _, p in seq]
    out = set()
    for t, kind in events:
        out.add((snap(float(np.interp(t, ts, ps))), "DOWN" if kind == "start" else "UP"))
    return out


def f1(pred, truth, tol):
    pl, tl = sorted(pred), sorted(truth)
    tp = 0
    mp, mt = set(), set()
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
                tp += 1
                mp.add(pi[a]); mt.add(ti[b])
    fp, fn = len(pl) - len(mp), len(tl) - len(mt)
    p = tp / (tp + fp) if (tp + fp) else 0.0
    r = tp / (tp + fn) if (tp + fn) else 0.0
    return {"tp": tp, "fp": fp, "fn": fn, "P": p, "R": r,
            "F1": 2 * p * r / (p + r) if (p + r) else 0.0}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dataset", type=Path, default=Path("data/asap-dataset"))
    ap.add_argument("--split", type=Path, default=Path("evidence/R1/G1-split/split_v1.json"))
    ap.add_argument("--rendered-dir", type=Path, default=Path("evidence/R1/full68v2"))
    ap.add_argument("--out-dir", type=Path, default=Path("evidence/R1/G1-replay"))
    args = ap.parse_args()

    ds = args.dataset
    split = json.loads(args.split.read_text(encoding="utf-8"))
    from lxml import etree
    main = set(split["main_scores"])
    repeat = {s for s in main if etree.parse(str(ds / s)).getroot().xpath(".//*[local-name()='repeat']")}
    rows = [p for p in split["per_performance"] if p["xml_score"] in main and p["xml_score"] not in repeat]

    cache = {}
    out_rows = []
    for p in rows:
        xml = p["xml_score"]
        if xml not in cache:
            cache[xml] = parse_score(ds / xml)
        notes, pedals = cache[xml]
        align = ds / p["alignment_path"] if p["alignment_path"] else None
        perf_mid = ds / p["midi_performance"]
        rend_mid = args.rendered_dir / Path(xml).with_suffix(".mid")
        if not (align and align.is_file() and perf_mid.is_file() and rend_mid.is_file()):
            continue
        al = parse_alignment(align)
        seq = sorted((onset, notes[b][1]) for b, r, onset in al if b in notes)
        if len(seq) < 2:
            continue
        truth = events_to_positions(cc64_transitions(perf_mid), seq)
        if not truth:
            continue
        # 渲染侧：第 i 个渲染音符 <-> 第 i 个展开谱面音符（单调索引映射）
        rf = mido.MidiFile(str(rend_mid))
        ront = []
        acc = 0.0
        for msg in rf:
            acc += msg.time
            if msg.type == "note_on" and msg.velocity > 0:
                ront.append(acc)
        if len(ront) < 2:
            continue
        idx = np.round(np.linspace(0, len(seq) - 1, len(ront))).astype(int)
        rmap = [(ront[i], seq[j][1]) for i, j in enumerate(idx)]
        used = [pos for _, pos in rmap]
        mono = all(used[i] <= used[i + 1] for i in range(len(used) - 1))
        pred = events_to_positions(cc64_transitions(rend_mid), rmap)
        span = max([x[0] for x in truth], default=0.0)
        rec = {"score": xml, "performance": p["midi_performance"], "monotone_map": bool(mono),
               "n_rendered_notes": len(ront), "n_unfolded_notes": len(seq),
               "oracle": f1(pred, truth, TOL_Q)}
        for n in (1, 2, 4):
            base = {(snap(x), "DOWN") for x in np.arange(0, span + 0.25, float(n))}
            rec[f"beat_periodic_{n}"] = f1(base, truth, TOL_Q)
        out_rows.append(rec)

    def agg(sel, key):
        tp = sum(r[key]["tp"] for r in sel); fp = sum(r[key]["fp"] for r in sel); fn = sum(r[key]["fn"] for r in sel)
        p = tp / (tp + fp) if (tp + fp) else 0; r = tp / (tp + fn) if (tp + fn) else 0
        return {"F1": 2 * p * r / (p + r) if (p + r) else 0, "P": p, "R": r, "tp": tp, "fp": fp, "fn": fn}

    summary = {"n_runs": len(out_rows), "tol_quarters": TOL_Q,
               "monotone_map_all": all(r["monotone_map"] for r in out_rows),
               "oracle": agg(out_rows, "oracle"),
               "beat_periodic_1": agg(out_rows, "beat_periodic_1"),
               "beat_periodic_2": agg(out_rows, "beat_periodic_2"),
               "beat_periodic_4": agg(out_rows, "beat_periodic_4")}
    args.out_dir.mkdir(parents=True, exist_ok=True)
    (args.out_dir / "replay_fidelity.json").write_text(
        json.dumps({"summary": summary, "per_run": out_rows}, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps(summary, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())