#!/usr/bin/env python
"""轮 B：canonical 域锚点级特征（A/B/C）。

输入空间（裁定 2）：
- 演奏 MIDI 本身（note onset；CC64 连续值）
- 该 run 的 CC64 曲线
- 谱面 MusicXML 的音符/时值/声部/小节/拍网格
- 禁止：印刷 pedal 元素、asap_annotations.json 的 performance_beats、曲目身份/折身份/路径

A 层 δ 主配置：最近拍 = 谱面 1 拍网格（四分音符）；
局部 IBI = 演奏 note onset 映射到谱面位置后的滑动窗口中位 IOI。
A_annotation 对照：δ 改用 asap_annotations.json 的 performance_beats，仅作对照。
"""
from __future__ import annotations

import bisect, hashlib, math, sys
from pathlib import Path
from typing import Any
import mido
import numpy as np
from lxml import etree

sys.path.insert(0, str(Path(__file__).resolve().parent))
from canonical_domain import GRID, canonical_anchors, score_end  # noqa: E402
from inversion_consistency import parse_alignment, parse_score, snap, to_anchor  # noqa: E402
from score_features import parse_score_extended, measure_starts  # noqa: E402

B_NAMES = ["is_chord_bass", "delta_bass_pc", "delta_pcs_card", "crosses_barlines", "pos_in_measure_beats"]
A_NAMES = ["cc64_on", "d_press_beats", "d_release_beats", "cc64_depth", "cc64_depth_mean_win", "has_press_win", "has_release_win"]
C1_OFFSETS = [-4, -3, -2, -1, 0, 1, 2, 3]
C1_NAMES = [f"c1_{name}_off{off:+d}" for name in B_NAMES for off in C1_OFFSETS]
FEATURE_NAMES = A_NAMES + B_NAMES + ["bars_since_last_down"] + C1_NAMES

# 每列来源函数；用于 V1 逐列来源报告。scorepedal 必须为 0。
FEATURE_SOURCES = {}
for n in A_NAMES:
    FEATURE_SOURCES[n] = "round_b_features.midi_cc64_features"
for n in B_NAMES:
    FEATURE_SOURCES[n] = "round_b_features.score_note_features"
FEATURE_SOURCES["bars_since_last_down"] = "round_b_features.cc64_down_history"
for n in C1_NAMES:
    FEATURE_SOURCES[n] = "round_b_features.shifted_score_note_features"


def _strip_pedals_xml(src: Path, dst: Path) -> None:
    tree = etree.parse(str(src))
    root = tree.getroot()
    for el in list(root.xpath(".//*[local-name()='pedal']")):
        parent = el.getparent()
        if parent is not None:
            parent.remove(el)
    tree.write(str(dst), encoding="utf-8", xml_declaration=True)


def load_score(score_path: Path, stripped_path: Path | None = None) -> dict[str, Any]:
    path = stripped_path or score_path
    notes = parse_score_extended(path)
    _, pedals = parse_score(path)
    end = score_end(path)
    anchors = canonical_anchors(end)
    ms = sorted(measure_starts(path))
    return {"path": path, "notes": notes, "pedals": pedals, "end": end, "anchors": anchors, "ms": ms}


def score_note_features(score: dict[str, Any]) -> tuple[np.ndarray, list[dict[str, float]]]:
    anchors = score["anchors"]
    notes = sorted(score["notes"].values(), key=lambda x: (x["pos"], x["pitch"] if x["pitch"] is not None else -1))
    ms = score["ms"]
    n = len(anchors)
    B = np.zeros((n, len(B_NAMES)), dtype=np.float32)
    ptr = 0
    prev_bass = None
    prev_pcs = frozenset()
    last_bass = None
    last_pcs = frozenset()
    for i, t in enumerate(anchors):
        while ptr < len(notes) and notes[ptr]["pos"] < t:
            ptr += 1
        j = ptr
        pitches = []
        while j < len(notes) and notes[j]["pos"] < t + GRID:
            p = notes[j].get("pitch")
            if p is not None:
                pitches.append(int(p))
            j += 1
        if pitches:
            bass = min(pitches)
            pcs = frozenset(p % 12 for p in pitches)
            last_bass, last_pcs = bass, pcs
            is_chord_bass = 1.0 if len(set(pitches)) > 1 else 0.0
        else:
            bass, pcs = last_bass, last_pcs
            is_chord_bass = 0.0
        delta_bass = 0.0 if (prev_bass is None or bass is None) else float((bass % 12) != (prev_bass % 12))
        delta_pcs = 0.0 if (not prev_pcs or not pcs) else float(len(pcs ^ prev_pcs))
        crosses = 0.0
        k = bisect.bisect_left(ms, t)
        while k < len(ms) and ms[k] < t + GRID:
            if ms[k] >= t:
                crosses = 1.0
                break
            k += 1
        k = bisect.bisect_right(ms, t) - 1
        measure_start = ms[k] if k >= 0 else 0.0
        B[i] = [is_chord_bass, delta_bass, delta_pcs, crosses, float(t - measure_start)]
        if pitches:
            prev_bass, prev_pcs = bass, pcs
    return B, [dict(zip(B_NAMES, row.tolist())) for row in B]


def _read_midi(midi_path: Path) -> tuple[list[tuple[float, int]], list[float]]:
    mid = mido.MidiFile(str(midi_path))
    t = 0.0
    cc: list[tuple[float, int]] = []
    onsets: list[float] = []
    for msg in mid:
        t += msg.time
        if msg.type == "control_change" and msg.control == 64:
            cc.append((t, int(msg.value)))
        elif msg.type == "note_on" and msg.velocity > 0:
            onsets.append(t)
    return cc, onsets


def _continuous_positions(times: list[float], seq: list[tuple[float, float]]) -> list[float]:
    out = []
    for t in times:
        got = to_anchor(t, seq, [])
        if got is not None:
            out.append(float(got[0]))
    return sorted(out)


def _local_ibi(onsets: list[float]) -> tuple[np.ndarray, np.ndarray]:
    pos = np.asarray(sorted(onsets), dtype=np.float64)
    if len(pos) < 2:
        return pos, np.asarray([], dtype=np.float64)
    return pos, np.diff(pos)


def _ibi_at(p: float, onsets: np.ndarray, iois: np.ndarray) -> float:
    if len(iois) == 0:
        return 1.0
    k = bisect.bisect_left(onsets.tolist(), p)
    lo = max(0, k - 4); hi = min(len(iois), k + 4)
    vals = iois[lo:hi]
    if len(vals) == 0:
        vals = iois
    med = float(np.median(vals))
    return med if med > 1e-9 else 1.0


def _cc_event_positions(cc: list[tuple[float, int]], seq: list[tuple[float, float]]) -> list[tuple[float, int]]:
    out = []
    for t, v in cc:
        got = to_anchor(t, seq, [])
        if got is not None:
            out.append((float(got[0]), v))
    return sorted(out)


def _event_transitions(cc: list[tuple[float, int]]) -> list[tuple[float, str]]:
    out = []
    state = False
    for t, v in cc:
        on = v >= 64
        if on != state:
            out.append((t, "start" if on else "stop"))
            state = on
    return out


def midi_cc64_features(score: dict[str, Any], midi_path: Path, seq: list[tuple[float, float]], delta_mode: str = "score_grid", ann: dict | None = None) -> tuple[np.ndarray, dict[str, Any]]:
    anchors = score["anchors"]
    n = len(anchors)
    a = np.zeros((n, len(A_NAMES)), dtype=np.float32)
    a[:, 1:3] = np.nan
    cc, onset_times = _read_midi(midi_path)
    cc_pos = _cc_event_positions(cc, seq)
    onset_pos = _continuous_positions(onset_times, seq)
    onsets, iois = _local_ibi(onset_pos)
    # depth zero-order hold at anchors
    vals = np.zeros(n, dtype=np.float64)
    j = 0; cur = 0
    for i, t in enumerate(anchors):
        while j < len(cc_pos) and cc_pos[j][0] <= t + 1e-9:
            cur = cc_pos[j][1]; j += 1
        vals[i] = cur
    a[:, 0] = (vals >= 64).astype(np.float32)
    a[:, 3] = (vals / 127.0).astype(np.float32)
    for i in range(n):
        lo = max(0, i - 16); hi = min(n, i + 16)
        a[i, 4] = np.mean(a[lo:hi, 3]) if hi > lo else 0.0
    # event-relative d: assign to snapped anchor; ties keep smaller |delta|
    start_times = [t for t, kind in _event_transitions(cc) if kind == "start"]
    stop_times = [t for t, kind in _event_transitions(cc) if kind == "stop"]
    ann_beats = None
    if delta_mode == "performance_beats" and ann is not None:
        ann_beats = ann.get("performance_beats")
    def assign_d(times: list[float], col: int):
        for t in times:
            got = to_anchor(t, seq, [])
            if got is None:
                continue
            p = float(got[0]); ia = int(round(p / GRID))
            if ia < 0 or ia >= n:
                continue
            if delta_mode == "performance_beats" and ann_beats:
                arr = np.asarray(ann_beats, dtype=np.float64)
                k = int(np.argmin(np.abs(arr - t)))
                nearest = arr[k]
                lo = max(0, k - 4); hi = min(len(arr), k + 5)
                ibi = float(np.median(np.diff(arr[lo:hi]))) if hi - lo >= 2 else 1.0
                d = (t - nearest) / (ibi if ibi > 1e-9 else 1.0)
            else:
                nearest = round(p)
                d = (p - nearest) / _ibi_at(p, onsets, iois)
            cur = a[ia, col]
            if np.isnan(cur) or abs(d) < abs(cur):
                a[ia, col] = d
    assign_d(start_times, 1)
    assign_d(stop_times, 2)
    # presence windows [t-4 beats, t+4 beats)
    press_pos = [to_anchor(t, seq, [])[0] for t in start_times if to_anchor(t, seq, []) is not None]
    rel_pos = [to_anchor(t, seq, [])[0] for t in stop_times if to_anchor(t, seq, []) is not None]
    for i, t in enumerate(anchors):
        a[i, 5] = float(any(t - 4 <= p < t + 4 for p in press_pos))
        a[i, 6] = float(any(t - 4 <= p < t + 4 for p in rel_pos))
    pos_starts = sorted(float(x) for x in press_pos)
    a[np.isnan(a)] = 0.0
    return a, {"d_press_positions": press_pos, "d_release_positions": rel_pos, "start_event_positions": pos_starts, "midi_cc_events": len(cc), "onset_positions": len(onset_pos)}


def build_run_features(score: dict[str, Any], midi_path: Path, seq: list[tuple[float, float]], delta_mode: str = "score_grid", ann: dict | None = None) -> tuple[np.ndarray, list[str], dict[str, Any]]:
    B, _ = score_note_features(score)
    A, meta = midi_cc64_features(score, midi_path, seq, delta_mode=delta_mode, ann=ann)
    anchors = score["anchors"]
    n = len(anchors)
    # bars_since_last_down
    bs = np.full((n, 1), -1.0, dtype=np.float32)
    starts = meta["start_event_positions"]
    j = 0; last = None
    for i, t in enumerate(anchors):
        while j < len(starts) and starts[j] <= t:
            last = starts[j]; j += 1
        if last is not None:
            bs[i, 0] = (t - last) / 4.0
    # C1 shifted B features, offsets in beats
    C = np.zeros((n, len(C1_NAMES)), dtype=np.float32)
    for oi, off in enumerate(C1_OFFSETS):
        shift = int(round(off / GRID))
        for bi in range(len(B_NAMES)):
            col = oi * len(B_NAMES) + bi
            for i in range(n):
                j = i + shift
                if 0 <= j < n:
                    C[i, col] = B[j, bi]
    X = np.concatenate([A, B, bs, C], axis=1).astype(np.float32)
    meta["B"] = B
    meta["A"] = A
    meta["C1"] = C
    return X, FEATURE_NAMES, meta


def make_stripped_score(score_path: Path, tmp_dir: Path) -> Path:
    tmp_dir.mkdir(parents=True, exist_ok=True)
    tag = hashlib.sha1(str(score_path.resolve()).encode("utf-8")).hexdigest()[:12]
    dst = tmp_dir / (score_path.stem + "__" + tag + "__no_pedal.musicxml")
    _strip_pedals_xml(score_path, dst)
    return dst


def change_merge_count(score: dict[str, Any]) -> int:
    """若开启 CHANGE：统计 stop 后紧随的 start 间隔 < 1 拍的对数。"""
    ped = sorted(score["pedals"], key=lambda x: (x[1], 0 if x[2] == "stop" else 1))
    stops = [p for p in ped if p[2] == "stop"]
    starts = [p for p in ped if p[2] == "start"]
    count = 0
    for _, so, _ in stops:
        nxt = [s for s in starts if s[1] > so]
        if nxt and (nxt[0][1] - so) < 1.0:
            count += 1
    return count
