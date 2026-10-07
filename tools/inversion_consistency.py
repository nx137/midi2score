#!/usr/bin/env python
"""交付 5：反演一致度（CC64 二值区间 → 锚点标签 vs 印刷记号）。

坐标：展开坐标由 nASAP 对齐直接给出（xml_id 形如 n12-1，后缀 = playthrough 序号），不展开 MusicXML。
比较完全在锚点栅格（谱面时间）上：CC64 时间 --分段线性--> (measure,offset,playthrough) --吸附--> 锚点。
工具参数、schema、路径均属执行端可自定范围（D-0044）。
"""

from __future__ import annotations

import argparse
import csv
import json
import re
from collections import Counter, defaultdict
from pathlib import Path

import mido
import numpy as np
from scipy.optimize import linear_sum_assignment
from lxml import etree

GRID = 0.25  # 十六分音符，单位 = 四分音符
BASE_RE = re.compile(r"^(?P<base>.+?)(?:-(?P<rep>\d+))?$")
ON_THRESHOLD = 64  # 冻结：v>=64 -> ON (D-0030)


def find1(el, tag):
    r = el.xpath(f".//*[local-name()='{tag}']")
    return r[0] if r else None


def parse_score(xml_path: Path) -> tuple[dict[str, tuple[int, float]], list[tuple[int, float, str]]]:
    root = etree.parse(str(xml_path)).getroot()
    divisions = 1.0
    notes: dict[str, tuple[int, float]] = {}
    pedals: list[tuple[int, float, str]] = []
    measure_start = 0.0
    for mi, measure in enumerate(root.xpath(".//*[local-name()='measure']")):
        pos = 0.0
        max_pos = 0.0
        for el in measure.iter():
            tag = etree.QName(el).localname
            if tag == "divisions":
                divisions = float(el.text or 1)
            elif tag == "backup":
                d = find1(el, "duration")
                if d is not None and d.text:
                    pos -= float(d.text) / divisions
            elif tag == "forward":
                d = find1(el, "duration")
                if d is not None and d.text:
                    pos += float(d.text) / divisions
            elif tag == "note":
                nid = el.get("id")
                dur = find1(el, "duration")
                if nid:
                    notes[nid] = (mi, pos)
                if find1(el, "chord") is None and dur is not None and dur.text:
                    pos += float(dur.text) / divisions
            elif tag == "direction":
                p = find1(el, "pedal")
                if p is not None and p.get("type") in ("start", "stop"):
                    pedals.append((mi, pos, p.get("type")))
    return notes, pedals


def parse_alignment(tsv_path: Path) -> list[tuple[str, int, float]]:
    rows = []
    with tsv_path.open(encoding="utf-8-sig", newline="") as fh:
        for row in csv.DictReader(fh, delimiter="\t"):
            if not row.get("xml_id") or not row.get("onset"):
                continue
            m = BASE_RE.match(row["xml_id"])
            if not m:
                continue
            rows.append((m.group("base"), int(m.group("rep") or 1), float(row["onset"])))
    return rows


def cc64_transitions(mid_path: Path) -> list[tuple[float, str]]:
    mid = mido.MidiFile(str(mid_path))
    t = 0.0
    state = 0
    out = []
    for msg in mid:
        t += msg.time
        if msg.type == "control_change" and msg.control == 64:
            new = 1 if msg.value >= ON_THRESHOLD else 0
            if new != state:
                out.append((t, "start" if new else "stop"))
                state = new
    return out


def snap(v: float) -> float:
    return round(v / GRID) * GRID


def to_anchor(t: float, seq: list[tuple[float, float]], layers: list[int]) -> tuple[int, float] | None:
    """seq = sorted [(onset, written_position_in_quarters)]（已按 onset 单调）; layers 只用于记录。"""
    if not seq:
        return None
    if t <= seq[0][0]:
        return seq[0][1], 0.0
    if t >= seq[-1][0]:
        return seq[-1][1], 0.0
    lo, hi = 0, len(seq) - 1
    while hi - lo > 1:
        mid = (lo + hi) // 2
        if seq[mid][0] <= t:
            lo = mid
        else:
            hi = mid
    t0, p0 = seq[lo]
    t1, p1 = seq[hi]
    if t1 == t0:
        return p1, 0.0
    return p0 + (p1 - p0) * (t - t0) / (t1 - t0), 0.0


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dataset", type=Path, default=Path("data/asap-dataset"))
    ap.add_argument("--split", type=Path, default=Path("evidence/R1/G1-split/split_v1.json"))
    ap.add_argument("--out-dir", type=Path, default=Path("evidence/R1/G1-inversion"))
    ap.add_argument("--limit", type=int, default=0, help="0 = 全量")
    ap.add_argument("--tolerances", default="0,1,2", help="拍")
    args = ap.parse_args()

    ds = args.dataset
    split = json.loads(args.split.read_text(encoding="utf-8"))
    main_scores = set(split["main_scores"])
    repeat_scores = {s for s in main_scores
                     if etree.parse(str(ds / s)).getroot().xpath(".//*[local-name()='repeat']")}
    perf_rows = [p for p in split["per_performance"]
                 if p["xml_score"] in main_scores and p["xml_score"] not in repeat_scores]
    print(f"范围 = Main {len(main_scores)} 首中不含 repeat 的 {len(main_scores - repeat_scores)} 首（D-0045 坐标无歧义范围）")

    score_notes: dict[str, dict[str, tuple[int, float]]] = {}
    score_pedals: dict[str, list[tuple[int, float, str]]] = {}
    perfs = []
    for p in perf_rows:
        xml = p["xml_score"]
        if xml not in score_notes:
            try:
                score_notes[xml], score_pedals[xml] = parse_score(ds / xml)
            except Exception:
                score_notes[xml], score_pedals[xml] = {}, []
        align = ds / p["alignment_path"] if p["alignment_path"] else None
        midi = ds / p["midi_performance"]
        if align and align.is_file() and midi.is_file():
            perfs.append((p, align, midi))
    if args.limit:
        perfs = perfs[: args.limit]
    print(f"可用 (score, performance) 对 = {len(perfs)}")

    tols = [int(x) for x in args.tolerances.split(",")]
    results = []
    for p, align, midi in perfs:
        xml = p["xml_score"]
        notes, pedals = score_notes[xml], score_pedals[xml]
        al = parse_alignment(align)
        seq = sorted((onset, notes[base]) for base, rep, onset in al if base in notes)
        seq = [(t, pos[1]) for t, pos in seq]  # notes[base] = (measure, global_pos) -> 取 global_pos
        if len(seq) < 2:
            continue
        # 印刷记号（书写坐标 × 出现的 playthrough）
        reps = sorted({rep for _, rep, _ in al})
        truth = {(snap(o), ("DOWN" if k == "start" else "UP")) for (m, o, k) in pedals}
        pred = set()
        for t, kind in cc64_transitions(midi):
            got = to_anchor(t, seq, [])
            if got is None:
                continue
            pos, _ = got
            pred.add((snap(pos), "DOWN" if kind == "start" else "UP"))
        row = {"score": xml, "performance": p["midi_performance"],
               "n_truth": len(truth), "n_pred": len(pred)}
        pred_l, truth_l = sorted(pred), sorted(truth)
        for tol in tols:
            tp = 0
            matched_pred, matched_truth = set(), set()
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
                        matched_pred.add(pi[a])
                        matched_truth.add(ti[b])
            wrong = 0
            if tol > 0:
                for i, (pos, lab) in enumerate(pred_l):
                    if i in matched_pred:
                        continue
                    for j, (tpos, tlab) in enumerate(truth_l):
                        if j in matched_truth or tlab == lab:
                            continue
                        if abs(pos - tpos) <= tol:
                            wrong += 1
                            break
            fp = len(pred_l) - len(matched_pred)
            fn = len(truth_l) - len(matched_truth)
            prec = tp / (tp + fp + wrong) if (tp + fp + wrong) else 0.0
            rec = tp / (tp + fn) if (tp + fn) else 0.0
            f1 = 2 * prec * rec / (prec + rec) if (prec + rec) else 0.0
            row[f"tol{tol}"] = {"tp": tp, "fp": fp, "fn": fn, "wrong": wrong,
                                "P": round(prec, 4), "R": round(rec, 4), "F1": round(f1, 4)}
        results.append(row)

    args.out_dir.mkdir(parents=True, exist_ok=True)
    (args.out_dir / "inversion_runs.json").write_text(json.dumps(results, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    for tol in tols:
        vals = [r[f"tol{tol}"]["F1"] for r in results]
        print(f"tol ±{tol}拍: n={len(vals)} microF1={sum(vals)/len(vals) if vals else 0:.4f}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())