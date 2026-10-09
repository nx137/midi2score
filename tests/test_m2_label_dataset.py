from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest


pytest.importorskip("lxml")

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("m2_build_label_dataset", ROOT / "tools" / "m2_build_label_dataset.py")
assert SPEC and SPEC.loader
M2 = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(M2)


def _write_score(tmp_path: Path, pedal_types: tuple[str, ...]) -> Path:
    directions = "".join(
        f'<direction><direction-type><pedal type="{kind}"/></direction-type></direction>'
        for kind in pedal_types
    )
    xml = (
        '<score-partwise><part><measure number="1">'
        '<attributes><divisions>4</divisions></attributes>'
        '<note><rest/><duration>16</duration></note>'
        f'{directions}'
        '</measure></part></score-partwise>'
    )
    path = tmp_path / "score.musicxml"
    path.write_text(xml, encoding="utf-8")
    return path


def test_change_pair_requires_less_than_one_beat():
    pairs, consumed = M2.derive_change_pairs([(0, 1.0, "stop"), (0, 1.999, "start")])
    assert len(pairs) == 1
    assert consumed == {0, 1}
    assert pairs[0]["anchor"] == 2.0

    none_pairs, none_consumed = M2.derive_change_pairs([(0, 1.0, "stop"), (0, 2.0, "start")])
    assert none_pairs == []
    assert none_consumed == set()


def test_equal_position_events_preserve_document_order():
    pairs, consumed = M2.derive_change_pairs([(0, 1.0, "start"), (0, 1.0, "stop")])
    assert pairs == []
    assert consumed == set()


def test_change_pair_is_consumed_into_one_change_anchor(tmp_path):
    path = _write_score(tmp_path, ("stop", "start"))
    rows, meta = M2.build_score_rows(path, eval_eligible=True)
    last = next(row for row in rows if row["anchor"] == 4.0)
    assert meta["n_change_pairs"] == 1
    assert last["label"] == "CHANGE"
    assert last["raw_DOWN"] is True
    assert last["raw_UP"] is True
    assert last["remaining_DOWN"] is False
    assert last["remaining_UP"] is False
    assert last["supervision_mask"] == 1
    assert sum(row["label"] == "UP" for row in rows) == 0


def test_repeat_coordinate_can_be_excluded_from_supervision(tmp_path):
    path = _write_score(tmp_path, ("start",))
    rows, _ = M2.build_score_rows(path, eval_eligible=False)
    assert any(row["label"] == "DOWN" for row in rows)
    assert all(row["supervision_mask"] == 0 for row in rows)


def test_gzip_output_is_deterministic(tmp_path):
    first = tmp_path / "a.jsonl.gz"
    second = tmp_path / "b.jsonl.gz"
    rows = [{"score": "x", "anchor": 0.25, "label": "NONE", "supervision_mask": 1}]
    M2.write_jsonl_gz(first, rows)
    M2.write_jsonl_gz(second, rows)
    assert first.read_bytes() == second.read_bytes()
