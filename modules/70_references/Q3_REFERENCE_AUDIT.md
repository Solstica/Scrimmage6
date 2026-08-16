# Q3 参考文献审计

状态：`DRAFT / NEEDS_REVIEW`

Q3 文献只用于支持 BESS optimal/economic dispatch、连续/凸储能调度、互补约束处理和 no-storage benchmark。Q3 的 A/B/C、D/E、F 三类区域机制来自附件 `H=AvailableRenewable-FacilityLoad` 与 SellLimit 数据结构，不声称是已有标准模型。

## 1. 数据中心 BESS optimal dispatch

Zhang Y, Tang H, Li H, Wang S. Unlocking the flexibilities of data centers for smart grid services: Optimal dispatch and design of energy storage systems under progressive loading. Energy, 2025, 316: 134511. DOI: 10.1016/j.energy.2025.134511.

可支持：
- 给定数据中心负荷下单独建立储能 optimal dispatch；
- electricity-cost minimization 作为储能调度主目标。

本题不吸收：storage sizing、progressive loading 生命周期设计等附件没有的机制。

## 2. 储能充放电互补约束的 exact relaxation

Wang Q, Wu W, Lin C, Xu S, Wang S, Tian J. An exact relaxation method for complementarity constraints of energy storages in power grid optimization problems. Applied Energy, 2024, 371: 123592. DOI: 10.1016/j.apenergy.2024.123592.

可支持：
- 同时充放电属于储能优化的典型 complementarity 问题；
- 不必默认使用大量 binary，满足条件时可采用 exact relaxation / penalty 保持连续优化。

本题当前 `Cost -> Throughput` 字典序不是该论文方法的原样复现，只是数据上已经验证能消除 SCD 的轻量竞赛实现。若正式程序仍出现 SCD，再考虑引用该文的更严格松弛条件。

## 3. Convex BESS dispatch

Vaičys J, Gudžius S, Jonaitis A, Račkienė R, Blinov A, Peftitsis D. A case study of optimising energy storage dispatch: Convex optimisation approach with degradation considerations. Journal of Energy Storage, 2024, 97(B): 112941. DOI: 10.1016/j.est.2024.112941.

可支持：
- BESS dispatch 采用连续/凸优化是成熟路线；
- 模型复杂度应由问题结构决定，不等同于必须 MILP。

本题不引入 degradation 参数，因为附件没有 SOH、cycle life、replacement cost。

## 4. no-storage benchmark、curtailment 与 energy arbitrage

Grimaldi A, Minuto F D, Perol A, Casagrande S, Lanzini A. Techno-economic optimization of utility-scale battery storage integration with a wind farm for wholesale energy arbitrage considering wind curtailment and battery degradation. Journal of Energy Storage, 2025, 112: 115500. DOI: 10.1016/j.est.2025.115500.

可支持：
- 用 scenario without storage 衡量 BESS 集成的增量价值；
- BESS 可同时承担 renewable curtailment mitigation 与 energy arbitrage。

本题对应：E0/E1；不吸收该文的 sizing 和 degradation 模型。

## 5. 论文引用建议

Q3 正文推荐 3--4 篇足够：

- 数据中心 BESS optimal dispatch：Zhang et al. 2025；
- exact relaxation：Wang et al. 2024；
- convex dispatch：Vaičys et al. 2024；
- no-storage / arbitrage：Grimaldi et al. 2025。

不要堆 stochastic/DRO/MPC/RL/shared-storage/hydrogen 文献来制造复杂度，因为题目给的是确定逐时数据和单一储能参数。
