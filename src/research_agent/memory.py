"""章程加载、上下文窗口裁剪、长期 store 读写。

刻意不做的事：不实现 conversation_summary.md，不建自定义记忆框架。
短期状态交给 checkpointer，长期事实交给 store，上下文只保留有界窗口。
"""

from __future__ import annotations

import hashlib
import re
from pathlib import Path

from langchain_core.messages import AnyMessage, RemoveMessage
from langgraph.store.base import BaseStore

from .schemas import AcceptanceCriterion, Decision, TodoItem, WorkPackage

REPO_ROOT = Path(__file__).resolve().parents[2]
CHARTER_PATH = REPO_ROOT / "TASK_CHARTER.md"

# 上下文预算：只保留最近 N 条消息；更早的信息必须在结构化字段里
MAX_MESSAGES = 20

_CONSTRAINT_RE = re.compile(r"^- \*\*(HC-\d+|GV-\d+)\*\* (.+)$")

# ponytail: 关键词启发式，宁可误报也要拦住；升级路径 = 由 LLM 做意图判定
_CHARTER_TARGET = r"(TASK_CHARTER\.md|任务章程|章程)"
_CHARTER_VERB = r"(?:(?<!被)(?<!是否)(修改)|写入|改写|编辑|删除|覆盖|变更|rewrite|write|edit|modify|delete|overwrite)"
_CHARTER_WRITE_RE = re.compile(
    rf"(?:{_CHARTER_TARGET}[^\n]{{0,40}}?{_CHARTER_VERB}|{_CHARTER_VERB}[^\n]{{0,40}}?{_CHARTER_TARGET})",
    re.IGNORECASE,
)


def is_charter_write_attempt(text: str) -> bool:
    """检测"修改章程"的意图；命中则拒绝执行并交由人工确认（GV-01）。"""
    return bool(_CHARTER_WRITE_RE.search(text or ""))


def sha256_file(path: Path) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def load_charter(path: Path | None = None) -> dict[str, object]:
    """读取 TASK_CHARTER.md -> 正文、哈希、可机读硬约束清单。只读，绝不写。"""
    p = Path(path or CHARTER_PATH)
    text = p.read_text(encoding="utf-8")
    constraints = [
        f"{m.group(1)}: {m.group(2).strip()}"
        for m in (_CONSTRAINT_RE.match(line) for line in text.splitlines())
        if m
    ]
    return {"charter_text": text, "charter_sha256": sha256_file(p), "hard_constraints": constraints}


def trim_messages(messages: list[AnyMessage], max_messages: int = MAX_MESSAGES) -> list[RemoveMessage]:
    """返回需要删除的旧消息；由 planner 提交给 add_messages reducer。"""
    if len(messages) <= max_messages:
        return []
    return [RemoveMessage(id=m.id) for m in messages[: len(messages) - max_messages] if m.id]


def as_dict(record: object) -> dict:
    return record.model_dump(mode="json") if hasattr(record, "model_dump") else dict(record)  # type: ignore[arg-type]


# ---------- 长期记忆：跨 thread 的事实 / 决策 / 知识 ----------

def decisions_ns(project_id: str) -> tuple[str, ...]:
    return ("research", project_id, "decisions")


def remember_decision(store: BaseStore, project_id: str, decision: Decision) -> None:
    """只写已确认决策；暂定假设不进入长期 store。"""
    store.put(decisions_ns(project_id), decision.id, as_dict(decision))


def recall_decisions(store: BaseStore, project_id: str, limit: int = 10) -> list[dict]:
    items = store.search(decisions_ns(project_id), limit=limit)
    return [item.value for item in items]


# ---------- 示例初始状态（demo / 测试用） ----------

def initial_state(project_id: str = "midi2score", max_iterations: int = 3) -> dict:
    charter = load_charter()
    return {
        "project_id": project_id,
        "charter_text": charter["charter_text"],
        "charter_sha256": charter["charter_sha256"],
        "hard_constraints": charter["hard_constraints"],
        "messages": [],
        "research_questions": {},
        "work_packages": {
            "WP-1": WorkPackage(id="WP-1", goal="接通 LangGraph 骨架并留下可复现证据"),
            "WP-2": WorkPackage(id="WP-2", goal="把结构化状态写入 SQLite checkpointer/store"),
        },
        "decisions": {},
        "assumptions": {},
        "evidence": {},
        "todos": {
            "T-1": TodoItem(id="T-1", text="阶段 4 补齐进程重启恢复测试", blocking=["阶段 3"]),
        },
        "acceptance": {
            "AC-S1": AcceptanceCriterion(id="AC-S1", statement="相同 thread_id 可恢复", method="阶段 4 测试 1"),
        },
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


__all__ = [
    "CHARTER_PATH", "MAX_MESSAGES", "as_dict", "decisions_ns", "initial_state",
    "is_charter_write_attempt", "load_charter", "recall_decisions", "remember_decision", "sha256_file", "trim_messages",
    
]