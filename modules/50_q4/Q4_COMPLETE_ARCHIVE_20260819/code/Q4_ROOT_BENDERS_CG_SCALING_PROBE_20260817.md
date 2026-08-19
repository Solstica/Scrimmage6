# Q4 完整 Root Benders + Column Generation 扩展性探针（2026-08-17）

状态：`DRAFT / NEEDS_REVIEW`

目的：不再用 `233,375,201` 个潜在 time-indexed placements 的显式矩阵下界估计正式 Q4，而直接运行 **完整 0--2406 时域、完整合法域的 Root Benders + exact column pricing**，实测 5k / 10k / 25k / 50k 任务的 active columns、Benders cuts、运行时间与峰值内存。

本探针只测试 **Cost-only root LP relaxation**。它不等于最终整数 Q4，也不包含 Carbon/Price/Renewable 多场景批量求解；因此结果用于判断全规模根节点可计算性，不用于提前声明最终整数最优。

## 1. 可行初始排程

直接把所有任务放在 `SourceRegion + ArrivalHour` 会在 GPU 约束上产生少量超载：共 44 个 Region-Hour 发生超限，而 IT 约束仍可行。因此子样本若把未选任务固定在 raw source-arrival 状态，会人为造成 Master infeasible。

本探针先对 raw 状态做一个只用于初始化的确定性可行修复：优先移动造成超载的 flexible task，在完整 latency/deadline 合法域内寻找最近可行位置。共移动 36 个任务后得到全 50k GPU/IT 可行参考排程，最紧 GPU 余量仍约 `0.6833` equivalent-GPU。该修复只生成初始 feasible columns，不限制后续 CG 的完整合法域。

5k/10k/25k 探针中，未选任务固定在该可行参考排程；选中任务释放完整合法域。50k 探针释放全部任务。

## 2. Root 算法

每轮执行：

1. Restricted Task Master：assignment + exact GPU/IT presolve rows + 已生成 Benders cuts；
2. 给定 fractional task schedule，六区域分别求完整 0--2406 BESS/Grid/Renewable LP；
3. 若 `theta_r < Q_r(L_r)`，加入 region optimality cut；
4. 若无新 cut，则用当前 Master dual 做 **exact pricing**；
5. Batch/Training 利用附件结构 `EarliestStart=Arrival`、`LatestFinish=2406` 与 390 种 Duration，以 `(TaskType,Region,Duration)` 模板计算 start score 和 suffix minimum；RT 只检查固定 start 下完整 latency-feasible regions；
6. 只有同时满足“无 violated Benders cut”和“完整合法域无 negative reduced-cost column”才终止。

Probe A 已验证的 Facility duplicate elimination 与 GPU/IT dominance presolve，以及 Probe B 的 sparse Benders-cut assembly 均启用。

## 3. 40-task exact 校准

为了验证 pricing/reduced-cost 实现不是近似，另取同一 full-horizon selection rule 的 40 个真实任务：

- 完整显式合法 placements：`177,995`；
- Root Benders+CG 最终 active columns：`44`；
- full-explicit root objective：`-459,131,390.7416639 CNY`；
- CG root objective：`-459,131,390.7416639 CNY`；
- 绝对差：`0 CNY`（solver tolerance）。

因此本探针的 suffix-min pricing 在该完整显式 benchmark 上保持了 root LP 等价性。

## 4. 5k--50k scaling 结果

| Released tasks | Status | Root iterations | Final active columns | Columns/task | Benders cuts | Internal root time/s | Peak RSS/MB | Final root LB/CNY |
|---:|---|---:|---:|---:|---:|---:|---:|---:|
| 5,000 | CONVERGED | 3 | 5,130 | 1.0260 | 8 | 7.535 | 630.97 | -459,242,272.024680 |
| 10,000 | CONVERGED | 5 | 10,277 | 1.0277 | 10 | 9.099 | 631.47 | -459,272,850.980864 |
| 25,000 | CONVERGED | 7 | 25,713 | 1.0285 | 10 | 16.905 | 641.25 | -459,336,400.910604 |
| 50,000 | CONVERGED | 8 | 51,465 | 1.0293 | 11 | 19.665 | 649.64 | -459,340,688.800243 |

50k 单独新进程用 `/usr/bin/time` 复核：

- 从读取六个附件、重构 workload、修复初始排程到 root 收敛的总 wall time：约 `23.62 s`；
- 进程最大 RSS：约 `649.5 MB`。

该机器/环境时间仅作为工程量级，不进入论文作硬性能承诺。

## 5. 50k 每轮结构

50k 初始只显式放 `50,000` 个可行参考 columns。第 1 次 exact pricing 扫描完整合法域后新增 `1,332` 个 columns；随后仅继续新增 `80 + 53` 个。最终：

`50,000 -> 51,332 -> 51,412 -> 51,465`。

即最终只比“一任务一列”多 `1,465` 个 active placements；虽然数学合法域仍是约 `2.33e8` placements，但 99.97% 以上不需要进入 Root RMP。

50k 共生成 11 条 regional Benders cuts，8 次 root 迭代收敛。最后一次 exact pricing 的最小 reduced cost 为 0，且 recourse 与 Master LB 一致到 solver tolerance。

典型一轮耗时量级：

- RMP LP：约 `0.21--0.31 s`；
- 六区完整 Energy recourse：约 `0.57--0.63 s`；
- full-domain suffix pricing：约 `2.8--3.1 s`。

因此在这个 baseline Cost-only root 中，**pricing 已经比 RMP/energy LP 更耗时，但总量仍很小**。此前“RMP 必然是 root 阶段主要瓶颈”的工程判断需要修正；真正仍未知的主要成本转移到最终 integer refinement / branch-and-price，以及多场景重复求解。

## 6. 对此前“计算量很大”的纠偏

`233,375,201` 是完整数学合法 placements 的 cardinality，用来证明“不能一次性显式建立 time-indexed Master”；它不是最终算法实际需要处理的显式变量数。

本次 50k 实测：

- 潜在 placements：约 `233.4 million`；
- Root 实际 active task columns：`51,465`；
- 压缩比约 `4,534 : 1`；
- Root peak RSS 约 `0.65 GB`，远低于原 10 GB 目标和 20 GB hard cap；
- Root wall time 为几十秒量级，而不是小时量级。

所以 Q4 的全规模难点已经不能再描述为“2.33 亿变量本身不可计算”。准确表述应是：**显式 time-indexed formulation 会表示膨胀，但数据结构驱动的 Benders + exact CG 能把 root problem 压回约一任务一列的数量级。**

## 7. 当前冻结与未冻结结论

可以冻结：

- 完整合法域仍保留，不采用 top-k / 固定等待窗 / 最近区域截断；
- full explicit Master 不实现；
- Root 正式采用 Benders + exact suffix-min column pricing；
- exact GPU/IT presolve、sparse cuts 继续采用；
- 50k root 在本附件 baseline Cost-only 场景已实测可计算，RAM/时间远低于工程门禁。

仍未冻结：

- 51,465 root columns 不代表最终整数阶段也只需同样数量；
- 当前 objective 是 root lower bound，不能直接作为最终 Q4 integer schedule；
- Carbon budget、价格机制、新能源 stress 会改变 dual active set 和 column growth，需要 warm-start/scenario probe；
- 是否需要真正 branch-and-price，要由 generated-column restricted MILP 的 integrality gap 决定。

下一步优先任务：在这 51,465 个 generated columns 上做 **restricted integer refinement**，报告 `LB_root / UB_integer / integrality gap / runtime / RAM`；若 gap 已足够小，则不为形式完整强行实现完整 branch-and-price。
