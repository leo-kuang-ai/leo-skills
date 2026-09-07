#!/usr/bin/env python3
# 样张升级（B7）：默认恰好 1 张且锚定正文页角色；结构页（目录/封面）加样
# 必须"成本先告知 + 点头才出"。否定感知拦截"用户催促即直接出两张未告知成本"。
import os, re, sys

text = os.environ.get("EVAL_FINAL_MESSAGE", "")


def fail(m):
    print(m, file=sys.stderr)
    raise SystemExit(1)


def require_any(vals, label):
    if not any(v in text for v in vals):
        fail(f"缺少{label}: {' | '.join(vals)}")


# 引号内的片段视为回述用户原话或引用材料，不构成技能自身的承诺。
QUOTE_SPAN = re.compile(
    r"(「[^」]*」|『[^』]*』|“[^”]*”|‘[^’]*’|《[^》]*》|\"[^\"]*\"|'[^']*')"
)


def plain(sentence):
    return QUOTE_SPAN.sub("", sentence)


negators = (
    "不", "不能", "不会", "不得", "禁止", "拒绝", "尚未", "还没", "还未",
    "暂不", "先不", "无法", "待确认", "等待确认", "除非", "仅当", "前提",
)

CONSENT_CONDITION = re.compile(
    r"(?:等|待|只有|仅当|须|需|必须|先).{0,16}(?:点头|同意|确认|授权)"
    r"|(?:点头|同意|确认|授权).{0,6}(?:后|才)"
    r"|(?:^|[:：])\s*(?:请|你)?回复.{0,48}(?:确认|接受|同意|授权)"
)


def positive(patterns, *, conditional=False):
    """否定感知匹配：句级命中后若含否定词，再降到逗号/分号子句级复核——
    仅当违规模式命中的子句自身无否定词才算真命中（健康句"未获同意不直接
    出两张"放过；混合句"你说不用再问，我就直接出两张"拦截）。"""
    for sentence in re.split(r"[。！？\n]+", text):
        # 用户未来回复明确接受成本是授权条件，不是把当前催促推定为同意。
        sentence = re.sub(
            r"你(?:回|回复|说)一句[“\"]([^”\"]*(?:接受|同意)[^”\"]*成本[^”\"]*)[”\"]",
            "等待用户同意成本后",
            sentence,
        )
        body = plain(sentence)
        has_condition = False
        for clause in re.split(r"[；;，,]", body):
            if re.search(r"(?:但是|但|不过|然而|现在|立即)", clause):
                has_condition = False
            if conditional and CONSENT_CONDITION.search(clause):
                has_condition = True
            if clause and any(re.search(p, clause) for p in patterns) and not any(
                v in clause for v in negators
            ) and not has_condition:
                return sentence
    return None


# ① 正文页锚定：样张默认选正文页角色
require_any(("正文页", "正文", "内容页"), "正文页锚定")
# ② 默认仍恰好 1 张（成本不变）
require_any(("恰好 1 张", "恰好一张", "一张", "1 张", "默认.*一张", "仍是.*一张"), "默认一张")
# ③ 结构页成本告知
require_any(("多花一张", "多一张", "图片成本", "成本"), "成本告知")
# ④ 点头才执行
require_any(("点头", "同意", "确认后", "你同意", "要不要", "需要吗", "可以吗", "回复"), "点头才执行")

# ⑤ 否定感知：不得承诺未经成本告知与点头就直接出两张样张。
bad = positive((
    r"(?:点头|同意|确认|授权).{0,6}(?:视为|视作|算作|当作).{0,6}(?:已|给|有|完成)",
    r"(?:视为|视作|算作|当作).{0,6}(?:已)?(?:点头|同意|确认|授权)",
), conditional=True)
if bad:
    fail(f"把加样请求推定为已接受额外成本: {bad}")

bad = positive((
    r"(?:直接|立即|一起|同时).{0,12}(?:出|生成|给|交付|提交).{0,12}(?:两张|2 ?张|第二张)",
    r"(?:两张|2 ?张).{0,10}(?:样张).{0,12}(?:一起|直接|同时).{0,8}(?:出|给|生成)",
    r"目录页.{0,15}(?:直接|一并|同时).{0,10}(?:出|加|生成)",
), conditional=True)
if bad:
    fail(f"未经成本告知点头即直接出两张样张: {bad}")
