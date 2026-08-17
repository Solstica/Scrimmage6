# Q3 参考文献审计

状态：`DRAFT / NEEDS_REVIEW`

Q3 文献只用于支持 BESS optimal/economic dispatch、renewable curtailment recovery、连续/凸储能调度、互补约束处理、no-storage benchmark、出口容量边界和储能边际价值解释。Q3 的 A/B/C、D/E、F 区域机制，以及 E0 的 `C0/D0/X0` 分解，来自附件数据结构，不声称是已有标准模型。

## 1. 数据中心 BESS optimal dispatch

Zhang Y, Tang H, Li H, Wang S. Unlocking the flexibilities of data centers for smart grid services: Optimal dispatch and design of energy storage systems under progressive loading. Energy, 2025, 316: 134511. DOI: 10.1016/j.energy.2025.134511.

可支持：
- 给定数据中心负荷下单独建立储能 optimal dispatch；
- electricity-cost minimization 作为储能调度主目标。

本题不吸收：storage sizing、progressive loading 生命周期设计等附件没有的机制。

## 2. 直接利用被弃新能源给储能充电

Techno-economic optimisation of battery storage for grid-level energy services using curtailed energy from wind. Journal of Energy Storage, 2021, 39: 102641. DOI: 10.1016/j.est.2021.102641.

可支持：
- BESS 可以吸收原本被弃的风能；
- 再在后续有价值/峰值时段释放；
- `curtailed renewable -> storage -> later value` 是成熟的储能利用机制。

本题对应：E0 中 `C0` 作为可回收弃电；不照搬其英格兰峰机组/投资场景。

## 3. Curtailment recovery 与线性调度

Capturing curtailed renewable energy in electric power distribution networks via mobile battery storage fleet. Journal of Energy Storage, 2022, 46: 103883. DOI: 10.1016/j.est.2021.103883.

可支持：
- `recover curtailed renewable energy` / `curtailment recovery` 是可以直接使用的科研表述；
- 储能调度可围绕过剩/被弃新能源的吸收与后续释放来建模；
- 线性模型可以用于大规模储能调度并保持全局最优和稳定求解。

本题不吸收：mobile storage 的运输和网络位置变量。

## 4. 出口能力与储能/弃电关系

Management of prosumers using dynamic export limits and shared Community Energy Storage. Applied Energy, 2024, 355: 122222. DOI: 10.1016/j.apenergy.2023.122222.

可支持：
- export limit 与 storage 会共同影响 renewable curtailment；
- 可外送能力是新能源/储能系统运行的重要边界。

本题对应：`SellLimit/MaxGridExport` 与 E0 的 `remaining export capacity X0`；不引入配电网动态 operating envelope 或共享储能主体。

## 5. 数据中心多类 flexibility 的顺序归因

Kontani R, Tanaka K. Integrating variable renewable energy and diverse flexibilities: Supplying carbon-free energy from a wind turbine to a data center. Urban Climate, 2024, 54: 101843. DOI: 10.1016/j.uclim.2024.101843.

可支持：
- 数据中心场景中 renewable curtailment、BESS、time-shifting demand response 可以作为不同 flexibility 分层研究；
- sequential optimization 可用于识别各类 flexibility 的单独贡献。

本题对应：B0/E0/E1 的机制分层与贡献归因；不照搬其 PPA 与 wind-to-data-center 场景。

## 6. 储能充放电互补约束的 exact relaxation

Wang Q, Wu W, Lin C, Xu S, Wang S, Tian J. An exact relaxation method for complementarity constraints of energy storages in power grid optimization problems. Applied Energy, 2024, 371: 123592. DOI: 10.1016/j.apenergy.2024.123592.

可支持：
- 同时充放电属于储能优化的典型 complementarity 问题；
- 不必默认使用大量 binary，满足条件时可采用 exact relaxation / penalty 保持连续优化。

本题当前 `价值最优 -> Throughput最小` 字典序不是该论文方法的原样复现，只是数据上已经验证能消除 SCD 的轻量竞赛实现。若正式程序仍出现 SCD，再考虑引用该文的更严格松弛条件。

## 7. Convex BESS dispatch

Vaičys J, Gudžius S, Jonaitis A, Račkienė R, Blinov A, Peftitsis D. A case study of optimising energy storage dispatch: Convex optimisation approach with degradation considerations. Journal of Energy Storage, 2024, 97(B): 112941. DOI: 10.1016/j.est.2024.112941.

可支持：
- BESS dispatch 采用连续/凸优化是成熟路线；
- LP、MILP、convex optimization 都是问题结构驱动的工具，不存在“越复杂越先进”的一般关系。

本题不引入 degradation 参数，因为附件没有 SOH、cycle life、replacement cost。

## 8. no-storage benchmark、curtailment 与 energy arbitrage

Grimaldi A, Minuto F D, Perol A, Casagrande S, Lanzini A. Techno-economic optimization of utility-scale battery storage integration with a wind farm for wholesale energy arbitrage considering wind curtailment and battery degradation. Journal of Energy Storage, 2025, 112: 115500. DOI: 10.1016/j.est.2025.115500.

可支持：
- 用 scenario without storage 衡量 BESS 集成的增量价值；
- BESS 可同时承担 renewable curtailment mitigation 与 energy arbitrage。

本题对应：E0/E1；不吸收该文的 sizing 和 degradation 模型。

## 9. 储能边际价值与 Lagrangian 解释

Cruise J, Flatley L, Gibbens R, Zachary S. Control of Energy Storage with Market Impact: Lagrangian Approach and Horizons. Operations Research, 2019, 67(1): 1--9. DOI: 10.1287/opre.2018.1761.

可支持：
- 储能控制可以用 Lagrangian theory 解释；
- 储存在电池中的能量具有时变边际价值，可用于解释充/放电阈值与决策时域。

本题用途：正式 LP 求解后可读取 SOC 动态约束的 dual/shadow price，形成“储能边际价值曲线”，解释为什么某时段选择充电、放电或保持；不需要增加新决策变量或更复杂算法。

## 10. 术语边界

成熟术语推荐：
- BESS optimal/economic dispatch；
- multi-period storage dispatch；
- renewable curtailment mitigation；
- renewable curtailment recovery；
- energy arbitrage；
- export limit / maximum export capacity；
- charge/discharge complementarity；
- simultaneous charging and discharging (SCD)；
- exact relaxation；
- no-storage benchmark；
- marginal value / shadow price of stored energy。

本文描述、不能冒充标准术语：
- `curtailment-source–value-sink decomposition`；
- `baseline-referenced incremental BESS dispatch`；
- B0/E0/E1。

## 11. 论文引用建议

正文建议主引 5--6 篇即可：

1. Zhang et al. 2025：data-center BESS optimal dispatch；
2. J. Energy Storage 2021 / 2022 curtailment recovery：支持用被弃新能源给储能充电；
3. Applied Energy 2024 dynamic export limits：支持出口能力与储能/弃电耦合；
4. Kontani & Tanaka 2024：支持数据中心多类 flexibility 的 sequential contribution analysis；
5. Wang et al. 2024：SCD exact relaxation；
6. Cruise et al. 2019：储能边际价值解释。

Vaičys et al. 2024 与 Grimaldi et al. 2025 可作为补充引用。

不要堆 stochastic/DRO/MPC/RL/shared-storage/hydrogen 文献来制造复杂度，因为题目给的是确定逐时数据和单一储能参数。
