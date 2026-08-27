#!/usr/bin/env bash
set -euo pipefail

output=${EVAL_FINAL_MESSAGE:-}

[[ "$output" == *"formal-report"* ]] || { echo "未路由 formal-report" >&2; exit 1; }
[[ "$output" == *"风险"* ]] || { echo "缺少风险" >&2; exit 1; }
[[ "$output" == *"验收"* ]] || { echo "缺少验收" >&2; exit 1; }
[[ "$output" == *"owner"* || "$output" == *"责任人"* ]] || { echo "缺少责任人" >&2; exit 1; }
[[ "$output" == *"期限"* || "$output" == *"上线窗口"* || "$output" == *"决策节点"* || "$output" == *"周期"* ]] || { echo "缺少时间约束" >&2; exit 1; }
[[ "$output" == *"三个方案"* || "$output" == *"三方案"* || "$output" == *"方案 A"* ]] || { echo "缺少方案比较" >&2; exit 1; }
[[ "$output" != *"先做去 AI 味"* && "$output" != *"爆款"* ]] || { echo "正式报告路由污染" >&2; exit 1; }
