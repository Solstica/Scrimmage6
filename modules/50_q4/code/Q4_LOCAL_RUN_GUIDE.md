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
3. 当前可用内存建议不低于 20 GiB，输出盘可用空间不低于 15 GiB；
4. 依赖版本和附件路径已写入 JSON，便于队友复现。

## 3. 小规模一致性验证

预检通过后，可直接运行现有 40 任务精确基准；它默认写入 `modules/50_q4/results/local_probe`：

    python q4_probe_benders.py "D:\qq文件\2026年武汉理工大学数学建模训练题目7-9\C题附件" "..\results\local_probe"

该程序现在会显示基线重建、全合法候选枚举、稀疏矩阵装配和 Benders 轮次进度。它的用途是验证完整域、分解逻辑和 ABC 压缩依据；不是 5 万任务的最终求解器。

读取 `probe3_summary.json` 时，只有 `benders_converged=true` 才能把相应 Benders 值作为该探针的收敛结果。紧碳预算情景若触及轮次上限，仅可作为数值对照，不可据此报告 Benders 收敛或全局下界。

## 4. 全规模运行门槛

生产版将采用 A（严格支配预处理）、B（稀疏 Benders cuts）、精确定价和受限整数收尾。运行中必须持续记录 active columns、RMP 时间、LB/UB、整数 gap、RSS 和 ETA。

如 active columns 超过 2,000,000、单轮 RMP 超过 10 分钟，或预测超过 10 GiB 推荐内存 / 9 小时时限，应停止并优化列池或稳定化策略；不得通过裁剪合法候选域来绕开该门槛。

## 5. 全规模求解

关闭 GPT 等高内存程序后，直接运行 `q4_full_solver.py`。默认可用内存门槛为 12 GiB，12--16 GiB 会告警，建议至少 16 GiB。它会把实时检查点、每轮指标、当前最优可行排程写入 `modules/50_q4/results/full_run`。默认运行上限是 25 轮、8.5 小时、100 万活动列、10 GiB 进程 RSS；到达任一门槛会保存状态并停止。

输出的 `summary.json` 中只有“根节点闭合”为真时，才表示 LP 列生成已通过完整域定价门禁；`restricted_integer_status` 只说明受限列池整数精化状态。除非另有完整分支定价证明，不得把结果称为全局整数最优。

如达到时间、活动列或 RSS 门槛，或你在一轮结束后手动停止，状态会写入 `checkpoint_state.npz`。恢复时，在同一输出目录的运行配置中添加参数 `--resume`；程序将复用已生成的活动列和 Benders cuts，从下一轮继续，不会重新枚举完整候选域。
