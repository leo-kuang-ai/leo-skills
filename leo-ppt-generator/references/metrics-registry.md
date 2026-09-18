# 运行质量指标注册表

唯一聚合实现为 `runtime/src/leo_ppt_generator/quality_metrics.py`。所有消费者必须复用该实现，不从生产方式或历史缺失记录推断纠错与零成本。

| metric_id | formula | source | caliber_version | consumer | missing_policy | observation_window | evidence_level |
| --- | --- | --- | --- | --- | --- | --- | --- |
| tf_trigger_rate | K/(K+N)；另报 K/N/U/T、覆盖率 (K+N)/T、全目标范围 [K/T,(K+U)/T] 及事件次数 | quality-event-v1 的 tf 事件；目标页集须在选 lane 前固定 | tf-caliber-v2 | quality scorecard、backend report、R-70 | 无完整观察的页归 U；T=0 为 not_applicable；U>0 为 blocked | 显式 run_id + window；触发后成功不消除 K | recorded-events；synthetic 被排除并单列身份；不是用户收益证据 |
| observed_cost | 按真实 call_id 去重的金额和；币种与价格版本分桶；跨页等分并由最后一页接收尾差 | quality-event-v1 的 call 事件及可核验 provider 收费凭据 | cost-caliber-v2 | quality scorecard、backend report、R-70、R-74 | 缺金额/币种/价格版本列入 unknown_calls；缺身份的历史记录不可补造；未证明计费窗口完整仅 partial 或 blocked | 与 TF 相同固定窗口，开发和生产阶段须由窗口隔离；失败与重试收费均计入 | recorded-events；不是账单完整性证明；估算另列 |
| user_rework_rounds | 同 phase/feedback_id 的 received、revised、presented 全部存在计一轮；涉及多页不增轮次 | quality-event-v1 的用户 rework 事件 | rework-caliber-v1 | quality scorecard、北极星观测 | 无反馈为 not_yet_observed；不完整/取消分别列出；窗口未关闭保持 partial；自动 QA 和模型代审不计入 | 显式 run_id + window；phase 固定为该反馈开始时的生产授权阶段 | recorded-events；构造回放不证明返工改善 |

## 事件与对账边界

- `event_id` 冲突和 `call_id` 载荷冲突均报错，不选择任意一条记录。
- `source=synthetic` 只用于回放与测试，默认聚合排除并返回 `excluded_synthetic_events`，不得补齐真实窗口。
- `tokens` 是调用累计用量，不能再次乘 `attempts`，也不能在缺少计费分类和价格版本时直接换算实测金额。
- 当前聚合器尚无完整计费/反馈窗口的关闭凭据消费接口，因此 `window_complete=false`。这限制真实效果准入，不将缺失强制转换成零。
- 每个反馈和调用身份固定使用首次登记阶段；聚合器拒绝跨阶段复用身份。只记录必要枚举及身份，不复制业务正文。

## 只读消费者

`scripts/run_quality_scorecard.py <run>` 与 `leo-ppt backend report <run>` 共用 `scorecard_for_run`。前者默认只向 stdout 输出 JSON；`--out <run>/scorecard/quality-scorecard.json` 使用固定目录描述符原子替换，只允许这一输出路径，拒绝符号链接。观测缺失为结构化 blocked，文件损坏为退出码 2，不静默跳过中断行。

输入为 `<run>/observability/quality-window.json`（`schema_version: 1`、非空 `run_id`、`window`、唯一字符串数组 `target_pages`，可选 `phase`，默认 `after-authorization`）和同目录 `quality-events.jsonl`。窗口必须由生产写方在选 lane 前冻结；消费者不创建窗口、不从 manifest 补造身份，也不回写历史输入。

主指标只统计选定 phase，`cost_by_phase` 分列开发、生产授权前与授权后费用；不会把开发盲评费用加进生产费用。测试夹具的文件流验证只证明消费者机制，不构成真实 provider 运行证据。

## 事件写入口与封存

- 在新 run 的页级 lane 准备前执行 `leo-ppt quality start <run> --window <id> --target-pages <pages.json> --phase after-authorization`；pages.json 是目标页身份字符串数组。已有 prepare/layout-selection 不允许补造早期窗口；相同窗口可幂等重放，改变目标必须创建新 run。
- `leo-ppt quality record <run> --event <event.json>` 消费 quality-event-v1：真实 provider 调用与收费重试按实际 call_id 登记；来源不明不得用操作号或时间伪装真实调用身份。用户反馈按 received→revised→presented 记录，取消单列；状态不可倒退，重复事件不增轮次。
- `image record --fallback-event TF-1|TF-2 --generation-method image|render|composite` 在显式实际纠错时写事件。没有旗标的 `--rework` 不推断 TF；失败生成也应由调用写方在触发时通过 quality record 登记，不能只统计最后成功页。
- `render page --run-dir <run> --page-id <id> --operation-id <id>` 由真实确定性渲染成功路径自动记录正常 render 的完整页观测。三个参数须同时提供。旧调用不启用观测时保持兼容，不从旧产物补登历史事件。
- `leo-ppt quality close <run>` 固定窗口与事件流 SHA256；之后只允许已有事件重放，新增事件被拒。只读报告以同一次读取的字节核对封存，篡改或并发变化不输出错误的可信合计。关闭不证明账单完整，未观察页仍为 U；成本完整性仍须独立账单证据，当前保持 window_complete=false。
- `evals/fixtures/quality-replay-v1/manifest.json` 固定两页真实离线渲染、内容包、输入、事件及期望报告的 SHA，消费者测试固定 manifest hash。它证明本地采集链，不代表收费 image 路径、人工视觉协议或用户返工收益。
