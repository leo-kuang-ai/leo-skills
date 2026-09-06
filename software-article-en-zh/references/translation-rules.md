# 翻译规则

优先保持技术事实、结构和规范性语义，再处理中文自然度。`not guaranteed` 保持“不保证”；`at most`/`at least` 保持上下界；`only if`、`if`、`unless` 按条件关系翻译；MUST/SHOULD/MAY 按规范语义处理。数字后的单位分两类：符号、指标与量纲形态（`ms`、`GiB`、`MB/s`、`QPS`、`p99`、`GB`）默认原样保留，不换算、不替换；英文单词形态的单位词（hours、cores、threads、days）按中文习惯译出（小时、核、线程、天），中文数词量词（四核、两倍）合法。需要解释时保留原符号并另加中文说明。可能性情态（can/may）不得强化为确定性（“会”“将”）；程度强化词（far、much、significantly）不得丢失。不得把相关性改为因果，不得静默修正原文错误。原文的拼写错误（如 recieve/seperate）保留原拼写或附译者注指出，不得静默改对。

## 数值方向、变化幅度与倍数

- `increase/decrease/reduce by X%` 是变化量，译“增加/降低了 X%”；`to X%` 是终点值，译“降至/升至 X%”。方向和 by/to 不得互换或省略。
- `X times faster` 统一按“速度为原来的 X 倍”处理（本技能约定口径，避免“快了 X 倍”的歧义）；`twice` 译“两倍”；`halve`/`cut in half` 译“减半”；`an order of magnitude` 译“一个数量级”。
- 比较方向不得颠倒：`A is faster than B` 必须保持 A 快于 B 的方向。

## 时态与版本演进

- `will be deprecated/removed in vX` 保留将来时标记（“将在 vX 中弃用/移除”），不得译成既成事实。
- `has been deprecated/replaced` 译“已弃用/已被替换”；`is being replaced` 译“正在被替换”。被动与施动者关系保留。

## 否定辖域与连接词

- 否定词 + `A or B` 的辖域覆盖整个析取：`does not support Windows or macOS` 译“既不支持 Windows 也不支持 macOS”，不得只否定第一项。
- `not all` 译“并非全部”；`none of` 译“没有一个/均不”；`only` 的辖域随句中位置变化，需逐位核对（`supports only X` 与 `only supports X` 强调点不同）。
- `and/or` 保留双连形式“和/或”，或按上下文显式消歧，不得擅自二选一。

## 规范性情态的大小写分流

- 大写 MUST/SHOULD/MAY/SHOULD NOT/MUST NOT 出现在规范类文本（RFC、标准、API 约定）时按规范语义译：MUST 必须、MUST NOT 不得、SHOULD 应当、SHOULD NOT 不应、MAY 可以（许可）。
- 小写 may/can 在一般语境按可能性处理（可能/可以），不得强化为确定性；句首 May 等无法区分时按上下文判定并在存疑时保持较弱解读。

## 缩写与首次展开

- 行业通用缩写首次出现时可附中文展开（如“服务等级目标（SLO）”），此后直接使用缩写；产品名与社区惯用缩写（K8s、CI）不强行展开。
- 展开只使用原文已有信息，不得借展开补充新事实。
