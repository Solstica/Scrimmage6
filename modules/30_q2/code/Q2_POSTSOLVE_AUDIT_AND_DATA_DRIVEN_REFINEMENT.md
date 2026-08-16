# Q2 求解后审计与数据结构驱动修正

状态：`DRAFT / NEEDS_REVIEW`

本文件记录 2026-08-17 对最新 SFETA 草稿结果的复核，以及必须回写到正式实现的修正。当前 `q2_solver.py` 已能对 50000 个任务构造满足硬约束的完整可行解，但结果尚不能冻结。

## 1. 最新可行解的有效部分

当前草稿结果：

- 50000/50000 任务成功排程；
- GPU、IT、Facility、GridImport/GridExport、SLA、deadline、2406 边界均通过；
- 能量平衡最大残差约 `2e-4 MW`；
- 相对附件基准：Cost 约下降 7.34%，Carbon 约下降 6.22%，新能源利用率提高约 3.45 个百分点，弃电减少约 398505 MWh；
- 当前结果是某一固定字典序启发式的可行解，不是全局最优性证明。

这些数值继续保持 `DRAFT / NEEDS_REVIEW`。

## 2. 当前程序与正式模型规范的关键偏差

### 2.1 RT 被提前锁死在 SourceRegion

正式合法域：

`R_i = {r : Latency[source_i,r] <= MaxLatency_i}`。

RealTimeInference 只要求 `s_i = ArrivalHour_i`，并没有要求 `r_i = SourceRegion_i`。

当前程序只把 Batch/Training 放入 flexible set，RT 没有枚举其 20 ms 内合法区域，相当于人为缩小搜索域。

必须修正：

- RT 时间固定；
- RT 空间候选必须覆盖完整 `R_i`；
- 最终 RT 迁移数可以为 0，但必须是调度结果，而不能由代码先验写死。

### 2.2 候选排序仍是 baseline 静态信号，不是真正边际能源效应

当前代码缓存并排序：

`baseline Curtailment -> CarbonIntensity -> Price`。

这会把已经被前序任务吸收掉的基准弃电继续当成“可用机会”。可行性检查虽然使用当前状态，因此方案最终不会非法，但候选优先级可能严重失真。

正式 SFETA 必须对当前残余状态计算：

`DeltaCurtailment(i,r,s)`、`DeltaGridPurchase(i,r,s)`、`DeltaCost(i,r,s)`、`DeltaCarbon(i,r,s)`。

对于当前调度状态 `L_current` 和候选新增负荷 `deltaL_i`，边际量必须来自：

`EnergyResponse(L_current + deltaL_i) - EnergyResponse(L_current)`，

而不是读取 baseline `Curtailment0` 的静态积分。

### 2.3 Cost/Carbon 主次关系尚未做极值探针

正式规范要求先做：

- Cost-only；
- Carbon-only；

再计算交叉损失，判断两者是否近同向。

当前代码提前使用 `Curtailment -> Carbon -> Price` 字典序，因此 7.34%/6.22% 只能解释为当前规则结果。

必须补：

- `x_cost`：成本优先/近极值排程；
- `x_carbon`：碳优先/近极值排程；
- 交叉比较 `Cost(x_carbon)-Cost(x_cost)` 与 `Carbon(x_cost)-Carbon(x_carbon)`；
- 若冲突弱，冻结单主目标 + 另一指标评价；若冲突明显，再使用 epsilon-constraint。

### 2.4 等价能源候选缺少等待/迁移 tie-break

当前草稿出现：

- 迁移率约 46.66%；
- 延迟任务 21158；
- 最大等待约 1909 h。

硬约束上合法，但解释性较差。

正式规则不增加任何人为最大等待窗口，而是在边际能源后果完全等价或近等价时，按：

1. 更早开工；
2. 保持 SourceRegion；
3. 更小 NetworkLatency；

作确定性 tie-break。

这样不会截断合法域，也不会用主观权重，却可以避免“没有额外能源收益仍把任务推迟很久”。

### 2.5 baseline 不是当前硬约束下的 certified feasible schedule

附件 baseline 可以精确重构，但存在 GPU-hour 超限；当前结果报告中 baseline 最大 GPU 利用率约 135.58%。

因此代码和论文都不得写：

`baseline is a certified feasible starting point`。

应改成：

> baseline 是附件给定并可精确重构的参考运行状态；SFETA 从该状态出发完成资源可行性修复和能源感知重新分配。

若候选搜索失败，不能无条件回退 baseline position。必须：

- 记录 fallback 次数；
- 对 fallback 重新执行完整硬约束检查；
- 无合法候选则明确报 FAIL，而不是默认 baseline 必然可行。

## 3. 数据结构如何真正进入 Q2 建模

Q2 的创新不来自给普通 0-1 调度换名字，而来自附件数据直接决定了调度规则。

### 3.1 任务柔性与资源重量是两个不同维度

对每个任务定义：

- 空间柔性：`|R_i|`；
- 时间余量：`Slack_i = LatestFinish_i - Arrival_i - p_i`；
- 资源重量：`W_i = GPU_i * p_i`（GPU-hour）。

数据表明：

- RT：时间刚性，空间域约 1--3 个区域，资源重量最小；
- Batch：时间和空间均较柔性，资源重量中等；
- Training：空间域全部 6 区、时间余量最大，而且贡献约 80% GPU-hour、约 87% 任务 AI 能耗。

因此 priority rule 不应来自主观权重，而由数据自然形成偏序：

`|R_i| 小 -> Slack_i 小 -> GPU-hour 大` 优先。

这表示先保护“最难移动”的任务，再处理“大体量柔性任务”。

### 3.2 能源机会来自基准弃电空间差异，而不是 AvailableRenewable 标签

数据探针发现六区域 `AvailableRenewable` 逐时完全相同，因此不能写“迁往新能源更多的 E/F”。

真正存在空间差异的是 `Curtailment0`。因此增加设施负荷的能源响应是分段的：

- `0 < DeltaL <= Curtailment0`：只减少弃电，不增加购电；
- `DeltaL > Curtailment0`：超出部分才增加购电；
- `DeltaL < 0`：先减少原供负荷购电，再增加弃电。

这就是 Q2 最关键的数据驱动机制：

`任务时空柔性 -> Facility Load 增量 -> 弃电/购电分段响应 -> Cost/Carbon/eta_R`。

### 3.3 论文模型建立顺序

推荐按：

1. 任务类型的时空柔性差异；
2. GPU-hour 资源重量差异；
3. AvailableRenewable 无空间辨识、Curtailment0 有空间差异；
4. 建立增量能源分段响应；
5. 再定义完整时空候选与硬约束；
6. 用 SFETA 构造可行调度。

不要从 `x[i,r,s]` 和目标函数直接起笔。

## 4. 文献对应关系

以下文献支持概念和算法思想，不声称与本题一模一样。

1. Sukprasert T, Souza A, Bashir N, Irwin D, Shenoy P. On the Limitations of Carbon-Aware Temporal and Spatial Workload Shifting in the Cloud. EuroSys 2024: 924--941. DOI: 10.1145/3627703.3650079.
   - 支持 temporal/spatial workload shifting；
   - 支持复杂算法收益可能有限，因此保留简单、可解释的规则调度。

2. Zheng J, Chien A A, Suh S. Mitigating Curtailment and Carbon Emissions through Load Migration between Data Centers. Joule, 2020, 4(10): 2208--2222. DOI: 10.1016/j.joule.2020.08.001.
   - 直接支持 workload migration 用于 renewable curtailment mitigation。

3. Hanafy W A, Liang Q, Bashir N, Irwin D, Shenoy P. CarbonScaler: Leveraging Cloud Workload Elasticity for Optimizing Carbon-Efficiency. Proc. ACM Meas. Anal. Comput. Syst., 2023, 7(3), Article 57. DOI: 10.1145/3626788.
   - 支持用 marginal resource allocation 思想评价调度的边际碳影响；
   - 本题不照搬可弹性缩放 GPU 数，只吸收“边际而非静态评分”的思想。

4. Xu K, Sun D, Tian H, Zhang J, Chen K. GREEN: Carbon-efficient Resource Scheduling for Machine Learning Clusters. NSDI 2025: 999--1014.
   - 支持利用 ML job temporal flexibility 做 carbon-aware scheduling，同时保留容量/时间效率边界。

5. Chen D, Ma Y, Wang L, Yao M. Spatio-temporal management of renewable energy consumption, carbon emissions, and cost in data centers. Sustainable Computing: Informatics and Systems, 2024, 41: 100950. DOI: 10.1016/j.suscom.2023.100950.
   - 直接支持数据中心计算负荷的 spatio-temporal scheduling 与新能源、成本、碳联动。

## 5. 下一轮程序验收门禁

- RT 完整空间域已释放；
- 任一候选的排序使用当前状态边际能源后果，而非 baseline 静态评分；
- Cost-only / Carbon-only 探针完成；
- 等价能源后果下等待/迁移 tie-break 已加入；
- baseline fallback 不再默认可行；
- 50000 个任务全部完成，所有容量/SLA/能源门禁仍 PASS；
- 报告等待时间分布是否显著收敛；
- 新结果继续保持 `DRAFT / NEEDS_REVIEW`，直到建模手复核。
