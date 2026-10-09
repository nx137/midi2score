#!/usr/bin/env python
"""轮 B：canonical 域锚点级 LR(L2) 两分类（DOWN/UP）。"""
from __future__ import annotations

import argparse, csv, gc, hashlib, json, math, sys, tempfile
from pathlib import Path
import numpy as np
from scipy.optimize import minimize
from scipy.special import expit

sys.path.insert(0, str(Path(__file__).resolve().parent))
from canonical_domain import GRID, canonical_anchors, score_end  # noqa: E402
from inversion_consistency import parse_alignment, cc64_transitions, parse_score, snap, to_anchor  # noqa: E402
from inversion_baselines import f1_of  # noqa: E402
from b2_harmony_segments import features_once, predict  # noqa: E402
from b2_perlabel_bootstrap import per_label_counts  # noqa: E402
from round_b_features import FEATURE_NAMES, FEATURE_SOURCES, build_run_features, change_merge_count, load_score, make_stripped_score, score_note_features  # noqa: E402

TOLS = [0.0, 1.0, 2.0]
THRESHOLDS = [round(0.05 * i, 2) for i in range(1, 20)]
CLASS_WEIGHTS = ("none", "balanced")


def stable_hash_text(lines):
    h = hashlib.sha256()
    for line in lines:
        h.update((line + "\n").encode("utf-8"))
    return h.hexdigest()


def fit_scaler(X):
    X = np.asarray(X, dtype=np.float64)
    mean = X.mean(axis=0)
    std = X.std(axis=0)
    std[std < 1e-8] = 1.0
    return mean, std


def apply_scaler(X, mean, std):
    return (np.asarray(X, dtype=np.float64) - mean) / std


def sample_weight(y, mode):
    y = np.asarray(y, dtype=np.float64)
    n = len(y); npos = float(y.sum()); nneg = float(n - npos)
    if mode == "balanced" and npos > 0 and nneg > 0:
        return np.where(y > 0.5, n / (2.0 * npos), n / (2.0 * nneg))
    return np.ones(n, dtype=np.float64)

def fit_lr(X, y, weights, C=1.0):
    X = np.asarray(X, dtype=np.float64)
    y = np.asarray(y, dtype=np.float64)
    wgt = np.asarray(weights, dtype=np.float64)
    n, d = X.shape
    ws = float(wgt.sum())

    def obj(theta):
        w = theta[:d]; b = theta[d]
        z = X @ w + b
        p = expit(z)
        eps = 1e-12
        loss = -(wgt * (y * np.log(p + eps) + (1.0 - y) * np.log(1.0 - p + eps))).sum() / ws
        loss += 0.5 * float(np.dot(w, w)) / C
        gz = wgt * (p - y) / ws
        grad = np.empty(d + 1, dtype=np.float64)
        grad[:d] = X.T @ gz + w / C
        grad[d] = gz.sum()
        return loss, grad

    res = minimize(obj, np.zeros(d + 1, dtype=np.float64), method="L-BFGS-B", jac=True,
                   options={"maxiter": 60, "ftol": 1e-6, "gtol": 1e-4})
    return res.x[:d], float(res.x[d])


def predict_prob(X, w, b):
    return expit(np.asarray(X, dtype=np.float64) @ w + b)


def pred_set(run, p_down, p_up, tau_down, tau_up):
    out = set()
    for i, a in enumerate(run["anchors"]):
        if p_down[i] >= tau_down:
            out.add((a, "DOWN"))
        if p_up[i] >= tau_up:
            out.add((a, "UP"))
    return out


def evaluate_runs(runs, probs, tau_down, tau_up, tol=1.0):
    parts = {"DOWN": {"tp": 0, "fp": 0, "fn": 0, "wrong": 0, "n_pred": 0, "n_truth": 0},
             "UP": {"tp": 0, "fp": 0, "fn": 0, "wrong": 0, "n_pred": 0, "n_truth": 0}}
    for run, (pd, pu) in zip(runs, probs):
        pred = pred_set(run, pd, pu, tau_down, tau_up)
        c = per_label_counts(pred, run["truth"], tol)
        for lab in ("DOWN", "UP"):
            for k in parts[lab]:
                parts[lab][k] += c[lab][k]
    return summarize_counts(parts)


def summarize_counts(parts):
    out = {}
    for lab in ("DOWN", "UP"):
        c = parts[lab]
        p = c["tp"] / c["n_pred"] if c["n_pred"] else 0.0
        r = c["tp"] / c["n_truth"] if c["n_truth"] else 0.0
        out[lab] = {**c, "P": p, "R": r, "F1": 2 * p * r / (p + r) if (p + r) else 0.0}
    tp = out["DOWN"]["tp"] + out["UP"]["tp"]
    fp = out["DOWN"]["fp"] + out["UP"]["fp"]
    fn = out["DOWN"]["fn"] + out["UP"]["fn"]
    wrong = out["DOWN"]["wrong"] + out["UP"]["wrong"]
    n_pred = out["DOWN"]["n_pred"] + out["UP"]["n_pred"]
    n_truth = out["DOWN"]["n_truth"] + out["UP"]["n_truth"]
    p = tp / n_pred if n_pred else 0.0
    r = tp / n_truth if n_truth else 0.0
    out["micro"] = {"tp": tp, "fp": fp, "fn": fn, "wrong": wrong, "n_pred": n_pred, "n_truth": n_truth,
                    "P": p, "R": r, "F1": 2 * p * r / (p + r) if (p + r) else 0.0}
    return out


def micro_f1_from_label_counts(counts):
    tp = counts["DOWN"]["tp"] + counts["UP"]["tp"]
    fp = counts["DOWN"]["fp"] + counts["UP"]["fp"]
    fn = counts["DOWN"]["fn"] + counts["UP"]["fn"]
    return 2 * tp / (2 * tp + fp + fn) if (2 * tp + fp + fn) else 0.0


def bootstrap_diff(rows, counts_a, counts_b, boot, seed):
    scores = sorted({r["score"] for r in rows})
    by = {s: [i for i, r in enumerate(rows) if r["score"] == s] for s in scores}
    rng = np.random.default_rng(seed)
    diffs = []
    for _ in range(boot):
        sample = rng.choice(scores, size=len(scores), replace=True)
        idx = [i for s in sample for i in by[s]]
        ca = {"DOWN": {"tp":0,"fp":0,"fn":0}, "UP": {"tp":0,"fp":0,"fn":0}}
        cb = {"DOWN": {"tp":0,"fp":0,"fn":0}, "UP": {"tp":0,"fp":0,"fn":0}}
        for i in idx:
            for lab in ("DOWN", "UP"):
                for k in ("tp", "fp", "fn"):
                    ca[lab][k] += counts_a[i][lab][k]
                    cb[lab][k] += counts_b[i][lab][k]
        diffs.append(micro_f1_from_label_counts(ca) - micro_f1_from_label_counts(cb))
    return {"mean_diff": float(np.mean(diffs)), "ci95_low": float(np.percentile(diffs, 2.5)),
            "ci95_high": float(np.percentile(diffs, 97.5)), "p_gt_0": float(np.mean(np.asarray(diffs) > 0))}

def fit_and_prob(train_runs, valid_runs, label, weight_mode, feature_key="X"):
    Xtr = np.concatenate([r[feature_key] for r in train_runs], axis=0)
    ytr = np.concatenate([r["y_" + label] for r in train_runs], axis=0)
    mean, std = fit_scaler(Xtr)
    Xtr = apply_scaler(Xtr, mean, std)
    w, b = fit_lr(Xtr, ytr, sample_weight(ytr, weight_mode), C=1.0)
    out = []
    for r in valid_runs:
        Xv = apply_scaler(r[feature_key], mean, std)
        out.append(predict_prob(Xv, w, b))
    return out, (mean, std, w, b)


def score_model_thresholds(runs, probs, tol=1.0):
    best = None
    for td in THRESHOLDS:
        for tu in THRESHOLDS:
            m = evaluate_runs(runs, probs, td, tu, tol=tol)["micro"]["F1"]
            key = (m, -abs(td - 0.5) - abs(tu - 0.5), -td, -tu)
            if best is None or key > best[0]:
                best = (key, td, tu)
    return best[1], best[2], best[0][0]

def build_all_runs(dataset, split_path, ann_path, tmp_dir, limit_scores=0):
    D = Path(dataset)
    split = json.loads(Path(split_path).read_text(encoding="utf-8"))
    ann = json.loads(Path(ann_path).read_text(encoding="utf-8")) if Path(ann_path).is_file() else {}
    from lxml import etree
    main_scores = set(split["main_scores"])
    repeat = {s for s in main_scores if etree.parse(str(D / s)).getroot().xpath(".//*[local-name()='repeat']")}
    score_cache = {}
    v1_score_cache = {}
    seen_scores = set()
    runs = []
    v1_bad = []
    v1_orig_hash = hashlib.sha256()
    v1_strip_hash = hashlib.sha256()
    v3_counts_test = {"tp": 0, "fp": 0, "fn": 0, "wrong": 0, "n_pred": 0, "n_truth": 0}
    for p in split["per_performance"]:
        xml = p["xml_score"]
        if xml not in main_scores or xml in repeat:
            continue
        if limit_scores and xml not in seen_scores and len(seen_scores) >= limit_scores:
            continue
        seen_scores.add(xml)
        al = D / p["alignment_path"] if p["alignment_path"] else None
        midi = D / p["midi_performance"]
        if not (al and al.is_file() and midi.is_file()):
            continue
        if xml not in score_cache:
            score_cache[xml] = load_score(D / xml)
        score = score_cache[xml]
        seq = sorted((o, score["notes"][b]["pos"]) for b, _, o in parse_alignment(al) if b in score["notes"])
        if len(seq) < 2:
            continue
        truth = {(snap(o), "DOWN" if k == "start" else "UP") for _, o, k in score["pedals"]}
        if not truth:
            continue
        aset = set(score["anchors"])
        if any(a not in aset for a, _ in truth):
            return None, {"error": "truth_outside_canonical", "score": xml, "perf": p["midi_performance"]}
        X, names, meta = build_run_features(score, midi, seq, delta_mode="score_grid", ann=ann.get(p["midi_performance"]))
        X_annot, _, _ = build_run_features(score, midi, seq, delta_mode="performance_beats", ann=ann.get(p["midi_performance"]))
        y_down = np.asarray([(a, "DOWN") in truth for a in score["anchors"]], dtype=np.int8)
        y_up = np.asarray([(a, "UP") in truth for a in score["anchors"]], dtype=np.int8)
        if xml not in v1_score_cache:
            stripped = make_stripped_score(D / xml, tmp_dir)
            score_s = load_score(D / xml, stripped)
            B_orig, _ = score_note_features(score)
            B_strip, _ = score_note_features(score_s)
            v1_score_cache[xml] = (score_s, B_orig, B_strip, np.array_equal(B_orig, B_strip))
        score_s, B_orig, B_strip, b_equal = v1_score_cache[xml]
        seq_s = sorted((o, score_s["notes"][b]["pos"]) for b, _, o in parse_alignment(al) if b in score_s["notes"])
        seq_equal = (seq == seq_s)
        v1_orig_hash.update(B_orig.tobytes()); v1_strip_hash.update(B_strip.tobytes())
        v1_orig_hash.update(repr(seq).encode("utf-8")); v1_strip_hash.update(repr(seq_s).encode("utf-8"))
        if not (b_equal and seq_equal):
            v1_bad.append([xml, p["midi_performance"], {"B_equal": bool(b_equal), "seq_equal": bool(seq_equal)}])
        b2 = set()
        F = features_once(D / xml, end=score["end"])
        if F is not None:
            anchors_b2, feats, truth_b2, span_b2, dpcs, bass_chg, meas = F
            starts = []
            for t, kind in cc64_transitions(midi):
                if kind != "start":
                    continue
                got = to_anchor(t, seq, [])
                if got is not None and snap(got[0]) in aset:
                    starts.append(snap(got[0]))
            b2 = predict(anchors_b2, span_b2, dpcs, bass_chg, meas, starts, 3)
            b2 = {x for x in b2 if x[0] in aset}
            if p["fold"] == "test":
                c = per_label_counts(b2, truth, 1.0)
                for lab in ("DOWN", "UP"):
                    for k in v3_counts_test:
                        v3_counts_test[k] += c[lab][k]
        inv = set()
        for t, kind in cc64_transitions(midi):
            got = to_anchor(t, seq, [])
            if got is not None and snap(got[0]) in aset:
                inv.add((snap(got[0]), "DOWN" if kind == "start" else "UP"))
        bp2 = {(a, "DOWN") for i, a in enumerate(score["anchors"]) if i % 8 == 0}
        bp4 = {(a, "DOWN") for i, a in enumerate(score["anchors"]) if i % 16 == 0}
        baseline_counts = {
            "inversion_B1": per_label_counts(inv, truth, 1.0),
            "B2_K3": per_label_counts(b2, truth, 1.0),
            "beat_periodic_2": per_label_counts(bp2, truth, 1.0),
            "beat_periodic_4": per_label_counts(bp4, truth, 1.0),
        }
        runs.append({"score": xml, "perf": p["midi_performance"], "fold": p["fold"],
                     "group": split["score_meta"][xml]["group"], "anchors": score["anchors"],
                     "X": X, "X_annot": X_annot, "y_DOWN": y_down, "y_UP": y_up, "truth": truth,
                     "baseline_counts": baseline_counts,
                     "meta": {"feature_names": names, "sources": FEATURE_SOURCES},
                     "change_pairs": change_merge_count(score)})
    out = {"runs": runs, "v1_equal": not v1_bad, "v1_bad": v1_bad,
           "v1_orig_hash": v1_orig_hash.hexdigest(), "v1_strip_hash": v1_strip_hash.hexdigest(),
           "v3_test_counts": v3_counts_test, "n_scores": len({r["score"] for r in runs})}
    return out, None

def reference_keys(dataset, split_path):
    D = Path(dataset)
    split = json.loads(Path(split_path).read_text(encoding="utf-8"))
    from lxml import etree
    main_scores = set(split["main_scores"])
    repeat = {s for s in main_scores if etree.parse(str(D / s)).getroot().xpath(".//*[local-name()='repeat']")}
    lines = []
    for p in split["per_performance"]:
        xml = p["xml_score"]
        if xml not in main_scores or xml in repeat:
            continue
        al = D / p["alignment_path"] if p["alignment_path"] else None
        midi = D / p["midi_performance"]
        if not (al and al.is_file() and midi.is_file()):
            continue
        score = load_score(D / xml)
        seq = sorted((o, score["notes"][b]["pos"]) for b, _, o in parse_alignment(al) if b in score["notes"])
        if len(seq) < 2 or not score["pedals"]:
            continue
        truth = {(snap(o), "DOWN" if k == "start" else "UP") for _, o, k in score["pedals"]}
        if not truth:
            continue
        for a in score["anchors"]:
            lines.append(f"{xml}\t{a:.6f}")
    return stable_hash_text(lines), len(lines)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dataset", type=Path, default=Path("data/asap-dataset"))
    ap.add_argument("--split", type=Path, default=Path("evidence/R1/G1-split/split_v1.json"))
    ap.add_argument("--out-dir", type=Path, default=Path("results/E1/domain_unified"))
    ap.add_argument("--annotation-json", type=Path, default=Path("data/asap-dataset/asap_annotations.json"))
    ap.add_argument("--boot", type=int, default=10000)
    ap.add_argument("--seed", type=int, default=20260101)
    ap.add_argument("--limit-scores", type=int, default=0)
    ap.add_argument("--smoke", action="store_true")
    args = ap.parse_args()
    tmp_dir = args.out_dir / "_v1_stripped_xml"
    built, err = build_all_runs(args.dataset, args.split, args.annotation_json, tmp_dir, limit_scores=args.limit_scores)
    if err:
        print(json.dumps(err, ensure_ascii=False)); return 2
    runs = built["runs"]
    print(f"runs={len(runs)} scores={built['n_scores']} V1_equal={built['v1_equal']} v1_bad={len(built['v1_bad'])}")
    if not built["v1_equal"]:
        print(json.dumps({"V1": "FAIL", "bad": built["v1_bad"]}, ensure_ascii=False)); return 3
    if args.smoke:
        print(json.dumps({"smoke": True, "runs": len(runs), "v1_equal": built["v1_equal"], "v3_test_counts": built["v3_test_counts"]}, ensure_ascii=False))
        return 0
    train = [r for r in runs if r["fold"] == "train"]
    val = [r for r in runs if r["fold"] == "val"]
    test = [r for r in runs if r["fold"] == "test"]
    groups = sorted({r["group"] for r in train})
    fold_id = {g: i % 5 for i, g in enumerate(groups)}
    cv = {}
    for mode in CLASS_WEIGHTS:
        fold_scores = []
        for k in range(5):
            tr = [r for r in train if fold_id.get(r["group"]) != k]
            va = [r for r in train if fold_id.get(r["group"]) == k]
            pd, _ = fit_and_prob(tr, va, "DOWN", mode)
            pu, _ = fit_and_prob(tr, va, "UP", mode)
            fold_scores.append(evaluate_runs(va, list(zip(pd, pu)), 0.5, 0.5, tol=1.0)["micro"]["F1"])
        cv[mode] = {"fold_f1_at_1": fold_scores, "mean_f1_at_1": float(np.mean(fold_scores))}
        print("CV", mode, cv[mode])
    selected = max(CLASS_WEIGHTS, key=lambda m: (cv[m]["mean_f1_at_1"], m == "none"))
    base = {}
    for mode in CLASS_WEIGHTS:
        pd, packd = fit_and_prob(train, val, "DOWN", mode)
        pu, packu = fit_and_prob(train, val, "UP", mode)
        td, tu, val_f1 = score_model_thresholds(val, list(zip(pd, pu)), tol=1.0)
        base[mode] = {"w_down": packd, "w_up": packu, "thresholds": (td, tu), "val_f1": val_f1}
        print("thresholds", mode, td, tu, val_f1)
    table = []
    lr_counts_test = []
    lr_counts_full = []
    for mode in CLASS_WEIGHTS:
        pack = base[mode]
        pd, pu = [], []
        for r in test:
            pd.append(predict_prob(apply_scaler(r["X"], pack["w_down"][0], pack["w_down"][1]), pack["w_down"][2], pack["w_down"][3]))
            pu.append(predict_prob(apply_scaler(r["X"], pack["w_up"][0], pack["w_up"][1]), pack["w_up"][2], pack["w_up"][3]))
        probs = list(zip(pd, pu))
        if mode == selected:
            lr_counts_test = [per_label_counts(pred_set(r, pd[i], pu[i], pack["thresholds"][0], pack["thresholds"][1]), r["truth"], 1.0) for i, r in enumerate(test)]
        for tmode, (td, tu) in (("selected", pack["thresholds"]), ("0.5", (0.5, 0.5))):
            m = evaluate_runs(test, probs, td, tu, tol=1.0)
            for scope in ("micro", "DOWN", "UP"):
                table.append({"domain": "test", "method": f"LR_{mode}", "threshold": tmode, "scope": scope, **m[scope]})
        trfull = train + val
        pdd, packd2 = fit_and_prob(trfull, runs, "DOWN", mode)
        puu, packu2 = fit_and_prob(trfull, runs, "UP", mode)
        probs_full = list(zip(pdd, puu))
        if mode == selected:
            lr_counts_full = [per_label_counts(pred_set(r, pdd[i], puu[i], pack["thresholds"][0], pack["thresholds"][1]), r["truth"], 1.0) for i, r in enumerate(runs)]
        for tmode, (td, tu) in (("selected", pack["thresholds"]), ("0.5", (0.5, 0.5))):
            m = evaluate_runs(runs, probs_full, td, tu, tol=1.0)
            for scope in ("micro", "DOWN", "UP"):
                table.append({"domain": "full", "method": f"LR_{mode}", "threshold": tmode, "scope": scope, **m[scope]})
    # A_annotation 对照：只使用 selected class_weight；阈值仍只在 val 选。
    pd_a, packd_a = fit_and_prob(train, val, "DOWN", selected, feature_key="X_annot")
    pu_a, packu_a = fit_and_prob(train, val, "UP", selected, feature_key="X_annot")
    ta_d, ta_u, _ = score_model_thresholds(val, list(zip(pd_a, pu_a)), tol=1.0)
    pd_t, pu_t = [], []
    for r in test:
        pd_t.append(predict_prob(apply_scaler(r["X_annot"], packd_a[0], packd_a[1]), packd_a[2], packd_a[3]))
        pu_t.append(predict_prob(apply_scaler(r["X_annot"], packu_a[0], packu_a[1]), packu_a[2], packu_a[3]))
    m = evaluate_runs(test, list(zip(pd_t, pu_t)), ta_d, ta_u, tol=1.0)
    for scope in ("micro", "DOWN", "UP"):
        table.append({"domain": "test", "method": "LR_annotation_beats", "threshold": "selected", "scope": scope, **m[scope]})
    trfull = train + val
    pd_f, packd_f = fit_and_prob(trfull, runs, "DOWN", selected, feature_key="X_annot")
    pu_f, packu_f = fit_and_prob(trfull, runs, "UP", selected, feature_key="X_annot")
    m = evaluate_runs(runs, list(zip(pd_f, pu_f)), ta_d, ta_u, tol=1.0)
    for scope in ("micro", "DOWN", "UP"):
        table.append({"domain": "full", "method": "LR_annotation_beats", "threshold": "selected", "scope": scope, **m[scope]})
    # V5：只对 |Δmicro F1| >= 0.05 的方法对做 bootstrap；<0.05 写“不可分辨”。
    v5 = []
    for domain, rows, counts_a in (("test", test, lr_counts_test), ("full", runs, lr_counts_full)):
        f1_a = micro_f1_from_label_counts({
            "DOWN": {"tp": sum(c["DOWN"]["tp"] for c in counts_a), "fp": sum(c["DOWN"]["fp"] for c in counts_a), "fn": sum(c["DOWN"]["fn"] for c in counts_a)},
            "UP": {"tp": sum(c["UP"]["tp"] for c in counts_a), "fp": sum(c["UP"]["fp"] for c in counts_a), "fn": sum(c["UP"]["fn"] for c in counts_a)}})
        for method in ("inversion_B1", "B2_K3", "beat_periodic_2", "beat_periodic_4"):
            counts_b = [r["baseline_counts"][method] for r in rows]
            f1_b = micro_f1_from_label_counts({
                "DOWN": {"tp": sum(c["DOWN"]["tp"] for c in counts_b), "fp": sum(c["DOWN"]["fp"] for c in counts_b), "fn": sum(c["DOWN"]["fn"] for c in counts_b)},
                "UP": {"tp": sum(c["UP"]["tp"] for c in counts_b), "fp": sum(c["UP"]["fp"] for c in counts_b), "fn": sum(c["UP"]["fn"] for c in counts_b)}})
            point = f1_a - f1_b
            rec = {"domain": domain, "a": "LR_balanced", "b": method, "micro_f1_a": f1_a, "micro_f1_b": f1_b, "point_diff": point}
            if abs(point) >= 0.05:
                rec["status"] = "bootstrap"
                rec.update(bootstrap_diff(rows, counts_a, counts_b, args.boot, args.seed))
            else:
                rec["status"] = "不可分辨（Δ<0.05，不做 CI）"
            v5.append(rec)
    keys = stable_hash_text([f"{r['score']}\t{a:.6f}" for r in runs for a in r["anchors"]])
    ref_keys, ref_count = reference_keys(args.dataset, args.split)
    v2_pass = keys == ref_keys
    canon = json.loads((args.out_dir / "E1_main_canonical.json").read_text(encoding="utf-8"))
    b2_row = next(x for x in canon["table"] if x["domain"] == "test" and x["method"] == "B2_K3" and x["tol"] == 1.0 and x["scope"] == "micro")
    v3_pass = all(int(built["v3_test_counts"][k]) == int(b2_row[k]) for k in ("tp", "fp", "fn", "wrong", "n_pred", "n_truth"))
    out = {"selected_class_weight": selected, "cv": cv, "class_weight_tiers": list(CLASS_WEIGHTS),
           "thresholds": {m: list(base[m]["thresholds"]) for m in CLASS_WEIGHTS}, "annotation_thresholds": [ta_d, ta_u],
           "table": table,
           "v1": {"equal": built["v1_equal"], "orig_sha256": built["v1_orig_hash"], "strip_sha256": built["v1_strip_hash"], "bad": built["v1_bad"]},
           "v2": {"pass": v2_pass, "feature_keys_sha256": keys, "reference_keys_sha256": ref_keys, "reference_anchor_rows": ref_count},
           "v3": {"pass": v3_pass, "recomputed": built["v3_test_counts"], "recorded": {k: b2_row[k] for k in ("tp","fp","fn","wrong","n_pred","n_truth")}},
           "change_pairs_total": int(sum(r["change_pairs"] for r in runs)),
           "v5": v5, "bootstrap": {"boot": args.boot, "seed": args.seed, "generator": "tools/round_b_lr.py"},
           "feature_names": FEATURE_NAMES, "feature_sources": FEATURE_SOURCES}
    for row in canon["table"]:
        if row["tol"] == 1.0:
            out["table"].append({"domain": row["domain"], "method": row["method"], "threshold": "na", "scope": row["scope"], **{k: row[k] for k in ("n_pred","n_truth","tp","fp","fn","wrong","P","R","F1")}})
    args.out_dir.mkdir(parents=True, exist_ok=True)
    (args.out_dir / "LR_model.json").write_text(json.dumps(out, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    with (args.out_dir / "LR_model.csv").open("w", encoding="utf-8", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=["domain","method","threshold","scope","n_pred","n_truth","tp","fp","fn","wrong","P","R","F1"])
        w.writeheader(); w.writerows([{k: r.get(k) for k in w.fieldnames} for r in out["table"]])
    print(json.dumps({"selected_class_weight": selected, "v1": out["v1"], "v2": out["v2"], "v3": out["v3"], "change_pairs_total": out["change_pairs_total"]}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
