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
    parser.add_argument("--replay-plan", help="任务根内固定回放计划；写入 qa/visual-replay.json")
    parser.add_argument("--execute-replay", action="store_true", help="按计划调用真实 generate；未指定时只重新核验")
    parser.add_argument("--library-root", type=Path, help="真实回放显式使用的库根")
    parser.add_argument("--freeze-baseline", help="任务根内旧链导出描述；只封存已有真实字节")
    args = parser.parse_args(argv)
    try:
        root = Path(args.run).expanduser().resolve()
        if args.freeze_baseline:
            if args.replay_plan or args.execute_replay:
                raise MetricEventError("baseline capture and replay are separate operations")
            from leo_ppt_generator.quality_replay import freeze_legacy_baseline
            from leo_ppt_generator.qualification import file_reference
            reference = freeze_legacy_baseline(root, file_reference(root, args.freeze_baseline), "qa/legacy-baseline.json")
            print(json.dumps({"baseline": reference}, ensure_ascii=False))
            return 0
        if args.replay_plan:
            from leo_ppt_generator.quality_replay import evaluate_quality_replay, attach_replay_receipt
            from leo_ppt_generator.qualification import file_reference
            from leo_ppt_generator.storage import atomic_write_json
            result = evaluate_quality_replay(root, file_reference(root, args.replay_plan),
                execute=args.execute_replay, library_root=args.library_root)
            target = root / "qa/visual-replay.json"
            if target.is_symlink() or target.parent.is_symlink():
                raise MetricEventError("replay output must not be a symlink")
            atomic_write_json(target, result)
            attach_replay_receipt(root, file_reference(root, "qa/visual-replay.json"))
            print(json.dumps(result, ensure_ascii=False, indent=2))
            return 0 if result["status"] == "passed" else 1
        if args.execute_replay or args.library_root:
            raise MetricEventError("replay-plan required")
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
