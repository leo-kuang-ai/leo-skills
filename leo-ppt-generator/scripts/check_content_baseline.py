#!/usr/bin/env python3
"""check_content_baseline.py — 内容层基线哈希锁（R-36 CAS 写锁 + R-39 手改保护）。

对 content/ 工件（outline-v<N>.md / deck-master-v<N>.md / sources-manifest.json）
记录 sha256 基线到 sidecar（<FILE>.base-lock.json），写回前复核当前哈希与锁一致
（基线哈希 CAS）。上游依据：chinese-longnovel-skill scripts/项目事务.py 的
commit_head_cas（仅当当前 head 哈希等于 base 时才推进）与 WriteLock 的
base_head_sha256 复核；webnovel-writer write-resume 的 sha256 手改检测。

用法：
  check_content_baseline.py --record FILE    记录当前 sha256 到 sidecar
  check_content_baseline.py --verify FILE    复核当前 sha256 与锁是否一致

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
from datetime import datetime, timezone
from pathlib import Path

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
    tmp = lock.with_name(lock.name + ".tmp")
    tmp.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    # Atomic publish, mirroring upstream os.replace CAS style.
    os.replace(tmp, lock)
    return payload


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
    parser = argparse.ArgumentParser(description="内容层基线哈希锁（CAS verify + 手改保护）")
    parser.add_argument("--record", metavar="FILE", help="记录工件当前 sha256 到 sidecar")
    parser.add_argument("--verify", metavar="FILE", help="复核工件当前 sha256 与锁一致")
    args = parser.parse_args(argv)
    if bool(args.record) == bool(args.verify):
        parser.error("必须且只能指定 --record 或 --verify 之一")
    raw = args.record or args.verify
    target = Path(raw).expanduser().resolve()
    if not target.is_file():
        print(f"文件不存在: {target}", file=sys.stderr)
        return EXIT_USAGE
    if args.record:
        payload = write_lock(target)
        print(json.dumps({"status": "recorded", "lock": str(lock_path_for(target)), **payload},
                         ensure_ascii=False, indent=2))
        return EXIT_OK
    return verify(target)


if __name__ == "__main__":
    raise SystemExit(main())
