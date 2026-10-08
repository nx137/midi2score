#!/usr/bin/env python
"""B2 = 和声段驱动规则（§5.2）。事件制激活（D-0067，缺陷 #14 更正）。只能新增，不改既有文件。"""

from __future__ import annotations
import argparse, csv, json, random, sys
from pathlib import Path
import numpy as np
sys.path.insert(0, str(Path(__file__).resolve().parent))
from score_features import anchor_features, measure_starts, parse_score_extended  # noqa: E402
from inversion_consistency import GRID, cc64_transitions, parse_alignment, parse_score, snap, to_anchor  # noqa: E402
from inversion_baselines import f1_of  # noqa: E402

TOLS = [0.0, 1.0, 2.0]
K_GRID = [1, 2, 3]


def build(xml: Path, perf: Path, al: Path, K: int):
    notes_ext = parse_score_extended(xml)
    notes_pos, pedals = parse_score(xml)
    ms = {snap(m) for m in measure_starts(xml)}
    truth = {(snap(o), "DOWN" if k == "start" else "UP") for (m, o, k) in pedals}
    if not truth:
        return None
    span = max(t for t, _ in truth)
    anchors = [round(i * GRID, 6) for i in range(int(round(span / GRID)) + 1)]
    # 空锚点 zero-order hold（D-0066 + D-0067）
    feats, last = [], None
    for t in anchors:
        f = anchor_features(notes_ext, t)
        if f["n_notes"] == 0 and last is not None:
            f = {"n_notes": 0, "bass_pc": last["bass_pc"], "pcs": last["pcs"]}
        feats.append(f)
        if f["n_notes"] > 0:
            last = f
    nxt = None
    for i in range(len(feats) - 1, -1, -1):
        if feats[i]["n_notes"] > 0:
            nxt = feats[i]
        elif nxt is not None and feats[i]["bass_pc"] is None:
            feats[i] = {"n_notes": 0, "bass_pc": nxt["bass_pc"], "pcs": nxt["pcs"]}
    # Step 1 边界（三要素取或）
    bnd = [anchors[0]]
    for i in range(1, len(anchors)):
        a, b = feats[i - 1], feats[i]
        chg_bass = a["bass_pc"] is not None and b["bass_pc"] is not None and a["bass_pc"] != b["bass_pc"]
        chg_pcs = a["pcs"] is not None and len(b["pcs"] ^ a["pcs"]) >= K
        if chg_bass or chg_pcs or snap(anchors[i]) in ms:
            bnd.append(anchors[i])
    if bnd[-1] != span:
        bnd.append(span)
    # CC64 start 事件的位置（事件制，D-0067）
    seq = sorted((o, notes_pos[b][1]) for b, r, o in parse_alignment(al) if b in notes_pos)
    if len(seq) < 2:
        return None
    starts = []
    for t, kind in cc64_transitions(perf):
        if kind != "start":
            continue
        got = to_anchor(t, seq, [])
        if got:
            starts.append(snap(got[0]))
    # Step 2/3：段激活 → (ta,DOWN)+(tb,UP)
    pred = set()
    for ta, tb in zip(bnd, bnd[1:]):
        if not (0 <= ta <= span and 0 <= tb <= span):
            continue
        if any(ta <= p < tb for p in starts):
            pred.add((ta, "DOWN"))
            pred.add((tb, "UP"))
    return truth, pred, span


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dataset", type=Path, default=Path("data/asap-dataset"))
    ap.add_argument("--split", type=Path, default=Path("evidence/R1/G1-split/split_v1.json"))
    ap.add_argument("--out-dir", type=Path, default=Path("results/E1"))
    ap.add_argument("--boot", type=int, default=10000)
    ap.add_argument("--seed", type=int, default=20260101)
    args = ap.parse_args()
    D = args.dataset
    split = json.loads(args.split.read_text(encoding="utf-8"))
    from lxml import etree
    main_scores = set(split["main_scores"])
    repeat = {s for s in main_scores if etree.parse(str(D / s)).getroot().xpath(".//*[local-name()='repeat']")}
    fold_of = {p["xml_score"]: p["fold"] for p in split["per_performance"]}
    group_of = {s: split["score_meta"][s]["group"] for s in split["main_scores"]}
    runs = []
    for p in split["per_performance"]:
        xml = p["xml_score"]
        if xml not in main_scores or xml in repeat:
            continue
        al = D / p["alignment_path"] if p["alignment_path"] else None
        perf = D / p["midi_performance"]
        if not (al and al.is_file() and perf.is_file()):
            continue
        runs.append({"score": xml, "perf": p["midi_performance"], "fold": fold_of.get(xml),
                     "group": group_of.get(xml), "xml": D / xml, "perf_path": perf, "al": al})
    print(f"可用 runs = {len(runs)}")

    def per_run(K):
        out = []
        for r in runs:
            b = build(r["xml"], r["perf_path"], r["al"], K)
            if b is None:
                continue
            truth, pred, span = b
            rec = {k: r[k] for k in ("score", "perf", "fold", "group")}
            rec["span"] = span
            for tol in TOLS:
                rec[f"tol{tol}"] = f1_of(pred, truth, tol)
            rec["truth"] = truth
            rec["pred"] = pred
            out.append(rec)
        return out

    def agg(sel, tol):
        tp = sum(x[f"tol{tol}"]["tp"] for x in sel); fp = sum(x[f"tol{tol}"]["fp"] for x in sel)
        fn = sum(x[f"tol{tol}"]["fn"] for x in sel); wr = sum(x[f"tol{tol}"]["wrong"] for x in sel)
        p = tp / (tp + fp) if (tp + fp) else 0; rr = tp / (tp + fn) if (tp + fn) else 0
        return {"tp": tp, "fp": fp, "fn": fn, "wrong": wr, "P": p, "R": rr,
                "F1": 2 * p * rr / (p + rr) if (p + rr) else 0,
                "n_pred": sum(x[f"tol{tol}"]["n_pred"] for x in sel)}

    def per_label(sel, tol):
        out = {}
        for lab in ("DOWN", "UP"):
            tp = fp = fn = 0
            for x in sel:
                pr = {y for y in x["pred"] if y[1] == lab}; tr = {y for y in x["truth"] if y[1] == lab}
                m = f1_of(pr, tr, tol); tp += m["tp"]; fp += m["fp"]; fn += m["fn"]
            p = tp / (tp + fp) if (tp + fp) else 0; rr = tp / (tp + fn) if (tp + fn) else 0
            out[lab] = {"P": p, "R": rr, "F1": 2 * p * rr / (p + rr) if (p + rr) else 0}
        return out

    out = args.out_dir; out.mkdir(parents=True, exist_ok=True)
    rows = {}
    for K in K_GRID:
        rows[K] = per_run(K)
    tr = [r for r in runs if r["fold"] == "train"]
    groups = sorted({r["group"] for r in tr})
    fold_id = {g: i % 5 for i, g in enumerate(groups)}   # 与 B1 同一 fold assignment（D-0067 ④）
    cv = []
    for K in K_GRID:
        sel = [x for x in rows[K] if x["fold"] == "train"]
        c = {"K": K}
        for tol in TOLS:
            c[f"tol{tol}"] = agg(sel, tol)
        f1s = [agg([x for x in sel if fold_id.get(x["group"]) == k], 1.0)["F1"] for k in range(5)]
        c["fold_f1_at_1"] = f1s; c["mean_f1_at_1"] = float(np.mean(f1s))
        cv.append(c)
        print(f"CV K={K}: " + " ".join(f"±{t}:#pred={c[f'tol{t}']['n_pred']} P={c[f'tol{t}']['P']:.3f} R={c[f'tol{t}']['R']:.3f} F1={c[f'tol{t}']['F1']:.4f}" for t in TOLS) + f" | meanfoldF1@1={c['mean_f1_at_1']:.4f}")
    best = max(cv, key=lambda c: (c["mean_f1_at_1"], -c["K"]))
    print(f"\n选中 K = {best['K']}（各折最优跨度 = {len({int(np.argmax(c['fold_f1_at_1'])) for c in cv})} 档）")
    summary = {"selected_K": best["K"], "cv": cv,
               "val": {}, "test": {}, "per_label_test": {},
               "note": "B2 与 bp2/bp4 严格同域（span = max(truth)）；与 inversion/B1 域不同 ⇒ 仅参考不作判据"}
    for f in ("val", "test"):
        sel = [x for x in rows[best["K"]] if x["fold"] == f]
        summary[f] = {f"±{t}": agg(sel, t) for t in TOLS}
        summary[f]["per_label_±1"] = per_label(sel, 1.0)
        print(f"{f}: " + " ".join(f"±{t}:#pred={summary[f][f'±{t}']['n_pred']} P={summary[f][f'±{t}']['P']:.3f} R={summary[f][f'±{t}']['R']:.3f} F1={summary[f][f'±{t}']['F1']:.4f}" for t in TOLS))
        print(f"  {f} 分标签@±1: DOWN {summary[f]['per_label_±1']['DOWN']} | UP {summary[f]['per_label_±1']['UP']}")
    # bootstrap（test 折，B2 vs bp2/bp4，逐曲配对）
    rng = random.Random(args.seed)
    test_scores = sorted({x["score"] for x in rows[best["K"]] if x["fold"] == "test"})
    by_score = {}
    for x in rows[best["K"]]:
        if x["fold"] == "test":
            by_score.setdefault(x["score"], []).append(x)
    diffs = []
    for _ in range(args.boot):
        sel = [x for s in (test_scores[rng.randrange(len(test_scores))] for _ in range(len(test_scores))) for x in by_score[s]]
        b2 = agg(sel, 1.0)["F1"]
        span = max((max(t for t, _ in x["truth"]) for x in sel), default=0.0)
        bp = {}
        for n in (2, 4):
            tp = fp = fn = 0
            for x in sel:
                base = {(snap(v), "DOWN") for v in np.arange(0, x["span"] + 0.25, float(n))}
                m = f1_of(base, x["truth"], 1.0); tp += m["tp"]; fp += m["fp"]; fn += m["fn"]
            p = tp / (tp + fp) if (tp + fp) else 0; rr = tp / (tp + fn) if (tp + fn) else 0
            bp[n] = 2 * p * rr / (p + rr) if (p + rr) else 0
        diffs.append({"bp2": b2 - bp[2], "bp4": b2 - bp[4]})
    boot = {k: {"mean": round(float(np.mean([d[k] for d in diffs])), 4),
                "ci95_low": round(float(np.percentile([d[k] for d in diffs], 2.5)), 4),
                "ci95_high": round(float(np.percentile([d[k] for d in diffs], 97.5)), 4)}
            for k in ("bp2", "bp4")}
    summary["bootstrap_test_vs"] = boot
    print("bootstrap(test) vs bp2/bp4:", json.dumps(boot, ensure_ascii=False))
    with (out / "B2_perf.csv").open("w", encoding="utf-8", newline="") as fh:
        w = csv.writer(fh); w.writerow(["K", "fold", "score", "perf", "tol", "n_pred", "tp", "fp", "fn", "wrong", "P", "R", "F1"])
        for K in K_GRID:
            for x in rows[K]:
                for tol in TOLS:
                    m = x[f"tol{tol}"]
                    w.writerow([K, x["fold"], x["score"], x["perf"], tol, m["n_pred"], m["tp"], m["fp"], m["fn"], m["wrong"],
                                round(m["P"], 6), round(m["R"], 6), round(m["F1"], 6)])
    (out / "B2_summary.json").write_text(json.dumps(summary, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())