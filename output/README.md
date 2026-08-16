# Output

- `final/`：稳定集成后可提交的正式产物；
- `build/`：可再生中间产物；
- `handoff/`：由 `scripts/export_handoff.py` 临时生成的普通 AI 交接包，默认被 `.gitignore` 忽略。

不要把某个个人 worktree 的临时 PDF 当成正式交付物，也不要把 `output/handoff/` 当作新的仓库真源。交接包只是在某一时刻对当前模块状态、只读参考和历史材料的可携带快照；AI 返回的修改仍必须落回模板规定的正式路径。
