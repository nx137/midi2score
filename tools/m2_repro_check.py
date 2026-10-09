#!/usr/bin/env python
"""M2 可复现性检查：用同一显式参数重新构建到临时目录并比较内容哈希。"""
from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import subprocess
import sys
from pathlib import Path


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dataset", type=Path, required=True)
    ap.add_argument("--split", type=Path, required=True)
    ap.add_argument("--baseline-data", type=Path, required=True)
    ap.add_argument("--baseline-results", type=Path, required=True)
    ap.add_argument("--out", type=Path, required=True)
    args = ap.parse_args()

    repo = Path(__file__).resolve().parents[1]
    temp_root = repo / "data" / "derived" / "m2_repro_check_tmp"
    temp_data = temp_root / "data"
    temp_results = temp_root / "results"
    if temp_root.exists():
        resolved = temp_root.resolve()
        allowed = (repo / "data" / "derived").resolve()
        if allowed not in resolved.parents and resolved != allowed:
            raise SystemExit(f"refuse to remove outside data/derived: {resolved}")
        shutil.rmtree(resolved)
    temp_root.mkdir(parents=True, exist_ok=True)

    cmd = [
        sys.executable,
        "tools/m2_build_label_dataset.py",
        "--dataset", str((repo / args.dataset).resolve() if not args.dataset.is_absolute() else args.dataset),
        "--split", str((repo / args.split).resolve() if not args.split.is_absolute() else args.split),
        "--out-dir", str(temp_results),
        "--data-out", str(temp_data),
    ]
    proc = subprocess.run(cmd, cwd=str(repo), capture_output=True, text=True, shell=False)
    if proc.returncode != 0:
        print(proc.stdout)
        print(proc.stderr)
        return proc.returncode

    baseline_manifest = json.loads((repo / args.baseline_results / "m2_manifest.json").read_text(encoding="utf-8"))
    temp_manifest = json.loads((temp_results / "m2_manifest.json").read_text(encoding="utf-8"))
    baseline_hashes = {Path(k).name: v for k, v in baseline_manifest["outputs"].items()}
    temp_hashes = {Path(k).name: v for k, v in temp_manifest["outputs"].items()}
    checks = {
        "counts_equal": baseline_manifest["counts"] == temp_manifest["counts"],
        "rules_equal": baseline_manifest["rules"] == temp_manifest["rules"],
        "inputs_equal": baseline_manifest["inputs"] == temp_manifest["inputs"],
        "artifact_hashes_equal": baseline_hashes == temp_hashes,
    }
    status = "passed" if all(checks.values()) else "failed"
    output = {
        "status": status,
        "checks": checks,
        "baseline_manifest_sha256": sha256_file(repo / args.baseline_results / "m2_manifest.json"),
        "temp_manifest_sha256": sha256_file(temp_results / "m2_manifest.json"),
        "artifact_hashes": {"baseline": baseline_hashes, "repro": temp_hashes},
        "command": cmd,
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(output, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    shutil.rmtree(temp_root)
    print(json.dumps({"status": status, "checks": checks}, ensure_ascii=False))
    return 0 if status == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
