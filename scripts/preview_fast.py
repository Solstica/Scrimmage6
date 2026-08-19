#!/usr/bin/env python3
from __future__ import annotations

"""Fast paper-preview entry point.

Keeps the ownership audit from preview_merge.py, but only overlays files that can
matter to the compiled paper. Heavy solver archives/results/code/editable figure
sources are intentionally excluded from this temporary preview only.
"""

from pathlib import Path

import preview_merge as pm


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


def main() -> None:
    pm.overlay_branch = fast_overlay_branch
    pm.main()


if __name__ == "__main__":
    main()
