#!/usr/bin/env python
"""通过 LangGraph 控制平面执行 M2 构建、独立验证和可复现性检查。"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
from typing import Any

from langgraph.types import Command

from research_agent.control import REPO_ROOT
from research_agent.graph import compile_graph, sqlite_persistence, stable_thread_id, thread_config
from research_agent.memory import initial_state
from research_agent.schemas import CommandSpec, Evidence, ExecutionRecord, WorkPackage


def dump(value: Any) -> Any:
    if value is None:
        return None
    if hasattr(value, "model_dump"):
        return value.model_dump(mode="json")
    if isinstance(value, dict):
        return {key: dump(item) for key, item in value.items()}
    if isinstance(value, list):
        return [dump(item) for item in value]
    return value


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--run-id", required=True)
    ap.add_argument("--research-python", type=Path, default=Path(".venv-research/Scripts/python.exe"))
    ap.add_argument("--dataset", type=Path, default=Path("data/asap-dataset"))
    ap.add_argument("--split", type=Path, default=Path("evidence/R1/G1-split/split_v1.json"))
    args = ap.parse_args()

    os.environ.setdefault("MIDI2SCORE_LLM_ENABLED", "false")
    research_python = (REPO_ROOT / args.research_python).resolve() if not args.research_python.is_absolute() else args.research_python.resolve()
    db_dir = REPO_ROOT / "data"
    checkpoint_db = db_dir / f"m2_control_plane_{args.run_id}.db"
    store_db = db_dir / f"m2_control_plane_{args.run_id}_store.db"
    if checkpoint_db.exists() or store_db.exists():
        raise SystemExit(f"refuse to reuse existing M2 control-plane state: {checkpoint_db} / {store_db}")
    db_dir.mkdir(parents=True, exist_ok=True)

    builder_outputs = [
        "data/derived/m2/score_labels.jsonl.gz",
        "data/derived/m2/run_masks.jsonl.gz",
        "data/derived/m2/m2_excluded_anchors.jsonl.gz",
        "results/E1/m2/m2_summary.json",
        "results/E1/m2/m2_summary.md",
        "results/E1/m2/m2_scores.csv",
        "results/E1/m2/m2_folds.csv",
        "results/E1/m2/m2_table1.csv",
        "results/E1/m2/m2_table1.md",
        "results/E1/m2/m2_label_schema.json",
        "results/E1/m2/m2_manifest.json",
    ]
    commands = [
        CommandSpec(
            argv=[
                str(research_python), "tools/m2_build_label_dataset.py",
                "--dataset", str(args.dataset), "--split", str(args.split),
                "--out-dir", "results/E1/m2", "--data-out", "data/derived/m2",
            ],
            cwd=".",
            timeout_seconds=1200,
            expected_outputs=builder_outputs,
            writes=builder_outputs,
            description="build M2 canonical label dataset",
        ),
        CommandSpec(
            argv=[
                str(research_python), "tools/m2_validate_labels.py",
                "--dataset", str(args.dataset), "--split", str(args.split),
                "--data-dir", "data/derived/m2", "--results-dir", "results/E1/m2",
                "--out", "evidence/R1/M2/m2_validation.json",
            ],
            cwd=".",
            timeout_seconds=1200,
            expected_outputs=[
                "evidence/R1/M2/m2_validation.json",
                "evidence/R1/M2/m2_validation.md",
            ],
            writes=[
                "evidence/R1/M2/m2_validation.json",
                "evidence/R1/M2/m2_validation.md",
            ],
            description="independently validate M2 label dataset",
        ),
        CommandSpec(
            argv=[
                str(research_python), "tools/m2_repro_check.py",
                "--dataset", str(args.dataset), "--split", str(args.split),
                "--baseline-data", "data/derived/m2", "--baseline-results", "results/E1/m2",
                "--out", "evidence/R1/M2/m2_repro_check.json",
            ],
            cwd=".",
            timeout_seconds=1200,
            expected_outputs=["evidence/R1/M2/m2_repro_check.json"],
            writes=["evidence/R1/M2/m2_repro_check.json"],
            description="reproduce M2 artifacts and compare content hashes",
        ),
    ]
    work_package = WorkPackage(
        id="WP-M2",
        goal="构建并验证 ASAP Main 的踏板标签数据集，使用 canonical 锚点与 unlabeled mask，保留回放保真度主指标边界",
        phase="execute",
        goal_refs=["GOAL-1"],
        constraint_refs=["HC-01", "HC-08", "HC-11", "HC-13"],
        decision_refs=["D-0059", "D-0081", "D-0082"],
        allowed_tools=["python"],
        commands=commands,
        expected_outputs=builder_outputs + [
            "evidence/R1/M2/m2_validation.json",
            "evidence/R1/M2/m2_validation.md",
            "evidence/R1/M2/m2_repro_check.json",
        ],
        outputs=[
            "data/derived/m2/score_labels.jsonl.gz",
            "data/derived/m2/run_masks.jsonl.gz",
            "results/E1/m2/m2_table1.md",
            "evidence/R1/M2/m2_validation.json",
            "evidence/R1/M2/m2_repro_check.json",
        ],
    )
    state = initial_state("midi2score", max_iterations=1)
    state["work_packages"] = {"WP-M2": work_package}
    cfg = thread_config("midi2score", f"M2-{args.run_id}")

    with sqlite_persistence(checkpoint_db, store_db) as (checkpointer, store):
        graph = compile_graph(checkpointer, store)
        graph.invoke(state, cfg)
        snapshot = graph.get_state(cfg)
        values = snapshot.values
        verification = values.get("verification")
        alignment = values.get("alignment")
        approved = False
        if verification is not None and verification.passed and alignment is not None and alignment.verdict == "aligned":
            graph.invoke(Command(resume="approve"), cfg)
            snapshot = graph.get_state(cfg)
            values = snapshot.values
            approved = True

    record = {
        "run_id": args.run_id,
        "thread_id": stable_thread_id("midi2score", f"M2-{args.run_id}"),
        "checkpoint_db": str(checkpoint_db),
        "store_db": str(store_db),
        "approved": approved,
        "current_phase": values.get("current_phase"),
        "alignment": dump(values.get("alignment")),
        "verification": dump(values.get("verification")),
        "work_package": dump(values.get("work_packages", {}).get("WP-M2")),
        "execution_records": dump(values.get("execution_records", {})),
        "evidence": dump(values.get("evidence", {})),
        "pending_human_action": values.get("pending_human_action"),
        "approval": values.get("approval"),
    }
    out = REPO_ROOT / "evidence" / "R1" / "M2" / "m2_control_plane_record.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(record, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    status = "ok" if approved and verification is not None and verification.passed else "blocked"
    print(json.dumps({"status": status, "record": str(out), "phase": record["current_phase"]}, ensure_ascii=False))
    return 0 if status == "ok" else 2


if __name__ == "__main__":
    raise SystemExit(main())
