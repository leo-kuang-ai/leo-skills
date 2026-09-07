# 交付报告：Leo PPT 生成任务可视化控制台

- 日期：2026-09-07
- 流程：调研 → PRD（5 轮审查）→ 技术方案（5 轮审查）→ 开发 → 3 轮代码审查与修复 → 全面测试与浏览器验收 → 本报告
- 角色：需求总负责人（主会话）＋ 产品/UX 评审员、安全/a11y 评审员、架构评审员、代码评审员、测试验收（多角色子代理 + 真实浏览器）

## 1. 产品目标与结果

把"生成 PPT"从黑盒变成看得见的过程。交付：本地控制台新增「生成任务」Tab——

- **任务列表**：扫描 `${LEO_PPT_HOME}/projects/*/runs/`，状态徽标（进行中呼吸态）、页进度（含失败计数）、陈旧提示（>5 分钟无更新中性提醒）、URL 直达（`#run=<id>`）。
- **详情五视图**：流程条（步骤✔+耗时+当前态，无百分比）｜页网格（颜色+图标双编码，failed/timeout 从 timing.json 与 run.log 推断，recorded 渐进填充缩略图）｜事件时间线（尾窗+坏行计数+失败自动展开+加载更早分页）｜链路聚合（渠道×调用×尝试×tokens）｜交付卡（六门/失败回落/路径缩写复制）。
- **交互与礼仪**：lightbox（modal/Esc/键盘翻页）、3s/15s 轮询（隐藏暂停/恢复即拉/终态停+标题更新）、aria-live 三类关键播报、点击分流（recorded→预览 / failed→时间线定位）。
- **入口**：`leo-ppt ui`（新规范入口）与 `leo-ppt config ui`（兼容）同一服务。

## 2. 关键决策（多角色讨论产出）

1. **只读观察面红线**：页面不驱动/重试/取消 run——运行编排权属顶层 agent（SKILL.md 架构红线）。
2. **不用百分比**：业界共识（ChatGPT o1/Gamma/Bolt 调研）——阶段+耗时+页进度表达进展。
3. **数据契约以写侧源码为准**（架构评审 R2 核验纠正了三处 PRD 初稿假设）：image 路线页级仅二态落盘、失败从 timing/run.log 推断；页图真实路径在 slide_jobs 的 artifact 字段；editable 的 active 直接落盘。
4. **页图沙箱**：客户端只传 run_id+页码，服务端从 artifact 构造路径，resolve+is_relative_to+后缀白名单三层（实测穿越/symlink/大小写/多余段全拒）。
5. **存量安全修复**：首屏 `<script>` 注入转义（`<`→`\u003c`，安全评审发现的真实逃逸面）。
6. **渲染稳定性**：数据签名未变跳过 DOM 重建（防 3s 轮询缩略图重取风暴与点击打断——验收现场实证）。

## 3. 质量过程记录

| 阶段 | 轮次 | 关键发现与处置 |
|---|---|---|
| PRD 审查 | R1-R5 | R1 六项（过度承诺/短码定义等）；R2 八项（页状态数据源、点击分流冲突、"卡没卡"陈旧检测、URL 可寻址、指标可测化）；R3 可行性对齐；R4 八项（沙箱形状、注入逃逸、双重编码、lightbox 焦点、aria-live 礼仪、四条降级行为）；R5 终审一致 |
| 技术方案审查 | R1-R5 | R2 八项（三处契约不符硬伤：dispatched 事件不存在/artifact 后缀/jobs 键名；timing 为主；home 归属）；R3 安全终确认；R4 测试矩阵；R5 定稿 |
| 代码审查 | 3 轮 | E-R1 独立评审（含实测探针）10 项：9 修（坏 number 容错、DOM 重建风暴、editable 过滤形状、pages 段断言、stale 双源 mtime、run.log 第二失败源、按钮诚实性、5 条测试负路径）1 辨误（轮询死亡为误报）；E-R2/E-R3 复核通过 |
| 浏览器验收 | 双 run 场景 | 全视图 + lightbox + 过滤 + 播报 + 错误路径（run_not_found hash 回退）；现场发现 A-1（列表轮询打断点击）与 A-3（失败页定位回落）并修复复测 |

## 4. 验证证据

- 单测：`tests/test_runs_console.py` 19 例 + `tests/test_config_web.py` 58 例，合计 **77/77 绿**；JS 语法校验通过；`git diff --check` 干净。
- 沙箱矩阵实测：`..%2F` URL 编码穿越、`../` artifact、symlink 逃逸、绝对路径 artifact、`.PNG` 大写、`1x.png`、中间段非 pages、int 失败——全部 404。
- 注入转义实测：项目目录名含 `<script>` 时 served HTML 中仅 `\u003cscript\u003e`。
- 浏览器实测（Safari，隔离 home 双 run：进行中 12 页含 1 失败 1 超时 + 已完成带六门）：列表/详情/流程条耗时/12 格双编码网格/坏行计数/失败自动展开/链路 tokens 未记录容错/lightbox modal 焦点/Esc/过滤播报——全部通过（AX 树级证据）。
- 受管运行时已刷新（identity `efb04596…`），`leo-ppt ui` 即可用。

## 5. 限制与后续建议

- 合成 fixture 覆盖 generate/direct-editable 主干；upgrade-selected 的 delivery manifests 与 hybrid 视图仅契约级实现，待首个真实 run 回访。
- 性能口径（500 行无 >100ms 长帧）未做 DevTools Performance 录制（AX 验收路径无 Performance 面板），以签名跳过 + 尾窗分页的设计保证兜底；建议首个真实长 run 时补测。
- 本机暂无真实 run（projects 下 runs/ 为空），首屏真实数据体验待用户下一次生成时自然验证。
- 已知预存在失败（非本功能）：`tests/test_channel_catalog` 1 例属并行会话 param_compat 批次。

## 6. 产物清单

- 文档：`docs/prd/2026-09-07-leo-ppt-run-visualization-prd.md`、`docs/plans/2026-09-07-004-feat-run-visualization-console-plan.md`、本报告
- 代码：`runtime/src/leo_ppt_generator/runs_console.py`（新）、`runtime/src/leo_ppt_generator/config/web.py`（扩展）、`runtime/src/leo_ppt_generator/config/assets/config-ui.html`（双 Tab）、`runtime/src/leo_ppt_generator/cli.py`（`ui` 入口）
- 测试：`tests/runs_fixture.py`（合成 run 工厂）、`tests/test_runs_console.py`、`tests/test_config_web.py`（扩展）
- 文档同步：CHANGELOG.md（Added 条目）、SKILL.md/README.md/provider-catalog.md（控制台入口与说明）

## 7. 迭代轮 2：多视角专家评审与优化（PM/运维/架构）

### 评审与修复矩阵

三路独立专家评审（24 项发现）+ 运维复评（2 项追加）+ 浏览器现场验收（2 项追加），全部处置：

| # | 来源 | 问题 | 处置 |
|---|---|---|---|
| PM-1 | 产品 | 时间全 UTC 原串、纯秒数耗时不可读 | fmtClock/fmtDur 本地化；详情"开始于 16:00 · 总耗时 10 分 21 秒" |
| PM-2 | 产品 | **流程条耗时恒 null**（读 command/duration，写侧是 stage/duration_seconds，fixture 同错掩盖） | 读侧改生产键 + fixture 改真实 writer 键（契约对齐） |
| PM-3 | 产品 | 死进程在列表仍"呼吸" | 列表 stale≥5min → 停呼吸 + "⚠ N 分钟无更新" |
| PM-4/5 | 产品 | 进度纯文本混排 / 无筛选 | 三段进度条（aria progressbar）+ 状态筛选 chips 带计数 |
| PM-6 | 产品 | 交付卡埋底 | 终态交付上移至流程条后（I-2 修正函数位置后浏览器复验） |
| PM-7 | 产品 | 过滤无提示且被轮询重置 | 过滤提示条 + "显示全部" + runs.filterPage 重放 |
| PM-8 | 产品 | 空态无命令/错误吞刷新 | 文案补 run create；catch 保留头部+重试 |
| OPS-1/ARCH-2 | 运维/架构 | 每轮 13 次全量目录扫描（~195 文件读/s） | RunScanner 线程锁 + 1.5s TTL 索引缓存 + jobs (mtime,size) 缓存 + clock/monotonic 注入 |
| OPS-2 | 运维 | 页图 no-store 全尺寸重传（GB/时） | ETag(sha256 前 8 字节) + If-None-Match 304 + private,max-age |
| OPS-3 | 运维 | events 全量重读 + **翻页跳段 bug**（before_seq 取最旧 N 条） | 翻页改紧邻窗口（含测试）；尾读 seek 优化 defer |
| OPS-4 | 运维 | 零访问日志、异常无上下文 | log_message 带 method/path/status；runs 路由 500 兜底 + traceback 带 path |
| OPS-5 | 运维 | runtime 切换后旧进程首页 500 半残态 | asset 首次读取后模块级缓存 |
| OPS-复评 | 运维 | 惊群 / jobs 缓存无界 / ETag 跨重启不稳 / 日志缺状态码 | 持锁扫描、每 path 单版本驱逐、sha256、日志带 code（全部采纳） |
| ARCH-4 | 架构 | 契约漂移零防护（三份人肉副本） | ROUTE_STEP_SEQUENCES ↔ 写侧 ROUTES 对齐测试 + EVENT_LABELS ↔ 写侧 kind 源码提取对齐测试 |
| ARCH-5/7/8 | 架构 | clock 不可注入 / jobs 路径重复 / py3.9 死代码 | 全部清理 |
| ARCH-1/3 | 架构 | web.py 职责泛化 / 单文件阈值 | docstring 纠偏；拆包/拆 JS defer 触发条件已记录 |
| I-1/I-2 | 浏览器验收 | 阶段名套"第 X 页"模板 / 交付上移未生效 | 均修复并复验 |

### 验证证据

- 回归：**80/80 全绿**（runs_console 22 + config_web 58），JS 语法通过，git diff --check 干净。
- 性能探针（46 run 场景）：列表/详情冷扫 ~0.4ms（远低于 300ms 指标）；12 页图冷/热均 ~0.6ms（一轮轮询 13 扫 → 1 扫）。
- 浏览器复验：筛选 chips 计数、本地时间、route 中文、陈旧提示（真实触发 7 分钟）、终态交付第一屏（deck 路径缩写 + 六门 ✔ + 复制）、时间线阶段名/页号显示、304 缓存（测试证明）。
- 运维复评结论：四项必修全部可验收；两个追加一行修复已随批落地。

### Defer 台账（带触发条件）

- 拆 console 包：第三个 Tab 域或 web.py >900 行；拆前端 JS：1500 行/第三个 Tab/JS 复用需求（当前 1431 行）。
- events 尾部 seek 读取：万行级真实 run 出现时；GET 读端点 cookie token 加固：多用户主机场景；getpass 线程回收、unreadable 计数：单用户本机暂缓。
- 阶段耗时/失败推断的命令名启发式：写侧 timing 落显式 stage 字段时根治。

