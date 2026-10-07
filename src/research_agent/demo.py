"""最小运行示例 + 中断/恢复示例 + 跨线程 store 读取 + 重启恢复。

用法:
    python -m research_agent.demo
"""

from __future__ import annotations

import sys

from langgraph.types import Command

from .graph import compile_graph, sqlite_persistence, thread_config
from .memory import initial_state, recall_decisions


def show_interrupts(snapshot) -> None:
    for task in getattr(snapshot, "tasks", ()) or ():
        for item in getattr(task, "interrupts", ()) or ():
            print(f"    [interrupt] {item.value}")


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    project, task = "midi2score", "PHASE-2"
    cfg = thread_config(project, task)
    print(f"thread_id = {cfg['configurable']['thread_id']}  (stable, 可推导)")

    with sqlite_persistence() as (checkpointer, store):
        graph = compile_graph(checkpointer, store)

        print("\n[1] 首次运行：应在 human_review 处中断")
        graph.invoke(initial_state(project), cfg)
        snap = graph.get_state(cfg)
        print(f"    next = {snap.next}")
        show_interrupts(snap)

        print("\n[2] 恢复会话：Command(resume='approve')")
        graph.invoke(Command(resume="approve"), cfg)
        snap = graph.get_state(cfg)
        print(f"    next = {snap.next}  phase = {snap.values.get('current_phase')}")
        print(f"    approval = {snap.values.get('approval')}")
        print(f"    decisions = {list(snap.values.get('decisions', {}))}")
        print(f"    recalled  = {snap.values.get('recalled_decisions')}")
        print(f"    messages  = {len(snap.values.get('messages', []))} 条（窗口上限 20）")

        print("\n[3] 检查点历史（最近 3 条）")
        for i, s in enumerate(graph.get_state_history(cfg)):
            if i >= 3:
                break
            print(f"    {i}: next={s.next} phase={s.values.get('current_phase')}")

    print("\n[4] 跨线程：长期 store 可被另一 thread 读取（状态互相隔离）")
    other = thread_config(project, "OTHER-TASK")
    with sqlite_persistence() as (cp2, store2):
        graph2 = compile_graph(cp2, store2)
        print(f"    store decisions = {[d['id'] for d in recall_decisions(store2, project)]}")
        try:
            snap2 = graph2.get_state(other)
            print(f"    other thread values empty = {not snap2.values}")
        except Exception as exc:  # 全新 thread 无状态时应表现为空
            print(f"    other thread has no state ({type(exc).__name__})")

    print("\n[5] 进程重启恢复：重新打开 SQLite 读回同一 thread")
    with sqlite_persistence() as (cp3, store3):
        graph3 = compile_graph(cp3, store3)
        snap3 = graph3.get_state(cfg)
        print(f"    phase = {snap3.values.get('current_phase')}  approval = {snap3.values.get('approval')}")
        print(f"    charter_sha256 前 16 位 = {str(snap3.values.get('charter_sha256'))[:16]}")

    print("\n[6] 目标偏离：conflicting 时普通 approve 不放行")
    with sqlite_persistence() as (cp4, store4):
        graph4 = compile_graph(cp4, store4)
        drift = initial_state(project)
        drift["charter_sha256"] = "0" * 64  # 模拟章程被外部改动
        cfg_drift = thread_config(project, "PHASE-3-DRIFT")
        graph4.invoke(drift, cfg_drift)
        al = graph4.get_state(cfg_drift).values["alignment"]
        print(f"    alignment = {al.verdict}")
        print(f"    violates  = {al.violates}")
        graph4.invoke(Command(resume="approve"), cfg_drift)
        print(f"    普通 approve 后 phase = {graph4.get_state(cfg_drift).values['current_phase']}（未放行）")

    print("\n[7] 只有显式 override 才放行，并记为人工覆盖决策")
    with sqlite_persistence() as (cp5, store5):
        graph5 = compile_graph(cp5, store5)
        drift2 = initial_state(project)
        drift2["charter_sha256"] = "0" * 64
        cfg_ovr = thread_config(project, "PHASE-3-OVERRIDE")
        graph5.invoke(drift2, cfg_ovr)
        graph5.invoke(Command(resume="override"), cfg_ovr)
        vals = graph5.get_state(cfg_ovr).values
        d = vals["decisions"]["D-WP-1"]
        print(f"    phase = {vals['current_phase']}  decision = {d.id}  source = {d.source}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())