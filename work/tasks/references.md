# references 实时待办

## 当前冻结口径

- `feature/references` 保留研究主库；不得为了最终篇数直接删主库。
- 最终论文子集真源：`modules/70_references/paper/references_final15.tex`。
- 当前子集：**15 篇研究论文 = 中文 4 + 英文 11，全部发表于 2022--2026**。
- 赛题/附件不占“约15篇研究文献”名额，不进入最终 bibliography。
- 最终文献表不显示 DOI/URL；研究主库和支持范围说明中可继续保留 DOI 供核验。

## P0：最终 cite 审计

- [ ] Q1--Q4 最新正文重新扫描全部 `\cite{}`。此前不同分支并行修改后，部分曾加入的引用已被后续正文更新覆盖，不能再依据旧任务记录认定“已引用”。
- [ ] 按 `FINAL_15_REFERENCE_SET_20260818.md` 的问题分工，把引用重新贴到方法/判断第一次出现的位置。
- [ ] 所有附件实证结论只写为本文数据诊断，不用外部文献背书。
- [ ] 每个 `\cite{key}` 必须存在于最终 15 篇子集。
- [ ] 反向检查 15 篇文献均至少有一次正文中的真实用途；若某篇最终不用，用主库中真正支撑正文的近年高水平文献替换，禁止为凑数量硬插。

## P1：推荐引用位置

### Q1
- `wu_survey_2025`：问题分析/地理分布式调度总体定位，可与 Q2 共用。
- `cohen_dac_2022`：训练数据决定参数估计层级的文字说明。
- `zou_poissonity_2022`：Poisson 假设前的时间尺度与相关性诊断说明。

### Q2
- `chen_idc_2022`, `wen_vpp_2024`：IDC 时空柔性和多数据中心低碳协同背景。
- `yang_repta_2026`：SFETA 介绍前，说明 heterogeneous delay tolerance 和领域规则驱动 task assignment 的已有工作。
- `hanafy_carbonscaler_2023`, `sukprasert_limitations_2024`：碳感知计算柔性和其实际收益边界。
- `choudhury_mast_2024`：大规模跨区域 ML 调度的时空/作用域结构利用。

### Q3
- `zhang_dc_bess_2025`：数据中心储能调度与电网灵活性。
- `wang_exact_relax_2024`：充放电互补约束及避免无意义同时充放电的文献背景；正文必须说明本题实际采用的是字典序吞吐量去退化，而非直接套该 exact-relaxation 定理。

### Q4
- `zhou_multiflex_2024`, `guo_integrated_2025`：计算柔性与能源柔性联合优化的领域依据。
- `wang_bcg_2026`：Benders + column generation 组合求解大规模分配/调度结构的现代算法依据。
- `zhang_flex_dro_2024`：正式 renewable fluctuation / uncertainty 场景完成后使用；若最终正文不讨论其分布鲁棒思想，则替换为更贴近最终 scenario 的文献。

## Merge 规则

推荐顺序：

1. Q1--Q4 分支先稳定正文和 cite key；
2. references 分支冻结 `references_final15.tex`；
3. 单向同步为 `feature/paper-shell/modules/70_references/paper/references.tex`；
4. paper-shell 合入 Q1--Q4 正文；
5. 做 cite-key 双向审计和完整编译；
6. 最后冻结 references。

**不要让 Q1--Q4 分支各自编辑 bibliography，也不要依赖 Git 自动合并两份不同的 references.tex。**

## DONE

- [x] 保留较宽的 references 研究主库和 `REFERENCE_GUIDE.md` 支持范围说明。
- [x] 建立 15 篇最终研究文献子集。
- [x] 中文/英文数量满足当前要求，年份统一收敛到 2022--2026。
- [x] `feature/paper-shell` 已同步当前 15 篇子集，等待正文 cite 审计后最终冻结。
