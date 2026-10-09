> 状态注记（2026-10-09 后续）：本报告的 open-end `[0,score_end)` 已由 D-0075 改为闭区间 `[0,score_end]`；canonical 复算与 LR 首轮均已完成，见 `results/E1/domain_unified/LR_model.md`。本文件保留为当时 STOP ③ 的历史记录。

# 轮 B 停机报告（2026-10-09）

## 结论

- canonical domain 复算完成：`[0, score_end)`、`GRID=0.25`、含无音符格点。
- B1 canonical CV 的 `d_min` argmax：**0.0 拍**（未重调）。
- **触发轮 B 停机条件 ③**：full B2_K3 ±1 micro F1 在 canonical 域为 **0.26415214**，旧域为 **0.29705973**，差 **−0.03290759**（绝对值 > 0.03）。
- 因此未开始训练表、LR、V1–V5 训练管线；未进入轮 C。

## 逐值对照（±1 micro F1）

| 域 | 方法 | canonical | 旧域 | 差 |
|:--|:--|--:|--:|--:|
| test | B1/inversion | 0.39356363 | 0.39353135 | +0.00003228 |
| test | B2_K3 | 0.36657179 | 0.37122234 | −0.00465055 |
| full | B1/inversion | 0.27665189 | 0.27655722 | +0.00009467 |
| full | B2_K3 | 0.26415214 | 0.29705973 | **−0.03290759** |

## 边界披露

`[0, score_end)` 不含右端点。`Chopin/Etudes_op_10/10` 的 4 个 runs 各有一个 `UP` 标签恰落在 `score_end`，被 canonical 域排除。因此 full `n_truth=28,599`，旧域为 `28,603`。

## V1 定义冲突（未排除，训练表未启动）

轮 B 指示 V1 要求“特征只能由谱面音符 + 栅格算出”，且“是否触碰任何标注/演奏文件”必须可证伪。但 `PedNotate_Plan_v3.0.md` §5.1 A 层明确为“源自该 run 的 CC64”，且 `δ_onset/δ_offset` 的“最近拍 / 局部 IBI”若取 performance beats 必然读取 `data/asap-dataset/asap_annotations.json`。在该冲突裁定前，未自行发明 score-grid IBI，也未运行训练。

## 产物与命令

```text
.venv-research\Scripts\python.exe tools/canonical_unified_eval.py --dataset data/asap-dataset --split evidence/R1/G1-split/split_v1.json --out-dir results/E1/domain_unified
```

- `results/E1/domain_unified/E1_main_canonical.csv`
- `results/E1/domain_unified/E1_main_canonical.json`
- `results/E1/domain_unified/E1_main_canonical.md`
- `evidence/R1/E1/canonical_unified_eval.log`

退出码 0。
