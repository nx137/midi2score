#!/usr/bin/env python
"""B2 前置：谱面解析扩展（**不修改** parse_score；用独立函数追加字段）。

新字段：pitch(整数 MIDI 音高) / chord(bool) / voice / staff / duration(四分音符)
派生量（写死，供 B2）：锚点 t 的音符集合 = onset ∈ [t, t+GRID) 的全部音符（跨 staff/voice）；
bass(t)=min(pitch)、bass_pc(t)=bass(t) mod 12、pcs(t)={pitch mod 12}。

**不变量**：本模块的消费者数 = 0，直到 B2 显式使用；不得进入锚点构造/匹配/划分。
"""

from __future__ import annotations

from pathlib import Path

from lxml import etree

GRID = 0.25


def _first(el, tag):
    r = el.xpath(f".//*[local-name()='{tag}']")
    return r[0] if r else None


def _text(el, tag):
    x = _first(el, tag)
    return x.text if x is not None and x.text else None


def parse_score_extended(xml_path: Path) -> dict[str, dict]:
    """notes[id] = {measure, pos, pitch, chord, voice, staff, duration}。pos/duration 单位=四分音符。"""
    root = etree.parse(str(xml_path)).getroot()
    divisions = 1.0
    notes: dict[str, dict] = {}
    measure_start = 0.0
    for mi, measure in enumerate(root.xpath(".//*[local-name()='measure']")):
        pos = 0.0
        max_pos = 0.0
        for el in measure.iter():
            tag = etree.QName(el).localname
            if tag == "divisions":
                divisions = float(el.text or 1)
            elif tag == "backup":
                d = _text(el, "duration")
                if d: pos -= float(d) / divisions
            elif tag == "forward":
                d = _text(el, "duration")
                if d:
                    pos += float(d) / divisions
                    max_pos = max(max_pos, pos)
            elif tag == "note":
                nid = el.get("id")
                step, alter, octave = _text(el, "step"), _text(el, "alter"), _text(el, "octave")
                pitch = None
                if step and octave:
                    base = {"C":0,"D":2,"E":4,"F":5,"G":7,"A":9,"B":11}.get(step.upper())
                    if base is not None:
                        pitch = 12 * (int(octave) + 1) + base + int(alter or 0)
                dur = _text(el, "duration")
                if nid:
                    notes[nid] = {
                        "measure": mi,
                        "pos": measure_start + pos,
                        "pitch": pitch,
                        "chord": _first(el, "chord") is not None,
                        "voice": _text(el, "voice"),
                        "staff": _text(el, "staff") or "1",
                        "duration": (float(dur) / divisions) if dur else 0.0,
                    }
                if _first(el, "chord") is None and dur:
                    pos += float(dur) / divisions
                    max_pos = max(max_pos, pos)
        measure_start += max_pos if max_pos > 0 else 0.0
    return notes


def anchor_features(notes: dict[str, dict], t: float, grid: float = GRID) -> dict:
    """锚点 t 的派生量（写死后供 B2）：音符集合 onset ∈ [t, t+grid)。"""
    sel = [n["pitch"] for n in notes.values() if n["pitch"] is not None and t <= n["pos"] < t + grid]
    if not sel:
        return {"n_notes": 0, "bass": None, "bass_pc": None, "pcs": frozenset()}
    bass = min(sel)
    return {"n_notes": len(sel), "bass": bass, "bass_pc": bass % 12, "pcs": frozenset(p % 12 for p in sel)}


def measure_starts(xml_path: Path) -> list[float]:
    """小节起始全局位置（四分音符）。累加规则与 parse_score 逐字相同：
    measure_start += max_pos if max_pos > 0 else 0.0（零长度小节与其后小节共享起点）。
    纯新增函数，不改变任何既有路径（D-0067 ①）。
    """
    root = etree.parse(str(xml_path)).getroot()
    divisions = 1.0
    starts: list[float] = []
    measure_start = 0.0
    for measure in root.xpath(".//*[local-name()='measure']"):
        starts.append(measure_start)
        pos = 0.0
        max_pos = 0.0
        for el in measure.iter():
            tag = etree.QName(el).localname
            if tag == "divisions":
                divisions = float(el.text or 1)
            elif tag == "backup":
                d = _text(el, "duration")
                if d: pos -= float(d) / divisions
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
    return starts
