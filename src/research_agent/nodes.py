"""planner / executor / verifier / human_review 四个节点。

阶段 2 只做结构：verifier 检查章程哈希与证据诚实性；
目标偏离三值判定（aligned/partially_aligned/conflicting）在阶段 3 接入。
节点默认使用 stub 模型，不依赖任何 LLM 供应商。
"""

from __future__ import annotations

from typing import Callable

from langchain_core.messages import AIMessage, HumanMessage
from langgraph.runtime import Runtime
from langgraph.types import interrupt

from .memory import CHARTER_PATH, recall_decisions, remember_decision, sha256_file, trim_messages
from .schemas import Decision, Evidence, TaskState, VerificationResult

APPROVE_WORDS = {"approve", "approved", "yes", "y", "ok", "批准", "同意"}


def _stub_llm(prompt: str) -> str:
    return "[stub] 未调用真实模型；骨架路径已走通。"


def planner(state: TaskState, runtime: Runtime | None = None, llm: Callable[[str], str] = _stub_llm) -> dict:
    updates: dict = {"current_phase": "plan", "iteration": state.get("iteration", 0) + 1}
    removals = trim_messages(list(state.get("messages", [])))
    if removals:
        updates["messages"] = list(removals)

    pending = [wp for wp in state["work_packages"].values() if wp.status == "pending"]
    if pending:
        wp = sorted(pending, key=lambda w: w.id)[0]
        updates["active_work_package"] = wp.id
        updates.setdefault("messages", []).append(HumanMessage(content=f"plan: {wp.id} → {wp.goal}"))
        updates["messages"].append(AIMessage(content=llm(f"为 {wp.id} 制定计划：{wp.goal}")))
    else:
        updates["active_work_package"] = None
        updates["current_phase"] = "done"

    store = getattr(runtime, "store", None)
    if store is not None:
        updates["recalled_decisions"] = [d["id"] for d in recall_decisions(store, state["project_id"], limit=5)]
    return updates


def executor(state: TaskState, runtime: Runtime | None = None, llm: Callable[[str], str] = _stub_llm) -> dict:
    wp_id = state.get("active_work_package")
    if not wp_id:
        return {"current_phase": "done"}

    wp = state["work_packages"][wp_id]
    note = llm(f"执行工作包 {wp.id}：{wp.goal}")
    # 骨架阶段不运行真实实验：证据一律 not_run，绝不写成 verified（GV-05 / HC-16）
    evidence = Evidence(id=f"EV-{wp.id}", kind="document", locator=f"work_package:{wp.id}", status="not_run")
    return {
        "work_packages": {wp.id: wp.model_copy(update={"status": "done"})},
        "evidence": {evidence.id: evidence},
        "last_result": {"work_package": wp.id, "note": note, "commands": []},
        "current_phase": "execute",
    }

def verifier(state: TaskState, runtime: Runtime | None = None, llm: Callable[[str], str] = _stub_llm) -> dict:
    """阶段 2：只做章程完整性 + 证据诚实性检查。目标偏离判定在阶段 3。"""
    issues: list[str] = []

    current_sha = sha256_file(CHARTER_PATH)
    if current_sha != state.get("charter_sha256"):
        issues.append("TASK_CHARTER.md 哈希与运行时不一致：章程被修改，必须人工确认")

    for ev in state.get("evidence", {}).values():
        if ev.status == "verified" and not ev.command:
            issues.append(f"{ev.id}: 声称 verified 但缺少 command，视为未验证")

    for ac in state.get("acceptance", {}).values():
        if ac.result == "pass" and not ac.evidence_id:
            issues.append(f"{ac.id}: 声称 pass 但缺少 evidence_id")

    result = VerificationResult(
        id="VR",
        passed=not issues,
        issues=issues,
        charter_sha256=current_sha,
    )
    return {"verification": result, "current_phase": "verify"}


def human_review(state: TaskState, runtime: Runtime | None = None) -> dict:
    """人在环闸门：interrupt() 暂停，恢复后按批准/驳回决定是否继续。"""
    verification = state.get("verification")
    payload = {
        "question": "是否批准当前工作包的产出？",
        "work_package": state.get("active_work_package"),
        "issues": list(verification.issues) if verification else [],
    }
    answer = interrupt(payload)
    text = str(answer).strip().lower()
    approved = text in APPROVE_WORDS

    updates: dict = {
        "pending_human_action": None,
        "approval": str(answer),
        "current_phase": "reviewed",
    }
    if approved:
        wp_id = state.get("active_work_package")
        store = getattr(runtime, "store", None)
        if wp_id and store is not None:
            decision = Decision(
                id=f"D-{wp_id}",
                decision=f"批准工作包 {wp_id} 的产出",
                status="confirmed",
                source="human_review",
                rationale="人在环批准；已写入长期 store 供跨线程复用",
            )
            remember_decision(store, state["project_id"], decision)
            updates["decisions"] = {decision.id: decision}
        updates["messages"] = [AIMessage(content=f"human_review: approved {wp_id}")]
    else:
        updates["messages"] = [AIMessage(content="human_review: rejected，返回 planner")]
    return updates
