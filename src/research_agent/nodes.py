"""planner / executor / verifier / human_review 四个节点。

阶段 3：verifier 输出三值 task_alignment（aligned / partially_aligned / conflicting）；
conflicting 一律暂停，且普通 approve 不足以放行，必须显式 override。
程序侧不存在任何写 TASK_CHARTER.md 的代码路径，并由意图拦截 + 哈希校验双重把关。
默认使用 stub 模型，不依赖任何 LLM 供应商。
"""

from __future__ import annotations

from typing import Callable

from langchain_core.messages import AIMessage, HumanMessage
from langgraph.runtime import Runtime
from langgraph.types import interrupt

from .memory import (
    CHARTER_PATH,
    is_charter_write_attempt,
    recall_decisions,
    remember_decision,
    sha256_file,
    trim_messages,
)
from .schemas import AlignmentResult, Decision, Evidence, TaskState, VerificationResult

APPROVE_WORDS = {"approve", "approved", "yes", "y", "ok", "批准", "同意"}
OVERRIDE_WORDS = {"override", "force", "强制继续", "确认覆盖", "人工覆盖"}


def _stub_llm(prompt: str) -> str:
    return "[stub] 未调用真实模型；骨架路径已走通。"


def _norm(value: object) -> str:
    return str(value).strip().lower()


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

    # GV-01：任何试图修改章程的工作包一律拒绝执行，交人工确认
    intent_text = " ".join([wp.goal, *wp.outputs])
    if is_charter_write_attempt(intent_text):
        return {
            "charter_write_attempt": True,
            "current_phase": "blocked",
            "last_result": {"work_package": wp.id, "refused": True, "reason": "检测到修改 TASK_CHARTER.md 的意图，已拒绝执行"},
            "messages": [AIMessage(content=f"executor: 拒绝 {wp.id} —— 涉及修改章程，已转人工确认")],
        }

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
    """产出 task_alignment：aligned / partially_aligned / conflicting。"""
    issues: list[str] = []
    violations: list[str] = []

    current_sha = sha256_file(CHARTER_PATH)
    if current_sha != state.get("charter_sha256"):
        violations.append("GV-01: TASK_CHARTER.md 哈希漂移——章程已被修改")
    if state.get("charter_write_attempt"):
        violations.append("GV-01: 检测到修改章程的意图，执行器已拒绝")

    for ev in state.get("evidence", {}).values():
        if ev.status == "verified" and not ev.command:
            issues.append(f"{ev.id}: 声称 verified 但缺少 command，视为未验证")
    for ac in state.get("acceptance", {}).values():
        if ac.result == "pass" and not ac.evidence_id:
            issues.append(f"{ac.id}: 声称 pass 但缺少 evidence_id")

    wp_id = state.get("active_work_package")
    questions = state.get("research_questions", {})
    if wp_id and questions:
        linked = any(wp_id in rq.linked_packages for rq in questions.values())
        if not linked:
            issues.append(f"{wp_id}: 未挂到任何研究问题（RQ），是否在章程范围内需人工确认")

    if violations:
        verdict, needs_confirm = "conflicting", True
        rationale = "违反硬约束/治理规则：" + "；".join(violations)
    elif issues:
        verdict, needs_confirm = "partially_aligned", True
        rationale = "未违反硬约束，但存在待确认问题：" + "；".join(issues)
    else:
        verdict, needs_confirm = "aligned", False
        rationale = "当前工作服务于 GOAL-1，未发现违反 HC/GV"

    alignment = AlignmentResult(
        id="AL",
        verdict=verdict,
        violates=violations,
        needs_user_confirmation=needs_confirm,
        rationale=rationale,
    )
    all_issues = violations + issues
    verification = VerificationResult(
        id="VR",
        passed=not all_issues,
        issues=all_issues,
        charter_sha256=current_sha,
    )
    return {"verification": verification, "alignment": alignment, "current_phase": "verify"}


def human_review(state: TaskState, runtime: Runtime | None = None) -> dict:
    """人在环闸门。conflicting 必须显式 override 才放行；普通 approve 不放行。"""
    alignment = state.get("alignment")
    verdict = alignment.verdict if alignment else "aligned"
    payload = {
        "question": "是否批准当前工作包的产出？",
        "work_package": state.get("active_work_package"),
        "alignment": verdict,
        "violations": list(alignment.violates) if alignment else [],
        "issues": list(state["verification"].issues) if state.get("verification") else [],
        "needs_user_confirmation": bool(alignment.needs_user_confirmation) if alignment else False,
        "hint": "conflicting 必须显式 override（强制继续）才放行；普通 approve 不足以通过。"
        if verdict == "conflicting"
        else "",
    }
    answer = interrupt(payload)
    text = _norm(answer)
    approved = text in APPROVE_WORDS
    override = text in OVERRIDE_WORDS

    if verdict == "conflicting" and not override:
        return {
            "pending_human_action": "conflicting：需要显式 override 才能继续",
            "approval": str(answer),
            "current_phase": "blocked_by_human",
            "messages": [AIMessage(content=f"human_review: blocked (conflicting, answer={answer})")],
        }

    updates: dict = {"pending_human_action": None, "approval": str(answer), "current_phase": "reviewed"}
    if approved or override:
        wp_id = state.get("active_work_package")
        store = getattr(runtime, "store", None)
        if wp_id and store is not None:
            is_override = verdict == "conflicting"
            decision = Decision(
                id=f"D-{wp_id}",
                decision=(f"人工强制覆盖 conflicting 并批准 {wp_id}" if is_override else f"批准工作包 {wp_id} 的产出"),
                status="confirmed",
                source="human_override" if is_override else "human_review",
                rationale=(
                    f"alignment={verdict}；违规={'；'.join(alignment.violates) if alignment else ''}"
                    if is_override
                    else "人在环批准；已写入长期 store 供跨线程复用"
                ),
            )
            remember_decision(store, state["project_id"], decision)
            updates["decisions"] = {decision.id: decision}
        updates["messages"] = [
            AIMessage(content=f"human_review: {'override' if override else 'approved'} {wp_id} (alignment={verdict})")
        ]
    else:
        updates["messages"] = [AIMessage(content=f"human_review: rejected (alignment={verdict})，返回 planner")]
    return updates
