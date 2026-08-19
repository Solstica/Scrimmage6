#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Q4 三个正式约束情景的有限时长分析入口。

只分析价格峰谷和新能源上下浮动。Cost 先用完整域 LP 下界与 canonical
整数排程的真实能源上界做证书；证书通过后才运行 Latency 阶段。
"""
from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import q4_formal_scenarios as fs  # noqa: E402
import q4_full_solver as full  # noqa: E402
import q4_qos_refinement as qos  # noqa: E402

SCENS = ("price_peak_valley", "renew_down_80", "renew_up_120")
ROOT_H = 0.5
B_TOL = 0.006
P_TOL = 1e-7
C_TOL = 0.001


def sha(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def stat(attach: Path, spec: dict) -> dict:
    book = pd.read_excel(attach / "region_time_data.xlsx")
    out = {"场景": spec["id"], "附件目录": str(attach), "文件哈希": {}}
    for name in ("region_time_data.xlsx", "workload_trace.xlsx", "network_latency.xlsx",
                 "GPU_information.xlsx", "power_mapping.xlsx", "storage_information.xlsx"):
        out["文件哈希"][name] = sha(attach / name)
    out["参数统计"] = {}
    for col in ("ElectricityPrice_CNY_per_MWh", "AvailableRenewable_MW"):
        g = book.groupby("Region")[col].agg(["mean", "std", "min", "max"])
        out["参数统计"][col] = {str(k): {str(c): float(v) for c, v in row.items()} for k, row in g.iterrows()}
    out["与canonical附件不同"] = bool(sha(attach / "region_time_data.xlsx") != sha(fs.solver.DEFAULT_ATTACH / "region_time_data.xlsx"))
    return out


def run_root(spec: dict, att: Path, out: Path, py: Path) -> int:
    out.mkdir(parents=True, exist_ok=True)
    resume = (out / "checkpoint_state.npz").is_file() and not (
        (out / "summary.json").is_file()
        and json.loads((out / "summary.json").read_text(encoding="utf-8")).get("根节点闭合")
    )
    cmd = [str(py), str(HERE / "q4_full_solver.py"), "--attachment-dir", str(att), "--output-dir", str(out),
           "--max-iter", "100000", "--max-hours", str(ROOT_H), "--max-rss-gib", "10", "--min-free-gib", "2",
           "--price-tol", str(P_TOL), "--benders-tol-cny", str(B_TOL), "--integer-time-limit-s", "60"]
    if resume:
        cmd.append("--resume")
    log = out / "root_run.log"
    mode = "a" if resume else "w"
    print(f"[根节点] {spec['id']}：{'从 checkpoint 恢复' if resume else '启动'}，最多 {ROOT_H:g} 小时；日志={log}", flush=True)
    with log.open(mode, encoding="utf-8") as fh:
        proc = subprocess.Popen(cmd, cwd=str(HERE.parent.parent), stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                text=True, errors="replace", bufsize=1)
        assert proc.stdout is not None
        for line in proc.stdout:
            print(f"[{spec['id']}] {line.rstrip()}", flush=True)
            fh.write(line); fh.flush()
        return proc.wait()


def canonical_pool(att: Path, final_dir: Path):
    data = qos.read_data(att)
    pool, _, _, _, _, _, _ = qos.load_state(final_dir)
    schedule = pd.read_csv(final_dir / "q4_字典序最终排程.csv")
    ti = {int(v): i for i, v in enumerate(data.task.TaskID.to_numpy())}
    ri = {v: i for i, v in enumerate(qos.REGIONS)}
    keys = {qos.ColumnPool.key(t, r, s): j for j, (t, r, s) in enumerate(zip(*pool.arrays()))}
    x = np.zeros(len(pool), dtype=float)
    for row in schedule.itertuples(index=False):
        key = qos.ColumnPool.key(ti[int(row.TaskID)], ri[str(row.目标区域)], int(row.开工小时))
        if key not in keys:
            pool.add(ti[int(row.TaskID)], ri[str(row.目标区域)], int(row.开工小时)); keys[key] = len(pool) - 1
        x[keys[key]] = 1.0
    if int(x.sum()) != len(data.task):
        raise RuntimeError("canonical 排程没有覆盖全部任务")
    return data, pool, x, schedule


def cost_cert(spec: dict, att: Path, root: Path, final_dir: Path, out: Path) -> dict:
    data, pool, x, schedule = canonical_pool(att, final_dir)
    energy = full.energy_lp(full.facility_load(pool, data, x), data)
    if not energy["success"]:
        raise RuntimeError(f"{spec['id']} canonical 排程能源 LP 不可行：{energy['message']}")
    summary = json.loads((root / "summary.json").read_text(encoding="utf-8"))
    rows = pd.read_csv(root / "iteration_metrics.csv")
    closed = bool(summary.get("根节点闭合"))
    closed_rows = rows[rows["new_columns"].eq(0)]
    lb = float(closed_rows.iloc[-1]["lp_lb_cny"]) if closed and len(closed_rows) else float("nan")
    ub = float(energy["cost"])
    cert = {"状态": "PASS" if np.isfinite(lb) and ub - lb <= C_TOL else "NEEDS_RESUME", "场景": spec["id"],
            "根节点闭合": closed, "LB完整域成本_CNY": lb, "UB_canonical真实能源成本_CNY": ub,
            "UB减LB_CNY": None if not np.isfinite(lb) else ub - lb, "成本证书容差_CNY": C_TOL,
            "等待下界_h": 0.0, "canonical总等待_h": float(schedule["等待_h"].sum()),
            "canonical总时延_ms": float(schedule["时延_ms"].sum()), "能源审计": energy.get("audit", {}),
            "活动列数": int(len(pool)), "Benders切数": int(summary.get("Benders切数", 0))}
    out.mkdir(parents=True, exist_ok=True)
    (out / "cost_certificate.json").write_text(json.dumps(cert, ensure_ascii=False, indent=2), encoding="utf-8")
    return cert


def run_latency(spec: dict, att: Path, final_dir: Path, out: Path) -> dict:
    data, pool, _, schedule = canonical_pool(att, final_dir)
    ti = {int(v): i for i, v in enumerate(data.task.TaskID.to_numpy())}
    ri = {v: i for i, v in enumerate(qos.REGIONS)}
    keys = {qos.ColumnPool.key(t, r, s): j for j, (t, r, s) in enumerate(zip(*pool.arrays()))}
    x = np.zeros(len(pool), dtype=float)
    for row in schedule.itertuples(index=False):
        x[keys[qos.ColumnPool.key(ti[int(row.TaskID)], ri[str(row.目标区域)], int(row.开工小时))]] = 1.0
    load = qos.facility_load(pool, data, x); energy = qos.energy_lp(load, data)
    cuts: list[full.Cut] = []
    qos.add_region_cuts(cuts, data, load, energy)
    gpu, it, rhs, _ = qos.make_presolve_rows(data); lat = qos.read_latency(att)
    args = argparse.Namespace(benders_tol_cny=B_TOL, columns_per_task=2, cost_feas_tol_cny=C_TOL,
        heartbeat_seconds=30.0, integer_time_limit_s=1800.0, max_stage_iter=0, max_hours=ROOT_H,
        max_active_columns=1_000_000, max_rss_gib=10.0, min_free_gib=2.0, mip_rel_gap=1e-7,
        price_tol=P_TOL, wait_tolerance=1e-6, progress_mode="auto")
    out.mkdir(parents=True, exist_ok=True); cap = float(energy["cost"] + C_TOL)
    result = qos.run_stage(qos.StageSpec("Latency阶段", "latency", cap, 1e-6), pool, cuts, data, gpu, it, rhs, lat,
                           args, out, time.time(), len(pool), 0.0, 0)
    sch, audit = qos.audit_solution(pool, data, result.x, gpu, it, rhs, lat, result.energy)
    sch.to_csv(out / "q4_字典序最终排程.csv", index=False, encoding="utf-8-sig")
    good = audit_ok(audit)
    ans = {"状态": "PASS" if good else "NEEDS_REVIEW", "场景": spec["id"], "Latency_ms": float(result.objective),
           "真实能源成本_CNY": float(result.energy["cost"]), "Cost上界_CNY": cap,
           "Benders切数": int(result.benders_cuts), "活动列数": int(len(pool)), "约束审计": audit,
           "全局整数最优已证明": False}
    (out / "latency_certificate.json").write_text(json.dumps(ans, ensure_ascii=False, indent=2), encoding="utf-8")
    return ans


def audit_ok(audit: dict, tol: float = 1e-5) -> bool:
    for value in audit.values():
        if isinstance(value, (int, float, np.integer, np.floating)) and float(value) > tol:
            return False
    return True


def saved_cert(spec: dict, att: Path, out: Path) -> dict | None:
    metrics = out / "q4_lexicographic_stage_metrics.csv"
    schedule_path = out / "q4_字典序最终排程.csv"
    state_path = out / "lexicographic_state.npz"
    if not metrics.is_file() or not schedule_path.is_file() or not state_path.is_file():
        return None
    rows = pd.read_csv(metrics)
    done = rows[rows["事件"].eq("stage_completed")]
    if done.empty:
        return None
    data = qos.read_data(att)
    pool, _, _, _, _, _, _ = qos.load_state(out)
    schedule = pd.read_csv(schedule_path)
    ti = {int(v): i for i, v in enumerate(data.task.TaskID.to_numpy())}
    ri = {v: i for i, v in enumerate(qos.REGIONS)}
    keys = {qos.ColumnPool.key(t, r, s): j for j, (t, r, s) in enumerate(zip(*pool.arrays()))}
    x = np.zeros(len(pool), dtype=float)
    for row in schedule.itertuples(index=False):
        key = qos.ColumnPool.key(ti[int(row.TaskID)], ri[str(row.目标区域)], int(row.开工小时))
        if key not in keys:
            return None
        x[keys[key]] = 1.0
    gpu, it, rhs, _ = qos.make_presolve_rows(data)
    latency = qos.read_latency(att)
    energy = qos.energy_lp(qos.facility_load(pool, data, x), data)
    if not energy["success"]:
        return None
    _, audit = qos.audit_solution(pool, data, x, gpu, it, rhs, latency, energy)
    last = done.iloc[-1]
    ans = {"状态": "PASS" if audit_ok(audit) else "NEEDS_REVIEW", "场景": spec["id"],
           "Latency_ms": float(last["MIP目标值"]), "真实能源成本_CNY": float(energy["cost"]),
           "Cost上界_CNY": float(energy["cost"] + C_TOL), "Benders切数": int(last["Benders切数"]),
           "活动列数": int(last["活动列数"]), "约束审计": audit, "全局整数最优已证明": False,
           "恢复来源": "已完成stage_completed、最终排程与能源复核"}
    (out / "latency_certificate.json").write_text(json.dumps(ans, ensure_ascii=False, indent=2), encoding="utf-8")
    return ans


def one(sid: str, args) -> dict:
    spec = fs.scenario_by_id(sid); base = args.attachment_dir.resolve(); root = args.output_root.resolve() / sid; att = root / "attachment"
    if not att.exists(): fs.rewrite_region_time(base, att, spec)
    (root / "input_audit.json").write_text(json.dumps(stat(att, spec), ensure_ascii=False, indent=2), encoding="utf-8")
    code = root / "solver"; summary_path = code / "summary.json"
    if not summary_path.is_file() or not json.loads(summary_path.read_text(encoding="utf-8")).get("根节点闭合"):
        rc = run_root(spec, att, code, args.python)
        if rc != 0 and not summary_path.is_file(): return {"场景": sid, "状态": "ROOT_FAILED", "返回码": rc}
    cert = cost_cert(spec, att, code, args.canonical_dir, root / "certificate")
    if cert["状态"] != "PASS": return {"场景": sid, "成本证书": cert, "状态": "NEEDS_RESUME"}
    lat_out = root / "latency_certificate"; path = lat_out / "latency_certificate.json"
    lat = json.loads(path.read_text(encoding="utf-8")) if path.is_file() else saved_cert(spec, att, lat_out)
    if lat is None:
        lat = run_latency(spec, att, args.canonical_dir, lat_out)
    return {"场景": sid, "成本证书": cert, "Latency证书": lat,
            "状态": "PASS" if lat.get("状态") == "PASS" else "NEEDS_REVIEW"}


def main() -> None:
    p = argparse.ArgumentParser(description="Q4 约束情景有限时长分析")
    p.add_argument("--scenario", choices=SCENS + ("all",), default="all")
    p.add_argument("--attachment-dir", type=Path, default=full.DEFAULT_ATTACH)
    p.add_argument("--canonical-dir", type=Path, default=HERE.parent / "results" / "qos_final_recertification")
    p.add_argument("--output-root", type=Path, default=HERE.parent / "results" / "formal_scenarios")
    p.add_argument("--python", type=Path, default=Path(r"D:\python3.12.7\python.exe"))
    a = p.parse_args(); ids = SCENS if a.scenario == "all" else (a.scenario,); all_out = []
    for sid in ids:
        print("\n" + "=" * 78 + f"\n[正式情景] {sid}：开始\n" + "=" * 78, flush=True)
        try: all_out.append(one(sid, a))
        except Exception as exc:
            all_out.append({"场景": sid, "状态": "ERROR", "错误": repr(exc)}); print(f"[{sid}] ERROR: {exc!r}", flush=True)
    out = a.output_root.resolve(); out.mkdir(parents=True, exist_ok=True)
    summary_path = out / "q4_constraint_analysis_summary.json"
    previous = json.loads(summary_path.read_text(encoding="utf-8")) if summary_path.is_file() else []
    merged = {str(row.get("场景")): row for row in previous if row.get("场景")}
    merged.update({str(row.get("场景")): row for row in all_out if row.get("场景")})
    summary_path.write_text(json.dumps(list(merged.values()), ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(all_out, ensure_ascii=False, indent=2), flush=True)
    if any(x.get("状态") == "ERROR" for x in all_out): raise SystemExit(1)


if __name__ == "__main__": main()
