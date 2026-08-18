# Q3 术语与 LP 层级审计

状态：`DRAFT / NEEDS_REVIEW`

## 1. LP 属于哪一层

`Linear Programming (LP)` 首先是**数学优化模型/问题类别**：目标函数与约束均为线性，决策变量为连续变量。论文“模型建立”部分可以写“将 Q3 约化为一个多时段线性规划”。

真正的**算法层**是求解该 LP 的数值算法，例如单纯形法、对偶单纯形法、内点法/障碍法等；若代码使用 HiGHS/CBC/Gurobi 等求解器，应在“模型求解”部分说明具体 solver/algorithm，而不能把“LP”本身当成唯一算法名称。

本题当前层级应区分为：

1. 模型结构层：E0 解析基准 + 弃电回收/价值释放的增量 BESS 调度；
2. 数学形式层：连续多时段 LP；
3. 求解组织层：`Stage 1 最大 BESS 经济价值 -> Stage 2 最小储能吞吐量` 的字典序求解；
4. 数值算法层：实际 LP solver 的 simplex / dual-simplex / interior-point 等；
5. 验证层：与完整新能源—电网—储能流 LP 比较最优值、吞吐量、SOC、SCD 与约束残差。

因此正式论文不要写“采用 LP 算法建立模型”；推荐写“建立……线性规划模型，并采用……求解器求解”。

## 2. 术语审计

### 2.1 可直接采用的成熟术语

- `Battery Energy Storage System (BESS) optimal dispatch`
- `BESS economic dispatch`
- `multi-period energy storage dispatch / scheduling`
- `renewable curtailment mitigation`
- `renewable curtailment recovery / recovering curtailed renewable energy`
- `energy arbitrage`
- `export limit / maximum export capacity`
- `charge/discharge complementarity constraint`
- `simultaneous charging and discharging (SCD)`
- `exact relaxation`
- `no-storage benchmark / scenario without storage`
- `marginal value of stored energy / Lagrangian marginal value`（用于解释 SOC 对偶变量，不改变主模型）

### 2.2 只作为本文描述、不能包装成标准模型名的词

- “弃电源—价值汇分解” / `curtailment-source–value-sink decomposition`：本文针对附件数据的结构性描述，不是公认固定术语。
- “基于 E0 的储能增量价值调度” / `baseline-referenced incremental BESS dispatch`：本文模型描述，不声称是已有标准问题名。
- “机会成本型储能调度”：可用于中文机理解释，不作为文献标准模型名称。
- B0/E0/E1：本文场景编号。

### 2.3 推荐正式命名

问题族名称保持成熟：

**固定负荷下的多时段 BESS 经济调度（multi-period BESS economic dispatch under fixed load）**。

题目特化描述写为：

**基于可再生弃电回收与出口/缺口价值释放的增量储能调度**。

其中“可再生弃电回收（renewable curtailment recovery）”有文献依据；“出口/缺口价值释放”是对本题 `remaining export capacity` 与 `grid deficit` 的机制性解释。

## 3. LP 是否“太常规”

### 3.1 如果把“用了 LP”当创新：是，太常规

标准 SOC 递推 + 功率平衡 + 电价目标构成的 BESS LP 已经是成熟做法。仅仅把 Q3 写成“建立 LP 并求解”没有足够辨识度。

### 3.2 如果 LP 是数据结构约化后的最终形式：不构成问题

当前更值得强调的不是 LP，而是以下结构推导：

1. 从固定 Facility Load 与 AvailableRenewable 得到 `H=R-L`；
2. 解析得到无储能 E0：购电缺口 `D0`、售电 `S0`、弃电 `C0`、剩余出口容量 `X0`；
3. 由附件发现 A/B/C 无缺口且无售电，解析消去三个区域的 BESS 决策；
4. 对 D/E/F，仅把 E0 的原弃电作为充电源，把购电缺口与剩余出口容量作为放电价值位置；
5. 在当前数据条件下验证 GridCharge 可从一个最优代表解中消失；
6. 得到低维增量 BESS 模型；
7. 与完整能源流 LP 对照验证最优经济价值与最小吞吐量一致。

如果正式程序复现上述等价性，论文创新应表述为“利用附件盈余/弃电/出口结构进行模型约化与贡献分解”，而不是“提出新 LP 算法”。

## 4. 近十年文献对当前路线的支持

### 4.1 Data-center BESS optimal dispatch

Zhang et al., Energy 2025, *Unlocking the flexibilities of data centers for smart grid services: Optimal dispatch and design of energy storage systems under progressive loading*。

支持：数据中心给定负荷下可以单独建立储能 optimal dispatch；electricity-cost minimization 是合理主目标。本文不吸收其 sizing / progressive loading。

### 4.2 直接利用被弃新能源给储能充电

*Techno-economic optimisation of battery storage for grid-level energy services using curtailed energy from wind*, Journal of Energy Storage 2021, 39:102641。

支持：BESS 可用原本被弃的风能充电，再在后续有价值时段释放；这与本题 `C0 -> BESS -> future value` 的解释高度接近。

### 4.3 “curtailment recovery” 与线性调度并不落后

*Capturing curtailed renewable energy in electric power distribution networks via mobile battery storage fleet*, Journal of Energy Storage 2022, 46:103883。

该文直接使用 `recover curtailed renewable energy` 的问题表述，并强调线性模型可处理大规模问题、保持全局最优与稳定求解。说明“线性”本身不是缺陷，关键是模型是否抓住了真实结构。

### 4.4 出口能力会决定弃电回收价值

*Management of prosumers using dynamic export limits and shared Community Energy Storage*, Applied Energy 2024, 355:122222。

支持：export limits 与储能共同决定新能源弃电和可利用程度。本题虽然没有动态网络约束，但 `SellLimit/MaxGridExport` 确实是 D/E/F 储能价值的重要边界，因此可把 `remaining export capacity` 作为结果解释变量。

### 4.5 数据中心多种 flexibility 的顺序/分层量化

Kontani & Tanaka, Urban Climate 2024, *Integrating variable renewable energy and diverse flexibilities: Supplying carbon-free energy from a wind turbine to a data center*。

支持：对 renewable curtailment、BESS、time-shifting demand response 等 flexibility 采用 sequential optimization 分层识别贡献。可为本题 B0/E0/E1 的分层归因提供方法学类比，但不照搬其 PPA 场景。

### 4.6 Exact relaxation 与连续模型

Wang et al., Applied Energy 2024, 371:123592, *An exact relaxation method for complementarity constraints of energy storages in power grid optimization problems*。

支持：储能 SCD 的互补约束会带来非凸/整数变量；在合适条件或惩罚下可通过 exact relaxation 保持连续优化。本文当前 `价值最优 -> 最小吞吐量` 不是该 exact-relaxation 定理原样实现，只用来说明无需机械地把 Q3 升级为 MILP。

### 4.7 Convex / LP / MILP 都是正常工具

Vaičys et al., Journal of Energy Storage 2024, 97:112941。

该文把 convex optimisation 与 naive、LP、MILP 对照，说明储能 dispatch 的求解形式应由物理结构和附加机制（如 degradation）决定；本题没有 degradation/SOH 参数，因此没有必要为“新”强行引入非线性或整数变量。

### 4.8 储能边际价值的 Lagrangian 解释

Cruise, Flatley, Gibbens & Zachary, Operations Research 2019, 67(1):1-9, *Control of Energy Storage with Market Impact: Lagrangian Approach and Horizons*。

支持：储能控制可通过 Lagrangian/marginal-value 解释。若论文希望增加数学解释，可读取 SOC 动态约束的对偶变量，解释“电池内 1 MWh 在 t 时刻的影子价值”，形成充/放电阈值解释；不需要改变 LP 或再增加一个优化模型。

## 5. 对 Q3 最有价值的轻量升级

### A. 把解析结构写成命题，而非只写数据观察

建议至少证明或数值严格验证：

- 命题 1：E0 在当前无储能条件下具有逐时闭式分解；
- 命题 2：在 A/B/C 的 `H>=0, SellLimit=0` 条件下，字典序最优代表解为零 BESS 动作；
- 命题 3：在当前价格与新能源条件下，存在最优代表解满足 `GridCharge=0`；
- 命题 4：缩减增量模型与完整能源流 LP 在本附件上给出相同最优价值和最小吞吐量（当前先作为数值等价性，不在无证明前写成一般定理）。

### B. 用 SOC 对偶变量形成“储能边际价值曲线”

不增加复杂度，只从已求 LP 中读取 dual/shadow price：

- 充电：当前弃电机会成本/售电机会成本低于经效率修正的未来储能边际价值时发生；
- 放电：当前避免购电或释放售电的边际价值高于保留电量的未来影子价值时发生。

这样充放电策略不再只是一条曲线，而有可解释的数学判据。

### C. LP 的论文定位

模型标题不要出现“LP 创新”。正文建议：

> 基于附件中长期新能源盈余、显著弃电和有限外送能力的结构，先解析构造无储能基准 E0，并将 BESS 作用约化为“弃电回收—跨时段价值释放”的增量调度问题。该约化模型保持线性，可由成熟 LP 求解器获得全局最优；再采用字典序最小吞吐量选择无无效循环的物理解。

## 6. 当前判断

- `LP`：成熟、常规，但不是缺点；不应作为创新点。
- `MILP / RL / DRO / MPC`：在当前确定数据和附件参数下没有必要，仅为显得复杂而加入会削弱模型。
- 真正值得写的创新：`E0 解析化 + 数据结构约化 + 弃电回收/出口价值机制 + 无损等价验证 + 边际价值解释`。
- 若上述结构能由正式程序和必要证明闭合，Q3 的模型辨识度会明显高于“普通 BESS LP”，而计算复杂度反而更低。
