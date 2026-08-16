#!/usr/bin/env python3
from __future__ import annotations
import argparse, csv, re
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def tex_files():
    return list((ROOT / "modules").glob("*/paper/*.tex")) + list((ROOT / "paper").glob("*.tex"))


def read(path: Path):
    return path.read_text(encoding="utf-8", errors="replace")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--post-build", action="store_true")
    a = ap.parse_args()

    errors = []
    warns = []
    labels = defaultdict(list)

    module_tex = list((ROOT / "modules").glob("*/paper/*.tex"))
    forbidden_global_style = (
        r"\geometry{",
        r"\setmainfont",
        r"\setCJKmainfont",
        r"\renewcommand\section",
        r"\renewcommand{\baselinestretch}",
    )

    for p in tex_files():
        t = read(p)
        for token in ("??", "[?]", "TODO", "FIXME"):
            if token in t:
                warns.append(f"{p.relative_to(ROOT)}: 发现 {token}")
        for x in re.findall(r"\\label\{([^}]+)\}", t):
            labels[x].append(p)

    for p in module_tex:
        t = read(p)
        for token in forbidden_global_style:
            if token in t:
                errors.append(f"{p.relative_to(ROOT)}: 章节正文不得重定义公共样式 {token}")

    for k, ps in labels.items():
        if len(ps) > 1:
            errors.append(f"重复 label {k}: " + ", ".join(str(p.relative_to(ROOT)) for p in ps))

    for reg in ROOT.glob("modules/*/results/registry.csv"):
        with reg.open(encoding="utf-8", newline="") as f:
            for row in csv.DictReader(f):
                if not row.get("result_id"):
                    continue
                if row.get("used_in_paper", "").strip().lower() in {"yes", "true", "1", "y"}:
                    if row.get("status") != "FROZEN" or row.get("review_state") != "CHECKED":
                        errors.append(
                            f"{reg.relative_to(ROOT)}: {row['result_id']} 已用于正文但不是 FROZEN+CHECKED"
                        )

    maintex = read(ROOT / "paper/main.tex")
    required_main = (
        r"\input{settings.tex}",
        r"\ifshowtoc",
        r"\tableofcontents",
        r"\pagenumbering{arabic}",
        r"\setcounter{page}{1}",
    )
    for token in required_main:
        if token not in maintex:
            errors.append(f"paper/main.tex 缺少公共结构: {token}")

    if maintex.count(r"\clearpage") < 4:
        errors.append("paper/main.tex 分页不足：参考文献、附录、AI使用报告应各自另起一页")

    settings = ROOT / "paper/settings.tex"
    if not settings.exists() or "\\newif\\ifshowtoc" not in read(settings):
        errors.append("paper/settings.tex 缺少目录开关")

    abstract = ROOT / "modules/00_abstract/paper/abstract.tex"
    if abstract.exists() and re.search(r"\\section\*?\{", read(abstract)):
        errors.append("摘要模块不应自行创建 section；摘要标题由公共模板负责")

    appendix = ROOT / "modules/80_appendix/paper/appendix.tex"
    if appendix.exists() and re.search(r"\\subsection\{", read(appendix)):
        errors.append("附录不应使用有编号 subsection，避免目录出现错误章节号")

    if not (ROOT / "modules/20_q1/paper/q1_algorithm.tex").exists():
        errors.append("问题一伪代码示例 q1_algorithm.tex 缺失")

    if a.post_build:
        log = ROOT / "paper/main.log"
        if log.exists():
            log_text = read(log)
            if "Overfull \\hbox" in log_text:
                warns.append("LaTeX 日志存在 Overfull \\hbox")
            if "undefined references" in log_text.lower() or "citation" in log_text.lower() and "undefined" in log_text.lower():
                errors.append("LaTeX 日志存在未解析引用或文献引用")

    for w in dict.fromkeys(warns):
        print("[WARN]", w)
    for e in dict.fromkeys(errors):
        print("[FAIL]", e)
    if not errors:
        print("[PASS] final preflight")
    raise SystemExit(1 if errors else 0)


if __name__ == "__main__":
    main()
