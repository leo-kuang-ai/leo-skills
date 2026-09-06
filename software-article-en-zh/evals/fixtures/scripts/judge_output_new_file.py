#!/usr/bin/env python3
"""写新文件不动源文件：新文件真实创建且含保护内容，源文件保持英文原文，输出含处置披露。
文件事实优先从磁盘核对新文件；无法定位新文件时回退解析 transcript 中的 Write 调用目标。"""
import json
import os
import re
import sys

text = os.environ.get("EVAL_FINAL_MESSAGE", "")


def find_in_transcript(name):
    tp = os.environ.get("EVAL_TRANSCRIPT_PATH", "")
    if not tp or not os.path.isfile(tp):
        return None
    try:
        raw = open(tp, encoding="utf-8", errors="replace").read()
    except OSError:
        return None
    hits = set(re.findall(r'(/[^\s"\',:]*/' + re.escape(name) + r')', raw))
    hits = {h.rstrip("\\") for h in hits}
    for h in sorted(hits, key=len):
        if h.endswith(name) and os.path.isfile(h):
            return h
    return None


# ① 新文件事实核对
new_path = None
for cand_dir in (os.getcwd(), os.path.join(os.getcwd(), "with_skill")):
    cand = os.path.join(cand_dir, "deploy-guide.zh.md")
    if os.path.isfile(cand):
        new_path = cand
        break
if new_path is None:
    new_path = find_in_transcript("deploy-guide.zh.md")
if new_path is None:
    print("未创建新文件 deploy-guide.zh.md（磁盘与 transcript 均无证据）", file=sys.stderr)
    sys.exit(1)

content = open(new_path, encoding="utf-8", errors="replace").read()
if len(re.findall(r"[\u4e00-\u9fff]", content)) < 20:
    print("新文件中文内容不足，疑未翻译", file=sys.stderr)
    sys.exit(1)
for protected in ("/etc/gateway/upstreams.yaml", "gatewayctl reload", "30"):
    if protected not in content:
        print("新文件缺少保护内容: %s" % protected, file=sys.stderr)
        sys.exit(1)

# ② 源文件未被改动（保持英文原文）
src_path = os.path.join(os.path.dirname(new_path), "deploy-guide.md")
if not os.path.isfile(src_path):
    src_path = find_in_transcript("deploy-guide.md") or "deploy-guide.md"
try:
    src = open(src_path, encoding="utf-8", errors="replace").read()
except OSError:
    src = ""
for must in ("revalidates", "upstreams.yaml", "gatewayctl reload"):
    if must not in src:
        print("源文件被改动或缺失（未见 %s）" % must, file=sys.stderr)
        sys.exit(1)
if re.search(r"网关|读取|配置文件", src):
    print("源文件被就地中文化", file=sys.stderr)
    sys.exit(1)

# ③ 处置披露
if not re.search(
    r"新文件|已保存|另存|存为|保存为|未改动|未做.{0,6}改动|没有.{0,8}(改动|修改)|不修改原文件|不改动原文件|保留原文件|原文件[^。\n]{0,12}(不变|未动|未改|保持)|(保存|存|写入|输出)在?[^。\n]{0,30}deploy-guide\.zh\.md",
    text,
):
    print("缺少处置披露（新文件/未改动原文件）", file=sys.stderr)
    sys.exit(1)

print("写新文件且不动源文件通过")
