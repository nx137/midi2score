#!/usr/bin/env python
"""通过 LangGraph 控制平面执行 M3S-1 BiLSTM-CRF + validator + repro。"""
from __future__ import annotations
import argparse, json, os
from pathlib import Path
from typing import Any
from langgraph.types import Command
from research_agent.graph import compile_graph, sqlite_persistence, stable_thread_id, thread_config
from research_agent.memory import initial_state
from research_agent.schemas import CommandSpec, WorkPackage


def dump(value: Any) -> Any:
    if value is None:
        return None
    if hasattr(value, "model_dump"):
        return value.model_dump(mode="json")
    if isinstance(value, dict):
        return {k: dump(v) for k, v in value.items()}
    if isinstance(value, list):
        return [dump(v) for v in value]
    return value


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--run-id", required=True)
    ap.add_argument("--research-python", type=Path, default=Path(".venv-research/Scripts/python.exe"))
    ap.add_argument("--dataset", type=Path, default=Path("data/asap-dataset"))
    ap.add_argument("--m3-data", type=Path, default=Path("data/derived/m3/linear"))
    ap.add_argument("--m3-linear-summary", type=Path, default=Path("results/E1/m3/linear/linear_summary.json"))
    args = ap.parse_args()
    os.environ.setdefault("MIDI2SCORE_LLM_ENABLED", "false")
    repo = Path(__file__).resolve().parents[1]
    py = (repo / args.research_python).resolve() if not args.research_python.is_absolute() else args.research_python.resolve()
    db_dir = repo / "data"
    checkpoint_db = db_dir / f"m3_bilstm_control_plane_{args.run_id}.db"
    store_db = db_dir / f"m3_bilstm_control_plane_{args.run_id}_store.db"
    if checkpoint_db.exists() or store_db.exists():
        raise SystemExit(f"refuse to reuse M3 BiLSTM control-plane state: {checkpoint_db} / {store_db}")
    db_dir.mkdir(parents=True, exist_ok=True)

    builder_outputs = [
        "data/derived/m3/bilstm_crf/best_model.pt",
        "data/derived/m3/bilstm_crf/predictions.jsonl.gz",
        "results/E1/m3/bilstm_crf/bilstm_crf_model.json",
        "results/E1/m3/bilstm_crf/bilstm_crf_summary.json",
        "results/E1/m3/bilstm_crf/bilstm_crf_data_summary.json",
        "results/E1/m3/bilstm_crf/bilstm_crf_table.csv",
        "results/E1/m3/bilstm_crf/bilstm_crf_per_class.csv",
        "results/E1/m3/bilstm_crf/bilstm_crf_confusion.csv",
        "results/E1/m3/bilstm_crf/bilstm_crf_training_curve.csv",
        "results/E1/m3/bilstm_crf/bilstm_crf_manifest.json",
    ]
    commands = [
        CommandSpec(
            argv=[str(py), "tools/m3_bilstm_crf.py",
                  "--dataset", str(args.dataset), "--data-dir", str(args.m3_data),
                  "--out-data", "data/derived/m3/bilstm_crf", "--out-dir", "results/E1/m3/bilstm_crf",
                  "--hidden", "32", "--dropout", "0.2", "--chunk", "256", "--batch-size", "32",
                  "--lr", "0.0001", "--epochs", "100", "--patience", "10", "--seed", "20260101",
                  "--class-weight-mode", "balanced_clipped"],
            cwd=".", timeout_seconds=1800, expected_outputs=builder_outputs, writes=builder_outputs,
            description="train small BiLSTM-CRF under M3S-1 protocol",
        ),
        CommandSpec(
            argv=[str(py), "tools/m3_validate_bilstm_crf.py",
                  "--results-dir", "results/E1/m3/bilstm_crf", "--data-dir", "data/derived/m3/bilstm_crf",
                  "--linear-summary", str(args.m3_linear_summary),
                  "--out", "evidence/R1/M3/bilstm_crf_validation.json"],
            cwd=".", timeout_seconds=1800,
            expected_outputs=["evidence/R1/M3/bilstm_crf_validation.json", "evidence/R1/M3/bilstm_crf_validation.md"],
            writes=["evidence/R1/M3/bilstm_crf_validation.json", "evidence/R1/M3/bilstm_crf_validation.md"],
            description="independent M3S-1 validator including relative gate",
        ),
        CommandSpec(
            argv=[str(py), "tools/m3_bilstm_repro_check.py",
                  "--results-dir", "results/E1/m3/bilstm_crf", "--data-dir", "data/derived/m3/bilstm_crf",
                  "--check", "evidence/R1/M3/bilstm_crf_pre_control_plane_snapshot.json",
                  "--out", "evidence/R1/M3/bilstm_crf_repro_check.json"],
            cwd=".", timeout_seconds=1800,
            expected_outputs=["evidence/R1/M3/bilstm_crf_repro_check.json", "evidence/R1/M3/bilstm_crf_repro_check.md"],
            writes=["evidence/R1/M3/bilstm_crf_repro_check.json", "evidence/R1/M3/bilstm_crf_repro_check.md"],
            description="compare controlled BiLSTM-CRF rerun against pre-control snapshot",
        ),
    ]
    wp = WorkPackage(
        id="WP-M3-BILSTM-CRF",
        goal="训练并验证小型 BiLSTM-CRF 踏板锚点序列模型，检查其是否相对 M3.1 线性模型改善 DOWN/UP precision 与 macro F1",
        phase="execute",
        goal_refs=["GOAL-1"],
        constraint_refs=["HC-01", "HC-08", "HC-11", "HC-13", "HC-18"],
        decision_refs=["D-0059", "D-0081", "D-0082", "D-0089"],
        allowed_tools=["python"], commands=commands,
        expected_outputs=builder_outputs + ["evidence/R1/M3/bilstm_crf_validation.json", "evidence/R1/M3/bilstm_crf_validation.md", "evidence/R1/M3/bilstm_crf_repro_check.json", "evidence/R1/M3/bilstm_crf_repro_check.md"],
        outputs=["results/E1/m3/bilstm_crf/bilstm_crf_summary.json", "evidence/R1/M3/bilstm_crf_validation.json", "evidence/R1/M3/bilstm_crf_repro_check.json"],
    )
    state = initial_state("midi2score", max_iterations=1)
    state["work_packages"] = {"WP-M3-BILSTM-CRF": wp}
    cfg = thread_config("midi2score", f"M3-BILSTM-CRF-{args.run_id}")
    with sqlite_persistence(checkpoint_db, store_db) as (cp, store):
        graph = compile_graph(cp, store)
        graph.invoke(state, cfg)
        snap = graph.get_state(cfg); values = snap.values
        verification, alignment = values.get("verification"), values.get("alignment")
        approved = False
        if verification is not None and verification.passed and alignment is not None and alignment.verdict == "aligned":
            graph.invoke(Command(resume="approve"), cfg)
            snap = graph.get_state(cfg); values = snap.values; approved = True
    record = {
        "run_id": args.run_id,
        "thread_id": stable_thread_id("midi2score", f"M3-BILSTM-CRF-{args.run_id}"),
        "checkpoint_db": str(checkpoint_db), "store_db": str(store_db),
        "approved": approved, "current_phase": values.get("current_phase"),
        "alignment": dump(values.get("alignment")), "verification": dump(values.get("verification")),
        "work_package": dump(values.get("work_packages", {}).get("WP-M3-BILSTM-CRF")),
        "execution_records": dump(values.get("execution_records", {})),
        "evidence": dump(values.get("evidence", {})),
        "approval": values.get("approval"), "pending_human_action": values.get("pending_human_action"),
    }
    out = repo / "evidence" / "R1" / "M3" / "bilstm_crf_control_plane_record.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(record, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    status = "ok" if approved and verification is not None and verification.passed else "blocked"
    print(json.dumps({"status": status, "record": str(out), "phase": record["current_phase"]}, ensure_ascii=False))
    return 0 if status == "ok" else 2


if __name__ == "__main__":
    raise SystemExit(main())
