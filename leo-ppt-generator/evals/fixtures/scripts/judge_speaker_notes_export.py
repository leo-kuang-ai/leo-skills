#!/usr/bin/env python3
# Judge for "speaker-notes-export-offered": the reply must know the speaker
# script export path (script name, PPTX/master sources), state that pages
# without notes are listed honestly and script text is never invented.
import os
import sys

text = os.environ.get("EVAL_FINAL_MESSAGE", "")


def fail(reason):
    print(reason, file=sys.stderr)
    raise SystemExit(1)


def require_any(values, what):
    if not any(v in text for v in values):
        fail(f"缺少{what}: {' / '.join(values)}")


require_any(("export_speaker_notes", "speaker_script", "speech.md", "讲稿"), "讲稿导出通道")
require_any(("--pptx", "PPTX notes", "成品", "母版", "--master"), "导出来源（成品/母版）")
require_any(("无备注", "缺备注", "缺失", "如实列出", "不编造", "不得编造"), "缺备注诚实边界")
