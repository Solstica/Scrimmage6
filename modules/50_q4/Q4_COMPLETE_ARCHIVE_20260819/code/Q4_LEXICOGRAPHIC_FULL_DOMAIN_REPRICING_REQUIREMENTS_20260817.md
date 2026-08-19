# Q4 修正要求：字典序阶段必须重新进行完整域定价

状态：`P0 / IMPLEMENTATION_REQUIRED`

目的：修复当前 50k 全规模 Q4 中“Cost root 已对完整域定价，但 QoS/Latency 只在 Cost 活动列池上求 restricted MIP”的实现偏差。该修正不更换 Q4 数学模型，不改掉 Benders + exact column generation，只要求全规模实现忠实对应此前 40-task exact benchmark 已验证的字典序模型。

## 1. 已有数据依据，不得改成六指标等权模型

此前 40-task exact benchmark 使用完整合法 `(region,start)` 候选域，得到：

- Cost-only 任意代表解可出现 `38/40` 迁移、总等待 `172 h`；
- 在 `Cost <= Cost* + tol` 的完整合法域内继续最小总等待，再保持 Cost/Wait 最优最小网络时延，可得到：
  - migrated = `5`；
  - total wait = `6 h`；
  - mean wait = `0.15 h`；
  - max wait = `2 h`；
  - mean latency = `10.925 ms`。

因此当前正式路线仍是数据驱动的层级处理：

`Cost 主层 -> Carbon epsilon-constraint / 场景轴 -> QoS 字典序精化 -> Latency 字典序精化`。

禁止因为当前 50k 结果出现 `max wait = 1171 h` 就直接改成 AHP、熵权、人工加权和、六指标等权 minimax-regret 或其他未经数据探针验证的新多目标模型。

RenewableUtilization 与 PeakNetImport 继续保留为题面要求的评价/候选约束量；是否需要成为独立优化轴，应先做 full-system 辨识力与冲突关系探针，不能预设等权。

## 2. 当前实现偏差

当前 `q4_full_solver.py` 的 Cost 阶段使用完整域 exact pricing，但根节点闭合后活动列仅约 `51,247`，而任务数为 `50,000`。因此 Cost 阶段只为少数任务生成了第二个或更多 placement。

当前 `q4_qos_refinement.py` 直接读取该 Cost 活动列池，在固定列池中执行：

1. `EnergyCost <= C* + tol` 下最小总等待；
2. 保持 Cost/Wait 后最小时延。

它没有为 QoS 或 Latency 阶段重新扫描完整合法 `(task,region,start)` 域。当前结果文件已明确记录：

`成本目标已通过完整域定价的活动列池；QoS 精化未另行做全域零成本列定价`。

这意味着当前 50k “最小等待”只是在 Cost-generated restricted column pool 上的最优，不是完整字典序模型的最优。

TaskID `32861` 是直接诊断例：

- BatchInference；
- ArrivalHour = `119`；
- 当前 Cost 排程：RegionD, StartHour = `1290`；
- 当前 QoS 最终排程仍为 RegionD, StartHour = `1290`；
- 等待 = `1171 h`。

该任务没有被 QoS 阶段改变，当前实现无法据此证明“为了最优成本必须等待 1171 h”。

## 3. 必须实现的三阶段 full-domain lexicographic CG

### Stage A — Cost Benders + exact CG

保持现有实现：

- Master：任务 placement + GPU/IT + Benders cuts；
- Energy subproblem：真实 Renewable/BESS/Grid LP；
- 对完整合法域执行 Cost reduced-cost pricing；
- root 闭合后得到 `C*`、Cost active column pool 和 Cost Benders cuts；
- restricted integer master 只提供整数 incumbent/UB，不得声称全局整数最优，除非有相应证明。

### Stage B — QoS full-domain repricing

在约束

`TrueEnergyCost(x) <= C* + epsilon_C`

下最小化总等待：

`W(x) = sum_i (Start_i - Arrival_i)`。

要求：

1. 不能只在 Cost active columns 上求一次 MIP 后结束；
2. 需要建立 QoS 阶段 RMP/CG 循环；
3. pricing 必须重新扫描每个任务的完整合法区域和完整合法 start domain；
4. QoS reduced cost 中必须包含候选列的等待系数 `s - Arrival_i`，并正确计入 assignment dual、GPU/IT dual、Cost-cap 相关 dual / Benders recourse 信息；
5. Cost 阶段 reduced cost 为 0、但能降低等待的列必须有机会在 QoS 阶段被加入；
6. 每次获得整数候选后必须用真实 Energy LP 复核成本上界；若 Benders underestimator 不足则补 cut 后继续，不得只相信 theta；
7. 直到“无新的 QoS 负 reduced-cost 列 + 当前成本上界真实可行”才允许宣布 QoS stage closed。

若直接做带 Cost-cap 的 exact pricing 推导较复杂，可以采用等价的两层 master/dual formulation，但必须保持完整合法域 exactness；禁止用固定最大等待窗、top-k 起点或经验候选池替代。

### Stage C — Latency full-domain repricing

得到 QoS 最优值 `W*` 后，加入：

`W(x) <= W* + epsilon_W`

并保持 Cost cap，然后最小化总网络时延：

`L(x) = sum_i NetworkLatency(Source_i, ExecRegion_i)`。

要求与 Stage B 相同：

- 重新扫描完整合法域；
- Latency reduced cost 必须包含候选区域的网络时延系数；
- 允许新增 Cost 阶段与 Wait 阶段都未生成的列；
- 完成真实 Energy LP、Cost cap、Wait cap 复核后才能闭合。

最终流程应为：

`Cost-Benders/CG -> Wait-Benders/CG -> Latency-Benders/CG`。

## 4. 第一验收门：必须先复现 40-task exact benchmark

在上 50k 前，先用此前 40-task benchmark 验证新实现。

验收指标：

- 使用与 exact benchmark 相同的 40 个真实任务和完整合法域；
- Cost 阶段目标与 exact Cost 在 solver tolerance 内一致；
- 字典序最终结果应复现或在 solver tolerance 内等价于：
  - migrated = `5`；
  - total wait = `6 h`；
  - mean wait = `0.15 h`；
  - max wait = `2 h`；
  - latency sum = `437 ms`；
  - mean latency = `10.925 ms`。

若新 CG 不能复现这个已知 exact 结果，不得继续 50k，也不得通过改目标函数掩盖实现偏差。

建议新增输出：

- `q4_lexicographic_40task_validation.json`
- 每阶段 active columns；
- 每阶段 new columns；
- min reduced cost；
- Benders cuts；
- true recourse cost；
- Cost/Wait/Latency stage closure flag。

## 5. 第二验收门：50k 修正结果

40-task 闭合后再运行 50k。至少输出：

- `C*`、`epsilon_C`；
- Cost stage active columns；
- Wait stage 新增列数、最终 active columns；
- Latency stage 新增列数、最终 active columns；
- Cost/Wait/Latency 三阶段 runtime 与 peak RAM；
- 最终 true EnergyCost；
- total / mean / P95 / max waiting；
- total / mean network latency；
- migrated tasks；
- GPU/IT/SLA/LatestFinish/finish<=2406 全部违规数；
- SOC、MaxGridImport、MaxGridExport、SellLimit、terminal SOC 审计；
- integrality status / gap 能给则给，不能给就明确 `not proven globally integer optimal`。

重点比较旧结果：

- old total wait = `378,199 h`；
- old mean wait = `7.56398 h`；
- old max wait = `1171 h`；
- old mean latency = `29.13924 ms`；
- old migrated = `37,127`。

只有完成 full-domain Wait/Latency repricing 后，才有资格判断这些 QoS 数值是否是 Cost 主层的真实代价。

## 6. Cost tolerance 暂不拍值，先做实现修复

当前 `--cost-tolerance=1e-3 CNY` 很紧，但现有 1171 h 不能先归因于该容差，因为当前 QoS 阶段没有完整域候选。

修复 full-domain repricing 后，再做 Cost--QoS opportunity curve：

`delta_C = (C-C*)/|C*|`

建议至少测试一组预先声明的相对容差，例如 `0, 1e-7, 1e-6, 1e-5, 1e-4`，记录：

- Cost penalty；
- total / P95 / max wait；
- migrated tasks；
- latency。

该 probe 用来判断极小经济让步能否显著改善服务质量；不得先拍 1%、5% 之类阈值。

## 7. 场景部分暂时保持 DRAFT

当前 `q4_energy_scenarios.py` 固定 QoS 排程后只重算 Energy LP，因此：

- 可以作为条件 energy-recourse probe；
- 不能把 75%/50%/25%/0% 的可行性写成完整联合 Q4 的全局可行性；
- 正式回答“不同碳约束、电价机制、新能源波动场景下策略变化”时，需要允许 workload placement 与 energy/storage 一起重新优化。

场景正式实现等本次 lexicographic full-domain 修复通过后再继续，避免同时改变求解器与场景定义导致无法定位问题。

## 8. 本轮禁止事项

- 不改成六指标等权 minimax-regret；
- 不新增 AHP、熵权、TOPSIS 或人工加权和；
- 不新增最大等待硬窗来强行消除 1171 h；
- 不通过 top-k region/start、缩短合法时间域来降低计算量；
- 不把 Cost restricted pool 上的 Wait/Latency 最优写成 complete-domain lexicographic optimum；
- 不冻结当前 `q4_qos_summary.json` 和固定排程 carbon scenario 数值。

## 9. 修改位置建议

优先修改：

- `modules/50_q4/code/q4_qos_refinement.py`

必要时抽取/复用：

- `q4_full_solver.py::price_all`
- RMP matrix assembly
- Benders cut / true Energy LP validation
- checkpoint / state serialization

建议不要在 `q4_full_solver.py` 中复制三套大段代码；可以将 pricing objective coefficients / cap duals 参数化，使 Cost / Wait / Latency 三阶段复用同一 exact-pricing 基础设施。

结果文件全部保持 `DRAFT / NEEDS_REVIEW`，40-task exact 验收和 50k 全约束审计完成后再申请升级状态。
