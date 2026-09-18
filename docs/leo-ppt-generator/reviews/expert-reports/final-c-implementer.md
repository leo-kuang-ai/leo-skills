# 终审 C · 实现方验收（仅凭文档能否开工）

- 对象：PRD v1.5 · 立场：从未参加前三轮评审的实现工程师，仅凭 PRD 开工（禁读 reviews/）
- 日期：2026-09-11 · 独立审查（含源码抽验 11 条）

## R-77 动作清单（照文档会怎么做，11 项）

TF-2 标记走 a′（argparse store_true＋`_append_backend_stats`，插入点 cli.py 3625/2845）；不写 canonical entry；top2 修复（`allocate_deck` 用纯 `_soft_rank` 序）；导出同一排序函数契约供 R-71；**绑定对象持久化——需要新入口，文档未给**；runs_fixture 扩展；债5 容错与回归；**指标注册表——文档未给路径/格式/入口**；TF 口径页级去重＋分母回退；收编 10 项观察指标（北极星需先定义 schema）；红绿＋分 commit。
**被迫去猜/翻别处的点**：动作 5、8、9、10 无落点；动作 2/6/7 有约束无归属；动作 3 发现仓库已有**第二套** top2 实现（`scripts/suggest_layout.py` 的 `TOP_CANDIDATES=2`＋加权），文档说「二选一」未说选哪个。

## 前置声明抽验（11 条）

**一致 10 条**：TF-2 无写入方且 canonical state_hash 封死手补（adapter.py 170-171/225-226 实测）；`--backend` 默认 fixture＋page_type 三枚举＋tokens 自报；run-ledger 双写入方 schema 不兼容（**实测复现 TypeError**）；无 image dispatch 命令；top2 是 asset_id 序（docstring 自称推荐摘要与实现脱节）；A8 三条陷阱逐条吻合（早退先于 profiles 构建、`_selection_result` 无 profiles 入参、`_soft_rank` 纯函数）；债3 GATE_ORDER 零引用＋债4 仅测试消费；`estimate_run_cost` 无 lane 维度；15 模板 lint 15/15＋99 个 judge＋五类指纹＋OCR 三读者；`previews/` 与五类指纹零冲突。
**不一致 1 条（关键）**：**§1.5 未登记 `page_intent.py` 与 `page-type-regime-v1.json`**（二者已存在且在消费）——而 §4 R-70c 把 `page_type_regime` 列为待建、A6 只给「schema 草案」；按文档做 R-70c 会从零重造既有件。

## 阻塞分级

**A（不开工无法推进）**：A1 R-77 交付物无入口/路径/格式（全文无命令名或文件名）；A2 最小子集的一半「成本对账」无公式无数据源，且 §8 清单里根本没有成本项（与 §4 自相矛盾）；A3 指标注册表无 schema 无位置（验收 3 无可断言对象）。
**B（开工后早期阻塞）**：B1 a′/manifest 二选一未授权未指定登记位置（仓库有现成载体 `scripts/decision_log.py` 未被引用）；B2 绑定对象持久化无生成命令（`image prepare --layout-selection` 只消费，`allocate_deck` 生产路径零调用）；B3 `_soft_rank` 复用范围未定；B4 债5 修复归属方向未定（两侧分属不同所有权边界）；B5 TF 分子在两口径间分叉；B6 北极星列入范围但 schema 未定义且未说是否属最小子集；B7 §1.5 基线遗漏 page_intent/regime；B8 R-78 拼图落盘路径未给（若选 `reports/render-preview/` 将自撞指纹）。
**C（可自行判断）**：fixture 复用、旗标命名、枚举目标值、输出形态、测试命名、CHANGELOG 同步。

## Findings（12 项）

G3-1 blocker R-77 交付物无入口/路径/格式（含建议：`scripts/run_quality_scorecard.py <run>`＋`references/metrics-registry.md`）；G3-2 blocker 成本对账无公式与数据源且与 §8 矛盾；G3-3 blocker 注册表无 schema/位置/样例（建议新增附录 A10）；G3-4 major a′/manifest 未授权（建议默认 a′＋决策记 `decision-log.md`）；G3-5 major 绑定对象持久化无生成命令（建议 `image allocate` 子命令）；G3-6 major §1.5 基线遗漏 page_intent/regime 并与 R-70c/A6/§9-8 冲突；G3-7 major R-78 路径缺失（建议 `<run>/diffs/`）；G3-8 major 债5 修复方向（建议 runtime 侧改 str＋schema_version，agent 侧加容错）；G3-9 major TF 分子分叉（建议 manifest 优先、sidecar 回退、标注 tf_source）；G3-10 major `_soft_rank` 与 `suggest_layout` 关系未裁决；G3-11 minor 北极星波次归属；G3-12 minor 成本对账口径版本无登记载体。

## 结论

**需补文档后才能开工。** 必需补充：G3-1/G3-2/G3-3（缺一即无法交付 R-77 最小子集）。建议同批：G3-4~G3-10、G3-7。
事实补充（不含建议）：v1.5 的**条目完整性**成立（R-75/76/78/79/80/82/83 与 §7 四要素已恢复、无占位残留）；但**基线事实层**仍不自包含——§1.5 的 11 条声明逐条与源码一致，唯遗漏 page_intent/regime 这一既存实现。A8/A9 的实施线索与源码逐一吻合，可照做。
