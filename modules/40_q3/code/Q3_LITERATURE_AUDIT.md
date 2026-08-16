# Q3 近十年文献审计：BESS optimal/economic dispatch

状态：`DRAFT / NEEDS_REVIEW`

目的：只吸收能改善 Q3 建模质量、术语严谨性或求解效率，且不要求大改当前结构的研究。题面和附件字段定义始终优先。

## 1. 正式问题类型

Q3 最合适的科研问题族表述为：

- `Battery Energy Storage System (BESS) optimal dispatch`；
- `BESS economic dispatch`；
- `multi-period energy management / optimal scheduling with BESS`。

本题特化：fixed data-center facility load + renewable allocation + grid purchase/sale + BESS SOC dynamics。

不建议为主模型再造缩写。

## 2. 最值得吸收的近期文献思想

### 2.1 数据中心储能 optimal dispatch：Energy 2025

文献：*Unlocking the flexibilities of data centers for smart grid services: Optimal dispatch and design of energy storage systems under progressive loading*, Energy, 316 (2025), 134511.

可吸收：

- 数据中心储能可以单独建立 `optimal dispatch` 问题；
- 调度目标可直接采用 electricity cost minimization；
- 储能价值可在固定/给定负荷下单独识别，不必把计算任务调度一起重新优化。

本题不吸收：

- progressive loading 生命周期设计；
- storage sizing / investment；
- grid ancillary service reliability 等附件未给参数的机制。

### 2.2 Energy-storage complementarity exact relaxation：Applied Energy 2024

文献：*An exact relaxation method for complementarity constraints of energy storages in power grid optimization problems*, Applied Energy, 371 (2024), 123592.

可吸收：

- “禁止同时充放电”通常产生 complementarity / binary variables；
- 不一定必须直接使用 MILP；在满足条件或引入恰当充放电损失惩罚时，可以使用 exact relaxation 保持连续优化；
- 该类方法适用于 storage-participating economic dispatch。

本题建议：

- 继续先解连续 LP；
- 成本最优后采用 lexicographic throughput regularization 选取低循环物理解；
- 把 SCD=0 作为门禁；
- 若门禁失败，再参考 exact-relaxation penalty 条件，而不是第一步就加 1.4 万个二元变量。

注意：本题当前的“成本最优面上最小 throughput”不是上述论文定理的原样实现，只是与 exact-relaxation 思路一致的更保守竞赛版处理，不能声称直接采用该论文算法。

### 2.3 Convex BESS dispatch：Journal of Energy Storage 2024

文献：*A case study of optimising energy storage dispatch: Convex optimisation approach with degradation considerations*, Journal of Energy Storage, 97 (2024), 112941.

可吸收：

- BESS dispatch 不必等同于 MILP；凸优化可以在保持计算效率的同时处理充放电状态与部分循环；
- LP/MILP/convex 方法之间应按数据与模型需求选择，不是算法越复杂越好。

本题不吸收 degradation 模型：附件没有 battery ageing / SOH / cycle-life 参数。

### 2.4 无储能基线对照：Journal of Energy Storage 2025

文献：*Techno-economic optimization of utility-scale battery storage integration with a wind farm for wholesale energy arbitrage considering wind curtailment and battery degradation*, Journal of Energy Storage (2025), DOI 10.1016/j.est.2025.115500.

可吸收：

- 对 BESS 集成价值进行评价时，明确与 `scenario without storage` 比较；
- 分离储能带来的增量经济价值与原系统自身运行状态差异。

本题对应：

- E0 = same energy-allocation problem without storage；
- E1 = same problem with BESS；
- `E1 - E0` 作为 BESS 增量价值。

这为 B0/E0/E1 中 E0 的设置提供了直接文献类比。

### 2.5 Curtailment + BESS 的经济调度：Journal of Energy Storage 2024 / 2025

近期文献普遍把 BESS 用于：

- renewable curtailment mitigation；
- energy arbitrage；
- peak shaving / valley filling；
- market participation。

本题的实际数据也自然形成三类服务：

1. D/E/F：新能源跨时段搬移与售电价格套利；
2. F：唯一新能源不足小时的购电/峰值削减；
3. A/B/C：新能源逐时已覆盖负荷，成本最优时储能可能无增量价值。

不应预设六区都有同样明显的削峰填谷效果。

## 3. 很新但当前不建议采用的模型

### 3.1 degradation-aware MILP / Bayesian Optimization + MILP（2024--2025）

优点：可描述电池寿命、容量配置与经济性。

不采用原因：附件没有 cycle-life、DoD-aging、SOH、replacement cost；硬加会引入外部参数并改变题目边界。

### 3.2 stochastic programming / DRO

优点：适用于可再生出力、价格、负荷预测不确定。

不采用原因：Q3 明确使用附件实际逐时负荷和实际电力参数，不需要把确定输入重新随机化。

### 3.3 MPC / LP-based predictive control

2024 年已有 LP-based predictive battery control 与 adaptive time aggregation 等方法，适用于滚动预测和在线控制。

不采用原因：本题是离线全时域优化，0--2406 参数已给定，MPC 会多一层预测/滚动结构但不会改善题意匹配。

### 3.4 ADP / RL

适合大规模在线随机控制，但本题只有 6 个区域、确定时域和线性 SOC 动态，直接 LP 更透明且可验证。

### 3.5 Stackelberg / shared energy storage / cooperative game

2024--2025 有数据中心集群共享储能、双层博弈等研究。

不采用原因：本题没有共享储能运营商、租赁价格或利益分配主体；引入后会改变物理对象。

### 3.6 hybrid hydrogen-battery / multi-energy storage

2025 有数据中心氢-电混合储能、双时间尺度协同优化研究。

不采用原因：附件只给单一储能参数，没有氢储能设备和转换效率，属于题外扩展。

## 4. 可选但暂不推荐的“新表述”：generalized min-cost flow

BESS 的多时段 SOC 可理解为时间扩展网络中的库存/能量传递；若忽略效率损失，问题可写成标准 min-cost flow。考虑 `eta_c, eta_d != 1` 后更接近 generalized flow。

优点：结构直观，网络算法高效。

缺点：本题直接 LP 已很小且更容易和附件变量一一对应；引入 generalized flow 会增加解释成本，没有明显数值收益。

结论：只可作为理论备注，不作为主模型。

## 5. 当前推荐的轻量升级

不换模型，推荐把求解器组织为：

### Stage 1：区域分解经济调度 LP

6 个 Region 独立求：

`min electricity purchase cost - renewable export revenue`

subject to renewable allocation, fixed-load balance, SOC dynamics, charge/discharge limits, import/export limits, terminal SOC。

### Stage 2：成本最优面上的物理解选择

先探查：

- PeakImport；
- NetGridImport ramp / volatility；
- battery throughput。

若成本最优面有明显自由度，则按题意做无权重 lexicographic refinement：

`Cost -> Peak/Ramp -> Throughput`。

若没有明显自由度，则：

`Cost -> Throughput`。

### Stage 3：SCD 门禁

若仍同时充放电：

1. 参考 Applied Energy 2024 exact-relaxation/penalty 思路；
2. 仍失败才升级 MILP binary。

该路线比直接 MILP 更轻，也比随意删除互补约束更严谨。

## 6. 当前推荐论文术语

- 储能最优调度：`BESS optimal dispatch`；
- 储能经济调度：`BESS economic dispatch`；
- 多时段调度：`multi-period optimal dispatch`；
- SOC 动态：`state-of-charge dynamics`；
- 同时充放电：`simultaneous charging and discharging (SCD)`；
- 充放电互补约束：`charge/discharge complementarity constraint`；
- 精确松弛：`exact relaxation`；
- 新能源弃电缓解：`renewable curtailment mitigation`；
- 无储能对照：`scenario without storage / no-storage benchmark`；
- 峰值削减：`peak shaving`；
- 能量套利：`energy arbitrage`。

“B0/E0/E1”仅是本文场景编号，不宣称为标准科研模型名。

## 7. 文献审计结论

当前 Q3 最值得采用的新思想只有一个：

**用 recent exact-relaxation / convex storage dispatch 文献加强“保持连续 LP、避免不必要 MILP”的理论依据。**

其余前沿方向（退化、随机、MPC、ADP、共享储能、氢储能）都会增加题外参数或改变问题结构，不建议加入。

因此主模型仍维持：

**fixed-load multi-period BESS economic dispatch + no-storage ablation + region decomposition + lexicographic physical-solution refinement**。
