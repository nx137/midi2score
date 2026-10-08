#!/usr/bin/env python
"""主指标 v2：回放保真度（事件级为主）。

- 演奏侧 CC64 → 谱面位置：nASAP 对齐的分段线性映射（秒 → 四分音符）
- 渲染侧 CC64' → 谱面位置：**逐轨 tick / PPQ**（通道自检已确认该映射落在量化格内，40/43）
- 容差曲线：0 / ±0.25 / ±0.5 / ±1.0 拍（四分音符单位）
- 基线：always_down / beat_periodic_N（同在谱面位置轴上）
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import defaultdict
from pathlib import Path

import mido
import numpy as np
from scipy.optimize import linear_sum_assignment

sys.path.insert(0, str(Path(__file__).resolve().parent))
from inversion_consistency import cc64_transitions, parse_alignment, parse_score, snap  # noqa: E402

TOLS = [0.0, 0.25, 0.5, 1.0]


def rendered_events(mid_path: Path) -> list[tuple[float, str]]:
    """渲染 MIDI 的 CC64 → (四分音符位置, 'start'/'stop')；用逐轨 tick。"""
    mf = mido.MidiFile(str(mid_path))
    ppq = mf.ticks_per_beat
    out = []
    for tr in mf.tracks:
        t = 0
        for msg in tr:
            t += msg.time
            if msg.type == "control_change" and msg.control == 64:
                out.append((t / ppq, "start" if msg.value >= 64 else "stop"))
    out.sort()
    return out


def to_positions(events, seq):
    ts = [t for t, _ in seq]; ps = [p for _, p in seq]
    return {(snap(float(np.interp(t, ts, ps))), "DOWN" if k == "start" else "UP") for t, k in events}


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
    return {"tp": tp, "fp": fp, "fn": fn, "P": p, "R": r, "F1": 2 * p * r / (p + r) if (p + r) else 0.0}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dataset", type=Path, default=Path("data/asap-dataset"))
    ap.add_argument("--split", type=Path, default=Path("evidence/R1/G1-split/split_v1.json"))
    ap.add_argument("--rendered-dir", type=Path, default=Path("evidence/R1/full68v2"))
    ap.add_argument("--out-dir", type=Path, default=Path("evidence/R1/G1-replay"))
    args = ap.parse_args()
    ds = args.dataset
    split = json.loads(args.split.read_text(encoding="utf-8"))
    fold_of = {p["xml_score"]: p["fold"] for p in split["per_performance"]}
    composer_of = {s: split["score_meta"][s]["composer"] for s in split["main_scores"]}
    cache = {}
    runs = []
    for p in split["per_performance"]:
        xml = p["xml_score"]
        rend = args.rendered_dir / Path(xml).with_suffix(".mid")
        align = ds / p["alignment_path"] if p["alignment_path"] else None
        perf = ds / p["midi_performance"]
        if not (rend.is_file() and align and align.is_file() and perf.is_file()):
            continue
        if xml not in cache:
            cache[xml] = parse_score(ds / xml)
        notes, _ = cache[xml]
        seq = sorted((onset, notes[b][1]) for b, r, onset in parse_alignment(align) if b in notes)
        if len(seq) < 2:
            continue
        truth = to_positions(cc64_transitions(perf), seq)
        if not truth:
            continue
        pred = to_positions(rendered_events(rend), seq=[(x, x) for x, _ in rendered_events(rend)]) if False else \
               {(snap(q), "DOWN" if k == "start" else "UP") for q, k in rendered_events(rend)}
        span = max([x[0] for x in truth], default=0.0)
        rec = {"score": xml, "performance": p["midi_performance"], "fold": fold_of.get(xml),
               "composer": composer_of.get(xml)}
        for tol in TOLS:
            rec[f"oracle@{tol}"] = f1(pred, truth, tol)
        for n in (1, 2, 4):
            base = {(snap(x), "DOWN") for x in np.arange(0, span + 0.25, float(n))}
            for tol in TOLS:
                rec[f"bp{n}@{tol}"] = f1(base, truth, tol)
        runs.append(rec)

    def agg(sel, key):
        tp = sum(r[key]["tp"] for r in sel); fp = sum(r[key]["fp"] for r in sel); fn = sum(r[key]["fn"] for r in sel)
        p = tp / (tp + fp) if (tp + fp) else 0; rr = tp / (tp + fn) if (tp + fn) else 0
        return {"F1": 2 * p * rr / (p + rr) if (p + rr) else 0, "P": p, "R": rr, "tp": tp, "fp": fp, "fn": fn}
    summary = {"n_runs": len(runs), "tols": TOLS,
               "micro": {f"oracle@{t}": agg(runs, f"oracle@{t}") for t in TOLS},
               "baselines": {f"bp{n}@{t}": agg(runs, f"bp{n}@{t}") for n in (1, 2, 4) for t in TOLS},
               "macro_oracle_F1": {str(t): float(np.mean([r[f"oracle@{t}"]["F1"] for r in runs])) for t in TOLS},
               "per_composer_oracle_F1@1.0": {},
               "fold_counts": {}}
    by_comp = defaultdict(list)
    for r in runs:
        by_comp[r["composer"]].append(r)
    for c, sel in sorted(by_comp.items()):
        summary["per_composer_oracle_F1@1.0"][c] = {"n_runs": len(sel), "F1": agg(sel, "oracle@1.0")["F1"]}
    for f in ("train", "val", "test"):
        sel = [r for r in runs if r["fold"] == f]
        summary["fold_counts"][f] = {"runs": len(sel), "scores": len({r["score"] for r in sel}),
                                     "composers": len({r["composer"] for r in sel})}
    args.out_dir.mkdir(parents=True, exist_ok=True)
    (args.out_dir / "replay_fidelity_v2.json").write_text(json.dumps({"summary": summary, "per_run": runs}, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps(summary, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())