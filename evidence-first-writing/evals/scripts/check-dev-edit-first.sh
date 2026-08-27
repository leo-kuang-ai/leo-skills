#!/usr/bin/env bash
set -euo pipefail

output=${EVAL_FINAL_MESSAGE:-}

# First byte offset among the given fixed strings; empty when none present.
first_index() {
  local best="" term idx
  for term in "$@"; do
    idx=$(grep -Fbo -- "$term" <<<"$output" 2>/dev/null | head -n1 | cut -d: -f1 || true)
    idx=${idx:-}
    [[ -z "$idx" ]] && continue
    if [[ -z "$best" || "$idx" -lt "$best" ]]; then best=$idx; fi
  done
  printf '%s' "$best"
}

dev_idx=$(first_index "论点" "主线" "thesis" "中心句" "论断" "结构" "可换序" "顺序" "warrant" "论证" "证据")
style_idx=$(first_index "标点" "句长" "禁词" "错别字" "副词" "被动句" "措辞" "用词")

[[ -n "$dev_idx" ]] || { echo "缺少发展编辑层 finding（论点/结构/论证）" >&2; exit 1; }

if [[ -n "$style_idx" && "$style_idx" -lt "$dev_idx" ]]; then
  echo "句子润色先于发展编辑" >&2
  exit 1
fi

[[ "$output" == *"可换序"* || "$output" == *"交换"* || "$output" == *"顺序"* || "$output" == *"平行"* || "$output" == *"互换"* || "$output" == *"换序"* || "$output" == *"并列"* || "$output" == *"零贡献"* || "$output" == *"文章不变"* || "$output" == *"删掉任何"* || "$output" == *"换一批"* || "$output" == *"推进"* || "$output" == *"罗列"* || "$output" == *"通用真理"* || "$output" == *"通用断言"* || "$output" == *"常识"* ]] || {
  echo "未做段落顺序/结构测试" >&2
  exit 1
}

[[ "$output" == *"warrant"* || "$output" == *"论据"* || "$output" == *"证据"* || "$output" == *"为什么"* ]] || {
  echo "未说明证据与结论的连接" >&2
  exit 1
}
