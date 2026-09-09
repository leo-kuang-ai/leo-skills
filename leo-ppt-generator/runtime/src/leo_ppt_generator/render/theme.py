"""render/theme.py：effective theme 计算（F3，方案 §7.0/§7.2）。

只处理校验、覆盖、角色解析；不重选风格、不合并品牌外的对象、不拥有几何。
阶段顺序（组合器调用）：选定 theme → mode 变体 → 品牌声明角色 → 任务视觉
覆盖（仅 overrideable_roles；品牌 locked_roles 不得改）。

覆盖语义：schema 白名单叶子路径赋值；未出现的键保持原值；null 不是删除
指令且非法；数组整体替换并验证元素。对比度硬检查：正文对背景 ≥4.5:1，
大字/强调 ≥3.0:1——不满足即拒绝，不静默放行。
"""

from __future__ import annotations

from ..asset_resolver import ResolverError

# 必查角色由模板声明；这里只定义"参与硬检查的油墨角色及其下限"。
# 方案口径：普通文字 ≥4.5:1，大字/信息标记 ≥3:1。边框等装饰性非文本
# 不设硬下限（视觉走 QA 档），避免误伤常规发丝线设计。
INK_FLOORS = {
    ("text", "background"): 4.5,
    ("on_primary", "primary"): 4.5,
    ("primary", "background"): 3.0,
    ("accent", "background"): 3.0,
    ("muted", "background"): 3.0,
}


class ThemeError(ResolverError):
    reason_code = "theme_invalid"


class ThemeOverrideError(ThemeError):
    reason_code = "theme_override_invalid"


class ThemeContrastError(ThemeError):
    reason_code = "theme_contrast_insufficient"


def _relative_luminance(hex_value: str) -> float:
    def chan(v: int) -> float:
        c = v / 255.0
        return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4

    r = chan(int(hex_value[1:3], 16))
    g = chan(int(hex_value[3:5], 16))
    b = chan(int(hex_value[5:7], 16))
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def contrast_ratio(fg: str, bg: str) -> float:
    l1, l2 = _relative_luminance(fg), _relative_luminance(bg)
    hi, lo = max(l1, l2), min(l1, l2)
    return (hi + 0.05) / (lo + 0.05)


def _is_hex(value: object) -> bool:
    if not isinstance(value, str) or len(value) != 7 or value[0] != "#":
        return False
    try:
        int(value[1:], 16)
    except ValueError:
        return False
    return True


def select_mode(theme: dict, mode: str | None) -> dict:
    """对选定 theme 应用其声明的 mode；未指定用默认；未知 mode 拒绝。"""
    modes = theme.get("modes") or {}
    if not isinstance(modes, dict) or not modes:
        raise ThemeError("theme_invalid: theme 无 modes")
    chosen = mode or theme.get("default_mode")
    if chosen not in modes:
        raise ThemeError(
            f"theme_invalid: mode {chosen!r} 未由该主题声明（可用: {sorted(modes)}）")
    return dict(modes[chosen])


def check_contrast(colors: dict) -> None:
    for (ink, base), floor in INK_FLOORS.items():
        fg, bg = colors.get(ink), colors.get(base)
        if not (_is_hex(fg) and _is_hex(bg)):
            continue
        ratio = contrast_ratio(fg, bg)
        if ratio < floor:
            raise ThemeContrastError(
                f"theme_contrast_insufficient: {ink} {fg} vs {base} {bg} "
                f"= {ratio:.2f}:1（下限 {floor}）")


def apply_brand(colors: dict, brand: dict | None) -> tuple[dict, list[str]]:
    """在当前 mode 上应用 brand 声明的色彩角色；locked_roles 由调用方并入。"""
    if not brand:
        return dict(colors), []
    brand_colors = brand.get("colors") or {}
    if not isinstance(brand_colors, dict):
        raise ThemeOverrideError("theme_override_invalid: brand.colors 非对象")
    locked = set(brand.get("locked_roles") or [])
    merged = dict(colors)
    applied: list[str] = []
    for role, value in sorted(brand_colors.items()):
        if role not in colors:
            raise ThemeOverrideError(
                f"theme_override_invalid: brand 角色 {role!r} 不在主题声明中")
        if not _is_hex(value):
            raise ThemeOverrideError(
                f"theme_override_invalid: brand.{role}={value!r} 非 #RRGGBB")
        merged[role] = value
        applied.append(role)
    return merged, applied


def apply_overrides(colors: dict, overrides: dict | None, theme: dict,
                    *, locked_roles: set[str] | None = None) -> dict:
    """任务视觉覆盖：仅限 theme 声明的 overrideable_roles；locked_roles 拒绝。"""
    if not overrides:
        return dict(colors)
    allowed = set(theme.get("overrideable_roles") or [])
    locked = set(locked_roles or [])
    merged = dict(colors)
    for role, value in sorted(overrides.items()):
        if role in locked:
            raise ThemeOverrideError(
                f"theme_override_invalid: 角色 {role!r} 被品牌锁定，任务覆盖拒绝")
        if role not in colors:
            raise ThemeOverrideError(
                f"theme_override_invalid: 角色 {role!r} 不在主题声明中")
        if role not in allowed:
            raise ThemeOverrideError(
                f"theme_override_invalid: 角色 {role!r} 不可覆盖"
                f"（overrideable_roles: {sorted(allowed)}）")
        if value is None:
            raise ThemeOverrideError(
                f"theme_override_invalid: {role}=null；null 不是删除指令")
        if not _is_hex(value):
            raise ThemeOverrideError(
                f"theme_override_invalid: {role}={value!r} 非 #RRGGBB")
        merged[role] = value
    return merged


def apply_font_overrides(fonts: dict, overrides: dict | None, theme: dict) -> dict:
    """字体角色叶子覆盖（family/weight/size/line_height）；null 拒绝。"""
    if not overrides:
        return {role: dict(defn) for role, defn in fonts.items()}
    merged = {role: dict(defn) for role, defn in fonts.items()}
    for path, value in sorted(overrides.items()):
        role, dot, leaf = path.partition(".")
        if not dot or role not in merged:
            raise ThemeOverrideError(f"theme_override_invalid: 字体键 {path!r} 未知")
        if leaf not in {"family", "weight", "size", "line_height"}:
            raise ThemeOverrideError(
                f"theme_override_invalid: 字体叶子 {leaf!r} 非白名单")
        if value is None:
            raise ThemeOverrideError(
                f"theme_override_invalid: {path}=null；null 不是删除指令")
        merged[role][leaf] = value
    return merged


def compute_effective_theme(
    theme: dict,
    *,
    mode: str | None = None,
    brand: dict | None = None,
    color_overrides: dict | None = None,
    font_overrides: dict | None = None,
) -> dict:
    """组合 effective theme：mode → brand → 任务覆盖 → 硬检查 → source_map。"""
    colors = select_mode(theme, mode)
    fonts = theme.get("font_roles") or {}
    if not isinstance(fonts, dict) or "title" not in fonts or "body" not in fonts:
        raise ThemeError("theme_invalid: font_roles 缺 title/body 必需角色")
    source_map: dict[str, str] = {role: "theme" for role in colors}
    locked_roles: set[str] = set()
    if brand:
        colors, applied = apply_brand(colors, brand)
        locked_roles = set(brand.get("locked_roles") or [])
        for role in applied:
            source_map[role] = "brand"
    if color_overrides:
        colors = apply_overrides(colors, color_overrides, theme, locked_roles=locked_roles)
        for role in color_overrides:
            source_map[role] = "task-override"
    fonts = apply_font_overrides(fonts, font_overrides, theme)
    check_contrast(colors)
    return {
        "colors": dict(sorted(colors.items())),
        "fonts": {role: dict(defn) for role, defn in sorted(fonts.items())},
        "chart_palette": theme.get("chart_palette") or {},
        "mode": mode or theme.get("default_mode"),
        "source_map": source_map,
        "locked_roles": sorted(locked_roles),
    }
