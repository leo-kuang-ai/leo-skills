# 质量观测回放 v1

2026-09-11 使用正式 `run create` → `quality start` → 两次 `render page --run-dir ... --page-id ... --operation-id ...` → `quality close` 生成。页图为本地 Playwright/离线字体真实输出，页面内容是构造的工程说明。事件 source=runtime 来自实际渲染写方，未填造用户反馈或收费调用。

本基线验证 TF K=0/N=2/U=0、观测封存及只读聚合；费用 blocked、用户返工 not_yet_observed。它不证明视觉偏好、返工收益、真实 image 路径或完整账单。模板与数据的实际 SHA 保留于来源凭据；只剔除了机器路径和时间。

输入与期望输出的固定 SHA 在 manifest.json；消费者为 tests/test_quality_observation.py。已有版本不得原地更新，后续回放新增版本。
