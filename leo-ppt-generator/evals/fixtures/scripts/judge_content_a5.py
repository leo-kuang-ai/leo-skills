#!/usr/bin/env python3
"""跨行业内容质量测评 · L1 判官入口 A5（风格与版式选择（合同层））。引擎见 judge_content_common.py。"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import judge_content_common as jcc  # noqa: E402

if __name__ == "__main__":
    raise SystemExit(jcc.main_for(
        "A5", f"L1 判官 A5（风格与版式选择（合同层））：匿名包 → 双家族之一单维度评审"))
