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
CFG = json.loads((ROOT / "config/project.json").read_text(encoding="utf-8"))
MARKER = ".cumcm-preview-worktree"


def run(args, cwd=ROOT, check=True, capture=False):
    kwargs = {
        "cwd": cwd,
        "text": True,
        "check": check,
        "capture_output": capture,
    }
    # Git emits UTF-8 path names even on Windows. Force UTF-8 so Chinese paths
    # are not decoded with the active GBK locale.
    if capture:
        kwargs.update(encoding="utf-8", errors="replace")
    return subprocess.run(args, **kwargs)


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


def owned_roots(module: dict) -> list[str]:
    roots: list[str] = []
    for key in ("path", "task"):
        value = module.get(key)
        if value:
            roots.append(value.rstrip("/"))
    for value in module.get("extra_paths", []):
        if value:
            roots.append(value.rstrip("/"))
    # Backward compatibility with Scrimmage5/Scrimmage6 older project.json.
    if module.get("key") == "shared":
        roots.extend(["scripts", "config/project.json"])
    return list(dict.fromkeys(roots))


def is_owned(path: str, module: dict) -> bool:
    path = path.replace("\\", "/")
    return any(path == root or path.startswith(root + "/") for root in owned_roots(module))


def branch_changes(audit_base_ref: str, branch_ref: str):
    p = run(
        ["git", "diff", "--name-status", "-z", f"{audit_base_ref}...{branch_ref}"],
        capture=True,
    )
    parts = p.stdout.split("\0")
    out = []
    i = 0
    while i < len(parts):
        status = parts[i]
        if not status:
            break
        i += 1
        code = status[0]
        if code in {"R", "C"}:
            old, new = parts[i], parts[i + 1]
            i += 2
            out.append((code, old, new))
        else:
            path = parts[i]
            i += 1
            out.append((code, path, None))
    return out


def audit_ownership(module: dict, audit_base_ref: str) -> list[tuple[str, str, str | None]]:
    branch_ref = f"origin/{module['branch']}"
    changes = branch_changes(audit_base_ref, branch_ref)
    violations: list[str] = []
    for _code, p1, p2 in changes:
        for path in (p1, p2):
            if path and not is_owned(path, module):
                violations.append(path)
    if violations:
        bad = "\n  - ".join(sorted(set(violations)))
        raise RuntimeError(
            f"{module['branch']} 修改了模块所有权之外的路径：\n  - {bad}\n"
            "请先把误提交迁回正确分支；preview 不会自动吞并跨模块改动。"
        )
    return changes


def overlay_branch(module: dict, audit_base_ref: str, preview: Path) -> None:
    branch_ref = f"origin/{module['branch']}"
    changes = audit_ownership(module, audit_base_ref)
    head = run(["git", "rev-parse", branch_ref], capture=True).stdout.strip()
    print(f"[OVERLAY] {module['key']}: {module['branch']} @ {head[:12]} ({len(changes)} changes)")
    for code, p1, p2 in changes:
        if code == "D":
            run(["git", "rm", "-f", "--ignore-unmatch", "--", p1], cwd=preview, check=False)
        elif code == "R":
            run(["git", "rm", "-f", "--ignore-unmatch", "--", p1], cwd=preview, check=False)
            run(["git", "checkout", branch_ref, "--", p2], cwd=preview)
        elif code == "C":
            run(["git", "checkout", branch_ref, "--", p2], cwd=preview)
        else:
            run(["git", "checkout", branch_ref, "--", p1], cwd=preview)


def module_plan(extra_skip: set[str]) -> list[dict]:
    integ = integration_cfg()
    skip = set(integ.get("skip_module_keys", [])) | extra_skip
    curated = integ.get("curated_references")
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


def sync_curated_references(preview: Path, audit_base_ref: str, strict: bool) -> None:
    cfg = integration_cfg().get("curated_references")
    if not cfg:
        return
    module = next((m for m in CFG["modules"] if m["key"] == cfg.get("module_key", "references")), None)
    if module:
        audit_ownership(module, audit_base_ref)
    branch = cfg["branch"]
    source = cfg["source"]
    destination = cfg["destination"]
    if not ref_exists(f"refs/remotes/origin/{branch}"):
        if strict:
            raise RuntimeError(f"远端缺少精选文献分支 {branch}")
        print("[WARN] 远端缺少精选文献分支", branch)
        return
    p = run(["git", "show", f"origin/{branch}:{source}"], capture=True, check=False)
    if p.returncode:
        if strict:
            raise RuntimeError(f"无法读取 {branch}:{source}")
        print(f"[WARN] 无法读取 {branch}:{source}")
        return
    dst = preview / destination
    dst.parent.mkdir(parents=True, exist_ok=True)
    dst.write_text(p.stdout, encoding="utf-8")
    run(["git", "add", destination], cwd=preview)
    print(f"[SYNC] references: {branch}:{source} -> {destination}")


def cite_audit(preview: Path) -> tuple[set[str], set[str]]:
    cfg = integration_cfg().get("curated_references", {})
    bib = preview / cfg.get("destination", "modules/70_references/paper/references.tex")
    if not bib.exists():
        print("[WARN] 未找到最终 bibliography，跳过 cite 审计。")
        return set(), set()
    cite_keys: set[str] = set()
    cite_re = re.compile(r"\\cite\{([^}]+)\}")
    for root in (preview / "modules", preview / "paper"):
        if not root.exists():
            continue
        for tex in root.rglob("*.tex"):
            text = tex.read_text(encoding="utf-8", errors="replace")
            for group in cite_re.findall(text):
                cite_keys.update(key.strip() for key in group.split(",") if key.strip())
    bib_text = bib.read_text(encoding="utf-8", errors="replace")
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
        print("[WARN] bibliography 中未被正文使用的条目:")
        for key in sorted(unused):
            print(" -", key)
    else:
        print("[PASS] bibliography 反向审计：无未使用条目。")
    return missing, unused


def compose_commit(preview: Path) -> None:
    run(["git", "add", "-A"], cwd=preview)
    if run(["git", "diff", "--cached", "--quiet"], cwd=preview, check=False).returncode:
        run(
            [
                "git",
                "-c",
                "user.name=CUMCM Preview",
                "-c",
                "user.email=preview@local.invalid",
                "commit",
                "-m",
                "preview: compose owned module snapshots",
            ],
            cwd=preview,
        )


def build(preview: Path, no_build: bool) -> None:
    if no_build:
        print("[INFO] --no-build：仅完成 overlay 与静态审计。")
        return
    paper = preview / "paper"
    if shutil.which("latexmk"):
        run(["latexmk", "-xelatex", "-interaction=nonstopmode", "-halt-on-error", "main.tex"], cwd=paper)
    elif shutil.which("xelatex"):
        run(["xelatex", "-interaction=nonstopmode", "-halt-on-error", "main.tex"], cwd=paper)
        run(["xelatex", "-interaction=nonstopmode", "-halt-on-error", "main.tex"], cwd=paper)
    else:
        print("[WARN] 未找到 latexmk/xelatex，仅完成临时拼装。")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--clean", action="store_true")
    ap.add_argument("--strict", action="store_true", help="缺任一计划分支/精选文献即失败")
    ap.add_argument("--strict-preflight", action="store_true")
    ap.add_argument("--no-open", action="store_true")
    ap.add_argument("--no-build", action="store_true")
    ap.add_argument("--preview-dir")
    ap.add_argument("--base-branch", help="覆盖 config.integration.base_branch")
    ap.add_argument("--skip", action="append", default=[], help="额外跳过模块 key，可重复")
    a = ap.parse_args()

    preview = Path(a.preview_dir).resolve() if a.preview_dir else (ROOT.parent / (ROOT.name + "-preview")).resolve()
    if a.clean:
        clean_preview(preview)
        print("preview 已清理")
        return
    if (ROOT / MARKER).exists():
        raise SystemExit("当前位于 preview worktree，请回到正常 worktree。")

    run(["git", "fetch", "origin", "--prune"])
    if preview.exists() or registered(preview):
        raise SystemExit(f"已存在 preview：{preview}\n先运行 python scripts/preview_merge.py --clean")

    integ = integration_cfg()
    compose_base = a.base_branch or integ.get("base_branch") or CFG.get("default_base", "main")
    audit_base = CFG.get("default_base", "main")
    compose_ref = f"origin/{compose_base}"
    audit_ref = f"origin/{audit_base}"
    for label, ref in (("总装底座", compose_ref), ("责任域审计基线", audit_ref)):
        if not ref_exists(f"refs/remotes/{ref}"):
            raise SystemExit(f"远端缺少{label} {ref}")

    plan = module_plan(set(a.skip))
    print("=== preview overlay plan ===")
    print("compose base:", compose_ref)
    print("audit base:  ", audit_ref)
    for m in plan:
        print(f"  {m['merge_order']:>3}  {m['key']:<12} {m['branch']}")
    if integ.get("curated_references"):
        print("  REF  references    curated one-way sync")

    run(["git", "worktree", "add", "--detach", str(preview), compose_ref])
    (preview / MARKER).write_text("temporary detached full-paper preview\n", encoding="utf-8")
    try:
        for module in plan:
            ref = f"refs/remotes/origin/{module['branch']}"
            if not ref_exists(ref):
                msg = f"远端缺少 {module['branch']}"
                if a.strict:
                    raise RuntimeError(msg)
                print("[WARN]", msg, "，本次跳过")
                continue
            overlay_branch(module, audit_ref, preview)

        sync_curated_references(preview, audit_ref, a.strict)
        compose_commit(preview)

        if run(["git", "diff", "--check", "HEAD^", "HEAD"], cwd=preview, check=False).returncode:
            raise RuntimeError("git diff --check 发现空白错误。")

        missing, _unused = cite_audit(preview)
        if missing:
            raise RuntimeError("正文引用与最终 bibliography 不一致。")

        pre = preview / "scripts/final_preflight.py"
        if pre.exists():
            p = run([sys.executable, str(pre)], cwd=preview, check=False)
            if p.returncode and a.strict_preflight:
                raise RuntimeError("final_preflight 未通过。")

        build(preview, a.no_build)

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
                except Exception as exc:
                    print("[WARN] 无法自动打开 PDF:", exc)
        print("[PASS] preview overlay completed:", preview)
    except Exception:
        print(f"\n临时目录保留用于检查：{preview}")
        raise


if __name__ == "__main__":
    main()
