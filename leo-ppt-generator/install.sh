#!/usr/bin/env bash
# install.sh — 从本地源安装 leo-ppt-generator Skill。
#
# 本脚本只支持本地安装：默认从脚本所在目录拷贝 Skill 内容到目标位置。
# 远端下载与版本拉取逻辑已被移除；版本管理以 git / 包管理器为准。

set -euo pipefail

SKILL_NAME="leo-ppt-generator"

usage() {
  cat <<'EOF'
安装 Leo PPT Generator Skill（仅本地模式）。

用法：
  bash install.sh [选项]

选项：
  --agents                 安装到 ~/.agents/skills，而不是 Codex 用户目录
  --source <目录>          从本地 Skill 目录安装（默认：本脚本所在目录）
  --target <目录>          指定完整安装目录（高级用法）
  --bin-dir <目录>         安装稳定 leo-ppt 命令，默认 ~/.local/bin
  --upgrade                验证新版本后替换现有 Skill，并保留旧版本备份
  --host <name>            目标宿主：codex | agents | claude（默认 codex）
  --uninstall [--purge-data]
                           移除命令链接与技能目录；--purge-data 连同数据目录
                           一并清除。钥匙串条目永不自动删除。
  -h, --help               显示帮助

默认目标：${CODEX_HOME:-$HOME/.codex}/skills/leo-ppt-generator
EOF
}

fail() {
  printf '安装失败：%s\n' "$*" >&2
  exit 1
}

# 内部维护动词（不出现在 usage 契约面）：供 install.ps1 等调用方复用同一
# 剪裁实现；失败永不阻断调用方的成功路径。
run_internal_prune() {
  local backups_root="$1"
  local script_dir
  script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd -P)"
  local manager="$script_dir/scripts/runtime_manager.py"
  [[ -f "$manager" ]] || return 0
  local prune_json prune_line
  # 备份剪裁（保留最近 3）
  prune_json="$(python3 "$manager" prune-backups \
    --root "$backups_root" --keep-newest 3 2>/dev/null)" || return 0
  [[ -n "$prune_json" ]] || return 0
  prune_line="$(python3 - "$prune_json" <<'PY'
import json, sys

data = json.loads(sys.argv[1])
if data.get("aborted_reason"):
    print(f"警告：备份保留清理整批跳过（{data['aborted_reason']}）；未删除任何内容。")
elif data.get("removed_count"):
    count = data["removed_count"]
    freed = data["total_bytes_freed"]
    mb = freed / (1024 * 1024)
    unit = f"{mb:.1f} MB" if mb >= 0.1 else f"{freed} B"
    print(f"保留清理：已删除 {count} 项历史备份，释放 {unit}")
PY
)" || return 0
  [[ -n "$prune_line" ]] && printf '%s\n' "$prune_line"
  # 受管 runtime 剪裁（除 current 外保留最近 2）
  local rt_json rt_line
  rt_json="$(python3 "$manager" prune-runtimes --keep-newest 2 2>/dev/null)" || return 0
  [[ -n "$rt_json" ]] || return 0
  rt_line="$(python3 - "$rt_json" <<'PY'
import json, sys

data = json.loads(sys.argv[1])
if data.get("aborted_reason"):
    print(f"警告：runtime 保留清理整批跳过（{data['aborted_reason']}）；未删除任何内容。")
elif data.get("removed_count"):
    count = data["removed_count"]
    freed = data["total_bytes_freed"]
    mb = freed / (1024 * 1024)
    unit = f"{mb:.1f} MB" if mb >= 0.1 else f"{freed} B"
    print(f"保留清理：已删除 {count} 个旧受管 runtime，释放 {unit}")
PY
)" || return 0
  [[ -n "$rt_line" ]] && printf '%s\n' "$rt_line"
}

if [[ "${1:-}" == "--internal-prune-skill-backups" ]]; then
  shift
  [[ $# -ge 1 ]] || fail "--internal-prune-skill-backups 缺少备份根目录"
  run_internal_prune "$1"
  exit 0
fi

if [[ "${1:-}" == "--internal-run-onboard" ]]; then
  shift
  [[ $# -ge 1 ]] || fail "--internal-run-onboard 缺少安装目录"
  script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd -P)"
  manager="$script_dir/scripts/runtime_manager.py"
  [[ -f "$manager" ]] || { printf '{"status":"blocked","reason_code":"config_check_unavailable"}\n'; exit 0; }
  python3 "$manager" onboard --route generate 2>/dev/null || \
    printf '{"status":"blocked","reason_code":"config_check_unavailable"}\n'
  exit 0
fi

# 单一事实来源：冲突检查与默认目标解析（正常流程与内部测试动词共用）。
resolve_install_scope() {
  : "${target:=}" "${host_kind:=}" "${agents_mode:=0}"
  if [[ -n "$target" && "$agents_mode" == "1" ]]; then
    fail "--agents 与 --target 不能同时使用"
  fi
  if [[ -n "$target" && -n "$host_kind" ]]; then
    fail "--host 与 --target 不能同时使用"
  fi
  if [[ -n "$host_kind" && "$agents_mode" == "1" && "$host_kind" != "agents" ]]; then
    fail "--agents 与 --host $host_kind 冲突"
  fi
  if [[ -z "$target" ]]; then
    if [[ -n "$host_kind" ]]; then
      case "$host_kind" in
        codex) target="${CODEX_HOME:-$HOME/.codex}/skills/$SKILL_NAME" ;;
        agents) target="$HOME/.agents/skills/$SKILL_NAME" ;;
        claude) target="${CLAUDE_CONFIG_DIR:-$HOME/.claude}/skills/$SKILL_NAME" ;;
      esac
    elif [[ "$agents_mode" == "1" ]]; then
      target="$HOME/.agents/skills/$SKILL_NAME"
    else
      target="${CODEX_HOME:-$HOME/.codex}/skills/$SKILL_NAME"
    fi
  fi
  [[ "$(basename "$target")" == "$SKILL_NAME" ]] || \
    fail "安装目录末级名称必须是 $SKILL_NAME"
}

# R17：--uninstall 默认只拆程序面；--purge-data 显式清数据；钥匙串永不自动触碰。
if [[ "${1:-}" == "--uninstall" ]]; then
  shift
  purge_data=0
  uninstall_bin_dir=""
  while (($# > 0)); do
    case "$1" in
      --purge-data) purge_data=1; shift ;;
      --bin-dir)
        (($# >= 2)) || fail "--bin-dir 缺少值"
        uninstall_bin_dir="$2"
        shift 2
        ;;
      *) fail "未知选项：$1" ;;
    esac
  done
  script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd -P)"
  bin_dir="${uninstall_bin_dir:-${LEO_PPT_BIN_DIR:-$HOME/.local/bin}}"
  launcher="$bin_dir/leo-ppt"
  if [[ -L "$launcher" ]]; then
    rm -f "$launcher"
    printf '已移除命令：%s\n' "$launcher"
  elif [[ -e "$launcher" ]]; then
    printf '跳过：%s 存在但不属于本安装（非符号链接）。\n' "$launcher"
  fi
  if [[ -d "$script_dir" && -f "$script_dir/SKILL.md" ]] && \
    [[ "$(basename "$(dirname "$script_dir")")" == "skills" ]]; then
    rm -rf "$script_dir"
    printf '已移除技能目录：%s\n' "$script_dir"
  else
    printf '跳过：当前目录形态不像已安装位置（父目录须为 skills）；未做删除。\n'
  fi
  data_home="${LEO_PPT_HOME:-$HOME/Library/Application Support/leo-ppt-generator}"
  if [[ "$purge_data" == "1" && -d "$data_home" ]]; then
    rm -rf "$data_home"
    printf '已清除数据目录：%s\n' "$data_home"
  else
    printf '数据目录已保留：%s\n' "$data_home"
  fi
  printf '钥匙串条目（服务名 leo-ppt-generator/*）不会被自动删除；如需清理，请在「钥匙串访问」中确认后手动删除。\n'
  exit 0
fi

if [[ "${1:-}" == "--internal-print-target" ]]; then
  shift
  while (($# > 0)); do
    case "$1" in
      --host)
        (($# >= 2)) || fail "--host 缺少值"
        case "$2" in codex|agents|claude) host_kind="$2" ;; *) fail "未知宿主：$2" ;; esac
        shift 2
        ;;
      --agents) agents_mode=1; shift ;;
      *) fail "未知选项：$1" ;;
    esac
  done
  resolve_install_scope
  printf 'parent=%s\nname=%s\n' "$(dirname "$target")" "$(basename "$target")"
  exit 0
fi

host_kind=""
target=""
agents_mode=0
upgrade=0
source_dir=""
target=""
bin_dir="${LEO_PPT_BIN_DIR:-}"

while (($# > 0)); do
  case "$1" in
    --agents)
      agents_mode=1
      shift
      ;;
    --source)
      (($# >= 2)) || fail "--source 缺少值"
      source_dir="$2"
      shift 2
      ;;
    --target)
      (($# >= 2)) || fail "--target 缺少值"
      target="$2"
      shift 2
      ;;
    --bin-dir)
      (($# >= 2)) || fail "--bin-dir 缺少值"
      bin_dir="$2"
      shift 2
      ;;
    --upgrade)
      upgrade=1
      shift
      ;;
    --host)
      (($# >= 2)) || fail "--host 缺少值"
      case "$2" in
        codex|agents|claude) host_kind="$2" ;;
        *) fail "未知宿主：$2；--host 仅支持 codex|agents|claude" ;;
      esac
      shift 2
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      fail "未知选项：$1"
      ;;
  esac
done

resolve_install_scope

platform="$(uname -s)"
architecture="$(uname -m)"
if [[ "$platform" != "Darwin" || ( "$architecture" != "arm64" && "$architecture" != "x86_64" ) ]]; then
  fail "当前版本仅支持 macOS arm64/x86_64 或 Windows x64；检测到 ${platform}/${architecture}"
fi
printf 'install[platform_check]: macOS %s 已确认\n' "$architecture"

# 默认 source_dir 为本脚本所在目录（Skill 自带 installer）
if [[ -z "$source_dir" ]]; then
  script_self="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd -P)"
  if [[ -f "$script_self/SKILL.md" ]]; then
    source_dir="$script_self"
  else
    fail "未指定 --source，且本脚本所在目录缺少 SKILL.md：$script_self"
  fi
fi
[[ -d "$source_dir" ]] || fail "本地来源目录不存在：$source_dir"
source_dir="$(cd "$source_dir" && pwd -P)"

target_parent="$(dirname "$target")"
mkdir -p "$target_parent"
target_parent="$(cd "$target_parent" && pwd -P)"
target="$target_parent/$SKILL_NAME"

codex_root="${CODEX_HOME:-$HOME/.codex}/skills"
agents_root="$HOME/.agents/skills"
claude_root="${CLAUDE_CONFIG_DIR:-$HOME/.claude}/skills"
discovery_roots=("$codex_root" "$agents_root" "$claude_root")
if [[ -n "${LEO_PPT_EXTRA_DISCOVERY_ROOTS:-}" ]]; then
  IFS=':' read -r -a extra_roots <<< "$LEO_PPT_EXTRA_DISCOVERY_ROOTS"
  for extra_root in "${extra_roots[@]}"; do
    [[ -n "$extra_root" ]] || continue
    discovery_roots+=("$extra_root")
  done
fi
for discovery_root in "${discovery_roots[@]}"; do
  discovered="$discovery_root/$SKILL_NAME"
  if [[ "$discovered" != "$target" && -f "$discovered/SKILL.md" ]]; then
    fail "检测到另一个活动 Skill：${discovered}；请只保留目标 ${target} 后重试。处置：mkdir -p ~/.leo-ppt-generator-quarantine && mv '${discovered}' ~/.leo-ppt-generator-quarantine/"
  fi
  for discovered_backup in "$discovery_root"/$SKILL_NAME.backup-*/SKILL.md; do
    [[ -e "$discovered_backup" ]] || continue
    fail "检测到可被发现的旧备份：$(dirname "$discovered_backup")；请移入非发现目录后重试。处置：mkdir -p ~/.leo-ppt-generator-quarantine && mv '$(dirname "$discovered_backup")' ~/.leo-ppt-generator-quarantine/"
  done
done

stage_root=""
launcher_path=""
launcher_target="$target/scripts/leo-ppt"
launcher_stage=""
launcher_created=0
launcher_committed=0
runtime_switched=0
install_lock="$target_parent/.$SKILL_NAME.install.lock"
lock_acquired=0
cleanup() {
  if [[ "${runtime_switched:-0}" == "1" && "${launcher_committed:-0}" != "1" && \
        -n "${candidate:-}" && -x "${candidate}/scripts/leo-bootstrap.sh" ]]; then
    LEO_PPT_INSTALL_TARGET="${target:-}" "${candidate}/scripts/leo-bootstrap.sh" rollback >/dev/null 2>&1 || true
  fi
  if [[ -n "${launcher_stage:-}" && -L "$launcher_stage" ]]; then
    rm -f -- "$launcher_stage"
  fi
  if [[ "${launcher_created:-0}" == "1" && "${launcher_committed:-0}" != "1" && \
        -L "${launcher_path:-}" && "$(readlink "$launcher_path" 2>/dev/null || true)" == "$launcher_target" ]]; then
    rm -f -- "$launcher_path"
  fi
  if [[ -n "${stage_root:-}" && -d "$stage_root" ]]; then
    case "$stage_root" in
      "$target_parent"/.leo-ppt-installer.*) rm -rf -- "$stage_root" ;;
      *) printf '警告：拒绝清理非安装器临时目录：%s\n' "$stage_root" >&2 ;;
    esac
  fi
  if [[ "${lock_acquired:-0}" == "1" && -d "$install_lock" ]]; then
    case "$install_lock" in
      "$target_parent"/.$SKILL_NAME.install.lock)
        rmdir -- "$install_lock" 2>/dev/null || \
          printf '警告：安装锁未能自动移除：%s\n' "$install_lock" >&2
        ;;
      *) printf '警告：拒绝清理非安装器锁目录：%s\n' "$install_lock" >&2 ;;
    esac
  fi
}
trap cleanup EXIT

if ! mkdir "$install_lock" 2>/dev/null; then
  fail "另一个安装或升级正在操作该目标；若确认没有活动进程，请移除陈旧锁：$install_lock"
fi
lock_acquired=1

if [[ -e "$target" && "$upgrade" != "1" ]]; then
  fail "同名目录已存在：${target}；请先审阅，或明确使用 --upgrade"
fi
if [[ -e "$target" && ! -d "$target" ]]; then
  fail "目标已存在但不是目录：$target"
fi

if [[ -z "$bin_dir" ]]; then
  bin_dir="$HOME/.local/bin"
fi
mkdir -p "$bin_dir" || fail "无法创建用户命令目录：$bin_dir"
bin_dir="$(cd "$bin_dir" && pwd -P)"
launcher_path="$bin_dir/leo-ppt"
launcher_on_path=0
case ":${PATH:-}:" in
  *":$bin_dir:"*) launcher_on_path=1 ;;
esac
launcher_needs_install=1
if [[ -L "$launcher_path" ]]; then
  if [[ "$(readlink "$launcher_path")" == "$launcher_target" ]]; then
    launcher_needs_install=0
  else
    fail "leo-ppt 命令已指向其他位置：${launcher_path}；拒绝覆盖"
  fi
elif [[ -e "$launcher_path" ]]; then
  fail "leo-ppt 命令已存在且不属于当前安装：${launcher_path}；拒绝覆盖"
fi

stage_root="$(mktemp -d "$target_parent/.leo-ppt-installer.XXXXXX")"
if [[ "$launcher_needs_install" == "1" ]]; then
  launcher_stage="$bin_dir/.leo-ppt.$$.installing"
  [[ ! -e "$launcher_stage" && ! -L "$launcher_stage" ]] || \
    fail "launcher 临时路径已存在：$launcher_stage"
  ln -s "$launcher_target" "$launcher_stage" || fail "无法准备 leo-ppt launcher"
fi

[[ -f "$source_dir/SKILL.md" ]] || fail "来源缺少 SKILL.md：$source_dir"
[[ -f "$source_dir/scripts/runtime_manager.py" ]] || \
  fail "来源缺少 scripts/runtime_manager.py：$source_dir"
[[ -f "$source_dir/scripts/leo-bootstrap.sh" ]] || \
  fail "来源缺少 scripts/leo-bootstrap.sh：$source_dir"
[[ -f "$source_dir/scripts/leo-ppt" ]] || \
  fail "来源缺少 scripts/leo-ppt：$source_dir"
[[ -f "$source_dir/runtime/bootstrap-lock.json" ]] || \
  fail "来源缺少 runtime/bootstrap-lock.json：$source_dir"

candidate="$stage_root/$SKILL_NAME"
command -v tar >/dev/null 2>&1 || fail "缺少 tar，无法准备安装包"
mkdir -p "$candidate"
tar -C "$source_dir" \
  --exclude='.venv' --exclude='*/.venv' \
  --exclude='__pycache__' --exclude='*/__pycache__' \
  --exclude='build' --exclude='*/build' \
  --exclude='dist' --exclude='*/dist' \
  --exclude='*.egg-info' --exclude='*.pyc' --exclude='*.pyo' \
  --exclude='install.sh' --exclude='install.ps1' \
  -cf - . | tar -C "$candidate" -xf - || fail "准备安装包失败"

unsafe_path="$(find "$candidate" \( -type l -o -type d \( \
  -name third_party -o -name __pycache__ -o -name build -o -name '*.egg-info' \
  -o -name dist \
  \) -o -type f \( -name '*.pyc' -o -name '*.pyo' \) \) -print -quit)"
[[ -z "$unsafe_path" ]] || fail "安装包包含不允许的目录、生成物或符号链接：$unsafe_path"
chmod 755 "$candidate/scripts/leo-bootstrap.sh" || fail "无法设置 bootstrap launcher 执行权限"
chmod 755 "$candidate/scripts/leo-ppt" || fail "无法设置 leo-ppt launcher 执行权限"

backup=""
if [[ -e "$target" ]]; then
  backup_root="$target_parent/.$SKILL_NAME-backups"
  mkdir -p "$backup_root"
  backup="$backup_root/$(date -u +%Y%m%dT%H%M%SZ)-$$"
fi
install_channel="${LEO_PPT_PROVIDED_CHANNEL:-standalone}"
if [[ "$agents_mode" == "1" ]]; then
  install_channel="agent-skill"
fi

printf 'install[runtime_ensure]: 正在初始化受管 runtime…\n'
ensure_log="$stage_root/runtime-ensure.log"
if ! LEO_PPT_INSTALL_TARGET="$target" LEO_PPT_PREVIOUS_BUNDLE_BACKUP="$backup" \
  LEO_PPT_INSTALL_CHANNEL="$install_channel" \
  "$candidate/scripts/leo-bootstrap.sh" bootstrap >"$ensure_log"; then
  cat "$ensure_log" >&2
  fail "runtime 初始化失败；现有 Skill 未被替换"
fi
runtime_switched=1
if [[ "$(plutil -extract protocol raw -o - "$ensure_log" 2>/dev/null || true)" != "leo-ppt-bootstrap/v1" || \
      "$(plutil -extract status raw -o - "$ensure_log" 2>/dev/null || true)" != "ready" || \
      -z "$(plutil -extract runtime_identity raw -o - "$ensure_log" 2>/dev/null || true)" || \
      -z "$(plutil -extract cli_reference raw -o - "$ensure_log" 2>/dev/null || true)" ]]; then
  cat "$ensure_log" >&2
  reason="$(plutil -extract reason_code raw -o - "$ensure_log" 2>/dev/null || true)"
  fail "runtime 初始化返回无效 receipt（reason_code=${reason:-未知}）；现有 Skill 未被替换"
fi
printf 'runtime：就绪\n'

for route in generate direct-editable upgrade-full upgrade-selected; do
  printf 'install[route_doctor]: 正在验证 route：%s…\n' "$route"
  doctor_log="$stage_root/doctor-$route.log"
  if ! "$candidate/scripts/leo-bootstrap.sh" doctor --route "$route" \
    >"$doctor_log"; then
    cat "$doctor_log" >&2
    fail "route 验证失败：${route}；现有 Skill 未被替换"
  fi
  if [[ "$(plutil -extract status raw -o - "$doctor_log" 2>/dev/null || true)" != "ready" || \
        "$(plutil -extract reason_code raw -o - "$doctor_log" 2>/dev/null || true)" != "ready" ]]; then
    cat "$doctor_log" >&2
    reason="$(plutil -extract reason_code raw -o - "$doctor_log" 2>/dev/null || true)"
    fail "route 返回无效或未就绪 receipt：${route}（reason_code=${reason:-未知}）；现有 Skill 未被替换"
  fi
  printf 'route %s：本地机制就绪\n' "$route"
done

if [[ "$launcher_needs_install" == "1" ]]; then
  if ! mv "$launcher_stage" "$launcher_path"; then
    fail "无法激活 leo-ppt launcher：$launcher_path"
  fi
  launcher_stage=""
  launcher_created=1
fi
if [[ -e "$target" ]]; then
  [[ -n "$backup" ]] || fail "内部错误：未预留旧 bundle 备份目录"
  [[ ! -e "$backup" ]] || fail "备份目录已存在：$backup"
  mv "$target" "$backup"
fi

if ! mv "$candidate" "$target"; then
  if [[ -n "$backup" && -d "$backup" && ! -e "$target" ]]; then
    mv "$backup" "$target"
  fi
  fail "激活新 Skill 失败；已尝试恢复旧版本"
fi
launcher_committed=1
printf 'install[activate]: 已原子激活验证后的 Skill\n'
printf 'install[launcher]: 已安装稳定命令：%s\n' "$launcher_path"

shell_quote() {
  local value="$1"
  printf "'%s'" "${value//\'/\'\"\'\"\'}"
}

onboarding_log="$stage_root/post-activation-onboarding.json"
onboarding_status="blocked"
configuration_state="not_checked"
verification_status="not_checked"
execution_eligibility="blocked"
installation_readiness="installed_not_ready"
onboarding_reason="config_check_unavailable"
cli_reference=""

onboarding_value() {
  local key="$1"
  local fallback="$2"
  local value
  value="$(plutil -extract "$key" raw -o - "$onboarding_log" 2>/dev/null || true)"
  printf '%s' "${value:-$fallback}"
}

verification_label() {
  case "$verification_status" in
    passed) printf '已通过真实验证' ;;
    failed) printf '真实验证失败' ;;
    stale) printf '已过期（配置/模型/凭据已变化，需重新验证）' ;;
    not_run) printf '未验证（尚未生成过图片）' ;;
    *) printf '%s' "$verification_status" ;;
  esac
}

config_state_label() {
  case "$configuration_state" in
    configured) printf '已配置' ;;
    configured_unverified|locally_configured) printf '已配置（首次生成时验证）' ;;
    not_configured|missing) printf '尚未配置' ;;
    invalid) printf '配置无效' ;;
    not_checked) printf '未检查' ;;
    *) printf '%s' "$configuration_state" ;;
  esac
}

eligibility_label() {
  case "$execution_eligibility" in
    allowed) printf '允许开始任务' ;;
    blocked) printf '当前受阻' ;;
    retryable) printf '可重试' ;;
    unknown) printf '待确认' ;;
    *) printf '%s' "$execution_eligibility" ;;
  esac
}

readiness_label() {
  case "$installation_readiness" in
    ready) printf '就绪' ;;
    usable_unverified) printf '可用（待首次验证）' ;;
    installed_not_ready) printf '已安装但未就绪' ;;
    *) printf '%s' "$installation_readiness" ;;
  esac
}

host_display_name() {
  if [[ -n "$host_kind" ]]; then
    case "$host_kind" in
      claude) printf 'Claude Code' ;;
      agents) printf 'agents 宿主' ;;
      *) printf 'Codex' ;;
    esac
  elif [[ "$agents_mode" == "1" ]]; then
    printf 'agents 宿主'
  else
    printf 'Codex'
  fi
}

run_post_activation_onboarding() {
  printf 'install[onboarding]: 正在检查图片服务配置…\n'
  if ! "$target/scripts/leo-bootstrap.sh" onboard --route generate >"$onboarding_log"; then
    printf '安装后配置检查未完整执行；Skill 仍保持已激活状态。\n' >&2
  fi

  onboarding_status="$(onboarding_value status blocked)"
  configuration_state="$(onboarding_value configuration_state not_checked)"
  verification_status="$(onboarding_value verification.status not_run)"
  execution_eligibility="$(onboarding_value execution_eligibility blocked)"
  installation_readiness="$(onboarding_value installation_readiness installed_not_ready)"
  onboarding_reason="$(onboarding_value reason_code config_check_unavailable)"
  cli_reference="$(onboarding_value cli_reference '')"
  if [[ "$cli_reference" != /* ]]; then
    cli_reference=""
  fi
}

print_onboarding_report() {
  printf '安装状态：已安装\n'
  printf '配置状态：%s\n' "$(config_state_label)"
  printf '真实验证状态：%s\n' "$(verification_label)"
  printf '执行资格：%s\n' "$(eligibility_label)"
  printf '安装可用性：%s\n' "$(readiness_label)"
  printf '原因码：%s\n' "$onboarding_reason"

  case "$installation_readiness" in
    ready)
      printf '图片服务已就绪，可以开始生成 PPT。\n'
      ;;
    usable_unverified)
      if [[ "$verification_status" == "stale" ]]; then
        printf '配置已更新，但此前验证已失效；下次生成图片时会重新验证。\n'
      else
        printf '配置完成，可以开始使用；首次生成图片时验证服务。\n'
      fi
      ;;
    *)
      printf 'Skill 已安装，但当前图片服务尚未就绪。\n'
      ;;
  esac
}

print_configuration_command() {
  printf '稍后可运行：'
  if [[ "$launcher_on_path" == "1" ]]; then
    printf 'leo-ppt config\n'
  elif [[ -n "$launcher_path" ]]; then
    shell_quote "$launcher_path"
    printf ' config\n'
  elif [[ -n "$cli_reference" ]]; then
    shell_quote "$cli_reference"
    printf ' config\n'
  else
    shell_quote "$target/scripts/leo-bootstrap.sh"
    printf ' bootstrap\n'
  fi
}

printf '\n安装成功：%s\n' "$target"
if [[ -n "$backup" ]]; then
  printf '旧版本备份：%s\n' "$backup"
  # L9：升级成功即触发历史备份保留清理（失败不阻断本次交付）。
  run_internal_prune "$target_parent/.$SKILL_NAME-backups"
fi

run_post_activation_onboarding
print_onboarding_report

if [[ "$execution_eligibility" != "allowed" ]]; then
  if [[ -z "$cli_reference" ]]; then
    print_configuration_command
  elif [[ ! -t 0 ]]; then
    printf '未检测到交互终端；不会等待配置输入或发起可能计费的验证。\n'
    print_configuration_command
  else
    response=""
    printf '现在启动配置向导吗？ [y/N] '
    IFS= read -r response || response=""
    case "$response" in
      y|Y|yes|YES|Yes)
        printf '正在启动配置向导；任何可能计费的验证仍需在向导中单独确认。\n'
        if ! "$cli_reference" config; then
          printf '配置向导未完成；Skill 仍保持已安装状态。\n' >&2
        fi
        run_post_activation_onboarding
        print_onboarding_report
        if [[ "$execution_eligibility" != "allowed" ]]; then
          print_configuration_command
        fi
        ;;
      *)
        printf '已推迟配置；Skill 仍保持已安装状态。\n'
        print_configuration_command
        ;;
    esac
  fi
fi

if [[ "$launcher_on_path" == "1" ]]; then
  printf '配置命令：leo-ppt config\n'
else
  printf '提示：%s 尚不在 PATH；加入 shell 配置后即可使用短命令：\n' "$bin_dir"
  printf "  export PATH='%s':\$PATH\n" "$bin_dir"
fi
printf '请重新启动 %s，或开启下一轮对话后使用 leo-ppt-generator。\n' "$(host_display_name)"
printf '下一步：直接说「把这份材料做成图片式 PPT」即可开始。\n'
if [[ -n "$backup" ]]; then
  printf '变更详情：%s\n' "$target/UPDATES.md"
fi
