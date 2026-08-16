#!/usr/bin/env python3
from __future__ import annotations
import argparse, json, subprocess
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
CFG=json.loads((ROOT/"config/project.json").read_text(encoding="utf-8"))

def run(*args,check=True):
    return subprocess.run(args,cwd=ROOT,text=True,check=check)

def exists_ref(ref):
    return subprocess.run(["git","show-ref","--verify","--quiet",ref],cwd=ROOT).returncode==0

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--root",default=str(ROOT.parent/(ROOT.name+"-worktrees")))
    ap.add_argument("--push",action="store_true",help="创建后 push 到 origin")
    a=ap.parse_args(); wtroot=Path(a.root).resolve(); wtroot.mkdir(parents=True,exist_ok=True)
    if subprocess.run(["git","diff","--quiet"],cwd=ROOT).returncode or subprocess.run(["git","diff","--cached","--quiet"],cwd=ROOT).returncode:
        raise SystemExit("当前仓库有未提交修改，请先处理。")
    run("git","fetch","origin","--prune",check=False)
    base=CFG.get("default_base","main")
    for m in sorted((x for x in CFG["modules"] if x.get("active",True)), key=lambda x:x["merge_order"]):
        branch=m["branch"]; dest=wtroot/m["key"]
        if dest.exists():
            print(f"[SKIP] {dest} 已存在"); continue
        local=f"refs/heads/{branch}"; remote=f"refs/remotes/origin/{branch}"
        if exists_ref(local):
            run("git","worktree","add",str(dest),branch)
        elif exists_ref(remote):
            run("git","worktree","add","-b",branch,str(dest),f"origin/{branch}")
        else:
            run("git","worktree","add","-b",branch,str(dest),base)
            if a.push: run("git","push","-u","origin",branch)
        print(f"[OK] {m['key']}: {dest}")
    print("\n完成。每个章节/问题已有独立 worktree；进入对应目录后运行 workflow.py start <key>。")

if __name__=="__main__": main()
