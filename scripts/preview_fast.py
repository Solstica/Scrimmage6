#!/usr/bin/env python3
from __future__ import annotations

"""Fast paper-preview entry point.

Keeps the ownership audit from preview_merge.py, but only overlays files that can
matter to the compiled paper. Heavy solver archives/results/code/editable figure
sources are intentionally excluded from this temporary preview only.

Unlike the formal integration gate, fast preview also strips trailing spaces/tabs
from changed text files inside the temporary detached preview before committing.
This prevents purely cosmetic whitespace from blocking PDF inspection while never
modifying any responsibility branch.
"""

from pathlib import Path

import preview_merge as pm


_TEXT_SUFFIXES = {
    ".tex", ".sty", ".cls", ".md", ".py", ".sh", ".json", ".txt"
}


def preview_excluded(path: str | None) -> bool:
    if not path:
        return False
    p = path.replace("\\", "/")
    parts = p.split("/")

    # Historical/full computational archives are not paper inputs.
    if any("COMPLETE_ARCHIVE_" in part for part in parts):
        return True

    # Solver implementation and runtime artifacts are intentionally omitted from
    # the paper-only preview. The live paper/ and figures/ snapshots remain.
    if "/code/" in p or "/results/" in p or "/records/" in p:
        return True

    # Editable plotting sources are not needed once rendered figures exist.
    if "/figures/editable/" in p or p.lower().endswith(".opju"):
        return True

    # Console logs can contain CR/progress-control bytes and should never gate PDF preview.
    if p.lower().endswith((".log", ".log.err")):
        return True

    return False


def fast_overlay_branch(module: dict, audit_base_ref: str, preview: Path) -> None:
    branch_ref = f"origin/{module['branch']}"

    # Keep the full ownership audit: preview filtering must not hide cross-module edits.
    changes = pm.audit_ownership(module, audit_base_ref)
    kept = []
    for item in changes:
        _code, p1, p2 = item
        if preview_excluded(p1) or preview_excluded(p2):
            continue
        kept.append(item)

    head = pm.run(["git", "rev-parse", branch_ref], capture=True).stdout.strip()
    print(
        f"[FAST OVERLAY] {module['key']}: {module['branch']} @ {head[:12]} "
        f"({len(kept)}/{len(changes)} paper-relevant changes)"
    )

    for code, p1, p2 in kept:
        if code == "D":
            pm.run(["git", "rm", "-f", "--ignore-unmatch", "--", p1], cwd=preview, check=False)
        elif code == "R":
            pm.run(["git", "rm", "-f", "--ignore-unmatch", "--", p1], cwd=preview, check=False)
            pm.run(["git", "checkout", branch_ref, "--", p2], cwd=preview)
        elif code == "C":
            pm.run(["git", "checkout", branch_ref, "--", p2], cwd=preview)
        else:
            pm.run(["git", "checkout", branch_ref, "--", p1], cwd=preview)


def _strip_trailing_ws_bytes(data: bytes) -> bytes:
    """Strip only spaces/tabs immediately before EOL/EOF; preserve CRLF/LF."""
    chunks = data.splitlines(keepends=True)
    if not chunks:
        return data.rstrip(b" \t")

    out: list[bytes] = []
    for line in chunks:
        if line.endswith(b"\r\n"):
            body, ending = line[:-2], b"\r\n"
        elif line.endswith(b"\n"):
            body, ending = line[:-1], b"\n"
        elif line.endswith(b"\r"):
            body, ending = line[:-1], b"\r"
        else:
            body, ending = line, b""
        out.append(body.rstrip(b" \t") + ending)
    return b"".join(out)


def fast_compose_commit(preview: Path) -> None:
    """Compose a temporary commit after cosmetic whitespace cleanup.

    The cleanup applies only to text files changed in this detached preview. It
    never writes back to feature/* branches.
    """
    pm.run(["git", "add", "-A"], cwd=preview)

    changed = pm.run(
        ["git", "diff", "--cached", "--name-only", "-z", "HEAD"],
        cwd=preview,
        capture=True,
    ).stdout.split("\0")

    cleaned = 0
    for rel in changed:
        if not rel:
            continue
        path = preview / rel
        if not path.is_file() or path.suffix.lower() not in _TEXT_SUFFIXES:
            continue
        old = path.read_bytes()
        new = _strip_trailing_ws_bytes(old)
        if new != old:
            path.write_bytes(new)
            cleaned += 1

    if cleaned:
        print(f"[FAST CLEAN] 临时清理 {cleaned} 个文本文件的行尾空白")
        pm.run(["git", "add", "-A"], cwd=preview)

    if pm.run(["git", "diff", "--cached", "--quiet"], cwd=preview, check=False).returncode:
        pm.run([
            "git", "-c", "user.name=CUMCM Preview", "-c", "user.email=preview@local.invalid",
            "commit", "-m", "preview: compose owned module snapshots"
        ], cwd=preview)


def main() -> None:
    pm.overlay_branch = fast_overlay_branch
    pm.compose_commit = fast_compose_commit
    pm.main()


if __name__ == "__main__":
    main()
