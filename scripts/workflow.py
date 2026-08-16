#!/usr/bin/env python3
from __future__ import annotations
import argparse, json, subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CFG = ROOT / "config/project.json"


def git(*args, check=False):
    p = subprocess.run(["git", *args], cwd=ROOT, text=True, capture_output=True)
    if check and p.returncode:
        raise SystemExit(p.stderr.strip() or p.stdout.strip())
    return p.stdout.strip()


def load():
    return json.loads(CFG.read_text(encoding="utf-8"))["modules"]


def get_module(key):
    for m in load():
        if m["key"] == key:
            return m
    raise SystemExit(f"未知模块 {key!r}。可用：" + ", ".join(m["key"] for m in load()))


def task_text(m):
    p = ROOT / m["task"]
    return p.read_text(encoding="utf-8") if p.exists() else "(任务文件缺失)"


def changed_paths(branch):
    paths = set()
    remote = f"origin/{branch}"
    if subprocess.run(["git", "rev-parse", "--verify", remote], cwd=ROOT, capture_output=True).returncode == 0:
        out = git("diff", "--name-only", f"{remote}...HEAD")
        paths.update(x for x in out.splitlines() if x)
    out = git("diff", "--name-only")
    paths.update(x for x in out.splitlines() if x)
    out = git("diff", "--name-only", "--cached")
    paths.update(x for x in out.splitlines() if x)
    return sorted(paths)


def allowed_path(path: str, module: dict) -> bool:
    prefixes = [module["path"].rstrip("/") + "/"]
    exact = {module["task"]}
    for item in module.get("extra_paths", []):
        if item.endswith("/"):
            prefixes.append(item)
        else:
            exact.add(item)
    return path in exact or any(path.startswith(prefix) for prefix in prefixes)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("action", choices=["start", "finish"])
    ap.add_argument("module")
    ap.add_argument("--no-fetch", action="store_true")
    a = ap.parse_args()
    m = get_module(a.module)

    if not a.no_fetch:
        subprocess.run(["git", "fetch", "origin", "--prune"], cwd=ROOT)

    branch = git("branch", "--show-current") or "(detached)"
    print(f"模块: {m['key']}\n期望分支: {m['branch']}\n当前分支: {branch}")
    print(f"允许主路径: {m['path']}/\n任务文件: {m['task']}")
    if m.get("extra_paths"):
        print("额外允许路径: " + ", ".join(m["extra_paths"]))
    if branch != m["branch"]:
        print("[WARN] 当前分支与模块约定不一致，请确认后再修改。")

    if a.action == "start":
        print("\n--- 实时待办 ---\n" + task_text(m))
        print("\n--- git status ---")
        print(git("status", "--short") or "clean")
        return

    changed = changed_paths(m["branch"])
    outside = [p for p in changed if not allowed_path(p, m)]
    print("\n--- 本分支/工作区改动 ---")
    print("\n".join(changed) if changed else "无")
    if outside:
        print("\n[FAIL] 检测到责任域外修改：")
        for p in outside:
            print(" -", p)
    else:
        print("\n[PASS] 未检测到责任域外修改。")

    task_changed = m["task"] in changed
    module_changed = any(p.startswith(m["path"].rstrip("/") + "/") for p in changed)
    if module_changed and not task_changed:
        print("[WARN] 本轮修改了模块内容，但任务文件没有同步变化；请确认待办/完成项/需要复核项是否已实时更新。")

    unchecked = sum(1 for line in task_text(m).splitlines() if line.lstrip().startswith("- [ ]"))
    print(f"[INFO] 当前任务文件仍有 {unchecked} 个未勾选项；允许保留，但结束汇报必须说明。")
    raise SystemExit(1 if outside else 0)


if __name__ == "__main__":
    main()
