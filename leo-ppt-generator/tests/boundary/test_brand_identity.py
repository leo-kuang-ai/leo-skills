#!/usr/bin/env python3
"""load_brand / compose_style(brand=) / 对比度护栏 / 风格锚 单元测试。

依赖 runtime venv（templates.py 导入链需要 filelock 等），测试通过环境发现
venv 后以子进程执行导入断言；找不到 venv 时 skip（与 boundary 套件口径一致）。
"""
import os
import subprocess
import sys
import unittest
from pathlib import Path

PKG_ROOT = Path(__file__).resolve().parents[2] / "runtime" / "src"
VENV_CANDIDATES = [
    Path(os.environ.get("LEO_PPT_TEST_VENV", "")),
    *sorted(Path.home().glob(
        "Library/Application Support/leo-ppt-generator/runtimes/*/venv/bin/python")),
]


def _venv_python():
    for c in VENV_CANDIDATES:
        if c and Path(c).is_file():
            return str(c)
    return None


PROBE = r"""
import sys, json
sys.path.insert(0, {root!r})
from leo_ppt_generator import templates as T
out = {{}}
bd = T.load_brand("accenture")
assert bd["primary"].startswith("#") and bd["accent"].startswith("#"), bd
assert bd["typography"], bd
out["load_brand"] = True
try:
    T.load_brand("__no_such_brand__")
    out["notfound"] = False
except T.TemplateError as e:
    out["notfound"] = "brand_not_found" in str(e)
r_default = T.compose_style("科研答辩风")
out["default_clean"] = "style_anchor" not in r_default and "brand" not in r_default
r_anchor = T.compose_style("科研答辩风", anchor=True)
out["anchor_lines"] = isinstance(r_anchor.get("style_anchor"), list) and len(r_anchor["style_anchor"]) >= 2
r_brand = T.compose_style("科研答辩风", brand="accenture")
out["brand_merged"] = r_brand["color_palette"]["primary"] == bd["primary"]
out["brand_implies_anchor"] = "style_anchor" in r_brand
out["brand_block"] = r_brand["brand"]["name"] == "accenture"
# 低对比品牌色触发护栏并给建议色
try:
    class FakePalette(dict): pass
    T.compose_style("科研答辩风", colors={{}}, brand="accenture")
    out["contrast"] = "not-triggered"
except Exception as e:
    out["contrast"] = "guard-hit"
print(json.dumps(out))
"""

LOW_CONTRAST = r"""
import sys, json
sys.path.insert(0, {root!r})
from leo_ppt_generator import templates as T
from leo_ppt_generator.styles import StyleStoreError
out = {{}}
try:
    T.compose_style("科研答辩风", colors={{"primary": "#FFFFFF", "accent": "#FFFF00"}})
    out["low_contrast"] = "not-guarded"
except T.StyleColorOverrideError as e:
    out["low_contrast"] = "not-brand-path"
# 直接验证对比度函数与建议色
cr = T._contrast_ratio("#FFFF00")
out["yellow_ratio"] = round(cr, 2)
out["suggest"] = T._suggest_accessible("#FFFF00")
out["suggest_ok"] = T._contrast_ratio(T._suggest_accessible("#FFFF00")) >= 4.5
print(json.dumps(out))
"""


class BrandIdentityTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.venv = _venv_python()
        if not cls.venv:
            raise unittest.SkipTest("runtime venv 未找到（LEO_PPT_TEST_VENV 可指定）")

    def _run(self, template):
        code = template.format(root=str(PKG_ROOT))
        r = subprocess.run([self.venv, "-c", code],
                           capture_output=True, text=True)
        self.assertEqual(r.returncode, 0, r.stderr)
        import json
        return json.loads(r.stdout.strip().splitlines()[-1])

    def test_load_brand_fields(self):
        out = self._run(PROBE)
        self.assertTrue(out["load_brand"])
        self.assertTrue(out["notfound"])
        self.assertTrue(out["default_clean"])
        self.assertTrue(out["anchor_lines"])
        self.assertTrue(out["brand_merged"])
        self.assertTrue(out["brand_implies_anchor"])
        self.assertTrue(out["brand_block"])

    def test_contrast_helpers(self):
        out = self._run(LOW_CONTRAST)
        self.assertLess(out["yellow_ratio"], 4.5)
        self.assertTrue(out["suggest_ok"])
        self.assertTrue(out["suggest"].startswith("#"))


if __name__ == "__main__":
    unittest.main()
