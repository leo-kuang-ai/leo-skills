#!/usr/bin/env python3
"""只读质量记分卡；显式输出仅允许 run/scorecard/quality-scorecard.json。"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import stat
import sys
import uuid

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "runtime" / "src"))
from leo_ppt_generator.quality_metrics import MetricEventError, scorecard_for_run, deck_quality_for_run


def write_scorecard(root, output, payload):
    expected = root / "scorecard" / "quality-scorecard.json"
    requested = Path(os.path.abspath(output))
    if (requested.name != expected.name or requested.parent.name != "scorecard"
            or requested.parent.parent.resolve() != root):
        raise MetricEventError("output must be run/scorecard/quality-scorecard.json")
    # 目录描述符固定写入边界，避免检查后目录被替换为符号链接。
    root_fd = os.open(root, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    directory_fd = None
    temporary = ".quality-scorecard-" + uuid.uuid4().hex
    try:
        try:
            os.mkdir("scorecard", dir_fd=root_fd)
        except FileExistsError:
            pass
        directory_fd = os.open("scorecard", os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW,
                               dir_fd=root_fd)
        try:
            target = os.stat(expected.name, dir_fd=directory_fd, follow_symlinks=False)
            if not stat.S_ISREG(target.st_mode):
                raise MetricEventError("output must not be a symlink or special file")
        except FileNotFoundError:
            pass
        fd = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600,
                     dir_fd=directory_fd)
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, expected.name, src_dir_fd=directory_fd, dst_dir_fd=directory_fd)
    finally:
        if directory_fd is not None:
            try:
                os.unlink(temporary, dir_fd=directory_fd)
            except FileNotFoundError:
                pass
            os.close(directory_fd)
        os.close(root_fd)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("run")
    parser.add_argument("--out", help="仅允许 run/scorecard/quality-scorecard.json")
    args = parser.parse_args(argv)
    try:
        root = Path(args.run).expanduser().resolve()
        result = scorecard_for_run(root)
        payload = json.dumps(result, ensure_ascii=False, sort_keys=True, indent=2) + "\n"
        if args.out:
            write_scorecard(root, args.out, payload)
        sys.stdout.write(payload)
        return 0
    except (OSError, ValueError) as exc:
        print(json.dumps({"status": "blocked", "reason_code": "quality_scorecard_invalid",
                          "detail": str(exc)}, ensure_ascii=False), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
