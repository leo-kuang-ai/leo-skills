#!/usr/bin/env bash
set -euo pipefail

output=${EVAL_FINAL_MESSAGE:-}
[[ "$output" == *"原句"* || "$output" == *"引用"* || "$output" == *"原文"* || "$output" == *"证据"* ]] || { echo "缺少原句/引用证据" >&2; exit 1; }
[[ "$output" == *"动作"* ]] || { echo "缺少可执行动作" >&2; exit 1; }
[[ "$output" == *"意义膨胀"* || "$output" == *"夸大"* || "$output" == *"宣传"* || "$output" == *"空泛"* || "$output" == *"套话"* || "$output" == *"无依据"* || "$output" == *"缺乏可验证依据"* || "$output" == *"无法被检验"* || "$output" == *"过度泛化"* || "$output" == *"绝对化"* || "$output" == *"模糊归因"* || "$output" == *"没有来源"* || "$output" == *"无来源"* || "$output" == *"无出处"* || "$output" == *"匿名权威"* || "$output" == *"虚假权威"* || "$output" == *"不可核验"* || "$output" == *"不可证伪"* ]] || {
  echo "未识别高影响事实或宣传问题" >&2
  exit 1
}
[[ "$output" != *"第一版改写"* && "$output" != *"第二版改写"* && "$output" != *"改写后："* ]] || {
  echo "audit 越权改写" >&2
  exit 1
}
