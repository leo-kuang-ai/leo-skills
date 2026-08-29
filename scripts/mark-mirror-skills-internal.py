#!/usr/bin/env python3
"""mark-mirror-skills-internal.py — 给 spec-first 宿主镜像 SKILL.md 注入 metadata.internal 标记。

背景：仓库镜像树（.agents/.claude/.codex/.kiro）是 skills CLI 的标准容器目录，
裸 `npx skills add leo-kuang-ai/leo-skills` 会把镜像技能与产品技能一并列出。
`metadata.internal: true` 使镜像技能从默认发现隐藏（`INSTALL_INTERNAL_SKILLS=1`
可显式安装）；产品技能位于仓库顶层不在镜像树内，天然不受影响。

注意：`spec-first update` 会重生成镜像并抹掉标记——重生成后须重跑本脚本
（约定记录于仓库根 AGENTS.md）。

用法：python3 scripts/mark-mirror-skills-internal.py
退出码：0 全部成功（含已标记跳过）；1 存在无法处理的文件（逐个列名）。
"""

import re
import sys
from pathlib import Path

MIRROR_TREES = (".agents", ".claude", ".codex", ".kiro")

FRONTMATTER_RE = re.compile(r"^---\n(.*?)\n---\n", re.S)


def mark_text(text: str) -> tuple[str, str]:
    """返回 (新文本, 状态)；状态为 marked / already / no-frontmatter / malformed。"""
    match = FRONTMATTER_RE.match(text)
    if match is None:
        return text, "no-frontmatter" if text.startswith("---") else "malformed"
    fm = match.group(1)
    if re.search(r"^  internal:\s*true\s*$", fm, re.M):
        return text, "already"
    if re.search(r"^  internal:", fm, re.M):
        fm = re.sub(r"^  internal:.*$", "  internal: true", fm, count=1, flags=re.M)
    elif re.search(r"^metadata:\s*$", fm, re.M):
        fm = re.sub(r"^metadata:\s*$", "metadata:\n  internal: true", fm, count=1, flags=re.M)
    else:
        fm += "\nmetadata:\n  internal: true"
    return "---\n" + fm + "\n---\n" + text[match.end():], "marked"


def main() -> int:
    repo_root = Path(__file__).resolve().parent.parent
    counts = {"marked": 0, "already": 0}
    failures: list[str] = []
    for tree in MIRROR_TREES:
        base = repo_root / tree
        if not base.is_dir():
            continue
        for skill_md in sorted(base.rglob("SKILL.md")):
            original = skill_md.read_text(encoding="utf-8")
            updated, status = mark_text(original)
            if status in ("marked", "already"):
                if status == "marked":
                    skill_md.write_text(updated, encoding="utf-8")
                counts[status] += 1
            else:
                failures.append(f"{skill_md.relative_to(repo_root)}: {status}")
    print(f"marked={counts['marked']} already-marked={counts['already']} failed={len(failures)}")
    for line in failures:
        print(f"FAIL {line}", file=sys.stderr)
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
