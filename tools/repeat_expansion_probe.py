#!/usr/bin/env python
"""①a 决定性测量：MuseScore 导出是否展开反复段落（D-0039 坐标系前置）。

方法：取一对同乐章变体（有反复版 vs *_no_repeat 版）分别导出 MIDI，比较音符数。
  音符数接近        -> MuseScore 会展开反复
  *_no_repeat 明显更多（反复已写开） -> 不展开
用法:
  python tools/repeat_expansion_probe.py --pair Beethoven/Piano_Sonatas/31-2 Beethoven/Piano_Sonatas/31-2_no_repeat
  python tools/repeat_expansion_probe.py --exitcode-repeat 3
"""

from __future__ import annotations

import argparse
import hashlib
import subprocess
from pathlib import Path

import mido

MS = Path(r"D:\MuseScore 4\bin\MuseScore4.exe")


def export(xml: Path, out: Path, force: bool) -> dict:
    out.parent.mkdir(parents=True, exist_ok=True)
    out.unlink(missing_ok=True)
    cmd = [str(MS)] + (["-f"] if force else []) + ["-o", str(out), str(xml)]
    p = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace",
                       timeout=300, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    h = hashlib.sha256(out.read_bytes()).hexdigest() if out.is_file() else None
    return {"cmd": subprocess.list2cmdline(cmd), "exit": p.returncode,
            "bytes": out.stat().st_size if out.is_file() else None, "sha256": h}


def note_count(mid: Path) -> int:
    mf = mido.MidiFile(str(mid))
    return sum(1 for tr in mf.tracks for msg in tr if msg.type == "note_on" and msg.velocity > 0)


def cc64_count(mid: Path) -> int:
    mf = mido.MidiFile(str(mid))
    return sum(1 for tr in mf.tracks for msg in tr if msg.type == "control_change" and msg.control == 64)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dataset", type=Path, default=Path("data/asap-dataset"))
    ap.add_argument("--pair", nargs=2, default=["Beethoven/Piano_Sonatas/31-2", "Beethoven/Piano_Sonatas/31-2_no_repeat"])
    ap.add_argument("--out-dir", type=Path, default=Path("evidence/R1/G1-coordsys"))
    ap.add_argument("--exitcode-file", default="Chopin/Sonata_3/3rd/xml_score.musicxml")
    ap.add_argument("--exitcode-repeat", type=int, default=3)
    args = ap.parse_args()

    print("=== ①a 反复展开决定性测量 ===")
    stats = []
    for rel in args.pair:
        xml = args.dataset / rel / "xml_score.musicxml"
        mid = args.out_dir / (rel.replace("/", "__") + ".mid")
        info = export(xml, mid, force=True)
        n = note_count(mid) if mid.is_file() else None
        c = cc64_count(mid) if mid.is_file() else None
        stats.append({"relative": rel, "notes": n, "cc64": c, **info})
        print(f"  {rel:<45} notes={n:<7} cc64={c:<5} exit={info['exit']} bytes={info['bytes']}")
    a, b = stats
    if a["notes"] and b["notes"]:
        ratio = round(b["notes"] / a["notes"], 4)
        verdict = "MuseScore 展开反复（音符数接近，no_repeat/有反复 = %.4f）" % ratio if ratio < 1.5 else \
                  "*_no_repeat 明显更多（ratio=%.4f）→ 不展开反复" % ratio
        print(f"  -> ratio(no_repeat / with_repeat) = {ratio}；结论：{verdict}")

    print(f"\n=== 退出码对称复现：{args.exitcode_file} ×{args.exitcode_repeat} ===")
    xml = args.dataset / args.exitcode_file
    for i in range(args.exitcode_repeat):
        mid = args.out_dir / "exitcode_repeat.mid"
        info = export(xml, mid, force=True)
        print(f"  run{i+1}: exit={info['exit']} bytes={info['bytes']} sha256={(info['sha256'] or '')[:16]}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())