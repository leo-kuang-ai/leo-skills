#!/usr/bin/env bash
set -euo pipefail

output=${EVAL_FINAL_MESSAGE:-}

[[ "$output" == *"taste-skill"* ]] || { echo "缺少 taste-skill" >&2; exit 1; }
[[ "$output" == *"前端"* || "$output" == *"Frontend"* || "$output" == *"视觉"* ]] || { echo "未识别视觉工具边界" >&2; exit 1; }
[[ "$output" == *"HC3"* ]] || { echo "缺少 HC3" >&2; exit 1; }
[[ "$output" == *"许可证"* ]] || { echo "缺少许可证边界" >&2; exit 1; }
[[ "$output" == *"shuorenhua"* && "$output" == *"ai-flavor-remover"* ]] || { echo "缺少未审候选状态" >&2; exit 1; }
[[ "$output" == *"源码"* ]] || { echo "缺少源码证据" >&2; exit 1; }
[[ "$output" != *"taste-skill 是经过验证的文字审美工具"* ]] || { echo "错误升级 taste-skill" >&2; exit 1; }
[[ "$output" != *"HC3 可以直接判定作者身份"* ]] || { echo "错误升级 HC3" >&2; exit 1; }
