#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""等待 renew_down_80 当前求解结束，并自动接力生成正式证书。"""
from __future__ import annotations

import argparse
import json
import subprocess
import time
from pathlib import Path

import psutil


HERE = Path(__file__).resolve().parent
ROOT = HERE.parent / "results" / "formal_scenarios"
SID = "renew_down_80"


def read_json(path: Path) -> dict:
    if not path.is_file():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def q4_processes() -> list[dict]:
    rows = []
    for proc in psutil.process_iter(["pid", "cmdline", "memory_info"]):
        try:
            cmd = [str(x) for x in (proc.info["cmdline"] or [])]
            joined = " ".join(cmd).lower()
            relevant = ("q4_full_solver.py" in joined or "q4_ca.py" in joined) and SID in joined
            if relevant:
                rows.append({"pid": proc.pid, "cmd": cmd,
                             "rss_gib": proc.info["memory_info"].rss / 1024 ** 3})
        except (psutil.AccessDenied, psutil.NoSuchProcess):
            continue
    return rows


def show_state(checkpoint: Path) -> tuple:
    row = read_json(checkpoint)
    latest = row.get("最新") or {}
    state = (row.get("状态"), row.get("轮次"), row.get("活动列数"),
             row.get("Benders切数"), latest.get("violation_cny"),
             latest.get("elapsed_min"), checkpoint.stat().st_mtime if checkpoint.is_file() else None)
    print(
        f"[监测] 状态={state[0]} | 轮次={state[1]} | 活动列={state[2]} | "
        f"cuts={state[3]} | Benders违反={state[4]} CNY | 本段分钟={state[5]}",
        flush=True,
    )
    return state


def wait_current(checkpoint: Path, interval: float) -> None:
    last = None
    while True:
        running = q4_processes()
        if not running:
            print("[接力] 当前 renew_down_80 进程已退出，开始检查结果。", flush=True)
            return
        state = show_state(checkpoint)
        if state == last:
            print(f"[心跳] 进程仍在运行 | PID={','.join(str(x['pid']) for x in running)} | "
                  f"RSS={sum(x['rss_gib'] for x in running):.2f} GiB", flush=True)
        last = state
        time.sleep(interval)


def certificate_pass(root: Path) -> bool:
    path = root / SID / "latency_certificate" / "latency_certificate.json"
    return read_json(path).get("状态") == "PASS"


def run_cert(py: Path, root: Path) -> int:
    command = [str(py), str(HERE / "q4_ca.py"), "--scenario", SID,
               "--output-root", str(root)]
    print("[接力] 启动 renew_down_80 恢复/认证；实时输出如下。", flush=True)
    return subprocess.run(command, cwd=str(HERE.parent), check=False).returncode


def write_status(path: Path, payload: dict) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="Q4 renew_down_80 自动接力与证书生成")
    parser.add_argument("--python", type=Path, default=Path(r"D:\python3.12.7\python.exe"))
    parser.add_argument("--output-root", type=Path, default=ROOT)
    parser.add_argument("--poll-seconds", type=float, default=30.0)
    parser.add_argument("--max-resumes", type=int, default=2,
                        help="当前进程退出后最多再自动续跑几个30分钟分段")
    args = parser.parse_args()
    if args.poll_seconds <= 0 or args.max_resumes < 0:
        raise SystemExit("poll-seconds 必须大于0，max-resumes 不能小于0")
    root = args.output_root.resolve()
    scenario = root / SID
    solver = scenario / "solver"
    checkpoint = solver / "checkpoint.json"
    status_path = scenario / "auto_certificate_status.json"
    scenario.mkdir(parents=True, exist_ok=True)
    write_status(status_path, {"状态": "WAITING_CURRENT", "最大自动续跑分段": args.max_resumes})
    wait_current(checkpoint, args.poll_seconds)
    if certificate_pass(root):
        write_status(status_path, {"状态": "PASS", "说明": "正式证书原已存在"})
        print("[正式完成] renew_down_80 证书已经通过，无需重复运行。", flush=True)
        return
    for attempt in range(args.max_resumes + 1):
        summary = read_json(solver / "summary.json")
        closed = bool(summary.get("根节点闭合"))
        if not closed and attempt >= args.max_resumes:
            payload = {"状态": "NEEDS_REVIEW", "原因": "达到自动续跑分段上限，根节点仍未闭合",
                       "已自动续跑分段": attempt, "根节点汇总": summary}
            write_status(status_path, payload)
            print("[自动停止] 已达到续跑上限，根节点仍未闭合；保留全部 checkpoint。", flush=True)
            raise SystemExit(2)
        write_status(status_path, {"状态": "CERTIFYING" if closed else "RESUMING_ROOT",
                                   "第几个自动分段": attempt + 1, "根节点闭合": closed})
        code = run_cert(args.python.resolve(), root)
        if certificate_pass(root):
            cert = read_json(scenario / "latency_certificate" / "latency_certificate.json")
            write_status(status_path, {"状态": "PASS", "自动续跑分段": attempt,
                                       "Latency证书": cert})
            print("[正式完成] renew_down_80 的 Cost、Wait、Latency 证书均已生成并通过。", flush=True)
            return
        if code != 0:
            write_status(status_path, {"状态": "ERROR", "返回码": code,
                                       "说明": "认证脚本异常退出，结果文件均已保留"})
            raise SystemExit(code)
    raise SystemExit(2)


if __name__ == "__main__":
    main()
