"""结构化状态与记录模型。

原则：任务对象进结构化字段，`messages` 只承载有界对话窗口。
LangGraph 状态用 TypedDict（原生 channel/reducer），记录用 Pydantic 校验。
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Annotated, Any, Literal, TypedDict

from langchain_core.messages import AnyMessage
from langgraph.graph.message import add_messages
from pydantic import BaseModel, Field


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


class Record(BaseModel):
    """账本条目公共字段：稳定 id + 创建时间。"""

    id: str
    created_at: str = Field(default_factory=_now)


class ResearchQuestion(Record):
    question: str
    status: Literal["open", "answered", "deferred"] = "open"
    linked_packages: list[str] = Field(default_factory=list)


class CommandSpec(BaseModel):
    """受控命令声明；模型不得直接提供 shell 字符串。"""

    argv: list[str]
    cwd: str = "."
    timeout_seconds: int = 300
    expected_outputs: list[str] = Field(default_factory=list)
    description: str = ""
    network: bool = False
    writes: list[str] = Field(default_factory=list)


class WorkPackage(Record):
    goal: str
    status: Literal["pending", "in_progress", "done", "blocked"] = "pending"
    outputs: list[str] = Field(default_factory=list)
    verification: str | None = None
    phase: str = "unassigned"
    goal_refs: list[str] = Field(default_factory=list)
    constraint_refs: list[str] = Field(default_factory=list)
    decision_refs: list[str] = Field(default_factory=list)
    acceptance_refs: list[str] = Field(default_factory=list)
    allowed_tools: list[str] = Field(default_factory=list)
    commands: list[CommandSpec] = Field(default_factory=list)
    expected_outputs: list[str] = Field(default_factory=list)


class Decision(Record):
    decision: str
    status: Literal["proposed", "confirmed", "superseded", "adopted"] = "proposed"
    source: str = "unspecified"
    rationale: str = ""
    rejected_alternatives: list[str] = Field(default_factory=list)


class Assumption(Record):
    statement: str
    confidence: Literal["low", "medium", "high"] = "medium"
    expires_when: str = ""
    status: Literal["open", "supported", "refuted", "promoted"] = "open"


class Evidence(Record):
    kind: Literal["literature", "experiment", "dataset", "document"]
    locator: str
    status: Literal["not_run", "not_verified", "claimed", "verified", "failed"] = "not_run"
    command: str | None = None
    argv: list[str] | None = None
    cwd: str | None = None
    exit_code: int | None = None
    started_at: str | None = None
    ended_at: str | None = None
    stdout_sha256: str | None = None
    stderr_sha256: str | None = None
    environment_sha256: str | None = None
    artifact_hashes: dict[str, str] = Field(default_factory=dict)
    source_hashes: dict[str, str] = Field(default_factory=dict)
    verifier: str | None = None


class TodoItem(Record):
    text: str
    status: Literal["todo", "doing", "blocked", "done"] = "todo"
    blocking: list[str] = Field(default_factory=list)


class AcceptanceCriterion(Record):
    statement: str
    method: str
    result: Literal["pass", "fail", "not_run"] = "not_run"
    evidence_id: str | None = None


class VerificationResult(Record):
    passed: bool
    issues: list[str] = Field(default_factory=list)
    reason_codes: list[str] = Field(default_factory=list)
    charter_sha256: str = ""
    contract_sha256: str = ""


AlignmentVerdict = Literal["aligned", "partially_aligned", "conflicting"]


class AlignmentResult(Record):
    """目标偏离判定：aligned / partially_aligned / conflicting。"""

    verdict: AlignmentVerdict = "aligned"
    violates: list[str] = Field(default_factory=list)
    issues: list[str] = Field(default_factory=list)
    needs_user_confirmation: bool = False
    rationale: str = ""
    contract_sha256: str = ""


class PolicyDecision(Record):
    effect: Literal["allow", "require_confirmation", "deny"]
    overridable: bool
    reason_codes: list[str] = Field(default_factory=list)
    violates: list[str] = Field(default_factory=list)
    reason: str = ""


class ExecutionRecord(Record):
    command: str
    argv: list[str]
    cwd: str
    timeout_seconds: int
    started_at: str
    ended_at: str
    exit_code: int | None
    stdout: str = ""
    stderr: str = ""
    stdout_sha256: str = ""
    stderr_sha256: str = ""
    environment_sha256: str = ""
    artifact_hashes: dict[str, str] = Field(default_factory=dict)
    source_hashes: dict[str, str] = Field(default_factory=dict)
    timed_out: bool = False


class GoalContract(BaseModel):
    contract_id: str
    version: str
    goal_statement: str
    in_scope: list[str] = Field(default_factory=list)
    out_of_scope: list[str] = Field(default_factory=list)
    hard_constraints: list[str] = Field(default_factory=list)
    governance_rules: list[str] = Field(default_factory=list)
    primary_metric: str = ""
    secondary_metric: str = ""
    training_order: list[str] = Field(default_factory=list)
    decision_ids: list[str] = Field(default_factory=list)
    decision_summaries: list[dict[str, str]] = Field(default_factory=list)
    allowed_phases: list[str] = Field(default_factory=list)
    allowed_tools: list[str] = Field(default_factory=list)
    allowed_script_roots: list[str] = Field(default_factory=list)
    allowed_write_roots: list[str] = Field(default_factory=list)
    source_hashes: dict[str, str] = Field(default_factory=dict)
    contract_sha256: str = ""


class ContextPacket(BaseModel):
    contract_sha256: str
    current_phase: str
    active_work_package: dict[str, Any] | None = None
    hard_constraints: list[str] = Field(default_factory=list)
    confirmed_decisions: list[dict[str, Any]] = Field(default_factory=list)
    recent_messages: list[str] = Field(default_factory=list)
    state_summary: dict[str, Any] = Field(default_factory=dict)
    context_sha256: str = ""


def merge_by_id(left: dict[str, Any] | None, right: dict[str, Any] | None) -> dict[str, Any]:
    """按 id 覆盖式合并，保证节点重放 / 重试不会产生重复条目。"""
    merged = dict(left or {})
    merged.update(right or {})
    return merged


class TaskState(TypedDict):
    project_id: str
    charter_text: str
    charter_sha256: str
    hard_constraints: list[str]

    goal_contract: GoalContract | None
    contract_drift: list[str]
    context_packet: ContextPacket | None

    messages: Annotated[list[AnyMessage], add_messages]

    research_questions: Annotated[dict[str, ResearchQuestion], merge_by_id]
    work_packages: Annotated[dict[str, WorkPackage], merge_by_id]
    decisions: Annotated[dict[str, Decision], merge_by_id]
    assumptions: Annotated[dict[str, Assumption], merge_by_id]
    evidence: Annotated[dict[str, Evidence], merge_by_id]
    todos: Annotated[dict[str, TodoItem], merge_by_id]
    acceptance: Annotated[dict[str, AcceptanceCriterion], merge_by_id]
    policy_attempts: Annotated[dict[str, PolicyDecision], merge_by_id]
    execution_records: Annotated[dict[str, ExecutionRecord], merge_by_id]

    current_phase: str
    active_work_package: str | None
    iteration: int
    max_iterations: int
    last_result: dict[str, Any] | None
    verification: VerificationResult | None

    alignment: AlignmentResult | None
    charter_write_attempt: bool
    recalled_decisions: list[str]
    pending_human_action: str | None
    approval: str | None
