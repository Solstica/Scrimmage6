# 固定资源地图

本文件是“东西在哪里”的唯一人工可读索引；机器可读版本见 `config/project.json`。任何人或 AI 在询问资源位置前，应先查本表或运行 `python scripts/workflow.py start <key>`。

## 论文模块

| key | 内容 | 正文 | 其他资源 | 待办 | 分支 |
|---|---|---|---|---|---|
| abstract | 摘要 | `modules/00_abstract/paper/abstract.tex` | `modules/00_abstract/` | `work/tasks/abstract.md` | `feature/abstract` |
| restatement | 问题重述 | `modules/10_restatement/paper/restatement.tex` | `modules/10_restatement/` | `work/tasks/restatement.md` | `feature/restatement` |
| notation | 符号说明 | `modules/11_notation/paper/notation.tex` | `modules/11_notation/` | `work/tasks/notation.md` | `feature/notation` |
| assumptions | 模型假设 | `modules/12_assumptions/paper/assumptions.tex` | `modules/12_assumptions/` | `work/tasks/assumptions.md` | `feature/assumptions` |
| q1 | 问题一 | `modules/20_q1/paper/q1.tex` | `code/`、`data/processed/`、`figures/`、`tables/`、`results/` | `work/tasks/q1.md` | `feature/q1` |
| q2 | 问题二 | `modules/30_q2/paper/q2.tex` | 同上 | `work/tasks/q2.md` | `feature/q2` |
| q3 | 问题三 | `modules/40_q3/paper/q3.tex` | 同上 | `work/tasks/q3.md` | `feature/q3` |
| q4 | 问题四 | `modules/50_q4/paper/q4.tex` | 同上 | `work/tasks/q4.md` | `feature/q4` |
| evaluation | 模型评价 | `modules/60_evaluation/paper/evaluation.tex` | `modules/60_evaluation/` | `work/tasks/evaluation.md` | `feature/evaluation` |
| references | 参考文献 | `modules/70_references/paper/references.tex` | `modules/70_references/` | `work/tasks/references.md` | `feature/references` |
| appendix | 附录 | `modules/80_appendix/paper/appendix.tex` | `modules/80_appendix/` | `work/tasks/appendix.md` | `feature/appendix` |
| ai-report | AI使用报告 | `modules/90_ai_report/paper/ai_report.tex` | `modules/90_ai_report/` | `work/tasks/ai-report.md` | `feature/ai-report` |
| shared | 跨问共享代码/接口 | — | `shared/` | `work/tasks/shared.md` | `feature/shared` |
| paper-shell | 标题、目录、页码、公共样式 | `paper/main.tex` | `paper/preamble.tex`、`paper/settings.tex`、`paper/title.tex` | `work/tasks/paper-shell.md` | `feature/paper-shell` |

### 特殊示例文件

- 问题一伪代码格式：`modules/20_q1/paper/q1_algorithm.tex`
- 论文完整格式规范：`docs/PAPER_STYLE_GUIDE.md`
- 普通 AI 交接规则：`docs/AI_HANDOFF_PROMPT.md`
- 普通 AI 交接导出器：`scripts/export_handoff.py`

## 数据与产物

- 官方原始附件：`data/raw/`。默认只追加、不改写原件。
- 外部补充数据：`data/external/`，同时记录来源。
- 单问派生数据：对应 `modules/<q>/data/processed/`。
- 正文引用图：对应模块 `figures/`。
- Origin/Excel/AGX 等可编辑图源：对应模块 `figures/editable/`。
- 精确结果表：对应模块 `tables/`。
- 结果状态：对应问题 `results/registry.csv`。
- 最终提交物：`output/final/`。
- 可再生临时产物：`output/build/`。
- 普通 AI 临时交接包：`output/handoff/`，由 `scripts/export_handoff.py` 生成，默认不提交 Git。
- 旧模型/旧图/废弃路线：`work/archive/`，只读归档；活动脚本与正式正文不得引用。

## 问题模块固定子目录

问题模块只使用以下既定结构，不自行创造 `src/`、`final/`、`old2/` 等并行位置：

```text
modules/<q>/paper/
modules/<q>/code/
modules/<q>/data/processed/
modules/<q>/figures/
modules/<q>/figures/editable/
modules/<q>/tables/
modules/<q>/results/registry.csv
```

## 历史资料与普通 AI 交接

历史资料即使位于导入快照中、文件更完整、旧 registry 标记过 `FROZEN`，也不能替代当前模块真源。当前状态只认当前模块自己的 `results/registry.csv`。

普通聊天 AI 不直接读 Git 仓库时，优先使用：

```bash
python scripts/export_handoff.py q2 --format md
python scripts/export_handoff.py q2 --format zip
```

需要附加当前只读参考（例如共享代码）：

```bash
python scripts/export_handoff.py q2 --reference shared/code
```

需要附加历史迁移材料：

```bash
python scripts/export_handoff.py q2 --legacy work/archive/imports/<snapshot>
```

导出器会把 `CURRENT`、`REFERENCE`、`LEGACY_NOT_CURRENT` 分层，并默认不把历史 registry 原文直接塞给普通 AI，而是生成去身份化冲突摘要，避免把旧 `FROZEN` 误认成当前状态。

## 公共格式资源

只允许 `feature/paper-shell` 改：

```text
paper/main.tex       全文装配与分页
paper/preamble.tex   字体、行距、标题、图表、算法、代码样式
paper/settings.tex   目录等公共开关
paper/title.tex      论文标题文字
```

章节分支如果遇到公共排版问题，应在任务文件记录依赖，不直接在自己的 TeX 中重定义全局格式。
