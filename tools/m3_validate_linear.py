#!/usr/bin/env python
"""M3.1 独立 validator：重算指标并核对 M3 linear artifacts。"""
from __future__ import annotations
import argparse, gzip, hashlib, json, sys
from pathlib import Path
from typing import Any
import numpy as np
from sklearn.metrics import confusion_matrix, f1_score, precision_recall_fscore_support

CLASS_NAMES = ["NONE", "DOWN", "UP"]


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def read_jsonl_gz(path: Path) -> list[dict[str, Any]]:
    with gzip.open(path, "rt", encoding="utf-8") as fh:
        return [json.loads(line) for line in fh if line.strip()]


def metrics(y_true: np.ndarray, y_pred: np.ndarray) -> dict[str, Any]:
    labels = [0, 1, 2]
    p, r, f, s = precision_recall_fscore_support(y_true, y_pred, labels=labels, zero_division=0)
    return {
        "micro_f1": float(f1_score(y_true, y_pred, labels=labels, average="micro", zero_division=0)),
        "macro_f1": float(f1_score(y_true, y_pred, labels=labels, average="macro", zero_division=0)),
        "accuracy": float(np.mean(y_true == y_pred)),
        "n": int(len(y_true)),
        "per_class": {name: {"precision": float(p[i]), "recall": float(r[i]), "f1": float(f[i]), "support": int(s[i])} for i, name in enumerate(CLASS_NAMES)},
        "confusion_matrix": confusion_matrix(y_true, y_pred, labels=labels).tolist(),
    }


def close(a: Any, b: Any, tol: float = 1e-10) -> bool:
    if isinstance(a, (int, float)) and isinstance(b, (int, float)):
        return abs(float(a) - float(b)) <= tol
    if isinstance(a, list) and isinstance(b, list):
        return len(a) == len(b) and all(close(x, y, tol) for x, y in zip(a, b))
    if isinstance(a, dict) and isinstance(b, dict):
        return a.keys() == b.keys() and all(close(a[k], b[k], tol) for k in a)
    return a == b


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--results-dir", type=Path, required=True)
    ap.add_argument("--data-dir", type=Path, required=True)
    ap.add_argument("--out", type=Path, required=True)
    args = ap.parse_args()
    results = args.results_dir.resolve()
    data = args.data_dir.resolve()
    failures: list[str] = []
    checks: list[dict[str, Any]] = []

    def check(code: str, cond: bool, detail: str = "") -> None:
        checks.append({"id": code, "passed": bool(cond), "detail": detail})
        if not cond:
            failures.append(code + ((": " + detail) if detail else ""))

    manifest = read_json(results / "linear_manifest.json")
    summary = read_json(results / "linear_summary.json")
    data_summary = read_json(results / "linear_data_summary.json")
    model = read_json(results / "linear_model.json")
    feature_schema = read_json(results / "linear_feature_schema.json")
    runs = read_jsonl_gz(data / "linear_runs.jsonl.gz")
    predictions = read_jsonl_gz(data / "linear_predictions.jsonl.gz")
    npz = np.load(data / "linear_dataset.npz", allow_pickle=False)
    X, y = npz["X"], npz["y"]

    for rel, expected in manifest.get("outputs", {}).items():
        path = Path(rel)
        check("MANIFEST_OUTPUT_HASH", path.is_file() and sha256_file(path) == expected, rel)
    check("GENERATOR_HASH", manifest["generator"]["sha256"] == sha256_file(Path("tools/m3_linear_baseline.py")))
    check("FEATURE_SHAPE", X.shape[1] == 53, str(X.shape))
    check("FEATURE_FINITE", bool(np.isfinite(X).all()))
    check("LABEL_DOMAIN", set(np.unique(y).tolist()) <= {-1, 0, 1, 2}, str(sorted(np.unique(y).tolist())))
    check("RUN_COUNT", len(runs) == 271, str(len(runs)))
    check("SCORE_COUNT", len({r["score"] for r in runs}) == 36, str(len({r["score"] for r in runs})))
    train_groups = {r["group"] for r in runs if r["fold"] == "train"}
    val_groups = {r["group"] for r in runs if r["fold"] == "val"}
    test_groups = {r["group"] for r in runs if r["fold"] == "test"}
    check("GROUP_DISJOINT_TRAIN_VAL", not (train_groups & val_groups))
    check("GROUP_DISJOINT_TRAIN_TEST", not (train_groups & test_groups))
    check("GROUP_DISJOINT_VAL_TEST", not (val_groups & test_groups))
    check("FOLD_RUNS", data_summary["fold_run_counts"] == {"train": 166, "val": 28, "test": 77}, str(data_summary["fold_run_counts"]))
    check("INCLUDED_COUNTS", data_summary["included_counts"] == {"NONE": 742432, "DOWN": 8135, "UP": 7798}, str(data_summary["included_counts"]))
    check("EXCLUDED_COUNTS_CHANGE", data_summary["excluded_counts"].get("CHANGE", 0) > 0, str(data_summary["excluded_counts"]))
    check("EXCLUDED_SUM", sum(data_summary["excluded_counts"].values()) == int((y < 0).sum()), str(data_summary["excluded_counts"]))
    check("V1_PASS", bool(data_summary["v1_pass"]))
    check("FEATURE_SOURCE_LEAK_EMPTY", not data_summary["feature_source_leak"], str(data_summary["feature_source_leak"]))
    check("FEATURE_SCHEMA_NO_LEAK", not feature_schema["source_leak"])
    check("MODEL_COEF_SHAPE", len(model["coef"]) == 3 and all(len(row) == 53 for row in model["coef"]), str([len(row) for row in model["coef"]]))
    check("SCALER_SHAPE", len(model["scaler_mean"]) == 53 and len(model["scaler_scale"]) == 53)
    check("SELECTED_C_MATCH", float(summary["selected_C"]) == float(model["selected_C"]))
    check("PREDICTION_ROWS", len(predictions) == int(data_summary["included_row_count"]), f"{len(predictions)} vs {data_summary['included_row_count']}")

    for domain in ("train", "val", "test", "full"):
        rows = predictions if domain == "full" else [row for row in predictions if row["fold"] == domain]
        y_true = np.asarray([row["y_true"] for row in rows], dtype=np.int64)
        y_pred = np.asarray([row["y_pred"] for row in rows], dtype=np.int64)
        recomputed = metrics(y_true, y_pred)
        check("METRIC_" + domain, close(recomputed, summary["domains"][domain]), f"recomputed={recomputed['micro_f1']}/{recomputed['macro_f1']}")

    status = "passed" if not failures else "failed"
    output = {
        "dataset_version": "m3-linear-v1",
        "status": status,
        "manifest_sha256": sha256_file(results / "linear_manifest.json"),
        "checks": checks,
        "failures": failures,
        "summary": {
            "runs": len(runs),
            "scores": len({r["score"] for r in runs}),
            "rows": int(X.shape[0]),
            "included_rows": int((y >= 0).sum()),
            "excluded_rows": int((y < 0).sum()),
            "selected_C": summary["selected_C"],
            "test": summary["domains"]["test"],
        },
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(output, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (args.out.with_suffix(".md")).write_text(
        "# M3.1 linear validation\n\n" + f"- status: {status}\n- checks: {len(checks)}\n- failures: {len(failures)}\n\n" + ("\n".join(f"- {x}" for x in failures) if failures else "- all checks passed\n"),
        encoding="utf-8",
    )
    print(json.dumps({"status": status, "checks": len(checks), "failures": failures}, ensure_ascii=False))
    return 0 if status == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
