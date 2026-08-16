# 第9题终极数据审计（DS-REPTA 共用输入）

状态：`DRAFT / NEEDS_REVIEW`

本文件只记录六份官方 Excel 的统计结构、字段依赖和对后续算法的直接后果。正式论文中的关键数值仍需在当前仓库代码复算后登记到各问 `results/registry.csv`，本文件不替代 FROZEN/CHECKED 结果。

## 1. 数据规模与时间轴

- `workload_trace.xlsx`：50,000 个任务，ArrivalHour 完整覆盖 0--2399。
- `region_time_data.xlsx`：6 区域 × 2407 h = 14,442 行；其中 0--2399 为主运行时域，2400--2406 为收尾/终端结算时域。
- 题目建议的预测划分：0--2351 参数估计，2352--2375 模型选择/调参，2376--2399 独立预测评价。
- 三段到达任务数分别为 48,963、499、538。
- 第 2376--2399 h 的 538 个实际任务中，AITraining 194、BatchInference 184、RealTimeInference 160；若全部到达即开工，有 68 个任务跨越第 2399 小时进入收尾时域。

## 2. 工作负载到达：近似平稳 Poisson，不支持复杂时序黑箱

### 2.1 小时任务数

对 0--2399 h 的小时任务数统计：

- 均值：20.8333 tasks/h；
- 方差：20.1815；
- Fano 因子 Var/Mean = 0.9687；
- 最小/最大：8 / 36 tasks/h；
- 离散度检验双侧 p = 0.2777；
- Poisson 分布拟合卡方检验 p = 0.7942；
- “2400 个小时等到达率”检验 p = 0.8612。

自相关：

- lag 1：-0.0035；
- lag 24：-0.0422；
- lag 168：0.0357。

按时刻统计：

- 24 个小时段的到达率差异检验 p = 0.2925；
- 按实际星期暴露小时数修正后，7 天到达率差异检验 p = 0.9973。

GPU 到达需求序列的相关性更弱：lag 24 = -0.0012，lag 168 = 0.0033。

**算法后果：** Q1 的预测优先采用分层标记/复合 Poisson 模型。当前数据没有显示可供 LSTM 学习的稳定 24 h、168 h 或短期记忆结构。

### 2.2 简单预测对照

以 2352--2375 为模型选择区间、2376--2399 为独立测试区间，对“每小时总 GPU 到达需求”比较：

- 全历史均值：测试 WAPE = 24.30%；
- 按小时日周期均值：24.54%；
- t-24 季节朴素：36.92%；
- t-168 季节朴素：35.81%。

验证区间中日周期均值只比全历史均值好约 0.02 个百分点，独立测试时反而略差，说明该差异主要来自样本波动，不能据此宣称存在稳定日周期。

## 3. 任务类型是最强解释变量

### 3.1 数量与算力贡献

| TaskType | 任务数 | 数量占比 | GPU 范围 | GPU-hour 占比 | 按 power_mapping 计 AI IT 能量占比 |
|---|---:|---:|---:|---:|---:|
| AITraining | 16,559 | 33.118% | 16--127 | 80.14% | 87.12% |
| BatchInference | 16,717 | 33.434% | 4--23 | 15.32% | 10.41% |
| RealTimeInference | 16,724 | 33.448% | 1--7 | 4.54% | 2.47% |

三类任务数量几乎各占 1/3，但训练任务贡献约 80% GPU-hour、87% AI IT 能量。因此后续调度的主要可控对象应是 AITraining，而不能按任务数平均对待三类任务。

### 3.2 GPU 与时长分布

- AITraining GPU 需求在 16--127 上与离散均匀分布相容，p = 0.6379；
- BatchInference 在 4--23 上，p = 0.7728；
- RealTimeInference 在 1--7 上，p = 0.7644。
- 三类 Duration 均为 10--399 min，离散均匀性检验 p 分别为 0.6819、0.8201、0.7691。
- 三类平均 Duration 分别为 204.51、204.21、203.93 min，类型差异检验 p = 0.8955。
- GPU_Demand 与 Duration 的相关系数分别约 0.0004、-0.0017、-0.0043。
- ArrivalHour 与 GPU_Demand/Duration 的 Spearman 相关均接近 0。

**算法后果：** GPU 需求主要由 TaskType 决定；Duration 可以作为与 GPU 规模近似独立的任务标记处理，不需要额外的高维预测器。

## 4. TaskType 与 SourceRegion 强相关

类型 × 区域列联检验：Cramér's V = 0.4337，p 近 0，说明任务类型与来源区域存在强结构关系。

条件比例：

- AITraining：D 34.58%，E 24.71%，F 25.22%，A/B/C 各约 5%；
- RealTimeInference：A 34.99%，B 30.00%，C 25.24%，D/E/F 合计约 9.77%；
- BatchInference：A/B/D 各约 20%，C 15.09%，E 12.99%，F 12.16%。

按 GPU-hour 看，D/E/F 的原始负荷中 AITraining 占比分别约 89.6%、90.0%、91.4%；A/B/C 训练占比约 47.8%、49.3%、52.9%。

**算法后果：** Q1 统计和预测应至少保留 `TaskType × SourceRegion` 的 18 个子流；Q2/Q4 则可利用“东部实时、D/E/F 训练”结构构造任务优先级。

## 5. SLA 与时间窗把任务柔性分成三层

字段规则经逐行核对：

- `EarliestStartHour = ArrivalHour` 对 50,000 个任务全部成立；
- `ExecutionMode = NonPreemptive` 全部成立；
- RealTimeInference：MaxLatency = 20 ms，且 `LatestFinish = Arrival + ceil(Duration/60)`，因此整数小时开工时刻只有 ArrivalHour 一个；
- BatchInference：MaxLatency = 80 ms，LatestFinish 全部为 2406；
- AITraining：MaxLatency = 150 ms，LatestFinish 全部为 2406。

按整数小时候选开始时刻计算：

- RealTimeInference：每任务恰好 1 个开始时刻；
- BatchInference：平均 1206.60 个，median = 1208；
- AITraining：平均 1195.52 个，median = 1185。

## 6. 网络时延矩阵：可行域可在优化前大幅剪枝

时延矩阵对称。按 SLA 阈值：

### 20 ms（RealTimeInference）

- A/B/C 构成互联块；
- D 只能留在 D；
- E/F 可相互迁移。
- 36 个区域对中仅 14 个可行。
- 按任务来源加权后，每个实时任务平均只有 2.873 个可执行区域。

### 80 ms（BatchInference）

- 36 个区域对中 34 个可行；仅 A↔F 两个方向被排除。
- 每任务平均可执行区域数 5.679。

### 150 ms（AITraining）

- 36/36 全部可行；每任务均有 6 个候选区域。

结合时间窗后，如果对所有任务显式建立 `(region,start)` 二元变量，候选规模约为：

- AITraining：118,779,696；
- BatchInference：114,547,455；
- RealTimeInference：48,050；
- 合计：233,375,201 个候选组合。

**算法后果：** 直接构造全时域 MILP 变量集没有必要。DS-REPTA 必须先按 SLA、LatestFinish 和资源容量做候选域压缩，再进行边际代价排序和冲突修复。

## 7. 电力侧时间序列具有强低维结构

### 7.1 AvailableRenewable_MW

- 六个区域逐小时完全相同；
- 24 h 精确重复；
- 单日均值 800 MW，最小 500 MW，最大 1100 MW；
- 24 h 模板解释 100% 时间方差。

因此附件文字虽然把 E/F 分别描述为光伏/风电区，但 `AvailableRenewable_MW` 数值本身没有空间差异，也没有给出两类独立随机新能源过程。正式优化必须服从数值数据，不能自行制造 E/F 的不同曲线。

### 7.2 CarbonIntensity

- 每个区域均满足 168 h 精确周期；
- 区域间相关系数均约 0.999996 以上；
- 六区域矩阵第一主成分解释 99.9999% 以上的时间方差；
- 24 h 模板可解释约 87.64%，168 h 模板解释 100%。

### 7.3 ElectricityPrice

- 六区域时间曲线相关系数在数值精度内约等于 1；
- 六区域矩阵第一主成分解释 99.99999997% 的时间方差；
- RegionA 到其他区域几乎可由一个固定比例缩放得到，线性回归 R² 均 > 0.999999999；
- 24 h 的峰/平/谷时段模板解释约 99.04% 方差，但价格水平还叠加缓慢公共漂移。

### 7.4 NonAI_IT_Load

NonAI 不是完全确定周期，但日周期很强：

- A/B/C 的 24 h 模板 R² 约 92.6%--93.1%；
- D/E/F 约 81.7%--86.7%；
- 六区域共同第一主成分解释约 88.7% 方差。

**算法后果：** 168 h rolling horizon 有明确数据依据：它同时完整覆盖 7 个新能源 24 h 周期和 1 个碳强度 168 h 周期，并能覆盖 NonAI 的主要日周期结构。

## 8. 区域价格与碳强度存在稳定偏序

0--2399 h 每一个小时，无论是否乘 PUE，区域排序始终为：

`RegionE < RegionF < RegionD < RegionC < RegionB < RegionA`

该排序对电价与碳强度同时成立。

主时域平均 PUE 修正后指标：

| Region | PUE×平均电价 | PUE×平均碳强度 |
|---|---:|---:|
| A | 956.00 | 0.8373 |
| B | 916.17 | 0.7833 |
| C | 909.38 | 0.7593 |
| D | 541.34 | 0.5378 |
| E | 467.18 | 0.2751 |
| F | 499.64 | 0.3303 |

RegionA 内：

- corr(price, carbon) = -0.3778；
- corr(price, renewable) = -0.1543；
- corr(carbon, renewable) = -0.6627；
- corr(NonAI load, price) = -0.7523；
- corr(NonAI load, renewable) = 0.5047。

因此“最低电价时段”和“最低碳/高新能源时段”并不完全重合，多目标冲突主要来自时间选择、时延/容量以及新能源售电机会成本，而不是区域成本和区域碳排序互相反转。

## 9. SellPrice 与新能源机会成本

- A/B/C：SellPrice 恒为 0，不具备外送能力；
- D/E/F：SellPrice / BuyPrice ≈ 0.78，全部 2400 h 成立；
- 售电上限：D 180 MW，E/F 220 MW。

因此新增 1 MW 算力负荷的能源机会成本应区分：

1. 消纳原本弃掉的新能源：边际电费 0；
2. 挤占原本可售新能源：边际代价约等于 SellPrice；
3. 需要新增电网购电：边际代价等于 BuyPrice。

这应成为 DS-REPTA 相对原始 REPTA 的主要数据修正之一。

## 10. 基准结果字段可以由原始任务与参数精确复算

逐小时复算表明：

- `Baseline_AI_IT_Load_MW` 与“所有任务在 SourceRegion 到达即开工、按实际重叠时长 × power_mapping”计算结果最大误差约 3.4e-7 MW；
- `AITrainingPower_MW` 可由 AITraining 子集同样精确复算；
- `GPU_Utilization_Percent = GPU_hour_occupancy / Available_GPU × 100%`，误差约 1e-6 量级；
- `IT_Load = Baseline_AI_IT_Load + NonAI_IT_Load`；
- `Total_Load = IT_Load × PUE`；
- `AvailableRenewable = UsedRenewable + RenewableCharge + GridSell + Curtailment`；
- `ChargePower = RenewableCharge + GridCharge`；
- `Total_Load = UsedRenewable + (GridPurchase - GridCharge) + DischargePower`；
- `NetGridImport = GridPurchase - GridSell`；
- `CarbonEmission = GridPurchase × CarbonIntensity`。

上述等式除附件保留小数造成约 1e-4 量级误差外逐点成立。

**算法后果：** `AITrainingPower_MW`、`GPU_Utilization_Percent`、`IT_Load_MW`、`Total_Load_MW`、购售电、SOC 等大量列属于基准派生状态/结果，不能当作独立外生变量重新输入 Q2/Q4。

## 11. Baseline 容量状态：主要紧约束是 GPU，不是 IT/设施功率

到达即开工的基准任务形成的 GPU-hour 占用：

| Region | Available_GPU | 基准最大 GPU-hour/h | GPU 超容量小时数 | IT/设施功率超限小时数 |
|---|---:|---:|---:|---:|
| A | 630 | 618.87 | 0 | 0 |
| B | 585 | 590.20 | 1 | 0 |
| C | 540 | 593.82 | 3 | 0 |
| D | 1472 | 1475.33 | 1 | 0 |
| E | 1012 | 1370.80 | 12 | 0 |
| F | 966 | 1309.73 | 27 | 0 |

共 44 个区域-小时发生 GPU 超限，而 IT/设施功率均未超上限。

最后 24 h 的立即执行状态中，只有 RegionF 出现 3 个 GPU 超限小时。

## 12. 新能源充裕程度远高于基准设施负荷

主时域 6×2400 个区域-小时全部满足：

`AvailableRenewable_MW > Baseline Total_Load_MW`

各区域最小裕量：

- A 10.60 MW；B 13.53 MW；C 13.54 MW；
- D 52.89 MW；E 57.35 MW；F 49.21 MW。

附件定义的系统级基准新能源利用率：

`(UsedRenewable + RenewableCharge + GridSell) / AvailableRenewable = 32.74%`

其中直接消纳仅约 19.03%；主时域累计弃电约 7.748×10^6 MWh。

基准运行仍大量购电，因此基准是有意保留优化空间的参考状态，不能把其新能源分配策略解释为必要物理结果。

## 13. 零购电可行性探针：Q2 的碳目标存在退化风险

进行了一个仅用于结构诊断的贪心可行性探针：

- 所有任务保持 SourceRegion，不做跨区迁移；
- RealTimeInference 到达即执行；
- Batch/Training 只在 GPU/IT/Facility/直接新能源约束不满足时向后延迟；
- 不使用储能；要求每小时 FacilityLoad <= AvailableRenewable，即 GridPurchase = 0。

结果：

- 50,000 个任务全部可行；
- 33,276 个弹性任务中仅 80 个需要延迟；
- 68 个延迟 1 h，12 个延迟 2 h，最大延迟 2 h；
- 延迟任务：AITraining 61、BatchInference 19；
- 主要发生在 F 52 个、E 24 个，其余区域仅 4 个。

该结果是可行性探针，不是 Q2 最优解。但它证明在附件数值下，`GridPurchase = 0` 的任务调度可行域存在，因此若碳排仅按 `GridPurchase × CarbonIntensity` 计算，纯碳目标可以直接达到 0。

**算法后果：** Q2 不能把“最小碳排”当作唯一有区分度目标。运行成本会通过 D/E/F 的售电机会成本继续区分方案；新能源利用率与售电收益之间也可能产生真实冲突。

## 14. Baseline 能源指标（0--2399 h，仅作比较基线）

- 系统基准运行成本约 1.802×10^9 CNY；
- 基准碳排约 2.045×10^6 tCO2；
- 可用新能源累计 1.152×10^7 MWh；
- 新能源利用率约 32.74%；
- 累计弃电约 7.748×10^6 MWh。

这些是附件基准运行状态的复算统计，不代表优化结果。

## 15. 储能数据一致性检查

SOC 递推按附件公式

`SOC(t)=SOC(t-1)+eta_c*ChargePower(t)-DischargePower(t)/eta_d`

检查结果：

- RegionA/B/C/D/F 全时域递推误差仅为舍入量级；
- RegionE 的 Hour 0 存在约 1.000 MWh 单点不一致：按 InitialSOC=370 MWh、ChargePower=116.3126 MW、eta_c=0.94 推得约 479.3338 MWh，而表中 SOC(0)=478.3339 MWh；从 Hour 1 起递推重新一致。

`NEEDS_REVIEW`：RegionE Hour 0 可能是基准数据的单点录入/生成偏差。Q3/Q4 应严格使用 `storage_information.xlsx` 的 InitialSOC_MWh 作为唯一初态，不反推修正官方原表。

另外，基准 SOC(2406) 中 D/E/F 分别约 225.98、217.25、189.18 MWh，低于各自 InitialSOC 405、370、382.5 MWh。题目要求优化结果满足 SOC(2406) >= InitialSOC，因此基准储能状态本身不能直接作为 Q3/Q4 的可行终端策略。

## 16. 对统一 DS-REPTA 的直接结论

1. **Q1 预测：** 分层标记复合 Poisson，参数估计/模型选择/独立测试按题目时间表执行；不采用 LSTM 作为默认路线。
2. **Q1/Q2/Q4 任务层：** 先利用任务类型、SLA、LatestFinish 和区域容量生成稀疏候选域；训练任务是主要调节对象。
3. **Q2 边际代价：** 不能只看电价和新能源绝对值，应引入“弃电 0 / 挤占售电 SellPrice / 新增购电 BuyPrice”的状态依赖机会成本。
4. **Q2 目标：** 碳排可能退化到 0，需要把运行成本、时延、服务质量和新能源利用率作为区分策略的主要评价量。
5. **Q3：** 仍属于 DS-REPTA 的能源响应模式；任务层冻结，能源状态方程精确求解。
6. **Q4：** 24 h 新能源 + 168 h 碳周期支持 168 h rolling horizon；是否引入 Benders 需由小规模精确模型对照决定。
7. **跨问统一接口：** `task decisions -> GPU occupancy -> AI IT load -> IT load -> facility load -> renewable/grid/storage -> cost/carbon/peak`。

## 17. 建议优先可视化

1. `TaskType × SourceRegion`：任务数与 GPU-hour 双热图；
2. 三类任务 GPU / Duration 分布；
3. 小时任务数与 GPU 到达量 + ACF；
4. 20/80/150 ms 三层网络时延可行图（WiFi/信号强度风格）；
5. 24 h Renewable、168 h Carbon、PricePeriod 的时间结构；
6. 六区域 PUE 修正电价/碳强度固定偏序；
7. Baseline GPU 利用率与超容量小时；
8. 新能源可用量 vs FacilityLoad 裕量与基准弃电；
9. 0--2351 / 2352--2375 / 2376--2399 / 2400--2405 / 2406 总时间轴。
