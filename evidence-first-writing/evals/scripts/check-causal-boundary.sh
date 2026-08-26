#!/usr/bin/env bash
set -euo pipefail

output=${EVAL_FINAL_MESSAGE:-}

[[ "$output" == *"相关"* || "$output" == *"关联"* || "$output" == *"观察性"* || "$output" == *"吻合"* ]] || { echo "未区分相关性" >&2; exit 1; }
[[ "$output" == *"因果"* ]] || { echo "未处理因果边界" >&2; exit 1; }
[[ "$output" == *"不能"* || "$output" == *"无法"* || "$output" == *"证据不足"* || "$output" == *"不成立"* ]] || {
  echo "未拒绝或收窄因果结论" >&2
  exit 1
}
[[ "$output" == *"对照组"* || "$output" == *"控制变量"* || "$output" == *"反事实"* ]] || {
  echo "未说明因果证据缺口" >&2
  exit 1
}
[[ "$output" != *"已经证明因果"* ]] || { echo "错误声称已证明因果" >&2; exit 1; }
