# leo-ppt-generator 页数契约多维测评报告(2026-08-29)

## 概述

对 generate 路线页数契约(docs/plans/2026-08-29-003)实施多 agent 四维测评:
全量回归分片(2 个并行 /tmp 隔离副本)、judge 对抗鲁棒性(subagent 构造语料)、
契约一致性与镜像漂移(subagent 只读审查)。发现并修复 1 处 P1 契约矛盾、
judge 假接受 15 处、1 个用例前提冲突;页数契约专项 5 用例最终全绿。

被评模型:`glm-5.3-flash[1m]`(claude_code 引擎经代理,同 known-issues 环境事实)。
统计时点套件快照 39 用例;评审期间并行会话新增 10 个多行业用例(至 49),
不在本次范围。

## 维度 A:全量回归(39 用例,2 分片并行)

- **分片 A1**(基础门禁+质量回路,21 例):20 PASS。`control-plane-blocked-summary`
  在 13 连败(known-issues 账目)后本轮首次 PASS。`master-before-render` FAIL,
  归因为**用例前提与新契约冲突**(见"修复"节),适配后复验 PASS。
- **分片 A2**(模版推荐+文档门+U10+页数,18 例):8 PASS、8 FAIL、2 ERROR。
  /tmp 干净副本缺少前置播种与 runtime 状态,与 docgates 报告的已知归因一致。
- **仓库目录对照复跑**(9 个失败/错误例):5 例 PASS——环境差异确证,非行为回归;
  4 例可复现 FAIL(`style-render-guardrail-visible`、`assertion-headline-advisory`、
  `density-cap-advisory`、`post-confirm-revision-doc-gate`),全部属于并行会话
  活跃工作面(风格系统/文档门修订回路),与页数契约无接触面,移交对应 owner。
- **页数契约专项**(4 例+受影响的 master-before-render,仓库目录,judge v2):
  **5/5 全过**。其中 `page-count-ambiguous-asks` 跨 5 轮迭代,契约强化后
  连续 4 轮合规,且询问形态多样(表格二选一/AB 选项/回复 1 或 2)。

## 维度 B:judge 对抗鲁棒性(subagent,58 样本语料)

4 个页数 judge × (34 对抗负例 + 24 健康正例)。

| Judge | 假接受 v1 | 假接受 v2 终版 | 假拒绝 v1 | 假拒绝 v2 终版 |
| --- | --- | --- | --- | --- |
| ambiguous-asks | 3 | 0 | 0 | 0 |
| explicit-total | 3 | 0 | 2 | 0 |
| no-closing | 4 | 0 | 0 | 0 |
| tiny-deck | 5 | 0 | 0 | 0 |

v1 假接受率 44%(15/34),五类共性根因:①NEGATORS 裸"不"整句过滤使
"要不要"类 forbid 永久失明;②否定词距离敏感词远时整句免疫;③forbid 词序
单一(倒装/中文数字/量词绕过);④宽松正向模式被无关引用满足("第16页"冒充
成品 16 页);⑤引号剔除晚于子句分割。v2 重写:否定检测改为匹配起点前 4 字符
窗口的带环视正则、全文匹配不分子句、J1 询问模式加关系词+完成式+否定性询问
三重守卫、J2 拆解三条独立断言、J3 补倒装与"承诺再确认"变体、J4 中文数字/
量词入表。终版 58 样本零假接受、零假拒绝;judge 另对 4 轮历史真实响应回归
(1 例正确拒绝、3 种询问形态全识别)。

## 维度 C:契约一致性与镜像漂移(subagent,只读)

- **P1(已修)**:第 2 步"封面必选,任何场景不得省略"与第 1 步卡片条款
  (≤2 页不加结构页)互斥——1–2 页请求无法同时满足。修复:第 2 步与
  deck-master 结构页纪律补卡片豁免(唯一卡片兼任开场,不设独立结构页)。
- **P2(已修)×2**:叙事三查"组装前关闭"但定义在组装后步骤(执行落点缺失)
  →标注"母版确认门首次执行关闭,此处为组装前复核";三查②三幕式对短 deck
  无豁免 →补"内容页 <3 时按实际关键点数缩放,卡片场景不适用"。
- **P3(记录)**:`reason-codes.md` 的 `input_too_large` 未注明页数口径,
  可选改进,不阻断。
- 五要素三层落位完整互引一致;全库无旧口径残留;安装镜像
  `~/.agents/skills/leo-ppt-generator` 为 symlink→仓库,实时同步;
  "SKILL.md 不改也不矛盾"经全词扫描成立。

## 修复清单

1. 契约 3 处:P1 卡片豁免(image-deck-workflow 第 2 步 + deck-master)、
   P2 三查落点与短 deck 豁免(第 12 步)。
2. judge 4 个重写为 v2(含 ASK_NEGATED 补丁),58 样本语料零假接受/零假拒绝。
3. `master-before-render.yaml` prompt 适配:页数改显式总数(避开模糊询问轮)、
   补数据密级(多行业 data-classification-gate 行为已生效,agent 会询问密级)。
4. 用例 prompt 自包含引用级数据(消除无播种环境下的反编造张力)。

## 结论与残留

页数契约语义、结构页规则、极小页数卡片处理在真实 agent 行为层验证通过;
契约文本的"催促/拍板措辞不构成口径明确"条款被 5 轮迭代证明是行为合规的
关键。残留四项均不在本计划范围:①4 个可复现失败属并行工作面,移交风格
系统/文档门 owner;②harness 级 content/ 前置播种仍缺失(known-issues 既有
建议),/tmp 类干净环境跑 docgates 用例会产生环境性失败;③judge 完成式守卫
的误杀半径(健康消息在询问 ±20 字符内含"已经")为已知低风险面;④skill-up
无 workspace 隔离旗标,并行分片需 /tmp 整目录复制 workaround。
