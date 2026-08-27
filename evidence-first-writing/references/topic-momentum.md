# 选题势能与情绪定位

在 `editorial-pipeline.md` Node 2（选题与价值验证）读取本文件；`quick` 跳过，`standard` 四问各答一行，`deep` 输出完整 momentum card。产品化选题问的不是「这篇能不能写」，而是「这篇凭什么被点开、被读完、被转发」。

## 四问合同

1. **时机张力**：写出目标圈层近期正在讨论该问题的证据或场景（公共讨论、读者提问、行业事件）。写不出 → 诚实标记 `evergreen`，改走差异化检查；不得伪造讨论热度。
2. **既有叙事定位**：一句话写出读者脑中已有的叙事，再从 `强化 | 复杂化 | 推翻` 三选一。两句话写不出来，说明选题还没想清楚，先回 brief。
3. **势能类型**：`conflict`（冲突）/ `utility`（工具）/ `identity`（身份）/ `contrarian`（反常识）四选一，并说明该选题属于此型的理由。
4. **情绪定位**：从 `anxiety-relief`（焦虑缓解）/ `anger-voice`（愤怒代言）/ `resonance`（共鸣陪伴）/ `superiority`（信息差供给）/ `hope`（希望）五选一，并附**该情绪在目标圈层真实存在的证据**。没有证据 → 降级为纯信息型文章，不假装有情绪势能。

## momentum card

```yaml
timing: recent-discussion | evergreen
reader_narrative: ""
position: reinforce | complicate | overturn
momentum_type: conflict | utility | identity | contrarian
emotion: anxiety-relief | anger-voice | resonance | superiority | hope
emotion_evidence: ""      # 情绪真实性的证据来源，必填
author_disclosure: []     # 本篇实际使用的势能手段，进入编辑说明
```

## 情绪真实性门禁

情绪工程与反操纵红线的分界只有一条：**情绪命名 ≠ 情绪制造**。

- 把读者已有的感受精确说出来，是共鸣，合法；
- 虚构场景诱发本不存在的感觉，是操纵，禁止。

判据：

1. 开头三行的情绪共振必须指向 momentum card 声明的情绪，且该情绪有 `emotion_evidence` 支撑；
2. 全文情绪曲线遵循「命名 → 复杂化 → 给出口」三段；只唤起、不给出口（不提供下一步认知或行动）的焦虑文按操纵处理；
3. 情绪浓度随证据强度走：没有证据支撑的情绪段降低语气，而不是加码形容词。

## 与既有门禁的关系

本文件只做势能与情绪的判断，不改变证据、授权和因果门禁：情绪证据与讨论热度证据同受「不虚构」约束；`author_disclosure` 中的每个手段都必须出现在交付时的编辑说明里——披露的势能是编辑服务，隐瞒的才是操纵。势能承诺一律使用概率语言（提高被点开、读完、转发的概率），不承诺任何阅读量数字。
