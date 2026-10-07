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
    return 0


if __name__ == "__main__":
    raise SystemExit(main())