# Q2 数据结构驱动论文强化要求（2026-08-18）

## 0. 目的

Q2 的模型已经大量使用附件真实结构，但当前论文呈现仍偏“算法驱动”。本轮不改模型，不加新目标，不加权；重点把真正支撑 SFETA 和 Cost/Carbon 组织方式的数据关系显式写进正文，并补成可见的数据图。

正式主线必须是：

`任务柔性结构 -> 基准能源矛盾 -> 分段边际能源响应 -> 完整合法域 SFETA -> Cost/Carbon 端点 -> 服务代价`。

---

## 1. 必须提升为正文核心的数据发现

### R1 附件基准同时存在大量弃电与供负荷购电

0--2399 h 共 14,400 个 region-hour：
- `Curtailment>0`：14,400 / 14,400；
- `GridToLoad>0`：13,230 / 14,400；
- 同时弃电且供负荷购电：13,230 / 14,400，约 91.9%。

累计：
- Curtailment ≈ 7,748,360.94 MWh；
- GridToLoad ≈ 4,028,324.59 MWh；
- baseline AI facility energy ≈ 950,773.63 MWh；
- Curtailment / AI facility energy ≈ 8.15。

**论文作用：**这是 Q2 为什么有必要做时空迁移的最强数据证据。不能只写“新能源有弃电”，必须写出“弃电和购电在绝大多数 region-hour 同时存在”，说明附件基准存在明显的时空错配。

**模型作用：**支撑“先吸收基准弃电、再改变购电”的分段边际能源响应。

### R2 六区域 AvailableRenewable 逐时完全相同，但基准 Curtailment 空间差异巨大

数据事实：同一小时六区 `AvailableRenewable` 最大差值为 0；而六区 Curtailment 的小时极差中位数约 443.30 MW，最大约 580.52 MW。

**论文作用：**必须强调不能按“E/F 新能源区”文字标签直接给任务加绿色评分。真实空间机会来自 `PUE + load + baseline energy state` 形成的可用弃电，而不是原始新能源出力空间差。

**模型作用：**支撑动态 marginal energy state，而不是静态 RegionRole score。

### R3 弃电时段天然带有低碳属性

各区域 `corr(Curtailment, CarbonIntensity)` 约 -0.690 至 -0.849；`corr(Curtailment, AvailableRenewable)` 约 0.925--0.995。

**论文作用：**解释为什么“优先吸收弃电”本身已经具有 carbon-aware 属性，不需要人为为新能源、碳、成本再设置权重。

### R4 Cost 与 Carbon 在新增购电区总体同向但不完全一致

全体 region-hour：Price 与 CarbonIntensity Pearson ≈ 0.578，Spearman ≈ 0.613；PUE 调整后仍为中等正相关。RegionE 在 2400/2400 h 的 `PUE*BuyPrice` 和 `PUE*CarbonIntensity` 上均处于最低/非支配位置。

**论文作用：**支撑“Cost-primary + Carbon-primary 对照端点”，而不是 Cost/Carbon 人工加权和。

### R5 三类任务柔性差异极强

RT：start 固定、SLA 合法区域 1--3；Batch：5--6 区、slack 中位数约 1207 h；Training：6 区全部开放、slack 中位数约 1184 h，GPU-hour 中位数约 194.35，贡献约 80.14% GPU-hour、约 87.12% AI IT 能量。

**论文作用：**排序键 `|R_i| 小 -> slack 小 -> GPU-hour 大` 必须明确是数据结构推导，不是人工综合评分。

### R6 完整合法域约 2.33375201e8 placements

**论文作用：**说明为什么不能显式 MILP 展开，也为什么 SFETA 必须在隐式完整域上做结构化扫描；同时强调“不截断合法域”是严谨性选择。

---

## 2. 当前正文必须补强的 Data-to-Model 解释

### 2.1 在“能源层分析”开头新增一个“小结论框”

建议正文直接形成：

`91.9% region-hour 同时弃电+购电 -> 任务负荷与绿色能源时空错配 -> Q2 仅释放 workload 时空柔性 -> 用迁移/延迟吸收弃电`。

这段应先于公式 `DeltaG` 出现。

### 2.2 把“AvailableRenewable 六区相同”提升为反直觉数据发现

不是一句附带说明。必须解释：题面角色标签不能替代数值数据；空间差异由 Curtailment、PUE、负荷、电价/碳形成。

### 2.3 把 Cost/Carbon 端点组织与相关结构直接关联

正文应明确：
- 弃电吸收区：Cost/Carbon 边际增量都近 0；
- 新增购电区：Price 与 CarbonIntensity 总体同向但不完全相同；
- 因此主方案 Cost-primary、Carbon-primary 做独立对照，不加权。

### 2.4 把极端等待解释为“数据给出的长 slack 被能源目标利用”

2016 h 最大等待不是 bug；必须和 Batch/Training 千小时级 slack 的数据结构并列解释，而不是只在结果后道歉式说明。

---

## 3. 必补主图

### 主图 Q2-A：基准能源错配证据图（P0）

建议三面板或复合图：
- (a) 六区/系统 `Curtailment` 与 `GridToLoad` 同时发生比例；明确标注 `13230/14400=91.9%`；
- (b) 累计 Curtailment、GridToLoad、AI facility energy 对比，突出 `Curtailment / AI facility energy ≈ 8.15`；
- (c) 若空间允许，显示六区域 Curtailment 分布/均值或小时极差，旁注 AvailableRenewable 六区逐时相同。

这张图的目的不是“展示能源曲线”，而是证明 Q2 的必要性。

### 主图 Q2-B：任务柔性结构三面板（P0）

- (a) 合法区域数 `|R_i|`；
- (b) 真正可调时间自由度（RT 应显示 0，而不是 deadline slack 0.5 h）；
- (c) GPU-hour。

结论：空间/时间刚性与资源重量共同决定处理顺序。

### 主图 Q2-C：分段边际能源响应（P0）

以 `DeltaL` 为横轴，至少展示：
- `DeltaGridPurchase`；
- `DeltaCurtailment`。

标注三个机制区：
1. 新增负荷先吸收弃电；
2. 弃电耗尽后新增购电；
3. 负荷下降先减少原供负荷购电，进一步下降可能增加弃电。

禁止写“负荷下降时弃电和购电同步下降”。

### 主图 Q2-D：弃电—碳强度关系图（P1）

可做六区散点/hexbin 或相关系数条形图：
- `Curtailment vs CarbonIntensity`；
- `Curtailment vs AvailableRenewable`。

目的：用数据说明弃电吸收天然偏低碳。

### 主图 Q2-E：Cost/Carbon/初始化端点图（P1）

散点至少含：Baseline、Cost-primary reference、Carbon-primary reference、Cost previous-start。

目的：同时展示显著改善、Cost/Carbon近同向、初始化路径依赖。不要称 Pareto front。

### 主图 Q2-F：Source -> Execution 迁移矩阵（P1）

用于回答 74.9% 迁移“迁到哪里”，只按真实矩阵解释，不预写某区是承接中心。

---

## 4. 图的降级/删除规则

- Cost柱图与Carbon柱图若已有端点散点，不再各占一张；
- mean/P95/max wait 不在同一线性柱图中画，max=2016 h 会压扁前两者；
- 普通四条全时序若视觉上过密，移附录；
- 不为“图多”重复证明同一 Cost/Carbon 端点关系。

---

## 5. 写作验收

论文读者在看到 SFETA 之前，应该已经知道：
1. 任务柔性差异是什么；
2. 为什么附件中存在巨大的绿色时空错配；
3. 为什么优先利用弃电比 Price/Carbon 加权评分更自然；
4. 为什么 Cost 与 Carbon 只需要主端点 + 对照端点；
5. 为什么 Q2 会出现长等待，并且该问题必须留给 Q4 处理。

如果上述五点只能从代码/数据探针看出来，而正文和图看不出来，本轮不算通过。
