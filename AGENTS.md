# AI / Agent 强制协作规则

本文件适用于所有支持仓库级指令的 AI 编程/写作代理。

## 开始任务前

1. 阅读 `README.md`、`docs/RESOURCE_MAP.md`、`docs/PAPER_STYLE_GUIDE.md`、`config/project.json`。
2. 如需要完整单文件交接，读取 `docs/AI_HANDOFF_PROMPT.md`。
3. 必须运行 `python scripts/workflow.py start <module-key>`。
4. 必须读取当前模块 `work/tasks/<module-key>.md`，以其中实时待办为工作入口。
5. 文件位置只以资源地图和配置为准；先自行查找固定路径，不要求协作者重复说明已经固定的资源位置。

## 修改边界

- 一个任务只修改一个责任域。
- 当前模块唯一正文源位于其 `modules/.../paper/`。
- `paper/` 仅由 `feature/paper-shell` 修改；章节分支不得编辑全文入口、字体、页边距、标题层级、目录和公共图表样式。
- 跨问共享内核只进入 `shared/`，由 `feature/shared` 维护。
- `work/archive/` 与显式 legacy/import 目录均为只读历史材料；不得在那里继续开发，也不得让正式正文长期引用其中的图、表、代码或结果。
- 历史仓库中的 `FROZEN`、`CHECKED` 等状态不得继承到当前项目。当前结果状态只认当前模块自己的 `results/registry.csv`。
- 问题模块固定使用 `code/`、`data/processed/`、`figures/`、`figures/editable/`、`tables/`、`results/`；不要自行创造 `src/` 等并行结构。
- 不新建第二套全文 TeX、第二套模块树或 `final2/真的final/论文汇总` 等目录。
- 不使用 `git push --force`、`git reset --hard` 处理协作冲突。

## 论文格式

- 默认沿用 `docs/PAPER_STYLE_GUIDE.md`，不要自行重新设计。
- 图表、表格、公式、伪代码、代码附录均使用仓库既有示例和宏。
- 非 `paper-shell` 任务若发现公共格式问题，只记录依赖/需要复核项，不直接改全局样式。
- 未验证结果不要先写进正式正文；也不要自行发明 `\TODO{}`、`\placeholder{}` 等模板未定义宏。未完成事项写入当前任务文件。

## 待办与检查

- 实际工作出现新任务、阻塞、风险或待复核项时，实时写入当前模块任务文件，不只留在聊天里。
- 需要人工判断的事项写为 `NEEDS_REVIEW` / `需要复核`；检查可由管理员或指定复核成员完成，不绑定固定角色。
- 正文关键结果只能来自当前项目 `FROZEN + CHECKED` 的结果登记。

## 普通聊天 AI 与仓库代理的区别

- 有仓库执行权限的代理按本文件运行命令并落盘。
- 没有仓库执行权限的普通聊天 AI 不得声称已经运行 Git/Python/LaTeX 或已经修改仓库；应返回准确的仓库相对路径、替换文本、补丁建议和需要复核项，由协作者落盘。
- 给普通聊天 AI 交接时，优先运行 `python scripts/export_handoff.py <module-key>` 生成结构化交接包，避免手工拼接当前文件与历史资料。

## 结束任务前

1. 更新当前模块任务文件；
2. 运行 `python scripts/workflow.py finish <module-key>`；
3. 检查 `git diff` 与越界修改；
4. 汇报修改、结果位置、未完成待办、阻塞和需要复核项。
