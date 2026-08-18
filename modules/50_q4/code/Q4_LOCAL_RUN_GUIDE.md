# Q4 本机运行说明

状态：`DRAFT / NEEDS_REVIEW`

本目录的预检脚本只读取附件并完整统计合法候选域。它不会构造全部候选列，不会求解 MILP，也不会占用长时间算力。

## 1. 在 PyCharm 或 VS Code 中配置

解释器需要 Python 3.10 及以上，并安装：`numpy`、`pandas`、`scipy`、`openpyxl`、`tqdm`、`psutil`。

直接点击 PyCharm 的运行按钮即可：脚本会默认使用已配置的 C 题附件目录，并把结果写入 `modules/50_q4/results/local_preflight`。如附件目录变更，运行配置的工作目录设为本文件所在的 `modules/50_q4/code`，脚本参数依次为附件目录与结果目录，例如：

    D:\qq文件\2026年武汉理工大学数学建模训练题目7-9\C题附件
    ..\results\local_preflight

也可以在终端中运行：

    python q4_local_preflight.py "D:\qq文件\2026年武汉理工大学数学建模训练题目7-9\C题附件" "..\results\local_preflight"

进度条“统计完整合法候选域”会遍历全部任务，但只累计数量；因此完整域没有被人为裁剪，也不会把 2.33 亿个候选列写入内存。

## 2. 通过预检的条件

1. `q4_preflight.json` 中“零候选任务数”为 0；
2. 候选总数与已记录的 `233,375,201` 保持一致，或任何差异均能追溯到附件版本；
3. 建议当前可用内存不低于 12 GiB；已验证的 Root 进程 RSS 远低于 1 GiB，但整数阶段仍按 10 GiB RSS 硬门槛保护；
4. 依赖版本和附件路径已写入 JSON，便于队友复现。

## 3. 小规模一致性验证

预检通过后，可直接运行现有 40 任务精确基准；它默认写入 `modules/50_q4/results/local_probe`：

    python q4_probe_benders.py "D:\qq文件\2026年武汉理工大学数学建模训练题目7-9\C题附件" "..\results\local_probe"

该程序现在会显示基线重建、全合法候选枚举、稀疏矩阵装配和 Benders 轮次进度，并额外运行 Cost、Wait、Latency 三阶段完整域列生成验收。验收文件为：

    ..\results\local_probe\q4_lexicographic_40task_validation.json

只有其中 `status=PASS`，且迁移数为 5、总等待为 6 h、最大等待为 2 h、总时延为 437 ms，才允许进入 50k。该程序不是 5 万任务的最终求解器。

读取 `probe3_summary.json` 时，只有 `benders_converged=true` 才能把相应 Benders 值作为该探针的收敛结果。紧碳预算情景若触及轮次上限，仅可作为数值对照，不可据此报告 Benders 收敛或全局下界。

## 4. 全规模运行门槛

生产版将采用 A（严格支配预处理）、B（稀疏 Benders cuts）、精确定价和受限整数收尾。运行中必须持续记录 active columns、RMP 时间、LB/UB、整数 gap、RSS 和 ETA。

如 active columns 超过 2,000,000、单轮 RMP 超过 10 分钟，或预测超过 10 GiB 推荐内存 / 9 小时时限，应停止并优化列池或稳定化策略；不得通过裁剪合法候选域来绕开该门槛。

## 5. 全规模求解

先运行修正版 `q4_full_solver.py` 得到 Cost 阶段。旧 `results/full_run` 使用过宽松的相对 Benders 门槛，在仍有约 4030 CNY recourse 违反时提前闭合，不能作为新字典序脚本的输入。不要对旧状态使用 `--resume`，建议写入新目录。

PyCharm 的“脚本参数”可填写：

    --output-dir ..\results\full_run_corrected --benders-tol-cny 0.001

工作目录设为 `modules/50_q4/code`。默认附件路径已写在脚本顶部，因此附件未移动时不需要再传路径。默认运行上限是 25 轮、8.5 小时、100 万活动列、10 GiB 进程 RSS。

输出的 `summary.json` 中只有“根节点闭合”为真时，才表示 LP 列生成已通过完整域定价门禁；`restricted_integer_status` 只说明受限列池整数精化状态。除非另有完整分支定价证明，不得把结果称为全局整数最优。

如达到时间、活动列或 RSS 门槛，或你在一轮结束后手动停止，状态会写入 `checkpoint_state.npz`。恢复时，在同一输出目录的运行配置中添加参数 `--resume`；程序将复用已生成的活动列和 Benders cuts，从下一轮继续，不会重新枚举完整候选域。

## 6. Wait 与 Latency 完整域字典序运行

Cost 阶段成功后运行 `q4_qos_refinement.py`。PyCharm 脚本参数填写：

    --input-dir ..\results\full_run_corrected --output-dir ..\results\qos_refinement_multicut

该脚本执行：

1. 在真实能源成本上界内最小化总等待，并重新扫描全部合法区域和开工时刻；
2. 保持成本和等待上界后最小化总网络时延，再次扫描完整合法域；
3. 每轮按 RegionA--RegionF 分别复核真实 Energy LP；对每个违反区域同时补 region Benders cut，回到 RMP 和完整域定价；
4. 输出 `q4_lexicographic_stage_metrics.csv`、`q4_qos_summary.json` 和 `q4_字典序最终排程.csv`。

该版本使用 6 个区域 recourse 变量，成本约束为六区 theta 之和；不能直接恢复旧版 `qos_refinement` 的 aggregate-cut 断点。程序在每个完整轮次后写入 `lexicographic_state.npz`。中断后保持相同输入和新输出目录，并在脚本参数末尾增加：

    --resume

恢复只从最后完整保存的轮次继续。`restricted_mip_completed` 仍不等于全局整数最优证明，最终结果保持 `DRAFT / NEEDS_REVIEW`。

当前版本默认 `max-stage-iter=0`、`max-hours=0`、`integer-time-limit-s=0`，即不再按轮数、总时长或单次 MIP 时长提前结束。Latency 真正闭合后会自动启动 final-pool 再认证，已有再认证断点时自动恢复。对第 180 轮旧断点，PyCharm 只保留一个参数：

    --resume

如果旧断点没有保存 Wait 阶段真实可行排程，程序会先在当前扩展列池自动重建一次，生成 `q4_latency_feasible_incumbent.json/csv`，再继续 Latency。每次 Latency 整数候选还会写入 `q4_latency_integer_certificate.csv`，其中包含真实可行上界、MIP 下界、Gap、成本上界违反和 RegionE/RegionF 违反。只有出现 `stage_completed` 才正常结束；活动列、RSS 等安全门槛仍然保留。

## 7. final-pool 字典序再认证

只有 `qos_refinement_multicut/checkpoint.json` 的状态已是 `FINISHED_DRAFT`，才能运行 `q4_final_recertification.py`。正常情况下 `q4_qos_refinement.py` 会自动接续该脚本；本节命令只用于单独调试或手动恢复再认证。它不会覆盖 QoS 运行目录，而是把当时的扩展列池作为 warm start，写入新的 `qos_final_recertification` 目录。

PyCharm 脚本参数填写：

    --input-dir ..\results\qos_refinement_multicut --output-dir ..\results\qos_final_recertification

工作目录仍设为 `modules/50_q4/code`。该程序按 R1 Cost、R2 Wait、R3 Latency 顺序运行；第一轮建立新的三个 best-known integer anchor，第二轮再次完整 sweep。只有一整轮中三个 anchor 都未变化，才会写出 `FINISHED_DRAFT`。

每轮进度条显示：`vmax` 为最大区域 Benders 违反，`vr` 为主导区域，`lp` 为当前 LP 目标，`ec` 为真实能源成本，`cols` 为活动列数，`cuts` 为 Benders cut 数，`new` 为新增列数，`rc` 为最小缺失列约化成本，`rss` 为进程内存。判定闭合需要同时看到 `vmax <= 0.001`，完整域定价后的 `rc >= -1e-7`，并随后完成 restricted MIP 和真实 Energy LP 复核。

再认证同样默认不限阶段轮数、总时长、单次 MIP 时长和 sweep 数。若程序被手动停止，保持输出目录不变，只需使用 `--resume`；不需要再递增任何轮数参数。

最终轻量结果为 `q4_qos_summary.json`、`q4_字典序最终排程.csv`、`q4_recertification_stage_metrics.csv` 和各 `sweep_*_summary.json`。其中的口径是 final-pool recertified representative solution，`全局整数最优已证明` 始终为 `false`。
