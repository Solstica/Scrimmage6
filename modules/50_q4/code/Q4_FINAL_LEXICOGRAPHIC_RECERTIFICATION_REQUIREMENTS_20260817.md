# Q4 最终字典序再认证要求（P0，2026-08-17）

## 0. 目的

当前 `region_multicut_v1` 已证明 6-region multi-cut + full-domain Wait/Latency repricing 的修正方向有效，但最新远端仅到 Latency 阶段运行中 checkpoint，尚不能作为最终 Q4 结果。更重要的是，Wait 阶段新增列后得到的真实能源成本已经优于原 Cost anchor，说明后续扩展列池反向改善了前序整数 Cost 上界。因此最终收尾必须做一次 **final-pool lexicographic recertification**，以保证 `Cost -> Wait -> Latency` 三层在同一扩展列池/完整定价逻辑下自洽。

本要求不改变数学模型、不裁剪合法域、不放宽 cost cap、不增加人工权重，也不要求为了形式强行实现 branch-and-price。

---

## P0-A 当前 Latency run 先闭合

继续现有 `qos_refinement_multicut` 断点，直到同时满足：

1. 所有区域 Benders 违反均不超过声明的 `benders_tol_cny`；
2. 再次执行完整合法域 pricing；
3. `min reduced cost >= -price_tol`；
4. 未发现新的缺失列；
5. restricted MIP 完成，并通过真实 Energy LP 复核。

不要以固定“180轮”等轮数作为闭合标准；轮数只作为运行上限，真正的停止条件必须是 Benders consistency + full-domain pricing 两个门同时通过。

若当前只剩 RegionF tailing-off，先继续现有 multi-cut。除非长时间稳定卡在同一数量级且无实质下降，否则不要提前加入 level/trust-region/其他 stabilization 模块。

---

## P0-B 最终列池三阶段再认证

当当前 Latency 阶段第一次真正闭合后，不直接冻结结果。使用此时已经扩展到约 1.37e5 列的 final active pool 作为 warm start，执行：

### Stage R1：Cost re-certification

- 在当前扩展列池上重新 `min Cost`；
- 真实 Energy LP + Benders 继续闭合；
- 对完整隐式合法域重新做 Cost exact pricing；
- 若找到新负 reduced-cost 列，继续加入并重新闭合；
- 得到新的 best-known integer Cost anchor `C_rec`。

原因：当前 Wait 阶段已经出现真实能源成本比旧 Cost anchor 低约 2.5e4 CNY 的整数方案，证明旧 restricted MIP anchor 不是最终扩展列池上的最佳整数 Cost 上界。

### Stage R2：Wait re-certification

在

`Cost <= C_rec + epsilon_C`

下重新最小化 Total Wait：

- full-domain Wait pricing 必须重新执行；
- Benders / region multi-cut 必须重新闭合；
- restricted MIP 完成并由真实 Energy LP 复核；
- 得到 best-known integer Wait anchor `W_rec`。

### Stage R3：Latency re-certification

在

`Cost <= C_rec + epsilon_C`

和

`Wait <= W_rec + epsilon_W`

下重新最小化 Total Latency：

- full-domain Latency pricing；
- region multi-cut Benders；
- restricted MIP；
- 真实 Energy LP 复核；
- 输出最终代表方案。

若 R1/R2/R3 中任何阶段又产生新列并改善前序 anchor，则继续循环，直到一次完整 `Cost -> Wait -> Latency` sweep 中三层 anchor 都不再变化（在既定数值容差内）。

---

## P0-C 结果口径

50k 结果在没有 branch-and-price/global integer proof 的情况下，禁止写：

- `Cost 全局整数最优`；
- `Wait 全局最优`；
- `Latency 全局最优`；
- `C* / W*`（若符号会让读者理解为全局整数最优）。

推荐表述：

- `完整域 LP 定价闭合`；
- `扩展列池 restricted MIP 可行端点`；
- `final-pool lexicographic recertified representative solution`；
- `best-known integer Cost / Wait / Latency anchor`；
- 明确 `global integer optimum proved = false`。

40-task exact benchmark 仍可使用 exact / optimum 表述。

当前 `Wait = 32 h` 在再认证前只能视为已验证可行的 restricted-integer 字典序端点，不直接称 50k 全局最优等待。

---

## P0-D 最终审计字段必须补齐

最终 `q4_qos_summary.json` / audit 至少显式输出：

### Workload

- task coverage violations；
- GPU capacity violations；
- IT capacity violations；
- SLA region violations；
- earliest/arrival violations；
- LatestFinish violations；
- finish > 2406 violations；
- **RT immediate-start violations：`StartHour == ArrivalHour`**。

### Energy/BESS

- MaxGridImport violation；
- MaxGridExport violation；
- SellLimit violation；
- SOC lower/upper violation；
- terminal SOC violation；
- renewable allocation balance residual；
- facility/load balance residual；
- SOC recursion residual；
- charge power bound violation；
- discharge power bound violation。

### Solver certificate

每个 Stage 输出：

- active columns；
- added columns；
- Benders cuts；
- final max regional Benders violation；
- min missing-column reduced cost；
- LP bound；
- restricted MIP objective；
- MIP gap（若 solver 提供）；
- runtime / peak RSS；
- `global integer optimum proved = false`。

---

## P0-E 可复现结果文件

最终完成后至少提交轻量真源：

- 修正版 Cost root：`summary.json`、`iteration_metrics.csv`、`best_schedule.csv`；
- QoS：`q4_qos_summary.json`、`q4_lexicographic_stage_metrics.csv`、`q4_字典序最终排程.csv`；
- final-pool recertification 的三阶段 summary/trace；
- 40-task exact benchmark 验收 JSON 保持可追溯。

运行中的 `.npz` checkpoint 可用于恢复，但不能代替最终 summary / schedule。

---

## 禁止事项

本轮不得为解决收尾问题而：

- 放宽 `Cost <= anchor + epsilon_C` 以掩盖违反；
- 加主观权重/六指标综合分数；
- 设人工最大等待窗；
- top-k / 固定时间窗裁剪 2.33e8 合法域；
- 退回 Cost-only restricted column pool 做 QoS；
- 把 `restricted_mip_completed` 写成全局整数最优证明。

本轮修改的性质是 **字典序一致性再认证 + 结果审计完善**，不是重新设计 Q4 模型。