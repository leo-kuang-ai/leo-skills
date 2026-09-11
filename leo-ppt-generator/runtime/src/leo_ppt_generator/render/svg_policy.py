"""render/svg_policy.py：静态 SVG 子集策略（F2，方案 §7.3）。

本期图表只接纳结构化解析的静态 SVG 子集：拒绝脚本、事件、foreignObject、
外部 href、CSS import/url 与实体扩展；Mermaid 严格模式产物按同一子集校验。
不支持的输出明确失败，不静默删标签或图表。

正文注入用 textContent 等文本 API（模板合同）；本模块管 SVG 与静态资产。
"""

from __future__ import annotations

import re
import xml.etree.ElementTree as ET

from ..asset_resolver import ResolverError


class SvgPolicyError(ResolverError):
    reason_code = "svg_policy_violation"


# 允许的 SVG 元素（静态子集：形状/文本/组/渐变/裁剪/标记/标题）。
ALLOWED_ELEMENTS = {
    "svg", "g", "defs", "title", "desc", "path", "rect", "circle", "ellipse",
    "line", "polyline", "polygon", "text", "tspan", "style", "linearGradient",
    "radialGradient", "stop", "clipPath", "mask", "marker", "pattern", "use",
    "symbol", "title", "switch", "a",
}
# 属性允许集：呈现属性 + 常用动画静止形态；style 只允许静态声明子串。
ALLOWED_ATTR_PATTERN = re.compile(
    r"^(id|name|class|d|x|y|x1|y1|x2|y2|cx|cy|r|rx|ry|width|height|transform|"
    r"fill|fill-opacity|fill-rule|clip-rule|stroke|stroke-width|stroke-opacity|stroke-dasharray|"
    r"stroke-linecap|stroke-linejoin|stroke-miterlimit|opacity|color|"
    r"font-family|font-size|font-weight|font-style|text-anchor|"
    r"dominant-baseline|alignment-baseline|letter-spacing|word-spacing|dx|dy|"
    r"gradientUnits|gradientTransform|spreadMethod|offset|stop-color|stop-opacity|"
    r"clip-path|clipPathUnits|mask|maskUnits|markerWidth|markerHeight|refX|refY|"
    r"orient|markerUnits|marker-start|marker-mid|marker-end|viewBox|"
    r"preserveAspectRatio|version|xmlns|xmlns:xlink|style|"
    r"patternUnits|patternContentUnits|points|tabindex|role|aria-label|aria-hidden|"
    r"aria-roledescription|data-[a-z0-9-]+)$"
    # data-* 是 mermaid 11 的纯元数据属性（data-edge/data-id/data-points），
    # 无执行语义；此前的白名单缺该前缀导致 flowchart 系全灭。
)
FORBIDDEN_ATTR_SUBSTRINGS = ("onerror", "onload", "onclick", "javascript:",
                             "expression(", "@import", "url(http", "url(https",
                             "url(//", "url(data:", "url(file:", "url(vbscript:",
                             "data:text/html")
def sanitize_svg(svg_text: str) -> str:
    """结构化解析 + 允许集过滤；违规即失败（不静默删标签）。"""
    if not isinstance(svg_text, str) or "<svg" not in svg_text:
        raise SvgPolicyError("svg_policy_violation: 输入不是 SVG 文本")
    if re.search(r"<!ENTITY|<!DOCTYPE", svg_text, re.I):
        raise SvgPolicyError("svg_policy_violation: 实体扩展/DOCTYPE 被拒绝")
    try:
        parser = ET.XMLParser()
        root = ET.fromstring(svg_text, parser=parser)
    except ET.ParseError as exc:
        raise SvgPolicyError(f"svg_policy_violation: SVG 解析失败 ({exc})") from exc
    _check_element(root)
    ET.register_namespace("", "http://www.w3.org/2000/svg")
    return ET.tostring(root, encoding="unicode")


def _check_element(element: ET.Element) -> None:
    tag = element.tag.split("}")[-1] if isinstance(element.tag, str) else ""
    if tag not in ALLOWED_ELEMENTS:
        raise SvgPolicyError(f"svg_policy_violation: 元素 <{tag}> 不在静态子集")
    for name, value in element.attrib.items():
        bare = name.split("}")[-1]
        if bare.startswith("on") or bare == "href" or bare.endswith(":href"):
            if bare.startswith("on"):
                raise SvgPolicyError(f"svg_policy_violation: 事件属性 {name}")
            href = value.strip()
            # Static SVG may only link to an in-document fragment; every
            # non-empty URL scheme and relative resource reference is unsafe.
            if href and not href.startswith("#"):
                raise SvgPolicyError(
                    f"svg_policy_violation: 外部 href {value!r} 被拒绝")
            continue
        if not ALLOWED_ATTR_PATTERN.match(bare):
            raise SvgPolicyError(f"svg_policy_violation: 属性 {name} 不在允许集")
        lowered = str(value).lower()
        for forbidden in FORBIDDEN_ATTR_SUBSTRINGS:
            if forbidden in lowered:
                raise SvgPolicyError(
                    f"svg_policy_violation: 属性 {name} 含被拒内容 {forbidden!r}")
        if bare == "style" and ("@import" in lowered or "url(" in lowered):
            raise SvgPolicyError("svg_policy_violation: style 内 CSS url()/import 被拒绝")
        if "font-family" == bare and ("url(" in lowered or "src:" in lowered):
            raise SvgPolicyError("svg_policy_violation: font-family 内嵌资源被拒绝")
    if element.text:
        text = element.text.lower()
        if re.search(r"<script|javascript:", text):
            raise SvgPolicyError("svg_policy_violation: 文本节点含脚本")
        # CSS lives in the text node of <style>, so attribute-only checks do
        # not protect it. External CSS and resource URLs are outside the
        # static SVG contract even when the style element itself is allowed.
        if tag == "style" and re.search(r"@import|url\s*\(", text):
            raise SvgPolicyError("svg_policy_violation: CSS 外链 @import/url 被拒绝")
    for child in element:
        _check_element(child)


def sanitize_chart_output(svg_text: str, *, dialect: str = "mermaid") -> str:
    """图表（Mermaid 严格模式等）输出按静态子集校验。"""
    # 使用元素/属性结构校验，普通标签里的配置名不具有执行语义。
    return sanitize_svg(svg_text)
