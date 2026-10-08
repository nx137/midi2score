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

# 缓存：仅在 B2 脚本内（D-0066「只能新增」；不给既有 parse_score 挂装饰器）
# 键 = XML 的规范化绝对路径；同一对象被多 run / 多 K 复用
_PARSE_CACHE: dict[str, dict] = {}
_CACHE_MISS = 0


def cached_parse(xml_path: Path) -> dict:
    global _CACHE_MISS
    key = str(Path(xml_path).resolve())
    if key not in _PARSE_CACHE:
        notes_pos, pedals = parse_score(xml_path)
        _PARSE_CACHE[key] = {"notes_pos": notes_pos, "pedals": pedals}
        _CACHE_MISS += 1
    return _PARSE_CACHE[key]
K_GRID = [1, 2, 3]


def features_once(xml: Path):
    """每 run 只算一次（K 无关）：锚点 / 特征序列 / 真值 / span / 小节首集合。

    分桶用**单遍双指针**，比较式与 anchor_features 的选择谓词逐字相同（半开区间 [t, t+GRID)）：
        sel = [n["pitch"] for n in notes.values() if n["pitch"] is not None and t <= n["pos"] < t + grid]
    冒烟已验证：6165/6165 锚点字典全等（tools/b2_smoke.py）。
    """
    notes_ext = parse_score_extended(xml)
    notes_pos, pedals = parse_score(xml)
    ms = {snap(m) for m in measure_starts(xml)}
    truth = {(snap(o), "DOWN" if k == "start" else "UP") for (m, o, k) in pedals}
    if not truth:
        return None
    span = max(t for t, _ in truth)
    anchors = [round(i * GRID, 6) for i in range(int(round(span / GRID)) + 1)]
    items = sorted(((n["pos"], i, n) for i, n in notes_ext.items() if n["pitch"] is not None), key=lambda x: x[0])
    onsets = [x[0] for x in items]
    raw, lo, hi = [], 0, 0
    for t in anchors:
        while lo < len(onsets) and onsets[lo] < t:
            lo += 1
        if hi < lo:
            hi = lo
        while hi < len(onsets) and onsets[hi] < t + GRID:
            hi += 1
        raw.append(anchor_features({items[k][1]: items[k][2] for k in range(lo, hi)}, t))
    # 空锚点 zero-order hold（首锚点空则继承其后首个非空）
    feats = list(raw); last = None
    for i, f in enumerate(raw):
        if f["n_notes"] > 0:
            last = f
        elif last is not None:
            feats[i] = {"n_notes": 0, "bass_pc": last["bass_pc"], "pcs": last["pcs"]}
    nxt = None
    for i in range(len(raw) - 1, -1, -1):
        if raw[i]["n_notes"] > 0:
            nxt = raw[i]
        elif nxt is not None and feats[i]["bass_pc"] is None:
            feats[i] = {"n_notes": 0, "bass_pc": nxt["bass_pc"], "pcs": nxt["pcs"]}
    # K 无关的整数增量：|pcs(t) Δ pcs(t-1)|
    dpcs = [0] * len(anchors)
    bass_chg = [False] * len(anchors)
    meas = [snap(t) in ms for t in anchors]
    for i in range(1, len(anchors)):
        a, b = feats[i - 1], feats[i]
        bass_chg[i] = a["bass_pc"] is not None and b["bass_pc"] is not None and a["bass_pc"] != b["bass_pc"]
        dpcs[i] = len(b["pcs"] ^ a["pcs"]) if (a["pcs"] is not None and b["pcs"] is not None) else 0
    return anchors, feats, truth, span, dpcs, bass_chg, meas


def predict(anchors, span, dpcs, bass_chg, meas, starts, K):
    bnd = [anchors[0]]
    for i in range(1, len(anchors)):
        if bass_chg[i] or dpcs[i] >= K or meas[i]:
            bnd.append(anchors[i])
    if bnd[-1] != span:
        bnd.append(span)          # 末段右端 = 序列末锚点（授权自行取值，见 evidence）
    pred = set()
    for ta, tb in zip(bnd, bnd[1:]):
        if not (0 <= ta <= span and 0 <= tb <= span):
            continue
        if any(ta <= p < tb for p in starts):
            pred.add((ta, "DOWN"))
            pred.add((tb, "UP"))
    return pred


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

    feats_cache = {}
    def get_feats(r):
        key = r["score"]
        if key not in feats_cache:
            t0 = __import__("time").perf_counter()
            feats_cache[key] = features_once(r["xml"])
            print(f"  features_once {key}: {__import__("time").perf_counter()-t0:.2f}s")
        return feats_cache[key]

    def per_run(K):
        out = []
        for r in runs:
            F = get_feats(r)
            if F is None:
                continue
            anchors, feats, truth, span, dpcs, bass_chg, meas = F
            _c = cached_parse(r["xml"])
            seq = sorted((o, _c["notes_pos"][b][1]) for b, rr, o in parse_alignment(r["al"]) if b in _c["notes_pos"])
            if len(seq) < 2:
                continue
            starts = []
            for t, kind in cc64_transitions(r["perf_path"]):
                if kind != "start":
                    continue
                got = to_anchor(t, seq, [])
                if got:
                    starts.append(snap(got[0]))
            pred = predict(anchors, span, dpcs, bass_chg, meas, starts, K)
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
                "n_pred": tp + fp}   # f1_of 不返回 n_pred（D-0063 口径），此处由 tp+fp 导出

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
    print(f"parse_cache: miss={_CACHE_MISS} (期望 36)")
    summary["cache_miss"] = _CACHE_MISS
    (out / "B2_summary.json").write_text(json.dumps(summary, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())