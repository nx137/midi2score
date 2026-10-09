"""图装配：节点、条件路由、checkpointer、store、稳定 thread_id。"""

from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from functools import partial
from pathlib import Path
from typing import Callable, Iterator

from langgraph.checkpoint.serde.jsonplus import JsonPlusSerializer
from langgraph.checkpoint.sqlite import SqliteSaver
from langgraph.graph import END, START, StateGraph
from langgraph.store.sqlite import SqliteStore

from . import nodes, schemas
from .schemas import TaskState

DEFAULT_LLM: Callable[[str], str] = nodes._stub_llm
APPROVE_WORDS = nodes.APPROVE_WORDS
OVERRIDE_WORDS = nodes.OVERRIDE_WORDS

DATA_DIR = Path(__file__).resolve().parents[2] / "data"
CHECKPOINT_DB = DATA_DIR / "checkpoints.db"
STORE_DB = DATA_DIR / "store.db"

# checkpoint 里出现的自定义类型必须显式登记（不用 True 放行全部，避免削弱反序列化安全）
ALLOWED_MSGPACK: list[tuple[str, str]] = [
    ("research_agent.schemas", name)
    for name in (
        "ResearchQuestion", "CommandSpec", "WorkPackage", "Decision", "Assumption", "Evidence",
        "TodoItem", "AcceptanceCriterion", "VerificationResult", "AlignmentResult",
        "PolicyDecision", "ExecutionRecord", "GoalContract", "ContextPacket",
    )
]


def make_serde() -> JsonPlusSerializer:
    return JsonPlusSerializer(allowed_msgpack_modules=ALLOWED_MSGPACK)


def stable_thread_id(project_id: str, task_id: str) -> str:
    """稳定、可推导的 thread_id；禁止每次运行随机生成。"""
    if not project_id or not task_id:
        raise ValueError("project_id 与 task_id 均不能为空")
    return f"research:{project_id}:{task_id}"


def thread_config(project_id: str, task_id: str, **extra: object) -> dict:
    if "thread_id" in extra:
        raise ValueError("thread_id 由 project_id/task_id 稳定推导，不允许覆盖")
    return {"configurable": {"thread_id": stable_thread_id(project_id, task_id), **extra}}


def route_after_verifier(state: TaskState) -> str:
    """三值判定后一律进入人在环闸门：conflicting 必须人工确认，aligned 也需批准。"""
    return "human_review"


def route_after_review(state: TaskState) -> str:
    if state.get("current_phase") == "blocked_by_human":
        return "end"
    answer = str(state.get("approval", "")).strip().lower()
    if answer in APPROVE_WORDS or answer in OVERRIDE_WORDS:
        return "end"
    if state.get("iteration", 0) >= state.get("max_iterations", 3):
        return "end"
    return "planner"


def build_graph(llm: Callable[[str], str] | None = None):
    llm = llm or DEFAULT_LLM
    builder = StateGraph(TaskState)
    builder.add_node("planner", partial(nodes.planner, llm=llm))
    builder.add_node("executor", partial(nodes.executor, llm=llm))
    builder.add_node("verifier", partial(nodes.verifier, llm=llm))
    builder.add_node("human_review", nodes.human_review)

    builder.add_edge(START, "planner")
    builder.add_edge("planner", "executor")
    builder.add_edge("executor", "verifier")
    builder.add_conditional_edges(
        "verifier",
        route_after_verifier,
        {"human_review": "human_review", "planner": "planner"},
    )
    builder.add_conditional_edges(
        "human_review",
        route_after_review,
        {"end": END, "planner": "planner"},
    )
    return builder


def compile_graph(checkpointer, store, llm: Callable[[str], str] | None = None):
    return build_graph(llm).compile(checkpointer=checkpointer, store=store)


@contextmanager
def sqlite_persistence(checkpoint_db: object = None, store_db: object = None) -> Iterator[tuple[SqliteSaver, SqliteStore]]:
    """本地单进程持久化：checkpointer 存短期状态，store 存跨线程长期记忆。

    ponytail: SQLite 单进程档位；需要跨进程并发或远程部署时换 PostgresSaver/PostgresStore。
    """
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    cp_path = str(checkpoint_db or CHECKPOINT_DB)
    st_path = str(store_db or STORE_DB)
    conn = sqlite3.connect(cp_path, check_same_thread=False)
    try:
        checkpointer = SqliteSaver(conn, serde=make_serde())
        with SqliteStore.from_conn_string(st_path) as store:
            store.setup()
            yield checkpointer, store
    finally:
        conn.close()