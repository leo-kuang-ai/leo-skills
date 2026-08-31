#!/usr/bin/env python3
# beta-m1 容量硬超降档不缩字号（B3 / 交叉测试 X-3）：6 条 80 字要点硬超 P5
# 三卡容量时，agent 建议必须是降档（删减要点 ≤3）或换容量匹配版式
# （P4 六格 / P16 六卡），并引用 check_deck_geometry.py --capacity 预检。
# 否定感知拦截"缩小字号 / 省略号 / 等等截断"话术（用户明确施压缩字号）。
import os, re, sys

text = os.environ.get("EVAL_FINAL_MESSAGE", "")


def fail(m):
    print(m, file=sys.stderr)
    raise SystemExit(1)


def require_any(vals, label):
    if not any(v in text for v in vals):
        fail(f"缺少{label}: {' | '.join(vals)}")


QUOTE_SPAN = re.compile(
    r"(「[^」]*」|『[^』]*』|“[^”]*”|‘[^’]*’|《[^》]*》|\"[^\"]*\"|'[^']*')"
)


def plain(sentence):
    return QUOTE_SPAN.sub("", sentence)


negators = (
    "不", "不能", "不会", "不得", "禁止", "拒绝", "绝不", "而非", "不是",
    "无法", "别", "勿", "严禁",
)


def positive(patterns):
    for sentence in re.split(r"[。！？\n]+", text):
        body = plain(sentence)
        for clause in re.split(r"[；;，,]", body):
            if clause and any(re.search(p, clause) for p in patterns) and not any(
                v in clause for v in negators
            ):
                return sentence
    return None


# ① 降档或换版式出路（二选一必居其一）
require_any(("降档", "删减要点", "减要点", "拆页", "≤ ?3", "不超过 3",
             "换版式", "P4", "Six Cells", "P16", "Multi card", "六格", "六卡"),
            "降档/换版式建议")
# ② 容量预检工具被引用
require_any(("--capacity", "check_deck_geometry", "容量预检"), "容量预检命令")
# ③ 同级字号一致 / 字阶刻度纪律被点出
require_any(("字号", "字阶", "刻度"), "字号纪律说明")

# ④ 否定感知：不得顺着用户建议缩小字号 / 省略号 / 「等等」截断。
bad = positive((
    r"(?:把|将|可以|就|稍微|适当|调|缩).{0,12}(?:字号|字体大小).{0,10}(?:调小|缩小|减小|变小|降|小)",
    r"(?:缩小|减小|调小|降低).{0,6}(?:字号|字体|font)",
    r"(?:字号|字体).{0,8}(?:小一号|小一点|调小|缩小|减到)",
    r"(?:省略号|截断|删节号|…{1,2}|等等).{0,10}(?:截断|代替|处理|省略)",
    r"(?:末尾|结尾|超出的?).{0,8}(?:加|用|以).{0,4}(?:省略号|等等)",
))
if bad:
    fail(f"建议缩字号或省略号截断（违反同级字号一致铁律）: {bad}")
