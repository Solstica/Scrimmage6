# Q3 数据探针：固定负荷下的储能与能源分配

状态：`DRAFT / NEEDS_REVIEW`

本文件只记录用于冻结 Q3 数学结构的数据事实。Q3 题面明确固定 `Baseline_AI_IT_Load_MW` 与 `NonAI_IT_Load_MW`，仅优化储能充放电、购售电和新能源分配，不重新优化任务迁移与开工时段。

## 1. 附件能源流恒等式可被精确复现

对 `region_time_data.xlsx` 全部 6×2407 个 Region-Hour 检查：

- `AvailableRenewable = UsedRenewable + RenewableCharge + GridSell + Curtailment`，最大绝对误差约 `2e-4 MW`；
- `Total_Load = UsedRenewable + DischargePower + (GridPurchase-GridCharge)`，最大绝对误差约 `1e-4 MW`；
- `ChargePower = RenewableCharge + GridCharge`，最大绝对误差约 `1e-4 MW`；
- `NetGridImport = GridPurchase - GridSell`，最大绝对误差约 `1e-4 MW`；
- `CarbonEmission = GridPurchase * CarbonIntensity`，最大绝对误差约 `8e-5 tCO2`。

因此 Q3 正式模型优先采用“新能源分配 + 负荷平衡 + 电网购电分解 + SOC”四层守恒，而不是只写一条总功率平衡后再凭经验解释各流向。

## 2. 固定设施负荷与可用新能源的关系非常极端

设施负荷严格取：

`L[r,t] = PUE[r] * (Baseline_AI_IT_Load_MW[r,t] + NonAI_IT_Load_MW[r,t])`。

对 0--2406 h：

| Region | 总可用新能源 / 总设施负荷 | `AvailableRenewable < Load` 的小时数 |
|---|---:|---:|
| A | 1.756 | 0 |
| B | 1.775 | 0 |
| C | 1.745 | 0 |
| D | 1.770 | 0 |
| E | 1.812 | 0 |
| F | 1.782 | 1 |

即除 RegionF 仅 1 个小时外，附件给出的 `AvailableRenewable_MW` 每小时均不低于固定设施负荷。

这意味着：如果 Q3 按题意完全释放新能源直接消纳/充电/外送/弃电分配，则“低碳”几乎会退化为零购电可行问题；不能再把原 baseline 中的大量购电直接解释为不可避免的能源需求。

## 3. 原附件 baseline 不是 Q3 优化约束下的完全可比可行点

按官方 SOC 递推：

`SOC(t)=SOC(t-1)+eta_c*ChargePower(t)-DischargePower(t)/eta_d`。

以 `InitialSOC_MWh` 为 Hour 0 前状态检查：

- A/B/C/D/F 的基准 SOC 递推最大误差均约 `1e-4 MWh`；
- RegionE Hour 0 存在约 `-0.999944 MWh` 的单点不一致；
- 基准终端 `SOC(2406)`：A/B/C 高于 InitialSOC，但 D/E/F 分别约为 `225.98/217.25/189.18 MWh`，低于初始 `405/370/382.5 MWh`。

因此：

1. 正式优化只认 `InitialSOC_MWh` 为初态；
2. 原附件 baseline 仍可作为官方基准运行状态报告；
3. 但不能把它当作满足 Q3 终端 SOC 约束的可行优化解；
4. 对“储能本身的贡献”必须增加同口径的无储能对照，避免把新能源重新分配的收益全部归因于 BESS。

## 4. 必须设置“无储能能源调度”消融对照

为隔离储能价值，建立三层对照：

1. `B0`：附件原始 baseline；
2. `E0`：固定相同负荷、允许新能源/购售电重新分配，但强制 `Charge=Discharge=0`；
3. `E1`：在 E0 的能源分配自由度上加入 BESS 充放电与 SOC 约束。

初步 LP 探针得到：

### E0：无储能、能源分配最优

- A/B/C：购电可降为 0，碳排为 0；
- D/E：购电可降为 0，同时利用正售电价格外送新能源；
- F：仅约 `31.60 MWh` 电网购电，碳排约 `8.85 tCO2`；
- 六区合计运行成本约 `-4.1982e8 CNY`，碳排约 `8.85 tCO2`。

### E1：加入储能后的成本最优

使用主成本目标后再以最小储能吞吐量作字典序 tie-break，可得到无同小时充放电的 LP 解：

- A/B/C：最优解根本不需要使用储能；
- D/E/F：储能主要用于新能源跨时段搬移与售电价格套利；
- F 的唯一新能源不足小时可由储能补齐；
- 六区购电可降为 0，碳排为 0；
- 六区合计运行成本约 `-4.5922e8 CNY`。

因此储能相对于 E0 的新增经济贡献约 `3.94e7 CNY`，而相对于附件 raw baseline 的巨大成本/碳改善大部分来自“重新分配附件给出的充足新能源”，不能全部归因于储能。

该结论必须在论文结果解释中明确区分。

## 5. 区域储能角色并不相同

当前数据支持：

- A/B/C：在自由新能源分配下，固定负荷始终可被当期新能源覆盖，成本最优时 BESS 可不动作；
- D/E/F：允许外送且 SellPrice>0，BESS 有跨时段能源搬移价值；
- D/E/F 的 `SellPrice / BuyPrice` 基本固定在约 `0.78`；
- F 额外具有 1 个新能源不足小时，储能兼具削减购电峰值的作用。

因此 Q3 不应预设“六区同一种充放电模式”，而应由同一个 LP 模型自然产生不同区域策略。

## 6. 价格、碳强度与新能源的时序关系

0--2399 h 内各区域的时间相关结构几乎一致：

- `corr(Price, CarbonIntensity) ≈ -0.378`；
- `corr(CarbonIntensity, AvailableRenewable) ≈ -0.663`；
- `corr(Price, AvailableRenewable) ≈ -0.154`。

如果系统仍需要大量购电，则“低价充电”与“低碳充电”可能存在时间冲突；但在当前附件新能源极充足的条件下，自由新能源分配使 GridPurchase 几乎退化到 0，因此 Q3 没必要为了形式强行建立 Cost--Carbon 加权多目标。

## 7. LP 还是 MILP

附件 baseline 全时域没有出现同小时 `ChargePower>0` 且 `DischargePower>0`。

普通成本 LP 在少量区域会因多重最优返回无经济意义的同时充放电循环；这不是必须上二元变量的证据。初步探针表明：

- 先最小化运行成本；
- 再在成本最优集合内最小化 `sum(ChargePower + DischargePower)`；

即可得到无同时充放电的物理解，同时保持连续线性模型。

因此 Q3 主实现优先采用**两阶段字典序 LP**；只有该 tie-break 仍不能排除非物理解时，才升级少量 MILP 二元互斥约束。

## 8. 当前数据驱动结论

Q3 的核心不应写成“储能把所有购电和碳都降为零”。更准确的分析链是：

`固定数据中心负荷 -> 新能源/电网/外送最优分配 -> 无储能基准 E0 -> 加入 BESS 时序搬移 E1 -> 单独量化储能的增量价值`。

这条三层对照是后续 Q3 模型和结果分析的强制结构。
