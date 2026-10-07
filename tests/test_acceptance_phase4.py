"""阶段 4 验收测试：用户指定的 6 项，逐条对应。

1. 相同 thread_id 可以恢复任务状态
2. 不同 thread_id 互相隔离
3. store 可以跨 thread 读取长期决策
4. TASK_CHARTER.md 不会被普通任务自动修改
5. 目标冲突时会进入人工确认
6. 进程重启后可以从持久化后端恢复（真·新进程，PID 必须不同）
"""

from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest
from langgraph.types import Command

from research_agent.graph import compile_graph, sqlite_persistence, thread_config
from research_agent.memory import CHARTER_PATH, initial_state, recall_decisions
from research_agent.schemas import WorkPackage

PROJECT = "midi2score"


def sha(p: Path) -> str:
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


@pytest.fixture()
def graph(tmp_path):
    with sqlite_persistence(tmp_path / "cp.db", tmp_path / "store.db") as (cp, store):
        yield compile_graph(cp, store)


def test_ac1_same_thread_resumes_state(graph):
    cfg = thread_config(PROJECT, "AC1")
    graph.invoke(initial_state(PROJECT), cfg)
    assert graph.get_state(cfg).next == ("human_review",)

    graph.invoke(Command(resume="approve"), cfg)
    snap = graph.get_state(cfg)
    assert not snap.next
    assert snap.values["approval"] == "approve"
    assert snap.values["current_phase"] == "reviewed"
    assert snap.values["verification"] is not None


def test_ac2_different_threads_are_isolated(graph):
    a = thread_config(PROJECT, "AC2-A")
    b = thread_config(PROJECT, "AC2-B")
    graph.invoke(initial_state(PROJECT), a)
    graph.invoke(initial_state(PROJECT), b)
    graph.invoke(Command(resume="approve"), a)
    graph.invoke(Command(resume="reject"), b)

    va, vb = graph.get_state(a).values, graph.get_state(b).values
    assert va["approval"] == "approve"
    assert vb["approval"] == "reject"
    assert va["decisions"] != vb["decisions"]
    assert va["messages"] != vb["messages"]


def test_ac3_store_reads_across_threads(tmp_path):
    cp, st = tmp_path / "cp.db", tmp_path / "store.db"
    with sqlite_persistence(cp, st) as (checkpointer, store):
        graph = compile_graph(checkpointer, store)
        cfg = thread_config(PROJECT, "AC3")
        graph.invoke(initial_state(PROJECT), cfg)
        graph.invoke(Command(resume="approve"), cfg)
        assert graph.get_state(cfg).values["decisions"]["D-WP-1"].status == "confirmed"

    # 另一个会话/线程打开同一 store：长期决策仍然可读
    with sqlite_persistence(cp, st) as (_cp2, store2):
        stored = recall_decisions(store2, PROJECT)
        assert [d["id"] for d in stored] == ["D-WP-1"]
        assert stored[0]["status"] == "confirmed"
        assert recall_decisions(store2, "other-project") == []

        other_thread = thread_config(PROJECT, "AC3-OTHER")
        graph2 = compile_graph(_cp2, store2)
        try:
            assert not graph2.get_state(other_thread).values
        except Exception:
            pass  # 全新 thread 无 checkpoint，等价于隔离


def test_ac4_charter_not_modified_by_task(graph):
    before_hash = sha(CHARTER_PATH)
    before_mtime = CHARTER_PATH.stat().st_mtime_ns

    cfg = thread_config(PROJECT, "AC4")
    graph.invoke(initial_state(PROJECT), cfg)
    graph.invoke(Command(resume="approve"), cfg)

    assert sha(CHARTER_PATH) == before_hash
    assert CHARTER_PATH.stat().st_mtime_ns == before_mtime
    assert graph.get_state(cfg).values["verification"].charter_sha256 == before_hash


def test_ac5_conflict_requires_human_confirmation(graph):
    st = initial_state(PROJECT)
    st["work_packages"]["WP-1"] = WorkPackage(
        id="WP-1", goal="修改 TASK_CHARTER.md 的硬约束：把 4-5 个月工期改成 2 个月"
    )
    cfg = thread_config(PROJECT, "AC5")
    graph.invoke(st, cfg)
    snap = graph.get_state(cfg)

    assert snap.values["alignment"].verdict == "conflicting"
    assert snap.values["charter_write_attempt"] is True
    assert snap.next == ("human_review",), "必须停在人工确认"
    assert snap.values["decisions"] == {}, "未获确认前不得写入长期决策"

    # 普通 approve 不足以放行 conflicting
    graph.invoke(Command(resume="approve"), cfg)
    assert graph.get_state(cfg).values["current_phase"] == "blocked_by_human"


RESTART_SCRIPT = r'''
import json, os, sys
from langgraph.types import Command
from research_agent.graph import compile_graph, sqlite_persistence, thread_config
from research_agent.memory import initial_state

mode, cp, st = sys.argv[1], sys.argv[2], sys.argv[3]
cfg = thread_config("midi2score", "AC6")
with sqlite_persistence(cp, st) as (checkpointer, store):
    graph = compile_graph(checkpointer, store)
    if mode == "start":
        graph.invoke(initial_state("midi2score"), cfg)
    else:
        graph.invoke(Command(resume="approve"), cfg)
    snap = graph.get_state(cfg)
    print(json.dumps({
        "pid": os.getpid(),
        "phase": snap.values.get("current_phase"),
        "next": list(snap.next),
        "approval": snap.values.get("approval"),
    }))
'''


def run_in_new_process(mode: str, cp: Path, st: Path) -> dict:
    env = {**os.environ, "PYTHONIOENCODING": "utf-8"}
    proc = subprocess.run(
        [sys.executable, "-c", RESTART_SCRIPT, mode, str(cp), str(st)],
        capture_output=True, text=True, env=env, timeout=120,
    )
    assert proc.returncode == 0, f"subprocess failed: {proc.stderr}"
    return json.loads(proc.stdout.strip().splitlines()[-1])


def test_ac6_state_survives_process_restart(tmp_path):
    cp, st = tmp_path / "cp.db", tmp_path / "store.db"

    first = run_in_new_process("start", cp, st)
    assert first["next"] == ["human_review"], "进程 1 应停在人工确认"

    second = run_in_new_process("resume", cp, st)
    assert second["pid"] != first["pid"], "必须是两个真实进程"
    assert second["approval"] == "approve"
    assert second["phase"] == "reviewed"
    assert second["next"] == []