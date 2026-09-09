# 风格资产索引

此入口只导航，资产计数与成员由源文件生成。不要从文件名、目录位置或缩略图推断可执行性或验证状态。

## 查询入口

- [当前 catalog 指针](../../../catalog/current.json)：确定性指向当前 generation 的 registry。
- registry 中的名称、别名、稳定 ID 和 lifecycle 是唯一查询真值；执行期使用
  `leo-ppt style list --summary --filter <名称或别名>`，不依赖静态 generated Markdown。
- [设计体系](设计体系.md)、[风格路由](风格路由.md)：说明组合原则，不替代 registry 查询。
- [版式调度](../../../../references/layout-dispatch.md)：候选打分后仍须独立容量预检。

## 使用边界

点名优先于参考图，参考图优先于自动推荐。缺 golden 不等于不可点名，schema/索引通过不等于视觉验证通过。
参考池代表保留明确点名的旧版兼容调用，但必须披露 pool 角色；无完整 brief 的参考池只能浏览。
advise 可读取 current 指针及其指向的 registry，并披露快照版本；不得读取完整候选 brief 或运行脚本。
execute 按 [模板推荐合同](../../../../references/style-recommendation.md) 查询实际摘要，核对用户覆盖，选定后才读完整 brief。
生成目录缺失、根生成段损坏或已知过期时，advise 仅说明无法确认并给出“恢复有效索引后继续查询”；execute 使用独立源摘要查询，不重写安装目录。

## 维护

由 `scripts/capability_manifest.py --template-library --library-publish` 原子生成
generation registry 并更新 current 指针，再运行 `--library-check`。禁止手工修改
registry 或 current；历史 generated Markdown 只作为 retired source tree 的归档证据。
新增资产按 [扩展模板](style-extension-template.md) 校验；物理目录迁移、稳定 ID 和语义排名属于后续阶段。
