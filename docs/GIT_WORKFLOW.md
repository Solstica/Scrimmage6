# Git / Worktree 协作流程

## 分支按责任域，不按人

每个论文章节、每个问题、共享代码和论文壳均为独立分支。这样摘要、问题重述、评价等可以和 Q1/Q2/Q3 同样独立更新，不互相覆盖。

## 推荐工作区

```text
project-main/               main 或管理工作区
project-worktrees/
├─ abstract/
├─ restatement/
├─ q1/
├─ q2/
├─ q3/
├─ q4/
├─ evaluation/
└─ ...
```

用 `python scripts/bootstrap_worktrees.py --push` 自动创建。

## 开始/结束

```bash
git fetch origin --prune
git pull --ff-only
python scripts/workflow.py start q2
# ...工作...
python scripts/workflow.py finish q2
git diff
git add <files>
git commit -m "feat(q2): ..."
git push
```

## 冲突

- 普通章节分支原则上只修改自己路径，因此不应频繁冲突。
- 发现冲突时先停止，查看 `git status` 与具体文件所有权。
- 二进制 Origin/Excel 文件不做并行 merge；同一文件同一时刻指定一个编辑者。
- 不以 force push/reset-hard 作为常规协作手段。

## 全文测试

`python scripts/preview_merge.py` 只在 detached 临时 worktree 中合并所有正式模块。测试成功不等于已经合并 main；稳定版本再通过 PR/明确集成进入 main。
