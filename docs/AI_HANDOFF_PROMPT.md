# AI 单文件交接说明与规范提示词

> 这份文件可以单独发给任何队友的 AI。更推荐直接运行 `python scripts/export_handoff.py <module-key>`，让脚本自动把当前真源、实时待办、当前 registry、只读参考和历史材料分层打包。

## A. 这个仓库怎么理解

这是一个数学建模竞赛模块化仓库。原则：

- 一个章节/问题一个独立分支；
- 一个章节只有一个正文源；
- 固定路径不随比赛过程改变；
- 每个模块都有实时待办；
- 正式数值必须可追溯到当前代码/结果文件；
- 全文只在临时 preview 中合并，不靠长期“总稿分支”日常开发；
- `main` 只保存稳定版本。

任何导出的 AI handoff 都只是当前仓库状态的携带快照，不是新的真源。

## B. 永久固定的资源路径

| 模块 | key | 正文/主资源 | 分支 |
|---|---|---|---|
| 摘要 | `abstract` | `modules/00_abstract/` | `feature/abstract` |
| 问题重述 | `restatement` | `modules/10_restatement/` | `feature/restatement` |
| 符号说明 | `notation` | `modules/11_notation/` | `feature/notation` |
| 模型假设 | `assumptions` | `modules/12_assumptions/` | `feature/assumptions` |
| 问题一 | `q1` | `modules/20_q1/` | `feature/q1` |
| 问题二 | `q2` | `modules/30_q2/` | `feature/q2` |
| 问题三 | `q3` | `modules/40_q3/` | `feature/q3` |
| 问题四 | `q4` | `modules/50_q4/` | `feature/q4` |
| 模型评价 | `evaluation` | `modules/60_evaluation/` | `feature/evaluation` |
| 参考文献 | `references` | `modules/70_references/` | `feature/references` |
| 附录 | `appendix` | `modules/80_appendix/` | `feature/appendix` |
| AI使用报告 | `ai-report` | `modules/90_ai_report/` | `feature/ai-report` |
| 跨问共享代码 | `shared` | `shared/` | `feature/shared` |
| 全文格式/标题/目录/页码 | `paper-shell` | `paper/` | `feature/paper-shell` |

问题模块固定位置：

```text
data/raw/                       官方原始附件，原则上不改写
data/external/                  外部补充数据及来源
modules/<q>/paper/              单问正文
modules/<q>/code/               单问代码
modules/<q>/data/processed/     单问派生数据
modules/<q>/figures/            正文引用图
modules/<q>/figures/editable/   Origin/Excel/AGX等可编辑图源
modules/<q>/tables/             精确结果表
modules/<q>/results/registry.csv 当前结果状态登记
work/tasks/<key>.md             当前模块实时待办
work/archive/                   旧模型/旧图/旧路线，只读
output/final/                   正式交付物
output/handoff/                 临时 AI 交接包，不是仓库真源
```

不要自行创造 `modules/<q>/src/`、`final2/`、第二套模块树或第二套全文 TeX。

## C. 开工前强制动作（有仓库执行权限的 AI）

假设本次模块是 `q2`：

```bash
git status
git fetch origin --prune
git pull --ff-only
python scripts/workflow.py start q2
```

`workflow.py start` 会打印当前模块、期望分支、允许修改路径、任务文件、实时待办和 Git 状态。当前分支与期望分支不一致时先停止修改。

## D. 普通聊天 AI 与仓库代理必须区分

普通 ChatGPT、DeepSeek 等如果只收到文件、没有仓库执行权限：

- 不得声称已经运行 Git/Python/LaTeX；
- 不得声称已经真正修改仓库；
- 应返回准确的仓库相对路径、完整替换文本/修改建议、需要复核项；
- 由协作者把结果落回正式仓库。

给普通聊天 AI 最稳妥的方式不是手工拼文件，而是：

```bash
python scripts/export_handoff.py q2 --format md
python scripts/export_handoff.py q2 --format zip
```

需要带当前只读参考：

```bash
python scripts/export_handoff.py q2 --reference shared/code
```

需要带历史迁移材料：

```bash
python scripts/export_handoff.py q2 --legacy work/archive/imports/<snapshot>
```

导出器会生成 `HANDOFF_MANIFEST`，显式写明当前 canonical root、当前 registry 行数与状态、允许写入路径、只读参考和 legacy 路径。

## E. 当前真源与历史材料必须隔离

- `canonical_root` / 当前模块目录才是正式真源。
- `work/archive/`、导入快照和 `legacy_paths` 全部是只读历史资料。
- 历史文件即使更完整、更新日期更晚、旧 registry 写过 `FROZEN` 或 `CHECKED`，也不能自动变成当前状态。
- **当前结果状态只认当前模块自己的 `results/registry.csv`。**
- 历史 `FROZEN` 不具有跨仓库、跨快照继承效力。
- 历史资料冲突时标记 `NEEDS_REVIEW`，不得凭“看起来更新”自行定版。
- 正式正文不得长期引用 `work/archive/...` 中的图、表、代码和结果；经确认可复用的内容必须迁移到当前模块固定路径。

`export_handoff.py` 默认不向普通 AI 原样嵌入历史 registry，而只生成去身份化的历史冲突摘要；只有专门做历史审计时才使用 `--include-legacy-registries`。

## F. 实时待办必须同步

每个模块任务文件：

```text
work/tasks/<key>.md
```

工作过程中发现新任务、尚未完成的图/表/代码、阻塞、需要复核的参数/引用/结论、已完成事项，都必须实时写回任务文件，不只留在聊天里。

需要人工判断统一写：

```text
NEEDS_REVIEW / 需要复核
```

未验证结果不要先写进正式正文，也不要自行发明 `\TODO{}`、`\placeholder{}` 等模板未定义宏来绕过任务管理。

## G. 责任域

当前模块只修改：

```text
<该模块主路径>/**
work/tasks/<key>.md
```

例如 `q2`：

```text
modules/30_q2/**
work/tasks/q2.md
```

跨模块问题只记录依赖，不直接覆盖其他章节。禁止：

```text
git push --force
git reset --hard
新建第二套全文 document.tex / final.tex
新建 final2 / 真的final / 论文汇总 等并行真源
从旧稿、截图、范文或历史 JSON/registry 手抄关键结果覆盖当前结果
```

## H. 正式结果状态

问题模块 `results/registry.csv` 使用：

```text
DRAFT       正在计算或尚未验证
VALIDATED   已复算，等待最终检查
FROZEN      已完成规定检查，可进入正式论文
```

复核状态：

```text
NEEDS_REVIEW
CHECKED
```

正文关键数值只使用当前项目：

```text
FROZEN + CHECKED
```

模型/代码改变且影响结果后，相关结果重新回到 `DRAFT`。

## I. 论文格式不要重新设计

完整规范见 `docs/PAPER_STYLE_GUIDE.md`。核心固定口径：

- A4，四边 `25 mm`；
- 中文正文 Windows 优先宋体，英文/数字优先 Times New Roman；
- 正文小四，段首缩进2字符，行距基准1.38；
- 题目三号加粗居中；
- 一级标题中文序号且居中，二级 `4.1`，三级 `4.1.1`；
- 目录显示到二级标题；
- 正文从问题重述重新计第1页；
- 参考文献、附录、AI使用报告分别另起一页；
- 三线表，浅蓝表头，不画纵线；
- 单个小图 `0.44\textwidth`；两个小图总宽 `0.88\textwidth`；Origin 合成双面板整张 `0.88\textwidth`；总体流程图约 `1.0\textwidth`；机理图通常 `0.70\textwidth`；
- 图题、表题由 LaTeX 生成，不把大标题做进图片；
- 伪代码统一使用 `algorithm2e`；
- 普通公式尽量行内，核心模型/约束/结果才单独编号；
- 不在章节文件里重定义字体、页边距、标题格式。

非 `paper-shell` 任务发现公共排版问题，只记录依赖。

## J. 推荐的单问写作结构

按题意选用，不机械堆标题：

```text
问题描述与分析
→ 总体流程图
→ 必要预备/数据处理
→ 模型建立
→ 模型汇总
→ 模型求解
→ 结果与分析
→ 对主要不确定性的检验
```

优化问题必须明确决策变量、目标函数、约束、模型汇总。

## K. 图表规则

每张正式图必须能回答：

1. 数据来自哪里？
2. 对应哪个当前代码/表格？
3. 可编辑图源在哪里？
4. 正文用它说明什么？

可编辑图源统一放 `figures/editable/`。历史图在未确认生成链前只能作为迁移候选，不得因为“看起来对应”就直接视为当前正式图。

## L. 结束本轮前强制动作（有仓库执行权限）

```bash
python scripts/workflow.py finish <module-key>
git diff
git status
```

同步更新任务文件，只 `git add` 明确需要提交的文件。结束汇报至少包含本轮修改、结果/图/代码准确路径、剩余待办、阻塞和需要复核项。

---

# 可直接复制给有仓库权限 AI 的规范提示词

```text
你正在 CUMCM 模块化 Git 仓库中工作，本次模块是 <模块key>，任务是：<本次任务>。
开始任何修改前完整阅读 AGENTS.md、README.md、docs/RESOURCE_MAP.md、docs/PAPER_STYLE_GUIDE.md，并运行 `python scripts/workflow.py start <模块key>`。
围绕 `work/tasks/<模块key>.md` 的实时待办推进，新任务/阻塞/风险/完成项/需要复核项实时写回。
只修改当前模块责任域；固定路径以 config/project.json 和资源地图为准，不创造 src/final2/第二套全文等并行真源。
当前结果状态只认当前模块 results/registry.csv；历史 archive/import 中的 FROZEN/CHECKED 不得继承。正文关键数值必须来自当前 FROZEN + CHECKED。
非 paper-shell 任务不得重定义论文公共格式；需要人工判断统一标记 NEEDS_REVIEW。
禁止 force push/reset-hard。
结束前更新待办，运行 `python scripts/workflow.py finish <模块key>`，检查 git diff，并汇报修改、准确路径、剩余待办和需要复核项。
```

# 给普通聊天 AI 的最简入口

先由仓库协作者生成：

```bash
python scripts/export_handoff.py <module-key> --format md
```

然后只需要把生成的 `output/handoff/<module-key>_handoff.md` 发给 AI，并说明本轮任务。AI 应优先服从文件顶部的 `HANDOFF_MANIFEST` 和 `CURRENT STATE`。
