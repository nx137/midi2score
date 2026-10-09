"""Goal Contract：从最高权威文件中派生只读目标快照。"""

from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Iterable

from .schemas import GoalContract

REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_BASELINE_PATH = REPO_ROOT / "governance_baseline.json"
SOURCE_FILES = {
    "charter": "TASK_CHARTER.md",
    "plan": "PedNotate_Plan_v3.0.md",
    "decisions": "DECISIONS.md",
    "fields": "FIELD_DEFINITIONS.md",
}
DEFAULT_PHASES = ["init", "control", "plan", "execute", "verify", "reviewed", "blocked", "blocked_by_policy", "blocked_by_human"]
DEFAULT_TOOLS = ["python"]
DEFAULT_SCRIPT_ROOTS = ["tools", "src", "tests"]
DEFAULT_WRITE_ROOTS = ["results", "evidence", "data/derived"]
_SECTION_RE = re.compile(r"^##\s+(\d+)\.\s+", re.MULTILINE)
_CONSTRAINT_RE = re.compile(r"^- \*\*(HC|GV)-(\d+)\*\*\s+(.+)$", re.MULTILINE)
_DECISION_ROW_RE = re.compile(r"^\|\s*(D-\d+)\s*\|")


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _section(text: str, number: int) -> str:
    matches = list(_SECTION_RE.finditer(text))
    for i, match in enumerate(matches):
        if int(match.group(1)) != number:
            continue
        start = match.end()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        return text[start:end].strip()
    return ""


def _lines(section: str, prefix: str = "- ") -> list[str]:
    out = []
    for line in section.splitlines():
        stripped = line.strip()
        if stripped.startswith(prefix):
            out.append(stripped[len(prefix):].strip())
    return out


def _table_rows(section: str) -> list[str]:
    return [line.strip() for line in section.splitlines() if line.strip().startswith("|") and "---" not in line]


def _active_decisions(decisions_text: str) -> list[str]:
    ids = []
    for line in decisions_text.splitlines():
        match = _DECISION_ROW_RE.match(line)
        if not match:
            continue
        cols = [c.strip() for c in line.strip().strip("|").split("|")]
        if len(cols) < 4:
            continue
        status = cols[3].lower()
        if "superseded" not in status and "rejected" not in status:
            ids.append(match.group(1))
    return ids


def _decision_summaries(decisions_text: str) -> list[dict[str, str]]:
    out: list[dict[str, str]] = []
    for line in decisions_text.splitlines():
        match = _DECISION_ROW_RE.match(line)
        if not match:
            continue
        cols = [c.strip() for c in line.strip().strip("|").split("|")]
        if len(cols) < 6:
            continue
        status = cols[3].lower()
        if "superseded" in status or "rejected" in status:
            continue
        out.append({"id": cols[0], "status": cols[3], "source": cols[2], "decision": cols[4]})
    return out


def _contract_hash(contract: GoalContract) -> str:
    payload = contract.model_dump(exclude={"contract_sha256"})
    return hashlib.sha256(json.dumps(payload, ensure_ascii=False, sort_keys=True).encode("utf-8")).hexdigest()


def build_goal_contract(root: Path | str = REPO_ROOT) -> GoalContract:
    root = Path(root)
    texts = {key: _read(root / rel) for key, rel in SOURCE_FILES.items()}
    source_hashes = {key: sha256_text(text) for key, text in texts.items()}
    charter = texts["charter"]
    goal = _section(charter, 1)
    in_scope = _lines(_section(charter, 3), "- ")
    out_of_scope = _table_rows(_section(charter, 4))
    constraints = [f"{m.group(1)}-{m.group(2)}: {m.group(3).strip()}" for m in _CONSTRAINT_RE.finditer(charter)]
    governance = [c for c in constraints if c.startswith("GV-")]
    hard = [c for c in constraints if c.startswith("HC-")]
    contract = GoalContract(
        contract_id="pednotate-goal-contract",
        version="1.0",
        goal_statement=goal,
        in_scope=in_scope,
        out_of_scope=out_of_scope,
        hard_constraints=hard,
        governance_rules=governance,
        primary_metric="回放保真度",
        secondary_metric="谱面一致度",
        training_order=["ASAP 初始训练", "PDMX 合成语料增强训练"],
        decision_ids=_active_decisions(texts["decisions"]),
        decision_summaries=_decision_summaries(texts["decisions"]),
        allowed_phases=DEFAULT_PHASES,
        allowed_tools=DEFAULT_TOOLS,
        allowed_script_roots=DEFAULT_SCRIPT_ROOTS,
        allowed_write_roots=DEFAULT_WRITE_ROOTS,
        source_hashes=source_hashes,
    )
    contract.contract_sha256 = _contract_hash(contract)
    return contract


def contract_drift(contract: GoalContract, baseline_path: Path | str = DEFAULT_BASELINE_PATH) -> list[str]:
    """比较当前合同与已确认基线；基线不存在时返回空列表并视为未建立。"""
    path = Path(baseline_path)
    if not path.exists():
        return []
    baseline = json.loads(path.read_text(encoding="utf-8"))
    drift: list[str] = []
    for key, digest in (baseline.get("source_hashes") or {}).items():
        current = contract.source_hashes.get(key)
        if current != digest:
            drift.append(f"CONTRACT_SOURCE_DRIFT:{key}")
    expected = baseline.get("contract_sha256")
    if expected and expected != contract.contract_sha256:
        drift.append("CONTRACT_HASH_DRIFT")
    return drift


def write_goal_baseline(contract: GoalContract, baseline_path: Path | str = DEFAULT_BASELINE_PATH, changed_by: str = "human") -> Path:
    path = Path(baseline_path)
    payload = {
        "contract_id": contract.contract_id,
        "contract_sha256": contract.contract_sha256,
        "source_hashes": contract.source_hashes,
        "changed_by": changed_by,
    }
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return path


__all__ = [
    "REPO_ROOT",
    "DEFAULT_BASELINE_PATH",
    "build_goal_contract",
    "contract_drift",
    "write_goal_baseline",
    "sha256_text",
]
