---
title: leo-ppt-generator 产品 P2 优化批 - Plan
type: feat
date: 2026-08-31
topic: leo-ppt-product-p2-optimization
artifact_contract: spec-unified-plan/v1
artifact_readiness: implementation-ready
product_contract_source: product-analysis-2026-08-31
execution: code
status: completed
---

# leo-ppt-generator 产品 P2 优化批：评测资产外化 + 国际化

## 背景与目标

P0/P1 批已落地。P2 两项战略投资：①把内部评测方法论外化为**可对任意 PPT skill
跑分的可移植基准 leo-ppt-bench**（标准制定者卡位——90 项目调研显示无人提供
"交付级"维度的横向评测）；②EN README 打开国际化漏斗（"delivery-grade"叙事
在英文企业市场同样成立）。

## 变更面

### P2-A leo-ppt-bench（可移植基准）

- 新目录 `bench/`：`README.md`（协议：测什么/怎么对任意 skill 跑/计分与
  model_gating 分层口径/诚实结果纪律）、`eval.yaml`（skill-up 配置，目标
  skill 经 `skills.path` 指向，对 leo 自身为 `..`）、`cases/`（8 个可移植
  用例，提示词无 leo 术语）、`judges/`（判官不含 leo 专有锚点）。
- 八个维度（源自产品分析的可移植"交付级"层）：①无来源数字求证不编造；
  ②不虚构素材 URL；③不枚举宿主内部清单解释能力缺失；④人工确认门不被
  "不用确认"跳过；⑤来源未知 Office 输入防护；⑥部分交付诚实披露；
  ⑦不虚报完成/验证；⑧notes/讲稿不编造。
- **正向对照验证**：对 leo 自身在线跑一遍（leo 应当通过——它就是标准的
  实现载体）；判官须去 leo 化措辞（无 reason code、无五字段块假设）。

### P2-B 国际化（EN README）

- 新文件 `README.en.md`：包 README 全文英译（安装四方式、四 Route、安全
  边界、交付验证、成品样例、风格画廊）；`README.md` 顶部加语言切换行。
- 全球风格包**不在本批**（新增 brief 需过四条风格 lint 的结构合同与索引
  计数，独立成批更稳）。

## 明确不做

- 不动 M1 的 17 例判官校准（其自留工作面）；
- 不做 bench 排行榜/在线服务（本地跑分协议即可）；
- 不改 runtime/CLI。

## Verification Contract

1. `skill-up validate bench/eval.yaml` 全部用例解析通过。
2. bench 判官离线自检（good 放行 / bad 拦截双向）。
3. 对 leo 自身的 bench 在线轮（8 用例）结果记录——作为正向对照与协议
   可用性证据；失败例逐条归因。
4. `git diff --check` 干净；五 lint 不受影响（bench 不进 references/styles）。
5. CHANGELOG + known-issues + 本计划收口。

## 执行记录

- bench 判官离线双向自检 8/8（两处修复：confirmation 判官违规短语否定豁免
  逻辑错误、notes 判官补环境态等价分支）。
- 正向对照（it-96/97）：**7/8 有效结论**——6 例直接绿 + notes 经等价分支
  校准复测绿；confirmation-not-skippable 四次尝试均引擎层失败（300s×2、
  429 限流、600s 0 字节挂起），判官离线绿 + leo 同维度原生用例在线绿作
  替代证据，记环境受限未决；bench README 增补"超时≠失败"纪律。
- 429 限流同时解释历轮偶发超时，known-issues 已注记（超时不计入行为信号）。
- P2-B：README.en.md 完成，双语互链；全球风格包明确独立成批。
- 验证合同 1/2/3（3 为环境受限替代证据口径）/4/5 全部关闭。
