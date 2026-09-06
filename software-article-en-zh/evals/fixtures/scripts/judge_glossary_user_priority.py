#!/usr/bin/env python3
"""用户显式指定 lease 译作“租约”后：正文至少两处用“租约”，且“租期”只允许出现在带说明/否定语境的句子里。"""
import os
import re
import sys

text = os.environ.get("EVAL_FINAL_MESSAGE", "")
sentences = re.split(r"[。！？；;\n]+", text)

zu_yue_count = len(re.findall(r"租约", text))
if zu_yue_count < 2:
    print("'租约'仅出现 %d 次（要求 >=2），未按用户指定译名翻译 lease" % zu_yue_count, file=sys.stderr)
    sys.exit(1)

zu_qi_count = len(re.findall(r"租期", text))
bare = [s for s in sentences if "租期" in s and not re.search(r"不|未|而非|避免|译名|术语|说明|词", s)]
if bare:
    print("被排除的译名“租期”出现在无说明语境的译文中: %s" % bare[0].strip(), file=sys.stderr)
    sys.exit(1)
if zu_yue_count <= zu_qi_count:
    print("'租约'(%d) 次数未多于 '租期'(%d)，用户指定译名未生效" % (zu_yue_count, zu_qi_count), file=sys.stderr)
    sys.exit(1)

print("用户指定术语优先通过")
