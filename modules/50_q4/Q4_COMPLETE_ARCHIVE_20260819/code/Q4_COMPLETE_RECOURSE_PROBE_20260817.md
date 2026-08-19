# Q4 Base-Case Complete Recourse Probe（2026-08-17）

状态：`DRAFT / NEEDS_REVIEW`

目的：判断正式 Benders 是否真的需要在 baseline Cost-only Q4 中实现 feasibility cuts。

## 1. 构造性可行解

Q4 task master 已强制：

`FacilityLoad[r,t] <= MaxFacility[r]`。

给定任意满足 task-side GPU/IT/Facility/SLA/deadline 的 master schedule，能源子问题可以选择：

- `qR=qG=d=s=0`；
- `SOC[t]=InitialSOC` 全时域；
- `u[r,t]=min(AvailableRenewable[r,t], FacilityLoad[r,t])`；
- `GridPurchase[r,t]=max(FacilityLoad[r,t]-AvailableRenewable[r,t],0)`；
- 剩余新能源全部 `Curtailment`。

该构造自动满足 terminal `SOC(2406)>=InitialSOC`。

因此只需要验证最坏情况下：

`MaxFacility[r] - min_t AvailableRenewable[r,t] <= MaxGridImport[r]`。

## 2. 附件数值验证

全时域 `min AvailableRenewable = 500 MW`。六区安全余量：

| Region | min Renewable | MaxGridImport | MaxFacility | `Renewable+GridImport-MaxFacility` |
|---|---:|---:|---:|---:|
| A | 500 | 550 | 567.0 | 483.0 |
| B | 500 | 520 | 553.5 | 466.5 |
| C | 500 | 510 | 558.9 | 451.1 |
| D | 500 | 510 | 921.6 | 88.4 |
| E | 500 | 370 | 700.0 | 170.0 |
| F | 500 | 340 | 685.8 | 154.2 |

全部严格为正。

因此在 **baseline Q4、无额外系统级 carbon budget / 非基准 renewable stress** 下：

> 任意 task-master 可行解都存在一个 Renewable/Grid/BESS 可行 recourse。

即 baseline energy subproblem 具有 complete recourse。

## 3. 对 Benders 的影响

Baseline Cost-only Q4 不需要 feasibility cuts；只需要 optimality cuts。

这可以显著简化正式 Benders：

- task master 负责 GPU/IT/Facility/SLA/deadline；
- energy LP 对任意 master-feasible `x` 都可行；
- Benders 只积累 recourse-value optimality cuts。

## 4. 场景边界

该结论不能无条件外推到所有 Q4 场景：

1. 若新能源压力场景使 `Renewable_scenario + MaxGridImport < MaxFacility`，complete recourse 可能失效；
2. 加系统级 `Carbon <= B_C` 后，即使物理供能可行，某个 master schedule 也可能无法满足给定碳预算；此时需要 feasibility cut，或确保 epsilon path / master 结构显式排除该类 schedule。

因此正式实现建议：

- baseline Cost-only：证明 complete recourse，省略 feasibility cut；
- Carbon/renewable stress scenario：保留 infeasibility detector，只有实际发生时再生成 feasibility cut。

这属于数据条件带来的算法简化，不为完整性机械加入未被触发的复杂模块。
