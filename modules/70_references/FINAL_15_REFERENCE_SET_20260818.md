# 第9题最终参考文献子集与合并规则（2026-08-18）

状态：`CURATED / PENDING FINAL CITE AUDIT`

## 1. 分支职责

- `feature/references`：参考文献研究主库、支持范围说明和最终引用子集的真源。
- `modules/70_references/paper/references.tex`：继续保留较宽的研究主库，不为最终篇数要求裁掉历史候选。
- `modules/70_references/paper/references_final15.tex`：面向最终论文的 15 篇研究文献子集。
- `feature/q1`--`feature/q4`：正文只写稳定的 `\cite{key}`，不各自维护 bibliography。
- `feature/paper-shell`：在总装阶段复制最终引用子集，并做 `cite-key -> bibliography` 双向审计。

这样可以避免多个问题分支同时编辑同一个 `references.tex` 导致 merge 覆盖。

## 2. 当前数量与年份

最终子集严格保留 **15 篇研究论文**：

- 中文研究论文：4；
- 英文研究论文：11；
- 年份：全部为 2022--2026。

赛题及附件属于本文原始问题来源，不占用“约15篇研究文献”的名额，也不放入最终 bibliography。中文来源集中在《中国电机工程学报》《电力系统自动化》《电网技术》，英文来源包括 IEEE TPDS、Operations Research、Applied Energy、Energy、Omega、EuroSys、OSDI、POMACS 等。

## 3. 按问题分工

### 总览与 Q1 工作负载统计/预测
- `wu_survey_2025`：支持 geo-distributed task scheduling 中网络条件、区域资源与调度目标异质性的总体研究定位。
- `cohen_dac_2022`：支持根据数据结构选择参数聚合/估计层级，不等于本题采用 DAC 算法。
- `zou_poissonity_2022`：支持 Poisson 假设必须结合时间尺度、相关性与实际工作负载诊断；不直接证明本附件一定服从 Poisson。

### Q2 时空任务柔性与碳/能源感知
- `chen_idc_2022`：中文总框架，支持 IDC 负荷的时空可转移性与算电协同研究定位。
- `wen_vpp_2024`：支持多数据中心时空协同与低碳经济调度研究方向。
- `yang_repta_2026`：支持 delay-tolerance 异质性、时空任务分配和领域规则驱动快速调度；本题不可照搬其 RES 空间互补假设。
- `hanafy_carbonscaler_2023`：支持计算负荷柔性用于碳效率优化以及延迟/服务代价需要同时审视。
- `sukprasert_limitations_2024`：支持碳感知时空迁移存在实际收益边界，避免把“可迁移”写成无条件巨大收益。
- `choudhury_mast_2024`：支持超大规模跨区域 ML 任务调度需要利用时空/作用域结构，而非显式穷举全部调度变量。

### Q3 固定负荷储能调度
- `zhang_dc_bess_2025`：支持数据中心 BESS 的最优调度和电网灵活性价值。
- `wang_exact_relax_2024`：支持储能充放电互补约束及连续松弛/物理可行性讨论；本题最终采用字典序吞吐量去退化，不应声称直接使用该论文的 exact-relaxation 定理。

### Q4 算力—储能联合优化与场景
- `zhou_multiflex_2024`：支持激活数据中心多元柔性并进行协同运行的中文研究背景。
- `zhang_flex_dro_2024`：支持数据中心集群灵活边界和可再生不确定性下的调度框架；主要用于正式 renewable scenario 讨论，不应覆盖本题附件确定性主场景。
- `guo_integrated_2025`：直接支持 workload transfer 与 energy dispatch 之间存在耦合和相互影响，是 Q4 联合优化最直接的领域依据之一。
- `wang_bcg_2026`：支持 Benders decomposition 与 column generation 可以组合处理大规模分配/调度结构；本题的区域 energy recourse 与 task-placement pricing 仍由附件结构重新推导。

## 4. 正文引用纪律

1. 文献必须贴近方法或研究判断第一次出现的位置，不设“文献堆砌段”。
2. 附件实证结论（如 91.9% 弃电与购电并存、六区 AvailableRenewable 同时刻相同、Training GPU-hour 占比等）不由外部文献背书，直接写为本文数据诊断。
3. 写法优先采用“已有研究说明 X；而本题附件具有 Y，因此本文只借鉴 Z”，明确文献与本题的边界。
4. 最终正文不为凑数量强行引用；如果某条最终未被正文实际使用，则从 `references_final15.tex` 删除并用主库中真正被使用的候选替换。
5. 最终提交 bibliography 按老师要求保持统一格式，不显示 DOI/URL。

## 5. Merge 顺序

推荐总装顺序：

1. Q1--Q4 各分支先稳定正文和 cite key；
2. `feature/references` 冻结最终引用子集；
3. 将 `references_final15.tex` 同步为 `feature/paper-shell/modules/70_references/paper/references.tex`；
4. 合并/复制 Q1--Q4 正文进入 paper-shell；
5. 扫描全部 `\cite{}`：每个 key 必须存在；
6. 反向扫描 bibliography：每条最终文献必须至少被正文一次实际引用；
7. 完整编译后再冻结 references。

原则：不要依赖 Git 自动 merge 两份不同 bibliography。最终 `references.tex` 由 references 分支单向同步到 paper-shell。
