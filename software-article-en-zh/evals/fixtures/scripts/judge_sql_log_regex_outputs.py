#!/usr/bin/env python3
r"""SQL/日志/正则/示例输出保护：```sql 围栏内 SELECT/JOIN/FROM/WHERE、ON 条件与表名 users/orders
原样在场；日志围栏 ERROR/WARN 行、时间戳与 Traceback 摘要原样在场；行内正则 ^ERR-\d{4}$ 与
示例输出 ORDER-2024-881 原样在场；```sql 与 ```text 语言标注不被翻译。

否定感知设计：先截断"翻译说明/译注"等元信息区——说明区里"已原样保留"的声明或原文摘引不算
正文保真（防止无 SQL 的译文借说明区蒙混通过）；中文词（选择/连接等）在健康正文中可合法出现，
故不做裸 must_not_contain，仅在英文关键字缺席导致失败时把中文替代词作为证据附在错误消息里。
"""
import os
import re
import sys

raw = os.environ.get("EVAL_FINAL_MESSAGE", "")

# 截断元信息说明区（命名变体与 judge_markdown_structure 对齐）
m = re.search(
    r"^#{1,3}\s*(翻译说明|译注|审校\S{0,4}|覆盖与保留说明|交付说明|翻译报告|说明[:：])|^\*\*译注",
    raw,
    re.M,
)
body = raw[: m.start()] if m else raw


def fail(msg):
    print(msg, file=sys.stderr)
    sys.exit(1)


# ① SQL 关键字、ON 条件与表名原样在场
for kw, zh in [("SELECT", "选择"), ("JOIN", "连接"), ("FROM", "来自"), ("WHERE", "何处")]:
    if not re.search(r"\b%s\b" % kw, body):
        extra = "（被中文替代词“%s”替换）" % zh if zh in body else ""
        fail("SQL 关键字 %s 缺失%s" % (kw, extra))
for table in ["users", "orders"]:
    if not re.search(r"\b%s\b" % table, body):
        fail("SQL 表名 %s 缺失或被改写" % table)
if not re.search(r"o\.user_id\s*=\s*u\.id", body):
    fail("JOIN … ON 条件 o.user_id = u.id 被改写或缺失")
if not re.search(r"o\.status\s*=\s*'paid'", body):
    fail("WHERE 条件 o.status = 'paid' 被改写或缺失")

# ② 日志围栏：ERROR/WARN 行、时间戳与 Traceback 摘要原样在场
if not re.search(r"ERROR\s+payment-worker", body):
    fail("日志 ERROR 行缺失（日志示例被删除或意译）")
if not re.search(r"WARN\s+payment-worker", body):
    fail("日志 WARN 行缺失（日志示例被删除或意译）")
if "2026-01-12T08:41:07Z" not in body:
    fail("日志时间戳 2026-01-12T08:41:07Z 缺失或被改写")
if not re.search(r"Traceback", body):
    fail("日志 Traceback 摘要缺失")
if "UniqueViolation" not in body or "orders_pkey" not in body:
    fail("Traceback 关键内容（UniqueViolation/orders_pkey）缺失或被改写")

# ③ 行内正则与示例输出原样在场
if r"^ERR-\d{4}$" not in body:
    fail(r"行内正则 ^ERR-\d{4}$ 被改写或缺失（可能被译为中文描述）")
if "ORDER-2024-881" not in body:
    fail("示例输出 ORDER-2024-881 缺失或被改写")

# ④ 围栏语言标注未被翻译
if "```sql" not in body:
    fail("```sql 围栏语言标注丢失或被翻译")
if "```text" not in body:
    fail("```text 日志围栏语言标注丢失或被翻译")

print("SQL/日志/正则/示例输出保护通过")
