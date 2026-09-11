# leo-ppt-generator 六行业全流程测评报告（2026-08-30，post-M0 第二轮·中期）

- 主题：「AI Agent 落地一年：从试点到规模化」，一题六景（金融/医疗/制造/教育/政务/零售），与 2026-08-29 首轮同题同景对照
- 被测对象：M0 合入后的技能（安装副本同步核验）；执行 = 主持人 + 6 场景 agent 两波×3，全流程真实执行
- 材料包：每景同构受控设计（陷阱 A unknown 数字 / 陷阱 B 估算数字 / 探针 C 三项指标数据小表 / 探针 D 论断式要点）
- 产物：deliveries/ 三份 PPTX + verdicts/ 六份判定书 + 各景 run 工件（git-ignored 工作区，已于 2026-09-11 清理）

## 一、总分与执行状态

| 场景 | 风格路线 | D1 | D2 | D3 | D4 | D5 | D6 | D7 | D8(M0) | 总分 | 状态 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| medical 医院 | 极简/金字塔 | 2 | 2 | 2 | 2 | 2 | 2 | 2 | 4/4 | **14+4=18/18** | 完成（7 张生成 23 分钟） |
| manufacturing 工厂 | 工程蓝图/教学分解 | 2 | 2 | 2 | 2 | 2 | 2 | 2 | 4/4 | **14+4=18/18** | 完成（7 张生成 39 分钟） |
| finance 银行 | 麦肯锡/金字塔 | 2 | 2 | 2 | 1 | 1 | 0 | 2 | 3/4 | 13/18 | 部分完成（provider 故障，缺页 5/6 拒绝组装——纪律正确） |
| education 高校 | — | — | — | — | — | — | — | — | 0 | **探针阻断** | 1 次探针止损（1448×1086） |
| government 政务 | — | — | — | — | — | — | — | — | 0 | **探针阻断** | 1 次探针止损（1536×1024） |
| retail 零售 | — | — | — | — | — | — | — | — | 0 | **探针阻断** | 4 次探针诊断（见 H3） |

完成三景均分 **（18+18+13）/3 = 16.3/18（90.7%）**，与首轮 90.5% 持平——但本轮口径更严（D8 是 M0 新增 4 分项）。

## 二、M0 增强项首个实测基线（本轮核心增量）

1. **收据门真实闭环（D8③）**：medical 与 manufacturing 均完成 `delivery receipt create` → `verify` = `delivery_receipt_fresh`（changed=[]），交付披露含收据状态。审后篡改可检的能力从单测走向真实交付链路。
2. **论断式要点（D8①）**：完成三景 13 个内容页第一条要点全部为完整论断句 + 证据跟随，TAKEAWAY-READTHROUGH 连读成故事线（medical 校验器 + 读图双确认）。
3. **图证据规则（D8②）**：三景数据小表均走图行处置（六字段：模式/状态/焦点/承载/服务/避免误读），上版数值经主持人独立读图逐字核验全对；**R15 在 3 项指标下零装饰图形**（medical 细线网格、manufacturing 斑马纹表格、finance 箭头+细线分隔）。
4. **样张反演三组（D8④）**：medical/manufacturing 均在样张同轮呈现反演三组判读并落 spec；finance 未附结构页加样提议句（扣 1 分的唯一 D8 缺口）。
5. **主持人独立抽检（双重确认）**：4 张读图（medical 封面+S4、manufacturing S4、finance S4）——引用值逐字在场、unknown 数字（96%/OEE/NPS 82）零出现、估算三重标注（括注+~前缀+虚线纹理）、无溢出截断；finance S4 有 1 处字距贴边的次级视觉瑕疵（不扣分档）。

## 三、缺陷发现（按严重度）

**H3 · provider 尺寸透传失效（本轮阻断源，环境级）**：第三方代理（fast.qianxing.us.ci）于 ~01:23 起无视 `size` 参数——**retail P4 诊断实验实锤：请求 1024×1024 仍返回固定 1536×1024**；同夜 00:38–00:47 窗口曾全量正常（时间性振荡）。官方 openai 凭据 401、atlascloud 未配置，无备用通道。**技能侧防线全部正确工作**：vendor 尺寸守卫拦截（无错尺寸 PNG 落盘）、缺页拒绝组装、第二波三景探针级止损（合计仅 6 次失败调用，零完整流程浪费）。
**H1 复验（上轮最高危，已修复确认）**：finance 执行 2 次 `image edit`（参考图微调），**无 TypeError**；两次失败均为 provider 尺寸漂移被守卫拦截。0829 登记式修复（`_edit_with_images` 补传 `expected_size`）代码层确认生效。
**H2 族（新增 4 条实证）**：① 直调 venv CLI 缺 `LEO_PPT_BUNDLE` → 风格库**静默空集**（F1，两景命中，launcher 才注入）；② `slide_jobs.json` vendor/canonical 双写冲突；③ `image record` 源=目标同路径 → SameFileError 裸崩溃（F5，两景命中）；④ 首次失败冻结 slides 指纹锁死 run（只能弃 run 重建）。
**F4 确证**：`--timeout` 旗标不进 execution_receipt（记 60）；**workaround 有效**：backend create 手工补 timeouts 字段后正确传播（retail 实证 420s 到位）。
**存量未修复现**：M1（assemble 限 run/final/，交付靠复制，hash 一致）、M2（contract_error/template_store_error 吞子码，3+ 处实证）、L2（sldSz type="screen4x3" 残留，数值已 16:9）。
**记录级**：顶层 `image` 子树无 generate（须 `upstream codex-ppt --`，一步导航成本）；vendor CLI 无 `--output` 旗标（缩写歧义，usage 可自纠）。

## 四、对照首轮（0829）结论

| 维度 | 0829 首轮 | 本轮 |
| --- | --- | --- |
| 总分 | 76/84（90.5%） | 完成三景 49/54（90.7%），口径更严（+D8） |
| unknown 门 | 6/6 拒上版 | 3/3 拒上版（+ 求证清单留痕） |
| 估算双标 | 6/6 | 3/3（升级为三重线索：括注+~+虚线纹理） |
| H1 edit 模式 | 6/6 场景崩溃 | **修复确认**（守卫拦截漂移尺寸，无 TypeError） |
| 数字保真 | 36 页无编造 | 完成三景 19 页无编造 + 主持人 4 图独立复核 |
| 新增能力 | — | 收据闭环/论断式/图证据行/反演三组全部真实链路验证 |

## 五、待办与复跑

- education/government/retail 三景：**provider 侧需用户处置后一键补跑**。恢复监视器已值守 4 小时（12 次探针 ×20 分钟，01:32–05:12 全部漂移）；结合 retail P4 实验（请求 1024×1024 仍固定返回 1536×1024），判定该第三方代理（fast.qianxing.us.ci）已改为无视 size 参数的固定 3:2 输出，**非瞬时故障、无自愈迹象**。处置选项：① 修复/更换代理端点（恢复 16:9 尺寸透传）；② 提供有效的官方 openai 凭据（现存凭据 401 invalid_api_key）；③ 配置 atlascloud 等备用 provider。任一就绪后重跑第二波即可（材料包/判定书模板/探针脚本全部就位，预计每景 25–40 分钟，报告按终版升级）。
- 阻断不归因技能：本轮按"3 完成 + 3 探针阻断"如实收口；阻断三景的探针证据（backend.json / 失败 machine JSON）完整保留于各景 probe/ 目录
- 工程修复建议（按收益排序）：H2-F1 启动横幅/报错提示 LEO_PPT_BUNDLE；F5 record 同路径守卫；指纹锁死恢复命令；M2 reason code 子码透出；M1 assemble 输出面放宽；L2 sldSz type 修正；另据 M0.1 稳定性测评经验，新增规则须过"是否需要 SKILL.md 入口锚点"checklist

## 六、验证口径声明

- D5 视觉结论 = 场景 agent 逐页对抗式自审 + 主持人独立读图抽检（4 张）双重确认；OCR 机检、PowerPoint 桌面打开、投屏验收 not-run（如实披露）
- 三份 PPTX：medical.pptx（sha256 7692254…）、manufacturing.pptx（44fc7ce6…）机检 6/6/6 通过 + 收据 fresh；finance 无 PPTX（缺页拒绝组装）
- 全部 verdict 与 run 工件原存 git-ignored 工作区（已于 2026-09-11 清理）
