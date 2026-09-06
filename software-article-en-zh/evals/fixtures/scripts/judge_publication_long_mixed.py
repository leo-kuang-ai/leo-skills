#!/usr/bin/env python3
"""发布型长文结构保护：围栏数、标识符、链接目标、图片路径、脚注、单位原样；
保护检查报告（类型 数量/数量）在场；术语首现“中文译名（英文原文）”且同篇一致（不混用反压）；
硬段内容词覆盖。"""
import os
import re
import sys

text = os.environ.get("EVAL_FINAL_MESSAGE", "")

fences = len(re.findall(r"(?m)^\s*```", text))
if fences != 6:
    print("围栏标记行数为 %d，应为 6（3 个代码块 × 开闭）" % fences, file=sys.stderr)
    sys.exit(1)

# 受保护标识符与链接/图片/脚注原样在场
for token in (
    "ingestctl",
    "--dry-run",
    "grpc_retry_limit",
    "shard_count",
    "queue_buffer",
    "flush_interval_ms",
    "https://example.com/docs/ingest",
    "assets/architecture-overview.png",
    "[^1]",
):
    if token not in text:
        print("受保护内容缺失: %s" % token, file=sys.stderr)
        sys.exit(1)

# 单位与数值保真
for token in ("ms", "GiB", "180", "812"):
    if token not in text:
        print("数值/单位锚点缺失: %s" % token, file=sys.stderr)
        sys.exit(1)

# 保护检查报告：类型 数量/数量 最小格式
if not re.search(r"\d+\s*/\s*\d+", text):
    print("缺少保护检查报告（类型 数量/数量 格式，如 围栏 3/3）", file=sys.stderr)
    sys.exit(1)

# 术语首现形态：背压（backpressure）
if not re.search(r"背压\s*[（(]\s*backpressure\s*[)）]", text):
    print("术语首现缺少“中文译名（英文原文）”形态：背压（backpressure）", file=sys.stderr)
    sys.exit(1)

# 同篇术语一致：不混用“反压”
if "反压" in text:
    print("同篇术语不一致：混用“反压”与“背压”", file=sys.stderr)
    sys.exit(1)

# 硬段覆盖（测量限定与脚注警示不得丢）
for a in ("分片", "队列", "延迟", "异步"):
    if a not in text:
        print("硬段内容词缺失: %s（疑漏译）" % a, file=sys.stderr)
        sys.exit(1)
if not re.search(r"仅|只|单一|一个", text):
    print("测量限定（one workload only）疑似丢失", file=sys.stderr)
    sys.exit(1)

print("发布型长文结构保护通过")
