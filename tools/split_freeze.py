#!/usr/bin/env python
"""G1' 交付 6：主表划分冻结（D-0033 / plan §4.1）。

比例 70/10/20，seed 20260101，按作曲家分层，分组键 = (composer, normalized_title)，
同组整体同折；组数 < 3 的作曲家并入 other 池；只用分组键 + 作曲家标签；输出冻结文件 + SHA256。
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import random
import re
from collections import Counter, defaultdict
from pathlib import Path

from lxml import etree

PEDAL_XPATH = ".//*[local-name()='pedal']"
SEED = 20260101
RATIOS = {"train": 0.70, "val": 0.10, "test": 0.20}


def normalize_title(title: str) -> str:
    t = title.strip()
    t = re.sub(r"(?i)[_\-\s]*(no_)?extra_repeat$", "", t)
    t = re.sub(r"(?i)[_\-\s]*(no_)?repeat$", "", t)
    return t


def pedal_count(xml: Path) -> int:
    return len(etree.parse(str(xml)).getroot().xpath(PEDAL_XPATH))


def allocate(groups: list[str], rng: random.Random, min_fold: int = 1) -> dict[str, list[str]]:
    """70/10/20 分层内分配；保证 val/test 至少 min_fold 组（组数足够时）。"""
    g = sorted(groups)
    rng.shuffle(g)
    n = len(g)
    n_test = int(round(RATIOS["test"] * n))
    n_val = int(round(RATIOS["val"] * n))
    if n >= 3:
        n_test, n_val = max(min_fold, n_test), max(min_fold, n_val)
    while n_test + n_val >= n and n_val > 0:
        n_val -= 1
    while n_test + n_val >= n and n_test > 0:
        n_test -= 1
    return {"test": g[:n_test], "val": g[n_test:n_test + n_val], "train": g[n_test + n_val:]}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dataset", type=Path, default=Path("data/asap-dataset"))
    ap.add_argument("--out", type=Path, default=Path("evidence/R1/G1-split/split_v1.json"))
    args = ap.parse_args()

    ds = args.dataset
    rows = list(csv.DictReader((ds / "metadata.csv").open(encoding="utf-8-sig", newline="")))
    ann = json.loads((ds / "asap_annotations.json").read_text(encoding="utf-8"))

    pedal_scores = {str(p.relative_to(ds)).replace("\\", "/"): pedal_count(p)
                    for p in sorted(ds.rglob("*.musicxml")) if pedal_count(p) > 0}
    print(f"含 pedal 乐谱: {len(pedal_scores)}")

    # Main = 乐谱级过滤（口径见 FIELD_DEFINITIONS §6）：
    #   先筛出合格演奏（robust == "1.0" 且 aligned is True 且 alignment 文件存在），
    #   命中乐谱 = Main 乐谱（43）；Main 演奏 = 这些乐谱的【全部】metadata 行（291）。
    passing = []
    for r in rows:
        xml = (r.get("xml_score") or "").replace("\\", "/")
        if xml not in pedal_scores:
            continue
        if (r.get("robust_note_alignment") or "") != "1.0":
            continue
        a = ann.get((r.get("midi_performance") or "").replace("\\", "/"), {})
        if a.get("score_and_performance_aligned") is not True:
            continue
        rel = (r.get("note_alignments") or "").replace("\\", "/")
        if not (rel and (ds / rel).is_file()):
            continue
        passing.append(r)

    main_scores = sorted({(x.get("xml_score") or "").replace("\\", "/") for x in passing})
    kept = [r for r in rows if (r.get("xml_score") or "").replace("\\", "/") in set(main_scores)]
    pedal_sum = sum(pedal_scores[s] for s in main_scores)
    print(f"合格演奏（过滤级）= {len(passing)}；Main 乐谱 = {len(main_scores)}；Main 演奏（乐谱级全量）= {len(kept)}；pedal 元素 = {pedal_sum}")
    print("  plan §4.4 期望: 43 首 / 291 演奏 / 3840 元素")

    # 分组
    score_meta = {}
    for r in kept:
        xml = (r.get("xml_score") or "").replace("\\", "/")
        score_meta.setdefault(xml, {"composer": r["composer"], "title": r["title"],
                                    "group": f'{r["composer"]}||{normalize_title(r["title"])}'})
    groups = defaultdict(list)
    for xml, m in score_meta.items():
        groups[m["group"]].append(xml)
    per_composer = defaultdict(set)
    for g, xs in groups.items():
        per_composer[score_meta[xs[0]]["composer"]].add(g)

    strata: dict[str, list[str]] = {}
    other_members = []
    for comp, gs in sorted(per_composer.items()):
        if len(gs) >= 3:
            strata[comp] = sorted(gs)
        else:
            other_members.append(comp)
            strata.setdefault("other", []).extend(sorted(gs))
    if "other" in strata:
        strata["other"] = sorted(set(strata["other"]))

    rng = random.Random(SEED)
    fold_groups = {"train": [], "val": [], "test": []}
    for stratum, gs in sorted(strata.items()):
        alloc = allocate(gs, rng)
        for fold, items in alloc.items():
            fold_groups[fold].extend(items)

    def counts(fold: str) -> dict:
        gs = fold_groups[fold]
        xmls = sorted({x for g in gs for x in groups[g]})
        perfs = [r for r in kept if (r.get("xml_score") or "").replace("\\", "/") in set(xmls)]
        return {
            "groups": len(gs),
            "scores": len(xmls),
            "performances": len(perfs),
            "pedal_elements": sum(pedal_scores[x] for x in xmls),
            "composer_scores": dict(sorted(Counter(score_meta[x]["composer"] for x in xmls).items())),
        }

    result = {
        "seed": SEED, "ratios": RATIOS,
        "filter": "SCORE-LEVEL: passing perf = robust_note_alignment==1.0 AND score_and_performance_aligned is True AND note_alignment file exists; Main scores = touched scores (43); Main performances = ALL metadata rows of those scores (291)",
        "main_scores": main_scores, "main_performances": len(kept), "main_pedal_elements": pedal_sum,
        "n_groups": len(groups),
        "other_pool": {"composers": sorted(other_members),
                       "groups": len(strata.get("other", [])),
                       "scores": sum(len(groups[g]) for g in strata.get("other", []))},
        "fold_groups": {k: sorted(v) for k, v in fold_groups.items()},
        "fold_counts": {k: counts(k) for k in fold_groups},
        "score_meta": score_meta,
    }
    payload = json.dumps(result, indent=2, ensure_ascii=False) + "\n"
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(payload, encoding="utf-8")
    digest = hashlib.sha256(payload.encode("utf-8")).hexdigest()
    (args.out.parent / "split_v1.sha256").write_text(f"{digest}  {args.out.name}\n", encoding="utf-8")

    print("\n=== 每折计数 ===")
    for k in ("train", "val", "test"):
        c = result["fold_counts"][k]
        print(f"  {k:<5} groups={c['groups']:<3} scores={c['scores']:<3} performances={c['performances']:<4} pedal={c['pedal_elements']:<5}")
    print(f"\nother 池: composers={result['other_pool']['composers']} groups={result['other_pool']['groups']} scores={result['other_pool']['scores']}")
    print(f"split sha256 = {digest}")
    empty = [k for k, c in result["fold_counts"].items() if c["groups"] == 0]
    single_test = result["fold_counts"]["test"]["groups"] <= 1
    if empty or single_test:
        print(f"\n!! STOP: 空折={empty} 或 test 组数<=1 ({result['fold_counts']['test']['groups']})")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())