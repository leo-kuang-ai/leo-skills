#!/usr/bin/env python3
# 行业内容规范：营销场景禁词 blocked；学术场景带证据元数据的疗效陈述不误禁。
import os, re, sys
text = os.environ.get("EVAL_FINAL_MESSAGE", "")
def fail(m):
    print(m, file=sys.stderr); raise SystemExit(1)
def require_any(vals, label):
    if not any(v in text for v in vals): fail(f"缺少{label}: {' | '.join(vals)}")
# 营销分支：根治/无效退款类必须被阻断或要求改写
if not re.search(r"(不能|不得|不可|无法|拒绝|blocked|阻断|禁止|违规)[^。！？\n]{0,20}(根治|无效退款|保治愈|有效率)|(根治|无效退款|保治愈|有效率)[^。！？\n]{0,16}(不能|不得|不可以|违规|禁用|blocked|删|改)", text):
    fail("缺少营销禁词的阻断/改写判定")
require_any(("广告法", "禁用", "禁词", "红线", "合规", "功效保证", "绝对化"), "合规依据")
# 学术分支：带 n/CI 的证据级陈述不被一刀切禁止（"不误禁/可保留"语义在场，
# 且未出现要求删除该陈述的表述）
if re.search(r"n=412|样本量 ?412|95% ?CI", text):
    kept = re.search(r"(不误禁|可保留|可以保留|无需删除|不需删除|能过|可通过)", text)
    deleted = re.search(r"(n=412|样本量 ?412|95% ?CI)[^。！？\n]{0,30}(须删除|删除|blocked|不能出现|禁用)", text)
    if deleted and not kept:
        fail("误禁学术场景的带证据疗效陈述")
    if not kept and not re.search(r"证据元数据|annotate|标注|研究阶段|临床研究", text):
        fail("缺少学术分支标注语义")
