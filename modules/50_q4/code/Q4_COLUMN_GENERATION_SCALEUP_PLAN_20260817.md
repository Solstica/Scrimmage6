# Q4 Benders + Column Generation 全规模实现计划（2026-08-17）

状态：`DRAFT / NEEDS_REVIEW`

## 1. 背景

Q4 的完整合法 task master 有约 `233,375,201` 个 `(task,region,start)` binary candidates。显式构造 assignment + GPU + IT + Facility 稀疏矩阵的 nonzero 下界约 `2.96e9`，仅 CSR 数值与索引粗略估计已约 `35--47 GB`，未计 solver/presolve/branch-and-bound/Benders cuts。

因此：

- 完整 joint formulation 与 Benders decomposition 作为数学模型保留；
- 全规模实现不能一次性显式生成全部 task columns；
- 必须使用保持完整合法域等价性的 delayed/implicit master representation。

## 2. 正式候选路线

采用：

`Benders decomposition + stabilized column generation`。

- Benders 处理 task decisions 与 Renewable/BESS/Grid recourse 的分离；
- Column generation 处理 2.33e8 个潜在 task columns 的隐式生成；
- baseline Cost-only 已证明 complete recourse，只需 Benders optimality cuts；
- Carbon/renewable stress scenario 若出现 recourse infeasibility，再按需补 feasibility cuts。

若 root CG 后 restricted integer master 的 gap 足够小，优先停在 `CG + restricted MILP`；只有整数 gap 仍明显时，才升级 branch-and-price / branch-price-and-Benders。

## 3. Pricing 的附件结构

Flexible tasks = BatchInference + AITraining。

附件结构：

- `EarliestStart=ArrivalHour`；
- `LatestFinish=2406`；
- duration 仅 10--399 min，最多占 7 个小时格；
- duration unique count 很小；
- RT start 固定为 ArrivalHour，可全部显式保留；
- flexible task 的 Region 仍使用完整 latency-feasible set。

因此 pricing 不需要枚举所有 `(r,s)` columns。

对固定 `(TaskType k, Region r, Duration d)`，由 RMP dual 与当前 Benders cuts 构造逐时有效 reduced-cost signal `phi[k,r,t]`，预计算：

`F[k,r,d](s)=sum_t overlap[d,s,t]*phi[k,r,t]`

再做合法 start 区间上的 suffix minimum / argmin。对单个 task-region pair，最优 start 只需要数组查询。

完整候选仍隐式存在；禁止 top-k、固定最大等待窗口、最近区域截断。

## 4. 终止条件

Root LP 只有同时满足：

1. 当前 task schedule 没有 violated Benders optimality cut；
2. pricing oracle 找不到 reduced cost `< -eps_price` 的合法 column；

才可认为 restricted master LP 与完整隐式 master LP 在当前 Benders cut set 上闭合。

## 5. 稳定化

Probe 2 已出现只用最新 dual 的 `A -> B -> A` 振荡。Column generation 同样可能受 master degeneracy / dual instability 影响。

因此 Probe 先比较：

- raw dual pricing；
- 简单 convex dual smoothing / stabilized pricing；

但 smoothing 参数只作为数值加速，不改变最终 exact pricing 门禁；终止时必须用未平滑原 dual 做一次 exact reduced-cost check。

## 6. 用户给定资源预算 / 验收门禁

全规模最终程序按以下硬工程目标设计：

- **总峰值内存目标：<= 10 GB；绝对上限：20 GB**；
- **总 wall-clock 目标：<= 9 h**；
- 若预测超过 20 GB 或 9 h，不直接运行完整方案，必须切换到更节省的 column batching / disk-backed column pool / exact dominance / branch 延后策略；
- 不以牺牲完整合法域为代价换算力。

Probe 必须输出：

- 每轮 active columns；
- 新增 columns；
- pricing wall time；
- RMP solve time；
- Benders recourse time；
- peak RSS；
- projected 50k-task memory/time；
- root LP LB；
- restricted integer UB；
- integrality gap。

## 7. 当前任务

下一步运行 `Q4 Column Pricing Probe`：

1. 在真实 40-task Benders benchmark 上实现 exact pricing，先与显式 3139-column master 对照；
2. 扩展到 100/500/1000/5000 task 子样本，记录 active-column growth 与求解时间；
3. 单独对全 50,000 task 运行 pricing-oracle-only / memory projection，不显式建立 2.33e8 columns；
4. 根据增长规律估计 10/20 GB 与 9 h 预算下是否可行；
5. 若可行，再交给正式程序实现 full-scale stabilized CG+Benders。

## 8. 文献范式边界

Benders + column generation / branch-and-price 是成熟分解范式；本文创新不表述为“提出新 Benders/CG”。本题特化来自：

- task-level full legal domain；
- RT/Batch/Training 异质柔性；
- short overlap duration；
-统一 closure 2406；
- BESS recourse 的 dual/Benders cut；
- 利用附件 duration/start-domain 结构实现 suffix-min exact pricing。
