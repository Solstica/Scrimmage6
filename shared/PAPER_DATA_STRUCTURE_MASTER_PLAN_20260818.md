# 全文数据结构驱动主线与公共模块补充计划（2026-08-18）

## 0. 总目标

当前四问核心模型已经大量利用附件数据，但整篇论文的公共章节仍偏模板化。最终论文不能只展示“用了 Poisson / SFETA / LP / Benders+CG”，而应让读者看到：

`附件数据关系 -> 发现关键矛盾 -> 决定模型结构 -> 决定算法结构 -> 得到结果 -> 用图验证机制`。

全文统一主线：

- Q1：从任务统计结构提取短期计算需求规律；
- Q2：利用 workload 时空柔性修复“弃电与购电并存”的算电错配；
- Q3：固定 workload 后利用 BESS 时间柔性识别三类储能角色；
- Q4：计算柔性与储能柔性争用同一新能源余量，因此必须联合优化。

---

## 1. 全文最值得突出的数据发现

### D1 TaskType × SourceRegion 不是独立的
Q1 使用联合业务标记，而不是独立边际。

### D2 任务数与资源工作量严重错位
Training 约 1/3 任务但约 80% GPU-hour、约 87% AI IT energy；后续 Q2/Q4 都不能按任务数等价处理。

### D3 六区 AvailableRenewable 逐时完全相同
题面 E/F 新能源标签不能直接用于“绿色区域评分”。真实能源空间差异来自 PUE、负荷、弃电、价格/碳、储能与售电边界。

### D4 Q2 基准存在极强“弃电 + 购电”同时发生
0--2399 h 14,400 region-hour 中约 91.9% 同时存在 Curtailment 与 GridToLoad；累计弃电约为 baseline AI facility energy 的 8.15 倍。

### D5 弃电时段天然偏低碳
Curtailment 与 CarbonIntensity 显著负相关；这支撑“先吸收弃电”而不是新能源/碳/价格主观加权。

### D6 Q3 固定负荷下新能源总体极充足
A--E 全时段 H>=0，F 仅 1 h H<0；结合 SellLimit 自然得到 A/B/C、D/E、F 三类储能机制。

### D7 Q3 baseline 不是终端 SOC 约束下同口径可行优化点
因此必须用 E0/E1 隔离 BESS 增量价值。

### D8 Q4 区域优势错位
低时延、算力规模、PUE、BESS、售电能力并不集中于同一区域；不存在单一最佳 Region。

### D9 Q4 顺序 Q2->Q3 可产生虚假迁移价值
小规模真实 probe 已证明静态 workload 边际价值与 post-BESS recourse value 不一致。

### D10 数据结构不仅决定模型，还决定可计算性
Facility/IT 约束严格重复、Benders dual support 稀疏、合法域约 2.33e8 placements，直接导出 exact presolve / sparse cuts / column generation。

---

## 2. 公共章节必须怎样改

### 2.1 标题
标题不应堆四个算法名。优先围绕：

“异构任务时空柔性—储能时间柔性—计算能源协同调度”

算法名最多保留一个核心求解词作为副标题候选。

### 2.2 摘要
摘要必须体现四问递进和三条关键数据发现，不能写成四段方法清单。

建议摘要逻辑：
1. 数据先验：任务/区域/能源存在明显异构与错配；
2. Q1 提取结构化需求；
3. Q2 释放 workload 柔性；
4. Q3 释放 BESS 柔性；
5. Q4 联合两类柔性；
6. 给出最终数字与验证，不堆算法缩写。

### 2.3 问题重述
必须真实写四问，不允许继续使用通用模板。重述时明确各问“释放哪些决策自由度”：
- Q1 基础；
- Q2 workload；
- Q3 energy/BESS；
- Q4 joint。

### 2.4 模型假设
只保留真正影响模型的 3--6 条，例如：
- 题目给出的 power mapping、PUE、价格、碳强度在对应小时内有效；
- 任务不可抢占/拆分、中途不迁移；
- 网络只用题给 latency/SLA，不虚构带宽/迁移能耗；
- Q1 短期窗口内到达结构局部稳定；
- 不修改附件 raw baseline 的异常值，只在优化中使用正式初始条件。

### 2.5 符号表
集中统一 `x_{irs}, L_{rt}, H_{rt}, E_{rt}, Cost, Carbon, eta_R, Wait, Latency` 等跨问符号，避免四问各自重复改名。

### 2.6 模型评价
优点必须具体写：
- 数据结构驱动而不是套模型；
- Q2/Q3 分离识别两类柔性，Q4 再联合；
- 不使用主观权重；
- 完整合法域不裁剪；
- 结果有 hard-audit / exact benchmark / multi-start / recourse check。

局限必须真实写：
- Q1 仅 24 h test；
- Q2 构造式启发式存在初始化路径依赖；
- Q4 50k 全局整数最优尚未证明，需报告 root LB / integer UB / gap；
- 场景结论仅对题给数据和透明构造有效。

### 2.7 参考文献
至少按四类补齐：
- marked/compound Poisson / hierarchical demand modeling；
- carbon-aware workload scheduling；
- BESS economic dispatch / exact relaxation；
- Benders / column generation / multi-cut / stabilization。

禁止只剩通用建模教材。

---

## 3. 全文图的角色分配

每问正文图都只承担三类角色：

### A. 为什么这样建模（Data evidence）
Q1 Region×Type / Poisson；Q2 弃电购电错配；Q3 H+SellLimit；Q4 区域结构矩阵/顺序优化失真。

### B. 算法是否可信（Method evidence）
Q1 prediction interval；Q2 convergence/multi-start；Q3 SOC/constraint audit；Q4 exact benchmark / closure。

### C. 模型带来了什么（Result evidence）
Q1 GPU utilization；Q2 migration + Cost/Carbon；Q3 BESS value + grid interaction；Q4 Q2/Q3/Q4 unified comparison + scenarios。

不要把同一个数值用柱图、散点、表格重复三次。

---

## 4. 跨问必须统一的口径

- 时域：0--2399 arrivals；2400--2405 drain；2406 energy terminal settlement only；
- Cost/Carbon/RenewableUtilization 的统计时域和公式；
- Baseline / B0 / reference 的命名；
- PeakImport 定义；
- RT immediate-start；
- “global optimum”只能在有 certificate 时使用；
- Q2 不是 energy dispatch，Q3 不是 workload scheduling，Q4 才联合。

---

## 5. 总论文最终验收问题

评委只看摘要、每问第一张数据图、流程图和结果表时，应能回答：
1. 这题的数据里最关键的非显然关系是什么？
2. 这些关系分别改变了哪些模型结构？
3. 为什么 Q2/Q3 不能直接替代 Q4？
4. 为什么不使用 AHP/熵权/六指标加权？
5. 为什么算法复杂度是数据规模与结构逼出来的，而不是为了炫技？

若这五点不能从论文直接看出，即使代码正确也不算全文完成。
