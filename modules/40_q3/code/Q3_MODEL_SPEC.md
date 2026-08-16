# Q3 正式模型规范：固定负荷下的 BESS 储能—新能源协同经济调度

状态：`DRAFT / NEEDS_REVIEW`

## 0. 模型定位

问题三不重新调度任务。固定输入为：

`L[r,t] = PUE[r] * (Baseline_AI_IT_Load_MW[r,t] + NonAI_IT_Load_MW[r,t])`。

只优化能源侧：

- 新能源直接消纳；
- 新能源充电；
- 电网充电；
- 储能放电；
- 电网供负荷购电；
- 新能源外送/售电；
- 弃电；
- SOC。

主问题属于连续多时段 **Battery Energy Storage System (BESS) optimal dispatch / economic dispatch**。当前不自造新的模型缩写。

Q3 主要回答：在完全相同的固定计算负荷下，如何通过 BESS 与新能源/电网能量分配降低运行成本，并分析其对碳排放、区域峰值净购电和电网交互波动的影响。

建模创新不来自把标准 LP 换成更复杂对象，而来自附件数据的新能源盈余结构。正式建模顺序必须先分析 `H[r,t]=AvailableRenewable[r,t]-L[r,t]`，再建立统一 LP；详见 `Q3_DATA_STRUCTURED_REFINEMENT.md`。

---

## 1. 时域与固定负荷

`t = 0,...,2406`，`Delta t = 1 h`。

- 0--2399：主运行时域；
- 2400--2405：无新任务但固定附件 Baseline AI 尾部负荷仍存在；
- 2406：AI 负荷为 0，只保留 NonAI 负荷以及终端电力/储能结算。

所有 Q3 能源流、成本和碳排均按 0--2406 真实小时结算；禁止通过 Hour 2406 免费补 SOC。

### 1.1 数据结构先验：新能源盈余

定义：

`H[r,t] = AvailableRenewable[r,t] - L[r,t]`。

当前数据探针：

- RegionA/B/C/D/E：全部时段 `H>=0`；
- RegionF：仅 1 个小时 `H<0`；
- 六区总可用新能源约为总设施负荷的 1.74--1.81 倍。

结合 SellLimit，形成三类题目特化机制：

1. A/B/C：持续新能源盈余 + 不允许售电；
2. D/E：持续新能源盈余 + 允许售电；
3. F：新能源盈余为主 + 单次短缺 + 允许售电。

统一 LP 对六区保持同一数学形式，但结果分析必须按这三类机制解释，不能预设六区同一种充放电模式。

在当前成本主目标下，A/B/C 存在 `GridPurchase=0, GridSell=0, qR=qG=d=0` 的可行零成本解；Stage 2 最小吞吐量应选出零储能动作。该结论是数据结构与目标共同导出的结构性结果。

D/E 的储能主要用于新能源跨时段价值转移；F 还承担唯一新能源短缺小时的购电替代。局部边际价格判据只用于解释时序，不作为新的硬约束。

---

## 2. 决策变量

对 Region `r`、Hour `t`：

- `u[r,t]`：直接满足设施负荷的新能源功率；
- `qR[r,t]`：新能源充电功率；
- `qG[r,t]`：电网充电功率；
- `d[r,t]`：储能放电功率；
- `gL[r,t]`：电网直接供负荷功率；
- `s[r,t]`：新能源外送/售电功率；
- `w[r,t]`：弃电功率；
- `E[r,t]`：小时末 SOC。

派生量：

- `GridPurchase = gL + qG`；
- `ChargePower = qR + qG`；
- `NetGridImport = GridPurchase - s`。

由于附件把 `GridSell_MW` 定义为“新能源富余外送或售电”，主模型不允许把网购电或储能放电直接作为售电来源。

---

## 3. 能量守恒

### 3.1 新能源分配

`AvailableRenewable[r,t] = u[r,t] + qR[r,t] + s[r,t] + w[r,t]`。

### 3.2 固定设施负荷供能

`L[r,t] = u[r,t] + d[r,t] + gL[r,t]`。

### 3.3 电网购电与充电分解

`GridPurchase[r,t] = gL[r,t] + qG[r,t]`。

`ChargePower[r,t] = qR[r,t] + qG[r,t]`。

以上分解与附件 baseline 在全时域误差约 `1e-4 MW` 内一致，优先于只写一条难以追踪能源来源的总平衡式。

---

## 4. SOC 动态与储能边界

初态：

`E[r,-1] = InitialSOC[r]`。

递推：

`E[r,t] = E[r,t-1] + eta_c[r]*(qR[r,t]+qG[r,t])*Delta t - d[r,t]/eta_d[r]*Delta t`。

约束：

`MinSOC[r] <= E[r,t] <= StorageCapacity[r]`；

`0 <= qR[r,t] + qG[r,t] <= MaxChargePower[r]`；

`0 <= d[r,t] <= MaxDischargePower[r]`；

终端：

`E[r,2406] >= InitialSOC[r]`。

原附件 `SOC_MWh` 仅作为 baseline 对照，不作为 Q3 优化初态。

---

## 5. 购售电边界

`0 <= GridPurchase[r,t] <= MaxGridImport[r]`。

`0 <= s[r,t] <= min(SellLimit[r], MaxGridExport[r])`。

A/B/C 的 SellLimit=0，因此无外送；D/E/F 允许有限新能源外送。

### 5.1 局部边际解释，不新增约束

对于 D/E，若 t 时刻 1 MWh 新能源直接售电的价值为 `SellPrice[t]`，而先储能再在未来 tau 时刻释放，忽略局部容量绑定时其有效未来售电价值近似为：

`eta_c * eta_d * SellPrice[tau]`。

因此 `eta_c*eta_d*SellPrice[tau] > SellPrice[t]` 可用于解释为什么某些低价值时段充电、高价值时段放电。

对于 F 的唯一新能源短缺时段 tau，放电还可以避免未来购电，因此局部比较可写成：

`eta_c * eta_d * BuyPrice[tau] > SellPrice[t]`。

这些不等式只作为结果机理解释。正式策略仍由统一 LP 在 SOC、功率、GridImport/Export 等全部约束下决定。

---

## 6. 主目标：运行成本最小

题目要求“设计储能充放电策略并分析其对多个指标的影响”，并未要求四指标同时进入优化目标。为避免人为权重，Q3 主目标先采用标准 economic dispatch：

`min Cost = sum_{r,t} [ Price[r,t]*(gL[r,t]+qG[r,t]) - SellPrice[r,t]*s[r,t] ] * Delta t`。

碳排、峰值净购电和负荷波动作为同一调度方案上的评价量重新计算，不强行加入 `w1*Cost+w2*Carbon+w3*Peak+w4*Fluctuation`。

数据探针已显示：当前附件新能源极充足，自由分配后 GridPurchase 几乎可降为 0，因此 Carbon 作为主目标会明显退化；Q3 不为制造 Pareto 前沿而人为增加权重。

---

## 7. 多重最优的物理解：两阶段字典序 LP

主成本 LP 可能存在多重最优，数值求解器偶尔会返回同小时充放电的零经济收益循环。

因此采用两阶段连续 LP：

### Stage 1

求 `Cost* = min Cost`。

### Stage 2

在 `Cost <= Cost* + tolerance` 下最小化：

`Throughput = sum_{r,t} [ qR[r,t] + qG[r,t] + d[r,t] ] * Delta t`。

该 tie-break 只从成本等价解中选择储能动作更少的物理解，不引入电池退化成本参数，也不改变主经济目标。

小探针已经显示：纯成本 LP 出现大量 simultaneous charging/discharging，而 Stage 2 可在成本数值不变的条件下将 SCD 降为 0，并使 A/B/C 的吞吐量变为 0。

若 Stage 2 后仍出现显著同小时充放电，再参考 energy-storage complementarity exact-relaxation/penalty；仍失败才升级带 charge/discharge binary 的 MILP。

可选 Stage 3：若最终篇幅允许，可在 Cost 与 Throughput 均保持最优的集合中进一步最小化 NetGridImport 的 L1 ramp，只作为等价解代表选择。当前探针显示主要收益只在 RegionF，因此不是主模型必需部分。

---

## 8. 评价指标

### 8.1 运行成本

`Cost` 使用主目标公式。

### 8.2 碳排放

严格按附件：

`Carbon = sum GridPurchase[r,t] * CarbonIntensity[r,t] * Delta t`。

### 8.3 区域峰值净购电功率

定义净购电：

`N[r,t] = GridPurchase[r,t] - s[r,t]`。

由于 N 可以为负（净外送），区域“峰值净购电”采用正部：

`PeakImport[r] = max_t max(N[r,t],0)`。

### 8.4 负荷波动与电网交互波动

Q3 固定 Facility Load，因此计算设施负荷本身的波动在优化前后不变，变化率应明确报告为 0。

储能真正能够改变的是电网交互功率 `N[r,t]`。因此另报告：

`SigmaGrid[r] = sqrt( (1/T) * sum_t (N[r,t]-mean(N[r,:]))^2 )`。

必要时附加平均绝对爬坡：

`MeanRamp[r] = (1/(T-1))*sum_t |N[r,t]-N[r,t-1]|`。

正文必须把它称为“电网交互功率波动”，不能静默替换题面的 Facility Load 波动。

### 8.5 新能源利用率

虽 Q3 原问未列为四个核心影响指标，但附件要求 Q2--Q4 统一重算：

`eta_R = sum(u + qR + s) / sum(AvailableRenewable)`。

---

## 9. 三层对照：不得把新能源重新分配收益全部归因于储能

必须同时给出：

### B0：附件 baseline

直接使用附件基准结果，只作 raw reference。注意 D/E/F 的基准 `SOC(2406)<InitialSOC`，因此 B0 不是 Q3 终端约束下的可行优化点。

### E0：无储能能源调度

固定同一负荷和全部能源参数，允许新能源直接消纳/售电/弃电以及电网供负荷，但设：

`qR=qG=d=0`。

从 `H` 的角度，E0 表示每个小时的新能源盈余只能当期售电或弃电，不能跨时段搬移。

### E1：BESS 协同调度

使用完整 Q3 模型。E1 相比 E0 额外释放的是储能跨时段搬移能力。

储能增量价值统一定义为 `E1 - E0` 的指标变化；`E1 - B0` 只能称为整体能源策略优化效果。

---

## 10. 六区域分解

当前主目标为区域成本之和，约束中不存在跨区域电力交换、共享储能或系统级耦合项，因此：

`min sum_r Cost_r = sum_r min Cost_r`。

主 Q3 可分解为 6 个独立的区域 LP，并在结果层汇总系统指标。

如果后续人为加入“全系统统一碳预算”或“系统最大峰值”等跨区域约束，则该分解性质消失；Q3 当前不增加此类结构，把跨区域联合权衡留给 Q4。

---

## 11. 时间展开能量网络表示（可选）

可把同一 LP 画成 `time-expanded energy-flow network`：

- Renewable 在每个小时流向 Load / Battery / Sell / Curtailment；
- Grid 流向 Load / Battery；
- SOC 构成跨时段能量传递弧。

该表示用于解释“储能协同”与跨时段能源搬移，不改变可行域、目标和求解器，也不作为创新来源。是否进入正文取决于 Q4 篇幅。

---

## 12. 当前不加入的复杂机制

- 不重新优化任务迁移/开工；
- 不使用 SFETA；
- 不引入负荷/新能源预测，因为题目给出实际 0--2406 逐时参数；
- 不做 stochastic programming / DRO / MPC；
- 不加入电池退化成本，因为附件没有寿命、循环成本、SOH 参数；
- 不建线路潮流；
- 不为了禁止同时充放电直接升级 MILP，先用成本最优后的最小吞吐量 tie-break。

---

## 13. 当前必须验证的结果门禁

1. 固定负荷 `L = PUE*(BaselineAI+NonAI)` 全时域一致；
2. 新能源分配、负荷供能、GridPurchase、ChargePower 四组平衡逐时残差 < tolerance；
3. SOC 初态从 `InitialSOC` 开始，终端 `SOC(2406)>=InitialSOC`；
4. SOC、充放电功率、GridImport、GridExport 全部不越界；
5. Stage 2 后同小时充放电为 0（容差内）；
6. GridSell 只来自新能源分配；
7. Cost/Carbon/NetGridImport/eta_R 全部从优化变量重新计算；
8. B0/E0/E1 三层结果同时输出；
9. 关键结论只把 `E1-E0` 解释为“储能贡献”；
10. `H` 与 SellLimit 导出的 A/B/C、D/E、F 区域角色必须与正式解一致；若不一致则回查局部绑定约束，不能强行套机制解释。

---

## 14. 当前判断

Q3 不需要新造复杂模型。最合适的结构是：

**新能源盈余结构识别 + 固定数据中心负荷 + 可再生能源/电网能量流分配 + BESS 多时段 SOC 约束 + 成本经济调度 + 无储能消融对照。**

数学上主体仍是连续线性规划；数据上的主要特点是新能源极充足导致 Carbon/PeakImport 退化，以及 A/B/C、D/E、F 三类不同的储能角色。
