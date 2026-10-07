#!/usr/bin/env python
"""冻结对象 = 指派三元组集合 {(piecegroup, performanceid, fold)} 的规范化 CSV 哈希。

规范：按 (piecegroup, performanceid) 排序；UTF-8 无 BOM；CRLF；列 = piecegroup,performanceid,fold。
文件字节可继续增补（enriched），指派身份由 assignment_sha256 唯一确定（同 D-0020 做法）。
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
from pathlib import Path


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--split", type=Path, default=Path("evidence/R1/G1-split/split_v1.json"))
    ap.add_argument("--out-csv", type=Path, default=Path("evidence/R1/G1-split/split_v1_assignment.csv"))
    args = ap.parse_args()

    d = json.loads(args.split.read_text(encoding="utf-8"))
    meta = d["score_meta"]
    rows = []
    for perf in d["per_performance"]:
        xml = perf["xml_score"]
        rows.append({"piecegroup": meta[xml]["group"],
                     "performanceid": perf["midi_performance"],
                     "fold": perf["fold"]})
    rows.sort(key=lambda r: (r["piecegroup"], r["performanceid"]))

    buf = io.StringIO(newline="")
    w = csv.DictWriter(buf, fieldnames=["piecegroup", "performanceid", "fold"], lineterminator="\r\n")
    w.writeheader()
    w.writerows(rows)
    payload = buf.getvalue().encode("utf-8")
    args.out_csv.write_bytes(payload)
    digest = hashlib.sha256(payload).hexdigest()
    (args.out_csv.with_suffix(".sha256")).write_text(f"{digest}  {args.out_csv.name}\n", encoding="utf-8")

    print(f"rows={len(rows)}  groups={len({r['piecegroup'] for r in rows})}")
    print(f"assignment_sha256 = {digest}")
    print("fold counts:", json.dumps({f: sum(1 for r in rows if r["fold"] == f) for f in ("train", "val", "test")}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())