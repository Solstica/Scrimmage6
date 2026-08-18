# Q3 数据结构驱动的储能机制细化

状态：`DRAFT / NEEDS_REVIEW`

本文件不替换 `Q3_MODEL_SPEC.md` 的统一 LP，只说明：附件数据中哪些结构可以在建模层面先被识别并利用，从而让 Q3 不停留在“标准 SOC + 成本最小化”的平铺表达。

## 1. 关键状态量：新能源盈余

固定设施负荷：

`L[r,t] = PUE[r] * (Baseline_AI_IT_Load_MW[r,t] + NonAI_IT_Load_MW[r,t])`。

定义新能源盈余：

`H[r,t] = AvailableRenewable[r,t] - L[r,t]`。

数据探针已经确认：

- RegionA/B/C/D/E：全部 2407 个小时 `H[r,t] >= 0`；
- RegionF：仅 1 个小时 `H[F,t] < 0`；
- 六区总可用新能源约为总设施负荷的 1.74--1.81 倍。

因此 Q3 的主要矛盾并不是“新能源长期不足”，而是：

> 大量新能源盈余如何在直接供能、售电、弃电和跨时段储能之间分配。

这应当成为 Q3 模型建立的第一步。

## 2. 数据自然形成三类区域机制

区域不需要人工聚类；由 `H[r,t]` 的符号结构与 `SellLimit` 直接得到三类机制。

### 2.1 A/B/C：持续新能源盈余 + 不允许售电

条件：

- `H[r,t] >= 0` 对所有 t 成立；
- `SellLimit_r = 0`。

在无负电价、终端 SOC 不低于初值的当前题目条件下，存在一个零购电、零售电、零储能动作的可行解：

`u[r,t]=L[r,t]`，`qR=qG=d=s=0`，多余新能源全部进入 `w`。

其运行成本为 0。由于 A/B/C 无售电收益，任何额外储能循环都不能把成本降到 0 以下；Stage 2 最小吞吐量会进一步选择：

`qR*=qG*=d*=0`。

因此 A/B/C 的“储能不动作”不是求解器偶然结果，而是由数据结构与成本目标共同导出的结构性结论。

注意：这里只证明成本最优集合中存在零储能动作解，并由最小吞吐量字典序把它选为代表解；不把该结论错误推广到所有其他目标或外部市场机制。

### 2.2 D/E：持续新能源盈余 + 允许售电

条件：

- `H[r,t] >= 0` 对所有 t 成立；
- `SellLimit_r > 0`。

这两区的 BESS 主要不承担“缺电保障”，而承担新能源的跨时段价值转移。

若在时刻 t 将 1 MWh 新能源直接售出，可获得 `SellPrice_t`；若用于充电，并在未来 tau 时刻放电去替代负荷供能，则大约可以释放 `eta_c*eta_d` MWh 的未来新能源用于售电。

在忽略出口容量、SOC/功率边界等局部约束时，一个简单的边际经济判据为：

`eta_c * eta_d * SellPrice[tau] > SellPrice[t]`。

满足时，新能源从 t 搬移到 tau 具有正的售电价值；不满足时，直接售电更有利。

正式 LP 仍负责处理所有同时存在的容量与 SOC 约束；上述不等式只用于解释最优充放电时序，不作为新的硬约束。

### 2.3 F：新能源盈余为主 + 单次短缺 + 允许售电

F 只有一个小时 `H[F,t] < 0`，因此储能除了与 D/E 类似的售电时移，还多一个明确角色：

> 在唯一新能源不足小时替代电网购电。

若未来短缺时段 tau 的电网购电价格为 `BuyPrice[tau]`，则从早期时段 t 储存 1 MWh 新能源去覆盖该短缺的局部边际判据可写为：

`eta_c * eta_d * BuyPrice[tau] > SellPrice[t]`。

左侧表示未来避免购电的有效价值，右侧表示现在放弃直接售电的机会成本。

同样，该判据用于结果解释；真正最优策略仍由完整 LP 决定。

## 3. B0/E0/E1 因此不再是人为消融

### B0：附件 raw baseline

只作为附件给定的运行状态参考。其 D/E/F 终端 SOC 低于 InitialSOC，因此不是 Q3 新终端约束下的正式可行基准。

### E0：无储能能源调度

在相同固定负荷和能源参数下，设 `qR=qG=d=0`。

从 `H[r,t]` 角度，E0 相当于：

> 每个时刻的新能源盈余只能在“当期售电/当期弃电”之间处理，不能跨时段搬移。

### E1：完整 BESS 协同调度

允许通过 SOC 动态把能源盈余跨时段移动。

因此：

`E1 - E0`

可以被严格解释为“跨时段储能柔性本身的增量价值”，而不是把 baseline 中新能源分配策略差异也归因于储能。

## 4. Q3 的数据结构驱动建模顺序

推荐正文按以下顺序建立：

1. 固定任务调度并得到 Facility Load；
2. 计算 `H[r,t]=AvailableRenewable-L`；
3. 根据 `H` 与 SellLimit 识别 A/B/C、D/E、F 三类储能角色；
4. 再建立统一的新能源分配 + Grid + BESS SOC 多时段 LP；
5. Stage 1 最小运行成本；
6. Stage 2 在成本最优集合内最小化储能吞吐量，消除 SCD 数值循环；
7. 用 B0/E0/E1 分离整体能源策略改善与 BESS 增量价值；
8. 分区解释充放电策略，而不是假设六区都有同样的“削峰填谷”模式。

这样 Q3 的创新来自附件中新能源盈余结构，而不是换一个更复杂的优化算法。

## 5. 时间展开能量网络的定位

`time-expanded energy-flow network` 可以保留为统一 LP 的结构化示意：

- 当期 Renewable 可流向 Load / Battery / Sell / Curtailment；
- Grid 可流向 Load / Battery；
- Battery 通过 SOC 将能量从 t 搬到 t+1。

它适合用来解释“储能协同”的跨时段能量转移，但不作为创新来源，也不必把主模型改写成 generalized min-cost flow。

是否进入正文取决于 Q4 篇幅。

## 6. 与近期文献的关系

1. Zhang Y, Tang H, Li H, Wang S. Unlocking the flexibilities of data centers for smart grid services: Optimal dispatch and design of energy storage systems under progressive loading. Energy, 2025, 316: 134511. DOI: 10.1016/j.energy.2025.134511.
   - 支持在给定数据中心负荷下单独研究储能 optimal dispatch 与 electricity-cost minimization。

2. Wang Q, Wu W, Lin C, Xu S, Wang S, Tian J. An exact relaxation method for complementarity constraints of energy storages in power grid optimization problems. Applied Energy, 2024, 371: 123592. DOI: 10.1016/j.apenergy.2024.123592.
   - 支持储能充/放电互补约束可以先考虑连续松弛而非直接引入大规模 binary；本题的 `Cost -> Throughput` 是更保守的竞赛实现，不声称等同于该论文 exact-relaxation 定理。

3. Vaičys J, Gudžius S, Jonaitis A, Račkienė R, Blinov A, Peftitsis D. A case study of optimising energy storage dispatch: Convex optimisation approach with degradation considerations. Journal of Energy Storage, 2024, 97(B): 112941. DOI: 10.1016/j.est.2024.112941.
   - 支持 BESS dispatch 可以采用连续/凸优化路线，不必默认 MILP。

4. Grimaldi A, Minuto F D, Perol A, Casagrande S, Lanzini A. Techno-economic optimization of utility-scale battery storage integration with a wind farm for wholesale energy arbitrage considering wind curtailment and battery degradation. Journal of Energy Storage, 2025, 112: 115500. DOI: 10.1016/j.est.2025.115500.
   - 支持用 no-storage scenario 单独衡量 BESS 的增量价值，并讨论 renewable curtailment 与 energy arbitrage。

## 7. 不过度外推

- A/B/C 零动作结论依赖当前数据、售电边界和成本主目标；
- D/E/F 的经济判据是局部边际解释，正式最优解仍由完整 SOC/功率/出口边界约束决定；
- 不引入附件没有给出的 degradation/SOH/cycle cost；
- 不为制造“碳优化”改变新能源极充足这一数据事实。
