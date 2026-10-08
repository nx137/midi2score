# B2 运行记录（第二轮）：冒烟通过，全量仍超时

## ✅ 收紧 1 的冒烟（已通过，命令与输出）

```
python tools/b2_smoke.py
Chopin/Ballades/3:            anchors=2893  全等=2893/2893  空锚点=1029  1.09s
Schumann/Kreisleriana/6:      anchors=723   全等=723/723    空锚点=418   0.13s
Beethoven/Piano_Sonatas/32-1: anchors=2549  全等=2549/2549  空锚点=604   0.87s
合计：全等 6165/6165；空锚点样本 2051；判据 = 字典全等（不是 F1/分布）→ PASS
```
- 覆盖：含和弦谱、out-of-grid 谱、`n_notes == 0` 的空锚点
- 双指针比较式与 `anchor_features` 的选择谓词**逐字相同**（半开区间 `[t, t+GRID)`），**不使用除法取整分桶**
- 谓词只依赖 `pos` ⇒ 桶化成立（未触发放置条件）

## ⚠️ 全量仍超时（第二轮根因）

已实施：每 run 特征只算一次（K 无关）+ 双指针分桶 + K 只参与整数比较。
**但 `per_run(K)` 内仍在逐 run 重复调用 `parse_score(r["xml"])`（且被调用两次、每 K 再重复）** ⇒
271 runs × 2 次 XML 解析 × 3 K ≈ 1,600 次解析，仍为分钟级~十分钟级。

**下一轮一行级修法**：把 `parse_score(xml)` 与 `parse_alignment(al)` 也放进**按 score 的缓存**（与 `features_once` 同一份），
使解析次数从 ~1,600 降到 36（每谱一次）。预计单轮 < 1 分钟。

**未出数、未留半成品产物**（脚本在末尾写文件）。