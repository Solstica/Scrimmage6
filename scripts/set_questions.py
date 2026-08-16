#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CFG = ROOT / "config/project.json"
MAIN = ROOT / "paper/main.tex"


def update_main_tex(text: str, questions: int) -> str:
    r"""Enable q1..qN and comment out the remaining canonical question inputs.

    Deliberately avoids re.sub replacement strings containing LaTeX backslashes,
    which can be interpreted as regex replacement escapes (for example \input).
    """
    found: set[int] = set()
    out: list[str] = []

    for original in text.splitlines():
        stripped = original.lstrip()
        indent = original[: len(original) - len(stripped)]
        candidate = stripped
        if candidate.startswith("%"):
            candidate = candidate[1:].lstrip()

        replaced = False
        for i in range(1, 5):
            canonical = rf"\input{{../modules/{10 + i * 10:02d}_q{i}/paper/q{i}.tex}}"
            if candidate == canonical:
                found.add(i)
                out.append(indent + (canonical if i <= questions else "% " + canonical))
                replaced = True
                break

        if not replaced:
            out.append(original)

    missing = sorted(set(range(1, 5)) - found)
    if missing:
        raise SystemExit(
            "paper/main.tex 缺少规范问题入口："
            + ", ".join(f"q{i}" for i in missing)
            + "。未写入任何初始化修改。"
        )

    suffix = "\n" if text.endswith("\n") else ""
    return "\n".join(out) + suffix


def main() -> None:
    ap = argparse.ArgumentParser(description="初始化比赛题目数（当前模板支持1-4问）")
    ap.add_argument("questions", type=int, choices=range(1, 5))
    ap.add_argument("--name")
    args = ap.parse_args()

    # 先在内存中完成并验证两份输出，全部成功后再落盘，避免半初始化状态。
    cfg = json.loads(CFG.read_text(encoding="utf-8"))
    if args.name:
        cfg["project_name"] = args.name
    for module in cfg["modules"]:
        if re.fullmatch(r"q[1-4]", module["key"]):
            module["active"] = int(module["key"][1:]) <= args.questions
    cfg_out = json.dumps(cfg, ensure_ascii=False, indent=2) + "\n"

    main_text = MAIN.read_text(encoding="utf-8")
    main_out = update_main_tex(main_text, args.questions)

    CFG.write_text(cfg_out, encoding="utf-8", newline="\n")
    MAIN.write_text(main_out, encoding="utf-8", newline="\n")

    print(
        f"已设置为 {args.questions} 问"
        + (f"，项目名为 {args.name}" if args.name else "")
        + "。请检查 git diff；确认无误后提交，再创建 feature 分支/worktree。"
    )


if __name__ == "__main__":
    main()
