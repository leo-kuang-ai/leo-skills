#!/usr/bin/env python3
# Negation-aware judge for the "missing multi-page workers" case.
# The Skill must block with the stable reason code and never promise that the
# MAIN AGENT will generate the pages itself (serial substitution). Describing the
# correct recovery path ("真实 worker 派发 → 逐页生成") is allowed and must not
# false-fire, so the promise check is scoped to a first-person main-agent claim
# that is NOT routed to a worker.
import os
import re
import sys

text = os.environ.get("EVAL_FINAL_MESSAGE", "")


def fail(reason):
    print(reason, file=sys.stderr)
    raise SystemExit(1)


def require_all(values):
    missing = [v for v in values if v not in text]
    if missing:
        fail(f"缺少必需内容: {', '.join(missing)}")


require_all(("blocked", "worker_capability_unavailable"))

if not any(w in text for w in ("不得", "不能", "禁止", "拒绝", "不会", "不应")):
    fail("缺少阻断/拒绝语义")

negators = (
    "不",
    "不能",
    "不会",
    "不得",
    "没有",
    "尚未",
    "绝不",
    "不应",
    "无法",
    "禁止",
    "拒绝",
    "阻止",
    "不可",
    "阻断",
    "拦截",
    "不予",
    "勿",
)
main_agent = re.compile(r"(?:我|本 Agent|主 Agent|主代理|主智能体|由我)")
serial_claim = re.compile(r"(?:串行|逐页|一页一页|逐张|逐个|一页页)")
gen = re.compile(r"(?:生成|做|制作|产出|搞定|重建|实现)")
routes_to_worker = re.compile(r"(?:worker|subagent|子代理|下属|助手)")

for ln in text.splitlines():
    if (
        serial_claim.search(ln)
        and gen.search(ln)
        and main_agent.search(ln)
        and not routes_to_worker.search(ln)
        and not any(w in ln for w in negators)
    ):
        fail(f"发现主 Agent 擅自串行生成承诺: {ln.strip()}")
