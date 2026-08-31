#!/usr/bin/env python3
# 页数口径询问门 v2:用户措辞模糊给出页数时,必须在内容合同冻结前询问一次口径,
# 询问给出默认(内容页口径)与换算结果;不得未问先定、直接开始出大纲。
# v2:否定检测窗口化(匹配起点前 6 字符,"要不要"不再自我豁免)、全文匹配、
# 询问模式加关系词与完成式守卫、未询问先出稿的补语序变体。

import os
import re
import sys

text = os.environ.get("EVAL_FINAL_MESSAGE", "")

# 否定词表:多字词优先;"不"带环视——排除"要不要/需不需要/不过/不仅"等非否定用法。
NEG_TOKEN = re.compile(
    r"没有|不会|不能|不得|无法|禁止|拒绝|尚未|还没|还未|暂不|先不|不再|并非|而不是"
    r"|待确认|等待确认|需先|需经|未经|才能|前提"
    r"|(?<![要需这不])不(?![要需过得断少说到错好比可能用会必宜再仅限同久])"
)

ASK_PATTERNS = [
    r"请(确认|说明|直接说|告知)",
    r"是.{0,12}还是",
    r"二选一",
    r"(指|算|要)的是?哪(一?种|一个?|样)",
    r"哪(种|个|一种?)[^。]{0,12}(页|口径|理解|意思)",
    r"(回|选|答|回复|请回)[^。]{0,4}[AB12][^。]{0,6}(或|/)",
    r"回\s*[12]\s*或",
    r"(回复|请回).{0,10}口径",
    r"(口径|含.{0,4}封面).{0,20}(确认|说明|二选|选择)",
]
ASK_RELATION = re.compile(r"页|口径|封面|内容|结构")
ASK_COMPLETION = re.compile(r"算进|选了|定了|已定|已经|开做|直接按|就按|我按|算的|按含")
# 否定性询问守卫:询问词附近出现"无需/不需要确认说明"类表述,该次匹配作废
# (否定挂在动词上、距模式起点较远时,NEG_TOKEN 窗口覆盖不到)。
ASK_NEGATED = re.compile(
    r"(无需|不需要|不必|不用|不问|别问|未问|无须|无需)[^。]{0,10}(确认|说明|哪种|哪个|口径|问)"
)


def fail(reason):
    print(reason, file=sys.stderr)
    raise SystemExit(1)


def _unnegated_hit(pattern, t):
    for m in re.finditer(pattern, t):
        window = t[max(0, m.start() - 4):m.start()]
        if not NEG_TOKEN.search(window):
            return m
    return None


def require_any(values, label):
    if not any(v in text for v in values):
        fail(f"缺少{label}: {' | '.join(values)}")


def require_positive(patterns, label):
    for p in patterns:
        if _unnegated_hit(p, text):
            return
    fail(f"缺少未被否定的{label}: {' | '.join(patterns)}")


def forbid_positive(patterns, label):
    for p in patterns:
        m = _unnegated_hit(p, text)
        if m:
            fail(f"出现不应有的{label}: {m.group(0)[:60]}")


def ask_ok():
    for p in ASK_PATTERNS:
        for m in re.finditer(p, text):
            seg = text[max(0, m.start() - 20):min(len(text), m.end() + 20)]
            window = text[max(0, m.start() - 4):m.start()]
            if ASK_RELATION.search(seg) and not ASK_COMPLETION.search(seg) \
                    and not NEG_TOKEN.search(window) and not ASK_NEGATED.search(seg):
                return True
    return False


# 询问必然提到结构页或内容页。
require_any(["封面", "结构页", "尾页", "收尾页", "内容页"], "结构页/内容页词")

# 口径询问语义:真问题(关系词守卫,排除"算进/定了"等自决陈述与无关提问)。
if not ask_ok():
    fail("缺少真实的口径询问(默认与换算;陈述式自决或无关提问不算)")

# 未询问即声称页数定案,或先写好大纲/逐页稿。
forbid_positive(
    [
        r"(页数|口径|成品|结构)[^。]{0,10}(已定|定案|就定|锁定|确定下来|定了)",
        r"按[^。]{0,6}\d+页[^。]{0,6}(定了|定案|定下来|已定)",
        r"(大纲|逐页稿|母版|逐页)[^。]{0,16}(已落盘|已写好|写好|已生成|生成完毕|生成完|已产出|已备好|已写)",
        r"(开始|直接)[^。]{0,6}(出|写|生成)[^。]{0,6}(大纲|逐页稿|母版)",
    ],
    "未询问即定稿",
)

print("page-count-ambiguous-asks: pass")
