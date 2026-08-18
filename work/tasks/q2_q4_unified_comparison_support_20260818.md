# Q2 -> Q4 统一比较支持任务（2026-08-18）

Q4 canonical 已完成两轮 final-pool 再认证。为形成最终 `Q2-only vs Q3-only vs Q4-joint` 比较，Q2 需要提供统一 accounting 的 workload-only 真源，不修改 Q2 模型。

## 已知 Q2 canonical workload 指标

Cost-primary reference-start：

- migration rate ≈ `74.896%`；
- migrated tasks = `37,448`；
- mean wait ≈ `20.47522 h`；
- P95 wait = `76 h`；
- max wait = `2016 h`；
- mean latency ≈ `26.74732 ms`；
- P95 latency = `76 ms`；
- max latency = `82 ms`。

Q4 canonical：

- migration=`61/50000=0.122%`；
- Total/Mean/Max Wait=`0`；
- mean latency=`5.0172 ms`。

该对照将用于解释：储能时间柔性在联合优化中替代了绝大部分 workload 时间/空间调节需求。

## P0 输出统一比较输入

- [ ] 从 `data/processed/q2_schedule_cost_only.csv` 重新生成一份 compact summary，明确 TaskID 覆盖、migration、wait、latency。
- [ ] 重新按最终统一时域核算 Q2 Cost/Carbon/RenewableUtilization/PeakNetImport。
- [ ] 明确 0--2405 scheduling-sensitive accounting 与 2406 terminal energy settlement 的关系。
- [ ] 输出 `q2_unified_comparison_metrics.csv/json`，供 shared/Q4 使用。
- [ ] 不重跑/改变 canonical SFETA 排程，除非发现硬约束或 accounting bug。

## P0 解释边界

- [ ] Q2 高 migration/high wait 不写成算法 bug；它是在储能动作固定条件下 workload flexibility 单独承担能源错配调节的结果。
- [ ] Q4 低 migration/zero wait 不反证 Q2 模型错误；它反映两类柔性的替代关系。
- [ ] Q2/Q4 Cost 不能直接比较未统一 Hour 2406 accounting 的绝对值。
- [ ] Q2 是 workload-only scheduling，不把 Q4 BESS recourse 反向塞回 Q2 模型。

## P1 最终图支持

为 Q4 unified comparison 提供：

- migration rate；
- mean/P95/max wait；
- mean/P95/max latency；
- unified Cost/Carbon/RenewableUtilization/PeakNetImport。

不再额外做 50k 全量 Gantt；若需要典型 Gantt，使用 `q2_schedule_cost_only.csv` 选 48--72 h 代表时窗即可。
