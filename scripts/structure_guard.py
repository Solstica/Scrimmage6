#!/usr/bin/env python3
from __future__ import annotations
import argparse, json, subprocess
from pathlib import Path, PurePosixPath

ROOT = Path(__file__).resolve().parents[1]
CFG = json.loads((ROOT / "config/project.json").read_text(encoding="utf-8"))
ALLOWED_ROOT = {".github", "config", "data", "docs", "modules", "output", "paper", "scripts", "shared", "work"}
FORBIDDEN_DIR = {"final_paper", "paper_final", "full_paper", "论文汇总", "总论文", "最终论文", "真的final"}
FORBIDDEN_TEX = {"document.tex", "final.tex", "final_paper.tex", "paper_final.tex", "full_paper.tex", "总论文.tex", "最终论文.tex"}
REQUIRED = {
    "paper/main.tex",
    "paper/preamble.tex",
    "paper/settings.tex",
    "paper/title.tex",
    "docs/PAPER_STYLE_GUIDE.md",
    "docs/AI_HANDOFF_PROMPT.md",
    "scripts/export_handoff.py",
    "modules/20_q1/paper/q1_algorithm.tex",
}
for m in CFG["modules"]:
    if m["key"] in {"shared", "paper-shell"}:
        continue
    tex = {
        "abstract": "abstract.tex",
        "restatement": "restatement.tex",
        "notation": "notation.tex",
        "assumptions": "assumptions.tex",
        "q1": "q1.tex",
        "q2": "q2.tex",
        "q3": "q3.tex",
        "q4": "q4.tex",
        "evaluation": "evaluation.tex",
        "references": "references.tex",
        "appendix": "appendix.tex",
        "ai-report": "ai_report.tex",
    }[m["key"]]
    REQUIRED.add(f"{m['path']}/paper/{tex}")


def git(*args):
    p = subprocess.run(["git", *args], cwd=ROOT, text=True, capture_output=True)
    if p.returncode:
        raise SystemExit(p.stderr)
    return p.stdout


def changed(base, head):
    return [x for x in git("diff", "--name-only", f"{base}...{head}").splitlines() if x]


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
    ap.add_argument("--base", required=True)
    ap.add_argument("--head", required=True)
    ap.add_argument("--branch", default="")
    a = ap.parse_args()
    files = changed(a.base, a.head)
    errors = []

    for f in files:
        p = PurePosixPath(f)
        parts = p.parts
        if len(parts) > 1 and parts[0] not in ALLOWED_ROOT:
            errors.append(f"未授权一级目录: {f}")
        if any(x.lower() in {y.lower() for y in FORBIDDEN_DIR} for x in parts[:-1]):
            errors.append(f"禁止第二套全文目录: {f}")
        if p.name.lower() in {x.lower() for x in FORBIDDEN_TEX}:
            errors.append(f"禁止第二套全文 TeX: {f}")

    mod = next((m for m in CFG["modules"] if m["branch"] == a.branch), None)
    if mod:
        for f in files:
            if not allowed_path(f, mod):
                errors.append(f"{a.branch} 越界修改: {f}")

    tree = set(git("ls-tree", "-r", "--name-only", a.head).splitlines())
    for r in REQUIRED:
        if r not in tree:
            errors.append(f"canonical source 缺失: {r}")

    if errors:
        print("STRUCTURE GUARD FAILED")
        for i, e in enumerate(dict.fromkeys(errors), 1):
            print(f"{i}. {e}")
        raise SystemExit(1)

    print(f"STRUCTURE GUARD PASS: {len(files)} changed path(s)")


if __name__ == "__main__":
    main()
