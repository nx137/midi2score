"""planner / executor / verifier / human_review 四个控制平面节点。"""

from __future__ import annotations

from typing import Callable

from langchain_core.messages import AIMessage, HumanMessage
from langgraph.runtime import Runtime
from langgraph.types import interrupt

from . import control
from .contract import build_goal_contract
from .memory import CHARTER_PATH, is_charter_write_attempt, recall_decisions, remember_decision, sha256_file, trim_messages
from .schemas import Decision, Evidence, TaskState

APPROVE_WORDS = {"approve", "approved", "yes", "y", "ok", "批准", "同意"}
OVERRIDE_WORDS = {"override", "force", "强制继续", "确认覆盖", "人工覆盖"}


def _stub_llm(prompt: str) -> str:
    return "[stub] 未调用真实模型；控制平面路径已走通。"


def _norm(value: object) -> str:
    return str(value).strip().lower()


def planner(state: TaskState, runtime: Runtime | None = None, llm: Callable[[str], str] = _stub_llm) -> dict:
    contract = state.get("goal_contract") or build_goal_contract()
    store = getattr(runtime, "store", None)
    decisions = recall_decisions(store, state["project_id"], limit=8) if store is not None else []
    updates: dict = {"current_phase": "plan", "iteration": state.get("iteration", 0) + 1}
    pending = [wp for wp in state["work_packages"].values() if wp.status == "pending"]
    new_messages = []
    if pending:
        wp = sorted(pending, key=lambda w: w.id)[0]
        updates["active_work_package"] = wp.id
        updates["work_packages"] = {wp.id: wp.model_copy(update={"status": "in_progress"})}
        new_messages.append(HumanMessage(content=f"plan: {wp.id} -> {wp.goal}"))
    else:
        updates["active_work_package"] = None
        updates["current_phase"] = "done"
    temp_state = dict(state)
    temp_state.update(updates)
    packet = control.build_context_packet(temp_state, contract, decisions)
    updates["context_packet"] = packet
    if pending:
        new_messages.append(AIMessage(content=llm(control.render_context(packet) + f"\nPLAN {updates['active_work_package']}")))
    updates["recalled_decisions"] = [d["id"] for d in decisions]
    combined = list(state.get("messages", [])) + new_messages
    removals = trim_messages(combined)
    if removals:
        updates["messages"] = list(removals) + new_messages
    elif new_messages:
        updates["messages"] = new_messages
    return updates


def executor(state: TaskState, runtime: Runtime | None = None, llm: Callable[[str], str] = _stub_llm) -> dict:
    wp_id = state.get("active_work_package")
    if not wp_id:
        return {"current_phase": "done"}
    wp = state["work_packages"][wp_id]
    contract = state.get("goal_contract") or build_goal_contract()
    intent_text = " ".join([wp.goal, *wp.outputs])
    if is_charter_write_attempt(intent_text):
        return {
            "charter_write_attempt": True,
            "current_phase": "blocked_by_policy",
            "work_packages": {wp.id: wp.model_copy(update={"status": "blocked"})},
            "last_result": {"work_package": wp.id, "refused": True, "policy_denied": True, "reason": "charter write intent"},
            "messages": [AIMessage(content=f"executor: refused {wp.id} because it attempts to modify the charter")],
        }
    decision = control.authorize_work_package(wp, contract, state)
    if decision.effect == "deny":
        return {
            "current_phase": "blocked_by_policy",
            "policy_attempts": {decision.id: decision},
            "work_packages": {wp.id: wp.model_copy(update={"status": "blocked"})},
            "last_result": {"work_package": wp.id, "refused": True, "policy_denied": True, "reason": decision.reason, "reason_codes": decision.reason_codes},
            "messages": [AIMessage(content=f"executor: policy denied {wp.id}: {decision.reason}")],
        }
    packet = state.get("context_packet") or control.build_context_packet(state, contract, [])
    note = llm(control.render_context(packet) + f"\nEXECUTE {wp.id}")
    records = {}
    evidence_updates = {}
    for idx, command in enumerate(wp.commands):
        record_id = f"RUN-{wp.id}-{idx + 1}"
        record, evidence = control.run_command(command, contract, state, record_id)
        records[record_id] = record
        evidence_updates[evidence.id] = evidence
    if not wp.commands:
        evidence = Evidence(id=f"EV-{wp.id}", kind="document", locator=f"work_package:{wp.id}", status="not_run")
        evidence_updates[evidence.id] = evidence
    return {
        "work_packages": {wp.id: wp.model_copy(update={"status": "in_progress"})},
        "execution_records": records,
        "evidence": evidence_updates,
        "last_result": {"work_package": wp.id, "note": note, "commands": [c.argv for c in wp.commands]},
        "current_phase": "execute",
    }


def verifier(state: TaskState, runtime: Runtime | None = None, llm: Callable[[str], str] = _stub_llm) -> dict:
    contract = state.get("goal_contract") or build_goal_contract()
    current_sha = sha256_file(CHARTER_PATH)
    verification_state = dict(state)
    evidence_updates = {}
    for evidence_id, evidence in state.get("evidence", {}).items():
        promoted = control.promote_evidence(evidence)
        if promoted != evidence:
            evidence_updates[evidence_id] = promoted
    if evidence_updates:
        verification_state["evidence"] = {**state.get("evidence", {}), **evidence_updates}
    alignment, verification = control.verify_state_alignment(verification_state, contract, current_sha, llm)
    return {"evidence": evidence_updates, "verification": verification, "alignment": alignment, "current_phase": "verify"}


def human_review(state: TaskState, runtime: Runtime | None = None) -> dict:
    alignment = state.get("alignment")
    verdict = alignment.verdict if alignment else "aligned"
    last = state.get("last_result") or {}
    policy_denied = bool(last.get("policy_denied"))
    payload = {
        "question": "是否批准当前工作包的产出？",
        "work_package": state.get("active_work_package"),
        "alignment": verdict,
        "violations": list(alignment.violates) if alignment else [],
        "issues": list(state["verification"].issues) if state.get("verification") else [],
        "needs_user_confirmation": bool(alignment.needs_user_confirmation) if alignment else False,
        "policy_denied": policy_denied,
        "hint": "policy deny 不可通过 override 放行" if policy_denied else (
            "conflicting 必须显式 override（强制继续）才放行；普通 approve 不足以通过。" if verdict == "conflicting" else ""
        ),
    }
    answer = interrupt(payload)
    text = _norm(answer)
    approved = text in APPROVE_WORDS
    override = text in OVERRIDE_WORDS
    wp_id = state.get("active_work_package")
    wp = state["work_packages"].get(wp_id) if wp_id else None

    if policy_denied or (verdict != "aligned" and not override):
        if policy_denied:
            updates = {"pending_human_action": "policy deny：不可 override", "approval": str(answer), "current_phase": "blocked_by_human"}
        else:
            updates = {"pending_human_action": f"{verdict}：需要显式 override 才能继续", "approval": str(answer), "current_phase": "blocked_by_human"}
        if wp is not None:
            updates["work_packages"] = {wp.id: wp.model_copy(update={"status": "blocked"})}
        updates["messages"] = [AIMessage(content=f"human_review: blocked (alignment={verdict}, policy_denied={policy_denied})")]
        return updates

    updates: dict = {"pending_human_action": None, "approval": str(answer), "current_phase": "reviewed"}
    if approved or override:
        if wp is not None:
            updates["work_packages"] = {wp.id: wp.model_copy(update={"status": "done"})}
        store = getattr(runtime, "store", None)
        if wp_id and store is not None:
            is_override = verdict != "aligned"
            decision = Decision(
                id=f"D-{wp_id}",
                decision=(f"人工强制覆盖 conflicting 并批准 {wp_id}" if is_override else f"批准工作包 {wp_id} 的产出"),
                status="confirmed",
                source="human_override" if is_override else "human_review",
                rationale=(f"alignment={verdict}；违规={'；'.join(alignment.violates) if alignment else ''}" if is_override else "人在环批准；已写入长期 store 供跨线程复用"),
            )
            remember_decision(store, state["project_id"], decision)
            updates["decisions"] = {decision.id: decision}
        updates["messages"] = [AIMessage(content=f"human_review: {'override' if override else 'approved'} {wp_id} (alignment={verdict})")]
    else:
        if wp is not None:
            updates["work_packages"] = {wp.id: wp.model_copy(update={"status": "pending"})}
        updates["messages"] = [AIMessage(content=f"human_review: rejected (alignment={verdict})，返回 planner")]
    return updates
