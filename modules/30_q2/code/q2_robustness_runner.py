"""Run Q2 previous-start robustness checks without overwriting canonical outputs."""
from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path


BASE_SUFFIX = {
    "cost": "cost_only",
    "carbon": "carbon_only",
    "dynamic": "dynamic_marginal",
}


def parse_args():
    p = argparse.ArgumentParser(description="Q2 safe previous-start robustness runner")
    p.add_argument("attachment_dir", type=Path)
    p.add_argument("mode", choices=("cost", "carbon", "dynamic"), default="cost")
    p.add_argument("--max-passes", type=int, default=8)
    p.add_argument("--relative-tol", type=float, default=1e-3)
    p.add_argument("--tag", default="previous_start")
    return p.parse_args()


def main():
    args = parse_args()
    mod = Path(__file__).resolve().parents[1]
    proc = mod / "data" / "processed"
    tab = mod / "tables"
    res = mod / "results"
    suffix = BASE_SUFFIX[args.mode]

    outputs = [
        proc / f"q2_schedule_{suffix}.csv",
        proc / f"q2_hourly_energy_{suffix}.csv",
        tab / f"q2_metrics_{suffix}.csv",
        tab / f"q2_wait_by_type_{suffix}.csv",
        res / f"q2_convergence_{suffix}.csv",
        res / f"q2_constraint_audit_{suffix}.csv",
        res / f"q2_run_summary_{suffix}.json",
    ]

    for path in outputs:
        if not path.exists():
            raise SystemExit(f"缺少 canonical 输出，拒绝稳健性运行：{path}")

    tag = args.tag.strip().replace(" ", "_")
    if not tag:
        raise SystemExit("tag 不能为空")

    with tempfile.TemporaryDirectory(prefix="q2_robustness_") as tmp:
        tmp = Path(tmp)
        backups = {}
        for path in outputs:
            backup = tmp / path.name
            shutil.copy2(path, backup)
            backups[path] = backup

        solver = Path(__file__).with_name("q2_iterative_solver.py")
        cmd = [
            sys.executable,
            str(solver),
            str(args.attachment_dir.resolve()),
            args.mode,
            "--start", "previous",
            "--max-passes", str(args.max_passes),
            "--relative-tol", str(args.relative_tol),
        ]

        try:
            completed = subprocess.run(cmd, check=False)
            if completed.returncode != 0:
                raise RuntimeError(f"previous-start 求解失败，exit={completed.returncode}")

            tagged = []
            for path in outputs:
                generated = path
                tagged_path = path.with_name(path.stem + f"_{tag}" + path.suffix)
                shutil.copy2(generated, tagged_path)
                tagged.append(tagged_path)
        finally:
            for path, backup in backups.items():
                shutil.copy2(backup, path)

    print("[PASS] previous-start 稳健性运行完成；canonical 文件已恢复。")
    for path in tagged:
        print(path.relative_to(mod.parent.parent))


if __name__ == "__main__":
    main()
