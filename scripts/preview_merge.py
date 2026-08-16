#!/usr/bin/env python3
from __future__ import annotations
import argparse, json, os, shutil, subprocess, sys
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
CFG=json.loads((ROOT/"config/project.json").read_text(encoding="utf-8"))
MARKER=".cumcm-preview-worktree"

def run(args,cwd=ROOT,check=True,capture=False):
    return subprocess.run(args,cwd=cwd,text=True,check=check,capture_output=capture)

def registered(path):
    p=run(["git","worktree","list","--porcelain"],capture=True).stdout
    return str(path).replace("\\","/") in p.replace("\\","/")

def clean_preview(path):
    if Path.cwd().resolve()==path.resolve():
        raise SystemExit("不能从待删除的 preview 目录内部执行 --clean；先 cd 到正常 worktree。")
    if registered(path): run(["git","worktree","remove","--force",str(path)],check=False)
    if path.exists(): shutil.rmtree(path,ignore_errors=False)
    run(["git","worktree","prune"],check=False)

def ref_exists(ref):
    return run(["git","show-ref","--verify","--quiet",ref],check=False).returncode==0

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--clean",action="store_true")
    ap.add_argument("--strict",action="store_true",help="缺任一活动分支即失败")
    ap.add_argument("--no-open",action="store_true")
    ap.add_argument("--preview-dir")
    a=ap.parse_args()
    preview=Path(a.preview_dir).resolve() if a.preview_dir else (ROOT.parent/(ROOT.name+"-preview")).resolve()
    if a.clean:
        clean_preview(preview); print("preview 已清理"); return
    if (ROOT/MARKER).exists(): raise SystemExit("当前位于 preview worktree，请回到正常 worktree。")
    run(["git","fetch","origin","--prune"])
    if preview.exists() or registered(preview):
        raise SystemExit(f"已存在 preview：{preview}\n先运行 python scripts/preview_merge.py --clean")
    base=CFG.get("default_base","main")
    run(["git","worktree","add","--detach",str(preview),f"origin/{base}"])
    (preview/MARKER).write_text("temporary detached full-paper preview\n",encoding="utf-8")
    try:
        mods=sorted((x for x in CFG["modules"] if x.get("active",True)),key=lambda x:x["merge_order"])
        for m in mods:
            ref=f"refs/remotes/origin/{m['branch']}"
            if not ref_exists(ref):
                msg=f"远端缺少 {m['branch']}"
                if a.strict: raise RuntimeError(msg)
                print("[WARN]",msg,"，本次跳过"); continue
            print("[MERGE]",m["branch"])
            p=run(["git","merge","--no-ff","--no-edit",f"origin/{m['branch']}"],cwd=preview,check=False)
            if p.returncode:
                raise RuntimeError(f"合并 {m['branch']} 冲突。只在临时目录 {preview} 中检查；不要用 force push 解决。")
        pre=preview/"scripts/final_preflight.py"
        if pre.exists(): run([sys.executable,str(pre)],cwd=preview,check=False)
        paper=preview/"paper"
        if shutil.which("latexmk"):
            run(["latexmk","-xelatex","-interaction=nonstopmode","-halt-on-error","main.tex"],cwd=paper)
        elif shutil.which("xelatex"):
            run(["xelatex","-interaction=nonstopmode","-halt-on-error","main.tex"],cwd=paper)
            run(["xelatex","-interaction=nonstopmode","-halt-on-error","main.tex"],cwd=paper)
        else:
            print("[WARN] 未找到 latexmk/xelatex，仅完成临时合并。")
            return
        if pre.exists(): run([sys.executable,str(pre),"--post-build"],cwd=preview,check=False)
        pdf=paper/"main.pdf"; print("PDF:",pdf)
        if pdf.exists() and not a.no_open:
            try:
                if os.name=="nt": os.startfile(pdf)  # type: ignore[attr-defined]
                elif sys.platform=="darwin": run(["open",str(pdf)],check=False)
                else: run(["xdg-open",str(pdf)],check=False)
            except Exception as e: print("[WARN] 无法自动打开 PDF:",e)
    except Exception:
        print(f"\n临时目录保留用于检查：{preview}")
        raise

if __name__=="__main__": main()
