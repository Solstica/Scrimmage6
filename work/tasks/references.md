# references 实时待办

## TODO
- [ ] 最终合并前逐一核对正文全部 `\cite{}` 键是否存在、是否真正支撑对应句子，并删除最终正文未引用的候选文献。
- [ ] 对 `problem` 及中文网页/报刊来源补齐最终提交所需的题名、发布日期和访问日期格式；若正文未使用则从最终 bibliography 删除。
- [ ] Q4 正式三类场景完成后，若引入鲁棒/不确定性方法，只从当前已登记的 Han 2025/2026 等文献中选择真正使用者，不因“场景分析”自动扩充参考文献。

## NEEDS_REVIEW
- [ ] 当前 `feature/references` 保留的是“研究主库”，包含正文已用和曾作为备选的方法文献；最终 `paper-shell` 应只保留实际被正文引用的子集。
- [ ] 若 SFETA 名称最终保留，正文首次介绍算法时已引用 REPTA 来源；是否还需引用 `chen_feta_2020` 说明 FETA 命名冲突，视最终是否讨论命名来源决定。
- [ ] Q1 的 marked Poisson、数据聚合与 coherent forecasting 已进入正文引用；经典 Poisson 基础公式不需要为了凑数量额外引用教材。

## DONE
- [x] 恢复此前已整理但未合入总模板的完整 bibliography：Q1 概率预测、Q2 地理分布式/碳感知调度、Q3 储能、Q4 联合优化等文献均保留在本分支。
- [x] 合并此前单独保存的 Q4 联合优化/Benders 文献，并补入 Benders (1962) 与 Dantzig--Wolfe (1960) 经典方法出处。
- [x] Q1 正文算法入口已加入 `taddy_marked_2012`、`zou_poissonity_2022`、`cohen_dac_2022`、`bertani_jbu_2025`。
- [x] Q2 正文算法入口已加入 `yang_repta_2026` 与 `hanafy_carbonscaler_2023`，并明确只借鉴任务柔性响应思想，不用文献覆盖附件数据结构。
- [x] Q3 正文算法入口已加入 `zhang_dc_bess_2025`、`vaicys_convex_bess_2024`、`wang_exact_relax_2024`。
- [x] Q4 正文算法入口已加入 `guo_integrated_2025`、`niu_benders_2021`、`ji_marginal_2021`、`benders_1962`、`dantzig_wolfe_1960`。
- [x] `paper-shell` 已从 3 条模板文献切换到 references 分支的真实文献体系；最终仍需按实际引用裁剪。
