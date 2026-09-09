#!/usr/bin/env python3
"""U7/§3.1：44 单元行业视觉矩阵执行器（HTML lane，本地渲染）。

单元构成：005 的 20 行业任务定义 × {light, dark} 展示环境 = 40 单元，
科技/金融/教育/医疗各补一个同材料的受众保守度对照 = 44 单元。
每单元三页（封面 cover-basic / 正文 body-basic / 数据 spec-table），
132 页/轮，两轮独立渲染 ≥264 页。

环境语义（§3.1）：展示环境不是强制主题 mode——组合主题无已验证深色
变体时，用有理由的浅底服务暗环境（env_note 登记），不宣称深色能力。

校准（--calibrate，正式执行前）：合格样本 + 注入缺陷样本（未换肤/
空白页/溢出/错误尺寸）逐类 100% 检出才可进入正式轮。

语义评审：硬检查全量 + 维护者单评审 + 模型辅助视觉抽样；方案要求的
两位独立评审 80% 一致率在本会话不可得，如实登记为缺口（不伪造）。

Usage:
  python3 scripts/verify_industry_visual_matrix.py --calibrate
  python3 scripts/verify_industry_visual_matrix.py --rounds 2
"""

from __future__ import annotations

import argparse
import json
import sys
import tempfile
from pathlib import Path

SKILL = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SKILL / "runtime" / "src"))

from leo_ppt_generator.asset_resolver import AssetResolver
from leo_ppt_generator.render.layout import compile_geometry
from leo_ppt_generator.render.page import RenderError, render_page
from leo_ppt_generator.render.theme import compute_effective_theme

BLANK_BYTES_MIN = 40_000  # 校准依据 governance/rules/render-qa-profiles.json

# 页角色 → (模板, 版式 profile)。数据页用 p25-spec-table（声明 3 列）
ROLE_LAYOUT = {"cover": ("cover-basic", "builtin:layout:cover-basic"),
               "content": ("body-basic", "builtin:layout:body-basic"),
               "data": ("spec-table", "builtin:layout:p25-spec-table")}

# 行业 → 九方向种子组合（20 行业无需 20 套皮肤，§3.1 允许复用）
# u05 基线取 edu-bright（组会同学），保守对照取 academic-austere（评审口径）
INDUSTRY_SEED = {
    "u01": "tech-dark", "u02": "gov-red", "u03": "health-clean",
    "u04": "finance-navy", "u05": "edu-bright", "u06": "consulting-pyramid",
    "u07": "management-clear", "u08": "tech-dark", "u09": "brand-creative",
    "u10": "brand-creative", "u11": "brand-creative", "u12": "brand-creative",
    "u13": "management-clear", "u14": "brand-creative", "u15": "tech-dark",
    "u16": "management-clear", "u17": "management-clear", "u18": "edu-bright",
    "u19": "finance-navy", "u20": "consulting-pyramid",
}

# 受众保守度对照（同材料换更保守组合与受众口径）
CONTRAST = {
    "u01": ("management-clear", "监管与合规评审受众（对照：机构投资人）"),
    "u03": ("gov-red", "卫生主管部门评审受众（对照：院长办公会）"),
    "u04": ("gov-red", "监管申报口径评审（对照：总行风险管理委员会）"),
    "u05": ("academic-austere", "答辩/评审委员会受众（对照：课题组组会）"),
}

# 每行业三页内容——全部取自 005 任务简报明示事实/短语，不新增数字
UNITS_CONTENT = {
  "u01": {
    "cover": {"kicker": "互联网科技 · C 轮路演", "title": "供应链协同 SaaS 的 C 轮融资路演",
              "subtitle": "净收入留存 · 融资用途 · 获客复制", "footer_left": "云衡科技",
              "footer_right": "投资委员会", "page_no": 1},
    "content": {"title": "投资委员会的三个问题",
                "bullets": ["净收入留存是否撑得起估值上移",
                            "2.4 亿融资用途与里程碑是否可核",
                            "现有获客体系是否可复制"], "page_no": 2},
    "data": {"title": "路演议程与证据口径",
             "columns": ["议题", "关注点", "口径来源"],
             "column_align": ["left", "left", "left"],
             "rows": [["净收入留存", "估值上移支撑", "材料财务口径"],
                      ["融资用途", "2.4 亿拆分可核", "测算或显式 unknown"],
                      ["获客体系", "可复制性", "CRM 导出口径"]], "page_no": 3}},
  "u02": {
    "cover": {"kicker": "政务公共 · 年度评估", "title": "营商环境优化行动年度评估汇报",
              "subtitle": "政策效果 · 资源排序 · 预算建议", "footer_left": "工作专班",
              "footer_right": "年度评估", "page_no": 1},
    "content": {"title": "年度评估两件事",
                "bullets": ["客观呈现第二年行动的政策效果（达成/未达/原因）",
                            "三个候选投放方向给出资源排序建议",
                            "专班据此形成向常务会提出的预算建议"], "page_no": 2},
    "data": {"title": "候选投放方向对照",
             "columns": ["方向", "定位", "决策口"],
             "column_align": ["left", "left", "left"],
             "rows": [["大厅扩容改造", "服务能力", "预算建议"],
                      ["数据共享深化", "跨部门协同", "预算建议"],
                      ["免申即享扩面", "惠企兑现", "预算建议"]], "page_no": 3}},
  "u03": {
    "cover": {"kicker": "医疗健康 · 运行评估", "title": "日间手术中心运行一年评估汇报",
              "subtitle": "效率 · 安全 · 费用三维评估", "footer_left": "医务部",
              "footer_right": "院长办公会", "page_no": 1},
    "content": {"title": "评估要回答的问题",
                "bullets": ["日间模式对「效率—安全—费用」三个维度的影响",
                            "扩大规模的前提条件是否成熟",
                            "新增术种的前提条件是否成熟"], "page_no": 2},
    "data": {"title": "评估维度与决议选项",
             "columns": ["维度", "评估口", "决议关联"],
             "column_align": ["left", "left", "left"],
             "rows": [["效率", "一年运行数据", "扩规模决议"],
                      ["安全", "一年运行数据", "扩规模决议"],
                      ["费用", "一年运行数据", "有条件扩/暂缓"]], "page_no": 3}},
  "u04": {
    "cover": {"kicker": "金融审计 · 申报核对", "title": "普惠小微贷款监管申报前数据核对汇报",
              "subtitle": "三套来源 · 差异成因 · 口径建议", "footer_left": "风险管理部",
              "footer_right": "监管口径", "page_no": 1},
    "content": {"title": "逐项回答三个问题",
                "bullets": ["三个核心指标在三套来源中的差异有多大",
                            "成因属于口径差异、时点差异还是数据质量",
                            "申报值采用哪套来源、依据与剩余风险控制"], "page_no": 2},
    "data": {"title": "核心指标与差异归类",
             "columns": ["指标", "来源数", "差异归类"],
             "column_align": ["left", "left", "left"],
             "rows": [["贷款余额", "三套来源", "口径/时点/质量"],
                      ["贷款户数", "三套来源", "口径/时点/质量"],
                      ["不良率", "三套来源", "口径/时点/质量"]], "page_no": 3}},
  "u05": {
    "cover": {"kicker": "教育学术 · 组会提案", "title": "博士组会的下一阶段实验设计提案",
              "subtitle": "科学假设 · 路线差别 · 预算申请", "footer_left": "课题组",
              "footer_right": "组会", "page_no": 1},
    "content": {"title": "组会要判断什么",
                "bullets": ["拟验证的科学假设是什么",
                            "与已有两条技术路线的差别在哪",
                            "实验怎么设计才能正负结果都有结论价值"], "page_no": 2},
    "data": {"title": "提案要素与行动目标",
             "columns": ["要素", "内容口", "组会决议"],
             "column_align": ["left", "left", "left"],
             "rows": [["科学假设", "新思路界定", "方案确认"],
                      ["实验设计", "正负有结论", "修改后通过"],
                      ["标注预算", "学期投入", "预算锁定"]], "page_no": 3}},
  "u06": {
    "cover": {"kicker": "咨询法律 · 项目提案", "title": "数字化供应链诊断项目提案路演",
              "subtitle": "诊断贴近实际 · 交付可验收 · 报价逻辑", "footer_left": "项目组",
              "footer_right": "客户专享", "page_no": 1},
    "content": {"title": "提案要证明三件事",
                "bullets": ["对 H 集团供应链问题的诊断比另外两家更贴近实际",
                            "阶段划分与交付物设计可核、可验收",
                            "三期分别计价的报价结构与价值假设逻辑成立"], "page_no": 2},
    "data": {"title": "提案论证结构",
             "columns": ["论点", "对照面", "验收口"],
             "column_align": ["left", "left", "left"],
             "rows": [["诊断更贴近实际", "两家竞对", "可核"],
                      ["阶段与交付物", "分期设计", "可验收"],
                      ["报价结构", "三期计价", "价值假设"]], "page_no": 3}},
  "u07": {
    "cover": {"kicker": "制造能源 · 立题汇报", "title": "化工集团双碳改造路线图立题汇报",
              "subtitle": "分阶段不虚 · 优先方向 · 立项申请", "footer_left": "双碳办公室",
              "footer_right": "总经理办公会", "page_no": 1},
    "content": {"title": "立题汇报要回答",
                "bullets": ["不做完整盘查的前提下路线图怎么分阶段才不虚",
                            "三个基地哪些改造方向大概率优先（定性判断）",
                            "立题阶段预算与周期申请多少合适"], "page_no": 2},
    "data": {"title": "立题决策要素",
             "columns": ["要素", "口径", "办公会决议"],
             "column_align": ["left", "left", "left"],
             "rows": [["路线图分期", "不依赖完整盘查", "批准立项"],
                      ["基地优先向", "工艺与能源结构定性", "一期盘查"],
                      ["预算周期", "立题阶段申请", "预算批准"]], "page_no": 3}},
  "u08": {
    "cover": {"kicker": "汽车交通 · B 轮路演", "title": "出行平台区域公司的 B 轮路演",
              "subtitle": "单位经济 · 运力协同 · 资金配置", "footer_left": "区域公司",
              "footer_right": "领投机构", "page_no": 1},
    "content": {"title": "投资人要形成的判断",
                "bullets": ["主业单位经济模型是否健康（逐单经济而非补贴堆量）",
                            "运力协同战略假设验证到什么程度",
                            "本轮 1.8 亿资金配置建议与对应里程碑"], "page_no": 2},
    "data": {"title": "路演论证与资金口径",
             "columns": ["议题", "判读口", "资金关联"],
             "column_align": ["left", "left", "left"],
             "rows": [["单位经济", "逐单口径", "健康前提"],
                      ["运力协同", "验证程度", "还需投入"],
                      ["资金配置", "1.8 亿拆分", "里程碑绑定"]], "page_no": 3}},
  "u09": {
    "cover": {"kicker": "消费时尚 · 新品提案", "title": "新锐美妆品牌的新品渠道发布提案",
              "subtitle": "客群匹配 · 势能转化 · 渠道政策", "footer_left": "品牌部",
              "footer_right": "渠道客户", "page_no": 1},
    "content": {"title": "让采购决策层相信三件事",
                "bullets": ["新品与 M 集合的客群定位匹配",
                            "线上势能可以转化为线下动销",
                            "渠道政策（供货价/毛利保护/动销支持/滞销退换）可执行"], "page_no": 2},
    "data": {"title": "渠道政策设计口径",
             "columns": ["政策项", "设计口", "渠道诉求"],
             "column_align": ["left", "left", "left"],
             "rows": [["供货价", "政策设计", "毛利保护"],
                      ["动销支持", "政策设计", "可执行"],
                      ["滞销退换", "政策设计", "友好且可执行"]], "page_no": 3}},
  "u10": {
    "cover": {"kicker": "文旅餐饮 · A 轮路演", "title": "区域连锁咖啡品牌的 A 轮路演",
              "subtitle": "单店模型 · 开店空间 · 资金用途", "footer_left": "山雀咖啡",
              "footer_right": "早期消费机构", "page_no": 1},
    "content": {"title": "路演要证明",
                "bullets": ["单店模型在真实口径下健康（回本周期/爬坡/同店增长）",
                            "「社区精品平价」定位在所在城市仍有开店空间",
                            "本轮 6,000 万用途（开店+供应链小仓）与里程碑成立"], "page_no": 2},
    "data": {"title": "单店模型与资金口径",
             "columns": ["议题", "口径", "目标"],
             "column_align": ["left", "left", "left"],
             "rows": [["单店模型", "真实口径", "健康判定"],
                      ["开店空间", "城市测算逻辑", "空间可核"],
                      ["资金用途", "6,000 万拆分", "条款单谈判"]], "page_no": 3}},
  "u11": {
    "cover": {"kicker": "游戏娱乐 · 发行提案", "title": "中型厂商的新手游发行提案",
              "subtitle": "产品竞争力 · 发行两案 · 里程碑", "footer_left": "发行部",
              "footer_right": "投资决策会", "page_no": 1},
    "content": {"title": "提案要完成",
                "bullets": ["产品竞争力论证（品类定位/留存与付费/差异化）",
                            "发行路线两案对比（独代 vs 自发行）给出推荐与依据",
                            "未来 12 个月里程碑（测试节点/版号节奏/上线窗口）与资金需求"], "page_no": 2},
    "data": {"title": "发行两案对比口径",
             "columns": ["方案", "结构", "风险口"],
             "column_align": ["left", "left", "left"],
             "rows": [["独代发行", "分成结构", "风险转移"],
                      ["自发买量", "回收模型", "现金流压力"],
                      ["推荐依据", "两案对照", "立项意向"]], "page_no": 3}},
  "u12": {
    "cover": {"kicker": "体育健身 · Pre-A 路演", "title": "精品健身工作室连锁的 Pre-A 路演",
              "subtitle": "模型可复制 · 爬坡解释 · 扩张节奏", "footer_left": "创始团队",
              "footer_right": "消费投资机构", "page_no": 1},
    "content": {"title": "路演要证明",
                "bullets": ["第一家成熟店模型可复制（内核要素 vs 选址运气）",
                            "第二、三家爬坡差异的解释框架",
                            "扩张节奏推荐方案（6 家 vs 3 家 vs 更保守）与依据"], "page_no": 2},
    "data": {"title": "扩张节奏决策口径",
             "columns": ["议题", "口径", "判断依据"],
             "column_align": ["left", "left", "left"],
             "rows": [["模型内核", "要素拆解", "可复制判定"],
                      ["爬坡差异", "二/三店对照", "解释框架"],
                      ["节奏方案", "6/3/更保守", "投决会决议"]], "page_no": 3}},
  "u13": {
    "cover": {"kicker": "农业 · 年度总结与扩产", "title": "智慧大棚示范基地年度运行总结与扩产提案",
              "subtitle": "产量 · 成本 · 渠道三维状态", "footer_left": "基地经营班子",
              "footer_right": "董事会", "page_no": 1},
    "content": {"title": "汇报要回答",
                "bullets": ["第二年「产量—成本—渠道」真实状态与第一年对比",
                            "扩产前提条件（已具备 vs 依赖未定因素）",
                            "第二个县选址逻辑与风险清单"], "page_no": 2},
    "data": {"title": "扩产决策要素",
             "columns": ["要素", "状态口", "决议关联"],
             "column_align": ["left", "left", "left"],
             "rows": [["三维状态", "两年对比", "原则同意"],
                      ["前提条件", "已备/未定", "扩产立项"],
                      ["选址尽调", "风险清单", "尽调预算"]], "page_no": 3}},
  "u14": {
    "cover": {"kicker": "传媒出版 · 年度提案", "title": "数字阅读平台的年度广告营销提案",
              "subtitle": "客群匹配 · 场景价值 · 组合方案", "footer_left": "平台商业化部",
              "footer_right": "汽车品牌市场部", "page_no": 1},
    "content": {"title": "让广告主相信三件事",
                "bullets": ["用户结构与目标客群（25–35 岁、家庭首购/换购）匹配",
                            "阅读场景对汽车品牌心智渗透的独特价值",
                            "组合方案（书单共创/有声冠名/社区活动）执行链路可交付"], "page_no": 2},
    "data": {"title": "组合方案与目标",
             "columns": ["方案组件", "形态", "目标"],
             "column_align": ["left", "left", "left"],
             "rows": [["书单共创", "内容共建", "年度框架短名单"],
                      ["有声栏目冠名", "场景渗透", "年度框架短名单"],
                      ["社区读书活动", "线下触达", "可交付链路"]], "page_no": 3}},
  "u15": {
    "cover": {"kicker": "航空航天 · 飞行评审", "title": "可复用火箭一子级第三次回收飞行结果评审",
              "subtitle": "事件时序 · 参数趋势 · 状态建议", "footer_left": "型号办公室",
              "footer_right": "技术评审委员会", "page_no": 1},
    "content": {"title": "评审要完成",
                "bullets": ["本次飞行关键事件时序还原（点火→着陆）",
                            "三次飞行关键参数对比与趋势判读（收敛 vs 边界）",
                            "下一次飞行的放宽或加严建议及依据"], "page_no": 2},
    "data": {"title": "评审要点与产出",
             "columns": ["要点", "口径", "产出"],
             "column_align": ["left", "left", "left"],
             "rows": [["事件时序", "飞行遥测", "时序还原"],
                      ["参数对比", "三次飞行", "趋势判读"],
                      ["状态建议", "放宽/加严", "状态变更单"]], "page_no": 3}},
  "u16": {
    "cover": {"kicker": "建筑工程 · 节点汇报", "title": "产业园区项目主体结构封顶节点汇报",
              "subtitle": "进度 · 质量 · 安全三线状态", "footer_left": "项目部",
              "footer_right": "业主与质监备案", "page_no": 1},
    "content": {"title": "节点汇报三件事",
                "bullets": ["封顶节点的进度、质量、安全三线状态",
                            "下一阶段（二次结构与机电安装）计划交底",
                            "投资完成情况与合同工期的解释框架（经得起追问）"], "page_no": 2},
    "data": {"title": "节点状态与目标",
             "columns": ["状态线", "口径", "目标"],
             "column_align": ["left", "left", "left"],
             "rows": [["进度", "节点对照", "节点款支付确认"],
                      ["质量", "验收口径", "备案一次通过"],
                      ["安全", "监督口径", "备案一次通过"]], "page_no": 3}},
  "u17": {
    "cover": {"kicker": "物流供应链 · 季度分析", "title": "仓配一体化转型的季度经营分析",
              "subtitle": "渗透黏性 · 成本时效 · 投入产出", "footer_left": "经营分析部",
              "footer_right": "经营班子", "page_no": 1},
    "content": {"title": "分析要回答",
                "bullets": ["一体化产品对客户的渗透与黏性（签约/单客户价值变化）",
                            "三块业务成本与时效变化（合并口径 vs 分业务口径）",
                            "自动化分拣一期投入产出与二三期决策建议"], "page_no": 2},
    "data": {"title": "二三期决策口径",
             "columns": ["议题", "口径", "决议选项"],
             "column_align": ["left", "left", "left"],
             "rows": [["客户渗透", "签约结构", "继续投入"],
                      ["成本时效", "仓+配合并口径", "暂缓"],
                      ["分拣二三期", "一期投入产出", "改方案"]], "page_no": 3}},
  "u18": {
    "cover": {"kicker": "公益组织 · 年度汇报", "title": "乡村阅读项目的年度捐赠人汇报",
              "subtitle": "证据链 · 财务坦诚 · 来年计划", "footer_left": "项目部",
              "footer_right": "捐赠人大会", "page_no": 1},
    "content": {"title": "汇报要完成",
                "bullets": ["捐赠转化为改变的可核证据链（做了什么—谁在用—怎么验证）",
                            "管理费用比例的口径与披露方式经得起公信力标准",
                            "明年的计划与资金需求框架"], "page_no": 2},
    "data": {"title": "证据链与行动目标",
             "columns": ["环节", "内容口", "目标"],
             "column_align": ["left", "left", "left"],
             "rows": [["做了什么", "项目事实", "月捐新增"],
                      ["到了哪里", "落地核对", "大额续捐邀约"],
                      ["怎么验证", "可核口径", "公信力标准"]], "page_no": 3}},
  "u19": {
    "cover": {"kicker": "大宗商品 · 风险复盘", "title": "铜贸业务风险敞口与对冲策略复盘",
              "subtitle": "结构钱与执行钱 · 偏差事实链 · 制度修订", "footer_left": "风险管理部",
              "footer_right": "经营班子", "page_no": 1},
    "content": {"title": "复盘要完成",
                "bullets": ["季度行情与公司敞口的对照还原（结构钱 vs 执行钱）",
                            "两处套保偏差的事实链（触发/发现/处置/影响量化口径）",
                            "套保制度修订建议与剩余风险"], "page_no": 2},
    "data": {"title": "复盘结论与产出",
             "columns": ["议题", "口径", "产出"],
             "column_align": ["left", "left", "left"],
             "rows": [["敞口对照", "行情 vs 敞口", "结构/执行归因"],
                      ["偏差还原", "事实链", "损失量化口径"],
                      ["制度修订", "权限与阈值", "委员会批准"]], "page_no": 3}},
  "u20": {
    "cover": {"kicker": "人力资源 · 选型提案", "title": "HR SaaS 的系统替换选型提案",
              "subtitle": "痛点诊断 · 替换路径 · 实施保障", "footer_left": "选型小组",
              "footer_right": "客户决策层", "page_no": 1},
    "content": {"title": "提案要完成",
                "bullets": ["对 D 集团现状痛点的诊断式理解（不假装做过详调）",
                            "替换路径分期建议（一次性切换 vs 分模块 vs 双轨）与依据",
                            "实施周期、风险与保障机制"], "page_no": 2},
    "data": {"title": "替换路径与目标",
             "columns": ["路径", "特征", "推荐依据"],
             "column_align": ["left", "left", "left"],
             "rows": [["一次性切换", "周期短", "风险口径"],
                      ["分模块迁移", "渐进", "保障机制"],
                      ["双轨并行", "稳态过渡", "POC 短名单"]], "page_no": 3}},
}

INDUSTRY_NAME = {
    "u01": "互联网科技", "u02": "政务公共", "u03": "医疗健康", "u04": "金融审计",
    "u05": "教育学术", "u06": "咨询法律", "u07": "制造能源", "u08": "汽车交通",
    "u09": "消费时尚", "u10": "文旅餐饮", "u11": "游戏娱乐", "u12": "体育健身",
    "u13": "农业", "u14": "传媒出版", "u15": "航空航天", "u16": "建筑工程",
    "u17": "物流供应链", "u18": "公益社会组织", "u19": "大宗商品贸易", "u20": "人力资源服务",
}


def build_units() -> list[dict]:
    """44 单元：20 行业 × {light,dark} + 4 受众保守度对照（light 环境）。"""

    units = []
    for uid in sorted(INDUSTRY_SEED):
        seed = INDUSTRY_SEED[uid]
        for env in ("light", "dark"):
            mode = "dark" if (env == "dark" and seed == "tech-dark") else "light"
            note = ""
            if env == "dark" and seed != "tech-dark":
                note = ("组合主题无已验证深色变体：以浅底服务暗环境（§3.1 允许），"
                        "不宣称深色能力")
            units.append({"unit_id": f"{uid}-{env}", "industry": INDUSTRY_NAME[uid],
                          "seed": seed, "env": env, "mode": mode, "env_note": note,
                          "audience_note": "", "content": UNITS_CONTENT[uid]})
    for uid, (seed, note) in CONTRAST.items():
        units.append({"unit_id": f"{uid}-conservative", "industry": INDUSTRY_NAME[uid],
                      "seed": seed, "env": "light", "mode": "light", "env_note": "",
                      "audience_note": note, "content": UNITS_CONTENT[uid]})
    assert len(units) == 44, len(units)
    return units


def _theme_vars_for(role: str, effective: dict, resolver: AssetResolver,
                    fixture: dict) -> dict:
    """F4：主题角色值 + layout profile 编译几何（与 deck-style 矩阵同一合同）。"""

    template, layout_id = ROLE_LAYOUT[role]
    profile = resolver.resolve(layout_id)["data"]
    column_count = len(fixture["columns"]) if "columns" in fixture else None
    geometry = compile_geometry(profile, effective, column_count=column_count)
    weights = geometry.pop("column_weights", None)
    theme_vars = {"colors": effective["colors"], "fonts": effective["fonts"],
                  "geometry": geometry}
    if weights is not None:
        theme_vars["column_weights"] = weights
    return theme_vars


def render_unit_page(unit: dict, role: str, out: Path, resolver: AssetResolver,
                     *, theme_override: dict | None = None,
                     size_override: tuple[int, int] | None = None,
                     fixture_override: dict | None = None) -> dict:
    """渲染一页并跑六项硬检查；注入参数仅供校准（--calibrate）使用。"""

    seed = unit["seed"]
    style = resolver.resolve(f"builtin:style:{seed}")
    theme_id = style["data"]["bindings"]["theme_default"]
    theme = resolver.resolve(theme_id)["data"]
    effective = compute_effective_theme(theme, mode=unit["mode"])
    fixture = fixture_override if fixture_override is not None else unit["content"][role]
    out.parent.mkdir(parents=True, exist_ok=True)
    data_path = out.with_suffix(".json")
    data_path.write_text(json.dumps(fixture, ensure_ascii=False, indent=2),
                         encoding="utf-8")
    theme_vars = theme_override if theme_override is not None else \
        _theme_vars_for(role, effective, resolver, fixture)
    kwargs = {}
    if size_override is not None:
        kwargs["size"] = size_override
    error = None
    try:
        result = render_page(ROLE_LAYOUT[role][0], data_path, out,
                             theme_variables=theme_vars, **kwargs)
    except RenderError as exc:
        result, error = {}, {"reason_code": exc.args[0] if exc.args else "render_error",
                             "detail": str(exc)[:200]}
    title = fixture.get("title") or fixture.get("quote") or ""
    png_bytes = out.stat().st_size if out.exists() else 0
    checks = [
        {"id": "overflow", "version": "render_page-sentinel", "result":
            "fail" if error else "pass",
         "detail": (error or {}).get("reason_code", "")},
        {"id": "dimensions", "version": "1", "result":
            "pass" if (result.get("width"), result.get("height")) == (2560, 1440)
            else "fail",
         "detail": f"{result.get('width')}x{result.get('height')}"},
        {"id": "blank", "version": "1", "result":
            "pass" if png_bytes >= BLANK_BYTES_MIN else "fail",
         "detail": f"{png_bytes} bytes"},
    ]
    # 主题生效闸（像素级，mode 感知）
    bg = effective["colors"]["background"]
    expected_bg = (int(bg[1:3], 16), int(bg[3:5], 16), int(bg[5:7], 16))
    if error or png_bytes == 0:
        checks.append({"id": "theme_applied", "version": "1", "result": "fail",
                       "detail": f"render error: {error}"})
    else:
        from PIL import Image

        im = Image.open(out).convert("RGB")
        corner = im.getpixel((30, 30))
        checks.append({"id": "theme_applied", "version": "1", "result":
            "pass" if all(abs(g - w) <= 16 for g, w in zip(corner, expected_bg)) else "fail",
            "detail": f"corner={corner} expected_bg={expected_bg} mode={unit['mode']}"})
    checks.append({"id": "ready_signal", "version": "1", "result":
        "pass" if result.get("ready_signal") == "data-leo-ready" else "fail"})
    checks.append({"id": "title_nonempty", "version": "1",
                   "result": "pass" if title else "fail"})
    return {"role": role, "template": ROLE_LAYOUT[role][0], "png": str(out),
            "bytes": png_bytes, "checks": checks, "error": error,
            "hard_pass": all(c["result"] == "pass" for c in checks)}


def run_calibration(resolver: AssetResolver, out_root: Path) -> dict:
    """正式执行前校准：合格样本 + 注入缺陷样本逐类 100% 检出。

    人工标签来源：维护者（会话内单人）按样本构造意图标注——合格样本
    必须六闸全过；缺陷样本必须被对应闸检出。检出率 <100% 则校准失败。
    """

    units = {u["unit_id"]: u for u in build_units()}
    cal_dir = out_root / "calibration"
    samples = []

    good = ["u04-light", "u01-dark", "u02-light", "u09-light"]
    for uid in good:
        unit = units[uid]
        for role in ("cover", "content", "data"):
            page = render_unit_page(
                unit, role, cal_dir / "good" / f"{uid}-{role}.png", resolver)
            samples.append({"sample": f"good:{uid}:{role}", "label": "pass",
                            "hard_pass": page["hard_pass"], "page": page})

    def _big_fixture(rows: int, title: str) -> dict:
        return {"title": title, "columns": ["议题", "口径", "决议"],
                "column_align": ["left", "left", "left"],
                "rows": [[f"项目 {i:02d}", f"口径 {i:02d}", f"决议 {i:02d}"]
                         for i in range(1, rows + 1)], "page_no": 3}

    # 缺陷样本 ≥10（方案：合格/不合格各至少十页）；类别 → 必须命中的闸
    defect_specs = [
        ("theme_failure", "u01-dark", "cover", {}, None, None),
        ("theme_failure", "u15-dark", "data", {}, None, None),
        ("theme_failure", "u08-dark", "content", {}, None, None),
        ("blank_page", "u04-light", "data", {}, {"title": "", "columns": [],
         "column_align": [], "rows": [], "page_no": 3}, None),
        ("blank_page", "u04-light", "cover", {}, {"kicker": "", "title": "",
         "subtitle": "", "footer_left": "", "footer_right": "", "page_no": 1}, None),
        ("overflow", "u04-light", "data", None, _big_fixture(12, "溢出注入样本 A"), None),
        ("overflow", "u04-light", "data", None, _big_fixture(16, "溢出注入样本 B"), None),
        ("dimensions", "u04-light", "cover", None, None, (1920, 1080)),
        ("dimensions", "u04-light", "content", None, None, (1280, 720)),
        ("title_nonempty", "u04-light", "data", None, {"title": "",
         "columns": ["议题", "口径", "决议"], "column_align": ["left", "left", "left"],
         "rows": [["净收入留存", "估值上移", "财务口径"]], "page_no": 3}, None),
    ]
    gate_by_cls = {"theme_failure": "theme_applied", "blank_page": "blank",
                   "overflow": "overflow", "dimensions": "dimensions",
                   "title_nonempty": "title_nonempty"}
    detection = {}
    for idx, (cls, uid, role, theme_ov, fixture_ov, size_ov) in enumerate(defect_specs):
        page = render_unit_page(units[uid], role,
                                cal_dir / "defect" / f"{cls}-{idx}.png", resolver,
                                theme_override=theme_ov,
                                fixture_override=fixture_ov,
                                size_override=size_ov)
        samples.append({"sample": f"defect:{cls}:{idx}", "label": "fail",
                        "hard_pass": page["hard_pass"], "page": page})
        gate = gate_by_cls[cls]
        hit = next((c for c in page["checks"] if c["id"] == gate), None)
        detection.setdefault(cls, {"gate": gate, "detected": True,
                                   "variants": 0})
        detection[cls]["detected"] = detection[cls]["detected"] and bool(
            hit and hit["result"] == "fail")
        detection[cls]["variants"] += 1
    good_pass = all(s["hard_pass"] for s in samples if s["label"] == "pass")
    all_detected = all(v["detected"] for v in detection.values())
    report = {
        "kind": "industry-visual-calibration", "schema_version": 1,
        "label_source": "维护者（会话内单评审，按构造意图标注；合格样本须六闸全过，缺陷样本须对应闸检出）",
        "pass_samples": sum(1 for s in samples if s["label"] == "pass"),
        "fail_samples": sum(1 for s in samples if s["label"] == "fail"),
        "good_samples_all_pass": good_pass,
        "defect_detection": detection,
        "defect_detection_100pct": all_detected,
        "calibration_ok": good_pass and all_detected,
        "samples": samples,
    }
    (out_root / "calibration-report.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    return report


def run_rounds(rounds: int, resolver: AssetResolver, out_root: Path) -> dict:
    units = build_units()
    results = []
    for round_no in range(1, rounds + 1):
        for unit in units:
            pages = []
            for role in ROLE_LAYOUT:
                out = out_root / f"round{round_no}" / unit["unit_id"] / f"{role}.png"
                pages.append(render_unit_page(unit, role, out, resolver))
            results.append({"unit": unit["unit_id"], "round": round_no,
                            "industry": unit["industry"], "seed": unit["seed"],
                            "env": unit["env"], "mode": unit["mode"],
                            "env_note": unit["env_note"],
                            "audience_note": unit["audience_note"],
                            "lane": "html",
                            "pages": pages,
                            "hard_pass": all(p["hard_pass"] for p in pages)})
    report = {
        "kind": "industry-visual-matrix", "schema_version": 1,
        "units": len(units), "rounds": rounds,
        "pages_total": sum(len(r["pages"]) for r in results),
        "summary": {"units_hard_pass": sum(1 for r in results if r["hard_pass"]),
                    "units_total": len(results)},
        "results": results,
        "review_gap": ("方案要求两位独立评审 80% 一致率与人工标签对齐；本会话只有"
                       "维护者单评审 + 模型辅助抽样，无第二位独立评审——该维度按"
                       "未完成登记，不伪造。"),
        "coverage_note": ("与九方向种子页（deck-style-matrix）内容/输入/依赖/路线/"
                          "参数均不同，不构成去重；两轮为独立渲染（不同输出目录，"
                          "无同次生成复用）。"),
    }
    (out_root / "matrix-report.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    return report


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--calibrate", action="store_true")
    parser.add_argument("--rounds", type=int, default=2)
    args = parser.parse_args()
    resolver = AssetResolver(library=SKILL / "template-library")
    out_root = SKILL / "evals" / "fixtures" / "template-quality" / "industry-visual"
    if args.calibrate:
        report = run_calibration(resolver, out_root)
        print(json.dumps({"calibration_ok": report["calibration_ok"],
                          "pass_samples": report["pass_samples"],
                          "fail_samples": report["fail_samples"],
                          "defect_detection": report["defect_detection"]},
                         ensure_ascii=False))
        return 0 if report["calibration_ok"] else 1
    report = run_rounds(args.rounds, resolver, out_root)
    print(json.dumps({"units": report["units"], "rounds": report["rounds"],
                      "pages": report["pages_total"],
                      "hard_pass": report["summary"]["units_hard_pass"]},
                     ensure_ascii=False))
    return 0 if report["summary"]["units_hard_pass"] == report["summary"]["units_total"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
