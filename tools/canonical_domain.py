#!/usr/bin/env python
"""统一评测域（D-0074，闭区间）：[0, score_end] canonical anchor grid.

score_end 只使用 MusicXML 本身的小节长度累加，与 parse_score 的
`measure_start += max_pos if max_pos > 0 else 0.0` 逐字一致；不读取
alignment、演奏 MIDI、pedal 标注或 performance_beats。
"""
from __future__ import annotations

from pathlib import Path
from lxml import etree
import math

GRID = 0.25


def _first(el, tag):
    r = el.xpath(f".//*[local-name()='{tag}']")
    return r[0] if r else None


def _text(el, tag):
    x = _first(el, tag)
    return x.text if x is not None and x.text else None


def score_end(xml_path: Path) -> float:
    """谱面自身结束位置（四分音符），不依赖任何对齐/演奏/踏板标注。"""
    root = etree.parse(str(xml_path)).getroot()
    divisions = 1.0
    measure_start = 0.0
    for measure in root.xpath(".//*[local-name()='measure']"):
        pos = 0.0
        max_pos = 0.0
        for el in measure.iter():
            tag = etree.QName(el).localname
            if tag == "divisions":
                divisions = float(el.text or 1)
            elif tag == "backup":
                d = _text(el, "duration")
                if d:
                    pos -= float(d) / divisions
            elif tag == "forward":
                d = _text(el, "duration")
                if d:
                    pos += float(d) / divisions
                    max_pos = max(max_pos, pos)
            elif tag == "note":
                if _first(el, "chord") is None:
                    d = _text(el, "duration")
                    if d:
                        pos += float(d) / divisions
                        max_pos = max(max_pos, pos)
        measure_start += max_pos if max_pos > 0 else 0.0
    return measure_start


def canonical_anchors(scoreend: float, grid: float = GRID) -> list[float]:
    """[0, scoreend] 内的全部格点，包含无音符格点；右端点在格点上时包含。"""
    if scoreend <= 0:
        return []
    n = int(math.floor(scoreend / grid + 1e-9)) + 1
    return [round(i * grid, 6) for i in range(n)]


def anchor_set(scoreend: float, grid: float = GRID) -> set[float]:
    return set(canonical_anchors(scoreend, grid))
