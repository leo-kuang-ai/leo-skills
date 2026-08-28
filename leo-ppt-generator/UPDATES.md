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
