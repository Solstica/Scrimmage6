#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Q4 本机全规模运行前预检。

只统计完整合法候选域，不显式建立候选列或优化模型，适合先在
PyCharm / VS Code 的本机终端中确认附件、依赖和硬件条件。

用法：
    python q4_local_preflight.py <附件目录> [输出目录]
"""
from __future__ import annotations

import json
import math
import os
import platform
import shutil
import sys
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from time import perf_counter

import numpy as np
import pandas as pd
import psutil
import scipy
import tqdm
from tqdm.auto import tqdm as progress


REGIONS = ("RegionA", "RegionB", "RegionC", "RegionD", "RegionE", "RegionF")
REQUIRED_FILES = {
    "任务轨迹": "workload_trace.xlsx",
    "GPU 中心": "GPU_information.xlsx",
    "网络时延": "network_latency.xlsx",
    "任务功率映射": "power_mapping.xlsx",
    "区域时序": "region_time_data.xlsx",
    "储能信息": "storage_information.xlsx",
}
REQUIRED_WORKLOAD_COLUMNS = {
    "TaskID", "TaskType", "ArrivalHour", "EstimatedDuration_min",
    "SourceRegion", "MaxLatency_ms", "LatestFinishHour",
}
DEFAULT_ATTACHMENT_DIR = Path(r"D:\qq文件\2026年武汉理工大学数学建模训练题目7-9\C题附件")
DEFAULT_OUTPUT_DIR = Path(__file__).resolve().parents[1] / "results" / "local_preflight"


def fatal(message: str) -> None:
    raise SystemExit(f"预检失败：{message}")


def count_starts(task_type: str, arrival: int, duration_h: float, latest_finish: float) -> int:
    """返回该任务在单个合法区域内的完整整数开工时刻数。"""
    horizon_finish = min(float(latest_finish), 2406.0)
    if task_type == "RealTimeInference":
        return int(arrival + duration_h <= horizon_finish + 1e-9)
    last_start = math.floor(horizon_finish - duration_h + 1e-10)
    return max(0, last_start - arrival + 1)


def main() -> None:
    if len(sys.argv) > 3:
        fatal("用法：python q4_local_preflight.py [附件目录] [输出目录]")
    attach = Path(sys.argv[1]).expanduser().resolve() if len(sys.argv) > 1 else DEFAULT_ATTACHMENT_DIR
    out = Path(sys.argv[2]).expanduser().resolve() if len(sys.argv) > 2 else DEFAULT_OUTPUT_DIR
    if len(sys.argv) == 1:
        print(f"未传入参数，使用默认附件目录：{attach}")
    if not attach.is_dir():
        fatal(f"附件目录不存在：{attach}")
    out.mkdir(parents=True, exist_ok=True)

    missing = {label: filename for label, filename in REQUIRED_FILES.items() if not (attach / filename).is_file()}
    if missing:
        fatal("缺少附件：" + "；".join(f"{label} ({filename})" for label, filename in missing.items()))

    started = perf_counter()
    workload = pd.read_excel(attach / REQUIRED_FILES["任务轨迹"])
    absent = sorted(REQUIRED_WORKLOAD_COLUMNS - set(workload.columns))
    if absent:
        fatal("workload_trace.xlsx 缺少字段：" + ", ".join(absent))
    if workload.empty:
        fatal("workload_trace.xlsx 没有任务记录")
    if workload["TaskID"].duplicated().any():
        fatal("TaskID 存在重复，无法进行一任务一列组的统计")

    latency_raw = pd.read_excel(attach / REQUIRED_FILES["网络时延"], sheet_name="network_latency")
    latency_required = {"FromRegion", "ToRegion", "NetworkLatency_ms"}
    if not latency_required.issubset(latency_raw.columns):
        fatal("network_latency 工作表缺少 FromRegion、ToRegion 或 NetworkLatency_ms")
    try:
        latency = latency_raw.pivot(index="FromRegion", columns="ToRegion", values="NetworkLatency_ms").loc[REGIONS, REGIONS]
    except KeyError as exc:
        fatal(f"network_latency 未覆盖六个标准区域：{exc}")
    if latency.isna().any().any():
        fatal("network_latency 存在缺失时延")

    total_candidates = 0
    no_candidate = []
    by_type = Counter()
    by_source = Counter()
    legal_region_hist = Counter()
    start_hist = Counter()
    type_task_count = Counter()
    type_duration_h = defaultdict(float)
    invalid_rows = []

    columns = list(workload.columns)
    ix = {name: columns.index(name) for name in REQUIRED_WORKLOAD_COLUMNS}
    rows = workload.itertuples(index=False, name=None)
    for row_number, row in enumerate(progress(rows, total=len(workload), desc="统计完整合法候选域", unit="任务"), start=2):
        task_id = row[ix["TaskID"]]
        task_type = str(row[ix["TaskType"]])
        source = str(row[ix["SourceRegion"]])
        try:
            arrival = int(row[ix["ArrivalHour"]])
            duration_h = float(row[ix["EstimatedDuration_min"]]) / 60.0
            deadline = float(row[ix["LatestFinishHour"]])
            max_latency = float(row[ix["MaxLatency_ms"]])
        except (TypeError, ValueError):
            invalid_rows.append({"行号": row_number, "TaskID": str(task_id), "原因": "到达、时长、截止或时延字段不可转换为数值"})
            continue
        if source not in REGIONS or not np.isfinite(duration_h) or duration_h <= 0 or not np.isfinite(deadline) or not np.isfinite(max_latency):
            invalid_rows.append({"行号": row_number, "TaskID": str(task_id), "原因": "区域非法或时长/截止/时延非法"})
            continue
        legal_regions = int((latency.loc[source].to_numpy(dtype=float) <= max_latency + 1e-9).sum())
        feasible_starts = count_starts(task_type, arrival, duration_h, deadline)
        candidates = legal_regions * feasible_starts
        total_candidates += candidates
        by_type[task_type] += candidates
        by_source[source] += candidates
        legal_region_hist[str(legal_regions)] += 1
        start_hist[str(feasible_starts)] += 1
        type_task_count[task_type] += 1
        type_duration_h[task_type] += duration_h
        if candidates == 0:
            no_candidate.append({"TaskID": str(task_id), "TaskType": task_type, "SourceRegion": source, "合法区域数": legal_regions, "合法开工数": feasible_starts})

    if invalid_rows:
        sample = invalid_rows[:10]
        fatal("发现非法任务记录，示例：" + json.dumps(sample, ensure_ascii=False))

    vm = psutil.virtual_memory()
    disk = shutil.disk_usage(out)
    process = psutil.Process(os.getpid())
    disk_free_gib = disk.free / 1024 ** 3
    ram_gib = vm.total / 1024 ** 3
    available_gib = vm.available / 1024 ** 3
    warnings = []
    if no_candidate:
        warnings.append(f"有 {len(no_candidate)} 个任务没有合法候选，正式求解前必须修复数据或模型口径。")
    if available_gib < 20:
        warnings.append("当前可用内存低于 20 GiB；建议关闭高占用程序后再启动全规模求解。")
    if ram_gib < 24:
        warnings.append("物理内存低于 24 GiB；不建议直接运行全规模列生成。")
    if disk_free_gib < 15:
        warnings.append("输出盘可用空间低于 15 GiB；日志、检查点和结果可能无法安全落盘。")

    report = {
        "状态": "DRAFT / NEEDS_REVIEW",
        "生成时间_UTC": datetime.now(timezone.utc).isoformat(),
        "附件目录": str(attach),
        "输出目录": str(out),
        "计算口径": {
            "候选域": "所有满足 SLA 时延、任务到达、截止时间和 finish<=2406 的 (任务, 区域, 整数开工时刻)",
            "禁止压缩": ["top-k 候选裁剪", "最大等待窗口裁剪", "最近区域裁剪"],
            "显式列": False,
        },
        "数据检查": {
            "任务总数": int(len(workload)),
            "任务类型数": int(workload["TaskType"].nunique()),
            "零候选任务数": int(len(no_candidate)),
            "零候选任务示例_最多20条": no_candidate[:20],
            "每任务合法区域数分布": dict(sorted(legal_region_hist.items(), key=lambda item: int(item[0]))),
            "每任务合法开工数分布": dict(sorted(start_hist.items(), key=lambda item: int(item[0]))),
        },
        "完整候选域统计": {
            "候选总数": int(total_candidates),
            "按任务类型候选数": dict(sorted(by_type.items())),
            "按源区域候选数": dict(sorted(by_source.items())),
            "按任务类型任务数": dict(sorted(type_task_count.items())),
            "按任务类型总时长_h": {key: float(value) for key, value in sorted(type_duration_h.items())},
        },
        "本机环境": {
            "操作系统": platform.platform(),
            "Python": sys.version.split()[0],
            "NumPy": np.__version__,
            "pandas": pd.__version__,
            "SciPy": scipy.__version__,
            "tqdm": tqdm.__version__,
            "逻辑CPU核数": psutil.cpu_count(logical=True),
            "物理CPU核数": psutil.cpu_count(logical=False),
            "物理内存_GiB": round(ram_gib, 2),
            "当前可用内存_GiB": round(available_gib, 2),
            "预检进程RSS_MiB": round(process.memory_info().rss / 1024 ** 2, 2),
            "输出盘可用空间_GiB": round(disk_free_gib, 2),
        },
        "运行门槛": {
            "目标峰值RAM_GiB": "4-8（ABC 压缩后的工程目标）",
            "推荐RAM上限_GiB": 10,
            "绝对RAM上限_GiB": 20,
            "目标总时长_h": "6-8",
            "绝对总时长上限_h": 9,
            "停止并优化条件": ["active columns 超过 2,000,000", "单轮 RMP 超过 10 分钟", "运行预测超过内存或时间上限"],
        },
        "告警": warnings,
        "耗时_s": round(perf_counter() - started, 3),
    }
    json_path = out / "q4_preflight.json"
    json_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({
        "状态": report["状态"],
        "任务总数": report["数据检查"]["任务总数"],
        "候选总数": report["完整候选域统计"]["候选总数"],
        "零候选任务数": report["数据检查"]["零候选任务数"],
        "告警": warnings,
        "结果文件": str(json_path),
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
