#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""renew_down_80 一次性可行上界与完整域下界证书。"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import q4_full_solver as fs  # noqa: E402
import q4_qos_refinement as qr  # noqa: E402


DEF_ROOT = HERE.parent / "results" / "formal_scenarios" / "renew_down_80"
DEF_OUT = HERE.parent / "results" / "renew_down_80_quick_certificate"


def jdump(path: Path, obj: dict) -> None:
    path.write_text(json.dumps(obj, ensure_ascii=False, indent=2), encoding="utf-8")


def sha(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def mk_prof(data, gr: np.ndarray, ir: np.ndarray, rd: np.ndarray,
            cd: np.ndarray, cuts: list[fs.Cut]) -> dict:
    sig = np.zeros((fs.R, fs.H_TASK), dtype=float)
    for dual, cut in zip(cd, cuts):
        sig += -dual * cut.lam[:, :fs.H_TASK]
    ans = {}
    ex = {
        int(tp): int(np.flatnonzero(data.type_idx == tp)[0])
        for tp in np.unique(data.type_idx)
    }
    keys = set(zip(data.type_idx.tolist(), data.duration.tolist()))
    for tp, dur in keys:
        pf = fs.overlap_profile(dur)
        alpha = float(data.alpha[ex[int(tp)]])
        for r in range(fs.R):
            hour = np.zeros(fs.H_TASK, dtype=float)
            for h in range(fs.H_TASK):
                gi, ii = int(gr[r, h]), int(ir[r, h])
                if gi >= 0:
                    hour[h] += -rd[gi]
                if ii >= 0:
                    hour[h] += -rd[ii] * alpha
                hour[h] += sig[r, h] * data.pue[r] * alpha
            ans[(int(tp), r, int(round(dur * 60)))] = np.convolve(
                hour, pf[::-1], mode="valid"
            )
    return ans


def scan(data, prof: dict, eqd: np.ndarray) -> tuple[np.ndarray, np.ndarray, np.ndarray, int]:
    n = len(data.task)
    rho = np.full(n, np.inf, dtype=float)
    br = np.full(n, -1, dtype=np.int8)
    bs = np.full(n, -1, dtype=np.int16)
    kinds = data.task["TaskType"].astype(str).to_numpy()
    total = 0
    t0 = time.time()
    for i in range(n):
        s0 = int(data.arrival[i])
        s1 = s0 if kinds[i] == "RealTimeInference" else fs.legal_last_start(data, i)
        if s1 < s0:
            raise RuntimeError(f"TaskID={data.task.iloc[i].TaskID} 没有合法开工时刻")
        count = s1 - s0 + 1
        for r in np.flatnonzero(data.legal[i]):
            vals = prof[(int(data.type_idx[i]), int(r), int(round(data.duration[i] * 60)))][s0:s1 + 1]
            k = int(np.argmin(vals))
            rc = float(data.gpu[i] * vals[k] - eqd[i])
            total += count
            if rc < rho[i]:
                rho[i], br[i], bs[i] = rc, int(r), s0 + k
        if (i + 1) % 5000 == 0 or i + 1 == n:
            print(
                f"[完整域扫描] {i + 1}/{n}任务 | 候选={total} | "
                f"当前最小rc={float(np.min(rho[:i + 1])):.6f} | "
                f"用时={(time.time() - t0) / 60:.2f}分钟",
                flush=True,
            )
    if not np.all(np.isfinite(rho)):
        raise RuntimeError("完整域扫描存在没有合法候选的任务")
    return rho, br, bs, total


def score_one(data, prof: dict, eqd: np.ndarray, task: int, region: int, start: int) -> float:
    val = prof[(int(data.type_idx[task]), region, int(round(data.duration[task] * 60)))][start]
    return float(data.gpu[task] * val - eqd[task])


def audit_rc(pool, data, prof: dict, eqd: np.ndarray, rd: np.ndarray,
             cd: np.ndarray, res, cm) -> dict:
    ti, rr, ss = pool.arrays()
    mat = -eqd[ti] - np.asarray(res.T @ rd).ravel() - np.asarray(cm.T @ cd).ravel()
    ids = np.unique(np.linspace(0, len(pool) - 1, min(200, len(pool)), dtype=int))
    dif = []
    for j in ids:
        val = score_one(data, prof, eqd, int(ti[j]), int(rr[j]), int(ss[j]))
        dif.append(abs(val - float(mat[j])))
    return {
        "抽查列数": int(len(ids)),
        "公式与矩阵约化成本最大差": float(max(dif, default=0.0)),
        "活动列最小矩阵约化成本": float(np.min(mat)),
        "活动列最大矩阵约化成本": float(np.max(mat)),
    }


def load_best(path: Path, data) -> fs.ColumnPool:
    tab = pd.read_csv(path)
    need = {"TaskID", "区域", "开工小时"}
    if not need.issubset(tab.columns):
        raise RuntimeError("best_schedule.csv 字段不完整")
    if len(tab) != len(data.task) or tab["TaskID"].nunique() != len(data.task):
        raise RuntimeError("best_schedule.csv 不是每任务恰好一行")
    imap = {int(v): i for i, v in enumerate(data.task.TaskID.to_numpy())}
    rmap = {v: i for i, v in enumerate(fs.REGIONS)}
    if set(tab["TaskID"].astype(int)) != set(imap):
        raise RuntimeError("best_schedule.csv 的 TaskID 集合与场景附件不一致")
    pool = fs.ColumnPool()
    for row in tab.itertuples(index=False):
        rid = str(getattr(row, "区域"))
        if rid not in rmap:
            raise RuntimeError(f"未知区域：{rid}")
        pool.add(imap[int(row.TaskID)], rmap[rid], int(row.开工小时))
    return pool


def audit_best(path: Path, data, gr: np.ndarray, ir: np.ndarray,
               rhs: np.ndarray, lat: np.ndarray) -> tuple[dict, pd.DataFrame, np.ndarray]:
    pool = load_best(path, data)
    x = np.ones(len(pool), dtype=float)
    load = fs.facility_load(pool, data, x)
    eng = fs.energy_lp(load, data)
    if not eng["success"]:
        raise RuntimeError("候选排程真实能源 LP 失败：" + eng["message"])
    sched, audit = qr.audit_solution(pool, data, x, gr, ir, rhs, lat, eng)
    ok = all(float(v) <= 1e-7 for v in audit.values())
    out = {
        "真实能源成本_CNY": float(eng["cost"]),
        "碳排放_tCO2": float(eng["carbon"]),
        "硬约束审计通过": bool(ok),
        "硬约束审计": audit,
    }
    return out, sched, load


def cert(args) -> dict:
    root = args.scenario_root.resolve()
    src = root / "solver"
    out = args.output_dir.resolve()
    out.mkdir(parents=True, exist_ok=True)
    attach = root / "attachment"
    files = [
        attach / "region_time_data.xlsx", attach / "workload_trace.xlsx",
        attach / "network_latency.xlsx", attach / "GPU_information.xlsx",
        attach / "power_mapping.xlsx", attach / "storage_information.xlsx",
        src / "checkpoint_state.npz", src / "best_schedule.csv",
    ]
    for path in files:
        if not path.is_file():
            raise FileNotFoundError(path)
    jdump(out / "checkpoint.json", {"状态": "RUNNING", "阶段": "读取场景与断点"})
    data = fs.read_data(attach)
    gr, ir, rhs, _ = fs.make_presolve_rows(data)
    lat = qr.read_latency(attach)
    pool, cuts, it, init_n, old_ub = fs.load_solver_state(src)
    if len(data.task) != 50000:
        raise RuntimeError(f"正式证书要求50000任务，实际为{len(data.task)}")
    if any(cut.region >= 0 for cut in cuts):
        raise RuntimeError("快速证书只接受当前 aggregate Benders 断点")

    print("[1/3] 复核现有整数候选排程", flush=True)
    ub, sched, load = audit_best(src / "best_schedule.csv", data, gr, ir, rhs, lat)
    sched.to_csv(out / "q4_renew_down_80_audited_schedule.csv", index=False, encoding="utf-8-sig")
    jdump(out / "candidate_audit.json", ub)
    if not ub["硬约束审计通过"]:
        raise RuntimeError("现有 best_schedule 未通过硬约束审计")
    jdump(out / "checkpoint.json", {"状态": "RUNNING", "阶段": "一次性RMP求解", "整数可行上界_CNY": ub["真实能源成本_CNY"]})

    print("[2/3] 求解当前201-cut限制主问题", flush=True)
    t0 = time.time()
    rmp, ar, res, cm = fs.solve_rmp(pool, data, gr, ir, rhs, cuts)
    m = len(rhs)
    rd = np.asarray(rmp["ub_dual"][:m])
    cd = np.asarray(rmp["ub_dual"][m:])
    eqd = np.asarray(rmp["eq_dual"])
    bub = np.r_[rhs, -np.asarray([cut.const for cut in cuts])]
    dobj = float(np.dot(bub, rmp["ub_dual"]) + np.sum(eqd))
    dgap = float(rmp["lb"] - dobj)
    if np.max(rd, initial=-math.inf) > args.dual_tol or np.max(cd, initial=-math.inf) > args.dual_tol:
        raise RuntimeError("RMP不等式对偶符号违反最小化LP门禁")
    if abs(float(-np.sum(cd)) - 1.0) > args.dual_tol:
        raise RuntimeError("theta自由变量的对偶平衡门禁失败")
    if abs(dgap) > args.dual_gap_tol:
        raise RuntimeError(f"RMP原始-对偶差过大：{dgap}")

    print("[3/3] 扫描全部合法候选并修正对偶下界", flush=True)
    jdump(out / "checkpoint.json", {"状态": "RUNNING", "阶段": "完整域精确定价", "RMP目标_CNY": rmp["lb"]})
    prof = mk_prof(data, gr, ir, rd, cd, cuts)
    rca = audit_rc(pool, data, prof, eqd, rd, cd, res, cm)
    if rca["公式与矩阵约化成本最大差"] > args.rc_check_tol:
        raise RuntimeError("定价公式与RMP矩阵约化成本不一致")
    rho, br, bs, total = scan(data, prof, eqd)
    if total != args.expected_domain:
        raise RuntimeError(f"完整候选域计数不一致：{total} != {args.expected_domain}")
    guard = float(args.price_guard)
    shift = np.minimum(0.0, rho - guard)
    lower = float(dobj + np.sum(shift))
    upper = float(ub["真实能源成本_CNY"])
    gap = float(upper - lower)
    rel = float(gap / max(abs(upper), 1.0))
    rc_tab = pd.DataFrame({
        "TaskID": data.task.TaskID.to_numpy(),
        "最小约化成本": rho,
        "下界修正量": shift,
        "最优定价区域": [fs.REGIONS[int(v)] for v in br],
        "最优定价开工小时": bs,
    })
    rc_tab.to_csv(out / "q4_renew_down_80_task_reduced_cost.csv", index=False, encoding="utf-8-sig")

    cm2 = fs.cut_matrix(load_best(src / "best_schedule.csv", data), data, cuts)
    pred = np.asarray([cut.const for cut in cuts]) + np.asarray(cm2 @ np.ones(len(data.task))).ravel()
    cut_over = float(np.max(pred - upper))
    status = "CERTIFIED_OPTIMAL" if gap <= args.cost_tol else "CERTIFIED_BOUNDED"
    ans = {
        "状态": status,
        "场景": "renew_down_80",
        "模型口径": "完整合法域、当前有效Benders低估器、一次性精确定价对偶修正",
        "任务数": int(len(data.task)),
        "完整候选域数": int(total),
        "断点已完成轮次": int(it),
        "活动列数": int(len(pool)),
        "Benders切数": int(len(cuts)),
        "断点记录可行上界_CNY": float(old_ub),
        "复核后整数可行上界_CNY": upper,
        "严格完整域LP下界_CNY": lower,
        "绝对Gap_CNY": gap,
        "相对Gap": rel,
        "全局整数Cost最优已证明": bool(gap <= args.cost_tol),
        "Cost证书容差_CNY": float(args.cost_tol),
        "RMP原始目标_CNY": float(rmp["lb"]),
        "RMP对偶目标_CNY": dobj,
        "RMP原始对偶差_CNY": dgap,
        "逐任务下界修正合计_CNY": float(np.sum(shift)),
        "全域最小约化成本": float(np.min(rho)),
        "负约化成本任务数": int(np.count_nonzero(rho < -guard)),
        "定价保护量_CNY每任务": guard,
        "约化成本一致性审计": rca,
        "候选硬约束审计": ub["硬约束审计"],
        "候选硬约束审计通过": ub["硬约束审计通过"],
        "候选点最大cut高估_CNY": cut_over,
        "输入SHA256": {str(path.relative_to(root)): sha(path) for path in files},
        "运行秒": float(time.time() - t0),
        "结论限制": "Gap大于容差时仅证明上下界区间，不声称全局整数最优",
    }
    jdump(out / "quick_certificate.json", ans)
    jdump(out / "checkpoint.json", {"状态": status, "阶段": "完成", "最新": ans})
    print(json.dumps(ans, ensure_ascii=False, indent=2), flush=True)
    return ans


def main() -> None:
    p = argparse.ArgumentParser(description="Q4 renew_down_80 快速有界证书")
    p.add_argument("--scenario-root", type=Path, default=DEF_ROOT)
    p.add_argument("--output-dir", type=Path, default=DEF_OUT)
    p.add_argument("--expected-domain", type=int, default=233375201)
    p.add_argument("--price-guard", type=float, default=1e-7)
    p.add_argument("--cost-tol", type=float, default=1e-3)
    p.add_argument("--dual-tol", type=float, default=1e-7)
    p.add_argument("--dual-gap-tol", type=float, default=1e-3)
    p.add_argument("--rc-check-tol", type=float, default=1e-7)
    raise SystemExit(0 if cert(p.parse_args()) else 2)


if __name__ == "__main__":
    main()
