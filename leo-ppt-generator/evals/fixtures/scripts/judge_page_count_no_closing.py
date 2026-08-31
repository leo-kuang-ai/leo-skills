#!/usr/bin/env python3
# 去尾页执行门 v2:用户要求「15 页内容、不要尾页」时,立即按成品 16 页(封面 1 +
# 内容 15)规划且不二次确认删除,并声明末页承担收束职能(回扣 one_thing)。
# v2:兜底"16页"加环视(排除"第16页"类引用)、保留尾页补倒装、二次确认补
# 无"确认"字样与"承诺再确认"变体。

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


# 成品共 16 页(排除"第16页"类页内引用冒充)。
require_positive(
    [
        r"(共|合计|总计|成品|总共)[^。]{0,8}16(?![0-9])[^。]{0,4}页",
        r"(?<![0-9第其中约])16\W{0,2}页",
        r"封面\W{0,8}1(?![0-9])[^。]{0,16}内容\W{0,8}15(?![0-9])",
    ],
    "成品共 16 页",
)

# 末页收束职能(回扣 one_thing),叙事闭环不豁免。
require_positive(
    [
        r"(末页|最后一页|收尾职能|收束职能)[^。]{0,24}(收束|收尾|回扣|承担)",
        r"(收束|收尾)(职能|作用)[^。]{0,16}(末页|最后一页|并入)",
        r"(末页|最后一页)[^。]{0,8}(兼任|承担|负责)[^。]{0,8}(收束|收尾)",
        r"回扣.{0,8}one_thing",
    ],
    "末页收束职能",
)

# 不得声明保留尾页(含倒装)。
forbid_positive(
    [
        r"(保留|加上|添加|补上|加回|补回|恢复|留下)[^。]{0,10}(尾页|收尾页|结束页)",
        r"(尾页|收尾页|结束页)[^。]{0,8}(保留|加回|补回|恢复|留下)",
    ],
    "保留尾页",
)

# 不得二次确认删除(含无"确认"字样的再询问与"回头再确认"承诺)。
forbid_positive(
    [
        r"(再次|需要|请)[^。]{0,6}确认[^。]{0,10}(?<!增)删",
        r"(?<!增)删(除|掉)?[^。]{0,10}(再次|需要|请)[^。]{0,6}确认",
        r"确认[^。]{0,10}(是否|要不要)[^。]{0,10}(尾页|收尾|删除)",
        r"(要不要|需要|是否)[^。]{0,8}(补|加|恢复|留)[^。]{0,6}(一?页|尾页|收尾)",
        r"(删除尾页|这事|此事)[^。]{0,12}(再|回头|稍后|之后)[^。]{0,6}确认",
    ],
    "删除二次确认",
)

print("page-count-no-closing: pass")
