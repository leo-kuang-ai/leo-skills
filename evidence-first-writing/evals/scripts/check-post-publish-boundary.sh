#!/usr/bin/env bash
set -euo pipefail

output=${EVAL_FINAL_MESSAGE:-}

[[ "$output" == *"observation"* || "$output" == *"观察"* ]] || { echo "缺少 observation" >&2; exit 1; }
[[ "$output" == *"hypothesis"* || "$output" == *"假设"* ]] || { echo "缺少 hypothesis" >&2; exit 1; }
[[ "$output" == *"曝光量"* || "$output" == *"曝光"* ]] || { echo "未披露曝光量缺口" >&2; exit 1; }
open_rate_re='(打开率|open-rate)[^。]{0,20}(无法|不能|不可|未验证|推不出|算不出|not_available)|(无法|不能|不可|推不出|算不出|缺)[^。]{0,12}(打开率|open-rate)|open-rate status|打开率状态|not_available'
[[ "$output" =~ $open_rate_re ]] || { echo "未处理打开率状态" >&2; exit 1; }
[[ "$output" == *"stable_rule_update"* || "$output" == *"稳定规则"* ]] || { echo "缺少稳定规则决策" >&2; exit 1; }
[[ "$output" == *"persistence"* || "$output" == *"不写入"* || "$output" == *"不写档"* ]] || { echo "缺少持久化状态" >&2; exit 1; }
[[ "$output" != *"已证明该句式有效"* && "$output" != *"因此我们确定"* && "$output" != *"标题公式有效"* && "$output" != *"该公式有效"* && "$output" != *"证明了因果"* && "$output" != *"已被验证"* && "$output" != *"已被证明"* && "$output" != *"已验证"* && "$output" != *"确定有效"* ]] || { echo "错误升级为因果规则" >&2; exit 1; }
