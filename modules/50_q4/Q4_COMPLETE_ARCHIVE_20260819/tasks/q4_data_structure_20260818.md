# Q4 数据结构驱动论文与作图任务（2026-08-18，canonical闭合后更新）

依据：

- `modules/50_q4/paper/DATA_STRUCTURE_PAPER_ENRICHMENT_20260818.md`；
- `modules/50_q4/results/FINAL_RECERTIFICATION_REVIEW_20260818.md`；
- `work/tasks/q4_finalization_20260818.md`。

当前 joint workload--energy--storage canonical 主问题已经闭合，旧“等待 Latency integer Benders”的状态作废。本任务现在只负责把**数据必要性 + 最终柔性替代机制 + 正式场景**做成论文证据，不再推动主算法改造。

## 已完成的正文必要性链

- [x] Training 高 GPU-hour/AI energy 与 RT 刚性写入 Q4 数据分析；
- [x] 区域 AvailableGPU/PUE/latency/BESS/SellLimit 优势错位写入；
- [x] 六区 AvailableRenewable 逐时相同的反直觉事实写入；
- [x] 动态盈余 `H_rt(x)` 随 workload placement 改变写入；
- [x] 3-task/8-combination 顺序 Q2->Q3 失真 probe 写入；
- [x] Energy LP dual -> Benders history 的数值依据写入；
- [x] Facility/IT exact duplicate、dual sparse support、2.33e8 placements 作为可计算性证据写入；
- [x] 50k final-pool 两轮再认证结果写入 `q4.tex`；
- [x] 新机制“储能柔性替代绝大部分 workload 调节”写入正文。

## 最新 canonical 数据

- Cost=`-459340688.8007043 CNY`；
- Wait=`0 h`；
- Total Latency=`250860 ms`；
- migration=`61/50000=0.122%`；
- mean latency=`5.0172 ms`；
- active columns=`137158`；
- cuts=`1173`；
- hard audit PASS；
- Latency LP--integer relative gap≈`0.1555%`；
- global integer optimum 未证明。

对照 Q2 Cost-primary：migration≈74.896%、mean wait≈20.475 h。该对照必须用来解释两类柔性的替代，而不是仅作为两组数字并排。

## P0 必补数据/机制图

### Q4-A 六区域算力—网络—能源—储能结构矩阵
- [ ] 行=Region A--F；
- [ ] 列含 AvailableGPU、PUE、低时延可达性、StorageCapacity、MaxCharge/Discharge、SellLimit、Price/Carbon、baseline Curtailment；
- [ ] 标准化仅用于显示，附原单位；
- [ ] 禁止综合评分；
- [ ] 核心结论：低时延、算力、能效、储能、售电优势错位。

### Q4-B 顺序 Q2->Q3 失真 probe
- [ ] 8 个 E/F placements；
- [ ] Q2 static marginal vs post-BESS true recourse；
- [ ] 旁注 latency；
- [ ] 结论固定为 `Q2 static marginal != Q4 post-BESS recourse value`。

### Q4-C 两类柔性争用/替代同一新能源
- [ ] 以 `H_rt(x)` 为核心画 workload absorption 与 BESS charging 两路；
- [ ] 机制层强调二者既竞争又可替代；
- [ ] 结果层接入 Q2 `74.896% / 20.475h` -> Q4 `0.122% / 0h`。

## P0 最终结果图

### Q4-D final-pool recertification
- [ ] Sweep1/2 Cost anchors；
- [ ] Sweep1/2 Wait anchors；
- [ ] Sweep1/2 Latency anchors；
- [ ] Latency Sweep1 新增19列，Sweep2新增0；
- [ ] final cuts=1173；
- [ ] min reduced cost=0；
- [ ] region Benders violation=0；
- [ ] LP LB=250469.9546 vs integer=250860，gap≈0.1555%。

### Q4-E Q2-only / Q3-only / Q4-joint
- [ ] 必须先统一 Hour2406 accounting；
- [ ] 比较 Cost、Carbon、Wait/QoS、Latency、RenewableUtilization、regional PeakNetImport；
- [ ] workload 侧重点：Q2 高迁移/等待 -> Q4 近零迁移/零等待；
- [ ] Q3 E1 vs Q4 成本差未统一 accounting 前不得标 synergy。

## P0 正式场景图

### Q4-F Carbon constraints
- [ ] joint reoptimization；
- [ ] epsilon budgets 事前冻结；
- [ ] six metrics 统一输出。

### Q4-G Electricity-price mechanisms
- [ ] flat / attachment / transparent peak-valley sensitivity；
- [ ] 参数事前冻结；
- [ ] joint reoptimization。

### Q4-H Renewable fluctuation
- [ ] 保持附件六区原始空间语义；
- [ ] transparent reproducible perturbation；
- [ ] joint reoptimization；
- [ ] `gamma=1.4` 仅 diagnostic。

## P1 算法证据图

- [ ] 40-task exact benchmark 可保留小图/表；
- [ ] Benders + Exact CG 主流程保留；
- [ ] 长轮次 convergence 日志降附录，不能抢 final recertification 图位置。

## WRITER 验收

- [x] 读者在 Benders 前能理解为什么 Q2->Q3 顺序拼接会错；
- [x] q4.tex 已明确 final 50k canonical；
- [x] q4.tex 已明确 global integer optimum 未证明；
- [ ] 读者能从 Q4-A 直接看见“没有单一最佳 Region”；
- [ ] 读者能从 Q4-C/Q4-E 看见“储能替代绝大部分 workload 调节”的最终机制；
- [ ] 正式场景完成后再冻结整问。
