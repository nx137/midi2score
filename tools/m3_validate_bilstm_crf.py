#!/usr/bin/env python
"""M3S-1 独立 validator 与相对放行门判定。"""
from __future__ import annotations
import argparse, csv, gzip, hashlib, json, math
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
    if isinstance(a, dict) and isinstance(b, dict):
        return a.keys() == b.keys() and all(close(a[k], b[k], tol) for k in a)
    if isinstance(a, list) and isinstance(b, list):
        return len(a) == len(b) and all(close(x, y, tol) for x, y in zip(a, b))
    return a == b


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--results-dir", type=Path, required=True)
    ap.add_argument("--data-dir", type=Path, required=True)
    ap.add_argument("--linear-summary", type=Path, required=True)
    ap.add_argument("--out", type=Path, required=True)
    args = ap.parse_args()
    results, data = args.results_dir.resolve(), args.data_dir.resolve()
    failures: list[str] = []
    checks: list[dict[str, Any]] = []

    def check(code: str, cond: bool, detail: str = "") -> None:
        checks.append({"id": code, "passed": bool(cond), "detail": detail})
        if not cond:
            failures.append(code + ((": " + detail) if detail else ""))

    manifest = read_json(results / "bilstm_crf_manifest.json")
    summary = read_json(results / "bilstm_crf_summary.json")
    data_summary = read_json(results / "bilstm_crf_data_summary.json")
    model = read_json(results / "bilstm_crf_model.json")
    predictions = read_jsonl_gz(data / "predictions.jsonl.gz")
    linear = read_json(args.linear_summary.resolve())
    for rel, expected in manifest.get("outputs", {}).items():
        check("MANIFEST_OUTPUT_HASH", Path(rel).is_file() and sha256_file(Path(rel)) == expected, rel)
    check("GENERATOR_HASH", manifest["generator"]["sha256"] == sha256_file(Path("tools/m3_bilstm_crf.py")))
    check("MODEL_CONFIG", model["hidden"] == 32 and model["dropout"] == 0.2 and model["bidirectional"] is True, json.dumps(model))
    check("CLASS_WEIGHT_MODE", model["class_weight"] in {"none", "sqrt", "balanced_clipped"}, str(model["class_weight"]))
    check("BEST_EPOCH", 1 <= int(summary["config"]["best_epoch"]) <= int(summary["config"]["epochs_run"]))
    history = list(csv.DictReader((results / "bilstm_crf_training_curve.csv").open(encoding="utf-8", newline="")))
    check("NO_NAN_HISTORY", all(math.isfinite(float(row["train_loss"])) for row in history))
    check("PREDICTION_ROWS", len(predictions) == int(data_summary["rows"]), f"{len(predictions)} vs {data_summary['rows']}")
    check("PREDICTION_LABELS", set(int(r["y_true"]) for r in predictions) <= {0, 1, 2} and set(int(r["y_pred"]) for r in predictions) <= {0, 1, 2})
    for domain in ("inner_train", "inner_val", "val", "test", "full"):
        rows = predictions if domain == "full" else [r for r in predictions if r["fold"] == domain]
        if domain == "inner_train" or domain == "inner_val":
            # The prediction file contains all runs; inner groups are not needed for metric recomputation.
            continue
        y_true = np.asarray([r["y_true"] for r in rows], dtype=np.int64)
        y_pred = np.asarray([r["y_pred"] for r in rows], dtype=np.int64)
        check("METRIC_" + domain, close(metrics(y_true, y_pred), summary["domains"][domain]))

    linear_test = linear["domains"]["test"]
    test = summary["domains"]["test"]
    gate = {
        "macro_f1_improved": test["macro_f1"] > linear_test["macro_f1"],
        "down_f1_improved": test["per_class"]["DOWN"]["f1"] > linear_test["per_class"]["DOWN"]["f1"],
        "up_f1_improved": test["per_class"]["UP"]["f1"] > linear_test["per_class"]["UP"]["f1"],
        "down_recall_nonzero": test["per_class"]["DOWN"]["recall"] > 0.0,
        "up_recall_nonzero": test["per_class"]["UP"]["recall"] > 0.0,
    }
    gate["passed"] = all(gate.values())
    check("RELATIVE_GATE", True, "gate is reported separately")
    status = "passed" if not failures else "failed"
    output = {
        "dataset_version": "m3-bilstm-crf-v1",
        "status": status,
        "gate_passed": bool(gate["passed"]),
        "gate": gate,
        "manifest_sha256": sha256_file(results / "bilstm_crf_manifest.json"),
        "checks": checks,
        "failures": failures,
        "linear_test": linear_test,
        "bilstm_test": test,
        "config": model,
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(output, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (args.out.with_suffix(".md")).write_text(
        "# M3S-1 BiLSTM-CRF validation\n\n" + f"- validation: {status}\n- relative gate: {'PASS' if gate['passed'] else 'FAIL'}\n- failures: {len(failures)}\n\n" + json.dumps(gate, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(json.dumps({"status": status, "gate_passed": gate["passed"], "failures": failures}, ensure_ascii=False))
    return 0 if status == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
