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

## 安全边界

- 来源未知或未确认可信的 PPT/PPTX 会直接返回 `blocked/untrusted_office_input`，不会读取、
  扫描、隔离、净化或继续重建；请改用可信 PDF 或逐页图片。
- 已确认可信的 PPTX 仍必须通过 CLI preflight；宏、嵌入对象、外部关系、远程模板和损坏结构
  会继续 fail-closed。
- 凭据只使用宿主注入、允许的环境变量引用或受保护的系统存储；不写入项目、日志或对话。

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
