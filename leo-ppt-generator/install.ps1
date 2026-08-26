# install.ps1 — 从本地源安装 leo-ppt-generator Skill。
#
# 本脚本只支持本地安装：默认从脚本所在目录拷贝 Skill 内容到目标位置。
# 远端下载与版本拉取逻辑已被移除；版本管理以 git / 包管理器为准。

[CmdletBinding()]
param(
  [switch]$Agents,
  [string]$Source,
  [string]$Target,
  [string]$BinDir,
  [switch]$Upgrade,
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
  -Source <目录>          从本地 Skill 目录安装（默认：本脚本所在目录）
  -Target <目录>          指定完整安装目录（高级用法）
  -BinDir <目录>          安装稳定 leo-ppt 命令，默认 ~/.local/bin
  -Upgrade                验证新版本后替换现有 Skill，并保留旧版本备份
  -Help                   显示帮助

默认目标：\$env:CODEX_HOME\\skills\\leo-ppt-generator（若未设置则使用 $HOME\.codex）
"@
}

function Fail([string]$Message) {
  Write-Error "安装失败：$Message"
  exit 1
}

if ($Help) {
  Write-Usage
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

if ($Target -and $Agents) {
  Fail "-Agents 与 -Target 不能同时使用"
}

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

if (-not $Target) {
  if ($Agents) {
    $Target = Join-Path $HOME ".agents/skills/$SkillName"
  } else {
    $codexHome = if ($env:CODEX_HOME) { $env:CODEX_HOME } else { Join-Path $HOME '.codex' }
    $Target = Join-Path $codexHome "skills/$SkillName"
  }
}
if ((Split-Path -Leaf $Target) -ne $SkillName) {
  Fail "安装目录末级名称必须是 $SkillName"
}

$targetParent = Split-Path -Parent $Target
if (-not (Test-Path -LiteralPath $targetParent)) {
  New-Item -ItemType Directory -Path $targetParent -Force | Out-Null
}
$targetParent = (Resolve-Path -LiteralPath $targetParent).ProviderPath
$Target = Join-Path $targetParent $SkillName

$codexRoot = if ($env:CODEX_HOME) { $env:CODEX_HOME } else { Join-Path $HOME '.codex' }
$codexRoot = Join-Path $codexRoot 'skills'
$agentsRoot = Join-Path $HOME '.agents/skills'
$discoveryRoots = @($codexRoot, $agentsRoot)
if ($env:LEO_PPT_EXTRA_DISCOVERY_ROOTS) {
  $extra = $env:LEO_PPT_EXTRA_DISCOVERY_ROOTS -split ':'
  foreach ($extraRoot in $extra) {
    if ($extraRoot) { $discoveryRoots += $extraRoot }
  }
}
foreach ($discoveryRoot in $discoveryRoots) {
  $discovered = Join-Path $discoveryRoot $SkillName
  if ($discovered -ne $Target -and (Test-Path -LiteralPath (Join-Path $discovered 'SKILL.md'))) {
    Fail "检测到另一个活动 Skill：${discovered}；请只保留目标 ${Target} 后重试"
  }
  $backupGlob = Join-Path $discoveryRoot "$SkillName.backup-*"
  foreach ($discoveredBackup in Get-ChildItem -LiteralPath $backupGlob -Directory -ErrorAction SilentlyContinue) {
    if (Test-Path -LiteralPath (Join-Path $discoveredBackup 'SKILL.md')) {
      Fail "检测到可被发现的旧备份：$($discoveredBackup.FullName)；请移入非发现目录后重试"
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
  }
  Write-Host "请重新启动 Codex，或开启下一轮对话后使用 leo-ppt-generator。"
} catch {
  Remove-CleanupHooks
  throw
}
Remove-CleanupHooks
