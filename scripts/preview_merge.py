#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CFG_PATH = ROOT / "config/project.json"
CFG = json.loads(CFG_PATH.read_text(encoding="utf-8"))
MARKER = ".cumcm-preview-worktree"


def run(args, cwd=ROOT, check=True, capture=False):
    return subprocess.run(args, cwd=cwd, text=True, check=check, capture_output=capture)


def registered(path: Path) -> bool:
    p = run(["git", "worktree", "list", "--porcelain"], capture=True).stdout
    return str(path).replace("\\", "/") in p.replace("\\", "/")


def clean_preview(path: Path) -> None:
    if Path.cwd().resolve() == path.resolve():
        raise SystemExit("不能从待删除的 preview 目录内部执行 --clean；先 cd 到正常 worktree。")
    if registered(path):
        run(["git", "worktree", "remove", "--force", str(path)], check=False)
    if path.exists():
        shutil.rmtree(path, ignore_errors=False)
    run(["git", "worktree", "prune"], check=False)


def ref_exists(ref: str) -> bool:
    return run(["git", "show-ref", "--verify", "--quiet", ref], check=False).returncode == 0


def integration_cfg() -> dict:
    return CFG.get("integration", {})


def module_plan(extra_skip: set[str]) -> list[dict]:
    integ = integration_cfg()
    skip = set(integ.get("skip_module_keys", [])) | extra_skip
    curated = integ.get("curated_references", {})
    if curated:
        skip.add(curated.get("module_key", "references"))
    return sorted(
        (
            m
            for m in CFG["modules"]
            if m.get("active", True) and m["key"] not in skip
        ),
        key=lambda x: x["merge_order"],
    )


def sync_curated_references(preview: Path, strict: bool) -> None:
    cfg = integration_cfg().get("curated_references")
    if not cfg:
        return
    branch = cfg["branch"]
    source = cfg["source"]
    destination = cfg["destination"]
    ref = f"refs/remotes/origin/{branch}"
    if not ref_exists(ref):
        msg = f"远端缺少精选文献分支 {branch}"
        if strict:
            raise RuntimeError(msg)
        print("[WARN]", msg)
        return

    p = run(["git", "show", f"origin/{branch}:{source}"], cwd=preview, capture=True, check=False)
    if p.returncode:
        msg = f"无法读取 {branch}:{source}"
        if strict:
            raise RuntimeError(msg)
        print("[WARN]", msg)
        return

    dst = preview / destination
    dst.parent.mkdir(parents=True, exist_ok=True)
    dst.write_text(p.stdout, encoding="utf-8")
    run(["git", "add", destination], cwd=preview)
    if run(["git", "diff", "--cached", "--quiet"], cwd=preview, check=False).returncode:
        run(
            [
                "git",
                "commit",
                "-m",
                "sync(references): apply curated final bibliography",
            ],
            cwd=preview,
        )
    print(f"[SYNC] curated references: {branch}:{source} -> {destination}")


def cite_audit(preview: Path) -> tuple[set[str], set[str]]:
    ref_cfg = integration_cfg().get("curated_references", {})
    bib_path = preview / ref_cfg.get(
        "destination", "modules/70_references/paper/references.tex"
    )
    if not bib_path.exists():
        print("[WARN] 未找到最终 bibliography，跳过 cite 审计。")
        return set(), set()

    cite_keys: set[str] = set()
    cite_re = re.compile(r"\\cite\{([^}]+)\}")
    for tex in list((preview / "modules").rglob("*.tex")) + list((preview / "paper").rglob("*.tex")):
        text = tex.read_text(encoding="utf-8", errors="replace")
        for group in cite_re.findall(text):
            cite_keys.update(k.strip() for k in group.split(",") if k.strip())

    bib_text = bib_path.read_text(encoding="utf-8", errors="replace")
    bib_keys = set(re.findall(r"\\bibitem\{([^}]+)\}", bib_text))
    missing = cite_keys - bib_keys
    unused = bib_keys - cite_keys

    if missing:
        print("[FAIL] bibliography 缺少正文 cite key:")
        for key in sorted(missing):
            print(" -", key)
    else:
        print(f"[PASS] cite-key 审计：正文 {len(cite_keys)} 个 key 均存在。")

    if unused:
        print("[WARN] 最终 bibliography 中尚未被正文引用的条目:")
        for key in sorted(unused):
            print(" -", key)
    else:
        print("[PASS] bibliography 反向审计：无未使用条目。")
    return missing, unused


def merge_branch(preview: Path, module: dict, strict: bool) -> None:
    branch = module["branch"]
    ref = f"refs/remotes/origin/{branch}"
    if not ref_exists(ref):
        msg = f"远端缺少 {branch}"
        if strict:
            raise RuntimeError(msg)
        print("[WARN]", msg, "，本次跳过")
        return

    head = run(["git", "rev-parse", f"origin/{branch}"], cwd=preview, capture=True).stdout.strip()
    print(f"[MERGE] {module['key']}: {branch} @ {head[:12]}")
    p = run(
        ["git", "merge", "--no-ff", "--no-edit", f"origin/{branch}"],
        cwd=preview,
        check=False,
    )
    if p.returncode:
        unresolved = run(
            ["git", "diff", "--name-only", "--diff-filter=U"],
            cwd=preview,
            capture=True,
            check=False,
        ).stdout.strip()
        detail = f"\n未解决文件:\n{unresolved}" if unresolved else ""
        raise RuntimeError(
            f"合并 {branch} 冲突。冲突只存在临时目录 {preview}；不要 force push。{detail}"
        )


def structural_checks(preview: Path) -> None:
    if run(["git", "diff", "--check"], cwd=preview, check=False).returncode:
        raise RuntimeError("git diff --check 发现空白/冲突标记问题。")
    status = run(["git", "status", "--porcelain"], cwd=preview, capture=True).stdout.strip()
    if status:
        raise RuntimeError(f"预览合并后工作区不干净：\n{status}")


def build_paper(preview: Path, no_build: bool) -> None:
    if no_build:
        print("[INFO] --no-build：仅完成合并与静态审计。")
        return
    paper = preview / "paper"
    if shutil.which("latexmk"):
        run(
            ["latexmk", "-xelatex", "-interaction=nonstopmode", "-halt-on-error", "main.tex"],
            cwd=paper,
        )
    elif shutil.which("xelatex"):
        for _ in range(2):
            run(["xelatex", "-interaction=nonstopmode", "-halt-on-error", "main.tex"], cwd=paper)
    else:
        print("[WARN] 未找到 latexmk/xelatex，仅完成临时合并和静态审计。")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--clean", action="store_true")
    ap.add_argument("--strict", action="store_true", help="缺任一计划分支/精选参考文献即失败")
    ap.add_argument("--strict-preflight", action="store_true", help="final_preflight 非零时终止")
    ap.add_argument("--no-open", action="store_true")
    ap.add_argument("--no-build", action="store_true")
    ap.add_argument("--preview-dir")
    ap.add_argument("--base-branch", help="覆盖 config.integration.base_branch")
    ap.add_argument("--skip", action="append", default=[], help="额外跳过模块 key，可重复")
    a = ap.parse_args()

    preview = (
        Path(a.preview_dir).resolve()
        if a.preview_dir
        else (ROOT.parent / (ROOT.name + "-preview")).resolve()
    )
    if a.clean:
        clean_preview(preview)
        print("preview 已清理")
        return
    if (ROOT / MARKER).exists():
        raise SystemExit("当前位于 preview worktree，请回到正常 worktree。")

    run(["git", "fetch", "origin", "--prune"])
    if preview.exists() or registered(preview):
        raise SystemExit(
            f"已存在 preview：{preview}\n先运行 python scripts/preview_merge.py --clean"
        )

    integ = integration_cfg()
    base = a.base_branch or integ.get("base_branch") or CFG.get("default_base", "main")
    base_ref = f"refs/remotes/origin/{base}"
    if not ref_exists(base_ref):
        raise SystemExit(f"远端缺少总装底座 {base}")

    plan = module_plan(set(a.skip))
    print("=== preview merge plan ===")
    print("base:", base)
    for m in plan:
        print(f"  {m['merge_order']:>3}  {m['key']:<12} {m['branch']}")
    ref_cfg = integ.get("curated_references")
    if ref_cfg:
        print("  REF  references    curated one-way sync")

    run(["git", "worktree", "add", "--detach", str(preview), f"origin/{base}"])
    (preview / MARKER).write_text("temporary detached full-paper preview\n", encoding="utf-8")

    try:
        for m in plan:
            merge_branch(preview, m, a.strict)

        sync_curated_references(preview, a.strict)
        structural_checks(preview)
        missing, _unused = cite_audit(preview)
        if missing:
            raise RuntimeError("正文引用与最终 bibliography 不一致。")

        pre = preview / "scripts/final_preflight.py"
        if pre.exists():
            p = run([sys.executable, str(pre)], cwd=preview, check=False)
            if p.returncode and a.strict_preflight:
                raise RuntimeError("final_preflight 未通过。")

        build_paper(preview, a.no_build)

        if pre.exists() and not a.no_build:
            p = run([sys.executable, str(pre), "--post-build"], cwd=preview, check=False)
            if p.returncode and a.strict_preflight:
                raise RuntimeError("final_preflight --post-build 未通过。")

        pdf = preview / "paper" / "main.pdf"
        if pdf.exists():
            print("PDF:", pdf)
            if not a.no_open:
                try:
                    if os.name == "nt":
                        os.startfile(pdf)  # type: ignore[attr-defined]
                    elif sys.platform == "darwin":
                        run(["open", str(pdf)], check=False)
                    else:
                        run(["xdg-open", str(pdf)], check=False)
                except Exception as e:
                    print("[WARN] 无法自动打开 PDF:", e)
        print("[PASS] preview merge completed:", preview)
    except Exception:
        print(f"\n临时目录保留用于检查：{preview}")
        raise


if __name__ == "__main__":
    main()
