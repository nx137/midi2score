#!/usr/bin/env python
"""独立验证 M2 v1 标签数据集、run mask、hash 与 frozen counts。"""
from __future__ import annotations

import argparse
import csv
import gzip
import hashlib
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))
from canonical_domain import GRID, canonical_anchors, score_end  # noqa: E402
from inversion_consistency import parse_score, snap  # noqa: E402

LABELS = {"NONE", "DOWN", "UP", "CHANGE"}
EXPECTED = {
    "main_scores": 43,
    "evaluation_eligible_scores": 36,
    "coordinate_ambiguous_scores": 7,
    "main_runs": 291,
    "evaluation_domain_runs": 271,
    "raw_pedal_elements": 3840,
    "canonical_truth_elements_full": 28603,
    "canonical_truth_elements_test": 16278,
}


def sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def sha256_file(path: Path) -> str:
    return sha256_bytes(path.read_bytes())


def load_jsonl_gz(path: Path) -> list[dict[str, Any]]:
    with gzip.open(path, "rt", encoding="utf-8") as fh:
        return [json.loads(line) for line in fh if line.strip()]


def normalize_rel(value: str | None) -> str:
    return (value or "").replace("\\", "/")


def assignment_sha256(split: dict[str, Any]) -> str:
    import io
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
    writer = csv.DictWriter(buf, fieldnames=["piecegroup", "performanceid", "fold"], lineterminator="\r\n")
    writer.writeheader()
    writer.writerows(rows)
    return sha256_bytes(buf.getvalue().encode("utf-8"))


def oracle_score_rows(xml_path: Path, eval_eligible: bool) -> list[dict[str, Any]]:
    anchors = canonical_anchors(score_end(xml_path))
    anchor_set = set(anchors)
    _, pedals = parse_score(xml_path)
    events = sorted(enumerate(pedals), key=lambda item: (float(item[1][1]), item[0]))
    pairs: list[dict[str, Any]] = []
    consumed: set[int] = set()
    i = 0
    while i + 1 < len(events):
        li, left = events[i]
        ri, right = events[i + 1]
        _, lp, lk = left
        _, rp, rk = right
        gap = float(rp) - float(lp)
        if lk == "stop" and rk == "start" and 0.0 <= gap < 1.0:
            sa, ea = snap(float(lp)), snap(float(rp))
            if sa in anchor_set and ea in anchor_set:
                pairs.append({"start_anchor": ea})
                consumed.update({int(li), int(ri)})
                i += 2
                continue
        i += 1
    raw = defaultdict(list)
    for idx, (_, pos, kind) in enumerate(pedals):
        anchor = snap(float(pos))
        if anchor in anchor_set:
            raw[anchor].append((idx, kind))
    remaining = defaultdict(list)
    for anchor, items in raw.items():
        for idx, kind in items:
            if idx not in consumed:
                remaining[anchor].append(kind)
    change_count = Counter(pair["start_anchor"] for pair in pairs)
    rows = []
    for anchor in anchors:
        original = [kind for _, kind in raw.get(anchor, [])]
        rem = remaining.get(anchor, [])
        if change_count.get(anchor):
            label = "CHANGE"
            status = "ok" if len(set(rem)) <= 1 else "ambiguous_multi_event"
        elif not rem:
            label = "NONE"
            status = "ok"
        elif len(set(rem)) == 1:
            label = "DOWN" if rem[0] == "start" else "UP"
            status = "ok"
        else:
            label = "DOWN" if rem[0] == "start" else "UP"
            status = "ambiguous_multi_event"
        rows.append({
            "anchor": anchor,
            "label": label,
            "label_status": status,
            "raw_DOWN": "start" in original,
            "raw_UP": "stop" in original,
            "raw_types": ["DOWN" if kind == "start" else "UP" for kind in original],
            "remaining_DOWN": "start" in rem,
            "remaining_UP": "stop" in rem,
            "change_pair_count": int(change_count.get(anchor, 0)),
            "supervision_mask": 1 if eval_eligible and status == "ok" else 0,
        })
    return rows


def truth_count_by_score(xml_path: Path) -> int:
    _, pedals = parse_score(xml_path)
    anchors = set(canonical_anchors(score_end(xml_path)))
    return len({
        (snap(float(pos)), "DOWN" if kind == "start" else "UP")
        for _, pos, kind in pedals
        if snap(float(pos)) in anchors
    })


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dataset", type=Path, required=True)
    ap.add_argument("--split", type=Path, required=True)
    ap.add_argument("--data-dir", type=Path, required=True)
    ap.add_argument("--results-dir", type=Path, required=True)
    ap.add_argument("--out", type=Path, required=True)
    args = ap.parse_args()

    dataset = args.dataset.resolve()
    split_path = args.split.resolve()
    data_dir = args.data_dir.resolve()
    results_dir = args.results_dir.resolve()
    manifest_path = results_dir / "m2_manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    failures: list[str] = []
    checks: list[dict[str, Any]] = []

    def check(code: str, condition: bool, detail: str = "") -> None:
        checks.append({"id": code, "passed": bool(condition), "detail": detail})
        if not condition:
            failures.append(code + ((": " + detail) if detail else ""))

    for rel, expected_hash in manifest.get("outputs", {}).items():
        path = Path(rel)
        if not path.is_file():
            check("MANIFEST_OUTPUT_EXISTS", False, rel)
            continue
        actual = sha256_file(path)
        check("MANIFEST_OUTPUT_HASH", actual == expected_hash, rel)

    check("MANIFEST_GENERATOR_HASH", manifest["generator"]["sha256"] == sha256_file(Path("tools/m2_build_label_dataset.py")))
    split = json.loads(split_path.read_text(encoding="utf-8"))
    split_bytes = split_path.read_bytes()
    check("SPLIT_RAW_HASH", manifest["inputs"]["split_raw_sha256"] == sha256_bytes(split_bytes))
    check("SPLIT_LF_HASH", manifest["inputs"]["split_lf_sha256"] == sha256_bytes(split_bytes.replace(b"\r\n", b"\n")))
    check("ASSIGNMENT_HASH", manifest["inputs"]["assignment_sha256"] == assignment_sha256(split))
    check("METADATA_HASH", manifest["inputs"]["metadata_sha256"] == sha256_file(dataset / "metadata.csv"))
    check("ANNOTATIONS_HASH", manifest["inputs"]["asap_annotations_sha256"] == sha256_file(dataset / "asap_annotations.json"))

    labels = load_jsonl_gz(data_dir / "score_labels.jsonl.gz")
    runs = load_jsonl_gz(data_dir / "run_masks.jsonl.gz")
    excluded = load_jsonl_gz(data_dir / "m2_excluded_anchors.jsonl.gz")
    schema = json.loads((results_dir / "m2_label_schema.json").read_text(encoding="utf-8"))
    check("LABEL_SCHEMA_VERSION", schema.get("dataset_version") == "m2-v1")
    check("LABEL_SCHEMA_GRID", schema.get("anchor_grid") == GRID)
    check("LABEL_SCHEMA_CHANGE", schema.get("change_merge_beats") == 1.0)
    check("LABEL_SET", all(row.get("label") in LABELS for row in labels))
    check("LABEL_UNIQUE", len({(row["score"], row["anchor"]) for row in labels}) == len(labels))
    check("LABEL_MASK_BINARY", all(int(row["supervision_mask"]) in (0, 1) for row in labels))
    check("LABEL_EXCLUDED_ROWS", excluded == [row for row in labels if row.get("label_status") != "ok"])

    main_scores = sorted(set(split["main_scores"]))
    repeat_scores = []
    label_by_score: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in labels:
        label_by_score[row["score"]].append(row)
    check("LABEL_SCORE_SET", set(label_by_score) == set(main_scores))
    for score in main_scores:
        xml_path = dataset / score
        root = __import__("lxml").etree.parse(str(xml_path)).getroot()
        repeat = bool(root.xpath(".//*[local-name()='repeat']"))
        if repeat:
            repeat_scores.append(score)
        expected_rows = oracle_score_rows(xml_path, eval_eligible=not repeat)
        actual_rows = sorted(label_by_score[score], key=lambda row: row["anchor"])
        check("SCORE_ROW_COUNT", len(actual_rows) == len(expected_rows), score)
        if len(actual_rows) != len(expected_rows):
            continue
        for actual, expected in zip(actual_rows, expected_rows):
            for key in ("anchor", "label", "label_status", "raw_DOWN", "raw_UP", "raw_types",
                        "remaining_DOWN", "remaining_UP", "change_pair_count", "supervision_mask"):
                if actual.get(key) != expected.get(key):
                    check("SCORE_ROW_FIELD", False, f"{score}:{actual.get('anchor')}:{key}")
                    break
    check("COORDINATE_AMBIGUOUS_SET", sorted(set(repeat_scores)) == sorted(manifest["counts"]["coordinate_ambiguous_score_list"]))
    check("LABEL_TOTAL", len(labels) == sum(len(oracle_score_rows(dataset / score, eval_eligible=score not in repeat_scores)) for score in main_scores))

    check("RUN_UNIQUE", len({(row["score"], row["midi_performance"]) for row in runs}) == len(runs))
    check("RUN_MAIN_MASK", sum(int(row["mask"]) for row in runs) == EXPECTED["main_runs"])
    check("RUN_EVAL_MASK", sum(int(row["evaluation_eligible"]) for row in runs) == EXPECTED["evaluation_domain_runs"])
    check("RUN_SUPERVISION_MASK", sum(int(row["supervision_mask"]) for row in runs) == EXPECTED["evaluation_domain_runs"])
    check("RUN_NON_MAIN_NOT_SUPERVISED", all(int(row["supervision_mask"]) == 0 for row in runs if not row["main_membership"]))
    check("RUN_REPEAT_NOT_SUPERVISED", all(int(row["supervision_mask"]) == 0 for row in runs if row["coordinate_ambiguous"]))
    check("RUN_NO_PEDAL_NOT_SUPERVISED", all(int(row["supervision_mask"]) == 0 for row in runs if not row["has_pedal"]))
    check("RUN_SUPERVISED_REQUIRES_INPUTS", all(
        int(row["supervision_mask"]) == 0 or (
            row["main_membership"] and row["has_pedal"] and not row["coordinate_ambiguous"]
            and row["has_alignment"] and row["has_midi"] and row["evaluation_eligible"]
        ) for row in runs
    ))

    metadata_rows = list(csv.DictReader((dataset / "metadata.csv").open(encoding="utf-8-sig", newline="")))
    align_by_key = {
        (normalize_rel(row.get("xml_score")), normalize_rel(row.get("midi_performance"))): normalize_rel(row.get("note_alignments"))
        for row in metadata_rows
    }
    hash_cache: dict[str, str] = {}
    def cached_hash(path: Path) -> str:
        key = str(path.resolve())
        if key not in hash_cache:
            hash_cache[key] = sha256_file(path)
        return hash_cache[key]
    source_ok = True
    for row in runs:
        score_path = dataset / row["score"]
        midi_path = dataset / row["midi_performance"]
        align_rel = align_by_key.get((row["score"], row["midi_performance"]), "")
        align_path = dataset / align_rel if align_rel else None
        expected_align = cached_hash(align_path) if align_path and align_path.is_file() else None
        if row["source_score_sha256"] != cached_hash(score_path):
            check("RUN_SOURCE_SCORE_HASH", False, row["score"])
            source_ok = False
            break
        if row["source_midi_sha256"] != (cached_hash(midi_path) if midi_path.is_file() else None):
            check("RUN_SOURCE_MIDI_HASH", False, row["midi_performance"])
            source_ok = False
            break
        if row["source_alignment_sha256"] != expected_align:
            check("RUN_SOURCE_ALIGNMENT_HASH", False, row["midi_performance"])
            source_ok = False
            break
    if source_ok:
        check("RUN_SOURCE_HASHES", True)

    truth_by_score = {
        score: truth_count_by_score(dataset / score)
        for score in main_scores if score not in repeat_scores
    }
    run_counts = Counter()
    truth_counts = Counter()
    for row in runs:
        if row["fold"]:
            run_counts[row["fold"]] += 1
        if int(row["supervision_mask"]) == 1:
            truth_counts[row["fold"]] += truth_by_score.get(row["score"], 0)
    truth_counts["full"] = sum(truth_counts.values())
    check("TRUTH_FULL", truth_counts.get("full", 0) == EXPECTED["canonical_truth_elements_full"])
    check("TRUTH_TEST", truth_counts.get("test", 0) == EXPECTED["canonical_truth_elements_test"])
    for key, expected in EXPECTED.items():
        check("COUNT_" + key, manifest["counts"].get(key) == expected, f"got={manifest['counts'].get(key)}")

    counts = {
        "label_rows": len(labels),
        "supervised_label_rows": sum(int(row["supervision_mask"]) for row in labels),
        "ambiguous_label_rows": sum(1 for row in labels if row["label_status"] != "ok"),
        "run_rows": len(runs),
        "main_runs": sum(int(row["mask"]) for row in runs),
        "evaluation_domain_runs": sum(int(row["evaluation_eligible"]) for row in runs),
        "supervised_runs": sum(int(row["supervision_mask"]) for row in runs),
        "canonical_truth_elements_full": truth_counts.get("full", 0),
        "canonical_truth_elements_test": truth_counts.get("test", 0),
    }
    for key, value in counts.items():
        check("COUNT_" + key, manifest["counts"].get(key) == value, f"manifest={manifest['counts'].get(key)} actual={value}")

    status = "passed" if not failures else "failed"
    output = {
        "dataset_version": "m2-v1",
        "status": status,
        "manifest_sha256": sha256_file(manifest_path),
        "checks": checks,
        "failures": failures,
        "counts": counts,
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(output, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    md = args.out.with_suffix(".md")
    md.write_text(
        "# M2 validation\n\n" +
        f"- status: {status}\n" +
        f"- checks: {len(checks)}\n" +
        f"- failures: {len(failures)}\n\n" +
        ("\n".join(f"- {item}" for item in failures) if failures else "- all checks passed\n"),
        encoding="utf-8",
    )
    print(json.dumps({"status": status, "checks": len(checks), "failures": failures}, ensure_ascii=False))
    return 0 if status == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
