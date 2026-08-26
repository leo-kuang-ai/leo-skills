#!/usr/bin/env bash
set -euo pipefail

output=${EVAL_FINAL_MESSAGE:-}

if [[ -z "$output" ]]; then
  echo "最终输出为空" >&2
  exit 1
fi

question_count=$(printf '%s' "$output" | rg -o '[?？]' | wc -l | tr -d ' ')
if [[ "$question_count" -ne 1 ]]; then
  echo "期望恰好一个分叉问题，实际问号数：$question_count" >&2
  exit 1
fi

if [[ ${#output} -gt 300 ]]; then
  echo "响应超过 300 字符，疑似已进入正文或多问题问卷" >&2
  exit 1
fi

if [[ "$output" != *"判断"* ]]; then
  echo "问题未包含形成判断这一读者任务" >&2
  exit 1
fi

if [[ "$output" != *"操作"* && "$output" != *"理解"* && "$output" != *"完成"* ]]; then
  echo "问题没有提供可改变 workflow 的第二个读者任务" >&2
  exit 1
fi

if [[ "$output" == *"##"* || "$output" == *"编辑说明"* || "$output" == *"正文如下"* ]]; then
  echo "响应已进入文章正文结构" >&2
  exit 1
fi
