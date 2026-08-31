# 专家5:PPT 素材生态与交付分发调研报告

- 被增强对象:`leo-ppt-generator`(输入端:用户自备材料 + validate_assets + 三级标注 + sources-manifest;交付端:PPTX/逐页图/notes/failure report + 讲稿导出 + 交付收据 + DELIVERY-GATE)
- 调研赛道:全流程自动化 / 热点选题 / 采集 / 多平台分发(8 组分析报告 + 4 项目源码深读)
- 日期:2026-08-31

## 一、赛道优势总结(分模块,附源码证据)

### 1. 素材库 / 资产库(Beav 为代表)

- **目录式素材库 + meta.json 投影**:`knowledgeLoader.ts` 把每条采集素材存为独立目录(`knowledge/redbook/<id>/meta.json`),封面本地路径经 `localAssetManager.toAppAssetUrl` 统一解析;知识条目按 note/video 类型统一为 `WanderItem`。
- **grep+vector 混合检索 RRF 融合**:`knowledgeRetrieval.ts` 用 `grep -ric` 按命中数排名关键词结果,与向量结果做 Reciprocal Rank Fusion(k=60),注释明确这是"Agentic Retrieval 替代重型 RAG"的轻量路线。
- **媒体资产 catalog**:`mediaLibraryStore.ts` 用 `catalog.json` 登记 `MediaAsset`(source: generated/planned/imported、provider/model/aspectRatio/relativePath),**prompt 归一化去重**(`normalizePrompt` 压空白后作键),generated/imported 分目录,可绑定稿件路径(`boundManuscriptPath`)。
- **主体库**:`subjectsLibraryStore.ts` 把人物/商品主体(图组+声音+视频+标签+属性)登记为可复用 `SubjectRecord`——同一发言人头像、产品照跨稿件复用。
- **启示**:leo 的 profiles/(偏好)、brands/(VI)已是用户档案通道,但**用户业务素材(图片/图表/数据/引用)没有跨 run 库**;sources-manifest 是单 run 机器投影,每次任务的素材一次性消费。

### 2. 多媒体输入(AI-Media2Doc / Video_note_generator)

- **ASR 异步任务模型**:`backend/routers/audio.py` 用"POST 创建任务 → GET 轮询"两段式,返回 utterances 携带 **毫秒级 start_time/end_time**——时间戳是后续一切对齐的锚。
- **时间戳预处理协议**:`VideoToMarkdown/index.vue` 把转写段落渲染为 `[mm:ss - mm:ss 时间范围秒数:(Xs-Ys)] text` 后再喂 LLM,使模型能"看见"时间、据此插标记。
- **`#image[秒数]` 占位标记协议**:LLM 在关键内容处输出 `#image[20]`(单独成行),前端 `captureVideoFrame` **确定性回填**视频帧;时间超出视频时长(TIME_OUT_OF_RANGE)则**静默移除标记并记日志**;MP3 文件保留标记不截图。这是"模型输出结构化占位 + 确定性渲染回填 + 越界降级"的完整协议——与 leo TF-2(留白版式+overlay_text 逐字贴字)同构。
- **风格模板可自定义**:`markdownService.ts` 按 localStorage customPrompts 覆盖 DEFAULT_PROMPTS,风格(小红书/公众号/笔记/导图)只是 prompt 变换层。
- **启示**:leo 输入端只认文本/图片/PDF;会议录音→汇报 PPT 是真实高频场景,时间戳锚定能让"引用"级事实回溯到录音原点。

### 3. 热点 / 数据聚合入口(last30days / newsnow / DailyHotApi / 60s / AIWriteX)

- **三腿发现协议 + 置信度地板**:last30days SKILL.md 的 discover 流程为 leg1 sweep 提名(离线 FTS)→ leg2 judge(逐提名读 bundle 证据)→ leg3 finalize+angles;**"Nothing solid this window" 空结果是合法终态**,禁止重试或编造话题——与 leo unknown 求证纪律同构。
- **engagement 证据权重**:cluster-first 输出按跨平台叙事簇打分,score/items/sources + uncertainty 标签(single-source/thin-evidence);Reddit 顶数、X 点赞、Polymarket 真金赔率作为强信号,top comment 逐字引用带票数。
- **受众 register 模板**:default/exec/dev/creator/eli5 五档只改综合指令不改数据。
- **多源降级链**:AIWriteX `hotnews.py` 同时对接知微数据与 tophub 两套热榜源,单源失败自动切备源,平台映射表驱动。
- **启示**:行业汇报需要市场数据,leo 现状只能等用户提供。归我管的是**通道与回溯标注**(源 URL+抓取时间戳入 manifest),研究方法论归专家1,选题判断 leo 不做。

### 4. 导出管线(elog / html-anything / write-then-publish / xiaohu-wechat-format)

- **写作端×发布端解耦**:elog monorepo 以 `sdk-notion/yuque/feishu/flowus/confluence/wolai`(下载端)× `sdk-halo/wordpress/outline`(发布端)× `plugin-adapter` + 图床插件(`plugin-img-r2/b2`)自由组合,core 是统一 download→transform→publish 管线——**一份内容多目标导出的架构范式**。
- **同一正文双输出**:write-then-publish 同一 Markdown 一键切换小红书卡片(1728×2304 自动分页)与公众号长文;html-anything 用 juice 内联 CSS 出公众号可粘贴 HTML + 2× PNG。
- **对 leo 的关键前提变化**:P1 搁置 handout 的理由是"渲染依赖属 M1 渲染 lane 后续"——**M1 已合入**:`render-contract.md` 定义了 Playwright 确定性渲染(`?leo_render=1` 禁动画、`data-leo-ready` 就绪信号、读 PNG 头断言实际像素、`<out>.render.json` provenance sidecar 带 sha256),known-issues 证实 HTML 链路像素 diff 0.000%;`social-card-specs.md`(guizang 抽取)已备好三画板规格但标注"实验性,SKILL.md 路由与 eval 门禁接入属后续批次"。**搁置理由已消除,导出通道现在做成立**。

### 5. 定时 / 无人值守(xhs_ai_publisher / AIMedia / Beav)

- **任务模型**:`database_manager.py` 的 `scheduled_tasks` 表(schedule_type once/循环、next_run_time、run_count、is_active)+ `publish_history`(status pending→…);main.py 以信号驱动:task_execute_requested → enqueue → handle_task_result 回执,started/completed/failed 三态分离。
- **防重入**:Beav `backgroundCronScheduler.ts` 用 inFlight 集合防止同任务并发重入,nextRunAt 缺失时以 lastRunAt/createdAt 锚定重算。
- **启示与风险**:leo 是技能非常驻服务,定时执行不适用;但"周期性 deck(周报)"的**结构复用**需求真实。任何建议不得绕 CONFIRM-GATE/DELIVERY-GATE——正确形态是"已确认结构的模板化复用 + 每期数据差异的完整确认序列",即减少往返而非减少确认。分发侧 AIWriteX `wx_publisher.py` 的 draft→publish 两段式(poll_article_url 轮询回执)印证"落草稿、人工确认后发"是行业安全默认。

## 二、重点项目深读纪要(4 个)

### 1. Beav(素材库架构)

本地优先工作台,三层资产体系:(a) 知识库(采集笔记/视频/文档,目录+meta.json,grep+vector RRF 检索);(b) 媒体库(catalog.json 登记生成/导入资产,prompt 归一化去重,绑定稿件);(c) 主体库(人物/商品,图+声+属性)。另有自动社媒调研沉淀素材、博主订阅每日同步、内容日历定时创作(cron 调度器 in-flight 防重入)。MIT-NC 许可,借鉴取机制不取码。

### 2. last30days-skill(选题简报协议)

60.5k star 调研 skill。核心是引擎(AI 写作侧只做 verbatim relay)与判读的分工:三腿发现协议(提名→judging→finalize)带置信度地板,空结果合法;cluster-first 证据簇带 uncertainty 标签;engagement 数据(顶数/赔率)决定证据权重;topic queue 持久化防同题重复;drill 命令基于 last-report.json 缓存对单一簇深挖。对 leo 的直接可借鉴点是**证据分级披露与"取不到就如实说"的协议形态**,而非研究能力本身。

### 3. AIWriteX(全链路编排)

`unified_workflow.py` 的 execute() 五段管线:基础内容生成(CrewAI 单 writer + 搜索工具)→ 维度化创意变换(五旋钮)→ template/design 双路转换(AI 填模板或 AI 出 HTML 设计)→ 保存 → **开关控制的可选发布**;monitor.track_execution 记录 duration/success。热榜工具 hotnews.py 知微/tophub 双源降级。发布走 wx_publisher 草稿箱两段式。工程价值在"统一管线+分段进度+发布开关",但其全自动发布与去 AI 味对抗不属 leo 可吸收范围。

### 4. AI-Media2Doc(多媒体转文档)

FastAPI 薄后端(467 行)+ Vue 前端。链路:上传→S3 预签名→火山 ASR 异步任务→utterances 时间戳→LLM 风格化(自定义 prompt)→`#image[秒数]` 标记提取→前端确定性截帧回填→保存任务。**最有含金量的是占位标记协议**:模型只产占位,确定性渲染器回填,越界标记静默降级移除——与 leo TF-2/required_images 机制同构,可平移到"视频关键帧作 PPT 图片素材"场景。

## 三、借鉴点清单

| 编号 | 来源项目+机制 | leo 现状(证据) | 建议(增强/新增) | 价值论证 | 优先级 | 验证方式 |
|---|---|---|---|---|---|---|
| E5-01 | Beav:目录式素材库+meta.json+catalog 登记(knowledgeLoader/mediaLibraryStore) | 无跨 run 用户素材库;sources-manifest 是单 run 投影(image-deck-workflow.md 步骤 7);profiles/brands/ 已有用户档案先例 | 新增 `${LEO_PPT_HOME}/library/` 素材库:图片/图表/数据表/引用入库(sha256+来源元数据+标签);母版视觉行引用库内素材时自动带出处,sources-manifest 从库登记派生 | logo/产品照/历史图表每轮重传是高频痛点;入库即携带 source_class,与 strict sources 门天然衔接 | P1 | 单测 catalog 读写与 sha 校验;新 case:library 素材入页后 strict 校验绿、库外编造链接仍拒 |
| E5-02 | Beav:媒体 catalog prompt 归一化去重+generated/imported 分桶 | image-history.jsonl 版本历史仅 run 内(image set-active);跨 run 无图资产复用 | 增强:跨 run 图资产登记(prompt 归一化键+backend+尺寸档),同合同页可提议复用历史图(经用户确认,涉及样张继承规则) | 重复母版页(同结构封面/分隔页)省真实生成成本;backend_stats 已有计量基础 | P2 | 单测归一化键;case:复用提议披露来源 run 与指纹 |
| E5-03 | Beav:主体库 SubjectRecord(人物/商品图组+属性复用) | brands/ 仅 VI 色板;人物政策仅 style_lock 一致性锁 | 新增主体库:发言人头像/产品照+使用政策(可否裁切/换底),汇报 deck 团队页/产品页复用 | 政务/金融汇报反复用同批人物图,风格合同可引用主体而非每次重传 | P2 | case:主体引用后逐页人物政策一致性检查 |
| E5-04 | AI-Media2Doc:ASR utterances 毫秒时间戳+`[mm:ss (Xs-Ys)]` 预处理协议 | input-routing 只认文章/报告/笔记/大纲文本与图/PDF | 新增音视频材料路线:登记外部转写通道(宿主能力或用户自备转写稿),leo 按既有文本路线处理;转写段落带时间戳前缀,"引用"级事实可回溯录音时间点 | 会议录音→汇报 PPT 高频;时间戳锚把口头发言升级为可回溯引用,契合三级标注 | P1 | case:audio-material 路由触发数据分级询问+时间戳引用格式;单测时间戳前缀解析 |
| E5-05 | AI-Media2Doc:`#image[秒数]` 占位标记+确定性回填+TIME_OUT_OF_RANGE 静默降级 | TF-2 overlay_text+required_images+视觉行容器清单(image-deck-workflow.md TF 节)已是同构机制 | 增强:母版视觉行扩展"视频帧占位"来源类型——模型只标时间点,确定性截帧工具回填,越界时间点移除并在 qa_note 披露;来源标"实拍(视频帧@Xs)" | 视频素材进 PPT 无需人工逐帧截取;占位协议已被 TF-2 验证,扩展成本低 | P1(依赖 E5-04) | 单测截帧确定性(同视频同秒同 sha);case:越界标记移除+披露 |
| E5-06 | last30days 置信度地板+空结果合法终态;DailyHotApi/newsnow 聚合 API;AIWriteX hotnews 双源降级;Video_note_generator 公共图库配图 | 无任何数据获取通道;三级标注管"来源等级"但市场数据只能等用户提供;validate_assets 已支持 https URL HEAD 探活 | 新增 `references/data-sources.md` 登记可复用数据/图库通道(热榜 API、Unsplash/Pexels、公共数据集):只登记通道与回溯格式(源 URL+抓取时间戳入 manifest 标引用级),抓不到如实 unknown/跳过,不做研究综合(边界归专家1) | 行业汇报需市场数据,通道化让"数据从哪来"有确定答案;回溯格式保证 strict sources 门可判 | P2 | case:引用热榜数字后 manifest 含抓取时间;无源数据仍标 unknown 求证 |
| E5-07 | elog:写作端×发布端解耦+插件化多目标导出;write-then-publish 同源双输出 | export_speaker_notes.py 是唯一导出形态;M1 渲染 lane 已合入(Playwright 确定性渲染+PNG 头断言+render provenance sidecar,render-contract.md);social-card-specs.md 三画板规格已备但"实验性,路由接入属后续" | 新增 export 子命令族:`--format handout-pdf`(逐页图+notes 版式)/`long-image`(逐页竖拼)/`carousel`(读 social-card-specs 正式接入路由),全部走 render lane 确定性渲染,导出物并入 delivery receipt 指纹,导出属交付动作须 DELIVERY-GATE 内披露 | P1 搁置理由(渲染依赖)已消除;逐页图+notes 素材齐备;交付衍生形态是分发生态通用打法(8 组报告半数项目在此卡位);确定性渲染与收据门现成 | P0 | 单测同输入同 sha(确定性);case:export 产物入 receipt、无 receipt 不得声称导出完成 |
| E5-08 | Wechatsync/postbot:默认同步为草稿、人工确认后发布;AIWriteX wx_publisher draft→publish 两段式 | leo 交付止于文件,SKILL.md 无分发相关声明 | 增强:交付披露补一句分发边界——leo 产出分发形态(卡片/长图/handout),**发布动作由用户经外部工具完成**(Wechatsync 等已在 efw tool-selection 登记),leo 不代发不存平台凭据 | 与 DELIVERY-GATE 同构的防范围蠕变声明;分发生态工具成熟,leo 补位导出即止 | P1 | case:用户要求代发时 leo 拒绝并指路外部工具、不请求凭据 |
| E5-09 | xhs_ai_publisher scheduled_tasks(run_count/三态回执)+Beav cron in-flight 防重入 | 无批量/周期模式;交付档案 profiles/ 只预填偏好字段(image-deck-workflow.md 步骤 1) | 新增 deck 模板(结构资产):已确认 deck 的母版骨架+风格+页数合同可存为模板,下期数据到来时走完整确认序列但合同/母版为 diff 式确认(只确认变化项);**确认门数量不减,样张与数据分级每期照常** | 周报/月报是 deck 最高频场景;diff 式确认减少往返而非减少确认,人在回路边界不破 | P2 | case:模板复用时确认序列完整(样张+分级仍在)、缺新材料照常 blocked |
| E5-10 | last30days:topic queue 已覆盖话题登记;judge 读 bundle 全量证据再判 | leo 多 run 间无主题/素材消费记忆 | 增强(寄生于 E5-09 模板):模板实例登记已用数据点与素材指纹,同模板下期自动 diff 出"沿用/新增/缺失",缺失项进材料确认清单 | 周期 deck 数据连续性(上月口径 vs 本月)靠机器 diff 而非人记忆 | P2(依赖 E5-09) | 单测指纹 diff;case:同题重复素材被标记沿用 |
| E5-11 | AIWriteX:统一管线分段进度+monitor.track_execution;Beav 定时任务三态信号 | 交付披露已含路径与未运行项;export_speaker_notes 已如实列缺备注页 | 增强:导出/衍生动作统一三态回执披露(started/completed/failed+产物路径+失败页清单),与收据 verify 衔接 | 导出形态增多后(E5-07),三态回执防止"导出了吗"含糊;讲稿导出的缺页披露先例可推广 | P1(随 E5-07) | case:导出失败页如实列出、不得声称全部导出 |

## 四、明确排除项及理由

1. **自动发布执行**(Wechatsync/postbot/social-auto-upload/xiaohongshu-mcp 的发布链路):leo 是生成技能,交付止于文件。发布属 efw 侧外部工具(Wechatsync 已登记于 tool-selection.md);leo 代发将引入平台风控、账号凭据保管与越权发布风险,DELIVERY-GATE 人在回路不可绕。只补"分发即草稿、leo 不代发"披露原则(E5-08)。
2. **去 AI 味对抗引擎**(AIWriteX 动态风格拟态/朱雀检测对抗/结构粉碎):与 PPT 生成无关;leo 已有自身文风合同(TITLE-READTHROUGH 已吸收 human-writing/avoid-ai-writing 子集,file-github-integration.md #13);检测对抗属规避性用途,不符仓库立场。
3. **热点流量预测**(AIWriteX 热点雷达 12 小时预测):研究/运营域能力,越 leo"生成技能"边界;选题判断归用户或研究类技能,leo 最多消费带时间戳的已获取数据(E5-06)。
4. **爬虫/浏览器自动化采集执行**(MediaCrawler/xiaohongshu-mcp 读写/Beav 插件采集):合规与账号风险;leo 素材来源必须用户自备或经登记的公共只读通道并可回溯;Gate 0/红灯清单的"编造素材链接禁止"精神延伸为"不做采集执行"。
5. **定时无人值守批量生产**(xhs_ai_publisher 到点自动发布/AIMedia 全自动托管/Beav 定时创作的"无人"形态):技能无常驻运行时;即使宿主有 cron,CONFIRM-GATE(大纲/母版/样张/数据分级逐门确认)与 DELIVERY-GATE 不因自动化豁免。吸收其任务模型(E5-09/E5-10)但不吸收其无人值守形态。
6. **多平台账号管理/多账号隔离/浏览器指纹**(xhs_ai_publisher users/proxy_configs/fingerprints 表):非 leo 职责,凭据边界红线(SKILL.md 不变边界)明确凭据只经宿主或 allowlist。
7. **elog 式"笔记平台同步"**(Notion/语雀/飞书下载端):leo 输入是用户提交的材料文件,不做写作平台账号拉取;仅吸收其"一份内容多目标导出"的管线架构(E5-07)。
8. **AIWriteX 创意五旋钮维度化引擎**:与 leo 风格库(137 brief+样式合同+风格反演三组判读)机制不同源且粒度冲突,不吸收。

## 五、边界与风险说明

- 人在回路不可交易:E5-07 导出属交付动作,产物入收据、readiness 披露;E5-09/E5-10 只减往返不减确认,样张与数据分级每期照常;E5-08 明确不代发。
- 与专家1边界:本报告 E5-06 只登记**数据获取通道与回溯格式**;数据怎么选、怎么交叉验证、研究方法论归 Deep Research 侧。
- 与已吸收清单不重复:wenyan-mcp/Wechatsync/XiaohongshuSkills 已在 file-github-integration.md 登记(efw L3 工具层),本报告仅引用不重登;社交卡片规格层(social-card-specs.md,guizang 来源)已存在,E5-07 只做"正式接入路由+导出通道"。
