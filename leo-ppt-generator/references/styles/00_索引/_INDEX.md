# 风格资产索引

此入口只导航，资产计数与成员由源文件生成。不要从文件名、目录位置或缩略图推断可执行性或验证状态。

## 查询入口

- [名称与别名](../generated/by-name-alias.md)：按名称定位；共享别名保留全部命中。
- [家族浏览](../generated/by-family-001.md)：只列普通 style，pool 不混入家族候选。
- [分类计数](../generated/counts.md)：区分 style、变体、pool、layout、axis、rule 与参考资料；不是已验证风格数量。
- [设计体系](设计体系.md)、[风格路由](风格路由.md)：说明组合原则，不替代派生目录。
- [版式调度](../../layout-dispatch.md)：候选打分后仍须独立容量预检。

## 使用边界

点名优先于参考图，参考图优先于自动推荐。缺 golden 不等于不可点名，schema/索引通过不等于视觉验证通过。
参考池代表保留明确点名的旧版兼容调用，但必须披露 pool 角色；无完整 brief 的参考池只能浏览。
advise 可按需读取上述生成 Markdown，并披露快照版本；不得读取 catalog JSON、完整候选 brief 或运行脚本。
execute 按 [模板推荐合同](../../style-recommendation.md) 查询实际摘要，核对用户覆盖，选定后才读完整 brief。
生成目录缺失、根生成段损坏或已知过期时，advise 仅说明无法确认并给出“恢复有效索引后继续查询”；execute 使用独立源摘要查询，不重写安装目录。

## 维护

由 `scripts/capability_manifest.py --style-index --index-out references/styles/generated` 生成随包资料，再运行只读 `--check`。
禁止手工增加成员行或修改 counts。旧 capability-manifest 的 briefs 是兼容计数，不应代替此处的分类 counts。
新增资产按 [扩展模板](style-extension-template.md) 校验；物理目录迁移、稳定 ID 和语义排名属于后续阶段。
