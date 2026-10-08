# B2 Round A 收尾记录（2026-10-09）

## 产物

- `results/E1/B2_perf.csv`：K=1/2/3 × 271 runs × 0/±1/±2；新增 DOWN/UP 分标签绝对计数列。
- `results/E1/B2_summary.json`、`results/E1/B2_summary.md`：CV、val、test、全量 36 首域、micro/bootstrap、分标签 bootstrap。
- `results/E1/B2_bootstrap_perlabel.json`：按 score 重采样的分标签配对 bootstrap（seed=20260101，boot=10000）。
- `results/E1/floor_reference_test.md`：谱面一致度轴地板表加入 `notation_reference` 恒等行；纠正注记 1 的 36 域分母。
- `results/E1/replay_fidelity_reference.md`：回放轴副指标表，与谱面轴分表；引用 `MAIN_METRIC_round1.md`。
- `evidence/R1/E1/fold_test_inventory.md`：test 折 7 首逐曲 runs / pedal elements 清单。

## 完整命令

```text
.venv-research\Scripts\python.exe tools/b2_harmony_segments.py --dataset data/asap-dataset --split evidence/R1/G1-split/split_v1.json --out-dir results/E1 --boot 10000 --seed 20260101
.venv-research\Scripts\python.exe tools/e1_test_domain.py --dataset data/asap-dataset --split evidence/R1/G1-split/split_v1.json --fold test --out results/E1/floor_reference_test.md
.venv-research\Scripts\python.exe tools/b2_perlabel_bootstrap.py --dataset data/asap-dataset --split evidence/R1/G1-split/split_v1.json --b2-perf results/E1/B2_perf.csv --out results/E1/B2_bootstrap_perlabel.json --boot 10000 --seed 20260101
```

退出码均为 0。B2 主运行日志：`evidence/R1/E1/B2_roundA_final.log`；地板表日志：`evidence/R1/E1/floor_reference_test_roundA.log`；分标签 bootstrap 日志：`evidence/R1/E1/B2_perlabel_bootstrap_roundA.log`。

## 逐值检查

- `B2_summary.json.alignment_proof.PASS = true`；n_scores=36，n_runs=271，B1 inversion F1=0.276557，四条基线逐值相等，`bootstrap_equal=true`。
- `parse_cache.miss = 36`。
- test ±1 聚合计数：tp=11006、fp=32012、fn=5272、wrong=352。
- 分标签计数：DOWN tp=7267 / fn=1190 / wrong=228；UP tp=3739 / fn=4082 / wrong=124；两类 tp/fp/fn/wrong 逐项相加回到上述聚合值。
- test 折 7 首：raw runs=78，evaluable runs=77，pedal elements=1051。

## 轴分离核查

- 谱面一致度轴 `notation_reference` 是构造恒等，F1=1.0，无判别力；不得当预测力参照。
- 回放轴 `MAIN_METRIC_round1.md` 的 notation reference 值为 0/±0.25/±0.5/±1.0 = 0.0552/0.1222/0.1807/0.2434。
- 0.3146 不在回放轴表中：它是谱面一致度轴上 inversion 的 ±2 拍值。
