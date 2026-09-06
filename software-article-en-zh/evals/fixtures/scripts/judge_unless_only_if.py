#!/usr/bin/env python3
"""only if 译出“只有/仅当…才”类必要条件（句内不得出现“只要…就”充分条件式），unless 译出“除非”。"""
import os
import re
import sys

text = os.environ.get("EVAL_FINAL_MESSAGE", "")
sentences = re.split(r"[。！？；;\n]+", text)

only_if_hits = [s for s in sentences if re.search(r"enable_replication", s)]
if not only_if_hits:
    print("未找到 enable_replication 标识符（未译或标识符被改写）", file=sys.stderr)
    sys.exit(1)

# ① only if → 只有…才 / 仅当…时（必要条件标记）
if not any(re.search(r"只有|仅当|唯有|仅在", s) for s in only_if_hits):
    print("only if 未译出“只有/仅当…才”类必要条件标记", file=sys.stderr)
    sys.exit(1)

# ③ 必要条件句内不得改成“只要…就”充分条件式
for s in only_if_hits:
    if re.search(r"只要.{0,32}就", s):
        print("必要条件被译成“只要…就”充分条件: %s" % s.strip(), file=sys.stderr)
        sys.exit(1)

# ② unless → 除非
unless_hits = [s for s in sentences if re.search(r"watchdog|看门狗|守护进程|守护程序|监控进程", s)]
if not unless_hits:
    print("未找到 watchdog 相关译句（内容缺失或未译）", file=sys.stderr)
    sys.exit(1)
if not any(re.search(r"除非", s) for s in unless_hits):
    print("unless 未译出“除非”: %s" % unless_hits[0].strip(), file=sys.stderr)
    sys.exit(1)

print("条件关系翻译通过")
