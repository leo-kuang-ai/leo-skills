"""风格库多行业/多场景渲染确定性矩阵测试。

全库 137 份 brief 的 palette HEX 锚点与身份字族收敛完成后，以下性质
对**每个**可加载风格成立，本测试按轴抽样 20 份代表风格固化断言：

1. **确定性**：同输入两次 ``compose_style`` 结果完全相等（快照合同）；
2. **配对注入**：输出含非空 ``image_rendering``（配对表 137/137 全覆盖
   的行为层验证——任何风格都有渲染锚，不静默缺失）；
3. **护栏锚点**：``guardrail=True`` 时含「accent 锚点：#RRGGBB」行
   （palette 四角色全 HEX 后的必现性质）;
4. **风格锚附录**：``anchor=True`` 时注入 ``style_anchor``。
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

SKILL_DIR = Path(__file__).resolve().parents[1]
RUNTIME_SRC = SKILL_DIR / "runtime" / "src"
if str(RUNTIME_SRC) not in sys.path:
    sys.path.insert(0, str(RUNTIME_SRC))

from leo_ppt_generator.templates import compose_style  # noqa: E402

# 按轴抽样：顶层内置 / 01 五子类 / 02 六行业 / 03 四场景 / 05 借鉴。
SAMPLED_STYLES = (
    "清爽专业风",
    "手绘白板风",
    "科研答辩风",
    "麦肯锡咨询风",
    "玻璃拟态风",
    "包豪斯风",
    "蒸汽波风",
    "水墨禅意风",
    "医院品牌风",
    "银行年报风",
    "人工智能大模型风",
    "智能制造风",
    "学术期刊风",
    "时尚品牌风",
    "高管汇报风",
    "融资路演风",
    "知识卡片风",
    "年会庆典风",
    "写实摄影风",
    "历史古风题材风",
)


class StyleMatrixTest(unittest.TestCase):
    def test_every_sampled_style_is_loadable(self):
        for name in SAMPLED_STYLES:
            with self.subTest(style=name):
                composed = compose_style(name)
                self.assertEqual(composed["name"], name)

    def test_same_input_twice_is_identical_across_matrix(self):
        for name in SAMPLED_STYLES:
            with self.subTest(style=name):
                first = compose_style(name, guardrail=True, anchor=True)
                second = compose_style(name, guardrail=True, anchor=True)
                self.assertEqual(first, second)

    def test_every_sampled_style_has_paired_rendering(self):
        for name in SAMPLED_STYLES:
            with self.subTest(style=name):
                composed = compose_style(name)
                self.assertTrue(
                    composed.get("image_rendering"),
                    f"{name} 缺少配对图片渲染（image_rendering 为空）",
                )

    def test_guardrail_carries_accent_anchor_for_every_style(self):
        for name in SAMPLED_STYLES:
            with self.subTest(style=name):
                lines = compose_style(name, guardrail=True)["guardrail"]
                self.assertTrue(
                    any("accent 锚点：#" in line for line in lines),
                    f"{name} 的 guardrail 缺少 accent HEX 锚点行",
                )

    def test_anchor_block_injected_when_requested(self):
        for name in SAMPLED_STYLES:
            with self.subTest(style=name):
                composed = compose_style(name, anchor=True)
                self.assertIn("style_anchor", composed)
                self.assertTrue(composed["style_anchor"])


if __name__ == "__main__":
    unittest.main()
