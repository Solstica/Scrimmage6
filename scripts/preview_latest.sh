#!/usr/bin/env bash
set -Eeuo pipefail

# One-command latest paper preview for Git Bash on Windows.
# It never merges/rebases the caller's current branch.

ROOT="${SCRIMMAGE6_ROOT:-$HOME/Scrimmage6}"
CTRL="${SCRIMMAGE6_PREVIEW_CTRL:-$HOME/Scrimmage6-preview-controller}"
PREVIEW="${SCRIMMAGE6_PREVIEW_DIR:-$HOME/Scrimmage6-paper-preview}"

if [[ ! -d "$ROOT/.git" && ! -f "$ROOT/.git" ]]; then
  echo "[FAIL] 找不到稳定仓库：$ROOT"
  echo "可先设置 SCRIMMAGE6_ROOT 指向主仓库。"
  exit 2
fi

cleanup_ctrl() {
  cd "$ROOT" 2>/dev/null || true
  git worktree remove --force "$CTRL" >/dev/null 2>&1 || true
  rm -rf "$CTRL" >/dev/null 2>&1 || true
  git worktree prune --expire now >/dev/null 2>&1 || true
}
trap cleanup_ctrl EXIT

cd "$ROOT"

echo "[1/5] 更新远端引用"
git fetch origin --prune

# Remove any stale registrations from aborted previous previews.
echo "[2/5] 清理旧临时 worktree"
git worktree prune --expire now >/dev/null 2>&1 || true
git worktree remove --force "$CTRL" >/dev/null 2>&1 || true
git worktree remove --force "$PREVIEW" >/dev/null 2>&1 || true
rm -rf "$CTRL" "$PREVIEW"
git worktree prune --expire now >/dev/null 2>&1 || true

# Always run the newest shared integration code from the remote branch.
echo "[3/5] 建立最新版 preview controller"
git worktree add --force --detach "$CTRL" origin/feature/shared >/dev/null

cd "$CTRL"

echo "[4/5] 临时拼装各责任分支并编译"
python scripts/preview_fast.py \
  --preview-dir "$PREVIEW" \
  --base-branch feature/paper-shell \
  --strict \
  --no-open

echo "[5/5] 完成"
PDF="$PREVIEW/paper/main.pdf"
if [[ -f "$PDF" ]]; then
  echo "PDF: $PDF"
  if command -v explorer.exe >/dev/null 2>&1; then
    explorer.exe "$(cygpath -w "$PDF")" >/dev/null 2>&1 || true
  fi
else
  echo "[WARN] 未生成 main.pdf，请查看上方 LaTeX 第一处硬错误。"
fi
