# 通道覆盖率表（43 首主轴，D-0050 第 1 件）

产物：`coverage_43.json`、`closed_loop_43_minpair.json`、`loop43_table.txt`。
口径：渲染侧坐标化 = **顺序对应 + 逐轨 tick / PPQ**（不使用演奏侧信息）。

## 分类结果

| 类别 | 首数 | 说明 |
|:--|--:|:--|
| **in_grid**（中位偏差 ≤ 2/PPQ） | **18** | 通道读数落在渲染量化格内 |
| **count_mismatch（T2 类）** | **9** | 渲染器产出 `C < 2·min(S,T)`（丢事件），1:1 顺序对应不适用 → 属于已披露的 T2/T2b 机制 |
| **deviation_out_of_grid（计数守恒）** | **8** | 计数一致但位置偏出格：需逐首归因 |
| no_data | 8 | 该谱 pedal 配对为空（全孤立 stop / 全未闭合 start）→ 天然无 CC64 |

## 逐首列名（非 in_grid，按中位偏差降序）

| 乐谱 | 中位偏差 | exp/cc64 | 类别 | 我方位置 vs partitura |
|:--|--:|:--|:--|--:|
| Chopin/Sonata_3/3rd | 73.75 | 16/12 | count_mismatch | 3.13 |
| Schumann/Arabeske | 62.00 | 136/136 | deviation | 1.25 |
| Schumann/Kreisleriana/4 | 56.25 | 4/4 | deviation | 0.00 |
| Chopin/Barcarolle | 42.50 | 418/388 | count_mismatch | **397.06** |
| Chopin/Ballades/1 | 27.00 | 446/432 | count_mismatch | 0.00 |
| Beethoven/29-4 | 23.50 | 20/14 | count_mismatch | 0.00 |
| Chopin/Scherzos/31 | 19.00 | 458/456 | count_mismatch | 0.00 |
| Chopin/Etudes_op_25/1 | 18.84 | 172/152 | count_mismatch | 1.00 |
| Chopin/Scherzos/39 | 18.00 | 236/224 | count_mismatch | 0.00 |
| Scriabin/Sonatas/5 | 5.50 | 14/14 | deviation | — |
| Beethoven/31-2 | 4.00 | 4/4 | deviation | 0.00 |
| Beethoven/31-2_no_repeat | 4.00 | 4/4 | deviation | 0.00 |
| Chopin/Etudes_op_10/8 | 3.00 | 70/68 | count_mismatch | 1.00 |
| Debussy/Reflets_dans_lEau | 0.09 | 10/10 | deviation | **82.01** |
| Ravel/Pavane | 0.04 | 4/4 | deviation | 0.00 |
| Chopin/Ballades/3 | 0.004 | 480/478 | count_mismatch | 415.5 |
| Scriabin/Etudes_op_8/11 | 0.004 | 2/2 | deviation | 0.00 |

no_data（8 首，全在 T3 类）：`Beethoven/21-3`、`28-1`、`Chopin/Etudes_op_25/12`、`Sonata_2/1st_no_repeat`、`Sonata_2/2nd`、`Sonata_2/2nd_no_repeat`、`Sonata_3/2nd`、`Sonata_3/4th`。

## 本轮确认的两条机理

1. **渲染器丢弃事件**：`C < 2·min(S,T)` 的 9 首即既有 T2/T2b 清单，与本表 count_mismatch 高度重合 → **顺序对应在这些谱上不适用**（不是位置错，是事件数就不等）。
2. **partitura 的 `onset_beat` 不是权威**：`Debussy/Reflets` 上 partitura 与我差 82 拍，而**渲染与我差 0.09 拍** → 渲染跟的是 XML 光标语义，partitura 的 beat 口径与它不同。故 partitura 只能作旁证，不能作判据。

## 状态

- 第 1 件（43 首覆盖率表）✅ 完成
- 第 2 件（修光标语义）：诊断为**两类**——T2 丢事件（不可用顺序对应）＋ 少数"渲染器把 CC64 放在非记号位置"（如 31-2 差 4.0 拍且我与 partitura 一致）
- 第 3 件（主指标）：**未产出**