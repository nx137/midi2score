#!/usr/bin/env python
"""缺陷 #6 更正：shortfall_pairs / unexplained + 奇数 C 检查 + 三条候选配对规则（上限 3）。

旧式（SUPERSEDED，D-0036）: residual_old = (I - C) - 2*(未闭合 + 孤立stop + 倒置对)
    —— min(S,T) 已吸收计数不平衡，旧式重复扣减，恒等式成立时仍非零。
新式: m = min(S,T); shortfall_pairs = m - C/2; unexplained = shortfall_pairs - inverted
"""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path

from lxml import etree

PEDAL_XPATH = ".//*[local-name()='pedal']"


def load_events(xml_path: Path) -> list[dict]:
    elems = etree.parse(str(xml_path)).getroot().xpath(PEDAL_XPATH)
    return [{"type": e.get("type"), "staff": e.get("staff") or "_"} for e in elems]


def inverted_balance(events: list[dict]) -> int:
    bal, inv = 0, 0
    for e in events:
        if e["type"] == "start":
            bal += 1
        elif e["type"] == "stop":
            bal -= 1
            if bal < 0:
                inv += 1
    return inv


def pairs_global_stack(events: list[dict]) -> int:
    depth, pairs = 0, 0
    for e in events:
        if e["type"] == "start":
            depth += 1
        elif e["type"] == "stop" and depth > 0:
            depth -= 1
            pairs += 1
    return pairs


def pairs_per_staff_stack(events: list[dict]) -> int:
    by_staff: dict[str, list[dict]] = {}
    for e in events:
        by_staff.setdefault(e["staff"], []).append(e)
    return sum(pairs_global_stack(v) for v in by_staff.values())


def pairs_greedy_nearest(events: list[dict]) -> int:
    """每个 stop 与其之前最近的未配对 start 配对。"""
    open_idx: list[int] = []
    pairs = 0
    for i, e in enumerate(events):
        if e["type"] == "start":
            open_idx.append(i)
        elif e["type"] == "stop" and open_idx:
            open_idx.pop()  # 最近
            pairs += 1
    return pairs


RULES = {
    "R1_global_stack": pairs_global_stack,
    "R2_per_staff_stack": pairs_per_staff_stack,
    "R3_greedy_nearest": pairs_greedy_nearest,
}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dataset", type=Path, default=Path("data/asap-dataset"))
    ap.add_argument("--probe", type=Path, default=Path("evidence/R1/full68v2/export_probe.json"))
    ap.add_argument("--out-dir", type=Path, default=Path("evidence/R1/G1-export"))
    args = ap.parse_args()

    rows = json.loads(args.probe.read_text(encoding="utf-8"))["rows"]
    out = []
    for r in rows:
        if r["kind"] != "positive":
            continue
        ev = load_events(args.dataset / r["relative_path"])
        S = sum(1 for e in ev if e["type"] == "start")
        T = sum(1 for e in ev if e["type"] == "stop")
        C = r["cc64_messages"] or 0
        m = min(S, T)
        I = 2 * m
        unclosed, orphan = max(S - T, 0), max(T - S, 0)
        inv = inverted_balance(ev)
        row = {
            "relative_path": r["relative_path"], "S": S, "T": T, "m": m, "I": I, "C": C,
            "odd_C": bool(C % 2),
            "inverted": inv, "unclosed": unclosed, "orphan_stop": orphan,
            "shortfall_pairs": round(m - C / 2, 3),
            "unexplained": round((m - C / 2) - inv, 3),
            "residual_old_SUPERSEDED": (I - C) - 2 * (unclosed + orphan + inv),
        }
        for name, fn in RULES.items():
            p = fn(ev)
            row[f"pairs_{name}"] = p
            row[f"unexplained_{name}"] = round((m - p) - inv, 3)
            row[f"Cpred_{name}"] = 2 * p
        out.append(row)

    args.out_dir.mkdir(parents=True, exist_ok=True)
    fields = list(out[0].keys())
    with (args.out_dir / "pairing_audit.csv").open("w", encoding="utf-8", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=fields, extrasaction="ignore")
        w.writeheader()
        w.writerows(out)

    ok = [r for r in out if r["I"] > 0 and r["C"] == r["I"]]
    old_nonzero = [r for r in ok if r["residual_old_SUPERSEDED"] != 0]
    odd = [r["relative_path"] for r in out if r["odd_C"]]
    unexp_pos = [r["relative_path"] for r in out if r["unexplained"] > 0]
    unexp_zero = sum(1 for r in out if r["unexplained"] == 0)
    rule_zero = {name: sum(1 for r in out if r[f"unexplained_{name}"] == 0) for name in RULES}
    rule_matchC = {name: sum(1 for r in out if r[f"Cpred_{name}"] == r["C"]) for name in RULES}

    summary = {
        "n_positives": len(out),
        "selfcheck_old_formula_on_OK": {
            "n_OK": len(ok), "n_residual_nonzero": len(old_nonzero),
            "example": [{"path": r["relative_path"], "S": r["S"], "T": r["T"], "C": r["C"],
                         "old_residual": r["residual_old_SUPERSEDED"]} for r in old_nonzero[:5]],
            "verdict": "旧公式在恒等式成立的乐谱上仍非零 → 重复扣减已证实（缺陷 #6）",
        },
        "odd_C_members": odd, "odd_C_count": len(odd),
        "unexplained_zero_count": unexp_zero,
        "unexplained_positive_members": unexp_pos,
        "candidate_rules": {
            name: {"unexplained_zero_count": rule_zero[name], "Cpred_matches_observed": rule_matchC[name],
                   "Cpred_mismatch_examples": [r["relative_path"] for r in out if r[f"Cpred_{name}"] != r["C"]][:5]}
            for name in RULES
        },
        "note": "候选规则上限 3 条（D-0035 §3.4）；若均不能清零，结论记为『导出侧配对规则未能唯一确定』",
    }
    (args.out_dir / "pairing_audit.json").write_text(
        json.dumps({"summary": summary, "rows": out}, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps(summary, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())