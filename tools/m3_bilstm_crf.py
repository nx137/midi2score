#!/usr/bin/env python
"""M3S-1：小型 BiLSTM-CRF（NONE/DOWN/UP）序列前置层。"""
from __future__ import annotations
import argparse, csv, gzip, hashlib, json, math, platform, random, sys, time
from pathlib import Path
from typing import Any
import numpy as np
import torch
import torch.nn as nn
from sklearn.metrics import confusion_matrix, f1_score, precision_recall_fscore_support

sys.path.insert(0, str(Path(__file__).resolve().parent))
from round_b_features import load_score  # noqa: E402

TAGS = 3
CLASS_NAMES = ["NONE", "DOWN", "UP"]
LABEL_TO_ID = {name: i for i, name in enumerate(CLASS_NAMES)}


def sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def sha256_file(path: Path) -> str:
    return sha256_bytes(path.read_bytes())


def relpath(path: Path) -> str:
    root = Path(__file__).resolve().parents[1]
    try:
        return path.resolve().relative_to(root.resolve()).as_posix()
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
    payload = "".join(json.dumps(row, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n" for row in rows).encode("utf-8")
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


def classification_metrics(y_true: np.ndarray, y_pred: np.ndarray) -> dict[str, Any]:
    labels = [0, 1, 2]
    p, r, f, s = precision_recall_fscore_support(y_true, y_pred, labels=labels, zero_division=0)
    return {
        "micro_f1": float(f1_score(y_true, y_pred, labels=labels, average="micro", zero_division=0)),
        "macro_f1": float(f1_score(y_true, y_pred, labels=labels, average="macro", zero_division=0)),
        "accuracy": float(np.mean(y_true == y_pred)) if len(y_true) else 0.0,
        "n": int(len(y_true)),
        "per_class": {name: {"precision": float(p[i]), "recall": float(r[i]), "f1": float(f[i]), "support": int(s[i])} for i, name in enumerate(CLASS_NAMES)},
        "confusion_matrix": confusion_matrix(y_true, y_pred, labels=labels).tolist(),
    }


class BiLSTMCRF(nn.Module):
    def __init__(self, input_dim: int = 53, hidden: int = 32, dropout: float = 0.2):
        super().__init__()
        self.lstm = nn.LSTM(input_dim, hidden, num_layers=1, bidirectional=True, batch_first=True)
        self.dropout = nn.Dropout(float(dropout))
        self.emission = nn.Linear(2 * hidden, TAGS)
        self.trans = nn.Parameter(torch.zeros(TAGS, TAGS))
        self.start = nn.Parameter(torch.zeros(TAGS))
        self.end = nn.Parameter(torch.zeros(TAGS))

    def emissions(self, x: torch.Tensor) -> torch.Tensor:
        h, _ = self.lstm(x)
        return self.emission(self.dropout(h))


def crf_nll(em: torch.Tensor, tags: torch.Tensor, mask: torch.Tensor, trans: torch.Tensor, start: torch.Tensor, end: torch.Tensor, class_weight: torch.Tensor | None = None) -> torch.Tensor:
    B, T, K = em.shape
    if class_weight is not None:
        em = em + torch.log(class_weight).view(1, 1, -1)
    score = start[tags[:, 0]] + em[:, 0, tags[:, 0]]
    for t in range(1, T):
        m = mask[:, t].float()
        score = score + m * (em[:, t, tags[:, t]] + trans[tags[:, t - 1], tags[:, t]])
    lengths = mask.sum(dim=1).long()
    last = tags[torch.arange(B), lengths - 1]
    score = score + end[last]
    alpha = start.unsqueeze(0) + em[:, 0]
    for t in range(1, T):
        nxt = torch.logsumexp(alpha.unsqueeze(2) + trans.unsqueeze(0), dim=1) + em[:, t]
        alpha = torch.where(mask[:, t].unsqueeze(1), nxt, alpha)
    log_z = torch.logsumexp(alpha + end.unsqueeze(0), dim=1)
    return (log_z - score).mean()


@torch.no_grad()
def viterbi(model: BiLSTMCRF, x: torch.Tensor, mask: torch.Tensor) -> list[int]:
    em = model.emissions(x.unsqueeze(0))[0]
    length = int(mask.sum().item())
    if length <= 0:
        return []
    score = model.start + em[0]
    back = torch.zeros((len(em), TAGS), dtype=torch.long)
    for t in range(1, length):
        vals = score.unsqueeze(1) + model.trans
        best, idx = vals.max(dim=0)
        score = best + em[t]
        back[t] = idx
    s = int(torch.argmax(score + model.end))
    tags = [s]
    for t in range(length - 1, 0, -1):
        s = int(back[t, s])
        tags.append(s)
    tags.reverse()
    return tags


def load_runs(dataset: Path, data_dir: Path) -> tuple[np.ndarray, list[dict[str, Any]]]:
    with np.load(data_dir / "linear_dataset.npz", allow_pickle=False) as z:
        X = z["X"]
        y = z["y"]
        offsets = z["offsets"]
    run_meta = read_jsonl_gz(data_dir / "linear_runs.jsonl.gz")
    return X, y, offsets, run_meta


def build_runs(dataset: Path, X: np.ndarray, y: np.ndarray, run_meta: list[dict[str, Any]]) -> list[dict[str, Any]]:
    anchors_by_score: dict[str, list[float]] = {}
    runs: list[dict[str, Any]] = []
    for meta in run_meta:
        score = str(meta["score"])
        if score not in anchors_by_score:
            anchors_by_score[score] = list(load_score(dataset / score)["anchors"])
        start = int(meta["x_offset"])
        length = int(meta["x_length"])
        y_part = y[start:start + length]
        valid = y_part >= 0
        X_part = X[start:start + length][valid]
        anchors = np.asarray(anchors_by_score[score], dtype=np.float64)[valid]
        runs.append({
            "run_id": str(meta["run_id"]),
            "score": score,
            "midi_performance": str(meta["midi_performance"]),
            "fold": str(meta["fold"]),
            "group": str(meta["group"]),
            "X": X_part.astype(np.float32),
            "y": y_part[valid].astype(np.int64),
            "anchors": anchors,
        })
    return runs


def fit_scaler(runs: list[dict[str, Any]]) -> tuple[np.ndarray, np.ndarray]:
    X = np.concatenate([run["X"] for run in runs], axis=0).astype(np.float64)
    mean = X.mean(axis=0)
    std = X.std(axis=0)
    std[std < 1e-8] = 1.0
    return mean, std


def scale_array(X: np.ndarray, mean: np.ndarray, std: np.ndarray) -> np.ndarray:
    return ((X.astype(np.float64) - mean) / std).astype(np.float32)


def make_chunks(runs: list[dict[str, Any]], mean: np.ndarray, std: np.ndarray, chunk: int) -> list[dict[str, Any]]:
    chunks: list[dict[str, Any]] = []
    for run in runs:
        x = scale_array(run["X"], mean, std)
        y = run["y"]
        for start in range(0, len(y), chunk):
            end = min(len(y), start + chunk)
            chunks.append({"run_id": run["run_id"], "start": start, "X": x[start:end], "y": y[start:end]})
    return chunks


def collate_chunks(batch: list[dict[str, Any]]) -> tuple[torch.Tensor, torch.Tensor, torch.Tensor]:
    max_len = max(len(item["y"]) for item in batch)
    B = len(batch)
    X = torch.zeros((B, max_len, 53), dtype=torch.float32)
    Y = torch.zeros((B, max_len), dtype=torch.long)
    M = torch.zeros((B, max_len), dtype=torch.bool)
    for i, item in enumerate(batch):
        n = len(item["y"])
        X[i, :n] = torch.from_numpy(item["X"])
        Y[i, :n] = torch.from_numpy(item["y"])
        M[i, :n] = True
    return X, Y, M


@torch.no_grad()
def eval_runs(model: BiLSTMCRF, mean: np.ndarray, std: np.ndarray, runs: list[dict[str, Any]]) -> tuple[np.ndarray, np.ndarray, list[dict[str, Any]]]:
    y_true: list[int] = []
    y_pred: list[int] = []
    predictions: list[dict[str, Any]] = []
    model.eval()
    for run in runs:
        x = torch.from_numpy(scale_array(run["X"], mean, std))
        mask = torch.ones(len(run["y"]), dtype=torch.bool)
        pred = np.asarray(viterbi(model, x, mask), dtype=np.int64)
        if len(pred) != len(run["y"]):
            raise RuntimeError(f"viterbi length mismatch for {run['run_id']}")
        y_true.extend(int(v) for v in run["y"])
        y_pred.extend(int(v) for v in pred)
        for anchor, true_id, pred_id in zip(run["anchors"], run["y"], pred):
            predictions.append({
                "run_id": run["run_id"], "score": run["score"], "midi_performance": run["midi_performance"],
                "fold": run["fold"], "anchor": float(anchor), "y_true": int(true_id), "y_pred": int(pred_id),
            })
    return np.asarray(y_true, dtype=np.int64), np.asarray(y_pred, dtype=np.int64), predictions


def class_weight_values(y_values: np.ndarray, mode: str) -> np.ndarray:
    counts = np.bincount(y_values.astype(np.int64), minlength=TAGS).astype(np.float64)
    total = float(counts.sum())
    if mode == "none":
        return np.ones(TAGS, dtype=np.float32)
    if mode == "sqrt":
        weights = np.sqrt(total / (np.maximum(counts, 1.0) * TAGS))
    elif mode == "balanced_clipped":
        weights = total / (np.maximum(counts, 1.0) * TAGS)
    else:
        raise ValueError(f"unknown class weight mode: {mode}")
    return np.clip(weights, 0.5, 5.0).astype(np.float32)


def train_model(
    inner_train: list[dict[str, Any]],
    inner_val: list[dict[str, Any]],
    *,
    hidden: int,
    dropout: float,
    chunk: int,
    batch_size: int,
    lr: float,
    epochs: int,
    patience: int,
    seed: int,
    class_weight_mode: str,
) -> tuple[BiLSTMCRF, np.ndarray, np.ndarray, list[dict[str, Any]], int, int]:
    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)
    torch.use_deterministic_algorithms(False)
    mean, std = fit_scaler(inner_train)
    chunks = make_chunks(inner_train, mean, std, chunk)
    class_weights_np = class_weight_values(np.concatenate([c["y"] for c in chunks]), class_weight_mode)
    class_weights = torch.from_numpy(class_weights_np)
    model = BiLSTMCRF(input_dim=53, hidden=hidden, dropout=dropout)
    optimizer = torch.optim.AdamW(model.parameters(), lr=lr, weight_decay=1e-4)
    order = list(range(len(chunks)))
    best_macro = -1.0
    best_state = None
    best_epoch = 0
    bad = 0
    history: list[dict[str, Any]] = []
    epochs_run = 0
    for epoch in range(1, epochs + 1):
        epochs_run = epoch
        model.train()
        random.shuffle(order)
        total_loss = 0.0
        n_batches = 0
        for start in range(0, len(order), batch_size):
            batch = [chunks[i] for i in order[start:start + batch_size]]
            X, Y, M = collate_chunks(batch)
            optimizer.zero_grad()
            emission = model.emissions(X)
            loss = crf_nll(emission, Y, M, model.trans, model.start, model.end, None if class_weight_mode == "none" else class_weights)
            loss.backward()
            torch.nn.utils.clip_grad_norm_(model.parameters(), 5.0)
            optimizer.step()
            total_loss += float(loss.detach())
            n_batches += 1
        y_val, p_val, _ = eval_runs(model, mean, std, inner_val)
        val_metrics = classification_metrics(y_val, p_val)
        row = {
            "epoch": epoch,
            "train_loss": total_loss / max(n_batches, 1),
            "inner_val_micro": val_metrics["micro_f1"],
            "inner_val_macro": val_metrics["macro_f1"],
            "inner_val_DOWN_f1": val_metrics["per_class"]["DOWN"]["f1"],
            "inner_val_UP_f1": val_metrics["per_class"]["UP"]["f1"],
            "class_weight_mode": class_weight_mode,
        }
        history.append(row)
        print(json.dumps(row, ensure_ascii=False), flush=True)
        if val_metrics["macro_f1"] > best_macro + 1e-6:
            best_macro = val_metrics["macro_f1"]
            best_epoch = epoch
            best_state = {k: v.detach().clone() for k, v in model.state_dict().items()}
            bad = 0
        else:
            bad += 1
            if bad >= patience:
                break
    if best_state is not None:
        model.load_state_dict(best_state)
    return model, mean, std, history, best_epoch, epochs_run


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dataset", type=Path, required=True)
    ap.add_argument("--data-dir", type=Path, required=True)
    ap.add_argument("--out-data", type=Path, required=True)
    ap.add_argument("--out-dir", type=Path, required=True)
    ap.add_argument("--hidden", type=int, default=32)
    ap.add_argument("--dropout", type=float, default=0.2)
    ap.add_argument("--chunk", type=int, default=256)
    ap.add_argument("--batch-size", type=int, default=32)
    ap.add_argument("--lr", type=float, default=1e-4)
    ap.add_argument("--class-weight-mode", choices=["none", "sqrt", "balanced_clipped"], default="sqrt")
    ap.add_argument("--epochs", type=int, default=100)
    ap.add_argument("--patience", type=int, default=10)
    ap.add_argument("--seed", type=int, default=20260101)
    args = ap.parse_args()

    t0 = time.time()
    dataset = args.dataset.resolve()
    data_dir = args.data_dir.resolve()
    out_data = args.out_data.resolve()
    out_dir = args.out_dir.resolve()
    out_data.mkdir(parents=True, exist_ok=True)
    out_dir.mkdir(parents=True, exist_ok=True)
    X, y, offsets, run_meta = load_runs(dataset, data_dir)
    runs = build_runs(dataset, X, y, run_meta)
    train = [r for r in runs if r["fold"] == "train"]
    val = [r for r in runs if r["fold"] == "val"]
    test = [r for r in runs if r["fold"] == "test"]
    inner_groups = set(sorted({r["group"] for r in train})[::5])
    inner_val = [r for r in train if r["group"] in inner_groups]
    inner_train = [r for r in train if r["group"] not in inner_groups]
    if len(inner_train) == 0 or len(inner_val) == 0:
        raise RuntimeError("inner train/val empty")

    model, mean, std, history, best_epoch, epochs_run = train_model(
        inner_train, inner_val,
        hidden=args.hidden,
        dropout=args.dropout,
        chunk=args.chunk,
        batch_size=args.batch_size,
        lr=args.lr,
        epochs=args.epochs,
        patience=args.patience,
        seed=args.seed,
        class_weight_mode=args.class_weight_mode,
    )

    domains: dict[str, dict[str, Any]] = {}
    domain_predictions: dict[str, list[dict[str, Any]]] = {}
    for name, subset in (("inner_train", inner_train), ("inner_val", inner_val), ("val", val), ("test", test), ("full", runs)):
        y_true, y_pred, pred_rows = eval_runs(model, mean, std, subset)
        domains[name] = classification_metrics(y_true, y_pred)
        domain_predictions[name] = pred_rows

    predictions = list(domain_predictions["full"])
    data_summary = {
        "dataset_version": "m3-bilstm-crf-v1",
        "scores": len({r["score"] for r in runs}),
        "runs": len(runs),
        "rows": int(sum(len(r["y"]) for r in runs)),
        "included_counts": {
            name: int(sum(np.sum(r["y"] == idx) for r in runs))
            for idx, name in enumerate(CLASS_NAMES)
        },
        "fold_runs": {fold: sum(1 for r in runs if r["fold"] == fold) for fold in ("train", "val", "test")},
        "inner_train_runs": len(inner_train),
        "inner_val_runs": len(inner_val),
        "inner_val_groups": sorted(inner_groups),
        "class_weight": args.class_weight_mode,
    }
    model_config = {
        "dataset_version": "m3-bilstm-crf-v1",
        "input_dim": 53,
        "hidden": args.hidden,
        "dropout": args.dropout,
        "layers": 1,
        "bidirectional": True,
        "tags": CLASS_NAMES,
        "chunk": args.chunk,
        "batch_size": args.batch_size,
        "lr": args.lr,
        "weight_decay": 1e-4,
        "clip_grad_norm": 5.0,
        "class_weight": args.class_weight_mode,
        "early_stop": "inner_val_macro_f1 patience=" + str(args.patience),
        "best_epoch": best_epoch,
        "epochs_run": epochs_run,
        "seed": args.seed,
        "optimizer": "AdamW",
    }
    summary = {
        "dataset_version": "m3-bilstm-crf-v1",
        "model_family": "small_bilstm_crf",
        "selection": "train_only_score_group_inner_validation",
        "domains": domains,
        "data": data_summary,
        "config": model_config,
        "wall_clock_sec": round(time.time() - t0, 3),
        "generator_sha256": sha256_file(Path(__file__).resolve()),
    }

    state_path = out_data / "best_model.pt"
    torch.save({"state_dict": model.state_dict(), "mean": mean, "std": std, "config": model_config}, state_path)
    predictions_path = out_data / "predictions.jsonl.gz"
    write_jsonl_gz(predictions_path, predictions)
    model_path = out_dir / "bilstm_crf_model.json"
    write_json(model_path, model_config)
    summary_path = out_dir / "bilstm_crf_summary.json"
    write_json(summary_path, summary)
    data_summary_path = out_dir / "bilstm_crf_data_summary.json"
    write_json(data_summary_path, data_summary)

    table_rows: list[dict[str, Any]] = []
    per_class_rows: list[dict[str, Any]] = []
    confusion_rows: list[dict[str, Any]] = []
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
    table_path = out_dir / "bilstm_crf_table.csv"
    per_class_path = out_dir / "bilstm_crf_per_class.csv"
    confusion_path = out_dir / "bilstm_crf_confusion.csv"
    history_path = out_dir / "bilstm_crf_training_curve.csv"
    write_csv(table_path, table_rows, ["domain", "scope", "metric", "value"])
    write_csv(per_class_path, per_class_rows, ["domain", "class", "precision", "recall", "f1", "support"])
    write_csv(confusion_path, confusion_rows, ["domain", "true_class", "pred_class", "count"])
    write_csv(history_path, history, ["epoch", "train_loss", "inner_val_micro", "inner_val_macro", "inner_val_DOWN_f1", "inner_val_UP_f1"])

    output_paths = [state_path, predictions_path, model_path, summary_path, data_summary_path, table_path, per_class_path, confusion_path, history_path]
    outputs = {relpath(path): sha256_file(path) for path in output_paths}
    manifest = {
        "dataset_version": "m3-bilstm-crf-v1",
        "generator": {"path": "tools/m3_bilstm_crf.py", "sha256": sha256_file(Path(__file__).resolve())},
        "inputs": {
            "dataset": relpath(dataset),
            "data_dir": relpath(data_dir),
            "out_data": relpath(out_data),
            "linear_dataset": relpath(data_dir / "linear_dataset.npz"),
            "linear_dataset_sha256": sha256_file(data_dir / "linear_dataset.npz"),
            "linear_runs": relpath(data_dir / "linear_runs.jsonl.gz"),
            "linear_runs_sha256": sha256_file(data_dir / "linear_runs.jsonl.gz"),
        },
        "rules": {
            "classes": CLASS_NAMES,
            "change_policy": "M3.1 included rows only; CHANGE excluded before sequence build",
            "chunk": args.chunk,
            "class_weight": args.class_weight_mode,
            "selection": "train_only_score_group_inner_validation",
            "test_used_once": True,
        },
        "outputs": outputs,
        "counts": data_summary,
    }
    manifest_path = out_dir / "bilstm_crf_manifest.json"
    write_json(manifest_path, manifest)
    print(json.dumps({
        "status": "ok",
        "runs": data_summary["runs"],
        "scores": data_summary["scores"],
        "rows": data_summary["rows"],
        "best_epoch": best_epoch,
        "epochs_run": epochs_run,
        "test_micro_f1": domains["test"]["micro_f1"],
        "test_macro_f1": domains["test"]["macro_f1"],
        "test_DOWN_f1": domains["test"]["per_class"]["DOWN"]["f1"],
        "test_UP_f1": domains["test"]["per_class"]["UP"]["f1"],
        "wall_clock_sec": summary["wall_clock_sec"],
    }, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
