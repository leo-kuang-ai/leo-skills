# 表达优先重构自主收口执行表

本表执行 004 原方案及本会话 U1–U13 验收要求，不修改原方案，不降低发布门。
本轮起点为 `7d9ae01d18c0ef4085ca18d4354a28ec01b00acb`；工作树和 owner 基线见
`expression-first-resume-baseline.json`。5 个宿主缓存文件属于外部既有改动，保留且不提交。
仅写 `leo-ppt-generator/`，根 `CHANGELOG.md` 为用户明确指定的例外。串行执行；不修改 generated mirrors。

## 执行顺序与验收

| 顺序 | 单元 | 自主工作 | 必须取得的证据 |
| --- | --- | --- | --- |
| 0 | 基线、U7-A/U12 前置调查 | 回读完整方案与当前源码；逐行记账；旧来源按 SHA-256 检查归档/Git；冻结旧链来源与环境 | dirty owner 基线、来源审计；旧账本只作 provenance，不冒充当前迁移 plan |
| 1 | U1 | 表达 authoring/schema/编译器/冲突与事实落位；移除所有活动 v1 及角色映射分叉 | 正负例、role/relation parity、v1 残留扫描 |
| 2 | U2 | 独立 relation oracle、owner/probe/evidence 资格；显式点名同门；容量、依赖和 evidence 漂移拒绝 | 正反 probe、实际输出 hash、环境 fingerprint；无证据不能晋升 |
| 3 | U3/U10 前置 | 统一 hard-qualified pool；完整 pairing identity；删除旧 binding 消费；最小 page invalidation | 双 lane、旧/缺/混用/篡改摘要负例；真实内容保真与容量验证 |
| 4 | U4 | 唯一 route→pipeline→RunIndex；冻结 selection；原子 generation/pointer/pins；双 lane adapter | 中断恢复、幂等/冲突、空 deck、compose 重选、实际 HTML 导出 |
| 5 | U5 | 封闭 op、逐 anchor/slot 类型范围与 scope；最多 3 次；内容/主题不可变；curation | canonical hash 保持、跨 run/越界负例、同一 qualification/materialization 链 |
| 6 | U6/U12 | 消除文件存在即通过；四 evidence channel；机器门、receipt/file 一一绑定；R-85 与视觉回放工具 | HTML/image/visual/用户收益分层；缺证据 fail closed；独立基线与 oracle |
| 7 | U7-B/U13 | 用当前 canonical 重冻 preview；单一五阶段 CLI；独立 staging 完整 shadow tree | source/dirty/closure/mapping/target/allowlist/plan digest；delivery 不变 |
| 8 | U8 | 位置合同、LibraryContext、v2 catalog、execution/diagnostic 隔离、三段 generation DAG | 新目录真实 catalog、同代不可变、错误码、并发/中断、recipe views |
| 9 | U9/U10 | 所有消费者与安装切换、完整 execution pairing 与 image recipe；旧 alias/fallback 清除 | 固定 roots closure 未分类和活动旧引用归零；copy/link bundle |
| 10 | U11 | verified receipt、maintenance 所有消费者互斥、逐文件 CAS、journal 恢复、原子 current、精确 cleanup、convergence | drift/类型/symlink/中断负例；实际交付与 staging 全部摘要一致 |
| 11 | 全量交付审计 | 依次运行 compileall、schema、lint、表达/运行/提案、迁移、quality、全量 unittest | 每条命令/退出码/日志/manifest；U1–U13 completion matrix 无占位 gap |

本会话已授权本地提交，独立单元独立 commit；提交不表示开发或验证全部通过。
没有 push/PR 授权，保持本地。历史混合提交不重写。

## 已确认的修正

- 旧 ledger 891 项：651 项可从当前归档完全按 hash 找回，8 项可从 Git 找回；
  157 项原位 hash 一致，75 项原位已变更。见 `legacy-source-recovery-audit.json`。
  原“源丢失无法恢复”阻塞已被证伪；75 项不得用旧字节覆盖当前内容。
- 当前 catalog 仍是 v1 路径和 schema，`library-check` 通过不能写成 U8 v2 完成。
- 当前全量日志 2064 tests、4 failures/4 errors 只作起点；修复后需重跑。
- `scorecard` 文件存在、普通观测事件不能证明 schema/事实/真实导出/视觉通过。
- 目前五阶段迁移 helper 没有完整 receipt/hash/根/锁/恢复闭环；5 个 focused 测试不证明 U11 完成。

## 外部依赖处理

自主完成实现、回归、真实本地 HTML、历史来源恢复、可复跑 image/replay 工具。
真实 image Provider 调用须使用已授权的渠道及调用范围；先查配置与宿主能力，只输出脱敏状态。
付费范围未确定时只阻塞该调用，不阻塞独立开发。
用户差页优先查找已有 run；没有可定位输入时保留未观测，不伪造用户验收或收益。
U6-A、预迁移价值门未通过时不实际发布/清理 delivery，但继续开发和验证工具本身。
