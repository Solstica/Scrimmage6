# Q4 全规模 Master 可扩展性与新能源场景校准探针（2026-08-17）

状态：`DRAFT / NEEDS_REVIEW`

本探针针对文献审计后的两个风险：

1. 40-task Benders 成功是否意味着 50,000-task full explicit master 也可直接建立；
2. 新能源波动场景能否用附件 100 天历史日波动分位数校准。

## 1. 完整合法 task candidate 数量

按当前统一解释：

- RT：`s_i=ArrivalHour_i`，Region 覆盖完整 latency-feasible set；
- Batch/Training：所有满足 `EarliestStart<=s`、`s+p_i<=min(LatestFinish,2406)` 的整数小时 start 与完整 SLA 合法 Region；
- 不使用 top-k、最大等待窗口、最近区域裁剪。

得到：

- AITraining：`118,779,696` candidates；
- BatchInference：`114,547,455` candidates；
- RealTimeInference：`48,050` candidates；
- 合计：`233,375,201` binary candidates。

平均每任务约 `4667.5` 个候选，单任务最大 `14,436`。

## 2. 显式 Master 的稀疏矩阵下界

即使 Benders master 只显式保留最基本的：

- 每任务 assignment；
- 每 `(r,t)` GPU；
- IT；
- Facility；

并把 latency/deadline 通过候选域预先过滤，不计任何 Benders cut、QoS、Carbon 或其他约束，按任务 duration 的实际 overlap 估算，也至少需要：

`2,957,875,739` 个 constraint nonzeros。

仅 CSR 数值+索引的粗略下界：

- 按 12 byte/nonzero：约 `35.49 GB`；
- 按 16 byte/nonzero：约 `47.33 GB`。

同时，仅 233,375,201 个候选的：

- 8-byte objective vector ≈ `1.87 GB`；
- 两个 8-byte bounds arrays ≈ `3.73 GB`；
- 即使 integrality 只按 1 byte 也 ≈ `0.23 GB`。

真实 MILP solver 还要保存 presolve、branch-and-bound、row/column metadata、Benders cuts 等，内存会明显更高。

## 3. 结论：完整 Benders 模型成立，但不能等价为“把 2.33e8 列一次性全部显式建出来”

Probe 3 已经证明：

`task master + continuous energy recourse + Benders cuts`

在小规模 exact benchmark 上正确。

本探针进一步说明：全规模实现必须采用 **隐式/延迟列表示**，例如：

- delayed candidate activation；
- restricted master + exact pricing / column generation；
- 可证明的 exact dominance pruning；
- 或等价的 branch-price-and-Benders 结构。

这些方法的目的不是增加算法复杂度，而是保持完整合法域同时避免显式存储 2.33e8 个候选。

仍然禁止 arbitrary top-k / 24 h wait window / nearest-region truncation。

因此正式论文表述应区分：

- **mathematical model**：完整 Benders-compatible joint formulation；
- **full-scale implementation**：需要 exact delayed/implicit master representation。

在真正实现 pricing/column activation 前，不得声称“50,000 任务全局最优已由 full Benders 直接求得”。

## 4. 新能源日波动分位数校准失败——这是附件结构，不是程序问题

对主时域 `Hour 0..2399` 的 100 个自然日检查 `AvailableRenewable`：

- 100 天的 24 h profile **完全相同**；
- daily CV 恒为 `0.2651661939`；
- daily max-min amplitude 恒为 `600 MW`；
- 100 天之间最大逐小时差为 0。

因此不能按“100 天日波动 CV 的 Q25/Q50/Q75”构造低/中/高新能源波动场景——这些分位数完全重合。

这纠正了此前“用附件日波动分位数校准 gamma”的建议。

## 5. 正式场景的合理方向

由于附件新能源曲线是严格重复的确定性 24 h profile，Q4 的“新能源波动场景”必然属于 **scenario construction / sensitivity analysis**，而不是从 100 天经验日波动分布直接抽样。

当前 Probe 3 的

`R_gamma = mean(R) + gamma*(R-mean(R))`

仍可作为透明的 mean-preserving volatility generator，但参数应由可解释阈值组织，例如：

- `gamma=1`：附件 baseline；
- `gamma=gamma_crit`：Cost-optimal recourse 首次出现正碳排/能源稀缺的结构临界点；
- 临界点以上选一个压力场景，仅用于敏感性。

`gamma_crit≈1.303326` 仍是 40-task 局部 probe 的诊断阈值，不能直接当全时域最终参数；全规模程序应重新求系统级 critical threshold。

结果摘要见 `modules/50_q4/results/q4_full_master_scalability_20260817.csv`。
