#!/usr/bin/env python3
"""核对样张门（SAMPLE-GATE）政策判据：内容链免逐步确认、逐页派发前默认呈样、
豁免只认用户显式原话、豁免不免样张生成与质检。"""
import json
import os
import sys

EXPECTED = {
    "content_chain_confirm": False,
    "sample_before_dispatch": True,
    "waiver_source": "user-explicit",
    "waiver_skips_qa": False,
}


def check(text):
    t = text.strip()
    # 容忍模型偶发加代码围栏（提示词已禁止，但措辞会轮换）
    if t.startswith("```") and t.count("```") >= 2:
        t = t.split("```")[1].strip()
        if t[:4].lower() == "json":
            t = t[4:].strip()
    try:
        result = json.loads(t)
    except (ValueError, TypeError):
        return ["输出不是单个合法JSON"]
    if not isinstance(result, dict):
        return ["输出不是对象"]
    return [key for key, value in EXPECTED.items()
            if type(result.get(key)) is not type(value) or result[key] != value]


if __name__ == "__main__":
    errors = check(os.environ.get("EVAL_FINAL_MESSAGE", ""))
    print(json.dumps({"passed": not errors, "errors": errors}, ensure_ascii=False))
    sys.exit(bool(errors))
