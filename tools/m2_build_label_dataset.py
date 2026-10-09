#!/usr/bin/env python
"""M2：构建 ASAP Main 的 canonical 逐锚点标签数据集（v1）。

交付：
- data/derived/m2/score_labels.jsonl.gz
- data/derived/m2/run_masks.jsonl.gz
- data/derived/m2/m2_excluded_anchors.jsonl.gz
- results/E1/m2/m2_summary.json/.md
- results/E1/m2/m2_scores.csv
- results/E1/m2/m2_folds.csv
- results/E1/m2/m2_table1.csv/.md
- results/E1/m2/m2_label_schema.json
- results/E1/m2/m2_manifest.json

冻结口径（见 TASK_CHARTER.md HC-01/08/11/13 与 PedNotate_Plan_v3.0.md §1.1）：
- 锚点 = canonical [0, score_end] 栅格，GRID=0.25，含无音符格点。
- DOWN/UP 来自 MusicXML <pedal type="start|stop">。
- CHANGE = 文档顺序中紧邻的 stop -> start，且间隔 0 <= gap < 1 拍；
  归到 start 锚点，并消费该对端点，避免同时输出 UP+DOWN。
- repeat 谱保留标签，但标 coordinate_ambiguous 且 supervision_mask=0；
  M2 v1 不声称已经完成 repeat 展开坐标。
- 同一锚点若残留 start/stop 两类事件且无法由 CHANGE 唯一表示，
  label_status=ambiguous_multi_event、supervision_mask=0；审计行单独落盘。
"""
from __future__ import annotations

import argparse
import csv
import gzip
import hashlib
import io
import json
import platform
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

from lxml import etree

sys.path.insert(0, str(Path(__file__).resolve().parent))
from canonical_domain import GRID, canonical_anchors, score_end  # noqa: E402
from inversion_consistency import parse_score, snap  # noqa: E402

DATASET_VERSION = "m2-v1"
LABELS = ("NONE", "DOWN", "UP", "CHANGE")
CHANGE_MERGE_BEATS = 1.0
REPO_ROOT = Path(__file__).resolve().parents[1]


def sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def sha256_text(text: str) -> str:
    return sha256_bytes(text.encode("utf-8"))


def sha256_file(path: Path) -> str:
    return sha256_bytes(path.read_bytes())


def relpath(path: Path) -> str:
    try:
        return path.resolve().relative_to(REPO_ROOT.resolve()).as_posix()
    except ValueError:
        return str(path.resolve())


def normalize_rel(value: str | None) -> str:
    return (value or "").replace("\\", "/")


def json_dump(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def write_jsonl_gz(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = "".join(
        json.dumps(row, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n"
        for row in rows
    ).encode("utf-8")
    with path.open("wb") as raw:
        with gzip.GzipFile(filename="", fileobj=raw, mode="wb", mtime=0) as out:
            out.write(payload)


def write_csv(path: Path, rows: list[dict[str, Any]], fields: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=fields, lineterminator="\n")
        writer.writeheader()
        for row in rows:
            writer.writerow({field: row.get(field) for field in fields})


def has_repeat(xml_path: Path) -> bool:
    return bool(etree.parse(str(xml_path)).getroot().xpath(".//*[local-name()='repeat']"))


def score_has_pedal(xml_path: Path) -> bool:
    return bool(etree.parse(str(xml_path)).getroot().xpath(".//*[local-name()='pedal']"))


def assignment_sha256(split: dict[str, Any]) -> tuple[str, int, int]:
    """复现 split_assignment_hash.py 的冻结身份；不写入新内容。"""
    meta = split["score_meta"]
    rows = []
    for perf in split["per_performance"]:
        score = perf["xml_score"]
        rows.append({
            "piecegroup": meta[score]["group"],
            "performanceid": perf["midi_performance"],
            "fold": perf["fold"],
        })
    rows.sort(key=lambda row: (row["piecegroup"], row["performanceid"]))
    buf = io.StringIO(newline="")
    writer = csv.DictWriter(
        buf,
        fieldnames=["piecegroup", "performanceid", "fold"],
        lineterminator="\r\n",
    )
    writer.writeheader()
    writer.writerows(rows)
    payload = buf.getvalue().encode("utf-8")
    return sha256_bytes(payload), len(rows), len({row["piecegroup"] for row in rows})


def derive_change_pairs(pedals: list[tuple[int, float, str]]) -> tuple[list[dict[str, Any]], set[int]]:
    """按文档顺序（相同位置保留文档顺序）消费 stop -> start 对。"""
    events = sorted(enumerate(pedals), key=lambda item: (float(item[1][1]), item[0]))
    pairs: list[dict[str, Any]] = []
    consumed: set[int] = set()
    index = 0
    while index + 1 < len(events):
        left_index, left = events[index]
        right_index, right = events[index + 1]
        left_measure, left_pos, left_kind = left
        right_measure, right_pos, right_kind = right
        gap = float(right_pos) - float(left_pos)
        if left_kind == "stop" and right_kind == "start" and 0.0 <= gap < CHANGE_MERGE_BEATS:
            pairs.append({
                "stop_index": int(left_index),
                "start_index": int(right_index),
                "stop_measure": int(left_measure),
                "start_measure": int(right_measure),
                "stop_pos": round(float(left_pos), 6),
                "start_pos": round(float(right_pos), 6),
                "stop_anchor": snap(float(left_pos)),
                "start_anchor": snap(float(right_pos)),
                "anchor": snap(float(right_pos)),
                "gap_beats": round(gap, 6),
            })
            consumed.add(int(left_index))
            consumed.add(int(right_index))
            index += 2
            continue
        index += 1
    return pairs, consumed


def build_score_rows(xml_path: Path, eval_eligible: bool) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    end = score_end(xml_path)
    anchors = canonical_anchors(end)
    anchor_set = set(anchors)
    _, pedals = parse_score(xml_path)
    all_pairs, _ = derive_change_pairs(pedals)
    pairs = [
        pair for pair in all_pairs
        if pair["stop_anchor"] in anchor_set and pair["start_anchor"] in anchor_set
    ]
    consumed = {
        int(index)
        for pair in pairs
        for index in (pair["stop_index"], pair["start_index"])
    }

    raw_by_anchor: dict[float, list[dict[str, Any]]] = defaultdict(list)
    outside: list[dict[str, Any]] = []
    for index, (measure, pos, kind) in enumerate(pedals):
        anchor = snap(float(pos))
        if anchor not in anchor_set:
            outside.append({
                "index": index,
                "measure": int(measure),
                "pos": round(float(pos), 6),
                "anchor": anchor,
                "kind": "DOWN" if kind == "start" else "UP",
            })
            continue
        raw_by_anchor[anchor].append({
            "index": index,
            "measure": int(measure),
            "pos": round(float(pos), 6),
            "kind": kind,
        })

    remaining_by_anchor: dict[float, list[dict[str, Any]]] = defaultdict(list)
    for anchor, items in raw_by_anchor.items():
        for item in items:
            if item["index"] not in consumed:
                remaining_by_anchor[anchor].append(item)

    change_at: dict[float, list[dict[str, Any]]] = defaultdict(list)
    for pair in pairs:
        change_at[pair["start_anchor"]].append(pair)

    rows: list[dict[str, Any]] = []
    for anchor in anchors:
        original_items = raw_by_anchor.get(anchor, [])
        remaining_items = remaining_by_anchor.get(anchor, [])
        original_kinds = [item["kind"] for item in original_items]
        remaining_kinds = [item["kind"] for item in remaining_items]
        has_change = bool(change_at.get(anchor))
        if has_change:
            label = "CHANGE"
            status = "ok" if len(set(remaining_kinds)) <= 1 else "ambiguous_multi_event"
        elif not remaining_kinds:
            label = "NONE"
            status = "ok"
        elif len(set(remaining_kinds)) == 1:
            label = "DOWN" if remaining_kinds[0] == "start" else "UP"
            status = "ok"
        else:
            label = "DOWN" if remaining_kinds[0] == "start" else "UP"
            status = "ambiguous_multi_event"
        rows.append({
            "anchor": anchor,
            "label": label,
            "label_status": status,
            "raw_DOWN": "start" in original_kinds,
            "raw_UP": "stop" in original_kinds,
            "raw_types": [
                "DOWN" if item["kind"] == "start" else "UP"
                for item in original_items
            ],
            "remaining_DOWN": "start" in remaining_kinds,
            "remaining_UP": "stop" in remaining_kinds,
            "change_pair_count": len(change_at.get(anchor, [])),
            "supervision_mask": 1 if eval_eligible and status == "ok" else 0,
        })

    meta = {
        "score_end": round(float(end), 6),
        "n_anchors": len(anchors),
        "n_pedal_elements": len(pedals),
        "n_raw_DOWN": sum(1 for _, _, kind in pedals if kind == "start"),
        "n_raw_UP": sum(1 for _, _, kind in pedals if kind == "stop"),
        "n_change_pairs": len(pairs),
        "n_truth_outside_canonical": len(outside),
        "truth_outside_canonical": outside,
        "n_ambiguous_anchors": sum(1 for row in rows if row["label_status"] != "ok"),
        "n_supervised_anchors": sum(int(row["supervision_mask"]) for row in rows),
    }
    return rows, meta


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dataset", type=Path, required=True)
    ap.add_argument("--split", type=Path, required=True)
    ap.add_argument("--out-dir", type=Path, required=True)
    ap.add_argument("--data-out", type=Path, required=True)
    args = ap.parse_args()

    dataset = args.dataset.resolve()
    split_path = args.split.resolve()
    out_dir = args.out_dir.resolve()
    data_out = args.data_out.resolve()
    split = json.loads(split_path.read_text(encoding="utf-8"))
    main_scores = sorted(set(split["main_scores"]))
    main_set = set(main_scores)
    score_meta = split["score_meta"]
    fold_by_score: dict[str, str] = {}
    for perf in split["per_performance"]:
        fold_by_score.setdefault(perf["xml_score"], perf["fold"])

    label_rows: list[dict[str, Any]] = []
    excluded_rows: list[dict[str, Any]] = []
    score_table: list[dict[str, Any]] = []
    repeat_scores: list[str] = []
    outside_total = 0
    for score in main_scores:
        xml_path = dataset / score
        repeat = has_repeat(xml_path)
        if repeat:
            repeat_scores.append(score)
        rows, meta = build_score_rows(xml_path, eval_eligible=not repeat)
        eligible = not repeat and meta["n_truth_outside_canonical"] == 0
        outside_total += meta["n_truth_outside_canonical"]
        label_counts = Counter(row["label"] for row in rows)
        supervised_counts = Counter(
            row["label"] for row in rows if int(row["supervision_mask"]) == 1
        )
        for row in rows:
            row.update({
                "score": score,
                "composer": score_meta[score].get("composer"),
                "group": score_meta[score].get("group"),
                "fold": fold_by_score.get(score),
                "coordinate_ambiguous": repeat,
                "evaluation_eligible": eligible,
            })
            if row["label_status"] != "ok":
                excluded_rows.append(dict(row))
            label_rows.append(row)
        score_table.append({
            "score": score,
            "composer": score_meta[score].get("composer"),
            "title": score_meta[score].get("title"),
            "group": score_meta[score].get("group"),
            "fold": fold_by_score.get(score),
            "coordinate_ambiguous": repeat,
            "evaluation_eligible": eligible,
            **meta,
            **{f"n_label_{label}": label_counts.get(label, 0) for label in LABELS},
            **{f"n_supervised_{label}": supervised_counts.get(label, 0) for label in LABELS},
        })

    metadata_path = dataset / "metadata.csv"
    run_rows: list[dict[str, Any]] = []
    hash_cache: dict[str, str] = {}
    pedal_cache: dict[str, bool] = {}
    repeat_cache: dict[str, bool] = {}
    outside_by_score = {row["score"]: int(row["n_truth_outside_canonical"]) for row in score_table}

    def cached_hash(path: Path) -> str:
        key = str(path.resolve())
        if key not in hash_cache:
            hash_cache[key] = sha256_file(path)
        return hash_cache[key]

    def cached_pedal(score: str) -> bool:
        if score not in pedal_cache:
            pedal_cache[score] = score_has_pedal(dataset / score)
        return pedal_cache[score]

    def cached_repeat(score: str) -> bool:
        if score not in repeat_cache:
            repeat_cache[score] = has_repeat(dataset / score)
        return repeat_cache[score]

    with metadata_path.open(encoding="utf-8-sig", newline="") as fh:
        for meta_row in csv.DictReader(fh):
            score = normalize_rel(meta_row.get("xml_score"))
            midi = normalize_rel(meta_row.get("midi_performance"))
            if not score or not midi:
                continue
            score_path = dataset / score
            midi_path = dataset / midi
            align_rel = normalize_rel(meta_row.get("note_alignments"))
            align_path = dataset / align_rel if align_rel else None
            main_membership = score in main_set
            has_midi = midi_path.is_file()
            has_alignment = bool(align_path and align_path.is_file())
            has_pedal = cached_pedal(score) if score_path.is_file() else False
            coordinate_ambiguous = cached_repeat(score) if score_path.is_file() else False
            eligible = (
                main_membership
                and has_pedal
                and not coordinate_ambiguous
                and has_alignment
                and has_midi
                and outside_by_score.get(score, 0) == 0
            )
            run_rows.append({
                "run_id": sha256_text(score + "|" + midi)[:16],
                "score": score,
                "midi_performance": midi,
                "fold": fold_by_score.get(score),
                "mask": 1 if main_membership else 0,
                "main_membership": main_membership,
                "reference_available": has_pedal,
                "coordinate_ambiguous": coordinate_ambiguous,
                "evaluation_eligible": eligible,
                "supervision_mask": 1 if eligible else 0,
                "has_alignment": has_alignment,
                "has_midi": has_midi,
                "has_pedal": has_pedal,
                "source_score_sha256": cached_hash(score_path) if score_path.is_file() else None,
                "source_midi_sha256": cached_hash(midi_path) if has_midi else None,
                "source_alignment_sha256": cached_hash(align_path) if has_alignment and align_path else None,
            })

    truth_by_score: dict[str, int] = {}
    for score in main_scores:
        if score in repeat_scores:
            continue
        xml_path = dataset / score
        _, pedals = parse_score(xml_path)
        anchors = set(canonical_anchors(score_end(xml_path)))
        truth_by_score[score] = len({
            (snap(float(pos)), "DOWN" if kind == "start" else "UP")
            for _, pos, kind in pedals
            if snap(float(pos)) in anchors
        })
    run_fold = Counter()
    truth_fold = Counter()
    for row in run_rows:
        if row["fold"]:
            run_fold[row["fold"]] += 1
        if int(row["supervision_mask"]) == 1:
            truth_fold[row["fold"]] += truth_by_score.get(row["score"], 0)
    truth_fold["full"] = sum(truth_fold.values())

    label_counts = Counter(row["label"] for row in label_rows)
    supervised_label_counts = Counter(
        row["label"] for row in label_rows if int(row["supervision_mask"]) == 1
    )
    summary = {
        "dataset_version": DATASET_VERSION,
        "canonical_domain": "[0, score_end]",
        "grid": GRID,
        "change_merge_beats": CHANGE_MERGE_BEATS,
        "change_anchor_rule": "CHANGE is assigned to the start (DOWN) anchor; the paired stop is consumed",
        "main_scores": len(main_scores),
        "evaluation_eligible_scores": sum(1 for row in score_table if row["evaluation_eligible"]),
        "coordinate_ambiguous_scores": len(repeat_scores),
        "coordinate_ambiguous_score_list": repeat_scores,
        "label_rows": len(label_rows),
        "supervised_label_rows": sum(int(row["supervision_mask"]) for row in label_rows),
        "ambiguous_label_rows": len(excluded_rows),
        "label_counts": {label: label_counts.get(label, 0) for label in LABELS},
        "supervised_label_counts": {label: supervised_label_counts.get(label, 0) for label in LABELS},
        "raw_pedal_elements": sum(row["n_pedal_elements"] for row in score_table),
        "raw_DOWN": sum(row["n_raw_DOWN"] for row in score_table),
        "raw_UP": sum(row["n_raw_UP"] for row in score_table),
        "change_pairs": sum(row["n_change_pairs"] for row in score_table),
        "truth_outside_canonical": outside_total,
        "run_rows": len(run_rows),
        "main_runs": sum(int(row["mask"]) for row in run_rows),
        "evaluation_domain_runs": sum(int(row["evaluation_eligible"]) for row in run_rows),
        "supervised_runs": sum(int(row["supervision_mask"]) for row in run_rows),
        "non_main_runs": sum(1 for row in run_rows if not row["main_membership"]),
        "no_pedal_run_rows": sum(1 for row in run_rows if not row["has_pedal"]),
        "run_fold_counts": {key: run_fold.get(key, 0) for key in ("train", "val", "test")},
        "canonical_truth_elements_full": truth_fold.get("full", 0),
        "canonical_truth_elements_train": truth_fold.get("train", 0),
        "canonical_truth_elements_val": truth_fold.get("val", 0),
        "canonical_truth_elements_test": truth_fold.get("test", 0),
        "generator_sha256": sha256_file(Path(__file__).resolve()),
    }

    if summary["main_scores"] != 43:
        raise SystemExit(f"main_scores mismatch: {summary['main_scores']}")
    if summary["evaluation_eligible_scores"] != 36:
        raise SystemExit(f"evaluation_eligible_scores mismatch: {summary['evaluation_eligible_scores']}")
    if summary["coordinate_ambiguous_scores"] != 7:
        raise SystemExit(f"coordinate_ambiguous_scores mismatch: {summary['coordinate_ambiguous_scores']}")
    if summary["main_runs"] != 291:
        raise SystemExit(f"main_runs mismatch: {summary['main_runs']}")
    if summary["evaluation_domain_runs"] != 271:
        raise SystemExit(f"evaluation_domain_runs mismatch: {summary['evaluation_domain_runs']}")
    if summary["raw_pedal_elements"] != 3840:
        raise SystemExit(f"raw_pedal_elements mismatch: {summary['raw_pedal_elements']}")
    if summary["canonical_truth_elements_full"] != 28603:
        raise SystemExit(f"canonical truth full mismatch: {summary['canonical_truth_elements_full']}")
    if summary["canonical_truth_elements_test"] != 16278:
        raise SystemExit(f"canonical truth test mismatch: {summary['canonical_truth_elements_test']}")

    data_out.mkdir(parents=True, exist_ok=True)
    out_dir.mkdir(parents=True, exist_ok=True)
    labels_path = data_out / "score_labels.jsonl.gz"
    runs_path = data_out / "run_masks.jsonl.gz"
    excluded_path = data_out / "m2_excluded_anchors.jsonl.gz"
    write_jsonl_gz(labels_path, label_rows)
    write_jsonl_gz(runs_path, run_rows)
    write_jsonl_gz(excluded_path, excluded_rows)

    score_rows_out = []
    for score in main_scores:
        score_row = next(row for row in score_table if row["score"] == score)
        score_rows_out.append({key: score_row.get(key) for key in (
            "score", "composer", "title", "group", "fold", "coordinate_ambiguous",
            "evaluation_eligible", "score_end", "n_anchors", "n_pedal_elements",
            "n_raw_DOWN", "n_raw_UP", "n_change_pairs", "n_truth_outside_canonical",
            "n_ambiguous_anchors", "n_supervised_anchors", "n_label_NONE",
            "n_label_DOWN", "n_label_UP", "n_label_CHANGE", "n_supervised_NONE",
            "n_supervised_DOWN", "n_supervised_UP", "n_supervised_CHANGE",
        )})
    score_fields = list(score_rows_out[0].keys())
    scores_csv = out_dir / "m2_scores.csv"
    write_csv(scores_csv, score_rows_out, score_fields)

    fold_rows = []
    for fold in ("train", "val", "test"):
        label_subset = [row for row in label_rows if int(row["supervision_mask"]) == 1 and row["fold"] == fold]
        fold_rows.append({
            "fold": fold,
            "runs": run_fold.get(fold, 0),
            "supervised_runs": sum(1 for row in run_rows if row["fold"] == fold and int(row["supervision_mask"]) == 1),
            "canonical_truth_elements": truth_fold.get(fold, 0),
            "supervised_label_rows": len(label_subset),
            "label_NONE": sum(1 for row in label_subset if row["label"] == "NONE"),
            "label_DOWN": sum(1 for row in label_subset if row["label"] == "DOWN"),
            "label_UP": sum(1 for row in label_subset if row["label"] == "UP"),
            "label_CHANGE": sum(1 for row in label_subset if row["label"] == "CHANGE"),
        })
    folds_csv = out_dir / "m2_folds.csv"
    write_csv(folds_csv, fold_rows, list(fold_rows[0].keys()))

    table1_rows = [
        {"section": "corpus", "metric": "all MusicXML scores", "value": len(sorted(dataset.rglob("*.musicxml")))},
        {"section": "corpus", "metric": "scores with printed pedal", "value": sum(1 for p in dataset.rglob("*.musicxml") if score_has_pedal(p))},
        {"section": "corpus", "metric": "raw pedal elements", "value": summary["raw_pedal_elements"]},
        {"section": "main", "metric": "Main scores", "value": summary["main_scores"]},
        {"section": "main", "metric": "Main runs", "value": summary["main_runs"]},
        {"section": "main", "metric": "evaluation-eligible scores", "value": summary["evaluation_eligible_scores"]},
        {"section": "main", "metric": "evaluation-domain runs", "value": summary["evaluation_domain_runs"]},
        {"section": "main", "metric": "supervised runs", "value": summary["supervised_runs"]},
        {"section": "main", "metric": "coordinate-ambiguous scores", "value": summary["coordinate_ambiguous_scores"]},
        {"section": "labels", "metric": "label rows", "value": summary["label_rows"]},
        {"section": "labels", "metric": "supervised label rows", "value": summary["supervised_label_rows"]},
        {"section": "labels", "metric": "ambiguous label rows", "value": summary["ambiguous_label_rows"]},
        {"section": "labels", "metric": "NONE", "value": summary["label_counts"]["NONE"]},
        {"section": "labels", "metric": "DOWN", "value": summary["label_counts"]["DOWN"]},
        {"section": "labels", "metric": "UP", "value": summary["label_counts"]["UP"]},
        {"section": "labels", "metric": "CHANGE", "value": summary["label_counts"]["CHANGE"]},
        {"section": "truth", "metric": "canonical truth elements full", "value": summary["canonical_truth_elements_full"]},
        {"section": "truth", "metric": "canonical truth elements test", "value": summary["canonical_truth_elements_test"]},
    ]
    table1_csv = out_dir / "m2_table1.csv"
    write_csv(table1_csv, table1_rows, ["section", "metric", "value"])
    table1_md = out_dir / "m2_table1.md"
    lines = ["# M2 Table 1", "", "| section | metric | value |", "|:--|:--|--:|"]
    lines.extend(f"| {row['section']} | {row['metric']} | {row['value']} |" for row in table1_rows)
    table1_md.write_text("\n".join(lines) + "\n", encoding="utf-8")

    summary_json = out_dir / "m2_summary.json"
    summary_md = out_dir / "m2_summary.md"
    json_dump(summary_json, summary)
    md = [
        "# M2 canonical 标签数据集",
        "",
        f"- Version: {DATASET_VERSION}",
        f"- Main scores: {summary['main_scores']}",
        f"- Evaluation-eligible scores: {summary['evaluation_eligible_scores']}",
        f"- Coordinate-ambiguous scores: {summary['coordinate_ambiguous_scores']}",
        f"- Main runs: {summary['main_runs']}",
        f"- Evaluation-domain runs: {summary['evaluation_domain_runs']}",
        f"- Supervised runs: {summary['supervised_runs']}",
        f"- Label rows: {summary['label_rows']}",
        f"- Supervised label rows: {summary['supervised_label_rows']}",
        f"- Ambiguous label rows: {summary['ambiguous_label_rows']}",
        f"- Raw pedal elements: {summary['raw_pedal_elements']}",
        f"- Raw DOWN: {summary['raw_DOWN']}",
        f"- Raw UP: {summary['raw_UP']}",
        f"- Derived CHANGE pairs: {summary['change_pairs']}",
        f"- Canonical truth elements full: {summary['canonical_truth_elements_full']}",
        f"- Canonical truth elements test: {summary['canonical_truth_elements_test']}",
        "",
        "## Label counts (all emitted rows)",
        "",
        "| label | anchors |",
        "|:--|--:|",
    ]
    md.extend(f"| {label} | {summary['label_counts'][label]} |" for label in LABELS)
    md.extend([
        "",
        "## Label counts (supervision_mask=1)",
        "",
        "| label | anchors |",
        "|:--|--:|",
    ])
    md.extend(f"| {label} | {summary['supervised_label_counts'][label]} |" for label in LABELS)
    md.extend([
        "",
        "## Boundary notes",
        "",
        "- `mask` is the Main 43 membership marker: Main runs = 1, all other runs = 0.",
        "- `supervision_mask` is the M2 v1 loss mask: 1 only for Main, non-repeat, printed-pedal, alignment+MIDI available runs.",
        "- The 7 repeat scores remain in the label audit but are `coordinate_ambiguous` and have `supervision_mask=0` until repeat unfolding is implemented.",
        "- Residual same-anchor mixed events are emitted with a valid 4-class label, `label_status=ambiguous_multi_event`, and `supervision_mask=0`.",
    ])
    summary_md.write_text("\n".join(md) + "\n", encoding="utf-8")

    schema = {
        "dataset_version": DATASET_VERSION,
        "labels": list(LABELS),
        "anchor_grid": GRID,
        "change_merge_beats": CHANGE_MERGE_BEATS,
        "fields": {
            "score": "MusicXML path relative to dataset root",
            "anchor": "canonical score-grid position in quarter notes",
            "label": "one of NONE/DOWN/UP/CHANGE",
            "label_status": "ok | ambiguous_multi_event; coordinate ambiguity is carried by coordinate_ambiguous",
            "supervision_mask": "1 only when label_status=ok and score is evaluation eligible",
            "raw_DOWN": "raw start exists at this anchor before CHANGE consumption",
            "raw_UP": "raw stop exists at this anchor before CHANGE consumption",
            "raw_types": "document-order raw event types at this anchor",
            "remaining_DOWN": "start event remains after CHANGE consumption",
            "remaining_UP": "stop event remains after CHANGE consumption",
            "change_pair_count": "derived stop->start CHANGE pairs assigned to this anchor",
            "coordinate_ambiguous": "score contains repeat and is not in the M2 v1 supervision domain",
            "evaluation_eligible": "score is Main, non-repeat, printed-pedal, and has no truth outside canonical domain",
        },
        "run_mask_fields": {
            "mask": "Main 43 membership marker; 1 for Main runs, otherwise 0",
            "main_membership": "boolean Main membership",
            "reference_available": "score has at least one printed pedal element",
            "coordinate_ambiguous": "score contains repeat",
            "evaluation_eligible": "run may be used in the canonical evaluation domain",
            "supervision_mask": "run may be used for M2 v1 supervised training",
        },
    }
    schema_path = out_dir / "m2_label_schema.json"
    json_dump(schema_path, schema)

    output_paths = [
        labels_path, runs_path, excluded_path, summary_json, summary_md, schema_path,
        scores_csv, folds_csv, table1_csv, table1_md,
    ]
    outputs = {relpath(path): sha256_file(path) for path in output_paths}
    assignment_hash, assignment_rows, assignment_groups = assignment_sha256(split)
    split_bytes = split_path.read_bytes()
    manifest = {
        "dataset_version": DATASET_VERSION,
        "generator": {
            "path": "tools/m2_build_label_dataset.py",
            "sha256": sha256_file(Path(__file__).resolve()),
        },
        "command": {
            "argv": sys.argv,
            "cwd": str(Path.cwd()),
            "python_version": platform.python_version(),
            "platform": platform.platform(),
        },
        "inputs": {
            "dataset": relpath(dataset),
            "split": relpath(split_path),
            "split_raw_sha256": sha256_bytes(split_bytes),
            "split_lf_sha256": sha256_bytes(split_bytes.replace(b"\r\n", b"\n")),
            "assignment_sha256": assignment_hash,
            "assignment_rows": assignment_rows,
            "assignment_groups": assignment_groups,
            "metadata_sha256": sha256_file(metadata_path),
            "asap_annotations_sha256": sha256_file(dataset / "asap_annotations.json") if (dataset / "asap_annotations.json").is_file() else None,
        },
        "rules": {
            "anchor_domain": "[0, score_end]",
            "grid": GRID,
            "change_merge_beats": CHANGE_MERGE_BEATS,
            "change_event_order": "global position, preserving document order for equal positions",
            "change_anchor_rule": "assign to start (DOWN) anchor; consume both endpoints",
            "repeat_policy": "emit audit labels with coordinate_ambiguous=true and supervision_mask=0",
            "ambiguous_policy": "residual same-anchor start/stop collisions use first remaining event as label and supervision_mask=0",
        },
        "outputs": outputs,
        "counts": summary,
    }
    manifest_path = out_dir / "m2_manifest.json"
    json_dump(manifest_path, manifest)
    print(json.dumps({
        "status": "ok",
        "summary": str(summary_json),
        "manifest": str(manifest_path),
        "labels": str(labels_path),
        "runs": str(runs_path),
        "main_runs": summary["main_runs"],
        "evaluation_domain_runs": summary["evaluation_domain_runs"],
        "supervised_runs": summary["supervised_runs"],
        "canonical_truth_elements_full": summary["canonical_truth_elements_full"],
        "canonical_truth_elements_test": summary["canonical_truth_elements_test"],
    }, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
