#!/usr/bin/env bash
# ci_gate.sh —— 评测分层 CI 入口（加固方案 WS7）。
#
# 用法：
#   bash scripts/ci_gate.sh                # L0 静态 + L1 单测（每次变更必过）
#   bash scripts/ci_gate.sh --with-field   # 追加 L2 现场抽样（合入前）
#
# 退出码：0 全过；1 任一层失败。L3（行为抽样）/L4（全量基线）不在本入口，
# 见 docs/plans/2026-09-07-002-leo-ppt-reliability-hardening-plan.md WS7。
set -uo pipefail
cd "$(dirname "$0")/.."

RUNTIME_PY="${LEO_PPT_RUNTIME_PY:-python3}"
FAIL=0
step() { printf '\n== %s ==\n' "$1"; }
run_check() {  # run_check <名称> <命令...>
  local name="$1"; shift
  step "$name"
  if "$@"; then echo "PASS: $name"; else echo "FAIL: $name"; FAIL=1; fi
}

# ---- L0 静态（零成本，秒级） ----
run_check "L0 lint_style_briefs"      "$RUNTIME_PY" scripts/lint_style_briefs.py
run_check "L0 lint_layout_grid"       "$RUNTIME_PY" scripts/lint_layout_grid.py
run_check "L0 lint_render_templates"  "$RUNTIME_PY" scripts/lint_render_templates.py
run_check "L0 lint_template_contract" "$RUNTIME_PY" scripts/lint_template_contract.py
run_check "L0 lint_skill_structure"   "$RUNTIME_PY" scripts/lint_skill_structure.py
run_check "L0 template-library registry" "$RUNTIME_PY" scripts/capability_manifest.py --template-library --library-check
run_check "L0 vendored lock"          "$RUNTIME_PY" scripts/sync_upstreams.py --check

# ---- L1 单测 ----
run_check "L1 pytest"                 "$RUNTIME_PY" -m pytest tests/ -q

# ---- L2 现场抽样（可选） ----
if [[ "${1:-}" == "--with-field" ]]; then
  run_check "L2 溢出哨兵回归"          "$RUNTIME_PY" -m pytest tests/render/test_overflow_sentinel.py -q
  run_check "L2 渠道参数面"            "$RUNTIME_PY" -m pytest tests/test_vendored_image_gen_params.py -q
  run_check "L2 渠道健康 L2（零成本）"  "$RUNTIME_PY" scripts/provider_health.py --level 2
fi

if [[ "$FAIL" -ne 0 ]]; then
  printf "\nCI GATE: FAIL\n"; exit 1
fi
printf "\nCI GATE: PASS\n"
