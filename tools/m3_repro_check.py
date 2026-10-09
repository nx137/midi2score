#!/usr/bin/env python
"""M3.1 运行快照与二次运行比较。"""
from __future__ import annotations
import argparse, gzip, hashlib, json
from pathlib import Path
from typing import Any
import numpy as np

FILES = [
    "linear_model.json",
    "linear_data_summary.json",
    "linear_feature_schema.json",
    "linear_table.csv",
    "linear_per_class.csv",
    "linear_confusion.csv",
    "linear_cv.csv",
]
DATA_FILES = ["linear_predictions.jsonl.gz", "linear_runs.jsonl.gz"]


def sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def sha256_file(path: Path) -> str:
    return sha256_bytes(path.read_bytes())


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def npz_semantic(path: Path) -> dict[str, str]:
    with np.load(path, allow_pickle=False) as z:
        return {
            "X": sha256_bytes(np.ascontiguousarray(z["X"]).tobytes()),
            "y": sha256_bytes(np.ascontiguousarray(z["y"]).tobytes()),
            "offsets": sha256_bytes(np.ascontiguousarray(z["offsets"]).tobytes()),
        }


def semantic_summary(path: Path) -> dict[str, Any]:
    summary = load_json(path)
    summary.pop("wall_clock_sec", None)
    return summary


def make_snapshot(results: Path, data: Path) -> dict[str, Any]:
    return {
        "dataset_version": "m3-linear-v1",
        "outputs": {name: sha256_file(results / name) for name in FILES},
        "data_outputs": {name: sha256_file(data / name) for name in DATA_FILES},
        "summary_semantic": semantic_summary(results / "linear_summary.json"),
        "npz_semantic": npz_semantic(data / "linear_dataset.npz"),
    }


def compare(snapshot: dict[str, Any], results: Path, data: Path) -> dict[str, bool]:
    checks: dict[str, bool] = {}
    for name, expected in snapshot["outputs"].items():
        checks["hash_" + name] = sha256_file(results / name) == expected
    for name, expected in snapshot["data_outputs"].items():
        checks["hash_" + name] = sha256_file(data / name) == expected
    checks["summary_semantic"] = semantic_summary(results / "linear_summary.json") == snapshot["summary_semantic"]
    checks["npz_semantic"] = npz_semantic(data / "linear_dataset.npz") == snapshot["npz_semantic"]
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
    payload = {"dataset_version": "m3-linear-v1", "status": status, "checks": checks, "failures": [k for k, v in checks.items() if not v]}
    out.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (out.with_suffix(".md")).write_text(
        "# M3.1 linear repro\n\n" + f"- status: {status}\n- checks: {len(checks)}\n- failures: {len(payload['failures'])}\n\n" + ("\n".join(f"- {x}" for x in payload["failures"]) if payload["failures"] else "- all checks passed\n"),
        encoding="utf-8",
    )
    print(json.dumps({"status": status, "checks": len(checks), "failures": payload["failures"]}, ensure_ascii=False))
    return 0 if status == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
