#!/usr/bin/env python3
"""monitor 一词多义：fleet 语境须译“监控”类动词，桌面硬件语境须译“显示器/屏幕”，不得两处同词全局替换。"""
import os
import re
import sys

text = os.environ.get("EVAL_FINAL_MESSAGE", "")

if not re.search(r"监控|监测|监视", text):
    print("动词 monitor（monitor the fleet）未按语境译作“监控/监测/监视”", file=sys.stderr)
    sys.exit(1)

if not re.search(r"显示器|屏幕|显示屏", text):
    print("名词 monitor（the monitor on your desk）未译作“显示器/屏幕”，疑做全局同词替换", file=sys.stderr)
    sys.exit(1)

print("同词多义按上下文处理通过")
