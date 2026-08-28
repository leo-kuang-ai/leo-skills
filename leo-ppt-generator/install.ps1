# install.ps1 — 从本地源安装 leo-ppt-generator Skill。
#
# 本脚本只支持本地安装：默认从脚本所在目录拷贝 Skill 内容到目标位置。
# 远端下载与版本拉取逻辑已被移除；版本管理以 git / 包管理器为准。

[CmdletBinding()]
param(
  [switch]$Agents,
  [Alias('Host')]
  [string]$InstallHost,
  [string]$Source,
  [string]$Target,
  [string]$BinDir,
  [switch]$Upgrade,
  [switch]$Uninstall,
  [switch]$PurgeData,
  [switch]$InternalPrintTarget,
  [switch]$Help
)

$ErrorActionPreference = 'Stop'

$SkillName = 'leo-ppt-generator'

function Write-Usage {
  @"
安装 Leo PPT Generator Skill（仅本地模式）。

用法：
  pwsh install.ps1 [选项]

选项：
  -Agents                 安装到 ~/.agents/skills，而不是 Codex 用户目录
  -Host <name>            目标宿主：codex | agents | claude（默认 codex）
  -Source <目录>          从本地 Skill 目录安装（默认：本脚本所在目录）
  -Uninstall [-PurgeData] 移除命令与技能目录；-PurgeData 连同数据目录清除。
                          钥匙串条目永不自动删除。
  -Target <目录>          指定完整安装目录（高级用法）
  -BinDir <目录>          安装稳定 leo-ppt 命令，默认 ~/.local/bin
  -Upgrade                验证新版本后替换现有 Skill，并保留旧版本备份
  -Help                   显示帮助

默认目标：\$env:CODEX_HOME\skills\leo-ppt-generator（若未设置则使用 $HOME\.codex）
"@
}

function Fail([string]$Message) {
  Write-Error "安装失败：$Message"
  exit 1
}

function Get-HostDisplayName {
  if ($InstallHost -eq 'claude') { return 'Claude Code' }
  if ($InstallHost -eq 'agents') { return 'agents 宿主' }
  if ($InstallHost -eq 'codex') { return 'Codex' }
  if ($Agents) { return 'agents 宿主' }
  return 'Codex'
}

function Get-ConfigStateLabel([string]$Value) {
  switch ($Value) {
    'configured' { '已配置' }
    { $_ -in @('configured_unverified', 'locally_configured') } { '已配置（首次生成时验证）' }
    { $_ -in @('not_configured', 'missing') } { '尚未配置' }
    'invalid' { '配置无效' }
    'not_checked' { '未检查' }
    default { $Value }
  }
}

function Get-EligibilityLabel([string]$Value) {
  switch ($Value) {
    'allowed' { '允许开始任务' }
    'blocked' { '当前受阻' }
    'retryable' { '可重试' }
    'unknown' { '待确认' }
    default { $Value }
  }
}

function Get-ReadinessLabel([string]$Value) {
  switch ($Value) {
    'ready' { '就绪' }
    'usable_unverified' { '可用（待首次验证）' }
    'installed_not_ready' { '已安装但未就绪' }
    default { $Value }
  }
}

function Get-VerificationLabel([string]$Value) {
  switch ($Value) {
    'passed' { '已通过真实验证' }
    'failed' { '真实验证失败' }
    'stale' { '已过期（配置/模型/凭据已变化，需重新验证）' }
    'not_run' { '未验证（尚未生成过图片）' }
    default { $Value }
  }
}

if ($Help) {
  Write-Usage
  exit 0
}

# R17：-Uninstall 默认只拆程序面；-PurgeData 显式清数据；钥匙串永不自动触碰。
if ($Uninstall) {
  $uninstallBin = if ($BinDir) { $BinDir } else { Join-Path $HOME '.local/bin' }
  foreach ($launcherName in 'leo-ppt.exe', 'leo-ppt') {
    $launcherCandidate = Join-Path $uninstallBin $launcherName
    if (Test-Path -LiteralPath $launcherCandidate -PathType Leaf) {
      Remove-Item -LiteralPath $launcherCandidate -Force
      Write-Host "已移除命令：$launcherCandidate"
    }
  }
  $selfDir = (Resolve-Path -LiteralPath $PSScriptRoot).ProviderPath
  $parentName = Split-Path -Leaf (Split-Path -Parent $selfDir)
  if ((Test-Path -LiteralPath (Join-Path $selfDir 'SKILL.md')) -and $parentName -eq 'skills') {
    Remove-Item -LiteralPath $selfDir -Recurse -Force
    Write-Host "已移除技能目录：$selfDir"
  } else {
    Write-Host '跳过：当前目录形态不像已安装位置（父目录须为 skills）；未做删除。'
  }
  $dataHome = if ($env:LEO_PPT_HOME) { $env:LEO_PPT_HOME } else { Join-Path $env:LOCALAPPDATA 'leo-ppt-generator' }
  if ($PurgeData -and (Test-Path -LiteralPath $dataHome)) {
    Remove-Item -LiteralPath $dataHome -Recurse -Force
    Write-Host "已清除数据目录：$dataHome"
  } else {
    Write-Host "数据目录已保留：$dataHome"
  }
  Write-Host '钥匙串条目（服务名 leo-ppt-generator/*）不会被自动删除；如需清理，请在凭据管理器/钥匙串中确认后手动删除。'
  exit 0
}

function Resolve-Scope {
  if ($Target -and $Agents) {
    Fail "-Agents 与 -Target 不能同时使用"
  }
  if ($Target -and $InstallHost) {
    Fail "-Host 与 -Target 不能同时使用"
  }
  if ($InstallHost) {
    if ($InstallHost -notin @('codex', 'agents', 'claude')) {
      Fail "未知宿主：$InstallHost；-Host 仅支持 codex|agents|claude"
    }
    if ($Agents -and $InstallHost -ne 'agents') {
      Fail "-Agents 与 -Host $InstallHost 冲突"
    }
  }
  if (-not $Target) {
    if ($InstallHost) {
      switch ($InstallHost) {
        'codex' {
          $codexHome = if ($env:CODEX_HOME) { $env:CODEX_HOME } else { Join-Path $HOME '.codex' }
          $script:Target = Join-Path $codexHome "skills/$SkillName"
        }
        'agents' { $script:Target = Join-Path $HOME ".agents/skills/$SkillName" }
        'claude' {
          $claudeHome = if ($env:CLAUDE_CONFIG_DIR) { $env:CLAUDE_CONFIG_DIR } else { Join-Path $HOME '.claude' }
          $script:Target = Join-Path $claudeHome "skills/$SkillName"
        }
      }
    } elseif ($Agents) {
      $script:Target = Join-Path $HOME ".agents/skills/$SkillName"
    } else {
      $codexHome = if ($env:CODEX_HOME) { $env:CODEX_HOME } else { Join-Path $HOME '.codex' }
      $script:Target = Join-Path $codexHome "skills/$SkillName"
    }
  }
  if ((Split-Path -Leaf $script:Target) -ne $SkillName) {
    Fail "安装目录末级名称必须是 $SkillName"
  }
}

if ($InternalPrintTarget) {
  Resolve-Scope
  Write-Output "parent=$(Split-Path -Parent $script:Target)"
  Write-Output "name=$(Split-Path -Leaf $script:Target)"
  exit 0
}

if ($PSVersionTable.Platform -ne 'Win32NT') {
  Fail "当前版本仅支持 Windows x64；检测到 $($PSVersionTable.Platform)"
}
$arch = [System.Runtime.InteropServices.RuntimeInformation]::OSArchitecture
if ($arch -ne 'X64' -and $arch -ne 'Arm64') {
  Fail "当前版本仅支持 Windows x64 / Arm64；检测到 $arch"
}
Write-Host "install[platform_check]: Windows $arch 已确认"

Resolve-Scope

# 默认 source_dir 为本脚本所在目录
if (-not $Source) {
  $scriptSelf = (Resolve-Path -LiteralPath $PSScriptRoot).ProviderPath
  if (-not (Test-Path -LiteralPath (Join-Path $scriptSelf 'SKILL.md'))) {
    Fail "未指定 -Source，且本脚本所在目录缺少 SKILL.md：$scriptSelf"
  }
  $Source = $scriptSelf
}
if (-not (Test-Path -LiteralPath $Source -PathType Container)) {
  Fail "本地来源目录不存在：$Source"
}
$Source = (Resolve-Path -LiteralPath $Source).ProviderPath

$targetParent = Split-Path -Parent $Target
if (-not (Test-Path -LiteralPath $targetParent)) {
  New-Item -ItemType Directory -Path $targetParent -Force | Out-Null
}
$targetParent = (Resolve-Path -LiteralPath $targetParent).ProviderPath
$Target = Join-Path $targetParent $SkillName

$codexRoot = if ($env:CODEX_HOME) { $env:CODEX_HOME } else { Join-Path $HOME '.codex' }
$codexRoot = Join-Path $codexRoot 'skills'
$agentsRoot = Join-Path $HOME '.agents/skills'
$claudeRoot = if ($env:CLAUDE_CONFIG_DIR) { $env:CLAUDE_CONFIG_DIR } else { Join-Path $HOME '.claude' }
$claudeRoot = Join-Path $claudeRoot 'skills'
$discoveryRoots = @($codexRoot, $agentsRoot, $claudeRoot)
if ($env:LEO_PPT_EXTRA_DISCOVERY_ROOTS) {
  $extra = $env:LEO_PPT_EXTRA_DISCOVERY_ROOTS -split ':'
  foreach ($extraRoot in $extra) {
    if ($extraRoot) { $discoveryRoots += $extraRoot }
  }
}
foreach ($discoveryRoot in $discoveryRoots) {
  $discovered = Join-Path $discoveryRoot $SkillName
  if ($discovered -ne $Target -and (Test-Path -LiteralPath (Join-Path $discovered 'SKILL.md'))) {
    Fail "检测到另一个活动 Skill：${discovered}；请只保留目标 ${Target} 后重试。处置：New-Item -ItemType Directory -Force `"$env:USERPROFILE\.leo-ppt-generator-quarantine`" | Out-Null; Move-Item `"$discovered`" `"$env:USERPROFILE\.leo-ppt-generator-quarantine\`""
  }
  $backupGlob = Join-Path $discoveryRoot "$SkillName.backup-*"
  foreach ($discoveredBackup in Get-ChildItem -LiteralPath $backupGlob -Directory -ErrorAction SilentlyContinue) {
    if (Test-Path -LiteralPath (Join-Path $discoveredBackup 'SKILL.md')) {
      Fail "检测到可被发现的旧备份：$($discoveredBackup.FullName)；请移入非发现目录后重试。处置：Move-Item `"$($discoveredBackup.FullName)`" `"$env:USERPROFILE\.leo-ppt-generator-quarantine\`" -Force"
    }
  }
}

$script:stageRoot = $null
$script:launcherPath = $null
$script:launcherTarget = Join-Path "$Target/scripts" 'leo-ppt.exe'
$script:launcherStage = $null
$script:launcherCreated = $false
$script:launcherCommitted = $false
$script:runtimeSwitched = $false
$script:candidate = $null
$script:lockAcquired = $false
$script:backup = $null

$installLock = Join-Path $targetParent ".$SkillName.install.lock"

function Remove-CleanupHooks {
  if ($script:runtimeSwitched -and -not $script:launcherCommitted -and $script:candidate -and (Test-Path -LiteralPath (Join-Path $script:candidate 'scripts/leo-bootstrap.sh'))) {
    $env:LEO_PPT_INSTALL_TARGET = $Target
    try { & (Join-Path $script:candidate 'scripts/leo-bootstrap.sh') rollback *> $null } catch { }
  }
  if ($script:launcherStage -and (Test-Path -LiteralPath $script:launcherStage)) {
    Remove-Item -LiteralPath $script:launcherStage -ErrorAction SilentlyContinue
  }
  if ($script:launcherCreated -and -not $script:launcherCommitted -and $script:launcherPath -and (Test-Path -LiteralPath $script:launcherPath)) {
    $linkTarget = (Get-Item -LiteralPath $script:launcherPath -ErrorAction SilentlyContinue).Target
    if ($linkTarget -eq $script:launcherTarget) {
      Remove-Item -LiteralPath $script:launcherPath -ErrorAction SilentlyContinue
    }
  }
  if ($script:stageRoot -and (Test-Path -LiteralPath $script:stageRoot)) {
    if ($script:stageRoot.StartsWith("$targetParent/.leo-ppt-installer.")) {
      Remove-Item -LiteralPath $script:stageRoot -Recurse -Force -ErrorAction SilentlyContinue
    } else {
      Write-Warning "拒绝清理非安装器临时目录：$($script:stageRoot)"
    }
  }
  if ($script:lockAcquired -and (Test-Path -LiteralPath $installLock)) {
    if ($installLock -eq (Join-Path $targetParent ".$SkillName.install.lock")) {
      Remove-Item -LiteralPath $installLock -ErrorAction SilentlyContinue
    } else {
      Write-Warning "拒绝清理非安装器锁目录：$installLock"
    }
  }
}

try {
  if (-not (New-Item -ItemType Directory -Path $installLock -ErrorAction SilentlyContinue)) {
    Fail "另一个安装或升级正在操作该目标；若确认没有活动进程，请移除陈旧锁：$installLock"
  }
  $script:lockAcquired = $true

  if ((Test-Path -LiteralPath $Target) -and -not $Upgrade) {
    Fail "同名目录已存在：${Target}；请先审阅，或明确使用 -Upgrade"
  }
  if ((Test-Path -LiteralPath $Target) -and -not (Test-Path -LiteralPath $Target -PathType Container)) {
    Fail "目标已存在但不是目录：$Target"
  }

  if (-not $BinDir) {
    $BinDir = Join-Path $HOME '.local/bin'
  }
  if (-not (Test-Path -LiteralPath $BinDir)) {
    New-Item -ItemType Directory -Path $BinDir -Force | Out-Null
  }
  $BinDir = (Resolve-Path -LiteralPath $BinDir).ProviderPath
  $script:launcherPath = Join-Path $BinDir 'leo-ppt.exe'
  $launcherOnPath = $false
  foreach ($dir in ($env:PATH -split [IO.Path]::PathSeparator)) {
    if ($dir -eq $BinDir) { $launcherOnPath = $true; break }
  }
  $launcherNeedsInstall = $true
  if (Test-Path -LiteralPath $script:launcherPath) {
    $item = Get-Item -LiteralPath $script:launcherPath
    if ($item.LinkType -and $item.Target -eq $script:launcherTarget) {
      $launcherNeedsInstall = $false
    } else {
      Fail "leo-ppt 命令已存在且不属于当前安装：$($script:launcherPath)；拒绝覆盖"
    }
  }

  $stageName = ".leo-ppt-installer.$(Get-Random)"
  $script:stageRoot = Join-Path $targetParent $stageName
  New-Item -ItemType Directory -Path $script:stageRoot | Out-Null
  if ($launcherNeedsInstall) {
    $script:launcherStage = Join-Path $BinDir ".leo-ppt.$PID.installing.exe"
    if (Test-Path -LiteralPath $script:launcherStage) {
      Fail "launcher 临时路径已存在：$($script:launcherStage)"
    }
    New-Item -ItemType SymbolicLink -Path $script:launcherStage -Target $script:launcherTarget -ErrorAction SilentlyContinue | Out-Null
    if (-not (Test-Path -LiteralPath $script:launcherStage)) {
      Fail "无法准备 leo-ppt launcher"
    }
  }

  foreach ($name in 'SKILL.md', 'scripts/runtime_manager.py', 'scripts/leo-bootstrap.sh', 'scripts/leo-ppt', 'runtime/bootstrap-lock.json') {
    if (-not (Test-Path -LiteralPath (Join-Path $Source $name))) {
      Fail "来源缺少 $name：$Source"
    }
  }

  $script:candidate = Join-Path $script:stageRoot $SkillName
  New-Item -ItemType Directory -Path $script:candidate | Out-Null
  $tar = (Get-Command tar -ErrorAction SilentlyContinue)
  if (-not $tar) { Fail "缺少 tar，无法准备安装包" }
  $excludeArgs = @(
    '--exclude=.venv', '--exclude=*/.venv',
    '--exclude=__pycache__', '--exclude=*/__pycache__',
    '--exclude=build', '--exclude=*/build',
    '--exclude=dist', '--exclude=*/dist',
    '--exclude=*.egg-info', '--exclude=*.pyc', '--exclude=*.pyo',
    '--exclude=install.sh', '--exclude=install.ps1'
  )
  tar -C $Source @excludeArgs -cf - . | tar -C $script:candidate -xf -
  if ($LASTEXITCODE -ne 0) { Fail "准备安装包失败" }

  $unsafe = Get-ChildItem -LiteralPath $script:candidate -Recurse |
    Where-Object {
      $_.LinkType -or
      ($_.PSIsContainer -and ($_.Name -in @('third_party', '__pycache__', 'build', 'dist') -or $_.Name -like '*.egg-info')) -or
      ($_.PSIsContainer -eq $false -and ($_.Name -like '*.pyc' -or $_.Name -like '*.pyo'))
    } | Select-Object -First 1
  if ($unsafe) { Fail "安装包包含不允许的目录、生成物或符号链接：$($unsafe.FullName)" }

  # scripts/leo-ppt is a bash launcher; on Windows PowerShell is a no-op for it.
  # The runtime CLI is reachable via scripts/leo-bootstrap.sh or the runtime build.

  if (Test-Path -LiteralPath $Target) {
    $backupRoot = Join-Path $targetParent ".$SkillName-backups"
    if (-not (Test-Path -LiteralPath $backupRoot)) {
      New-Item -ItemType Directory -Path $backupRoot | Out-Null
    }
    $stamp = (Get-Date).ToUniversalTime().ToString('yyyyMMddTHHmmssZ')
    $script:backup = Join-Path $backupRoot "$stamp-$PID"
  }
  $installChannel = if ($env:LEO_PPT_PROVIDED_CHANNEL) { $env:LEO_PPT_PROVIDED_CHANNEL } else { 'standalone' }
  if ($Agents) { $installChannel = 'agent-skill' }

  Write-Host 'install[runtime_ensure]: 正在初始化受管 runtime…'
  $ensureLog = Join-Path $script:stageRoot 'runtime-ensure.log'
  $env:LEO_PPT_INSTALL_TARGET = $Target
  $env:LEO_PPT_PREVIOUS_BUNDLE_BACKUP = $script:backup
  $env:LEO_PPT_INSTALL_CHANNEL = $installChannel
  & (Join-Path $script:candidate 'scripts/leo-bootstrap.sh') bootstrap *> $ensureLog
  $env:LEO_PPT_INSTALL_TARGET = $null
  $env:LEO_PPT_PREVIOUS_BUNDLE_BACKUP = $null
  $env:LEO_PPT_INSTALL_CHANNEL = $null
  if ($LASTEXITCODE -ne 0) {
    Get-Content -LiteralPath $ensureLog -ErrorAction SilentlyContinue
    Fail "runtime 初始化失败；现有 Skill 未被替换"
  }
  $script:runtimeSwitched = $true

  foreach ($route in 'generate', 'direct-editable', 'upgrade-full', 'upgrade-selected') {
    Write-Host "install[route_doctor]: 正在验证 route：$route…"
    $doctorLog = Join-Path $script:stageRoot "doctor-$route.log"
    & (Join-Path $script:candidate 'scripts/leo-bootstrap.sh') doctor --route $route *> $doctorLog
    if ($LASTEXITCODE -ne 0) {
      Get-Content -LiteralPath $doctorLog -ErrorAction SilentlyContinue
      Fail "route 验证失败：${route}；现有 Skill 未被替换"
    }
    Write-Host "route $route：本地机制就绪"
  }

  if ($launcherNeedsInstall) {
    Move-Item -LiteralPath $script:launcherStage -Destination $script:launcherPath -Force
    $script:launcherStage = $null
    $script:launcherCreated = $true
  }
  if (Test-Path -LiteralPath $Target) {
    if (-not $script:backup) { Fail '内部错误：未预留旧 bundle 备份目录' }
    if (Test-Path -LiteralPath $script:backup) { Fail "备份目录已存在：$($script:backup)" }
    Move-Item -LiteralPath $Target -Destination $script:backup
  }
  Move-Item -LiteralPath $script:candidate -Destination $Target
  $script:launcherCommitted = $true
  Write-Host 'install[activate]: 已原子激活验证后的 Skill'
  Write-Host "install[launcher]: 已安装稳定命令：$($script:launcherPath)"

  Write-Host ""
  Write-Host "安装成功：$Target"
  if ($script:backup) {
    Write-Host "旧版本备份：$($script:backup)"
    # L9：升级成功即触发历史备份保留清理（失败不阻断本次交付），复用 bash 侧实现。
    $pruneBackupsRoot = Split-Path -Parent $script:backup
    & (Join-Path $Target 'scripts/install.sh') --internal-prune-skill-backups $pruneBackupsRoot
  }

  # L3：装后 onboarding 报告（与 bash 版语义对齐；跳过交互向导时给出配置命令）。
  Write-Host 'install[onboarding]: 正在检查图片服务配置…'
  $onboardLog = Join-Path $env:TEMP ("leo-onboard-" + [guid]::NewGuid().ToString('N') + '.json')
  $cliReference = ''
  try {
    & bash (Join-Path $Target 'scripts/install.sh') --internal-run-onboard $Target *> $onboardLog
    $onboard = Get-Content -LiteralPath $onboardLog -Raw | ConvertFrom-Json
    $cliReference = [string]$onboard.cli_reference
    $configState = Get-ConfigStateLabel ([string]$onboard.configuration_state)
    $verifLabel = Get-VerificationLabel ([string]$onboard.verification.status)
    $eligLabel = Get-EligibilityLabel ([string]$onboard.execution_eligibility)
    $readyLabel = Get-ReadinessLabel ([string]$onboard.installation_readiness)
    Write-Host "安装状态：已安装"
    Write-Host "配置状态：$configState"
    Write-Host "真实验证状态：$verifLabel"
    Write-Host "执行资格：$eligLabel"
    Write-Host "安装可用性：$readyLabel"
    Write-Host "原因码：$([string]$onboard.reason_code)"
    if ($onboard.installation_readiness -eq 'ready') {
      Write-Host '图片服务已就绪，可以开始生成 PPT。'
    } elseif ($onboard.installation_readiness -eq 'usable_unverified') {
      Write-Host '配置完成，可以开始使用；首次生成图片时验证服务。'
    } else {
      Write-Host 'Skill 已安装，但当前图片服务尚未就绪。'
    }
  } catch {
    Write-Host '安装后配置检查未完整执行；Skill 仍保持已激活状态。'
  } finally {
    Remove-Item -LiteralPath $onboardLog -Force -ErrorAction SilentlyContinue
  }
  if ($eligLabel -ne '允许开始任务') {
    if (-not $cliReference) {
      Write-Host "稍后可运行：leo-ppt config（或 $(Join-Path $Target 'scripts/install.sh') bootstrap）"
    } elseif ([Environment]::UserInteractive) {
      $reply = Read-Host '现在启动配置向导吗？ [y/N]'
      switch -Regex ($reply) {
        '^(y|Y|yes|YES|Yes)$' {
          Write-Host '正在启动配置向导；任何可能计费的验证仍需在向导中单独确认。'
          & $cliReference config
          Write-Host "配置完成后回到本提示可复查：leo-ppt config status"
        }
        default { Write-Host '已推迟配置；Skill 仍保持已安装状态。' }
      }
    } else {
      Write-Host '未检测到交互终端；不会等待配置输入或发起可能计费的验证。'
      Write-Host "稍后可运行：& `"$cliReference`" config"
    }
  }

  Write-Host "请重新启动 $(Get-HostDisplayName)，或开启下一轮对话后使用 leo-ppt-generator。"
  Write-Host '下一步：直接说「把这份材料做成图片式 PPT」即可开始。'
  if ($script:backup) {
    Write-Host "变更详情：$(Join-Path $Target 'UPDATES.md')"
  }
} catch {
  Remove-CleanupHooks
  throw
}
Remove-CleanupHooks
