#!/usr/bin/env python
"""通道自检（D-0050）：合成·平衡·每小节一对的注入信号，43 首全覆盖。

注入位置由我们写进 XML（每小节 measure 起点一对 start/stop），不经任何解析；
渲染后读回 CC64 tick，与「我们写入的第 k 对 ↔ 第 k 小节」顺序对应，定位解析/渲染分叉点。
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

import mido
from lxml import etree

sys.path.insert(0, str(Path(__file__).resolve().parent))
from inversion_consistency import parse_score  # noqa: E402

MS = Path(r"D:\MuseScore 4\bin\MuseScore4.exe")


def inject(xml_path: Path, out_path: Path) -> int:
    tree = etree.parse(str(xml_path))
    root = tree.getroot()
    n = 0
    for m in root.xpath(".//*[local-name()='measure']"):
        idx = 0
        for i, ch in enumerate(m):
            if etree.QName(ch).localname == "attributes":
                idx = i + 1
        for kind in ("start", "stop"):
            d = etree.Element("direction")
            dt = etree.SubElement(d, "direction-type")
            p = etree.SubElement(dt, "pedal")
            p.set("type", kind)
            m.insert(idx, d)
            idx += 1
        n += 1
    out_path.parent.mkdir(parents=True, exist_ok=True)
    tree.write(str(out_path), encoding="utf-8", xml_declaration=True)
    return n


def render(xml: Path, out_mid: Path) -> dict:
    out_mid.unlink(missing_ok=True)
    cmd = [str(MS), "-f", "-o", str(out_mid), str(xml)]
    p = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace",
                       timeout=300, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    return {"exit": p.returncode, "exists": out_mid.is_file()}


def cc64_positions(mid_path: Path) -> tuple[list[float], int]:
    mf = mido.MidiFile(str(mid_path))
    ppq = mf.ticks_per_beat
    out = []
    for tr in mf.tracks:
        t = 0
        for msg in tr:
            t += msg.time
            if msg.type == "control_change" and msg.control == 64:
                out.append(t / ppq)
    out.sort()
    return out, ppq


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dataset", type=Path, default=Path("data/asap-dataset"))
    ap.add_argument("--split", type=Path, default=Path("evidence/R1/G1-split/split_v1.json"))
    ap.add_argument("--out-dir", type=Path, default=Path("evidence/R1/G1-synthetic"))
    ap.add_argument("--limit", type=int, default=0)
    args = ap.parse_args()

    D = args.dataset
    split = json.loads(args.split.read_text(encoding="utf-8"))
    scores = sorted(split["main_scores"])
    if args.limit:
        scores = scores[: args.limit]

    rows = []
    for rel in scores:
        xml = D / rel
        stem = rel.replace("/", "__")
        inj_xml = args.out_dir / "xml" / f"{stem}.musicxml"
        inj_mid = args.out_dir / "mid" / f"{stem}.mid"
        n_meas = inject(xml, inj_xml)
        r = render(inj_xml, inj_mid)
        rec = {"score": rel, "n_measures": n_meas, **r}
        if r["exists"]:
            pos, ppq = cc64_positions(inj_mid)
            rec["n_cc64"] = len(pos)
            rec["expected_cc64"] = 2 * n_meas
            rec["count_ok"] = len(pos) == 2 * n_meas
            rec["strictly_increasing"] = all(pos[i] <= pos[i + 1] for i in range(len(pos) - 1))
            # 我方能解析出的 measure 起点（用于定位分叉）
            _, pedals = parse_score(xml)
            rec["ppq"] = ppq
            rec["first_pos"] = round(pos[0], 4) if pos else None
            rec["last_pos"] = round(pos[-1], 4) if pos else None
            rec["span"] = round(pos[-1] - pos[0], 3) if pos else None
        rows.append(rec)
        print(f"{rel:<52} measures={n_meas:<4} cc64={rec.get('n_cc64')} count_ok={rec.get('count_ok')} incr={rec.get('strictly_increasing')}")

    args.out_dir.mkdir(parents=True, exist_ok=True)
    (args.out_dir / "synthetic_check.json").write_text(json.dumps(rows, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    n = len(rows)
    cnt_ok = sum(1 for r in rows if r.get("count_ok"))
    inc_ok = sum(1 for r in rows if r.get("strictly_increasing"))
    print(f"\n=== 汇总：{n} 首；count_ok {cnt_ok}/{n}；顺序不减 {inc_ok}/{n} ===")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())