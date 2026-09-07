#!/usr/bin/env python3
"""发布型复合保真：先剥离五件套元信息区，正文必须保留 MUST(必须)/SHOULD(应当)/MAY(可以) 与
only when(只有…才) 条件；相关性表述不得句级改成因果；弱化语气不得被润色成确定性承诺。"""
import os
import re
import sys

text = os.environ.get("EVAL_FINAL_MESSAGE", "")

# 剥离元信息区：首个说明类标题（含五件套节名）之后的内容不参与正文检查
m = re.search(
    r"(?m)^(?:#{1,3}\s*)?[-*•]?\s*\**\s*(?:交付说明|交付信息|逐句对照说明|审校状态|技术复核|编辑复核|翻译说明|译注|说明|覆盖范围|保护检查|未解决项|未解决事项|术语表|歧义与原文问题|歧义清单|原文问题|需作者确认)\s*[:：]?\**.*$",
    text,
)
body = text[: m.start()] if m else text

# 规范情态保真：MUST/SHOULD/MAY 的中文映射在场（应 排除 应对/应答/应变/应用 复合词）
for anchor, label in ((r"必须", "MUST"), (r"应当|应(?![对答变用])", "SHOULD"), (r"可以", "MAY 许可")):
    if not re.search(anchor, body):
        print("正文缺少规范情态锚点 %s（%s）" % (anchor, label), file=sys.stderr)
        sys.exit(1)

# only when 条件：只有/仅在/仅当 形态在场（“仅在…时启用”“只有…才”均合法）
if not re.search(r"只有|仅当|仅在", body):
    print("正文缺少 only when 的条件锚点（只有/仅在/仅当）", file=sys.stderr)
    sys.exit(1)

# 相关性不得改因果：提及队列与导致/造成/引起的句子必须带否定或对比语境
for s in re.split(r"[。！？；;\n]+", body):
    if re.search(r"队列", s) and re.search(r"导致|造成|引起", s) and not re.search(
        r"不|未|并非|并不是|没有|而非|并不|不能|无法|看不出|说明不了", s
    ):
        print("相关性表述被句级改成因果: %s" % s.strip(), file=sys.stderr)
        sys.exit(1)

# 润色不得引入确定性承诺（句级否定感知）
for s in re.split(r"[。！？；;\n]+", body):
    if re.search(r"一定|保证|确保|务必|万无一失", s) and not re.search(r"不|未|无|并非|并不是|没有|而非|原文", s):
        print("编辑润色引入确定性承诺: %s" % s.strip(), file=sys.stderr)
        sys.exit(1)

# 正文内容词在场（防回显/防空洞）
for a in ("拒绝", "令牌", "退避"):
    if a not in body:
        print("正文缺少内容词 %s（疑未翻译或剥离过界）" % a, file=sys.stderr)
        sys.exit(1)

print("发布型复合保真通过")
