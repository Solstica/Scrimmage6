#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CFG = ROOT / "config/project.json"
DEFAULT_OUT = ROOT / "output/handoff"

TEXT_SUFFIXES = {
    ".md", ".txt", ".tex", ".py", ".csv", ".json", ".yaml", ".yml",
    ".toml", ".ini", ".cfg", ".xml", ".svg", ".bib", ".sty", ".cls",
    ".sh", ".ps1", ".bat", ".cmd", ".r", ".jl", ".m",
}

FENCE_LANG = {
    ".md": "markdown", ".tex": "tex", ".py": "python", ".csv": "csv",
    ".json": "json", ".yaml": "yaml", ".yml": "yaml", ".toml": "toml",
    ".xml": "xml", ".svg": "xml", ".bib": "bibtex", ".sh": "bash",
    ".ps1": "powershell", ".r": "r", ".jl": "julia", ".m": "matlab",
}


def load_project() -> dict:
    return json.loads(CFG.read_text(encoding="utf-8"))


def get_module(project: dict, key: str) -> dict:
    for module in project["modules"]:
        if module["key"] == key:
            return module
    keys = ", ".join(m["key"] for m in project["modules"])
    raise SystemExit(f"未知模块 {key!r}。可用：{keys}")


def resolve_repo_path(raw: str) -> Path:
    path = (ROOT / raw).resolve()
    try:
        path.relative_to(ROOT.resolve())
    except ValueError as exc:
        raise SystemExit(f"路径必须位于仓库内：{raw}") from exc
    if not path.exists():
        raise SystemExit(f"路径不存在：{raw}")
    return path


def rel(path: Path) -> str:
    return path.resolve().relative_to(ROOT.resolve()).as_posix()


def iter_files(path: Path):
    if path.is_file():
        yield path
        return
    for item in sorted(path.rglob("*")):
        if item.is_file():
            yield item


def is_text_file(path: Path) -> bool:
    if path.suffix.lower() in TEXT_SUFFIXES:
        return True
    if path.suffix == "":
        try:
            path.read_text(encoding="utf-8")
            return True
        except (UnicodeDecodeError, OSError):
            return False
    return False


def sha256_short(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()[:12]


def read_registry(path: Path) -> tuple[list[dict[str, str]], dict[str, int]]:
    if not path.exists():
        return [], {
            "row_count": 0,
            "frozen_count": 0,
            "checked_count": 0,
            "approved_count": 0,
        }
    with path.open("r", encoding="utf-8-sig", newline="") as fh:
        rows = list(csv.DictReader(fh))
    frozen = sum(1 for r in rows if r.get("status", "").strip().upper() == "FROZEN")
    checked = sum(1 for r in rows if r.get("review_state", "").strip().upper() == "CHECKED")
    approved = sum(
        1
        for r in rows
        if r.get("status", "").strip().upper() == "FROZEN"
        and r.get("review_state", "").strip().upper() == "CHECKED"
    )
    return rows, {
        "row_count": len(rows),
        "frozen_count": frozen,
        "checked_count": checked,
        "approved_count": approved,
    }


def current_registry_path(module: dict) -> Path | None:
    candidate = ROOT / module["path"] / "results/registry.csv"
    return candidate if candidate.exists() else None


def registry_is_legacy(path: Path, legacy_roots: list[Path]) -> bool:
    name = path.name.lower()
    if not (name == "registry.csv" or "registry" in name):
        return False
    for root in legacy_roots:
        try:
            path.resolve().relative_to(root.resolve())
            return True
        except ValueError:
            pass
    return False


def legacy_registry_summary(legacy_roots: list[Path]) -> list[dict[str, str]]:
    summary: list[dict[str, str]] = []
    seen: set[str] = set()
    for root in legacy_roots:
        for path in iter_files(root):
            if not registry_is_legacy(path, legacy_roots):
                continue
            key = rel(path)
            if key in seen:
                continue
            seen.add(key)
            try:
                with path.open("r", encoding="utf-8-sig", newline="") as fh:
                    rows = list(csv.DictReader(fh))
            except Exception:
                summary.append({"source": key, "note": "无法解析；未嵌入原始历史 registry。"})
                continue
            if not rows:
                summary.append({"source": key, "note": "历史 registry 为空。"})
                continue
            for row in rows:
                result_id = row.get("result_id") or row.get("id") or "(unnamed)"
                value = row.get("value", "")
                unit = row.get("unit", "")
                old_status = row.get("status", "")
                summary.append(
                    {
                        "source": key,
                        "result_id": result_id,
                        "historical_value": f"{value} {unit}".strip(),
                        "historical_status": old_status or "(missing)",
                        "current_status": "UNVERIFIED_LEGACY_CANDIDATE",
                    }
                )
    return summary


def unique_files(roots: list[Path]) -> list[Path]:
    result: list[Path] = []
    seen: set[str] = set()
    for root in roots:
        for path in iter_files(root):
            key = rel(path)
            if key not in seen:
                seen.add(key)
                result.append(path)
    return result


def module_allowed_paths(module: dict) -> list[str]:
    allowed = [module["path"].rstrip("/") + "/**", module["task"]]
    allowed.extend(module.get("extra_paths", []))
    return allowed


def module_current_roots(module: dict) -> list[Path]:
    roots = [resolve_repo_path(module["path"]), resolve_repo_path(module["task"])]
    roots.extend(resolve_repo_path(path) for path in module.get("extra_paths", []))
    return roots


def make_manifest(project: dict, module: dict, references: list[Path], legacies: list[Path]) -> str:
    registry = current_registry_path(module)
    rows, stats = read_registry(registry) if registry else ([], {
        "row_count": 0,
        "frozen_count": 0,
        "checked_count": 0,
        "approved_count": 0,
    })
    approved_ids = [
        (r.get("result_id") or r.get("id") or "(unnamed)")
        for r in rows
        if r.get("status", "").strip().upper() == "FROZEN"
        and r.get("review_state", "").strip().upper() == "CHECKED"
    ]
    paper_dir = ROOT / module["path"] / "paper"
    paper_files = [rel(p) for p in iter_files(paper_dir)] if paper_dir.exists() else []

    lines = [
        "HANDOFF_MANIFEST:",
        f"  project: {project.get('project_name', '')}",
        f"  module: {module['key']}",
        f"  expected_branch: {module['branch']}",
        f"  canonical_root: {module['path']}",
        f"  task_path: {module['task']}",
        "  allowed_write_paths:",
    ]
    lines.extend(f"    - {p}" for p in module_allowed_paths(module))
    lines += ["  current_paper_files:"]
    if paper_files:
        lines.extend(f"    - {p}" for p in paper_files)
    else:
        lines.append("    - NONE")
    lines += [
        "  current_registry:",
        f"    path: {rel(registry) if registry else 'NONE'}",
        f"    row_count: {stats['row_count']}",
        f"    frozen_count: {stats['frozen_count']}",
        f"    checked_count: {stats['checked_count']}",
        f"    approved_count: {stats['approved_count']}",
        "  approved_current_results:",
    ]
    if approved_ids:
        lines.extend(f"    - {x}" for x in approved_ids)
    else:
        lines.append("    - NONE")
    lines += ["  read_only_reference_paths:"]
    if references:
        lines.extend(f"    - {rel(p)}" for p in references)
    else:
        lines.append("    - NONE")
    lines += ["  legacy_paths:"]
    if legacies:
        lines.extend(f"    - {rel(p)}" for p in legacies)
    else:
        lines.append("    - NONE")
    lines += [
        "  legacy_status_inheritable: false",
        "  ordinary_ai_git_execution_expected: false",
    ]
    return "\n".join(lines)


def append_file_section(out: list[str], title: str, files: list[Path], max_text_bytes: int,
                        legacy_roots: list[Path], embed_legacy_registries: bool):
    out.append(f"\n# {title}\n")
    if not files:
        out.append("(无文件)\n")
        return

    skipped: list[str] = []
    for path in files:
        if registry_is_legacy(path, legacy_roots) and not embed_legacy_registries:
            skipped.append(f"{rel(path)} — 历史 registry 已去身份化，仅在冲突摘要中呈现")
            continue
        size = path.stat().st_size
        if not is_text_file(path) or size > max_text_bytes:
            skipped.append(f"{rel(path)} — {size} bytes — sha256:{sha256_short(path)}")
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            skipped.append(f"{rel(path)} — {size} bytes — sha256:{sha256_short(path)}")
            continue
        lang = FENCE_LANG.get(path.suffix.lower(), "text")
        out.append(f"\n## `{rel(path)}`\n")
        out.append(f"```{lang}\n{text.rstrip()}\n```\n")

    if skipped:
        out.append("\n## 未嵌入正文的文件清单\n")
        for item in skipped:
            out.append(f"- {item}\n")


def build_markdown(project: dict, module: dict, reference_roots: list[Path],
                   legacy_roots: list[Path], max_text_bytes: int,
                   embed_legacy_registries: bool) -> str:
    current_registry = current_registry_path(module)
    _, stats = read_registry(current_registry) if current_registry else ([], {
        "row_count": 0, "frozen_count": 0, "checked_count": 0, "approved_count": 0
    })
    current_files = unique_files(module_current_roots(module))
    ref_files = unique_files(reference_roots)
    legacy_files = unique_files(legacy_roots)

    out: list[str] = [
        f"# {module['key']} AI Handoff\n",
        "以下文件是从当前仓库状态自动导出的普通 AI 交接包。"
        "如果后文历史材料与顶部 Manifest 冲突，以 Manifest 和 CURRENT STATE 为准。\n",
        "```yaml\n" + make_manifest(project, module, reference_roots, legacy_roots) + "\n```\n",
        "## 强制解释规则\n",
        "- `canonical_root` 是当前模块唯一正式真源；历史目录再完整也不能替代它。\n",
        "- 当前结果状态只认 CURRENT REGISTRY。历史仓库中的 `FROZEN`、`CHECKED` 或类似状态不得继承。\n",
        "- 正文关键数值只有在当前 registry 达到 `FROZEN + CHECKED` 后才可作为正式结果使用。\n",
        "- `work/archive/` 与 `legacy_paths` 仅作只读参考；冲突时标记 `NEEDS_REVIEW`，不得自行猜测。\n",
        "- 问题模块固定使用 `code/`、`data/processed/`、`figures/`、`figures/editable/`、`tables/`、`results/registry.csv`；不要创造 `src/`、`final2/` 等新真源。\n",
        "- 未验证结果不要先写进正式正文，也不要发明 `\\TODO{}`、`\\placeholder{}` 等未定义宏；未完成事项写入任务文件。\n",
        "- 普通聊天 AI 若没有仓库执行权限，不得声称已经运行 Git/Python/LaTeX 或已经修改仓库；应返回准确的仓库相对路径、替换文本或修改建议，由人落盘。\n",
        "\n# CURRENT STATE — 当前状态\n",
    ]

    if current_registry:
        out += [
            f"当前 registry：`{rel(current_registry)}`\n",
            f"- row_count: {stats['row_count']}\n",
            f"- frozen_count: {stats['frozen_count']}\n",
            f"- checked_count: {stats['checked_count']}\n",
            f"- approved_count (`FROZEN + CHECKED`): {stats['approved_count']}\n",
        ]
        if stats["approved_count"] == 0:
            out.append("\n**当前没有获准直接作为正式论文关键数值的结果。**\n")
    else:
        out.append("当前模块没有标准结果 registry；不应自行创建或推断结果状态。\n")

    append_file_section(
        out, "CURRENT FILES — 当前正式模块与实时待办",
        current_files, max_text_bytes, legacy_roots, embed_legacy_registries
    )

    if ref_files:
        out.append(
            "\n# READ-ONLY REFERENCES — 当前只读参考\n"
            "这些是为本任务显式附带的当前参考资料，不属于允许写入路径。\n"
        )
        append_file_section(
            out, "REFERENCE FILES", ref_files, max_text_bytes,
            legacy_roots, embed_legacy_registries
        )

    if legacy_files:
        out.append(
            "\n# LEGACY MATERIALS — 历史材料，不是当前状态\n"
            "以下内容只用于迁移、比较和追溯。所有历史结果默认是 "
            "`UNVERIFIED_LEGACY_CANDIDATE`，除非当前 registry 重新登记并完成验证。\n"
        )
        append_file_section(
            out, "LEGACY FILES [NOT CURRENT]", legacy_files, max_text_bytes,
            legacy_roots, embed_legacy_registries
        )
        if not embed_legacy_registries:
            summary = legacy_registry_summary(legacy_roots)
            out.append("\n# LEGACY RESULT CONFLICT SUMMARY — 去身份化历史结果\n")
            if not summary:
                out.append("未发现可解析的历史 registry。\n")
            else:
                for item in summary:
                    out.append("\n- " + "; ".join(f"{k}={v}" for k, v in item.items()) + "\n")
                out.append(
                    "\n以上历史状态仅描述旧工程当时的记录，"
                    "不能改变顶部 CURRENT REGISTRY 的事实状态。\n"
                )

    out += [
        "\n# AI 输出要求\n",
        f"1. 先说明当前正式真源是否为 `{module['path']}/`。\n",
        "2. 区分“当前正式内容”“只读参考”“历史迁移候选”“明确过期内容”。\n",
        "3. 任何历史数值在重新验证前不得称为当前冻结结果。\n",
        f"4. 建议修改必须限定在：{', '.join(module_allowed_paths(module))}。\n",
        f"5. 新任务、风险和人工判断写入 `{module['task']}`，使用 `NEEDS_REVIEW`。\n",
        "6. 不拥有仓库执行权限时，只给出可由协作者落盘的内容，不虚构执行结果。\n",
    ]
    return "".join(out)


def write_zip(zip_path: Path, markdown_path: Path, module: dict,
              reference_roots: list[Path], legacy_roots: list[Path],
              embed_legacy_registries: bool):
    with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        zf.write(markdown_path, arcname="HANDOFF.md")
        rules = [
            ROOT / "docs/AI_HANDOFF_PROMPT.md",
            ROOT / "docs/RESOURCE_MAP.md",
            ROOT / "docs/PAPER_STYLE_GUIDE.md",
        ]
        for path in rules:
            if path.exists():
                zf.write(path, arcname=f"_rules/{path.name}")

        for path in unique_files(module_current_roots(module)):
            zf.write(path, arcname=f"CURRENT/{rel(path)}")

        for path in unique_files(reference_roots):
            zf.write(path, arcname=f"REFERENCE/{rel(path)}")

        for path in unique_files(legacy_roots):
            if registry_is_legacy(path, legacy_roots) and not embed_legacy_registries:
                continue
            zf.write(path, arcname=f"LEGACY_NOT_CURRENT/{rel(path)}")

        zf.writestr(
            "LEGACY_NOT_CURRENT/README.txt",
            "本目录全部为历史材料，不是当前正式真源。历史状态不得继承；"
            "当前状态只认 HANDOFF.md 中的 CURRENT STATE 和 CURRENT REGISTRY。\n",
        )


def main():
    parser = argparse.ArgumentParser(
        description="导出普通 AI 可读的模块交接包，显式隔离当前状态、只读参考与历史材料。"
    )
    parser.add_argument("module", help="模块 key，例如 q2")
    parser.add_argument("--format", choices=["md", "zip", "both"], default="both")
    parser.add_argument(
        "--reference", action="append", default=[],
        help="额外只读当前参考路径，可重复，例如 --reference shared/code"
    )
    parser.add_argument(
        "--legacy", action="append", default=[],
        help="历史/归档参考路径，可重复，例如 --legacy work/archive/imports/s2_snapshot"
    )
    parser.add_argument(
        "--output-dir", default=str(DEFAULT_OUT.relative_to(ROOT)),
        help="输出目录，默认 output/handoff"
    )
    parser.add_argument(
        "--max-text-kb", type=int, default=256,
        help="Markdown 中单个文本文件最大嵌入大小，默认 256 KiB；ZIP 不受此限制"
    )
    parser.add_argument(
        "--include-legacy-registries", action="store_true",
        help="默认不嵌入历史 registry 原文以防状态串线；仅审计确有需要时启用"
    )
    args = parser.parse_args()

    project = load_project()
    module = get_module(project, args.module)
    if not module.get("active", True):
        print(f"[WARN] 模块 {args.module} 当前在 config/project.json 中为 inactive。")

    reference_roots = [resolve_repo_path(p) for p in args.reference]
    legacy_roots = [resolve_repo_path(p) for p in args.legacy]
    out_dir = (ROOT / args.output_dir).resolve()
    try:
        out_dir.relative_to(ROOT.resolve())
    except ValueError as exc:
        raise SystemExit("输出目录必须位于仓库内。") from exc
    out_dir.mkdir(parents=True, exist_ok=True)

    stem = f"{args.module}_handoff"
    md_path = out_dir / f"{stem}.md"
    zip_path = out_dir / f"{stem}.zip"

    markdown = build_markdown(
        project, module, reference_roots, legacy_roots,
        max(1, args.max_text_kb) * 1024,
        args.include_legacy_registries,
    )
    md_path.write_text(markdown, encoding="utf-8")

    if args.format in {"zip", "both"}:
        write_zip(
            zip_path, md_path, module, reference_roots, legacy_roots,
            args.include_legacy_registries
        )

    if args.format == "zip":
        md_path.unlink(missing_ok=True)
        print(f"已生成：{rel(zip_path)}")
    elif args.format == "md":
        print(f"已生成：{rel(md_path)}")
    else:
        print(f"已生成：{rel(md_path)}")
        print(f"已生成：{rel(zip_path)}")


if __name__ == "__main__":
    main()
