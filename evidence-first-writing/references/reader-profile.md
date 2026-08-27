# 读者模型档案

与作者侧的 [voice-profiles.md](voice-profiles.md) 对称：那边积累「我们怎么说话」，这边积累「读者是谁、正在经历什么」。产品化写作把读者当用户经营，本文件是读者侧的持久档案合同。

## 档案结构

```yaml
identity: ""            # 谁在读：身份、圈层、语言习惯
knows: ""               # 已经知道什么（避免过度解释）
misunderstands: ""      # 真实存在的误解（必须附证据）
active_emotions: []     # 当下活跃的情绪（每条附证据与更新时间）
reading_context: ""     # 何时何地为何点开：通勤、深夜、被转发、检索
proof: []               # 每个字段的证据来源
status: provisional | verified
```

## 建立与更新规则

- 来源只有两个：作者明确提供（读者留言、社群讨论、后台数据的转述），或 `post-publish` 的 observation 积累（回流路径见 [content-assets.md](content-assets.md)）。不得凭「目标读者一般会……」脑补。
- `misunderstands` 与 `active_emotions` 两个字段必须有证据链——这是「反代入四问」（禁虚构读者认知）的正向建设：与其被动防止虚构读者，不如主动积累真实读者。
- 少于两个独立证据来源的档案只能标记 `provisional`；引用 provisional 档案写作时，编辑说明必须声明。
- 没有档案时按 brief 推断，并在编辑说明声明 `reader_model: inferred`；推断出的误解不得作为「替读者说蠢话再纠正」的开头素材。

## 使用位置

- `intent-routing.md` 的文章类型判断（读者任务维度）；
- [topic-momentum.md](topic-momentum.md) 四问的既有叙事与情绪证据；
- `editorial-pipeline.md` N7 读者承诺、N13 读者与平台测试。

持久化沿用 `personal-context` 的授权机制：明确授权 + 目标路径，默认 `persistence: not_run`，不得把写作请求推断为建档授权。
