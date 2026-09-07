#!/usr/bin/env python3
"""check_size_budget.py —— deck 尺寸预算确定性校验（加固方案 WS2）。

用法：
  python3 scripts/check_size_budget.py <run_dir> [--budget <content/size-budget.json>]

预算文件（可选，缺省按基准档）：
  {"canvas_ratio": "16:9", "image_lane_px": "2560x1440",
   "render_lane_px": "2560x1440", "editable_slide_in": [10.0, 5.625]}

校验（对 run 内已 recorded 页产物逐页读 PNG 头）：
  ① 全册画幅比例一致且等于 canvas_ratio（误差 0.01）——违反 FAIL
  ② render lane 页尺寸在 1280×720×整数 dsf 阶梯内——违反 FAIL
  ③ 图像 lane 页不得超过 image_lane_px 预算（渠道只能给更小档）——超过 FAIL；
     低于预算（渠道档受限）输出 WARN（须在交付披露注明）

退出码：0 通过（允许 WARN）；1 存在 FAIL；2 用法错误。
"""
from __future__ import annotations

import argparse
import json
import struct
import sys
from pathlib import Path

RENDER_LADLE_LOGICAL = (1280, 720)
DEFAULT_BUDGET = {
    "canvas_ratio": "16 / 9",
    "image_lane_px": "2560x1440",
    "render_lane_px": "2560x1440",
}


def _ratio(w: int, h: int) -> float:
    return w / h


def _png_size(path: Path) -> tuple[int, int]:
    header = path.read_bytes()[:24]
    if header[:8] != b"\x89PNG\r\n\x1a\n":
        raise ValueError(f"not a png: {path.name}")
    return struct.unpack(">II", header[16:24])


def _parse_px(value: str) -> tuple[int, int]:
    w, h = value.lower().split("x")
    return int(w), int(h)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("run_dir")
    parser.add_argument("--budget", default="")
    args = parser.parse_args()

    run = Path(args.run_dir).resolve()
    jobs_path = run / "image-deck" / "slide_jobs.json"
    if not jobs_path.is_file():
        print("FAIL: run 目录下无 image-deck/slide_jobs.json", file=sys.stderr)
        return 2
    jobs = json.loads(jobs_path.read_text(encoding="utf-8"))

    budget = dict(DEFAULT_BUDGET)
    budget_path = Path(args.budget) if args.budget else run.parent.parent / "content" / "size-budget.json"
    if budget_path.is_file():
        loaded = json.loads(budget_path.read_text(encoding="utf-8"))
        budget.update(loaded)
        print(f"budget: {budget_path.name} 已加载")
    else:
        print("WARN: 预算文件缺失，按基准档（2560x1440）校验")

    ratio_w, ratio_h = (int(v.strip()) for v in str(budget["canvas_ratio"]).split("/"))
    image_cap = _parse_px(str(budget["image_lane_px"]))
    ladder = {RENDER_LADLE_LOGICAL[0] * s: RENDER_LADLE_LOGICAL[1] * s for s in (1, 2)}

    fails: list[str] = []
    warns: list[str] = []
    checked = 0
    for slide in jobs.get("slides", []):
        if slide.get("status") != "recorded":
            continue
        artifact = run / slide.get("artifact", "")
        if not artifact.is_file():
            fails.append(f"{slide['slide_id']}: artifact_missing")
            continue
        try:
            width, height = _png_size(artifact)
        except (OSError, ValueError) as exc:
            fails.append(f"{slide['slide_id']}: artifact_unreadable: {exc}")
            continue
        checked += 1
        backend = str(slide.get("backend", ""))
        if abs(_ratio(width, height) - ratio_w / ratio_h) > 0.01:
            fails.append(
                f"{slide['slide_id']}: ratio_mismatch {width}x{height} "
                f"!= {ratio_w}:{ratio_h}"
            )
            continue
        if backend.startswith("render:"):
            if ladder.get(width) != height:
                fails.append(
                    f"{slide['slide_id']}: render_size_off_ladder {width}x{height}"
                )
        elif backend and backend not in ("render:html", "render:mermaid"):
            if (width, height) == image_cap:
                pass
            elif width > image_cap[0] or height > image_cap[1]:
                fails.append(
                    f"{slide['slide_id']}: image_exceeds_budget {width}x{height} > {image_cap[0]}x{image_cap[1]}"
                )
            else:
                warns.append(
                    f"{slide['slide_id']}: image_below_budget {width}x{height}（渠道档受限，交付披露须注明）"
                )

    for line in warns:
        print("WARN:", line)
    for line in fails:
        print("FAIL:", line)
    print(f"SUMMARY: checked={checked} fail={len(fails)} warn={len(warns)}")
    return 1 if fails else 0


if __name__ == "__main__":
    raise SystemExit(main())
