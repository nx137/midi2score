#!/usr/bin/env python
"""统一评测域复算：canonical [0, score_end) 锚点栅格。

不覆盖旧域产物（D-0068）。输出 results/E1/domain_unified/。
"""
from __future__ import annotations

import argparse, csv, json, sys
from pathlib import Path
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
from canonical_domain import GRID as CANON_GRID, anchor_set, canonical_anchors, score_end  # noqa: E402
from inversion_consistency import GRID, cc64_transitions, parse_alignment, parse_score, snap, to_anchor  # noqa: E402
from inversion_baselines import f1_of  # noqa: E402
from b2_harmony_segments import features_once, predict  # noqa: E402
from b1_dejitter import dejitter  # noqa: E402
from b2_perlabel_bootstrap import per_label_counts  # noqa: E402

TOLS = [0.0, 1.0, 2.0]
METHODS = ("inversion_B1", "B2_K3", "beat_periodic_2", "beat_periodic_4")


def labels_from_snapped(seq_pairs, midi, aset):
    out = set()
    for t, kind in cc64_transitions(midi):
        got = to_anchor(t, seq_pairs, [])
        if got is None:
            continue
        a = snap(got[0])
        if a in aset:
            out.add((a, "DOWN" if kind == "start" else "UP"))
    return out


def periodic_down(anchors, n_beats):
    step = int(round(float(n_beats) / GRID))
    return {(a, "DOWN") for i, a in enumerate(anchors) if i % step == 0}


def aggregate(per_run, method, tol, fold=None):
    sel = [x for x in per_run if fold is None or x["fold"] == fold]
    out = {}
    for lab in ("DOWN", "UP"):
        tp = sum(x["counts"][method][f"tol{tol}"][lab]["tp"] for x in sel)
        fp = sum(x["counts"][method][f"tol{tol}"][lab]["fp"] for x in sel)
        fn = sum(x["counts"][method][f"tol{tol}"][lab]["fn"] for x in sel)
        wr = sum(x["counts"][method][f"tol{tol}"][lab]["wrong"] for x in sel)
        n_pred = sum(x["counts"][method][f"tol{tol}"][lab]["n_pred"] for x in sel)
        n_truth = sum(x["counts"][method][f"tol{tol}"][lab]["n_truth"] for x in sel)
        p = tp / n_pred if n_pred else 0.0
        r = tp / n_truth if n_truth else 0.0
        out[lab] = {"n_pred": n_pred, "n_truth": n_truth, "tp": tp, "fp": fp, "fn": fn, "wrong": wr,
                    "P": p, "R": r, "F1": 2 * p * r / (p + r) if (p + r) else 0.0}
    tp = out["DOWN"]["tp"] + out["UP"]["tp"]
    n_pred = out["DOWN"]["n_pred"] + out["UP"]["n_pred"]
    n_truth = out["DOWN"]["n_truth"] + out["UP"]["n_truth"]
    fp = n_pred - tp
    fn = n_truth - tp
    wrong = out["DOWN"]["wrong"] + out["UP"]["wrong"]
    p = tp / n_pred if n_pred else 0.0
    r = tp / n_truth if n_truth else 0.0
    out["micro"] = {"n_pred": n_pred, "n_truth": n_truth, "tp": tp, "fp": fp, "fn": fn, "wrong": wrong,
                    "P": p, "R": r, "F1": 2 * p * r / (p + r) if (p + r) else 0.0}
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dataset", type=Path, default=Path("data/asap-dataset"))
    ap.add_argument("--split", type=Path, default=Path("evidence/R1/G1-split/split_v1.json"))
    ap.add_argument("--out-dir", type=Path, default=Path("results/E1/domain_unified"))
    args = ap.parse_args()
    D = args.dataset
    split = json.loads(args.split.read_text(encoding="utf-8"))
    main_scores = set(split["main_scores"])
    from lxml import etree
    repeat = {s for s in main_scores if etree.parse(str(D / s)).getroot().xpath(".//*[local-name()='repeat']")}
    ann_path = D / "asap_annotations.json"
    ann = json.loads(ann_path.read_text(encoding="utf-8")) if ann_path.is_file() else {}
    fold_of = {p["xml_score"]: p["fold"] for p in split["per_performance"]}
    group_of = {s: split["score_meta"][s]["group"] for s in split["main_scores"]}
    score_cache, end_cache, feat_cache = {}, {}, {}
    per_run = []
    skipped = {"alignment_or_midi": 0, "seq_lt_2": 0, "no_truth": 0, "truth_outside_domain": 0}
    for p in split["per_performance"]:
        xml = p["xml_score"]
        if xml not in main_scores or xml in repeat:
            continue
        al = D / p["alignment_path"] if p["alignment_path"] else None
        midi = D / p["midi_performance"]
        if not (al and al.is_file() and midi.is_file()):
            skipped["alignment_or_midi"] += 1
            continue
        if xml not in score_cache:
            score_cache[xml] = parse_score(D / xml)
            end_cache[xml] = score_end(D / xml)
        notes, pedals = score_cache[xml]
        seq = sorted((o, notes[b][1]) for b, _, o in parse_alignment(al) if b in notes)
        if len(seq) < 2:
            skipped["seq_lt_2"] += 1
            continue
        truth = {(snap(o), "DOWN" if k == "start" else "UP") for _, o, k in pedals}
        if not truth:
            skipped["no_truth"] += 1
            continue
        end = end_cache[xml]
        anchors = canonical_anchors(end)
        aset = set(anchors)
        outside = [x for x in truth if x[0] not in aset]
        if outside:
            skipped["truth_outside_domain"] += 1
            truth = {x for x in truth if x[0] in aset}
        if not truth:
            continue
        inv = labels_from_snapped(seq, midi, aset)
        if xml not in feat_cache:
            feat_cache[xml] = features_once(D / xml, end=end)
        F = feat_cache[xml]
        if F is None:
            continue
        anchors_b2, feats, truth_b2, span_b2, dpcs, bass_chg, meas = F
        starts = [a for a, lab in labels_from_snapped(seq, midi, aset) if lab == "DOWN"]
        b2 = predict(anchors_b2, span_b2, dpcs, bass_chg, meas, starts, 3)
        b2 = {x for x in b2 if x[0] in aset}
        methods = {
            "inversion_B1": inv,
            "B2_K3": b2,
            "beat_periodic_2": periodic_down(anchors, 2),
            "beat_periodic_4": periodic_down(anchors, 4),
        }
        counts = {}
        for method, pred in methods.items():
            counts[method] = {}
            for tol in TOLS:
                pl = per_label_counts(pred, truth, tol)
                if tol <= 0:
                    for lab in ("DOWN", "UP"):
                        pl[lab]["wrong"] = 0
                m = f1_of(pred, truth, tol)
                mtp = pl["DOWN"]["tp"] + pl["UP"]["tp"]
                mfp = pl["DOWN"]["fp"] + pl["UP"]["fp"]
                mfn = pl["DOWN"]["fn"] + pl["UP"]["fn"]
                mw = pl["DOWN"]["wrong"] + pl["UP"]["wrong"]
                assert (mtp, mfp, mfn, mw) == (m["tp"], m["fp"], m["fn"], m["wrong"]), (xml, method, tol)
                counts[method][f"tol{tol}"] = pl
        per_run.append({"score": xml, "perf": p["midi_performance"], "fold": fold_of.get(xml),
                        "group": group_of.get(xml), "scoreend": end, "counts": counts,
                        "truth": truth, "methods": methods})
    print(f"可用 runs = {len(per_run)}; skipped = {skipped}")

    # B1 CV under canonical domain; only report argmax, no retuning/overwriting.
    train = [x for x in per_run if x["fold"] == "train"]
    groups = sorted({x["group"] for x in train})
    fold_id = {g: i % 5 for i, g in enumerate(groups)}
    b1_cv = []
    for dmin_grid in (0, 1, 2, 4, 8):
        dmin_beats = dmin_grid * GRID
        per_d = []
        for x in train:
            p = next(q for q in split["per_performance"] if q["xml_score"] == x["score"] and q["midi_performance"] == x["perf"])
            beats = ann.get(x["perf"], {}).get("performance_beats")
            if not beats or len(beats) < 2:
                continue
            al = D / p["alignment_path"]
            notes, _ = score_cache[x["score"]]
            seq = sorted((o, notes[b][1]) for b, _, o in parse_alignment(al) if b in notes)
            ev = dejitter(cc64_transitions(D / p["midi_performance"]), beats, dmin_beats)
            pred = labels_from_snapped(seq, D / p["midi_performance"], set(canonical_anchors(x["scoreend"]))) if dmin_grid == 0 else set()
            if dmin_grid != 0:
                for t, kind in ev:
                    got = to_anchor(t, seq, [])
                    if got is not None:
                        a = snap(got[0])
                        if a in set(canonical_anchors(x["scoreend"])):
                            pred.add((a, "DOWN" if kind == "start" else "UP"))
            per_d.append((x["group"], f1_of(pred, x["truth"], 1.0)))
        f1s = []
        for k in range(5):
            sel = [m for g, m in per_d if fold_id.get(g) == k]
            tp = sum(m["tp"] for m in sel); fp = sum(m["fp"] for m in sel); fn = sum(m["fn"] for m in sel)
            f1s.append(2 * tp / (2 * tp + fp + fn) if (2 * tp + fp + fn) else 0.0)
        b1_cv.append({"d_min_grid": dmin_grid, "d_min_beats": dmin_beats,
                      "mean_f1_at_1": float(np.mean(f1s)) if f1s else 0.0,
                      "fold_f1_at_1": f1s})
    best_b1 = max(b1_cv, key=lambda x: (x["mean_f1_at_1"], -x["d_min_grid"])) if b1_cv else None

    out = args.out_dir
    out.mkdir(parents=True, exist_ok=True)
    table = []
    for domain_name, fold in (("test", "test"), ("full", None)):
        for method in METHODS:
            for tol in TOLS:
                a = aggregate(per_run, method, tol, fold)
                for scope in ("micro", "DOWN", "UP"):
                    m = a[scope]
                    table.append({"domain": domain_name, "method": method, "tol": tol, "scope": scope,
                                  **{k: m[k] for k in ("n_pred", "n_truth", "tp", "fp", "fn", "wrong", "P", "R", "F1")}})
    with (out / "E1_main_canonical.csv").open("w", encoding="utf-8", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=["domain", "method", "tol", "scope", "n_pred", "n_truth", "tp", "fp", "fn", "wrong", "P", "R", "F1"])
        w.writeheader(); w.writerows(table)
    summary = {
        "canonical_domain": "all score-grid anchors in [0, score_end), GRID=0.25; score_end from MusicXML measure accumulation only",
        "methods": list(METHODS), "tols": TOLS, "n_runs": len(per_run),
        "n_scores": len({x["score"] for x in per_run}), "skipped": skipped,
        "b1_cv_canonical": b1_cv,
        "b1_cv_argmax_d_min_beats": best_b1["d_min_beats"] if best_b1 else None,
        "table": table,
    }
    (out / "E1_main_canonical.json").write_text(json.dumps(summary, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    md = ["# 统一评测域：E1 主表（canonical）", "",
          "canonical domain = `[0, score_end)` 的 score-grid 全部格点；`GRID=0.25`，含无音符格点。`score_end` 仅由 MusicXML 小节长度累加决定。", "",
          f"runs = {len(per_run)}; scores = {len({x['score'] for x in per_run})}; B1 CV canonical argmax d_min = {summary['b1_cv_argmax_d_min_beats']} 拍", "",
          "## test 折 / ±1 拍", "", "| 方法 | micro F1 | DOWN F1 | UP F1 |", "|:--|--:|--:|--:|"]
    for method in METHODS:
        a = aggregate(per_run, method, 1.0, "test")
        md.append(f"| {method} | {a['micro']['F1']:.4f} | {a['DOWN']['F1']:.4f} | {a['UP']['F1']:.4f} |")
    md += ["", "## full 36 首 / ±1 拍", "", "| 方法 | micro F1 | DOWN F1 | UP F1 |", "|:--|--:|--:|--:|"]
    for method in METHODS:
        a = aggregate(per_run, method, 1.0, None)
        md.append(f"| {method} | {a['micro']['F1']:.4f} | {a['DOWN']['F1']:.4f} | {a['UP']['F1']:.4f} |")
    (out / "E1_main_canonical.md").write_text("\n".join(md) + "\n", encoding="utf-8")
    print(json.dumps({"n_runs": len(per_run), "n_scores": len({x["score"] for x in per_run}),
                      "b1_cv_argmax_d_min_beats": summary["b1_cv_argmax_d_min_beats"], "skipped": skipped}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
