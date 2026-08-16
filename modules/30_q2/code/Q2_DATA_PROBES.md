# Q2 数据探针：能源状态、目标退化与任务时空柔性

状态：`DRAFT / NEEDS_REVIEW`

用途：在冻结 Q2 数学模型与 SFETA 规则之前，先用官方实际数据检查能源层与任务层的真实结构。本文件是数据探针，不是最终模型结果。

## 0. 题意边界

Q2 的显式决策变量是任务迁移区域与开工时段。`storage_information.xlsx` 在附件表格中对应 Q3/Q4 使用，因此本探针不把储能充放电、SOC 作为 Q2 决策变量。Q2 必须按实际任务、逐时电力参数和统一 power mapping 重算任务形成的负荷以及碳排/新能源利用指标。

当前 Q2 的一个关键解释问题是：能源层是否允许在 Q2 内完全重新分配 `AvailableRenewable_MW`，还是应把 `region_time_data.xlsx` 的基准能源运行状态视为外生背景，仅计算任务迁移造成的边际能源后果。下面同时检查这两种解释，以判断哪一种会导致模型退化。

---

## 1. 探针 A：若 Q2 允许“无储能、可用新能源优先直接供负荷”的完全重分配，会发生什么？

### A1. 基准设施负荷已经全部低于 AvailableRenewable

在 0--2399 h，六个区域按

`Facility = PUE * (NonAI_IT_Load + Baseline_AI_IT_Load)`

重算后，每个区域每个小时均有

`Facility < AvailableRenewable`。

基准最小新能源余量（MW）：

- RegionA: 10.5985
- RegionB: 13.5280
- RegionC: 13.5406
- RegionD: 52.8940
- RegionE: 57.3450
- RegionF: 49.2100

NonAI 单独负荷更不构成新能源缺口。

### A2. 构造性零购电可行性探针

在当前“整数小时开工”解释下，使用全 50000 个实际任务，保持全部合法 Region/Start 候选域，不人为截断候选，只施加：

- GPU 容量；
- IT 功率；
- Facility 功率；
- NetworkLatency <= MaxLatency；
- Earliest/LatestFinish；
- finish <= 2406；
- Facility <= AvailableRenewable（作为零购电探针的额外可行性条件）。

采用确定性可行性构造：RT 先放置；弹性任务按低 slack 优先，候选从最早合法时刻开始逐一检查全部 SLA 合法区域，直到找到第一个可行点。该规则只用于寻找一个可行证书，不代表正式 SFETA。

得到：

- 50000/50000 任务全部可行；
- GPU/IT/Facility/Latency/deadline/renewable 约束最大违规量均为 0；
- 仅 52 个任务需要跨区迁移；
- 其中 AITraining 44 个、BatchInference 8 个、RealTimeInference 0 个；
- 所有任务都可保持 ArrivalHour 立即开工，无需等待；
- GridPurchase = 0；
- CarbonEmission = 0。

因此在这种能源解释下，`min Carbon = 0` 被构造性证明，而且几乎不需要利用时间延迟柔性。

### A3. 这不是“好结果”，而是模型退化警报

如果 Q2 直接把 `AvailableRenewable_MW` 全部重新用于当前负荷，则碳目标会完全退化，购电价格也大幅失去作用。题目明确把 Q2 的决策变量写成任务迁移与开工时段，而储能/能源运行策略在 Q3/Q4 才正式释放；因此不宜在 Q2 偷偷加入一个完全自由的新能源再调度层。

**当前判断：Q2 正式模型不应采用“把所有 AvailableRenewable 无条件重新分配给负荷”的解释。该探针主要用于排除这一退化口径。**

---

## 2. 探针 B：把基准能源运行状态作为外生背景，数据中是否存在值得任务迁移利用的边际能源机会？

### B1. 基准状态同时存在大量弃电与电网供负荷

定义基准供负荷购电功率

`GridToLoad = max(GridPurchase_MW - GridCharge_MW, 0)`。

0--2399 h 共 14400 个 region-hour：

- `Curtailment_MW > 0`：14400 / 14400；
- `GridToLoad > 0`：13230 / 14400；
- **同时有弃电和电网供负荷**：13230 / 14400，约 91.9%。

全系统累计：

- Curtailment ≈ 7,748,360.94 MWh；
- GridToLoad ≈ 4,028,324.59 MWh；
- 基准 AI 设施侧能量 ≈ 950,773.63 MWh；
- Curtailment / AI facility energy ≈ 8.15。

这说明 Q2 的真正调节空间非常大：任务迁移可以把一部分当前由电网供给的 AI 负荷，移到存在弃电的区域/时段去消纳。

### B2. 六区域原始 AvailableRenewable 并没有空间差异，但 Curtailment 有很强空间差异

逐小时检查：

`AvailableRenewable_A(t) = ... = AvailableRenewable_F(t)`

严格成立，六区域同一小时最大差值为 0。

但基准 Curtailment 的空间差异很大：每小时六区弃电最大值与最小值之差的中位数约 443.30 MW，最大约 580.52 MW。

弃电最高区域：

- RegionA：2394 / 2400 h 为六区最高；
- RegionB：6 / 2400 h 为最高。

弃电最低区域：

- RegionE：1239 h；
- RegionF：1161 h。

因此，不能根据“E 光伏富集、F 风电富集”的文字标签给 Q2 人工制造空间新能源优势；实际可用于迁移调节的空间信号应来自逐时 `Curtailment_MW` / 基准能源余量，而不是原始 `AvailableRenewable_MW` 的区域标签。

### B3. 弃电本身已经具有明显低碳时间信息

各区域 `Curtailment_MW` 与 `CarbonIntensity` 的 Pearson 相关：

- A: -0.690
- B: -0.693
- C: -0.697
- D: -0.789
- E: -0.814
- F: -0.849

而 `Curtailment_MW` 与 `AvailableRenewable_MW` 的相关约 0.925--0.995。

含义：新能源富余高的时段通常同时具有更低的碳强度。因而“优先吸收弃电”本身已经天然带有 carbon-aware 属性，不需要人为给新能源和碳强度设置一套权重。

### B4. 电价与碳强度并非独立冲突轴，但区域排序非常稳定

全体 region-hour：

- ElectricityPrice 与 CarbonIntensity Pearson ≈ 0.578；
- Spearman ≈ 0.613；
- PUE 调整后 Pearson ≈ 0.626；
- PUE 调整后 Spearman ≈ 0.618。

更重要的是，对每个小时比较六区域 `PUE * BuyPrice` 与 `PUE * CarbonIntensity`：

- 2400 / 2400 h 的最低值都在 RegionE；
- RegionE 每小时均为这两个“购电边际信号”的 Pareto 非支配区域。

所以一旦某候选超过可利用的弃电余量、真正进入新增购电状态，成本和碳通常不会形成强烈的空间冲突；两者在区域选择上高度同向。

### B5. 对 SFETA 的直接启示

Q2 的候选位置不宜先用 BuyPrice/CarbonIntensity 加权评分，而应先识别能源状态：

1. 候选增量负荷可被基准 Curtailment 吸收：边际购电/碳增量近 0；
2. 弃电余量耗尽后，再进入电网边际区，此时由 BuyPrice 与 CarbonIntensity 区分；
3. 若正式解释允许考虑售电机会成本，再另行加入 SellPrice，但这一点必须先核对 Q2 是否允许使用 Q3/Q4 的购售电边界，不能直接从 `storage_information.xlsx` 偷渡到 Q2。

**因此现阶段应把“弃电吸收 -> 购电边际”作为 Q2 最稳定的能源状态分层；SellPrice 三状态版本暂不冻结。**

---

## 3. 探针 C：任务合法时空域到底有多大、柔性差异是否足以支撑 SFETA？

以下在当前整数小时开工解释下统计完整合法域，仅按 deadline/2406/MaxLatency 删除硬不可行候选。

### RealTimeInference

- 任务数：16724；
- 开工时刻：固定为 ArrivalHour，始终只有 1 个；
- SLA 合法区域数：
  - 3 区：15090 个任务；
  - 2 区：1146；
  - 1 区：488；
- 总 `(task,region,start)` 候选：48,050；
- slack 中位数约 0.50 h；
- GPU-hour 中位数约 10.83。

### BatchInference

- 任务数：16717；
- 合法区域数：5 或 6；
- 合法开工数中位数：1208；
- 候选数中位数：6835；
- slack 中位数：1207.22 h；
- GPU-hour 中位数：37.80；
- 总候选：114,547,455。

### AITraining

- 任务数：16559；
- 所有任务均有 6 个 SLA 合法区域；
- 合法开工数中位数：1185；
- 候选数中位数：7110；
- slack 中位数：1184.22 h；
- GPU-hour 中位数：194.35；
- 总候选：118,779,696。

三类合计完整候选约：

`233,375,201`。

### 结构判断

任务柔性差异不是人为构造出来的，而是非常强的数据结构：

- RT：时间几乎刚性，空间也受 20 ms 强限制；
- Batch：时间/空间均有大幅柔性；
- Training：空间完全开放、时间窗很宽，而且单任务 GPU-hour 最大。

这为 SFETA 的 `least-flexible-first` / 约束优先构造式调度提供直接数据依据。无需再造一个带主观权重的柔性 Score。

---

## 4. 当前冻结与未冻结判断

### 可以暂时冻结

1. Q2 是“碳感知多区域时空资源约束任务调度模型”，SFETA 是求解算法，不是模型本身。
2. Q2 不应自由重优化储能；若完全自由重分配 AvailableRenewable，数据会直接退化到零购电/零碳。
3. Q2 的能源感知应优先利用**实际逐时边际能源状态**，尤其是 Curtailment，而不是依据 E/F 的文字标签虚构新能源空间互补。
4. 任务柔性排序有非常强的数据依据：RT << Batch/Training；Training 又具有最大资源重量。
5. 当前完整合法域规模约 2.33e8，确实需要 SFETA 这类结构化构造算法，但合法域本身不得人为截断。

### 仍需复核后才能冻结

1. Q2 能源层的正式“基准状态冻结”口径：哪些 baseline energy columns 固定，迁移后哪些量重算；必须与题目/附件再对齐。
2. Q2 是否允许把 SellPrice/GridSell 纳入运行成本，以及是否允许调用 `storage_information.xlsx` 的 MaxGridExport/SellLimit。附件表格显示 storage_information 主要属于 Q3/Q4，因此目前不把售电机会成本作为 Q2 已冻结项。
3. Cost 与 Carbon 的目标组织：数据已经显示若采用错误的全新能源重分配口径，两者同时退化；在正确的边际能源状态口径下，应先计算真实的 cost/carbon 极值与冲突程度，再决定 lexicographic / epsilon-constraint / 单目标+评价指标。

## 5. 对编程实现的要求

正式实现 Q2 前，应先编写可重复的数据探针脚本，至少输出：

- 各 region-hour 的 Curtailment、GridToLoad、BuyPrice、CarbonIntensity、AvailableRenewable；
- 六区逐时 renewable/cutailment 空间差异；
- 三类任务的 `|R_i|`、合法 start 数、slack、GPU-hour、完整候选数；
- “完全新能源重分配”退化探针与“固定基准能源背景”边际探针分开报告，禁止混为同一模型结果。
