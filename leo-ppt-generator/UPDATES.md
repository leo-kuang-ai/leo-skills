# 更新内容速览

每次升级或受管 runtime 更新后，从这里了解"这次变了什么"。

## 如何查看完整历史

- 仓库级逐项变更：仓库根目录 `CHANGELOG.md`（Keep a Changelog 格式）。
- 技能合同级的行为变化：`SKILL.md` 与 `references/` 的对应小节；重大行为变化会以
  `(user-visible)` 标注出现在 CHANGELOG 中。

## 升级后会发生什么

- 旧版技能目录会自动备份到 `<安装根>/.leo-ppt-generator-backups/`，默认保留最近 3 份；
- 受管 runtime 只保留 current 与最近的 2 个版本，超出的会在成功路径末尾自动回收；
- 若图片服务配置此前已通过验证，配置/模型/凭据变化后该验证会被标记为过期，
  下次生成第一张真实业务图片时会自动重新验证——无需额外操作，也不产生额外费用。

## 常用命令

- 查看本地机制健康：`leo-ppt doctor`
- 回滚到上一个可用 runtime：`leo-ppt rollback`

## 本期速览（2026-09 渠道与控制台批次）

- **渠道目录扩至 18 项**：新增 8 家目录渠道——硅基流动、阶跃星辰、xAI Grok、
  DeepInfra、Together AI（OpenAI 兼容），以及 Google Gemini（Nano Banana）、MiniMax、
  Ideogram 三家原生协议渠道（适配器自动转换，配置方式与其他渠道一致）。渠道全表
  见 `references/provider-catalog.md`。
- **控制台「添加渠道」区重排**：按获取门槛分组（国内直连/国际服务/自定义中转）
  的紧凑行式列表；已配置渠道显示「已配置 ✓」，"重新配置"可沿用现有密钥直接换 Key。
- **「生成任务」Tab 时间线增强**：连续同类事件折叠为组、行间耗时与跨度徽章、
  事件详情中文化、失败事件自动展开。
- **生成任务视图升级**（详见 [README](README.md) 控制台段，含界面截图）：卡片/
  后台表格双视图可切换（偏好自动记忆）；状态色彩语义（进行中蓝呼吸/完成绿/失败
  红）；停滞任务橙色警示（含"可能停在确认门"指引）；页网格 lane 徽标区分本地渲染
  （HTML/Mermaid）与 AI 渠道页；任务自 backend 合同签署起自动全局登记，workspace
  生成无需手动操作。
- 提示：更新技能后先执行 `python3 scripts/runtime_manager.py ensure` 刷新受管
  runtime，再启动控制台（`leo-ppt ui`），否则可能仍是旧版页面。
