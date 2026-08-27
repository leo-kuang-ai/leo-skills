#!/usr/bin/env bash
# Serialize skill-up runs across sessions: refuse to start while another
# `skill-up run` process is alive (concurrent runs share the provider proxy
# quota and surface as spurious engine timeouts), and append a provenance
# line to the workspace run log so iteration directories can be attributed
# to their initiating session.
# Usage: bash evals/scripts/guarded-run.sh [skill-up run args...]
set -euo pipefail

skill_dir=$(cd "$(dirname "$0")/../.." && pwd)
workspace="${skill_dir}-workspace"

if pgrep -f 'skill-up run' >/dev/null 2>&1; then
  pgrep -fl 'skill-up run' >&2
  echo "另一个 skill-up run 仍在执行；为避免共享代理配额产生超时噪声，拒绝启动。" >&2
  exit 1
fi

mkdir -p "$workspace"
printf '%s\tppid=%s\targs=%s\n' "$(date -Iseconds)" "${PPID:-?}" "$*" \
  >> "$workspace/runs.log"

cd "$skill_dir"
exec skill-up run "$@"
