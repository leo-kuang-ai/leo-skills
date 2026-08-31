#!/usr/bin/env python3
# 学术五拍（B6）advise 侧判据：模式名在场；**不凭印象编造五拍序列**（列举五拍
# 必须伴随权威源/核实语义）；权威源可指认（06_论证模式 轴文档 / style render
# --list-templates / 进入 execute 读取）；注入机制正确（母版结论句标题按论证
# 模式条件化 / style render --mode）；答辩实质纪律（Numbers, not adjectives）。
import os, re, sys

text = os.environ.get("EVAL_FINAL_MESSAGE", "")

QUOTE_SPAN = re.compile(r"(「[^」]*」|『[^』]*』|“[^”]*”|\"[^\"]*\"|`[^`]*`)")


def fail(m):
    print(m, file=sys.stderr)
    raise SystemExit(1)


def require_any(vals, label):
    if not any(v in text for v in vals):
        fail(f"缺少{label}: {' | '.join(vals)}")


# ① 模式名在场（题目已给出，正确转述即可）
require_any(("学术五拍",), "学术五拍模式名")

# ② 权威源/核实指认：06_论证模式 轴文档、style render --list-templates、
#    或"进入 execute 后读取"的诚实延迟。
SOURCE = ("06_论证模式", "论证模式轴", "style-library", "风格库", "--list-templates",
          "list-templates", "进入 execute", "execute 后", "读取", "核实", "reference",
          "不凭印象", "不能现场", "无法现场")
require_any(SOURCE, "权威源/核实指认")

# ③ 注入机制：论证模式经 style render --mode 注入 + 母版结论句标题条件化。
require_any(("style render", "--mode", "论证模式", "骨架注入", "标题.{0,8}条件化",
             "结论句标题"), "注入机制")

# ④ 答辩实质纪律：Numbers, not adjectives / 断言式标题 / 具体数字。
require_any(("数字", "Numbers", "具体量", "断言式", "断言标题", "空话", "形容词"),
            "实质纪律")

# ⑤ 反编造陷阱：列举"五拍"完整序列却无权威源/核实语义伴随——advise 模式
#    读不到 06_论证模式 文件，凭模式名现场编五拍属编造。
BEATS = ("背景", "问题", "方法", "证据|实验", "结论|贡献")
sentences = [QUOTE_SPAN.sub("", s) for s in re.split(r"[。！？\n]+", text)]
for s in sentences:
    hits = sum(1 for b in BEATS if re.search(b, s))
    if hits >= 4 and not any(src in s for src in SOURCE):
        fail(f"疑似凭印象编造五拍序列（无权威源/核实语义伴随）: {s.strip()[:80]}")

print("beta-m6-academic-five: ok")
