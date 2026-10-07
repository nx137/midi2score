"""阶段 2 骨架测试：恢复、隔离、跨线程 store、章程不可变、消息窗口、漂移检测。"""

from __future__ import annotations

import hashlib
from pathlib import Path

import pytest
from langgraph.types import Command

from research_agent.graph import compile_graph, sqlite_persistence, thread_config
from research_agent.memory import CHARTER_PATH, initial_state, recall_decisions

PROJECT = "midi2score"


def sha(p: Path) -> str:
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


@pytest.fixture()
def graph(tmp_path):
    with sqlite_persistence(tmp_path / "cp.db", tmp_path / "store.db") as (cp, store):
        yield compile_graph(cp, store)


def test_resume_same_thread(graph):
    cfg = thread_config(PROJECT, "T1")
    graph.invoke(initial_state(PROJECT), cfg)
    snap = graph.get_state(cfg)
    assert snap.next, "应在 human_review 处中断"
    graph.invoke(Command(resume="approve"), cfg)
    snap = graph.get_state(cfg)
    assert not snap.next
    assert snap.values["approval"] == "approve"
    assert snap.values["current_phase"] == "reviewed"


def test_thread_isolation(graph):
    a, b = thread_config(PROJECT, "A"), thread_config(PROJECT, "B")
    graph.invoke(initial_state(PROJECT), a)
    graph.invoke(initial_state(PROJECT), b)
    graph.invoke(Command(resume="approve"), a)
    graph.invoke(Command(resume="reject"), b)
    assert graph.get_state(a).values["approval"] == "approve"
    assert graph.get_state(b).values["approval"] == "reject"
    assert graph.get_state(a).values["decisions"] != graph.get_state(b).values["decisions"]


def test_store_cross_thread(tmp_path):
    with sqlite_persistence(tmp_path / "cp.db", tmp_path / "store.db") as (cp, store):
        graph = compile_graph(cp, store)
        cfg = thread_config(PROJECT, "A")
        graph.invoke(initial_state(PROJECT), cfg)
        graph.invoke(Command(resume="approve"), cfg)

        stored = recall_decisions(store, PROJECT)
        assert [d["id"] for d in stored] == ["D-WP-1"]
        assert stored[0]["status"] == "confirmed"
        assert recall_decisions(store, "other-project") == []


def test_charter_not_modified(graph):
    before = sha(CHARTER_PATH)
    cfg = thread_config(PROJECT, "C")
    graph.invoke(initial_state(PROJECT), cfg)
    graph.invoke(Command(resume="approve"), cfg)
    assert sha(CHARTER_PATH) == before
    assert graph.get_state(cfg).values["verification"].charter_sha256 == before


def test_messages_window_bounded(graph):
    cfg = thread_config(PROJECT, "W")
    graph.invoke(initial_state(PROJECT, max_iterations=3), cfg)
    for _ in range(10):
        graph.invoke(Command(resume="reject"), cfg)
    assert len(graph.get_state(cfg).values["messages"]) <= 20


def test_verifier_detects_charter_drift(graph):
    st = initial_state(PROJECT, max_iterations=1)
    st["charter_sha256"] = "0" * 64
    cfg = thread_config(PROJECT, "DRIFT")
    graph.invoke(st, cfg)
    snap = graph.get_state(cfg)
    assert snap.values["verification"].passed is False
    assert any("章程" in issue for issue in snap.values["verification"].issues)
    assert snap.next, "冲突必须停在人工确认，不得自动继续"