#!/usr/bin/env bash
set -euo pipefail

output=${EVAL_FINAL_MESSAGE:-}
[[ "$output" == *"原句"* ]] || { echo "缺少原句证据" >&2; exit 1; }
[[ "$output" == *"动作"* ]] || { echo "缺少可执行动作" >&2; exit 1; }
[[ "$output" == *"意义膨胀"* || "$output" == *"夸大"* || "$output" == *"高强度判断"* || "$output" == *"宣传性"* || "$output" == *"空泛"* || "$output" == *"套话"* || "$output" == *"类目错配"* || "$output" == *"宏大表述"* || "$output" == *"空洞口号"* || "$output" == *"无依据"* || "$output" == *"绝对化断言"* || "$output" == *"抽象概念堆砌"* || "$output" == *"宣称性文案"* ]] || {
  echo "未识别意义膨胀或等价问题" >&2
  exit 1
}
[[ "$output" == *"模糊归因"* || "$output" == *"没有来源"* || "$output" == *"无来源"* || "$output" == *"无具名"* || "$output" == *"无出处"* || "$output" == *"匿名权威"* || "$output" == *"虚假权威"* || "$output" == *"weasel words"* || "$output" == *"专家没有来源"* || "$output" == *"不可证伪"* ]] || {
  echo "未识别模糊归因或等价问题" >&2
  exit 1
}
[[ "$output" != *"第一版改写"* && "$output" != *"第二版改写"* && "$output" != *"改写后："* ]] || {
  echo "audit 越权改写" >&2
  exit 1
}
