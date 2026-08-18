# Q4 50k 字典序最终再认证复核（2026-08-18）

## 1. 当前状态

模型版本：`region_multicut_v1`。

核心联合优化主问题已经完成最终列池上的两轮 `Cost -> Wait -> Latency` 再认证，状态可记为：

`FINISHED_DRAFT / CANONICAL JOINT ENDPOINT AVAILABLE`

这里的 `FINISHED_DRAFT` 表示 canonical 联合优化端点已经可用于论文结果整理，但题目要求的正式场景分析（Carbon constraints / electricity-price mechanisms / renewable fluctuation）仍未完成，因此 Q4 整问尚不能升级为 `FROZEN + CHECKED`。

## 2. 50k canonical 字典序端点

最终代表解：

- 任务数：50,000，TaskID 全覆盖且无重复；
- 最终真实能源成本：`-459,340,688.8007043 CNY`；
- Total Wait：`0 h`；
- Total Latency：`250,860 ms`；
- Mean Latency：`5.0172 ms`；
- P95 Latency：`5 ms`；
- Max Latency：`58 ms`；
- 迁移任务：`61 / 50,000 = 0.122%`；
- AITraining 迁移 52，BatchInference 迁移 8，RealTimeInference 迁移 1；
- 最晚完成时间：`2405.6 h`；
- 最终活动列：137,158；
- Benders cuts：1,173；
- hard-audit：PASS；
- 最大物理残差约 `1.14e-13`。

迁移主要集中于 E/F 之间：`F->E = 32`、`E->F = 15`，其余仅有少量 D/E/C/B/A 间调整。该结果不应被解读为“绿色区域硬编码”，因为附件六区 AvailableRenewable 的逐时值相同；空间调整来自 PUE、网络、负荷、价格/碳、储能与售电边界的联合结果。

## 3. 两轮 final-pool recertification

Sweep 1：

- Cost：active=137139，new columns=0，cuts=1135，LP=-459340688.80070555，restricted MIP=-459340688.80070555，true Energy=-459340688.8007043；
- Wait：active=137139，new columns=0，cuts=1149，LP=0，restricted MIP=0，true Energy=-459340688.8007043；
- Latency：active=137158，new columns=19，cuts=1160，LP=250469.95457912493 ms，restricted MIP=250860 ms，true Energy=-459340688.8007043。

Sweep 2：

- Cost：active=137158，new columns=0，cuts=1170，anchor 与 Sweep 1 完全一致；
- Wait：active=137158，new columns=0，cuts=1173，anchor=0 h，与 Sweep 1 完全一致；
- Latency：active=137158，new columns=0，cuts=1173，anchor=250860 ms，与 Sweep 1 完全一致。

两轮均满足：

- full-domain exact pricing 最小缺失列 reduced cost = 0；
- 最大区域 Benders violation = 0；
- restricted-column MIP gap = 0；
- true Energy LP 复核成本满足 Cost cap；
- 硬约束审计通过。

因此可称为：

**final-pool lexicographically recertified best-known integer representative solution**。

## 4. 最优性边界必须如实表述

不得写“50k 全局整数最优已证明”。

原因：`restricted_MIP_gap=0` 只说明当前最终活动列池上的整数 MIP 已解到最优；完整合法域的整数分支定价证书仍不存在。

Latency 阶段的完整域 LP 下界与整数代表解为：

- `LB_L = 250,469.954579 ms`；
- `UB_L = 250,860 ms`；
- absolute gap = `390.045421 ms`；
- relative gap = `0.1555%`。

论文推荐口径：

> 完整合法域 LP 定价与 region Benders 已闭合；最终扩展列池上获得真实能源可行的字典序整数代表解。Latency 的完整域 LP 下界与整数上界仅相差约 0.156%，但由于未执行完整 branch-price-and-Benders 整数证书，本文不声称 50k 全局整数最优。

Cost/Wait 两层在两轮再认证中均无新增负 reduced-cost 列，且 restricted MIP 与 LP anchor 一致；仍沿用同一谨慎措辞，不写 global integer optimum。

## 5. 新的数据机制结论：计算柔性与储能柔性具有强替代关系

Q2 在冻结能源动作时，Cost-primary canonical 排程表现为：

- migration rate 约 74.896%；
- mean wait 约 20.475 h；
- max wait 2016 h。

Q4 允许 BESS/Grid 与 workload 同时重新优化后，在更完整的真实能源 recourse 上得到：

- migration rate 仅 0.122%；
- Total/Mean/Max Wait 均为 0；
- 平均网络时延仅 5.0172 ms。

因此 Q4 的主要机制不应写成“为了降低能源成本，大规模迁移并延迟计算任务”，而应写成：

> **储能时间柔性吸收了绝大部分原本由 workload 时间/空间移动承担的调节需求；计算柔性仅需极少量空间修正即可维持同一成本 anchor。**

这说明 workload flexibility 与 storage flexibility 在当前附件数据下存在显著替代关系，Q2 与 Q3 的单侧价值不能简单相加，也进一步解释了为什么必须做 Q4 联合优化。

## 6. Q3 -> Q4 增量价值暂不冻结

当前已知 Q3 E1 成本约 `-459,217,791.04 CNY`，与 Q4 canonical 的表面差额约 `122,897.76 CNY`（约 0.0268%）。

但正式论文在引用该数前必须完成 Q3/Q4 accounting 对齐，特别检查 Hour 2406 terminal settlement、售电/购电统计时域和同一 Baseline 定义。未完成统一 accounting 前，该差额只能作为待核对的跨问 probe，不得写成正式“联合优化增量收益”。

## 7. 当前剩余 P0/P1

### P0-A 正式场景分析

必须在同一 joint workload--energy--storage 模型下完成：

1. Carbon constraints；
2. electricity-price mechanisms；
3. renewable fluctuation scenarios。

每个场景必须允许 workload placement + BESS/Grid 一起重新优化，并重新执行 exact pricing；不得把历史 `gamma=1.4` 诊断 probe 当正式场景。

### P0-B 六指标正式报告

对 canonical 与各正式场景统一计算：

- Cost；
- Carbon；
- Latency；
- QoS/Wait；
- RenewableUtilization；
- regional PeakNetImport。

不构造六指标等权分数。

### P0-C 跨问 accounting 统一

统一 Q2/Q3/Q4：

- 0--2405 scheduling-sensitive 统计；
- 2406 terminal energy settlement；
- Cost/Carbon/RenewableUtilization；
- PeakNetImport；
- Baseline/reference/B0 命名。

之后再冻结 `Q2-only vs Q3-only vs Q4-joint` 比较。

### P1 图与论文

优先图：

1. 六区域算力--网络--PUE--储能结构矩阵；
2. 顺序 Q2->Q3 失真 probe；
3. 两类柔性争用/替代同一新能源的机制图；
4. final-pool 两轮 Cost/Wait/Latency 再认证图；
5. Q2-only / Q3-only / Q4-joint 统一比较；
6. Carbon / price / renewable 正式场景图。

## 8. 禁止再做的事

- 不再为追求“全局最优”新增 branch-and-price / stabilization，除非最终论文明确需要更紧整数证书且计算预算允许；
- 不恢复旧 1171 h、378199 h restricted-pool QoS 结果；
- 不把 restricted MIP gap=0 写成 full-domain integer gap=0；
- 不为了六指标报告引入 AHP、熵权、等权 minimax；
- 不把 Q2 与 Q3 的成本简单相加或直接比较未统一 accounting 的绝对值。
