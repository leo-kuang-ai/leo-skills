#!/usr/bin/env bash
set -euo pipefail

output=${EVAL_FINAL_MESSAGE:-}

[[ "$output" == *"deep"* ]] || { echo "未选择 deep" >&2; exit 1; }
[[ "$output" == *"证据账本"* || "$output" == *"evidence-ledger"* || "$output" == *"evidence ledger"* ]] || { echo "缺少证据账本" >&2; exit 1; }
[[ "$output" == *"事实回归"* || "$output" == *"factual_regression"* ]] || { echo "缺少事实回归" >&2; exit 1; }
[[ "$output" == *"分层审查"* || "$output" == *"分层编辑"* || "$output" == *"development_edit"* ]] || { echo "缺少分层编辑" >&2; exit 1; }
[[ "$output" != *"AI 分数达标即可发布"* ]] || { echo "错误使用 AI 分数放行" >&2; exit 1; }
