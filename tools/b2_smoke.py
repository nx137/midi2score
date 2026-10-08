#!/usr/bin/env python
"""B2 冒烟：双指针分桶 vs 全表扫描，逐锚点 {n_notes,bass,bass_pc,pcs} **字典全等**。

谓词原文（score_features.anchor_features 内，逐字抄录）：
    sel = [n["pitch"] for n in notes.values() if n["pitch"] is not None and t <= n["pos"] < t + grid]
⇒ 只依赖 pos（半开区间 [t, t+grid)），故下列双指针用的**同一个 t + GRID 比较式**，成员集合由构造相同。
不使用除法取整分桶（避免浮点错桶）。
"""

from __future__ import annotations
import sys, time
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from score_features import GRID, anchor_features, parse_score_extended

SCORES = [
    "Chopin/Ballades/3/xml_score.musicxml",          # 含和弦
    "Schumann/Kreisleriana/6/xml_score.musicxml",    # out-of-grid（先前偏差谱）
    "Beethoven/Piano_Sonatas/32-1/xml_score.musicxml",
]


def main() -> int:
    D = Path("data/asap-dataset")
    total_eq = total = 0
    empty_seen = 0
    for rel in SCORES:
        t0 = time.perf_counter()
        notes = parse_score_extended(D / rel)
        items = sorted(((n["pos"], i, n) for i, n in notes.items() if n["pitch"] is not None), key=lambda x: x[0])
        onsets = [x[0] for x in items]
        span = max(onsets) if onsets else 0.0
        anchors = [round(i * GRID, 6) for i in range(int(round(span / GRID)) + 1)]
        eq = 0; lo = 0; hi = 0; n_empty = 0
        for t in anchors:
            while lo < len(onsets) and onsets[lo] < t: lo += 1
            if hi < lo: hi = lo
            while hi < len(onsets) and onsets[hi] < t + GRID: hi += 1
            sub = {items[k][1]: items[k][2] for k in range(lo, hi)}   # 同一谓词的成员集合
            full = anchor_features(notes, t)
            fast = anchor_features(sub, t)
            if full["n_notes"] == 0: n_empty += 1
            if (full["n_notes"], full["bass"], full["bass_pc"], full["pcs"]) == (fast["n_notes"], fast["bass"], fast["bass_pc"], fast["pcs"]):
                eq += 1
        total_eq += eq; total += len(anchors); empty_seen += n_empty
        print(f"{rel}: anchors={len(anchors)} 全等={eq}/{len(anchors)} 空锚点={n_empty} 耗时={time.perf_counter()-t0:.2f}s")
    print(f"\n合计：全等 {total_eq}/{total}；空锚点样本 {empty_seen}（应 >0）；判据 = 字典全等（不是 F1/分布）")
    print("PASS" if (total_eq == total and empty_seen > 0) else "FAIL")
    return 0 if (total_eq == total and empty_seen > 0) else 1


if __name__ == "__main__":
    raise SystemExit(main())