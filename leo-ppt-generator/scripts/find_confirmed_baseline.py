#!/usr/bin/env python3
"""find_confirmed_baseline.py — confirmed 基线链定位（R3 修复轮公共模块）。

Shared high→low walk over a versioned content series (`deck-master-v<N>.md`
by default; any ``name-v<N>.md`` series via a regex with the version in
group 1). Semantics follow execution-contract「内容层状态与恢复」: a
post-confirm write-back (`revision_kind: post-confirm`) inherits the
confirmed state of a lower root, while an explicitly pending version —
including a post-confirm revision sent back for re-confirmation after a
page/structure change — is a chain break: unconfirmed content never
becomes baseline truth.

Single implementation shared by reproject_derivatives.find_confirmed_master
and expire_candidates.find_baseline (incl. the outline series), preventing
dual-drift between the two scripts.
"""
from __future__ import annotations

import re
from pathlib import Path

MASTER_RE = re.compile(r"^deck-master-v(\d+)\.md$")
CONFIRM_RE = re.compile(r"^confirmation:\s*confirmed", re.M)
PENDING_RE = re.compile(r"^confirmation:\s*pending", re.M)
POST_CONFIRM_RE = re.compile(r"^revision_kind:\s*post-confirm", re.M)


def find_confirmed_baseline(content_dir: Path,
                            name_re: re.Pattern = MASTER_RE,
                            ) -> tuple[Path, list[str]] | None:
    """Highest confirmed baseline incl. post-confirm chain: (top, chain).

    Walk versions high→low:
    - explicitly pending (with or without post-confirm): chain break — a
      post-confirm rollback awaiting re-confirmation is not baseline truth,
      fall back to the lower confirmed root;
    - post-confirm without an explicit pending flag: chain member inheriting
      a lower confirmed root;
    - confirmed: the chain root (closes the chain, returns its top);
    - no confirmation marker at all: chain break, keep walking downward.

    ``chain`` is ordered high→low and includes the root; it is empty when
    the top is a confirmed root with no post-confirm members above. Returns
    None when no confirmed root exists in the series.
    """
    versions: list[tuple[int, Path]] = []
    for path in content_dir.glob("*.md"):
        m = name_re.match(path.name)
        if m:
            versions.append((int(m.group(1)), path))
    versions.sort(key=lambda item: item[0], reverse=True)

    chain_top: Path | None = None
    chain: list[str] = []
    for _, path in versions:
        try:
            text = path.read_text(encoding="utf-8")
        except OSError:
            continue  # unreadable version: never baseline truth
        is_pending = bool(PENDING_RE.search(text))
        is_post = bool(POST_CONFIRM_RE.search(text))
        is_confirmed = bool(CONFIRM_RE.search(text))
        if is_pending:
            # Rollback awaiting re-confirmation: chain broken, keep walking.
            chain_top, chain = None, []
            continue
        if is_post and not is_confirmed:
            # post-confirm write-back inherits from a lower confirmed root.
            if chain_top is None:
                chain_top = path
            if path.name not in chain:
                chain.append(path.name)
            continue
        if is_confirmed:
            if chain_top is None:
                return path, []
            chain.append(path.name)
            return chain_top, chain
        # No marker at all: chain broken, keep walking downward.
        chain_top, chain = None, []
    return None
