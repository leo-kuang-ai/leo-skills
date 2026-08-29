# Leo PPT Generator

Leo PPT Generator 用于生成图片式 PPTX、把图片/PDF/可信 Office 输入重建为对象级可编辑 PPTX，
以及把既有图片式演示文稿升级为全量或指定页的 editable/hybrid 版本。

## 支持的 Route

- `generate`：从文章、报告、笔记或大纲生成图片式演示文稿。
- `direct-editable`：从图片、PDF 或用户确认可信的 PPT/PPTX 重建可编辑对象。
- `upgrade-full`：将既有 image-deck 全量升级为可编辑版本。
- `upgrade-selected`：只升级指定页面，其余页面保留图片。

## 使用方式

安装后，在 Agent 对话中明确提交材料、目标受众、交付类型和验收要求。例如：

> 使用 `leo-ppt-generator` 把季度复盘报告做成 12 页、面向管理层的 PPT，先确认大纲和样张。

首次执行会自动检查受管 runtime、宿主能力和 Provider 状态。用户不需要手工初始化 runtime，
也不应在聊天中粘贴 API 密钥。

### 安装

#### 方式一：一行命令（推荐，已实测）

```sh
npx skills add leo-kuang-ai/leo-skills                       # 装齐三个技能
npx skills add leo-kuang-ai/leo-skills -s leo-ppt-generator  # 只装本技能
```

通用安装器（[vercel-labs/skills](https://github.com/vercel-labs/skills)）自动识别 78+ 宿主；`-a <宿主>` 指定安装目标、`-g` 装到用户级全局、`--list` 只预览不安装。也可以直接在 agent 对话里说：`帮我安装这个 skill：https://github.com/leo-kuang-ai/leo-skills`。

#### 方式二：手动 clone / 包级安装器

完整宿主路径表与 Claude Code 官方插件市场链路（含更新 / 卸载闭环）见[仓库根 README](../README.md#安装与使用)；Claude Code 一行装法：

```sh
claude plugin marketplace add leo-kuang-ai/leo-skills && claude plugin install leo-ppt-generator@leo-skills
```

包级安装器提供升级、卸载与稳定 `leo-ppt` 命令等通用安装器未覆盖的能力（在包根目录执行）：

| 宿主 | 安装命令 | 默认安装位置 |
|---|---|---|
| Codex（默认） | `bash install.sh` | `${CODEX_HOME:-~/.codex}/skills` |
| agents 通用目录 | `bash install.sh --agents` 或 `--host agents` | `~/.agents/skills` |
| Claude Code | `bash install.sh --host claude` | `${CLAUDE_CONFIG_DIR:-~/.claude}/skills` |
| Windows (x64) | `pwsh install.ps1 [-Host <name>]` | 同上规则 |

升级：`install.sh --upgrade` / `install.ps1 -Upgrade`（校验通过后原子替换，旧版自动备份，
历史备份保留最近 3 份；受管 runtime 仅保留 current 与最近 2 个版本，成功后自动回收并报告
释放空间）。更新内容速览见包内 `UPDATES.md`，完整逐项变更见仓库根 `CHANGELOG.md`。

配置状态短语对照：`configured_unverified / locally_configured` = 已配置，首次生成图片时
顺带完成真实验证；`not_configured / invalid` = 尚未配置或无效，需运行 `leo-ppt config`。

#### 方式三：作为参考资料使用

即使 runtime 不支持自动加载，也可以直接打开本技能的 `SKILL.md`，把内容粘贴进对话。

## 故障排查

- 本地机制健康自检：`leo-ppt doctor`
- 回滚到上一个可用 runtime：`leo-ppt rollback`（identity 可由 `doctor` 输出获得）
- 升级/清理相关问题先看 `UPDATES.md` 与 `CHANGELOG.md`，再考虑重装。

## 卸载

1. 移除稳定命令：删除 `~/.local/bin/leo-ppt`（Windows：删除 `-BinDir` 下的 `leo-ppt.exe`）；
2. 移除技能目录：删除上表"默认安装位置"中的 `leo-ppt-generator/` 目录；
   也可直接执行 `install.sh --uninstall`（Windows：`pwsh install.ps1 -Uninstall`），
   脚本只会拆除自身所在安装位；
3. 数据目录默认保留。确认不再使用后可加 `--purge-data`（Windows：`-PurgeData`）
   一并清除配置与受管 runtime；
4. 钥匙串条目不会被脚本触碰：请在「钥匙串访问」（macOS）或「凭据管理器」(Windows)
   中搜索服务名 `leo-ppt-generator/*`，确认后手动删除。

## 安全边界

- 来源未知或未确认可信的 PPT/PPTX 会直接返回 `blocked/untrusted_office_input`，不会读取、
  扫描、隔离、净化或继续重建；请改用可信 PDF 或逐页图片。
- 已确认可信的 PPTX 仍必须通过 CLI preflight；宏、嵌入对象、外部关系、远程模板和损坏结构
  会继续 fail-closed。
- 凭据只使用宿主注入、允许的环境变量引用或受保护的系统存储；不写入项目、日志或对话。
- 设计取舍：`SKILL.md` frontmatter 的 `description` 刻意超出 Agent Skills 官方
  ~100 token 建议，以在触发层保留 Gate 0 负触发语义（"来源未知的 PPT/PPTX 仍须激活本
  Skill 并立即阻断"）。宿主的技能选择通常只看 description；压缩它会带来恶意 Office
  输入不激活技能、阻断门禁旁路的风险。此偏离为有意为之。

## 交付与验证

生成、编辑和升级均要求独立项目目录、可追溯的 run、页面级验证和明确的交付类型。
结构验证不等于视觉等价；Provider、OCR、Office viewer、桌面 PowerPoint 和人工视觉验收
分别报告。只有 `delivery_readiness=accepted` 才能声称交付闭环。

详细规则见：

- [输入路由](references/input-routing.md)
- [首次使用](references/first-use.md)
- [执行合同](references/execution-contract.md)
- [图片式工作流](references/image-deck-workflow.md)
- [可编辑工作流](references/editable-workflow.md)
- [视觉质检](references/visual-qa.md)

## 兼容范围

安装器面向 macOS arm64/x86_64 与 Windows x64。实际图片 Provider、OCR、桌面 Office 和
worker 能力取决于当前宿主现场；安装成功不代表这些外部能力已验证可用。

## 许可证

本 Skill 及其随包 runtime 按目录中的许可证文件发布。
