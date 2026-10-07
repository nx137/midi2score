#!/usr/bin/env python
"""R1-3b：MusicXML → MIDI 踏板导出探针（MuseScore 4.7.5）。

判据（计划书 §10.3）：
  含印刷 pedal 的乐谱导出 MIDI 后必须真的产生 CC64，且 CC64 消息数 / pedal 元素数 ≈ 1.0；
  若完全没有 CC64 → 合成路线作废，立即停止上报（G0 否决条件）。
  负对照（无 pedal 的乐谱）应产生 0 条 CC64。

用法:
  python tools/musescore_export_probe.py --positive 3 --negative 1
"""

from __future__ import annotations

import argparse
import csv
import json
import subprocess
import time
from collections import Counter
from pathlib import Path

import mido
from lxml import etree

PEDAL_XPATH = ".//*[local-name()='pedal']"
DEFAULT_MUSESCORE = Path(r"D:\MuseScore 4\bin\MuseScore4.exe")


def count_pedal(xml_path: Path) -> dict:
    root = etree.parse(str(xml_path)).getroot()
    elems = root.xpath(PEDAL_XPATH)
    kinds = Counter(e.get("type") for e in elems)
    return {
        "pedal_elements": len(elems),
        "pedal_start": kinds.get("start", 0),
        "pedal_stop": kinds.get("stop", 0),
        "pedal_other": sum(v for k, v in kinds.items() if k not in ("start", "stop")),
    }


def count_cc64(mid_path: Path) -> dict:
    mid = mido.MidiFile(str(mid_path))
    n = 0
    values: set[int] = set()
    for track in mid.tracks:
        for msg in track:
            if msg.type == "control_change" and msg.control == 64:
                n += 1
                values.add(msg.value)
    return {
        "cc64_messages": n,
        "cc64_distinct_values": len(values),
        "cc64_nonendpoint_values": sorted(v for v in values if 0 < v < 127),
    }


def find_scores(dataset: Path, positive: int, negative: int) -> tuple[list[Path], list[Path]]:
    pos: list[Path] = []
    neg: list[Path] = []
    for xml in sorted(dataset.rglob("*.musicxml")):
        has_pedal = count_pedal(xml)["pedal_elements"] > 0
        if has_pedal and len(pos) < positive:
            pos.append(xml)
        elif not has_pedal and len(neg) < negative:
            neg.append(xml)
        if len(pos) >= positive and len(neg) >= negative:
            break
    return pos, neg


def export_one(xml: Path, out_mid: Path, exe: Path, force: bool, timeout: int) -> dict:
    out_mid.parent.mkdir(parents=True, exist_ok=True)
    out_mid.unlink(missing_ok=True)
    command = [str(exe)]
    if force:
        command.append("-f")
    command.extend(["-o", str(out_mid), str(xml)])
    started = time.perf_counter()
    try:
        completed = subprocess.run(
            command, capture_output=True, text=True, encoding="utf-8", errors="replace",
            timeout=timeout, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
        exit_code, stdout, stderr, timed_out = completed.returncode, completed.stdout or "", completed.stderr or "", False
    except subprocess.TimeoutExpired as exc:
        exit_code, stdout, stderr, timed_out = None, str(exc.stdout or ""), str(exc.stderr or ""), True
    return {
        "command": subprocess.list2cmdline(command),
        "exit_code": exit_code,
        "timed_out": timed_out,
        "wall_seconds": round(time.perf_counter() - started, 3),
        "output_exists": out_mid.is_file(),
        "stdout_head": stdout.strip()[:200],
        "stderr_head": stderr.strip()[:200],
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dataset", type=Path, default=Path("data/asap-dataset"))
    parser.add_argument("--out-dir", type=Path, default=Path("evidence/R1/R1-3b"))
    parser.add_argument("--musescore", type=Path, default=DEFAULT_MUSESCORE)
    parser.add_argument("--positive", type=int, default=3)
    parser.add_argument("--negative", type=int, default=1)
    parser.add_argument("--timeout", type=int, default=180)
    parser.add_argument("--force", action="store_true", help="pass -f to MuseScore (see plan §11.2 B-a)")
    args = parser.parse_args()

    if not args.musescore.is_file():
        raise SystemExit(f"MuseScore executable not found: {args.musescore}")

    version = subprocess.run(
        [str(args.musescore), "--version"], capture_output=True, text=True,
        encoding="utf-8", errors="replace", timeout=60,
        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
    )
    pos, neg = find_scores(args.dataset, args.positive, args.negative)
    rows: list[dict] = []
    for kind, xml in [("positive", p) for p in pos] + [("negative", n) for n in neg]:
        rel = str(xml.relative_to(args.dataset)).replace("\\", "/")
        mid = args.out_dir / Path(rel).with_suffix(".mid")
        pedal = count_pedal(xml)
        export = export_one(xml, mid, args.musescore, force=args.force, timeout=args.timeout)
        cc64 = count_cc64(mid) if export["output_exists"] else {"cc64_messages": None, "cc64_distinct_values": None, "cc64_nonendpoint_values": []}
        # 口径 1（计划书 §10.3 字面）: CC64 / pedal 元素数
        ratio_elements = None
        if cc64["cc64_messages"] is not None and pedal["pedal_elements"]:
            ratio_elements = round(cc64["cc64_messages"] / pedal["pedal_elements"], 4)
        # 口径 2（渲染器恒等式, §10.2）: CC64 == 2 * min(start, stop)
        identity_expected = 2 * min(pedal["pedal_start"], pedal["pedal_stop"])
        identity_match = cc64["cc64_messages"] == identity_expected if cc64["cc64_messages"] is not None else None
        veto = bool(pedal["pedal_start"] > 0 and cc64["cc64_messages"] == 0)
        rows.append({"kind": kind, "relative_path": rel, **pedal, **export, **cc64,
                     "cc64_per_pedal_element": ratio_elements,
                     "identity_expected_2xmin": identity_expected,
                     "identity_match": identity_match,
                     "veto_no_cc64_with_start": veto})
        print(f"[{kind}] {rel} exit={export['exit_code']} elems={pedal['pedal_elements']} "
              f"start={pedal['pedal_start']} stop={pedal['pedal_stop']} cc64={cc64['cc64_messages']} "
              f"ratio_elems={ratio_elements} identity_match={identity_match} veto={veto}")

    args.out_dir.mkdir(parents=True, exist_ok=True)
    (args.out_dir / "export_probe.json").write_text(
        json.dumps({"musescore": str(args.musescore), "version_stdout": (version.stdout or "").strip(),
                    "version_exit": version.returncode, "rows": rows}, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8")
    with (args.out_dir / "export_probe.csv").open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0].keys()), extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)

    positives = [r for r in rows if r["kind"] == "positive"]
    negatives = [r for r in rows if r["kind"] == "negative"]
    failures = [row["relative_path"] for row in rows if not row["output_exists"]]
    no_cc64 = [r["relative_path"] for r in positives if r["cc64_messages"] == 0]
    unbalanced = [r for r in positives if r["pedal_start"] != r["pedal_stop"]]
    vetoes = [r["relative_path"] for r in positives if r["veto_no_cc64_with_start"]]
    identity_ok = sum(1 for r in positives if r["identity_match"])
    print("\n=== SUMMARY ===")
    print(f"musescore: {(version.stdout or '').strip()} (exit {version.returncode})")
    print(f"positive exports ok: {sum(1 for r in positives if r['output_exists'])}/{len(positives)}")
    print(f"positive with CC64>0: {sum(1 for r in positives if (r['cc64_messages'] or 0) > 0)}/{len(positives)}")
    print(f"negative controls with CC64==0: {sum(1 for r in negatives if r['cc64_messages'] == 0)}/{len(negatives)}")
    print(f"structurally unbalanced (start != stop): {len(unbalanced)}/{len(positives)}")
    print(f"identity  CC64 == 2*min(start,stop): {identity_ok}/{len(positives)}")
    print(f"literal   CC64 / pedal_elements ~= 1.0: {sum(1 for r in positives if (r['cc64_per_pedal_element'] or 0) >= 0.8)}/{len(positives)}")
    print(f"failures: {failures}")
    print(f"positive with ZERO cc64 (informational): {no_cc64}")
    print(f"G0 VETO (start>0 but cc64==0): {vetoes}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())