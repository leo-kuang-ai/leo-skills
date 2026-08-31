#!/usr/bin/env bash
# post-publish 判官本地包装入口。2026-08-31 修复轮（scr-20260831-164237）起
# eval case YAML 的 judge.script_path 直接指向 postpublish_judge.py——skill-up
# 引擎按单文件上传契约执行判官（仅上传 script_path 指向的单个文件），本包装
# 不再作为引擎入口，仅供本地与单测调用。
# 双分支结构化解析（canonical fenced YAML 块逐字段枚举校验 / 自然语言同义词
# 判定）由 postpublish_judge.py 承载，本入口仅透传 EVAL_FINAL_MESSAGE（未设置
# 时由 python 侧读 stdin）。退出码：0 接受，1 拒绝。
set -euo pipefail

script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
exec python3 "$script_dir/postpublish_judge.py"
