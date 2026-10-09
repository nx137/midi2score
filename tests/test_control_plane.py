from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest
from langgraph.types import Command

import research_agent.control as control
from research_agent.contract import build_goal_contract, contract_drift
from research_agent.graph import compile_graph, sqlite_persistence, thread_config
from research_agent.memory import initial_state, remember_decision
from research_agent.schemas import AcceptanceCriterion, CommandSpec, Decision, Evidence, ResearchQuestion, WorkPackage

PROJECT = "midi2score"


@pytest.fixture()
def graph(tmp_path):
    with sqlite_persistence(tmp_path / "cp.db", tmp_path / "store.db") as (cp, store):
        yield compile_graph(cp, store)


def _cfg(name: str) -> dict:
    return thread_config(PROJECT, name)


def test_off_topic_work_package_is_blocked_before_execution(graph):
    st = initial_state(PROJECT)
    st["work_packages"] = {"WP-X": WorkPackage(id="WP-X", goal="抓取股票行情并写一篇金融预测报告，与本项目无关", phase="control", goal_refs=["GOAL-1"])}
    cfg = _cfg("CP-OFFTOPIC")
    graph.invoke(st, cfg)
    snap = graph.get_state(cfg)
    assert snap.values["alignment"].verdict == "conflicting"
    assert snap.values["verification"].passed is False
    assert snap.values["work_packages"]["WP-X"].status == "blocked"
    assert snap.values["execution_records"] == {}
    graph.invoke(Command(resume="override"), cfg)
    assert graph.get_state(cfg).values["current_phase"] == "blocked_by_human"
    assert graph.get_state(cfg).values["decisions"] == {}


def test_partially_aligned_requires_explicit_override(graph):
    st = initial_state(PROJECT)
    st["research_questions"] = {"RQ-1": ResearchQuestion(id="RQ-1", question="Q", linked_packages=[])}
    cfg = _cfg("CP-PARTIAL")
    graph.invoke(st, cfg)
    assert graph.get_state(cfg).values["alignment"].verdict == "partially_aligned"
    graph.invoke(Command(resume="approve"), cfg)
    assert graph.get_state(cfg).values["current_phase"] == "blocked_by_human"


def test_command_runner_records_candidate_evidence(monkeypatch, tmp_path):
    monkeypatch.setattr(control, "REPO_ROOT", tmp_path)
    (tmp_path / "tools").mkdir()
    (tmp_path / "results").mkdir()
    script = tmp_path / "tools" / "ok.py"
    script.write_text("from pathlib import Path\nPath('results/out.txt').write_text('ok', encoding='utf-8')\n", encoding="utf-8")
    cmd = CommandSpec(argv=[sys.executable, "tools/ok.py"], cwd=".", expected_outputs=["results/out.txt"])
    record, evidence = control.run_command(cmd, build_goal_contract(), {}, "RUN-TEST")
    assert record.exit_code == 0
    assert evidence.status == "not_verified"
    assert evidence.artifact_hashes
    assert (tmp_path / "results" / "out.txt").read_text(encoding="utf-8") == "ok"


def test_verifier_promotes_complete_candidate_evidence():
    evidence = Evidence(
        id="EV-OK", kind="experiment", locator="cmd", status="not_verified",
        command="python tools/ok.py", argv=["python", "tools/ok.py"], cwd=".",
        exit_code=0, stdout_sha256="a", stderr_sha256="b",
    )
    promoted = control.promote_evidence(evidence)
    assert promoted.status == "verified"
    assert promoted.verifier == "postflight"


def test_graph_executes_allowlisted_command_and_promotes_evidence(monkeypatch, tmp_path):
    monkeypatch.setattr(control, "REPO_ROOT", tmp_path)
    (tmp_path / "tools").mkdir()
    (tmp_path / "results").mkdir()
    (tmp_path / "tools" / "ok.py").write_text("from pathlib import Path\nPath('results/out.txt').write_text('ok', encoding='utf-8')\n", encoding="utf-8")
    st = initial_state(PROJECT)
    st["work_packages"] = {
        "WP-C": WorkPackage(
            id="WP-C",
            goal="控制平面执行允许命令并验证证据",
            phase="control",
            goal_refs=["GOAL-1"],
            allowed_tools=["python"],
            commands=[CommandSpec(argv=[sys.executable, "tools/ok.py"], cwd=".", expected_outputs=["results/out.txt"])],
            expected_outputs=["results/out.txt"],
        )
    }
    with sqlite_persistence(tmp_path / "cp.db", tmp_path / "store.db") as (cp, store):
        graph = compile_graph(cp, store)
        cfg = _cfg("CP-RUN-GRAPH")
        graph.invoke(st, cfg)
        values = graph.get_state(cfg).values
        assert values["evidence"]["EV-RUN-WP-C-1"].status == "verified"
        assert values["execution_records"]["RUN-WP-C-1"].exit_code == 0
        assert values["verification"].passed is True


def test_command_policy_rejects_inline_python_and_outside_paths():
    contract = build_goal_contract()
    inline = CommandSpec(argv=[sys.executable, "-c", "print(1)"], cwd=".")
    assert "TOOL_PYTHON_INLINE_FORBIDDEN" in control.validate_command(inline, contract, {})
    outside = CommandSpec(argv=[sys.executable, "tools/ok.py"], cwd=".", expected_outputs=["../outside.txt"])
    assert any(i.startswith("TOOL_WRITE_OUTSIDE_ALLOWED_ROOTS") for i in control.validate_command(outside, contract, {}))


def test_context_packet_contains_goal_and_full_decisions(tmp_path):
    with sqlite_persistence(tmp_path / "cp.db", tmp_path / "store.db") as (cp, store):
        remember_decision(store, PROJECT, Decision(id="D-TEST", decision="保留 D-0059", status="confirmed"))
        graph = compile_graph(cp, store)
        cfg = _cfg("CP-CONTEXT")
        graph.invoke(initial_state(PROJECT), cfg)
        packet = graph.get_state(cfg).values["context_packet"]
        assert packet.contract_sha256
        assert packet.confirmed_decisions
        assert any(d.get("id") == "D-TEST" and d.get("decision") == "保留 D-0059" for d in packet.confirmed_decisions)
        assert packet.active_work_package["goal_refs"] == ["GOAL-1"]


def test_long_rejection_history_keeps_contract_and_bounded_messages(graph):
    cfg = _cfg("CP-LONG")
    graph.invoke(initial_state(PROJECT, max_iterations=50), cfg)
    for _ in range(20):
        graph.invoke(Command(resume="reject"), cfg)
    snap = graph.get_state(cfg)
    values = snap.values
    assert len(values["messages"]) <= 20
    assert values["context_packet"].contract_sha256 == values["goal_contract"].contract_sha256
    assert list(snap.next) == ["human_review"]


def test_thread_config_rejects_override():
    with pytest.raises(ValueError):
        thread_config(PROJECT, "T", thread_id="other")


def test_contract_baseline_drift_is_reported(tmp_path):
    contract = build_goal_contract()
    baseline = tmp_path / "baseline.json"
    baseline.write_text(json.dumps({"contract_sha256": "bad", "source_hashes": {"charter": "bad"}}), encoding="utf-8")
    drift = contract_drift(contract, baseline)
    assert "CONTRACT_HASH_DRIFT" in drift
    assert "CONTRACT_SOURCE_DRIFT:charter" in drift


def test_initial_state_exposes_preexisting_baseline_drift(tmp_path):
    baseline = tmp_path / "baseline.json"
    baseline.write_text('{"contract_sha256":"bad","source_hashes":{"charter":"bad"}}', encoding="utf-8")
    st = initial_state(PROJECT, baseline_path=baseline)
    assert st["contract_drift"]
    assert "CONTRACT_HASH_DRIFT" in st["contract_drift"]


def test_verified_evidence_must_have_full_chain():
    issues = control.validate_evidence(Evidence(id="EV-BAD", kind="experiment", locator="x", status="verified"))
    assert "EVIDENCE_MISSING_COMMAND" in issues
    assert "EVIDENCE_MISSING_ARGV" in issues
    assert "EVIDENCE_MISSING_CWD" in issues
    assert "EVIDENCE_MISSING_EXIT_CODE" in issues


def test_acceptance_pass_requires_verified_evidence(graph):
    st = initial_state(PROJECT)
    st["acceptance"] = {"AC-BAD": AcceptanceCriterion(id="AC-BAD", statement="bad", method="test", result="pass", evidence_id="EV-404")}
    cfg = _cfg("CP-AC")
    graph.invoke(st, cfg)
    snap = graph.get_state(cfg)
    assert snap.values["alignment"].verdict == "conflicting"
    assert any("ACCEPTANCE_UNKNOWN_EVIDENCE" in x for x in snap.values["verification"].issues)
