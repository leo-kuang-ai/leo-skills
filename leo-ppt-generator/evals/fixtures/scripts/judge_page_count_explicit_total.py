#!/usr/bin/env python3
# 明确总页数字面执行门 v2:用户明确说「总共 15 页,含封面和尾页」时,不触发口径询问,
# 直接按成品共 15 页执行并呈现结构拆解(封面 1 + 内容 13 + 尾页 1)。
# v2:拆解改三条独立断言(表格/冒号列表健康形态可命中)、去除"要不要"否定自豁免、
# 补"边拆解边砍页"类伪装违规的 forbid。

import os
import re
import sys

text = os.environ.get("EVAL_FINAL_MESSAGE", "")

NEG_TOKEN = re.compile(
    r"没有|不会|不能|不得|无法|禁止|拒绝|尚未|还没|还未|暂不|先不|不再|并非|而不是"
    r"|待确认|等待确认|需先|需经|未经|才能|前提"
    r"|(?<![要需这不])不(?![要需过得断少说到错好比可能用会必宜再仅限同久])"
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


# 成品共 15 页。
require_positive(
    [
        r"(共|合计|总计|成品|总共)[^。]{0,8}15(?![0-9])[^。]{0,4}页",
        r"15(?![0-9])[^。]{0,3}页[^。]{0,12}(含|包含)[^。]{0,6}(封面|结构)",
    ],
    "成品共 15 页",
)

# 结构拆解:封面 1 / 内容 13 / 尾页 1,三条独立断言(表格、冒号列表均视为命中)。
require_positive([r"封面\W{0,8}1(?![0-9])"], "拆解·封面 1")
require_positive([r"内容\W{0,8}13(?![0-9])"], "拆解·内容 13")
require_positive([r"(尾页|收尾页?|结束页)\W{0,8}1(?![0-9])"], "拆解·尾页 1")

# 明确措辞下不得再触发口径询问。
forbid_positive(
    [
        r"请(确认|说明)[^。]{0,16}(页数|口径|封面)",
        r"(是否|要不要|需不需要)[^。]{0,12}(含|包含|加|去|删)[^。]{0,8}(封面|尾页|收尾)",
        r"(页数|口径)[^。]{0,16}(是|为)[^。]{0,20}还是",
    ],
    "口径询问",
)

# 不得边呈现拆解边砍结构页(伪装合规)。
forbid_positive(
    [
        r"(去掉|删除|砍掉|省去|不做|省略)[^。]{0,8}(封面|尾页|收尾)",
        r"(尾页|收尾页?|结束页|封面)[^。]{0,8}(去掉|删除|砍掉|省去|放弃)",
    ],
    "砍掉结构页",
)

print("page-count-explicit-total: pass")
