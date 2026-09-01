#!/usr/bin/env python3
"""style-brief-v1.schema.json 结构契约测试（机制线 M1）。

chart_smart 槽（源 presentation-ai smartLayout 七语义槽）进
token_sidecar.palette：断言 JSON 可解析、新槽 pattern 与核心键一致、
纯增量不破坏既有键与 additionalProperties 放行口径。"""
import json
import unittest
from pathlib import Path

SCHEMA_PATH = (
    Path(__file__).resolve().parents[1]
    / "runtime" / "src" / "leo_ppt_generator" / "schemas"
    / "style-brief-v1.schema.json"
)
HEX_PATTERN = "^#[0-9A-Fa-f]{6}$"


class StyleBriefSchemaTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))

    def test_schema_parses_as_draft7_json(self):
        self.assertEqual(
            self.schema["$schema"],
            "http://json-schema.org/draft-07/schema#",
        )
        self.assertEqual(self.schema["$id"], "style-brief-v1.schema.json")

    def test_palette_declares_chart_smart_slot(self):
        palette = self.schema["properties"]["token_sidecar"]["properties"][
            "palette"
        ]
        chart_smart = palette["properties"]["chart_smart"]
        self.assertEqual(chart_smart["type"], "string")
        self.assertEqual(chart_smart["pattern"], HEX_PATTERN)
        # Semantic provenance must be documented in the slot description.
        self.assertIn("smartLayout", chart_smart["description"])

    def test_chart_smart_keeps_core_five_keys_intact(self):
        palette = self.schema["properties"]["token_sidecar"]["properties"][
            "palette"
        ]
        for key in ("primary", "accent", "background", "surface", "text"):
            self.assertEqual(palette["properties"][key]["pattern"], HEX_PATTERN)

    def test_palette_extension_keys_still_pass_through(self):
        # chart_smart is a documented slot, not a gate: additionalProperties
        # must keep allowing extended hex keys (social-card 8-token precedent).
        palette = self.schema["properties"]["token_sidecar"]["properties"][
            "palette"
        ]
        self.assertEqual(
            palette["additionalProperties"],
            {"type": "string", "pattern": HEX_PATTERN},
        )

    def test_chart_smart_is_optional(self):
        # Pure additive slot: token_sidecar palette must not list chart_smart
        # (nor any palette key) as required.
        palette = self.schema["properties"]["token_sidecar"]["properties"][
            "palette"
        ]
        self.assertNotIn("required", palette)
        self.assertNotIn("chart_smart", self.schema["required"])


if __name__ == "__main__":
    unittest.main()
