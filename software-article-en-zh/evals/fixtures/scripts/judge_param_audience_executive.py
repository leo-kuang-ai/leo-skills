#!/usr/bin/env python3
"""管理层受众适配：blast radius 术语保留并给出影响面解释（爆炸半径/影响范围），
cell 译为单元并说明独立故障含义，p99 指标原样，error budget 未消耗不被夸大为零故障。"""
import os
import re
import sys

text = os.environ.get("EVAL_FINAL_MESSAGE", "")

if len(re.findall(r"[\u4e00-\u9fff]", text)) < 20:
    print("缺少中文译文", file=sys.stderr)
    sys.exit(1)

# 术语在场且给出影响面解释（管理层受众适配）
if not re.search(r"爆炸半径|blast radius|影响范围|影响面|波及范围", text):
    print("缺少 blast radius 术语或影响面解释", file=sys.stderr)
    sys.exit(1)

# cell → 单元，独立故障语义保留
if not re.search(r"单元|细胞单元|cell", text):
    print("缺少 cell 的译名锚点（单元）", file=sys.stderr)
    sys.exit(1)
if not re.search(r"独立|相互独立|各自|单独", text):
    print("缺少单元独立故障语义", file=sys.stderr)
    sys.exit(1)
if not re.search(r"租户|用户|客户", text):
    print("缺少 tenants 内容词", file=sys.stderr)
    sys.exit(1)

# 指标标识原样：p99
if "p99" not in text:
    print("指标标识 p99 缺失（应原样保留）", file=sys.stderr)
    sys.exit(1)

# error budget 语义：未被消耗，不得夸大为零故障/无错误（句级否定感知 + 译法说明句豁免）
if not re.search(r"错误预算|error budget|误差预算", text):
    print("缺少 error budget 术语锚点", file=sys.stderr)
    sys.exit(1)
for s in re.split(r"[。！？；;\n]+", text):
    if re.search(r"译为|译作|→|术语|说明|保留", s):
        continue
    if re.search(r"零故障|零错误|没有任何错误|完全无错", s) and not re.search(
        r"不|未|并非|而非|并不是|没有|避免|拒绝", s
    ):
        print("错误预算未消耗被夸大为零故障: %s" % s.strip(), file=sys.stderr)
        sys.exit(1)

# latency stayed flat：保持平稳，不得译成大幅改善
if not re.search(r"平稳|保持不变|没有(明显)?(变化|波动|上升)|持平", text):
    print("缺少 stayed flat 的语义锚点（平稳/持平）", file=sys.stderr)
    sys.exit(1)

print("管理层受众适配通过")
