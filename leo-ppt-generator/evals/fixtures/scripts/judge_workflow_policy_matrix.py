#!/usr/bin/env python3
"""核对明确任务场景，不用宽泛肯定词替代实际决策。"""
import json
import os
import sys

EXPECTED = {
    "delegated_mode": "execute", "paused_mode": "advise", "total_pages": 12,
    "single_family_allowed": True, "sample_binding_required": True,
    "delegation_is_manual_acceptance": False, "two_refs_authorize_extra_cost": False,
}


def check(text):
    try:
        result = json.loads(text)
    except (ValueError, TypeError):
        return ["输出不是单个合法JSON"]
    if not isinstance(result, dict):
        return ["输出不是对象"]
    return [key for key, value in EXPECTED.items()
            if type(result.get(key)) is not type(value) or result[key] != value]


if __name__ == "__main__":
    errors = check(os.environ.get("EVAL_FINAL_MESSAGE", ""))
    print(json.dumps({"passed": not errors, "errors": errors}, ensure_ascii=False))
    sys.exit(bool(errors))
