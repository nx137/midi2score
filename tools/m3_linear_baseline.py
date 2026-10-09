#!/usr/bin/env python
"""M3.1：在 M2 v1 canonical 标签层上训练正则化三分类线性 baseline。

协议（D-0089）：
- 只用 M2 v1 的 36 首 canonical 域 / 271 supervised runs。
- 标签 NONE/DOWN/UP 为 0/1/2；M2 supervision_mask=0 的 CHANGE 与
  ambiguous anchors 一律不进入训练和指标，不做静默映射。
- 模型选择只在 train 折内按 score group 做 GroupKFold；test 只在
  选择完成后评估一次。
- A/B/C 特征复用 round_b_features；禁止印刷 pedal 派生特征。
- 主指标仍为回放保真度，谱面一致度为强制副指标；本脚本只做
  序列模型前置条件验证，不把线性 baseline 当最终模型。
"""
from __future__ import annotations

import argparse
import csv
import gzip
import hashlib
import json
import platform
import sys
import time
from collections import Counter
from pathlib import Path
from typing import Any

import numpy as np
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import confusion_matrix, f1_score, precision_recall_fscore_support
from sklearn.model_selection import GroupKFold
from sklearn.preprocessing import StandardScaler

sys.path.insert(0, str(Path(__file__).resolve().parent))
from inversion_consistency import parse_alignment  # noqa: E402
from round_b_features import (  # noqa: E402
    FEATURE_NAMES,
    FEATURE_SOURCES,
    build_run_features,
    load_score,
    make_stripped_score,
    score_note_features,
)

REPO_ROOT = Path(__file__).resolve().parents[1]
CLASS_NAMES = ["NONE", "DOWN", "UP"]
LABEL_TO_ID = {name: idx for idx, name in enumerate(CLASS_NAMES)}
ID_TO_LABEL = {idx: name for name, idx in LABEL_TO_ID.items()}


def sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def sha256_file(path: Path) -> str:
    return sha256_bytes(path.read_bytes())


def sha256_text(text: str) -> str:
    return sha256_bytes(text.encode("utf-8"))


def relpath(path: Path) -> str:
    try:
        return path.resolve().relative_to(REPO_ROOT.resolve()).as_posix()
    except ValueError:
        return str(path.resolve())


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def read_jsonl_gz(path: Path) -> list[dict[str, Any]]:
    with gzip.open(path, "rt", encoding="utf-8") as fh:
        return [json.loads(line) for line in fh if line.strip()]


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


def flatten_group(groups: list[str], lengths: list[int]) -> np.ndarray:
    return np.concatenate([np.full(n, g, dtype=object) for g, n in zip(groups, lengths)]) if lengths else np.asarray([], dtype=object)


def build_dataset(
    dataset: Path,
    split_path: Path,
    labels_path: Path,
    runs_path: Path,
    v1_tmp: Path,
) -> tuple[np.ndarray, np.ndarray, list[dict[str, Any]], dict[str, Any], np.ndarray, np.ndarray, list[str]]:
    split = json.loads(split_path.read_text(encoding="utf-8"))
    score_meta = split["score_meta"]
    label_rows = read_jsonl_gz(labels_path)
    run_rows = read_jsonl_gz(runs_path)
    labels_by_score: dict[str, dict[float, dict[str, Any]]] = {}
    for row in label_rows:
        labels_by_score.setdefault(row["score"], {})[float(row["anchor"])] = row

    selected_runs = [row for row in run_rows if int(row.get("supervision_mask", 0)) == 1]
    score_cache: dict[str, dict[str, Any]] = {}
    X_parts: list[np.ndarray] = []
    y_parts: list[np.ndarray] = []
    run_meta: list[dict[str, Any]] = []
    included_counts: Counter[str] = Counter()
    excluded_counts: Counter[str] = Counter()
    fold_counts: Counter[str] = Counter()
    row_counts: list[int] = []
    groups: list[str] = []
    feature_names: list[str] = []
    v1_results: dict[str, bool] = {}
    v1_bad: list[str] = []
    offset = 0

    for run in selected_runs:
        score = str(run["score"])
        midi_rel = str(run["midi_performance"])
        if score not in score_cache:
            score_cache[score] = load_score(dataset / score)
        score_obj = score_cache[score]
        midi_path = dataset / midi_rel
        # run_masks does not carry the alignment path; recover it from the split.
        align_rel = None
        for perf in split["per_performance"]:
            if perf["xml_score"] == score and perf["midi_performance"] == midi_rel:
                align_rel = perf.get("alignment_path")
                break
        if not align_rel:
            raise RuntimeError(f"alignment path missing for {score} / {midi_rel}")
        align_path = dataset / align_rel
        seq = sorted(
            (float(onset), score_obj["notes"][base]["pos"])
            for base, _, onset in parse_alignment(align_path)
            if base in score_obj["notes"]
        )
        if len(seq) < 2:
            raise RuntimeError(f"alignment sequence too short: {score} / {midi_rel}")
        X, names, _ = build_run_features(score_obj, midi_path, seq, delta_mode="score_grid", ann=None)
        if not feature_names:
            feature_names = list(names)
        elif feature_names != list(names):
            raise RuntimeError(f"feature name drift: {score}")
        if not np.isfinite(X).all():
            raise RuntimeError(f"non-finite features: {score} / {midi_rel}")

        label_map = labels_by_score.get(score, {})
        y = np.empty(len(score_obj["anchors"]), dtype=np.int8)
        local_counts: Counter[str] = Counter()
        local_excluded: Counter[str] = Counter()
        for idx, anchor in enumerate(score_obj["anchors"]):
            label_row = label_map.get(float(anchor))
            if label_row is None:
                raise RuntimeError(f"M2 label missing for {score} anchor {anchor}")
            label = str(label_row["label"])
            if (
                int(label_row.get("supervision_mask", 0)) == 0
                or label == "CHANGE"
                or str(label_row.get("label_status", "ok")) != "ok"
            ):
                y[idx] = -1
                local_excluded[label] += 1
                excluded_counts[label] += 1
            else:
                if label not in LABEL_TO_ID:
                    raise RuntimeError(f"unexpected supervised label {label} for {score} anchor {anchor}")
                y[idx] = LABEL_TO_ID[label]
                local_counts[label] += 1
                included_counts[label] += 1
        X_parts.append(X.astype(np.float32))
        y_parts.append(y)
        n_rows = int(X.shape[0])
        row_counts.append(n_rows)
        groups.append(str(score_meta[score]["group"]))
        run_meta.append({
            "run_id": str(run["run_id"]),
            "score": score,
            "midi_performance": midi_rel,
            "fold": str(run["fold"]),
            "group": str(score_meta[score]["group"]),
            "n_rows": n_rows,
            "n_included": int((y >= 0).sum()),
            "n_excluded": int((y < 0).sum()),
            "included_counts": {name: int(local_counts.get(name, 0)) for name in CLASS_NAMES},
            "excluded_counts": dict(sorted(local_excluded.items())),
            "x_offset": offset,
            "x_length": n_rows,
        })
        offset += n_rows
        fold_counts[str(run["fold"])] += 1

    for score in sorted(score_cache):
        stripped = make_stripped_score(dataset / score, v1_tmp)
        score_stripped = load_score(dataset / score, stripped)
        b_original, _ = score_note_features(score_cache[score])
        b_stripped, _ = score_note_features(score_stripped)
        equal = bool(np.array_equal(b_original, b_stripped))
        v1_results[score] = equal
        if not equal:
            v1_bad.append(score)

    X_all = np.concatenate(X_parts, axis=0) if X_parts else np.empty((0, len(feature_names)), dtype=np.float32)
    y_all = np.concatenate(y_parts, axis=0) if y_parts else np.empty((0,), dtype=np.int8)
    run_offsets = np.cumsum([0] + [int(run["n_rows"]) for run in run_meta], dtype=np.int64)
    groups_by_row = flatten_group(groups, row_counts)
    source_leak = {
        name: source for name, source in FEATURE_SOURCES.items()
        if "pedal" in source.lower() or "score_pedal" in source.lower()
    }
    data_summary = {
        "dataset_version": "m3-linear-v1",
        "main_scores": len(score_cache),
        "supervised_runs": len(run_meta),
        "feature_count": len(feature_names),
        "row_count": int(X_all.shape[0]),
        "included_row_count": int((y_all >= 0).sum()),
        "excluded_row_count": int((y_all < 0).sum()),
        "included_counts": {name: int(included_counts.get(name, 0)) for name in CLASS_NAMES},
        "excluded_counts": dict(sorted(excluded_counts.items())),
        "fold_run_counts": {key: int(fold_counts.get(key, 0)) for key in ("train", "val", "test")},
        "v1_pass": not v1_bad,
        "v1_bad_scores": v1_bad,
        "v1_results": v1_results,
        "feature_sources": FEATURE_SOURCES,
        "feature_source_leak": source_leak,
        "label_map": LABEL_TO_ID,
    }
    return X_all, y_all, run_meta, data_summary, run_offsets, groups_by_row, feature_names


def classification_metrics(y_true: np.ndarray, y_pred: np.ndarray) -> dict[str, Any]:
    y_true = np.asarray(y_true, dtype=np.int64)
    y_pred = np.asarray(y_pred, dtype=np.int64)
    labels = [0, 1, 2]
    precision, recall, f1, support = precision_recall_fscore_support(
        y_true, y_pred, labels=labels, zero_division=0
    )
    cm = confusion_matrix(y_true, y_pred, labels=labels)
    return {
        "micro_f1": float(f1_score(y_true, y_pred, labels=labels, average="micro", zero_division=0)),
        "macro_f1": float(f1_score(y_true, y_pred, labels=labels, average="macro", zero_division=0)),
        "accuracy": float(np.mean(y_true == y_pred)) if len(y_true) else 0.0,
        "n": int(len(y_true)),
        "per_class": {
            name: {
                "precision": float(precision[i]),
                "recall": float(recall[i]),
                "f1": float(f1[i]),
                "support": int(support[i]),
            }
            for i, name in enumerate(CLASS_NAMES)
        },
        "confusion_matrix": cm.tolist(),
    }


def make_model(C: float, seed: int) -> LogisticRegression:
    return LogisticRegression(
        C=float(C),
        solver="lbfgs",
        class_weight="balanced",
        max_iter=2000,
        random_state=int(seed),
    )


def train_cv(
    X: np.ndarray,
    y: np.ndarray,
    groups: np.ndarray,
    c_grid: list[float],
    seed: int,
    n_splits: int = 5,
) -> tuple[float, list[dict[str, Any]]]:
    included = y >= 0
    X_inc = X[included]
    y_inc = y[included]
    g_inc = groups[included]
    unique_groups = sorted(set(str(g) for g in g_inc))
    splits = min(int(n_splits), len(unique_groups))
    if splits < 2:
        raise RuntimeError("not enough train groups for CV")
    cv_rows: list[dict[str, Any]] = []
    summary: dict[float, dict[str, float]] = {}
    splitter = GroupKFold(n_splits=splits)
    for C in c_grid:
        fold_macro: list[float] = []
        fold_micro: list[float] = []
        for fold_idx, (tr, va) in enumerate(splitter.split(X_inc, y_inc, g_inc), start=1):
            scaler = StandardScaler()
            X_tr = scaler.fit_transform(X_inc[tr])
            X_va = scaler.transform(X_inc[va])
            model = make_model(C, seed)
            model.fit(X_tr, y_inc[tr])
            pred = model.predict(X_va)
            met = classification_metrics(y_inc[va], pred)
            fold_macro.append(met["macro_f1"])
            fold_micro.append(met["micro_f1"])
            cv_rows.append({
                "C": float(C),
                "fold": fold_idx,
                "n_train": int(len(tr)),
                "n_val": int(len(va)),
                "macro_f1": met["macro_f1"],
                "micro_f1": met["micro_f1"],
                "class_f1_NONE": met["per_class"]["NONE"]["f1"],
                "class_f1_DOWN": met["per_class"]["DOWN"]["f1"],
                "class_f1_UP": met["per_class"]["UP"]["f1"],
            })
        summary[float(C)] = {
            "mean_macro_f1": float(np.mean(fold_macro)),
            "mean_micro_f1": float(np.mean(fold_micro)),
            "std_macro_f1": float(np.std(fold_macro)),
        }
    selected = max(c_grid, key=lambda C: (summary[float(C)]["mean_macro_f1"], -float(C)))
    return float(selected), cv_rows


def fit_final(
    X: np.ndarray,
    y: np.ndarray,
    C: float,
    seed: int,
) -> tuple[StandardScaler, LogisticRegression]:
    included = y >= 0
    scaler = StandardScaler()
    X_train = scaler.fit_transform(X[included])
    model = make_model(C, seed)
    model.fit(X_train, y[included])
    return scaler, model


def predict_included(
    X: np.ndarray,
    y: np.ndarray,
    scaler: StandardScaler,
    model: LogisticRegression,
) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    included = y >= 0
    idx = np.flatnonzero(included)
    X_inc = scaler.transform(X[included])
    probs = model.predict_proba(X_inc)
    pred = model.predict(X_inc)
    return idx, pred.astype(np.int64), probs.astype(np.float64), y[included].astype(np.int64)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dataset", type=Path, required=True)
    ap.add_argument("--split", type=Path, required=True)
    ap.add_argument("--m2-labels", type=Path, required=True)
    ap.add_argument("--m2-runs", type=Path, required=True)
    ap.add_argument("--out-dir", type=Path, required=True)
    ap.add_argument("--data-out", type=Path, required=True)
    ap.add_argument("--c-grid", type=str, default="0.1,1.0,10.0")
    ap.add_argument("--seed", type=int, default=20260101)
    args = ap.parse_args()

    t0 = time.time()
    dataset = args.dataset.resolve()
    split_path = args.split.resolve()
    labels_path = args.m2_labels.resolve()
    runs_path = args.m2_runs.resolve()
    out_dir = args.out_dir.resolve()
    data_out = args.data_out.resolve()
    out_dir.mkdir(parents=True, exist_ok=True)
    data_out.mkdir(parents=True, exist_ok=True)
    v1_tmp = data_out / "v1_stripped_xml"
    c_grid = [float(x) for x in args.c_grid.split(",") if x.strip()]

    X, y, run_meta, data_summary, offsets, groups_by_row, feature_names = build_dataset(
        dataset, split_path, labels_path, runs_path, v1_tmp
    )
    if len(feature_names) != len(FEATURE_NAMES):
        raise RuntimeError(f"feature count mismatch: {len(feature_names)} != {len(FEATURE_NAMES)}")
    if data_summary["supervised_runs"] != 271:
        raise RuntimeError(f"supervised runs mismatch: {data_summary['supervised_runs']}")
    if data_summary["main_scores"] != 36:
        raise RuntimeError(f"score count mismatch: {data_summary['main_scores']}")
    if not data_summary["v1_pass"]:
        raise RuntimeError(f"V1 failed: {data_summary['v1_bad_scores']}")
    if data_summary["feature_source_leak"]:
        raise RuntimeError(f"feature source leak: {data_summary['feature_source_leak']}")

    def indices_for_fold(fold: str) -> np.ndarray:
        parts = [
            np.arange(int(run["x_offset"]), int(run["x_offset"]) + int(run["x_length"]), dtype=np.int64)
            for run in run_meta if run["fold"] == fold
        ]
        return np.concatenate(parts) if parts else np.empty(0, dtype=np.int64)

    train_idx = indices_for_fold("train")
    val_idx = indices_for_fold("val")
    test_idx = indices_for_fold("test")
    all_idx = np.arange(len(y), dtype=np.int64)
    if len(train_idx) == 0 or len(val_idx) == 0 or len(test_idx) == 0:
        raise RuntimeError("missing train/val/test rows")
    train_groups = groups_by_row[train_idx]
    selected_c, cv_rows = train_cv(X[train_idx], y[train_idx], train_groups, c_grid, args.seed)
    scaler, model = fit_final(X[train_idx], y[train_idx], selected_c, args.seed)

    domains: dict[str, dict[str, Any]] = {}
    domain_indices = {"train": train_idx, "val": val_idx, "test": test_idx, "full": all_idx}
    for domain, idx in domain_indices.items():
        included = idx[y[idx] >= 0]
        X_inc = scaler.transform(X[included])
        pred = model.predict(X_inc)
        domains[domain] = classification_metrics(y[included], pred)

    # Reconstruct anchor ids from the score objects for the prediction audit.
    anchors_by_score: dict[str, list[float]] = {}
    for run in run_meta:
        score = str(run["score"])
        if score not in anchors_by_score:
            anchors_by_score[score] = list(load_score(dataset / score)["anchors"])

    predictions: list[dict[str, Any]] = []
    for run in run_meta:
        fold = str(run["fold"])
        start = int(run["x_offset"])
        end = start + int(run["x_length"])
        idx = np.arange(start, end, dtype=np.int64)
        included = idx[y[idx] >= 0]
        if len(included) == 0:
            continue
        pred = model.predict(scaler.transform(X[included]))
        probs = model.predict_proba(scaler.transform(X[included]))
        anchors = anchors_by_score[str(run["score"])]
        for row_idx, pred_id, prob in zip(included, pred, probs):
            local = int(row_idx - start)
            predictions.append({
                "run_id": run["run_id"],
                "score": run["score"],
                "midi_performance": run["midi_performance"],
                "fold": fold,
                "anchor": float(anchors[local]),
                "y_true": int(y[row_idx]),
                "y_pred": int(pred_id),
                "prob_NONE": round(float(prob[0]), 10),
                "prob_DOWN": round(float(prob[1]), 10),
                "prob_UP": round(float(prob[2]), 10),
            })

    model_payload = {
        "dataset_version": "m3-linear-v1",
        "classes": CLASS_NAMES,
        "class_ids": [0, 1, 2],
        "selected_C": float(selected_c),
        "seed": int(args.seed),
        "solver": "lbfgs",
        "class_weight": "balanced",
        "max_iter": 2000,
        "feature_names": feature_names,
        "scaler_mean": [float(x) for x in scaler.mean_],
        "scaler_scale": [float(x) for x in scaler.scale_],
        "coef": [[float(x) for x in row] for row in model.coef_],
        "intercept": [float(x) for x in model.intercept_],
    }
    summary = {
        "dataset_version": "m3-linear-v1",
        "model_family": "regularized_multinomial_logistic_regression",
        "selection": "train_only_score_group_cv",
        "selected_C": float(selected_c),
        "c_grid": c_grid,
        "cv": cv_rows,
        "domains": domains,
        "data": data_summary,
        "wall_clock_sec": round(time.time() - t0, 3),
        "generator_sha256": sha256_file(Path(__file__).resolve()),
    }

    dataset_npz = data_out / "linear_dataset.npz"
    runs_jsonl = data_out / "linear_runs.jsonl.gz"
    np.savez_compressed(dataset_npz, X=X, y=y, offsets=offsets)
    write_jsonl_gz(runs_jsonl, run_meta)

    predictions_path = data_out / "linear_predictions.jsonl.gz"
    write_jsonl_gz(predictions_path, predictions)
    model_path = out_dir / "linear_model.json"
    write_json(model_path, model_payload)
    summary_path = out_dir / "linear_summary.json"
    write_json(summary_path, summary)
    data_summary_path = out_dir / "linear_data_summary.json"
    write_json(data_summary_path, data_summary)
    feature_schema = {
        "dataset_version": "m3-linear-v1",
        "feature_count": len(feature_names),
        "feature_names": feature_names,
        "feature_sources": FEATURE_SOURCES,
        "source_leak": data_summary["feature_source_leak"],
        "v1_pass": data_summary["v1_pass"],
    }
    feature_schema_path = out_dir / "linear_feature_schema.json"
    write_json(feature_schema_path, feature_schema)

    table_rows = []
    per_class_rows = []
    confusion_rows = []
    for domain, met in domains.items():
        table_rows.extend([
            {"domain": domain, "scope": "micro", "metric": "F1", "value": met["micro_f1"]},
            {"domain": domain, "scope": "macro", "metric": "F1", "value": met["macro_f1"]},
            {"domain": domain, "scope": "accuracy", "metric": "accuracy", "value": met["accuracy"]},
        ])
        for class_name in CLASS_NAMES:
            vals = met["per_class"][class_name]
            per_class_rows.append({"domain": domain, "class": class_name, **vals})
            table_rows.append({"domain": domain, "scope": class_name, "metric": "F1", "value": vals["f1"]})
        for i, true_name in enumerate(CLASS_NAMES):
            for j, pred_name in enumerate(CLASS_NAMES):
                confusion_rows.append({
                    "domain": domain,
                    "true_class": true_name,
                    "pred_class": pred_name,
                    "count": int(met["confusion_matrix"][i][j]),
                })
    table_path = out_dir / "linear_table.csv"
    per_class_path = out_dir / "linear_per_class.csv"
    confusion_path = out_dir / "linear_confusion.csv"
    cv_path = out_dir / "linear_cv.csv"
    write_csv(table_path, table_rows, ["domain", "scope", "metric", "value"])
    write_csv(per_class_path, per_class_rows, ["domain", "class", "precision", "recall", "f1", "support"])
    write_csv(confusion_path, confusion_rows, ["domain", "true_class", "pred_class", "count"])
    write_csv(cv_path, cv_rows, ["C", "fold", "n_train", "n_val", "macro_f1", "micro_f1", "class_f1_NONE", "class_f1_DOWN", "class_f1_UP"])

    output_paths = [
        dataset_npz, runs_jsonl, predictions_path, model_path, summary_path, data_summary_path,
        feature_schema_path, table_path, per_class_path, confusion_path, cv_path,
    ]
    outputs = {relpath(path): sha256_file(path) for path in output_paths}
    manifest = {
        "dataset_version": "m3-linear-v1",
        "generator": {"path": "tools/m3_linear_baseline.py", "sha256": sha256_file(Path(__file__).resolve())},
        "inputs": {
            "dataset": relpath(dataset),
            "split": relpath(split_path),
            "split_raw_sha256": sha256_file(split_path),
            "m2_labels": relpath(labels_path),
            "m2_labels_sha256": sha256_file(labels_path),
            "m2_runs": relpath(runs_path),
            "m2_runs_sha256": sha256_file(runs_path),
        },
        "rules": {
            "domain": "36 M2 supervised scores / 271 runs",
            "classes": CLASS_NAMES,
            "change_policy": "M2 supervision_mask=0 rows excluded; no remap",
            "selection": "train_only_score_group_cv",
            "features": "round_b_features A/B/C, no printed-pedal-derived features",
            "replay_loss": False,
        },
        "outputs": outputs,
        "counts": {
            "runs": data_summary["supervised_runs"],
            "scores": data_summary["main_scores"],
            "rows": data_summary["row_count"],
            "included_rows": data_summary["included_row_count"],
            "excluded_rows": data_summary["excluded_row_count"],
            "included_counts": data_summary["included_counts"],
            "excluded_counts": data_summary["excluded_counts"],
            "selected_C": float(selected_c),
        },
        "environment": {
            "python_version": platform.python_version(),
            "platform": platform.platform(),
        },
    }
    manifest_path = out_dir / "linear_manifest.json"
    write_json(manifest_path, manifest)
    print(json.dumps({
        "status": "ok",
        "runs": data_summary["supervised_runs"],
        "scores": data_summary["main_scores"],
        "rows": data_summary["row_count"],
        "included_rows": data_summary["included_row_count"],
        "excluded_rows": data_summary["excluded_row_count"],
        "selected_C": selected_c,
        "test_micro_f1": domains["test"]["micro_f1"],
        "test_macro_f1": domains["test"]["macro_f1"],
        "v1_pass": data_summary["v1_pass"],
        "feature_source_leak": data_summary["feature_source_leak"],
        "wall_clock_sec": summary["wall_clock_sec"],
    }, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
