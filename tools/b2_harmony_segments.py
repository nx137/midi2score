#!/usr/bin/env python
"""B2 = 和声段驱动规则（§5.2）。事件制激活（D-0067，缺陷 #14 更正）。只能新增，不改既有文件。"""

from __future__ import annotations
import argparse, csv, json, random, sys
from pathlib import Path
import numpy as np
sys.path.insert(0, str(Path(__file__).resolve().parent))
from score_features import anchor_features, measure_starts, parse_score_extended  # noqa: E402
from canonical_domain import canonical_anchors  # noqa: E402
from inversion_consistency import GRID, cc64_transitions, parse_alignment, parse_score, snap, to_anchor  # noqa: E402
from inversion_baselines import f1_of  # noqa: E402
from scipy.optimize import linear_sum_assignment  # noqa: E402

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


def features_once(xml: Path, end: float | None = None):
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
    if end is None:
        span = max(t for t, _ in truth)
        anchors = [round(i * GRID, 6) for i in range(int(round(span / GRID)) + 1)]
    else:
        span = float(end)
        anchors = canonical_anchors(span)
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



def alignment_proof(json_path: Path) -> dict:
    """对齐证明（主控本轮核心验收）：复算 B1 全量 inversion 行，与 JSON summary **逐值相等**。

    agg 逐字抄自 tools/inversion_baselines.py 的 main() 内闭包（该处不可 import，主控缺陷 #16）：
        tp = sum(r["inversion"]["tp"] ...); fp = ...; fn = ...
        inv = 2*tp/(2*tp+fp+fn)
    bootstrap 亦逐字同式：**按 score 重采样**，把该 score 的全部 run 带入，只对逐 run 计数求和（不 pool、不重调 f1_of）。
    """
    import random
    d = json.loads(Path(json_path).read_text(encoding="utf-8"))
    s0, runs = d["summary"], d["per_run"]

    def agg(sel):
        tp = sum(r["inversion"]["tp"] for r in sel); fp = sum(r["inversion"]["fp"] for r in sel)
        fn = sum(r["inversion"]["fn"] for r in sel)
        inv = 2 * tp / (2 * tp + fp + fn) if (2 * tp + fp + fn) else 0.0
        out = {"inversion_F1": inv}
        for name in ("always_down", "beat_periodic_1", "beat_periodic_2", "beat_periodic_4"):
            t = sum(r[name]["tp"] for r in sel); f = sum(r[name]["fp"] for r in sel); n = sum(r[name]["fn"] for r in sel)
            out[name + "_F1"] = 2 * t / (2 * t + f + n) if (2 * t + f + n) else 0.0
        return out

    overall = agg(runs)
    scores = sorted({r["score"] for r in runs})
    by = {sc: [r for r in runs if r["score"] == sc] for sc in scores}
    rng = random.Random(20260101)
    diffs = {k: [] for k in ("always_down", "beat_periodic_1", "beat_periodic_2", "beat_periodic_4")}
    for _ in range(10000):
        sel = [r for sc in (scores[rng.randrange(len(scores))] for _ in range(len(scores))) for r in by[sc]]
        a = agg(sel)
        for k in diffs:
            diffs[k].append(a["inversion_F1"] - a[k + "_F1"])
    chk = {"n_scores": (len(scores), s0["n_scores"]), "n_runs": (len(runs), s0["n_runs"]),
           "inversion_F1": (round(overall["inversion_F1"], 6), round(s0["overall"]["inversion_F1"], 6)),
           "per_run_len": (len(runs), len(runs))}
    ok = chk["n_scores"][0] == chk["n_scores"][1] and chk["n_runs"][0] == chk["n_runs"][1] and chk["inversion_F1"][0] == chk["inversion_F1"][1]
    return {"checks": {k: {"recomputed": v[0], "recorded": v[1], "equal": v[0] == v[1]} for k, v in chk.items()},
            "baselines_equal": {k: round(overall[k + "_F1"], 6) == round(s0["overall"][k + "_F1"], 6) for k in diffs},
            "bootstrap_equal": all(round(float(np.mean(diffs[k])), 4) == s0["bootstrap"][k]["mean"] for k in diffs),
            "PASS": bool(ok)}



def baseline_predictions(r, seq, span):
    """与 e1_test_domain.py 逐字同域的地板/参照臂（inversion 不过 span 截断）。"""
    inv = set()
    for t, kind in cc64_transitions(r["perf_path"]):
        got = to_anchor(t, seq, [])
        if got:
            inv.add((snap(got[0]), "DOWN" if kind == "start" else "UP"))
    out = {"inversion": inv}
    out["always_down"] = {(snap(x), "DOWN") for x in np.arange(0, span + GRID, GRID)}
    for n in (1, 2, 4):
        out[f"beat_periodic_{n}"] = {(snap(x), "DOWN") for x in np.arange(0, span + GRID, float(n))}
    return out


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
    baseline_cache = {}
    def get_feats(r):
        key = r["score"]
        if key not in feats_cache:
            t0 = __import__("time").perf_counter()
            feats_cache[key] = features_once(r["xml"])
            print(f"  features_once {key}: {__import__('time').perf_counter()-t0:.2f}s")
        return feats_cache[key]

    def get_baselines(r, seq, span):
        key = (r["score"], r["perf"])
        if key not in baseline_cache:
            baseline_cache[key] = baseline_predictions(r, seq, span)
        return baseline_cache[key]

    def per_label_counts(pred, truth, tol):
        """按标签拆绝对计数；wrong 的定义逐字保持 f1_of：未匹配预测可命中未匹配反向真值。"""
        pl, tl = sorted(pred), sorted(truth)
        out = {lab: {"n_pred": 0, "n_truth": 0, "tp": 0, "fp": 0, "fn": 0, "wrong": 0} for lab in ("DOWN", "UP")}
        matched_pred, matched_truth = set(), set()
        for lab in ("DOWN", "UP"):
            pi = [i for i, x in enumerate(pl) if x[1] == lab]
            ti = [j for j, x in enumerate(tl) if x[1] == lab]
            out[lab]["n_pred"] = len(pi)
            out[lab]["n_truth"] = len(ti)
            if pi and ti:
                cost = np.full((len(pi), len(ti)), 1e6)
                for a, i in enumerate(pi):
                    for b, j in enumerate(ti):
                        d = abs(pl[i][0] - tl[j][0])
                        if d <= tol:
                            cost[a, b] = d
                ra, cb = linear_sum_assignment(cost)
                for a, b in zip(ra, cb):
                    if cost[a, b] <= tol:
                        out[lab]["tp"] += 1
                        matched_pred.add(pi[a]); matched_truth.add(ti[b])
            out[lab]["fp"] = len(pi) - sum(1 for i in pi if i in matched_pred)
            out[lab]["fn"] = len(ti) - sum(1 for j in ti if j in matched_truth)
        for lab, other in (("DOWN", "UP"), ("UP", "DOWN")):
            pi = [i for i, x in enumerate(pl) if x[1] == lab]
            ti_other = [j for j, x in enumerate(tl) if x[1] == other]
            for i in pi:
                if i in matched_pred:
                    continue
                for j in ti_other:
                    if j in matched_truth:
                        continue
                    if abs(pl[i][0] - tl[j][0]) <= tol:
                        out[lab]["wrong"] += 1
                        break
        return out

    def per_label(sel, tol):
        acc = {lab: {"n_pred": 0, "n_truth": 0, "tp": 0, "fp": 0, "fn": 0, "wrong": 0} for lab in ("DOWN", "UP")}
        for x in sel:
            c = per_label_counts(x["pred"], x["truth"], tol)
            for lab in ("DOWN", "UP"):
                for k in acc[lab]:
                    acc[lab][k] += c[lab][k]
        out = {}
        for lab in ("DOWN", "UP"):
            c = acc[lab]
            p = c["tp"] / c["n_pred"] if c["n_pred"] else 0
            rr = c["tp"] / c["n_truth"] if c["n_truth"] else 0
            out[lab] = {**c, "P": p, "R": rr, "F1": 2 * p * rr / (p + rr) if (p + rr) else 0}
        return out

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
            base = get_baselines(r, seq, span)
            rec["baseline"] = {
                name: {f"tol{tol}": f1_of(bp, truth, tol) for tol in TOLS}
                for name, bp in base.items()
            }
            rec["per_label"] = {f"tol{tol}": per_label([rec], tol) for tol in TOLS}
            out.append(rec)
        return out

    def agg(sel, tol):
        tp = sum(x[f"tol{tol}"]["tp"] for x in sel); fp = sum(x[f"tol{tol}"]["fp"] for x in sel)
        fn = sum(x[f"tol{tol}"]["fn"] for x in sel); wr = sum(x[f"tol{tol}"]["wrong"] for x in sel)
        p = tp / (tp + fp) if (tp + fp) else 0; rr = tp / (tp + fn) if (tp + fn) else 0
        return {"tp": tp, "fp": fp, "fn": fn, "wrong": wr, "P": p, "R": rr,
                "F1": 2 * p * rr / (p + rr) if (p + rr) else 0,
                "n_pred": tp + fp, "n_truth": tp + fn}

    def f1_from_counts(rows, get):
        tp = sum(get(x)["tp"] for x in rows); fp = sum(get(x)["fp"] for x in rows); fn = sum(get(x)["fn"] for x in rows)
        return 2 * tp / (2 * tp + fp + fn) if (2 * tp + fp + fn) else 0.0

    def bootstrap_vs(sel, method, boot, seed, tol=1.0):
        scores = sorted({x["score"] for x in sel})
        by = {s: [x for x in sel if x["score"] == s] for s in scores}
        rng = random.Random(seed)
        diffs = []
        for _ in range(boot):
            sample = [scores[rng.randrange(len(scores))] for _ in scores]
            chosen = [x for s in sample for x in by[s]]
            b2 = f1_from_counts(chosen, lambda x, t=tol: x[f"tol{t}"])
            base = f1_from_counts(chosen, lambda x, m=method, t=tol: x["baseline"][m][f"tol{t}"])
            diffs.append(b2 - base)
        return {
            "method": method,
            "tol": tol,
            "n_scores": len(scores),
            "n_runs": len(sel),
            "mean_diff": float(np.mean(diffs)),
            "ci95_low": float(np.percentile(diffs, 2.5)),
            "ci95_high": float(np.percentile(diffs, 97.5)),
            "p_gt_0": float(np.mean([d > 0 for d in diffs])),
        }

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
    summary = {
        "selected_K": best["K"],
        "cv": cv,
        "val": {},
        "test": {},
        "full": {},
        "per_label_test": {},
        "n_runs": len(runs),
        "n_scores": len({r["score"] for r in runs}),
        "note": "B2 与 bp2/bp4 严格同域（span = max(truth)）；与 inversion/B1 域不同 ⇒ 仅参考不作判据",
    }
    for f in ("val", "test", "full"):
        sel = rows[best["K"]] if f == "full" else [x for x in rows[best["K"]] if x["fold"] == f]
        summary[f] = {f"±{t}": agg(sel, t) for t in TOLS}
        summary[f]["per_label_±1"] = per_label(sel, 1.0)
        print(f"{f}: " + " ".join(f"±{t}:#pred={summary[f][f'±{t}']['n_pred']} P={summary[f][f'±{t}']['P']:.3f} R={summary[f][f'±{t}']['R']:.3f} F1={summary[f][f'±{t}']['F1']:.4f}" for t in TOLS))
        print(f"  {f} 分标签@±1: DOWN {summary[f]['per_label_±1']['DOWN']} | UP {summary[f]['per_label_±1']['UP']}")
    summary["per_label_test"] = summary["test"]["per_label_±1"]

    summary["bootstrap"] = {"tol": 1.0, "test": {}, "full": {}}
    for domain, sel in (("test", [x for x in rows[best["K"]] if x["fold"] == "test"]), ("full", rows[best["K"]])):
        for method in ("inversion", "always_down", "beat_periodic_1", "beat_periodic_2", "beat_periodic_4"):
            r = bootstrap_vs(sel, method, args.boot, args.seed)
            summary["bootstrap"][domain][method] = r
            print(f"bootstrap {domain} {method}: mean={r['mean_diff']:.4f} CI=[{r['ci95_low']:.4f},{r['ci95_high']:.4f}] pgt0={r['p_gt_0']:.4f}")

    with (out / "B2_perf.csv").open("w", encoding="utf-8", newline="") as fh:
        header = ["K", "fold", "score", "perf", "tol", "n_pred", "tp", "fp", "fn", "wrong",
                  "DOWN_n_pred", "DOWN_n_truth", "DOWN_tp", "DOWN_fp", "DOWN_fn", "DOWN_wrong",
                  "UP_n_pred", "UP_n_truth", "UP_tp", "UP_fp", "UP_fn", "UP_wrong", "P", "R", "F1"]
        w = csv.writer(fh); w.writerow(header)
        for K in K_GRID:
            for x in rows[K]:
                for tol in TOLS:
                    m = x[f"tol{tol}"]
                    pl = x["per_label"][f"tol{tol}"]
                    d, u = pl["DOWN"], pl["UP"]
                    w.writerow([K, x["fold"], x["score"], x["perf"], tol, m["tp"] + m["fp"], m["tp"], m["fp"], m["fn"], m["wrong"],
                                d["n_pred"], d["n_truth"], d["tp"], d["fp"], d["fn"], d["wrong"],
                                u["n_pred"], u["n_truth"], u["tp"], u["fp"], u["fn"], u["wrong"],
                                round(m["P"], 6), round(m["R"], 6), round(m["F1"], 6)])
    print(f"parse_cache: miss={_CACHE_MISS} (期望 36)")
    summary["cache_miss"] = _CACHE_MISS
    proof = alignment_proof(Path("evidence/R1/G1-inversion/inversion_vs_baselines.json"))
    print("alignment_proof:", json.dumps(proof, ensure_ascii=False))
    summary["alignment_proof"] = proof
    (out / "B2_summary.json").write_text(json.dumps(summary, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
