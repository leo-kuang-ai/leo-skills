#!/usr/bin/env python3
# 推荐合同：候选由合同信号驱动，默认推荐必须带归因一句，四行要素在场，
# 换法指路在场；无未否定的"已开始生成/跳过推荐"声明。
import os, re, sys
text = os.environ.get("EVAL_FINAL_MESSAGE", "")
def fail(m):
    print(m, file=sys.stderr); raise SystemExit(1)
def require_any(vals, label):
    if not any(v in text for v in vals): fail(f"缺少{label}: {' | '.join(vals)}")
NEG=("不","不能","不得","禁止","拒绝","尚未","还没","无法","待确认","没有","无")
def forbid_positive(pats,label):
    for sent in re.split(r"[。！？\n]+",text):
        body=re.sub(r"(「[^」]*」|\"[^\"]*\")","",sent)
        if any(re.search(p,body) for p in pats) and not any(v in body for v in NEG):
            fail(f"出现不应有的{label}: {sent[:50]}")
require_any(("候选","方向","推荐"), "候选/推荐在场")
require_any(("为什么","归因","因为","基于"), "默认归因句")
require_any(("长什么样","配色","风格","网格","主色"), "外观描述行")
require_any(("换","代价","重过样张","样张"), "换法/代价行")
require_any(("字母","点名","A/B","或","参考图"), "换法指路")
forbid_positive((r"已跳过推荐", r"已(开始)?生成", r"直接开始生成"), "跳过/生成声明")
