#!/usr/bin/env python
"""导出侧审计：按 D-0027/D-0028 的五格谓词（互斥且穷尽）+ T2 七字段 + 分位点 + 逐值一致。

谓词（见 FIELD_DEFINITIONS.md）：
  S/T/C = 记谱 start / stop 数、导出 MIDI 的 CC#64 条数
  I = 2*min(S,T);  g = |C-I|/I  (仅 I>0)
  格1 min>0 且 C==I          -> OK
  格2 min>0 且 C==0          -> T1 否决停机
  格3 min>0 且 C>0 且 C!=I   -> T2 (g>0.10 -> T2b，计入 T2 总数)
  格4 min==0 且 C==0         -> T3 构造上正确
  格5 min==0 且 C>0          -> T4 预期 0，非零即停机
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
from pathlib import Path

import numpy as np
from lxml import etree

PEDAL_XPATH = ".//*[local-name()='pedal']"
T2B_GAP = 0.10  # 报告阈值（非闸门），本轮冻结


def has_repeat(xml_path: Path) -> bool:
    return bool(etree.parse(str(xml_path)).getroot().xpath(".//*[local-name()='repeat']"))


def scan_pedal(xml_path: Path) -> dict:
    """文档顺序扫描。未闭合/孤立 stop 为全局口径；倒置对为局部 balance 跌破 0（不钳位）。"""
    elems = etree.parse(str(xml_path)).getroot().xpath(PEDAL_XPATH)
    kinds = [e.get("type") for e in elems]
    S, T = kinds.count("start"), kinds.count("stop")
    balance = 0
    inverted = 0
    for k in kinds:
        if k == "start":
            balance += 1
        elif k == "stop":
            balance -= 1
            if balance < 0:
                inverted += 1  # 不钳位：保留负值，后续 start 先还账
    first_is_stop_staves = 0  # 一次性交叉核对 (i)
    per_staff: dict[str, list[str]] = {}
    for e in elems:
        per_staff.setdefault(e.get("staff") or "_", []).append(e.get("type"))
    first_is_stop_staves = sum(1 for v in per_staff.values() if v and v[0] == "stop")
    return {
        "pedal_elements": len(elems),
        "pedal_start": S,
        "pedal_stop": T,
        "unclosed_start": max(S - T, 0),
        "orphan_stop": max(T - S, 0),
        "inverted_pairs": inverted,
        "staves_first_pedal_is_stop": first_is_stop_staves,
        "balance_final": balance,
        "has_repeat": has_repeat(xml_path),
    }


def classify(S: int, T: int, C: int) -> tuple[str, int, float | None, float | None]:
    I = 2 * min(S, T)
    g = round(abs(C - I) / I, 6) if I > 0 else None
    if min(S, T) > 0:
        if C == I:
            return "OK", I, g, None
        if C == 0:
            return "T1", I, g, None
        tier = "T2b" if (g or 0) > T2B_GAP else "T2"
        return tier, I, g, g
    return ("T3" if C == 0 else "T4"), I, g, None


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dataset", type=Path, default=Path("data/asap-dataset"))
    ap.add_argument("--probe", type=Path, default=Path("evidence/R1/full68v2/export_probe.json"))
    ap.add_argument("--reference", type=Path, default=Path("evidence/R1/reference/prior_cc64_details.csv"))
    ap.add_argument("--out-dir", type=Path, default=Path("evidence/R1/G1-export"))
    args = ap.parse_args()

    probe = json.loads(args.probe.read_text(encoding="utf-8"))
    rows = []
    for r in probe["rows"]:
        seq = scan_pedal(args.dataset / r["relative_path"])
        S, T, C = seq["pedal_start"], seq["pedal_stop"], r["cc64_messages"] if r["cc64_messages"] is not None else 0
        if seq["has_repeat"]:
            tier, I, g, gap = "coordinate_ambiguous", None, None, None
        else:
            tier, I, g, gap = classify(S, T, C)
        residual = (I - C) - 2 * (seq["unclosed_start"] + seq["orphan_stop"] + seq["inverted_pairs"]) if tier in ("T2", "T2b") else None
        rows.append({
            **r, **seq, "C": C, "I": I, "g": g, "tier": tier,
            "cc64_over_identity": (round(C / I, 4) if (I or 0) > 0 else None),
            "gap_pct": (round(gap * 100, 2) if gap is not None else None),
            "explanatory_residual": residual,
            "source_xml_sha256": hashlib.sha256((args.dataset / r["relative_path"]).read_bytes()).hexdigest(),
        })

    positives = [r for r in rows if r["kind"] == "positive"]
    effective = [r for r in positives if not r["has_repeat"]]
    ambiguous = [r for r in positives if r["has_repeat"]]
    negatives = [r for r in rows if r["kind"] == "negative"]

    # ---- 裁定 5：与既有记录逐值一致（全部重叠乐谱）----
    ref = {}
    with args.reference.open(encoding="utf-8-sig", newline="") as fh:
        for row in csv.DictReader(fh):
            ref[row["relative_xml"]] = row
    overlap = []
    for r in rows:
        old = ref.get(r["relative_path"])
        if old is None:
            continue
        old_c = int(old["cc64_event_count"] or 0)
        overlap.append({
            "relative_path": r["relative_path"],
            "old_cc64": old_c, "new_cc64": r["C"],
            "match": old_c == r["C"],
            "old_output_bytes": int(old["output_bytes"]) if old.get("output_bytes") else None,
            "new_output_bytes": r["output_bytes"],
        })
    overlap_all_match = all(o["match"] for o in overlap) if overlap else False

    # ---- 分位点（定义域：min(S,T) > 0）----
    ratios = sorted(r["cc64_over_identity"] for r in effective if r["cc64_over_identity"] is not None)
    pct = {}
    if ratios:
        arr = np.array(ratios)
        for method in ("linear", "lower", "nearest_rank"):
            if method == "nearest_rank":
                # 最近秩法：ceil(p*n)-1
                vals = [arr[max(0, int(np.ceil(p / 100 * len(arr))) - 1)] for p in (5, 50, 95)]
            else:
                vals = np.percentile(arr, [5, 50, 95], method=method).round(6).tolist()
            pct[method] = {"P5": vals[0], "P50": vals[1], "P95": vals[2]}

    buckets = {"gap==0": 0, "0<g<=0.01": 0, "0.01<g<=0.05": 0, "0.05<g<=0.10": 0, "g>0.10": 0}
    for r in effective:
        g = r["g"]
        if (r["I"] or 0) == 0:
            continue
        if g == 0:
            buckets["gap==0"] += 1
        elif g <= 0.01:
            buckets["0<g<=0.01"] += 1
        elif g <= 0.05:
            buckets["0.01<g<=0.05"] += 1
        elif g <= 0.10:
            buckets["0.05<g<=0.10"] += 1
        else:
            buckets["g>0.10"] += 1

    tiers: dict[str, list[str]] = {}
    for r in positives:
        key = "T2(含T2b)" if r["tier"] in ("T2", "T2b") else r["tier"]
        tiers.setdefault(key, []).append(r["relative_path"])

    unexplained = sorted(r["relative_path"] for r in positives if r["tier"] in ("T2", "T2b") and r["explanatory_residual"] not in (0, None))
    summary = {
        "ruling": "D-0027/D-0028 五格谓词",
        "n_positive": len(positives), "n_negative": len(negatives),
        "n_effective_no_repeat": len(effective), "n_coordinate_ambiguous": len(ambiguous),
        "negative_with_zero_cc64": sum(1 for r in negatives if r["C"] == 0),
        "negative_files": [r["relative_path"] for r in negatives],
        "tier_counts": {k: len(v) for k, v in sorted(tiers.items())},
        "tier_members": {k: sorted(v) for k, v in sorted(tiers.items())},
        "percentiles_over_min_gt_0": pct,
        "n_ratio_defined": len(ratios),
        "gap_histogram": buckets,
        "sorted_ratios": ratios,
        "baseline_overlap_n": len(overlap),
        "baseline_overlap_all_match": overlap_all_match,
        "unexplained_gap_members": unexplained,  # 空：该字段已作废(D-0036)
        "t2b_gap_threshold_pct": T2B_GAP * 100,
    }

    args.out_dir.mkdir(parents=True, exist_ok=True)
    (args.out_dir / "tiers.json").write_text(json.dumps({"summary": summary, "rows": rows, "baseline_overlap": overlap}, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    fields = ["tier", "relative_path", "pedal_start", "pedal_stop", "unclosed_start", "orphan_stop",
              "inverted_pairs", "C", "I", "g", "gap_pct", "cc64_over_identity",
              "exit_code", "output_bytes", "output_sha256", "source_xml_sha256"]
    with (args.out_dir / "tiers.csv").open("w", encoding="utf-8", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=fields, extrasaction="ignore")
        w.writeheader()
        w.writerows(positives)
    with (args.out_dir / "tiers_effective.csv").open("w", encoding="utf-8", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=fields, extrasaction="ignore"); w.writeheader(); w.writerows(effective)
    with (args.out_dir / "tiers_coordinate_ambiguous.csv").open("w", encoding="utf-8", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=fields, extrasaction="ignore"); w.writeheader(); w.writerows(ambiguous)
    with (args.out_dir / "baseline_overlap.csv").open("w", encoding="utf-8", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=["relative_path", "old_cc64", "new_cc64", "match", "old_output_bytes", "new_output_bytes"], extrasaction="ignore")
        w.writeheader()
        w.writerows(overlap)

    print(json.dumps(summary, indent=2, ensure_ascii=False))
    bad = tiers.get("T1", []) + tiers.get("T4", [])
    if bad:
        print(f"\n!! STOP: T1/T4 非空 = {bad}")
    if not overlap_all_match:
        print("\n!! STOP: 裁定 5 逐值一致未全中")
    return 1 if bad or not overlap_all_match else 0


if __name__ == "__main__":
    raise SystemExit(main())
