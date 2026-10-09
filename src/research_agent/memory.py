"""章程加载、上下文窗口裁剪、长期 store 读写与 Goal Contract 初始化。"""

from __future__ import annotations

import hashlib
import re
from pathlib import Path

from langchain_core.messages import AnyMessage, RemoveMessage
from langgraph.store.base import BaseStore

from .contract import DEFAULT_BASELINE_PATH, build_goal_contract, contract_drift
from .schemas import AcceptanceCriterion, Decision, TodoItem, WorkPackage

REPO_ROOT = Path(__file__).resolve().parents[2]
CHARTER_PATH = REPO_ROOT / "TASK_CHARTER.md"

MAX_MESSAGES = 20

_CONSTRAINT_RE = re.compile(r"^- \*\*(HC-\d+|GV-\d+)\*\* (.+)$")

_CHARTER_TARGET = r"(TASK_CHARTER\.md|任务章程|章程)"
_CHARTER_VERB = r"(?:(?<!被)(?<!是否)(修改)|写入|改写|编辑|删除|覆盖|变更|rewrite|write|edit|modify|delete|overwrite)"
_CHARTER_WRITE_RE = re.compile(
    rf"(?:{_CHARTER_TARGET}[^\n]{{0,40}}?{_CHARTER_VERB}|{_CHARTER_VERB}[^\n]{{0,40}}?{_CHARTER_TARGET})",
    re.IGNORECASE,
)


def is_charter_write_attempt(text: str) -> bool:
    return bool(_CHARTER_WRITE_RE.search(text or ""))


def sha256_file(path: Path) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def load_charter(path: Path | None = None) -> dict[str, object]:
    p = Path(path or CHARTER_PATH)
    text = p.read_text(encoding="utf-8")
    constraints = [
        f"{m.group(1)}: {m.group(2).strip()}"
        for m in (_CONSTRAINT_RE.match(line) for line in text.splitlines())
        if m
    ]
    return {"charter_text": text, "charter_sha256": sha256_file(p), "hard_constraints": constraints}


def trim_messages(messages: list[AnyMessage], max_messages: int = MAX_MESSAGES) -> list[RemoveMessage]:
    if len(messages) <= max_messages:
        return []
    return [RemoveMessage(id=m.id) for m in messages[: len(messages) - max_messages] if m.id]


def as_dict(record: object) -> dict:
    return record.model_dump(mode="json") if hasattr(record, "model_dump") else dict(record)  # type: ignore[arg-type]


def decisions_ns(project_id: str) -> tuple[str, ...]:
    return ("research", project_id, "decisions")


def remember_decision(store: BaseStore, project_id: str, decision: Decision) -> None:
    existing = store.get(decisions_ns(project_id), decision.id)
    if existing is not None and existing.value != as_dict(decision):
        raise ValueError(f"decision id collision: {decision.id}")
    store.put(decisions_ns(project_id), decision.id, as_dict(decision))


def recall_decisions(store: BaseStore, project_id: str, limit: int = 10) -> list[dict]:
    items = store.search(decisions_ns(project_id), limit=limit)
    return [item.value for item in items]


def initial_state(
    project_id: str = "midi2score",
    max_iterations: int = 3,
    charter_path: Path | str | None = None,
    baseline_path: Path | str | None = None,
) -> dict:
    charter = load_charter(Path(charter_path) if charter_path else None)
    contract = build_goal_contract(REPO_ROOT)
    drift = contract_drift(contract, Path(baseline_path) if baseline_path else DEFAULT_BASELINE_PATH)
    return {
        "project_id": project_id,
        "charter_text": charter["charter_text"],
        "charter_sha256": charter["charter_sha256"],
        "hard_constraints": charter["hard_constraints"],
        "goal_contract": contract,
        "contract_drift": drift,
        "context_packet": None,
        "messages": [],
        "research_questions": {},
        "work_packages": {
            "WP-1": WorkPackage(id="WP-1", goal="接通 LangGraph 控制平面并留下可复现证据", phase="control", goal_refs=["GOAL-1"], constraint_refs=["GOAL-1"], allowed_tools=["python"]),
            "WP-2": WorkPackage(id="WP-2", goal="把结构化状态写入 SQLite checkpointer/store", phase="control", goal_refs=["GOAL-1"], constraint_refs=["GOAL-1"], allowed_tools=["python"]),
        },
        "decisions": {},
        "assumptions": {},
        "evidence": {},
        "todos": {"T-1": TodoItem(id="T-1", text="阶段 4 补齐进程重启恢复测试", blocking=["阶段 3"])},
        "acceptance": {"AC-S1": AcceptanceCriterion(id="AC-S1", statement="相同 thread_id 可恢复", method="阶段 4 测试 1")},
        "policy_attempts": {},
        "execution_records": {},
        "current_phase": "init",
        "active_work_package": None,
        "iteration": 0,
        "max_iterations": max_iterations,
        "last_result": None,
        "verification": None,
        "alignment": None,
        "charter_write_attempt": False,
        "recalled_decisions": [],
        "pending_human_action": None,
        "approval": None,
    }


__all__ = ["CHARTER_PATH", "MAX_MESSAGES", "as_dict", "decisions_ns", "initial_state", "is_charter_write_attempt", "load_charter", "recall_decisions", "remember_decision", "sha256_file", "trim_messages"]
