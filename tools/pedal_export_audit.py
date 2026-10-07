#!/usr/bin/env python
"""按 D-0025（controller 裁定）对导出探针结果做 Tier 分级与分布统计。

裁定要点：
  1. 唯一否决条件 = start > 0 且 CC64 == 0（T1）
  2. 主结构诊断量 = CC64 == 2 × min(start, stop)（不否决，但必须逐首列名）
  3. 作废 [0.80, 1.05] 带宽；改报 P5/P50/P95（分母 = 2 × min(start, stop)），不设阈值
  4. Tier: T1 否决 / T2 恒等式不成立且 min>0（T2b: 缺口>10%）/ T3 min==0 且 CC64==0
  5. 与既有导出记录重叠的乐谱，CC64 必须逐值一致
"""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path

import numpy as np
from lxml import etree

PEDAL_XPATH = ".//*[local-name()='pedal']"
T2B_GAP = 0.10  # 报告阈值，非闸门（G1' 后按实测分布重设）
BASELINES = {
    "Chopin/Ballades/1/xml_score.musicxml": 432,
    "Chopin/Ballades/3/xml_score.musicxml": 478,
}


def pedal_sequence(xml_path: Path) -> dict:
    elems = etree.parse(str(xml_path)).getroot().xpath(PEDAL_XPATH)
    kinds = [e.get("type") for e in elems]
    depth = 0
    orphan_stop = 0
    unclosed = 0
    changes = 0
    for prev, cur in zip(kinds, kinds[1:]):
        if prev == "stop" and cur == "start":
            changes += 1
    for k in kinds:
        if k == "start":
            depth += 1
        elif k == "stop":
            if depth > 0:
                depth -= 1
            else:
                orphan_stop += 1
    unclosed = depth
    return {
        "pedal_elements": len(elems),
        "pedal_start": kinds.count("start"),
        "pedal_stop": kinds.count("stop"),
        "unclosed_start": unclosed,
        "orphan_stop": orphan_stop,
        # 定义待 controller 确认：本实现取「stop 紧跟 start」的换踩(changed)次数
        "inverted_pairs_PROVISIONAL": changes,
    }


def classify(row: dict) -> tuple[str, float | None]:
    start, stop, cc64 = row["pedal_start"], row["pedal_stop"], row["cc64_messages"]
    expected = 2 * min(start, stop)
    gap = round(abs(cc64 - expected) / expected, 4) if expected > 0 else None
    if start > 0 and cc64 == 0:
        tier = "T1"
    elif min(start, stop) == 0 and cc64 == 0:
        tier = "T3"
    elif cc64 != expected:
        tier = "T2b" if (gap or 0) > T2B_GAP else "T2"
    else:
        tier = "OK"
    return tier, gap


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dataset", type=Path, default=Path("data/asap-dataset"))
    parser.add_argument("--probe", type=Path, default=Path("evidence/R1/full68/export_probe.json"))
    parser.add_argument("--out-dir", type=Path, default=Path("evidence/R1/G1-tiers"))
    args = parser.parse_args()

    probe = json.loads(args.probe.read_text(encoding="utf-8"))
    rows = []
    for r in probe["rows"]:
        if r["kind"] != "positive":
            continue
        seq = pedal_sequence(args.dataset / r["relative_path"])
        merged = {**r, **seq}
        merged["cc64_over_identity"] = (
            round(merged["cc64_messages"] / (2 * min(merged["pedal_start"], merged["pedal_stop"])), 4)
            if min(merged["pedal_start"], merged["pedal_stop"]) > 0 else None
        )
        tier, gap = classify(merged)
        merged["tier"] = tier
        merged["t1_t3_overlap"] = bool(merged["pedal_start"] > 0 and merged["pedal_stop"] == 0 and merged["cc64_messages"] == 0)
        merged["gap_pct"] = None if gap is None else round(gap * 100, 2)
        rows.append(merged)

    ratios = [r["cc64_over_identity"] for r in rows if r["cc64_over_identity"] is not None]
    p5, p50, p95 = (np.percentile(ratios, [5, 50, 95]).round(4).tolist() if ratios else [None] * 3)

    by_tier: dict[str, list[str]] = {}
    for r in rows:
        by_tier.setdefault(r["tier"], []).append(r["relative_path"])

    baseline_check = {
        rel: {"expected": exp, "observed": next((r["cc64_messages"] for r in rows if r["relative_path"] == rel), None)}
        for rel, exp in BASELINES.items()
    }
    baseline_ok = all(v["expected"] == v["observed"] for v in baseline_check.values())

    summary = {
        "controller_ruling": "D-0025 (T1/T2/T2b/T3, identity diagnostic, no bandwidth)",
        "n_scores": len(rows),
        "tier_counts": {k: len(v) for k, v in sorted(by_tier.items())},
        "tier_members": {k: sorted(v) for k, v in sorted(by_tier.items())},
        "cc64_over_identity_percentiles": {"P5": p5, "P50": p50, "P95": p95, "n": len(ratios)},
        "t2b_gap_threshold_pct": T2B_GAP * 100,
        "t1_t3_overlap_count": sum(1 for r in rows if r.get("t1_t3_overlap")),
        "t1_t3_overlap_members": sorted(r["relative_path"] for r in rows if r.get("t1_t3_overlap")),
        "strict_t1_min_gt_0_and_cc64_eq_0": sorted(r["relative_path"] for r in rows
            if min(r["pedal_start"], r["pedal_stop"]) > 0 and r["cc64_messages"] == 0),
        "t2_required_fields": ["pedal_start", "pedal_stop", "unclosed_start", "orphan_stop",
                               "inverted_pairs_PROVISIONAL", "cc64_messages", "gap_pct"],
        "baseline_check": baseline_check,
        "baseline_all_match": baseline_ok,
        "inverted_pairs_definition": "PROVISIONAL: stop 紧跟 start 的次数（待 controller 确认）",
    }

    args.out_dir.mkdir(parents=True, exist_ok=True)
    (args.out_dir / "tiers.json").write_text(json.dumps({"summary": summary, "rows": rows}, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    with (args.out_dir / "tiers.csv").open("w", encoding="utf-8", newline="") as handle:
        fields = ["tier", "t1_t3_overlap", "relative_path", "pedal_elements", "pedal_start", "pedal_stop", "unclosed_start",
                  "orphan_stop", "inverted_pairs_PROVISIONAL", "cc64_messages", "cc64_over_identity",
                  "gap_pct", "exit_code", "output_exists"]
        writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)

    print(json.dumps(summary, indent=2, ensure_ascii=False))
    print("\n=== T2 / T2b 逐首（七字段） ===")
    for r in rows:
        if r["tier"] in ("T2", "T2b"):
            print(f"  [{r['tier']}] {r['relative_path']} | start={r['pedal_start']} stop={r['pedal_stop']} "
                  f"unclosed={r['unclosed_start']} orphan={r['orphan_stop']} inverted={r['inverted_pairs_PROVISIONAL']} "
                  f"cc64={r['cc64_messages']} gap={r['gap_pct']}%")
    return 0 if baseline_ok else 1


if __name__ == "__main__":
    raise SystemExit(main())