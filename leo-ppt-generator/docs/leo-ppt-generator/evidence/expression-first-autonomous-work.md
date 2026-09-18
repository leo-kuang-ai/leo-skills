# 表达优先重构自主收口执行表

本表执行 004 原方案及本会话 U1–U13 验收要求，不修改原方案，不降低发布门。
本轮起点为 `7d9ae01d18c0ef4085ca18d4354a28ec01b00acb`；工作树和 owner 基线见
`expression-first-resume-baseline.json`。5 个宿主缓存文件属于外部既有改动，保留且不提交。
仅写 `leo-ppt-generator/`，根 `CHANGELOG.md` 为用户明确指定的例外。串行执行；不修改 generated mirrors。

当前状态以本文件末尾的 2026-09-16 恢复记录和 `expression-first-completion-matrix.json` 为准。
早期轮次的缺口与测试数是历史快照，不能继续作为当前实现状态。

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

## 2026-09-14 continuation audit

- 提交 `9c16a88`：冻结表达证据、双 lane pipeline、资格与 recipe/provenance 基础。
- 提交 `cb1ee91`：收据仅消费 committed input generation；真实 HTML 产物、模板漂移、缺 pointer、旧/缺/混用 binding 摘要均 fail closed；62 个 receipt/quality/pipeline focused tests 通过。
- 提交 `1770709`：刷新 completion matrix，引用当前有序验证结果。
- 有序验证证据：`docs/leo-ppt-generator/evidence/expression-verification-integration-v3/verification.json`；compileall/schema/lint/quality 通过，expression-consumers 退出 1，migration 退出 1，全量 2135 tests / 58 failures / 64 errors / exit 1，`source_stable=true`。
- 该历史轮次尚未完成：U5 proposal 生产接入、U6 真实 Provider/配对视觉/用户差页，以及 U7–U13 v2 catalog 与完整迁移。U5 接入和部分 v2/迁移工具已在后续轮次实现；真实验证仍按最新矩阵记录。
- 外部 dirty 保护文件仍未修改；未 push、未创建 PR。

- 旧 ledger 891 项：651 项可从当前归档完全按 hash 找回，8 项可从 Git 找回；
  157 项原位 hash 一致，75 项原位已变更。见 `legacy-source-recovery-audit.json`。
  原“源丢失无法恢复”阻塞已被证伪；75 项不得用旧字节覆盖当前内容。
- 当前 catalog 仍是 v1 路径和 schema，`library-check` 通过不能写成 U8 v2 完成。
- 当前全量日志 2064 tests、4 failures/4 errors 只作起点；修复后需重跑。
- `scorecard` 文件存在、普通观测事件不能证明 schema/事实/真实导出/视觉通过。
- 该轮次的五阶段迁移只有局部 helper；后续已经替换为正式五阶段 owner，但不能把新增文件事务测试外推为真实 U11 发布完成。

## 外部依赖处理

自主完成实现、回归、真实本地 HTML、历史来源恢复、可复跑 image/replay 工具。
真实 image Provider 调用须使用已授权的渠道及调用范围；先查配置与宿主能力，只输出脱敏状态。
付费范围未确定时只阻塞该调用，不阻塞独立开发。
用户差页优先查找已有 run；没有可定位输入时保留未观测，不伪造用户验收或收益。
U6-A、预迁移价值门未通过时不实际发布/清理 delivery，但继续开发和验证工具本身。

## 2026-09-15 U4/U5 续作

- HEAD 基线 `176b6f3b6c924ab28ce83d09fd34149dae2e1c33`；307 条 dirty path 与 owner/hash 见 `continuation-2026-09-15-resume-baseline.json`。
- U4 原子页发布、旧 prepare 消费协议、预览缓存与补充输入收据已落地；U5 已接入有限候选池、任务私有取证、冻结与重放。
- `u5-qualified-materialization-2026-09-15.log`：69 tests / exit 0；`u4-u5-consumer-final-2026-09-15.log`：63 tests / exit 0。均为局部机制及真实 HTML 验证，不代表真实任务、image、视觉、发布或全量通过。
- 本轮新增 source 尚未提交；无 push/PR。U6 与 U7–U13 仍按矩阵保留 required gaps。

## 2026-09-15 迁移恢复与当前证据续作

- 恢复基线为 `176b6f3b6c924ab28ce83d09fd34149dae2e1c33`；修改前记录 361 条 dirty path、owner、类型与摘要，见 `continuation-2026-09-15-transaction-baseline.json`。5 个范围外文件逐项 hash 未变。
- U6 补齐 A 全集/B 代表集与独立执行前缀、拒答持久化与真实重算、完整回放附件和成对收益观测工具；缺真实数据仍为 not_run。
- U8 落地正式 v2 schemas、位置合同、LibraryContext、三段摘要与同代派生重算。v2 整库构建、bundle 安装、模板解析及实际 HTML pipeline 已验证。delivery 默认库仍为 v1，不能声明完成切换。
- U11 修正 cleanup 回滚后的重发与 maintenance 时序。最终收据必须先持久化；断点重试重核后再解除维护。正式迁移 schema 封闭操作与字段，final verify 重核完整收据链、owner、价值门、catalog 和文件摘要。
- `u9-consumer-bindings-fixed-2026-09-15.log`：21 tests / exit 0；`u8-u9-u11-bundle-v3-2026-09-15.log`：19 tests / exit 0；`u6-u13-contracts-2026-09-15.log`：44 tests / exit 0。包含真实文件、浏览器及 v2 库消费；不构成真实 Provider/视觉/高层发布闭环。
- 真实仓库 U7-A preview 位于 `.migration-work/2026-09-15-current-preview/migration-plan.json`：5,437 来源路径、4,591 目标路径、846 删除候选。无价值前置时 stage 实际拒绝，shadow 未创建；后续证据变化后，该计划只保留为当时合同基线。
- closure 覆盖固定 10 roots：`unclassified_hits=0`，但 `active_legacy_hits=305`，涉及 109 个文件。完整逐命中列表见 `consumer-closure-2026-09-15.json`；仍需切换旧 reader、fallback、alias、fixture/eval 和路径。
- 旧清单 891 项全部按 SHA-256 找回，见 `legacy-source-recovery-reverified-2026-09-15.json`。另从 `710846e20a900e02bd5349629015d6e3bd441510` 恢复 4,290 个历史源文件，旧 pack→binding→HTML 实际导出 2560×1440 PNG，退出 0、源字节未变，见 `u12-historical-html-runtime-2026-09-15.json`。使用历史测试材料，尚未建立完整 R-85/配对视觉基线。
- 当前资产五关系各正反一张，共 10 张 HTML PNG 已重新采集并逐条重核，见 `u2-current-probe-receipts-2026-09-15.json`。HTML 活动资格 provisional=5、unverified=35、rejected=8；image unverified=5、rejected=19；publication-qualified=0。
- Provider 已配置且凭据可用，当前选择 qianxing/gpt-image-1，状态 configured_unverified。不能再写成缺配置；实际缺口包括独立 image 输出检测实现、真实调用/导出、U6-A/B、用户差页及收益观测。
- 第一轮有序验证 `expression-verification-2026-09-15-v2-migration/verification.json`：compile/schema/三 lint/migration/quality 退出 0，expression-consumers 12 failures/6 errors；全量 2,177 tests、50 failures、28 errors、exit 1，source_stable=true。当前证据刷新后的最终有序验证见 `expression-verification-2026-09-15-live-evidence/verification.json`，其终态由 completion matrix 更新。
- 新增 `references/template-library-migration.md`，同步回放合同说明。所有新增源变更已登记根 CHANGELOG；本轮未提交、未推送、未创建 PR。U1–U13 均保持 partial，未调用 goal complete。

## 2026-09-15 准入、OCR 与发布事务续作

- 准入阶段基线为 `continuation-2026-09-15-admission-baseline.json`；接续发布事务前再次记录 736 个 dirty paths，见 `continuation-2026-09-15-journal-baseline.json`。5 个范围外文件与前次基线摘要一致。
- U2/U6 局部视觉评审不能独自取得 publication-qualified；正式晋升重算 U6-A、封闭附件树及同一能力证据。附件内 execution library 使用相对路径，搬移后仍可重核；真实正向晋升尚缺。
- image 正反探针必须绑定相同 Provider、模型和合同；候选与冻结重验核对本次合同摘要。首批 6 次真实调用授权仍待答复，本轮实际付费调用为 0。
- U4 OCR 使用已验证 image provenance 和冻结必现文字判域；可选 sources、overlay/composite 字段不能豁免。HTML/image 统一在页事务内保存 provenance；已迁移旧 OCR 手写 run 测试，保留真实 adapter 门测试及冻结 HTML CLI 正例。
- U7 固定 closure 纳入根 CHANGELOG，共 11 个扫描根；最新 `consumer-closure-admission-2026-09-15.json` 为 `unclassified_hits=0`、`active_legacy_hits=287`，所有活动命中均在目标包内。旧源已按字节恢复 891/891，不能再将缺源列作当前阻塞。
- 新一轮完整有序验证 `expression-verification-2026-09-15-admission-final/verification.json` 由既有进程持续执行，终态以 completion matrix 为准；不能引用上一轮 2,195 tests、4 errors 的结果充当本轮通过。
- U11 当前源码已复现缺少 transaction id、base revision、journal generation 及确认 marker，见 `u11-journal-identity-red-2026-09-15.log`（exit 1）。继续扩展现有 `library_migration.py`，不新建第二套迁移器。
- 目标服务当前返回 `blocked`，本轮未调用 goal complete，也未声称已恢复 active。正式 U6-A/B、双 lane、R-85、用户收益及高层 publish/cleanup/convergence 仍缺必要证据。

### 本轮 U8/U11 落地与验证

- `library_migration.py` 统一派生 transaction id、base revision，并递增 journal generation。prepared/current-switched 标记分别落盘，目录 fsync 失败直接阻断；签发收据前重核 delivery。发布凭证在 `publications/<transaction_id>/<journal_generation>/` 按代保存，根收据 CAS 更新；cleanup/final 拒绝陈旧或未确认的凭证。
- 真进程分别在 prepared、普通文件替换、current 替换、确认前与确认后硬退出；测试核对 maintenance 保留、当前字节、恢复与同代幂等。恢复后的旧收据失效，历史归档保持不变。伪造 transaction、base、generation 或越出 allowlist 的 journal 不能恢复文件。
- 串行检查发现 U8 的缓存旁路：真实 v2 catalog 预热后 maintenance 生效仍返回索引。由 U8 owner `AssetResolver._require_available` 修复，在 builtin/user 缓存读、摘要及 freeze 入口重核；未生成额外快照。发现和修复证据见 `u11-journal-inline-review-2026-09-15.json`、`u8-maintenance-cache-red-2026-09-15.log`；这是单 Agent 检查，独立评审未运行。
- `u8-u11-journal-final-2026-09-15.log`：45 tests / exit 0。包含真实文件事务与实际 v2 catalog，不能升级为完整高层迁移或真实 image 验证。
- 本轮源码 wheel 在 `.migration-work/journal-wheel/` 隔离构建与安装。177 个应打包文件全覆盖，逐文件摘要相等；安装后实际运行 37 项事务/catalog 回归，exit 0。详见 `u8-journal-wheel-2026-09-15.json`、`u8-u11-installed-wheel-2026-09-15.json`。项目环境缺 build/pip，使用现有 uv 的隔离构建，没有修改项目虚拟环境。
- 当前五组 HTML 正反 evidence 均重核为 provisional，publication-qualified=0，见 `u2-current-probes-journal-2026-09-15.json`。closure 重扫仍为 active=287、unclassified=0，见 `consumer-closure-journal-2026-09-15.json`。
- 旧源重核 891/891、unresolved=0，见 `legacy-source-journal-reverified-v2-2026-09-15.json`。第一次检查只覆盖工作树路径，漏读 83 个有明确 revision/path 的 Git 对象；v2 重读对象字节后通过，初次记录的 unresolved 不代表真正缺源。
- 前一轮 `expression-verification-2026-09-15-admission-final` 已取得 2,206 tests / exit 0 / source_stable=true。新增事务和缓存修复的最终有序运行是 `expression-verification-2026-09-15-journal-final`，必须收取终态后更新矩阵；不把前一轮结果当作当前源码的通过证据。
- 最终已收取 session `81917` 的进程终态：有序验证全部退出 0；全量 2,217 tests、0 failures、0 errors，exit 0，source_stable=true。日志摘要及每步命令见 `expression-verification-2026-09-15-journal-final/verification.json`；JSON/Markdown 完成矩阵全部行已更新为本轮证据，U1–U13 仍保持 partial。没有真实 Provider/视觉/正式发布证据的项继续保留 required gaps。

## 2026-09-16 操作期互斥、当前证据与最终验证

- 写入前基线为 `continuation-2026-09-16-maintenance-baseline.json`：HEAD `176b6f3b6c924ab28ce83d09fd34149dae2e1c33`，749 条 dirty（106 tracked、643 untracked），逐条记录 owner/type/hash；五个范围外文件保护不变。
- U11 将入口瞬时检查扩展为完整操作期互斥：库目录共享 flock 覆盖 route/pipeline/render、resolver/catalog、manifest/probe、style save/import/adopt 和 final receipt 复核；迁移取得独占目录锁后才写 maintenance。只读安装不创建共享锁文件；真实争锁、marker 前窗口和硬退出行为已验证。正式高层迁移仍未完成。
- U8 修复相对 library/home 根造成 owner 路径双前缀的问题；红例 exit 1，修复后 exit 0。当前 wheel 在 `.migration-work/maintenance-wheel-2026-09-16/` 隔离构建/安装，177 个必需文件字节完全一致，安装后 44 项实际事务/catalog 测试 exit 0，已核对模块来自安装根。
- 渲染 owner 改变后旧 HTML 收据被当前 verifier 正确判为 `evidence_environment_stale`；五关系各正反一张重新实际导出，共 10 张 PNG，附件 hash 重核后更新活动索引。五组均 provisional / `visual_review_not_run`；总探针 exit 1，image 仍 blocked，不能宣称 publication-qualified。
- Provider 当前仍为 qianxing、fixed、configured_unverified；本轮付费调用 0。准备当前环境下三关系正反 6 份输入，见 `u2-image-prepared-inputs-v5-2026-09-16.json`；comparison/trend 仍缺 image recipe，正式 U6-A/B、R-85、三册同环境配对视觉与用户差页未运行。
- 当前 closure 重扫 `active_legacy_hits=287`、`unclassified_hits=0`。工作树/归档/Git blob 旧源重核 891/891、unresolved=0；缺源已解除，不把它继续列作阻塞。
- 真实 CLI U7-A preview exit 0，5841 来源、4995 目标、846 删除候选；缺预迁移价值门时 stage exit 2、shadow_created=false。计划摘要 `02eef3ae6268b61352c8d1ead62fca0d4d3fefcdef0dbdec1921d2db8842670c`；后续文档写入改变 dirty，该计划只作当时基线，不能沿用为 U7-B 快照。
- 完整有序验证已取得终态：`expression-verification-2026-09-16-maintenance-final/verification.json`，compileall/schema/三项 lint/expression/migration/quality/full-suite 全部 exit 0；全量 2226 tests、0 failures、0 errors，source_stable=true。完整日志 SHA-256 `cabfc22d3abfc8616c6cf0315c736398e69b419f80f8af2ad54c3407632a34a2`。
- 单 Agent 串行检查见 `u11-maintenance-inline-review-2026-09-16.json`，degraded / Not ready；未宣称独立评审或跨模型审查通过。现有局部和全量机制测试不能替代真实 Provider、视觉、用户收益及正式发布。
- JSON/Markdown 完成矩阵已同步当前文件、符号、命令/退出码、日志和收据；所有 U1–U13 仍 partial，required gaps 全部保留。剩余消费者切换和正式 stage/publish/cleanup/convergence 依赖真实预迁移价值与 U6-A 证据；本轮未 commit/push/PR，未调用 goal complete，goal 工具仍为既有 blocked 状态。
- 正式 workflow helper 只接受 Git 根，包根探针为 `target-repo-not-found`；未向范围外 `.spec-first` 写入。项目原生 manifest/矩阵保留全部实际验证；formal closeout 未运行，见 `maintenance-workflow-boundary-2026-09-16.json`。

## 2026-09-16 表格 image recipe、安装态 regime 与验证闭环

- 修改前基线为 `continuation-2026-09-16-table-recipe-baseline.json`：836 dirty（109 tracked、727 untracked），逐路径 owner/type/hash 已记录；HEAD 未变。
- U2/U3/U10 新增 `builtin:recipe:p25-spec-table`，补齐 comparison/trend；schema 只允许 rows/columns/rows.*.* 路径。预编译与最终投影共用 layout owner 容量门，拒绝缺字段、错形、来源冲突及容量越界，保留事实、未知值与顺序；标题不误用 cell 容量。
- U1/U9/U11 修复 wheel 安装下 regime 源目录定位失效，改用正式 bundle 定位；每次持共享锁读取当前字节，解析缓存只按字节、返回深拷贝，库切换/漂移/维护均重核。
- 本轮最新探针 `expression-first-output-v12-table-recipe` 实际导出五关系各正反，共10张HTML PNG，全部 provisional；总probe CLI exit 1 / blocked。10/10 PNG与前轮同用例字节相等，只证明这些样例未变。
- 最新 `u2-image-prepared-inputs-v7-2026-09-16.json` 含五关系10份输入，各owner gaps为空。此前三关系6份、comparison/trend缺recipe的记录已被本轮接续；真实Provider调用仍0，首批6次付费范围未答复，不能因新增准备扩大调用。
- 最新wheel `.migration-work/table-recipe-wheel-v2-2026-09-16/` 的177个包文件与源码/installed逐字节一致；安装后7项regime/recipe测试exit 0，所有已加载包模块来自installed根。上一轮44项安装态事务/catalog为历史，不外推为本轮安装态全量。
- 中间失败原样保留：final-v1因layout manifest漂移中止；final-v2全量2230项、2 failures、exit 1，修复复制/链接安装的实体数并核对实际recipe解析；旧wheel7项、5 errors实际定位regime问题。
- 最终session84773已退出0：`expression-verification-2026-09-16-table-recipe-final-v3/verification.json`，compileall/schema/三lint/expression/migration/quality/full-suite均exit 0；全量2232 tests、0 failures、0 errors，source_stable=true。完整日志SHA-256 `4768f3fc69430b8054b9f2d253f4404eb67ad93d7de16449badbdce61fa7774a`。
- closure新扫描 `consumer-closure-table-recipe-2026-09-16.json`：active_legacy_hits=287、unclassified_hits=0，全部固定根存在。本轮未开始正式U7-B/U13或publish/cleanup/convergence。
- 串行检查 `table-recipe-inline-review-2026-09-16.json` 为degraded / Not ready；11个文件摘要与当前内容相等，不冒称独立review。formal helper边界保持上轮记录，未写范围外.spec-first。
- 完成矩阵JSON/Markdown已同步当前逐行文件、符号、命令/退出码、receipts/logs和required gaps；全部U1–U13仍partial。真实Provider、U6-A/B/R-85、三册配对视觉、用户差页与完整迁移发布仍未完成。本轮未commit/push/PR、未调用goal complete。
