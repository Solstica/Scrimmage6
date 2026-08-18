# Q1--Q4 模型支撑与新增探针汇总（2026-08-17）

状态：`DRAFT / NEEDS_REVIEW`

本文件只做跨问索引；各问正式模型仍以对应 feature 分支真源为准。

## Q1

新增：`feature/q1/modules/20_q1/code/Q1_COMPOSITION_STABILITY_PROBE_20260817.md`

结论：18 个 Region×TaskType 子流 dispersion 为 `0.944--1.079`；Bonferroni 后无子流拒绝 Poisson dispersion；cell 同时相关性很弱；四块训练组成稳定。当前无需升级 NB / 时变 pi / 高维 dependence model。

## Q2

新增：`feature/q2/modules/30_q2/code/Q2_FLEXIBILITY_HEADROOM_PROBE_20260817.md`

结论：在放松任务不可拆分和逐任务时间约束、但保留 source-type spatial SLA 与 GPU/IT/Facility 容量的 fluid probe 中，全部 Batch+Training 可在不增加任何时段购电的条件下重新承载。Removal-side Cost/Carbon headroom 约 `342.32m CNY / 302.28k tCO2`。旧静态草稿只捕获约 `38.6%/42.1%`，说明新版动态边际 SFETA 仍有明显空间；该比例需新版重跑后重算。

## Q3

新增：`feature/q3/modules/40_q3/code/Q3_REDUCTION_AND_SHADOW_VALUE_PROBE_20260817.md`

结论：附件满足 `BuyPrice>=SellPrice>=0`、`min Renewable=500 >= max ChargePower=260`；可证明 A/B/C 的字典序代表解零动作，并证明至少存在成本最优代表解 `GridCharge=0`。Full vs reduced LP 的 BESS value / minimum throughput 在六区数值一致到约 `1e-6`。SOC dual 可用于局部解释，但 D 区退化说明 dual 可能非唯一。

## Q4

新增：

- `feature/q4/modules/50_q4/code/Q4_FULL_MASTER_SCALABILITY_AND_SCENARIO_PROBE_20260817.md`
- `feature/q4/modules/50_q4/code/Q4_COMPLETE_RECOURSE_PROBE_20260817.md`

结论：完整合法 master 有 `233,375,201` task columns；仅 assignment+GPU+IT+Facility 的显式 sparse matrix 下界约 `2.96e9` nonzeros（约 `35--47 GB` CSR，不含 solver 开销/cuts），因此 full mathematical Benders 与 full explicit master 必须区分。全规模实现应采用 exact delayed/implicit column representation，不得 arbitrary top-k。

Base-case Q4 又具有 complete recourse：六区均满足 `min Renewable + MaxGridImport > MaxFacility`，所以任意 task-master 可行解都有 `q=d=s=0, SOC=Initial` 的能源可行 recourse。Baseline Cost-only Benders 因此只需 optimality cuts；Carbon budget / renewable stress 场景才按需触发 feasibility cuts。

另外附件 0--2399 的 100 个新能源日 profile 完全相同，不能用经验日波动 Q25/Q50/Q75 校准正式 scenario；新能源波动只能明确作为 sensitivity/scenario construction。

## 文献总审计

见 `feature/references/modules/70_references/Q1_Q4_LITERATURE_SUPPORT_INNOVATION_CORRECTION_20260817.md`。

统一原则：成熟方法负责求解；本题创新优先来自附件结构决定的模型自由度、约化、边际响应与联合耦合，而不是给 Poisson/LP/Benders/SFETA 换名字。
