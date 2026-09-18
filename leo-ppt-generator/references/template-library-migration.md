# 模板库五阶段迁移

从技能目录使用项目 Python。delivery 是包含 `leo-ppt-generator/` 的 Git 根；
工作目录放在包内被忽略的 `.migration-work/<批次>/`。不直接改 catalog generation 文件。

```sh
PYTHONPATH=runtime/src runtime/.venv/bin/python scripts/migrate_template_library.py preview --source-root .. --out-plan .migration-work/batch/migration-plan.json
PYTHONPATH=runtime/src runtime/.venv/bin/python scripts/migrate_template_library.py stage --plan .migration-work/batch/migration-plan.json --staging-root .migration-work/batch/shadow
PYTHONPATH=runtime/src runtime/.venv/bin/python scripts/migrate_template_library.py verify --plan .migration-work/batch/migration-plan.json --staging-root .migration-work/batch/shadow --out-receipt .migration-work/batch/verified-receipt.json --visual-receipt .migration-work/batch/qa/visual-replay.json
PYTHONPATH=runtime/src runtime/.venv/bin/python scripts/migrate_template_library.py publish --plan .migration-work/batch/migration-plan.json --receipt .migration-work/batch/verified-receipt.json --delivery-root ..
PYTHONPATH=runtime/src runtime/.venv/bin/python scripts/migrate_template_library.py cleanup --plan .migration-work/batch/migration-plan.json --publication-receipt .migration-work/batch/publication-receipt.json --delivery-root ..
```

第一条在缺少 `--prerequisite` 时只生成 U7-A 合同基线，第二条会拒绝它。要形成 U7-B，
须在新的批次目录重跑 preview，并通过 `--prerequisite` 引用该证据根内的真实预迁移价值收据。
同批次计划唯一且不可覆盖；源、dirty、映射、目标摘要或 owner 发生变化后，重新建立前置证据及计划。

`migration-plan-v2.schema.json` 是正式计划合同。映射只允许 `copy`、库声明 `normalize`、
catalog `derived`；记录全部来源状态、目标 hash、固定 consumer closure roots 和精确删除清单。
未知字段、越界路径、链接、非法 mode 和来源不匹配均拒绝。
固定范围是十个消费者根加根 `CHANGELOG.md`。变更记录参与来源、目标、CAS 和最终
逐文件收敛；其中的历史路径仅作 provenance，不视为运行消费者。cleanup 不允许删除它，
也不允许用此例外纳入兄弟技能。

stage 创建独立 worktree，并用持久 journal 记录每个文件的写前状态。重试只接受本批次写入的
准确状态；shadow 中的新外部修改不能被覆盖。stage 不修改 delivery，也不自动取得发布资格。

verify 检查资产与附属字节、identity/reference、probe、v2 catalog、consumer closure、bundle
及 manifest，并重核真实 U6-A 回放。缺失、失败、stale 或未执行的门都不能签发 publication-ready。
publish 只接受同一 plan 的正式 verified receipt，重核 owner、前置价值证据、HEAD 和 dirty，
取得独占锁及持久 maintenance 后逐文件 CAS，保存原字节备份，最后切换 current。

互斥覆盖完整操作，而非只在入口检查标记。生成与渲染、resolver、catalog 构建和发布、
关系探针、用户风格保存及包导入/采用持库目录共享锁；迁移先取得同目录独占锁，
再写 maintenance。已在执行的消费者会使迁移返回 `migration_maintenance_lock_busy`，
此时不写维护标记；独占锁已取得而 marker 尚未落盘时，新消费者也返回
`library_in_maintenance`。目录锁不要求向只读安装写锁文件，异常和进程退出会释放它。
持久 marker 在发布进程退出后仍有效，只有正式恢复/cleanup 能解除；不得手动删除。
final receipt 的公开复核同样持共享锁，避免收敛检查与下一次发布交错。

cleanup 只处理 plan 绑定的 allowlist。每项重新核对路径、类型、symlink、hash；已经消失的
文件仅在本批 journal 已记录 prepared/deleted 时可恢复，回滚后再次消失按外部漂移拒绝。
最终检查 staging/delivery 摘要收敛、活动旧引用归零、完整 v2 views 与正式收据链。
最终收据持久化后才解除 maintenance；在两者之间中断时，重试重核最终收据后解除维护。

发布事务绑定 `transaction_id`、`base_revision` 和递增 `journal_generation`。目录同步失败
直接阻断；`prepared` 标记及原字节备份持久化后才替换文件，current 最后替换并同步，
随后保存 `current-switched` 确认标记，最后签发收据。缺少确认、标记与 journal 不同代或
摘要不符时不能签发收据或 cleanup。进程在确认前退出时只能按原字节恢复后重试。

cleanup 回滚保留原不可变发布收据，通过原 journal 恢复后可以重放同批 publish。
恢复写入递增 journal generation，旧 receipt 变为 `stale`；新的凭证存入
`publications/<transaction_id>/<journal_generation>/`，根 `publication-receipt.json`
通过 CAS 指向同字节的最新收据。正常同代重试保持幂等；已确认 marker 后、收据前的中断
不等于已取得发布资格。cleanup 和 final verify 都重新核对当代确认链。
恢复期间遇到外部字节变更会留下明确 conflict 和 maintenance，不能手改 journal 或删除 marker 强行继续。

这些命令不执行 Git commit、push 或 PR。五阶段工具和文件故障测试通过，不等于真实 delivery
已经迁移；正式发布仍需要价值门、U6-A、完整消费者切换和最终收敛证据。
