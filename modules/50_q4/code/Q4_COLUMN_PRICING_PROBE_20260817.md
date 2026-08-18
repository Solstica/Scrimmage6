# Q4 Column Pricing Probe（2026-08-17）

状态：`DRAFT / NEEDS_REVIEW`

目的：验证 `Benders + Column Generation` 是否能在不截断完整合法 task domain 的前提下，把 2.33e8 个潜在 `(task,region,start)` columns 转成可计算的隐式 pricing，并给出全 50,000 任务的内存/时间工程预算。

## 1. 40-task exact pricing 验证

沿用 Probe 3 的真实 40-task benchmark：

- 16 Training + 14 Batch + 10 RT；
- 3139 个完整合法 columns；
- 同一 2376--2406 energy recourse；
- 任务容量约束与 Benders region multi-cuts 不变。

Column generation 仅从 40 个资源可行初始 columns 开始，每轮：

1. 解 restricted master LP；
2. 对当前 fractional workload 解 Renewable/BESS/Grid recourse；
3. 加 violated Benders cuts；
4. 用 assignment/resource/cut dual 计算所有合法候选 reduced cost；
5. 每任务按需加入负 reduced-cost columns；
6. 直到既无 violated Benders cut，也无 negative reduced-cost column。

### 结果

| Iter | Active columns | Cuts | Master LB (CNY) | Min reduced cost | Negative columns | Added |
|---:|---:|---:|---:|---:|---:|---:|
| 1 | 40 | 6 | -5,392,646.31 | -15,259.78 | 937 | 14 |
| 2 | 54 | 7 | -5,408,780.09 | -15,232.71 | 1022 | 22 |
| 3 | 76 | 9 | -5,423,465.30 | -14,243.26 | 1006 | 18 |
| 4 | 94 | 9 | -5,443,230.59 | -5,487.61 | 929 | 16 |
| 5 | 110 | 9 | **-5,450,201.934546** | **0** | **0** | 0 |

全部 3139 columns 的显式 master 在同一 cut 集下得到：

`LB_full = -5,450,201.934546 CNY`。

因此：

`|LB_CG - LB_full| = 0`（求解器精度内）。

只生成：

`110 / 3139 = 3.50%`

的 columns，平均 `2.75 columns/task`，即已有 benchmark 上约 96.5% 合法 columns 从未需要显式进入 master，但它们仍由 exact pricing oracle 检查，因此没有修改原问题。

这验证了：**Column Generation 可以作为 Benders master 的等价隐式表示，而不是人为候选裁剪。**

## 2. Full-50k pricing oracle 计时

全数据结构：

- flexible task-region pairs：`194,292`；
- RT start 固定，完整合法 Region candidates：`48,050`；
- flexible duration unique count 很小且每任务最多占约 7 个小时格；
- flexible start domain 是从 ArrivalHour 到合法 latest start 的连续区间。

Probe 对 `(TaskType, Region, Duration)` 预计算逐 start reduced-cost score，并做 suffix minimum / argmin；随后每个 task-region pair 只需要 O(1) 数组查询。

在当前 Python/Numpy 原型中：

- suffix table precompute：`7.84 s`；
- 194,292 个真实 task-region lookups：`1.31 s`；
- suffix arrays：`112.46 MB`；
- 整个 probe 进程 peak RSS：`548.25 MB`（包含附件解析、40-task matrices 与 pricing arrays）。

因此 full-domain **pricing 本身不是主要瓶颈**。正式实现中每轮 dual 变化都需重算 score，但当前数量级约 10 s/round；可进一步用 vectorized convolution / compiled implementation 加速。

## 3. Full-horizon Energy/BESS recourse 计时

另外对 0--2406 全时域六区 BESS LP 做 serial benchmark：

- A: 0.36 s；
- B: 0.23 s；
- C: 0.23 s；
- D: 0.25 s；
- E: 0.24 s；
- F: 0.26 s；
- 六区合计 solver time：`1.56 s`；
- benchmark process peak RSS：`381.5 MB`。

无全局 Carbon budget 时六区还可并行。因此正式 Q4 的主要工程瓶颈继续确认是 **restricted task master**，不是 energy recourse 或 pricing oracle。

## 4. RMP solve scaling 警告

为了避免只按非零元数量乐观外推，又做了一个含 2406h × 6 region × GPU/IT/Facility rows 的 deliberately-degenerate synthetic LP：

- 2000 tasks / 10,000 columns / 131,875 nnz：HiGHS LP 约 `0.77 s`；
- 5000 tasks / 25,000 columns / 323,755 nnz：约 `7.76 s`；
- 10,000 tasks / 50,000 columns：在该随机退化构造下未在剩余 300 s probe budget 内结束。

该随机 LP 不是本题真实 master，因此**不能把 300 s 当作真实 Q4 预测**；但它说明 RMP degeneracy / dual instability 可能比 raw sparse-memory 更危险。正式实现必须：

- 使用 stabilized CG；
- 每轮 batch 加列，避免一列一解；
- warm-start/persistent solver（正式环境若可用 Gurobi/CPLEX/HiGHS persistent API）；
- 对等价 columns 采用确定性 service tie-break；
- 必要时管理/删除长期非活跃列，但终止时 exact pricing 必须能重新生成它们。

## 5. 50k 内存预算

40-task exact probe 最终仅 `2.75 columns/task`。不能直接外推，因此工程预算按更保守的 active-column 密度：

- 5 columns/task：250k columns；
- 10 columns/task：500k；
- 20 columns/task：1.0m；
- 40 columns/task：2.0m。

按平均 overlap、assignment + GPU/IT/Facility + 约 10 个 region-cut coefficient/column 的粗略 sparse estimate：

| active cols | approx matrix nnz | raw sparse/vector estimate | 4× solver-working estimate |
|---:|---:|---:|---:|
| 250k | 5.68m | 0.10 GB | 0.40 GB |
| 500k | 11.35m | 0.20 GB | 0.81 GB |
| 1.0m | 22.70m | 0.40 GB | 1.62 GB |
| 2.0m | 45.41m | 0.81 GB | 3.23 GB |

上述只是低层数组估计，不能当总 RAM。正式预算还必须加入：solver basis/presolve、Python/runtime、column metadata、Benders cut pool、warm-start、energy arrays 和安全余量。

为防 Python object overhead，**禁止用每列一个 dict/object 的方式保存百万列**；必须使用 packed NumPy/CSR/solver-native arrays。

### 推荐工程预算

在 `<=1m` active columns、region cuts 约每列 10--20 个 cut coefficients 的目标下：

- packed task/column pool：约 0.5--1.0 GB；
- sparse RMP arrays：约 0.5--1.0 GB；
- LP/MILP solver working memory：保守 3--5 GB；
- suffix pricing tables / workload / energy / Benders state：约 0.5--1.0 GB；
- runtime + fragmentation + safety：约 1--2 GB；

**推荐目标 peak RAM：6--9 GB。**

若 active columns 接近 `2m` 或 cuts 明显增加，保守估计提升到约 **9--14 GB**。

因此用户给出的工程要求：

- preferred `<=10 GB`；
- hard cap `<=20 GB`；

目前从 probe 看是**有希望满足的**，但必须使用 packed column representation + delayed columns；不能显式 2.33e8 master，也不能保留大量 Python column objects。

## 6. 时间预算

已测非 Master 部分：

- full pricing round：约 `9--10 s`；
- full six-region recourse：约 `1.5--2 s serial`；

即使按 30 个 root CG/Benders rounds，二者合计也只有约 6 min 数量级。真正时间预算取决于 RMP LP/MILP。

当前建议按两档进行正式工程控制：

### 目标档

- root CG/Benders：<= 25 rounds；
- 平均 RMP solve <= 5 min；
- root phase <= 2.5 h；
- restricted integer refinement <= 3 h；
- Carbon/scenario 主结果复用 column pool / warm start，主要情景 <= 2 h；
- I/O 与安全余量约 1 h。

总计目标：约 **6--8 h**。

### 硬门禁

总 wall-clock **不得超过 9 h**。

若早期运行显示：

- active columns > 1--2m；
- 单轮 RMP > 10 min；
- projected total > 9 h；

则不继续硬跑，应启动：

1. stronger dual stabilization；
2. column batching / add only most-negative per task/block；
3. packed/disk-backed inactive column archive；
4. exact pricing screening；
5. root-CG + restricted MILP，而不是直接 full branch-and-price；
6. 只有整数 gap 无法接受才进入 branch-and-price。

这些措施都不能永久删除完整合法候选；最终 exact pricing scan 仍负责完整性门禁。

## 7. 当前结论

1. 40-task 上 `Benders + CG` 用 110/3139 columns 精确复现 full explicit master LP bound；
2. full-50k exact pricing oracle 只有 194,292 flexible task-region lookups，当前原型约 9 s/round，内存约百 MB 量级；
3. full-horizon Energy LP 约 1.6 s serial，非瓶颈；
4. 全规模不确定性集中在 RMP degeneracy 和 integer refinement；
5. 因此最终正式方案的工程目标可以设为：
   - **目标 RAM 6--9 GB；推荐不超过 10 GB；绝对不超过 20 GB**；
   - **目标时间 6--8 h；绝对不超过 9 h**。
6. 上述为 probe-based engineering projection，不是正式 50k solve 已完成；必须由编程手的 full-scale implementation 继续记录 peak RSS / active columns / RMP time 并动态停机。

结果 JSON：`modules/50_q4/results/q4_column_pricing_probe_20260817.json`。
