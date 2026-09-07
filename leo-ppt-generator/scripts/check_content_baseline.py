#!/usr/bin/env python3
"""check_content_baseline.py — 内容层基线哈希锁（R-36 CAS 写锁 + R-39 手改保护）。

对 content/ 工件（outline-v<N>.md / deck-master-v<N>.md / sources-manifest.json）
记录 sha256 基线到 sidecar（<FILE>.base-lock.json），写回前复核当前哈希与锁一致
（基线哈希 CAS）。上游依据：chinese-longnovel-skill scripts/项目事务.py 的
commit_head_cas（仅当当前 head 哈希等于 base 时才推进）与 WriteLock 的
base_head_sha256 复核；webnovel-writer write-resume 的 sha256 手改检测。

用法：
  check_content_baseline.py --record FILE    记录当前 sha256 到 sidecar
    check_content_baseline.py --verify FILE    只读核对，不构成并发写入许可
    check_content_baseline.py --commit FILE --candidate NEW --expected-sha256 HASH
        在共享写锁内比较旧版本并发布候选；新基线发布失败时后续检查拒绝继续。

所有协作写入必须走 --commit；外部编辑器不遵守此锁，不能宣称可阻止任意外部写入。
使用当前 runtime Python，复用包中已有 filelock 依赖。

退出码：0 一致/记录成功；3 基线漂移（检测到手改或并发写，给出有限选项，
       不自动覆盖）；4 用法错误（锁缺失 / 文件缺失 / sidecar 损坏）。
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

from filelock import FileLock, Timeout

SCHEMA_VERSION = 1
LOCK_SUFFIX = ".base-lock.json"
EXIT_OK = 0
EXIT_DRIFT = 3
EXIT_USAGE = 4

DRIFT_OPTIONS = """基线漂移检测：{file}
  锁记录 sha256 : {locked}
  当前 sha256   : {current}
该文件在锁记录后被修改（会话外手改或并发会话写回）。本脚本不自动覆盖。

有限选项（三选一，须人工/主 Agent 裁决）：
  1) 采纳为新版本：确认当前改动有效后，重新运行 --record 以当前内容重锁。
  2) 丢弃改动：恢复到锁记录版本需人工处理（本锁只存哈希，不存内容备份）。
  3) 只查看：对比两侧哈希与记录时间后停止，不做任何写动作。"""


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1 << 16), b""):
            digest.update(chunk)
    return digest.hexdigest()


def lock_path_for(target: Path) -> Path:
    return target.with_name(target.name + LOCK_SUFFIX)


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def write_lock(target: Path) -> dict:
    payload = {
        "schema_version": SCHEMA_VERSION,
        "file": target.name,
        "sha256": sha256_file(target),
        "size": target.stat().st_size,
        "recorded_at": now_iso(),
    }
    lock = lock_path_for(target)
    atomic_replace(lock, (json.dumps(payload, ensure_ascii=False, indent=2) + "\n").encode("utf-8"))
    return payload


def atomic_replace(target: Path, content: bytes) -> None:
    """在同目录发布；中断后的旧基线会拒绝未完成的提交。"""
    fd, name = tempfile.mkstemp(prefix=f".{target.name}.", dir=target.parent)
    temporary = Path(name)
    try:
        with os.fdopen(fd, "wb") as stream:
            if target.exists():
                os.chmod(temporary, target.stat().st_mode & 0o777)
            stream.write(content)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, target)
    finally:
        temporary.unlink(missing_ok=True)


def commit(target: Path, candidate: Path, expected: str) -> int:
    """调用者持有共用写锁；比较显式版本后发布候选和新基线。"""
    lock = read_lock(target)
    if lock is None:
        print(json.dumps({"status": "no_lock", "file": str(target)}, ensure_ascii=False))
        return EXIT_USAGE
    current = sha256_file(target)
    if current != expected or lock["sha256"] != expected:
        print(json.dumps({"status": "baseline_drift", "file": str(target),
                          "expected_sha256": expected, "current_sha256": current,
                          "message": "版本已变化，未写入候选；核对差异后再决定。"}, ensure_ascii=False))
        return EXIT_DRIFT
    content = candidate.read_bytes()
    atomic_replace(target, content)
    payload = write_lock(target)
    print(json.dumps({"status": "committed", "previous_sha256": expected, **payload}, ensure_ascii=False))
    return EXIT_OK


def read_lock(target: Path) -> dict | None:
    lock = lock_path_for(target)
    if not lock.is_file():
        return None
    try:
        payload = json.loads(lock.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    if not isinstance(payload, dict) or not re.fullmatch(r"[0-9a-f]{64}", str(payload.get("sha256", ""))):
        return None
    return payload


def verify(target: Path) -> int:
    lock = read_lock(target)
    if lock is None:
        print(json.dumps({
            "status": "no_lock",
            "file": str(target),
            "message": "基线锁缺失或损坏：先运行 --record 建立基线，再进入写回路径。",
        }, ensure_ascii=False, indent=2))
        return EXIT_USAGE
    if not target.is_file():
        print(json.dumps({
            "status": "file_missing",
            "file": str(target),
            "locked_sha256": lock["sha256"],
            "recorded_at": lock.get("recorded_at"),
            "message": "工件在锁记录后消失（人工移动/删除），写回前必须先裁决。",
        }, ensure_ascii=False, indent=2))
        return EXIT_USAGE
    current = sha256_file(target)
    if current == lock["sha256"]:
        print(json.dumps({
            "status": "ok",
            "file": str(target),
            "sha256": current,
            "recorded_at": lock.get("recorded_at"),
        }, ensure_ascii=False, indent=2))
        return EXIT_OK
    print(DRIFT_OPTIONS.format(
        file=str(target), locked=lock["sha256"], current=current))
    print(json.dumps({
        "status": "baseline_drift",
        "file": str(target),
        "locked_sha256": lock["sha256"],
        "current_sha256": current,
        "recorded_at": lock.get("recorded_at"),
        "hint": "post-confirm 写回前必须 --verify 通过；并发会话场景后者停止并报告。",
    }, ensure_ascii=False, indent=2))
    return EXIT_DRIFT


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="内容基线核对与受锁保护的版本提交")
    parser.add_argument("--record", metavar="FILE", help="记录工件当前 sha256 到 sidecar")
    parser.add_argument("--verify", metavar="FILE", help="复核工件当前 sha256 与锁一致")
    parser.add_argument("--commit", metavar="FILE", help="核对显式版本并原子替换目标")
    parser.add_argument("--candidate", type=Path, help="已完成编辑的独立候选文件")
    parser.add_argument("--expected-sha256", help="编辑前记录的目标版本，不能在冲突后自动刷新")
    args = parser.parse_args(argv)
    if sum(bool(value) for value in (args.record, args.verify, args.commit)) != 1:
        parser.error("必须且只能指定 --record、--verify 或 --commit 之一")
    if args.commit:
        if not args.candidate or not re.fullmatch(r"[0-9a-f]{64}", args.expected_sha256 or ""):
            parser.error("--commit 需要 --candidate 与有效 --expected-sha256")
    elif args.candidate or args.expected_sha256:
        parser.error("--candidate / --expected-sha256 仅用于 --commit")
    raw = args.record or args.verify or args.commit
    target = Path(raw).expanduser().resolve()
    if not target.is_file():
        print(f"文件不存在: {target}", file=sys.stderr)
        return EXIT_USAGE
    candidate = args.candidate.expanduser().resolve() if args.candidate else None
    if candidate and (not candidate.is_file() or candidate in {target, lock_path_for(target)}):
        parser.error("候选必须为独立的可读文件，不能覆盖目标或基线")
    try:
        with FileLock(str(target) + ".write.lock", timeout=10):
            if args.commit:
                return commit(target, candidate, args.expected_sha256)
            if args.record:
                payload = write_lock(target)
                print(json.dumps({"status": "recorded", "lock": str(lock_path_for(target)), **payload},
                                 ensure_ascii=False, indent=2))
                return EXIT_OK
            return verify(target)
    except Timeout:
        print(json.dumps({"status": "writer_busy", "message": "其他写入尚未完成，目标未修改。"}, ensure_ascii=False))
        return EXIT_DRIFT
    except OSError as exc:
        print(json.dumps({"status": "write_failed", "message": str(exc)}, ensure_ascii=False))
        return EXIT_USAGE


if __name__ == "__main__":
    raise SystemExit(main())
