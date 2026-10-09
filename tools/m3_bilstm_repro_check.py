#!/usr/bin/env python
"""M3S-1 运行快照与二次运行比较。"""
from __future__ import annotations
import argparse, hashlib, json
from pathlib import Path
from typing import Any

FILES = ["bilstm_crf_model.json", "bilstm_crf_data_summary.json", "bilstm_crf_table.csv", "bilstm_crf_per_class.csv", "bilstm_crf_confusion.csv", "bilstm_crf_training_curve.csv"]
DATA_FILES = ["best_model.pt", "predictions.jsonl.gz"]


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def semantic_summary(path: Path) -> dict[str, Any]:
    payload = load_json(path)
    payload.pop("wall_clock_sec", None)
    return payload


def make_snapshot(results: Path, data: Path) -> dict[str, Any]:
    return {
        "dataset_version": "m3-bilstm-crf-v1",
        "outputs": {name: sha256_file(results / name) for name in FILES},
        "data_outputs": {name: sha256_file(data / name) for name in DATA_FILES},
        "summary_semantic": semantic_summary(results / "bilstm_crf_summary.json"),
    }


def compare(snapshot: dict[str, Any], results: Path, data: Path) -> dict[str, bool]:
    checks: dict[str, bool] = {}
    for name, expected in snapshot["outputs"].items():
        checks["hash_" + name] = sha256_file(results / name) == expected
    for name, expected in snapshot["data_outputs"].items():
        checks["hash_" + name] = sha256_file(data / name) == expected
    checks["summary_semantic"] = semantic_summary(results / "bilstm_crf_summary.json") == snapshot["summary_semantic"]
    return checks


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--results-dir", type=Path, required=True)
    ap.add_argument("--data-dir", type=Path, required=True)
    ap.add_argument("--snapshot", type=Path, default=None)
    ap.add_argument("--check", type=Path, default=None)
    ap.add_argument("--out", type=Path, required=True)
    args = ap.parse_args()
    out = args.out.resolve()
    out.parent.mkdir(parents=True, exist_ok=True)
    if args.snapshot:
        payload = make_snapshot(args.results_dir.resolve(), args.data_dir.resolve())
        args.snapshot.resolve().write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print(json.dumps({"status": "snapshot", "snapshot": str(args.snapshot)}, ensure_ascii=False))
        return 0
    if not args.check:
        raise SystemExit("--check or --snapshot required")
    snapshot = load_json(args.check.resolve())
    checks = compare(snapshot, args.results_dir.resolve(), args.data_dir.resolve())
    status = "passed" if all(checks.values()) else "failed"
    payload = {"dataset_version": "m3-bilstm-crf-v1", "status": status, "checks": checks, "failures": [k for k, v in checks.items() if not v]}
    out.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (out.with_suffix(".md")).write_text("# M3S-1 BiLSTM-CRF repro\n\n" + f"- status: {status}\n- checks: {len(checks)}\n- failures: {len(payload['failures'])}\n\n" + ("\n".join(f"- {x}" for x in payload["failures"]) if payload["failures"] else "- all checks passed\n"), encoding="utf-8")
    print(json.dumps({"status": status, "checks": len(checks), "failures": payload["failures"]}, ensure_ascii=False))
    return 0 if status == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
