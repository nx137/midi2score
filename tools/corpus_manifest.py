#!/usr/bin/env python
"""生成 ASAP 语料身份 manifest（CSV）并输出其 sha256。

冻结口径（与 G0 证据一致）：
  列 = entry_type,relative_path,bytes,sha256
  条目 = *.musicxml (kind=musicxml) + note_alignment.tsv (kind=note_alignment)
  排序 = (entry_type, relative_path.lower())
  编码 = UTF-8 无 BOM，CSV 默认 CRLF 行尾
  manifest_sha256 = 该 CSV 文件的 sha256

用法:
    python tools/corpus_manifest.py --dataset data/asap-dataset --out evidence/corpus_manifest.csv
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import subprocess
from collections import Counter
from pathlib import Path

PATTERNS = (("musicxml", "*.musicxml"), ("note_alignment", "note_alignment.tsv"))
FIELDS = ["entry_type", "relative_path", "bytes", "sha256"]


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def build_rows(dataset: Path) -> list[dict]:
    rows: list[dict] = []
    for kind, pattern in PATTERNS:
        for path in sorted(dataset.rglob(pattern)):
            rows.append(
                {
                    "entry_type": kind,
                    "relative_path": str(path.relative_to(dataset)).replace("\\", "/"),
                    "bytes": path.stat().st_size,
                    "sha256": sha256_file(path),
                }
            )
    rows.sort(key=lambda row: (row["entry_type"], row["relative_path"].lower()))
    return rows


def write_manifest(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=FIELDS, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def main() -> int:
    parser = argparse.ArgumentParser(description="ASAP corpus identity manifest")
    parser.add_argument("--dataset", type=Path, default=Path("data/asap-dataset"))
    parser.add_argument("--out", type=Path, default=Path("evidence/corpus_manifest.csv"))
    parser.add_argument("--summary", type=Path, default=None)
    args = parser.parse_args()

    rows = build_rows(args.dataset)
    write_manifest(args.out, rows)
    counts = Counter(row["entry_type"] for row in rows)
    summary = {
        "dataset": str(args.dataset.resolve()).replace("\\", "/"),
        "dataset_git_head": subprocess.check_output(
            ["git", "-C", str(args.dataset), "rev-parse", "HEAD"], text=True
        ).strip(),
        "entry_count": len(rows),
        "musicxml_count": counts["musicxml"],
        "note_alignment_count": counts["note_alignment"],
        "total_bytes": sum(row["bytes"] for row in rows),
        "manifest_path": str(args.out.resolve()),
        "manifest_sha256": sha256_file(args.out),
    }
    print(json.dumps(summary, indent=2, ensure_ascii=False))
    if args.summary is not None:
        args.summary.write_text(json.dumps(summary, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())