"""recommendation/v1：风格推荐（U6，方案 §8/§8.3）。

输入：任务合同信号（genre/domain/audience/formality/density/environment/
conservatism/culture + named_style）。输出：2–3 个实质不同方向（构图/
排印/材质特征可区分），每个带引用真实任务条件与候选特征的理由。

纪律：
  - 点名 > 参考图 > 推荐；点名不覆盖硬错误（scope/依赖缺失仍拒绝）；
  - 可检索（全部）/ 静态可尝试（结构完整）/ 已验证（证据）/ 精选（维护者）
    分层计算；查询前核对证据集合（F1），陈旧撤验证标签并披露；
  - 整稿查询排除仅页面组件资格（F5 由 style_validation 派生）；
  - 环境路由（§8.3）：未知行业 → 通用方向；保守度/正式度缺 → balanced/
    0.5 试探并标默认来源；明亮环境不推只支持 dark 的组合；显式 dark 点名
    先披露适配缺口；
  - 推荐器不拥有判官或可接受集合（评测契约）。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from .asset_resolver import AssetResolver, ResolverError
from .style_validation import (deck_style_eligibility, quality_view,
                               scan_evidence_set)

# 信号 → 家族亲和（沿用 hard rules 词汇的语义锚；家族是标签非互斥分区）。
DOMAIN_FAMILY_HINTS = {
    "金融": ["金融审计", "商务专业", "数据图表"], "银行": ["金融审计", "商务专业"],
    "证券": ["金融审计"], "保险": ["金融审计"], "审计": ["金融审计", "商务专业"],
    "投行": ["金融审计", "韩式咨询"], "四大": ["金融审计"],
    "咨询": ["商务专业", "韩式咨询"], "战略": ["商务专业", "韩式咨询"],
    "医疗": ["医疗健康"], "医药": ["医疗健康"], "临床": ["医疗健康"],
    "医院": ["医疗健康"], "药": ["医疗健康"],
    "教育": ["教学课件"], "课件": ["教学课件"], "课堂": ["教学课件", "卡通儿童"],
    "公开课": ["教学课件"], "数学": ["教学课件"],
    "开发者": ["工程蓝图"], "开源": ["工程蓝图"], "编程": ["工程蓝图"],
    "品牌": ["消费营销", "设计流派"], "电商": ["消费营销"], "营销": ["消费营销"],
    "大促": ["消费营销"], "消费": ["消费营销"],
    "AI": ["科技暗色", "科技浅色"], "科技": ["科技暗色", "科技浅色"],
    "互联网": ["科技浅色"], "大模型": ["科技暗色"],
    "政务": ["党政红"], "党建": ["党政红"], "数据开放": ["数据图表"],
}
GENRE_FAMILY_HINTS = {
    "答辩": ["学术答辩"], "开题": ["学术答辩"], "结题": ["学术答辩"],
    "课题": ["学术答辩"], "基金": ["学术答辩"], "期刊": ["学术答辩", "极简排版"],
    "论文": ["学术答辩", "极简排版"],
    "董事会": ["商务专业"], "年报": ["金融审计", "商务专业"], "述职": ["商务专业"],
    "决算": ["金融审计"], "汇报": ["商务专业"], "路演": ["商务专业", "科技暗色"],
    "融资": ["商务专业"], "发布会": ["科技浅色", "科技暗色"], "新品": ["科技浅色"],
    "工作坊": ["极简排版"], "评审": ["商务专业"],
    "主题党日": ["党政红"], "宣讲": ["党政红"],
    "讲座": ["教学课件"], "科普": ["卡通儿童", "艺术手绘"],
    "大促": ["消费营销"], "品牌": ["消费营销", "设计流派"], "快闪": ["设计流派"],
}
CULTURE_FAMILY_HINTS = {
    "党政": ["党政红"], "党建": ["党政红"], "政府": ["党政红"], "机关": ["党政红"],
    "国风": ["水墨国风"], "水墨": ["水墨国风"], "禅意": ["水墨国风"],
}
AUDIENCE_FAMILY_HINTS = {
    "儿童": ["卡通儿童"], "小学生": ["卡通儿童", "教学课件"], "幼儿园": ["卡通儿童"],
    "中学生": ["教学课件"], "工程师": ["工程蓝图"], "开发者": ["工程蓝图"],
    "董事": ["商务专业"], "高管": ["商务专业"], "评审专家": ["学术答辩"],
    "患者": ["医疗健康", "艺术手绘"], "家属": ["医疗健康", "艺术手绘"],
    "公众": ["医疗健康", "艺术手绘"], "大众": ["艺术手绘"],
}
# 方向种子家族（九方向属"XX方向"家族）。
DIRECTION_FAMILY_SUFFIX = "方向"
DIRECTION_FAMILIES = ["管理方向", "金融方向", "咨询方向", "科技方向", "政务方向",
                      "医疗方向", "教育方向", "品牌方向", "学术方向"]
DIRECTION_INDUSTRY_HINTS = {
    "金融": "金融方向", "银行": "金融方向", "咨询": "咨询方向", "战略": "咨询方向",
    "科技": "科技方向", "AI": "科技方向", "互联网": "科技方向", "大模型": "科技方向",
    "政务": "政务方向", "党建": "政务方向", "医疗": "医疗方向", "临床": "医疗方向",
    "医院": "医疗方向", "药": "医疗方向", "教育": "教育方向", "课件": "教育方向",
    "课堂": "教育方向", "数学": "教育方向", "品牌": "品牌方向", "营销": "品牌方向",
    "消费": "品牌方向", "电商": "品牌方向", "答辩": "学术方向", "论文": "学术方向",
    "基金": "学术方向", "学术": "学术方向", "经营": "管理方向", "管理": "管理方向",
    "董事会": "管理方向", "审计": "金融方向", "评审": "咨询方向",
}


class RecommendationError(ResolverError):
    reason_code = "recommendation_invalid"


@dataclass
class RecommendationCandidate:
    asset_id: str
    name: str
    lifecycle: str
    families: list[str]
    features: list[str]
    environments: list[str]
    density: str | None
    formality: float | None
    conservatism: str | None
    modes: list[str]
    score: float = 0.0
    reasons: list[str] = field(default_factory=list)
    verified: bool = False
    stale_disclosure: str | None = None


ACADEMIC_GENRE_KEYS = ("答辩", "开题", "结题", "课题", "基金", "期刊", "论文")
NON_ACADEMIC_DOMAIN_KEYS = ("咨询", "战略", "金融", "银行", "营销", "品牌", "政务", "医疗", "管理", "经营")

DENSITY_TIERS = ["very-low", "low", "low-medium", "balanced", "medium-high", "high"]


def _signal_families(signals: dict) -> list[str]:
    families: list[str] = []
    domain_values = signals.get("domain")
    domain_values = [domain_values] if isinstance(domain_values, str) else list(domain_values or [])
    domain_text = " ".join(str(v) for v in domain_values)
    genre_text = str(signals.get("genre") or "")
    academic_gate_open = not any(k in domain_text for k in NON_ACADEMIC_DOMAIN_KEYS) or any(
        k in domain_text for k in ("科研", "学术", "基金", "高校"))
    for source, hints in (("domain", DOMAIN_FAMILY_HINTS),
                          ("genre", GENRE_FAMILY_HINTS),
                          ("culture", CULTURE_FAMILY_HINTS),
                          ("audience", AUDIENCE_FAMILY_HINTS)):
        values = signals.get(source)
        values = [values] if isinstance(values, str) else list(values or [])
        for value in values:
            for keyword, hint_families in hints.items():
                if keyword in str(value):
                    if source == "genre" and keyword in ACADEMIC_GENRE_KEYS and not academic_gate_open:
                        continue  # 非学术 domain 下的"结题/汇报"不锁学术家族
                    families.extend(hint_families)
            for keyword, direction in DIRECTION_INDUSTRY_HINTS.items():
                if keyword in str(value):
                    families.append(direction)
    return list(dict.fromkeys(families))


def _signal_tokens(signals: dict) -> list[str]:
    """任务信号里的实义词（≥2 字），用于适用性文本匹配。"""
    tokens: list[str] = []
    for key in ("genre", "domain", "audience", "culture"):
        values = signals.get(key)
        values = [values] if isinstance(values, str) else list(values or [])
        for value in values:
            text = str(value)
            tokens.extend(
                text[i:i + n]
                for n in (4, 3, 2)
                for i in range(0, len(text) - n + 1))
    return [t for t in dict.fromkeys(tokens) if len(t) >= 2]


def _environment_allows(candidate_modes: list[str], environment: str | None,
                        default_source: str) -> tuple[bool, str | None]:
    """§8.3 环境路由：明亮环境不推只支持 dark 的组合。"""
    if not environment or not candidate_modes:
        return True, None
    if environment in {"bright-large-venue", "classroom-screen", "community-hall",
                       "lecture-hall", "print", "meeting-room-projector"}:
        if "light" not in candidate_modes:
            return False, (f"明亮环境 {environment} 下仅支持 "
                           f"{'/'.join(candidate_modes)} 的组合被排除（default:{default_source}）")
    return True, None


def recommend_styles(
    signals: dict,
    *,
    limit: int = 3,
    resolver: AssetResolver | None = None,
    deck_query: bool = True,
) -> dict:
    """主推荐入口。返回候选方向（含理由、来源标记与披露），不生成、不落盘。"""
    if resolver is None:
        resolver = AssetResolver()
    named = str(signals.get("named_style") or "").strip()
    if named:
        try:
            resolved = resolver.require(named, kind="style")
            return {
                "kind": "style-recommendation", "schema_version": 1,
                "match_type": "named",
                "candidates": [ _candidate_from(resolved, resolver).__dict__],
                "disclosures": ["点名优先：跳过推荐排序（硬错误仍拒绝）"],
            }
        except ResolverError as exc:
            raise RecommendationError(
                f"recommendation_invalid: 点名失败 {exc.reason_code}") from exc

    # F1：查询前核对证据集合；陈旧撤验证标签并披露。
    disclosures: list[str] = []
    try:
        view = quality_view()
        stale_roots = [v["library_root"] for v in view["views"] if v["stale"]]
        if stale_roots:
            disclosures.append(
                "证据集合与 catalog 不一致（" + "; ".join(stale_roots) +
                "）：验证/精选标签已撤下，仅浏览静态候选")
        deck_eligible_by_root: dict[str, set[str]] = {}
        verified_by_root: dict[str, set[str]] = {}
        for v in view["views"]:
            root_key = str(Path(v["library_root"]).resolve())
            if v["stale"]:
                deck_eligible_by_root[root_key] = set()
                verified_by_root[root_key] = set()
                continue
            try:
                evidence = scan_evidence_set(Path(v["library_root"]))
            except ResolverError:
                deck_eligible_by_root[root_key] = set()
                verified_by_root[root_key] = set()
                continue
            style_ids = sorted({
                (record.get("assets") or {}).get("style")
                for record in evidence["records"]
                if isinstance((record.get("assets") or {}).get("style"), str)
            })
            eligible: set[str] = set()
            for style_id in style_ids:
                if deck_style_eligibility(evidence, style_id).get("eligible"):
                    eligible.add(style_id)
            deck_eligible_by_root[root_key] = eligible
            verified_by_root[root_key] = eligible.copy()
    except ResolverError as exc:
        disclosures.append(f"质量视图不可用（{exc.reason_code}）：仅浏览静态候选")
        deck_eligible_by_root = {}
        verified_by_root = {}

    default_source = "task"
    conservatism = signals.get("conservatism")
    if not conservatism:
        conservatism = "balanced"
        default_source = "default"
        disclosures.append("受众保守度缺失：按 balanced 试探（default 来源）")
    formality = signals.get("formality")
    if formality is None:
        formality = 0.5
        disclosures.append("正式度缺失：按 0.5 试探（default 来源）")
    environment = signals.get("environment") or None
    density = signals.get("density")
    if not density and isinstance(signals.get("content_shape"), dict):
        density = signals["content_shape"].get("density")

    signal_families = _signal_families(signals)
    if not signal_families:
        disclosures.append("行业/场景未知：保留通用方向（不选择不适配但证据多的凑数）")

    candidates: list[RecommendationCandidate] = []
    for entity in resolver.entities:
        if entity["kind"] != "style":
            continue
        try:
            resolved = resolver.resolve(entity["asset_id"])
        except ResolverError:
            continue
        brief = resolved["data"]
        features_obj = brief.get("recommendation_features") or {}
        candidate = _candidate_from(resolved, resolver)
        root_key = str(Path(entity["trusted_root"]).resolve())
        candidate.verified = entity["asset_id"] in verified_by_root.get(root_key, set())
        if deck_query and entity["asset_id"] not in deck_eligible_by_root.get(root_key, set()):
            # Explicitly named styles bypass recommendation eligibility; the
            # default deck pool must not present page-component-only evidence
            # as a full-deck direction.
            continue
        rf = features_obj
        candidate.environments = list(rf.get("environments") or [])
        candidate.density = rf.get("density")
        candidate.formality = rf.get("formality")
        candidate.conservatism = rf.get("audience_conservatism")
        candidate.features = list((brief.get("visual_language") or {}).get("features") or [])

        # F5：整稿查询排除仅页面组件（无证据时种子也只算组件，可浏览不占整稿位）。
        # 可检索分层：draft 可浏览；执行资格另由调用方判定。
        allowed, env_reason = _environment_allows(
            brief.get("bindings", {}).get("modes_supported") or ["light"],
            environment, default_source)
        if not allowed:
            continue

        score = 0.0
        matched = [f for f in signal_families if f in candidate.families]
        if matched:
            # 家族是标签非互斥分区：domain（行业承诺）权重高于 genre/audience
            # 的场景提示；首命中最强，叠加次之（压制多标签刷分）。
            domain_families = set(_signal_families({"domain": signals.get("domain")}))
            base = 3.5 if set(matched) & domain_families else 2.5
            score += base + (1.0 if len(matched) > 1 else 0.0)
            candidate.reasons.append(
                f"任务语境命中家族 {', '.join(matched[:3])}（来自任务 "
                f"{'/'.join(sorted(k for k in ('domain', 'genre', 'culture', 'audience') if signals.get(k)))}）")
        # 适用性文本命中（best_for/名称/别名的关键词重叠）：真实适用性证据。
        applicability = " ".join([
            str((brief.get("legacy_payload") or {}).get("best_for") or ""),
            candidate.name, *candidate.families,
            *[str(a) for a in brief.get("aliases", [])]])
        signal_tokens = _signal_tokens(signals)
        token_hits = [token for token in signal_tokens if token in applicability]
        if token_hits:
            # 适用性文本是辅助证据（≤2.0）：不得压过行业/场景家族命中。
            score += min(1.0 * len(set(token_hits)), 2.0)
            candidate.reasons.append(
                f"适用场景命中 {', '.join(list(dict.fromkeys(token_hits))[:3])}")
        if candidate.formality is not None and formality is not None:
            delta = abs(candidate.formality - formality)
            if delta <= 0.2:
                score += 1.5 - delta
                candidate.reasons.append(
                    f"正式度匹配（任务 {formality} vs 风格 {candidate.formality}）")
            elif delta > 0.4:
                # 适用性过滤：正式度差超过 0.4 的风格不进入该任务候选（先过滤再排序）。
                continue
        if candidate.conservatism and conservatism and candidate.conservatism == conservatism:
            score += 0.5
            candidate.reasons.append(f"受众保守度一致（{conservatism}）")
        if density and candidate.density:
            if candidate.density == density:
                score += 0.5
                candidate.reasons.append(f"密度匹配（{density}）")
            elif density in DENSITY_TIERS and candidate.density in DENSITY_TIERS:
                gap = abs(DENSITY_TIERS.index(density) - DENSITY_TIERS.index(candidate.density))
                if gap == 1:
                    score += 0.2
                elif gap >= 3:
                    # 适用性过滤：密度差 ≥3 档不进入候选（低密度大屏任务配高密度风格为错配）。
                    continue
                elif gap >= 2:
                    score -= 1.5
                    candidate.reasons.append(
                        f"密度错配（任务 {density} vs 风格 {candidate.density}，差 {gap} 档）")
        if (candidate.conservatism and conservatism
                and candidate.conservatism != conservatism
                and {candidate.conservatism, conservatism} == {"reserved", "expressive"}):
            score -= 2.0
            candidate.reasons.append(
                f"受众保守度冲突（任务 {conservatism} vs 风格 {candidate.conservatism}）")
        if resolved["lifecycle"] == "active":
            score += 1.0
            candidate.reasons.append("结构完整 active（主题绑定/特征齐备）")
        if brief.get("constraints", {}).get("negative"):
            score += 0.25
        candidate.score = round(score, 3)
        if candidate.score <= 0:
            continue
        candidates.append(candidate)

    candidates.sort(key=lambda c: (-c.score, c.asset_id))
    # 家族命中硬优先：存在语境家族命中时，仅靠 token/正式度凑分的候选不进前排。
    family_matched = [c for c in candidates
                      if any(r.startswith("任务语境命中家族") for r in c.reasons)]
    if family_matched:
        candidates = family_matched + [c for c in candidates if c not in family_matched]

    # 实质不同方向：同分带内按家族差异去重（别名/仅换色不算差异——家族与特征都相同即视为同方向）。
    selected: list[RecommendationCandidate] = []
    for candidate in candidates:
        duplicate = any(
            set(candidate.families) & set(chosen.families)
            and candidate.features and chosen.features
            and set(candidate.features) == set(chosen.features)
            for chosen in selected)
        if not duplicate:
            selected.append(candidate)
        if len(selected) >= limit:
            break
    if not selected and candidates:
        selected = candidates[:1]
    return {
        "kind": "style-recommendation", "schema_version": 1,
        "match_type": "recommended",
        "signal_families": signal_families,
        "defaults_applied": default_source == "default",
        "candidates": [c.__dict__ for c in selected],
        "disclosures": ([*disclosures,
                          "整稿查询已排除未覆盖封面/正文/证据/结尾四角色的 page-component 风格"]
                        if deck_query else disclosures),
    }


def _candidate_from(resolved: dict, resolver: AssetResolver) -> RecommendationCandidate:
    brief = resolved["data"]
    return RecommendationCandidate(
        asset_id=resolved["asset_id"],
        name=resolved["name"],
        lifecycle=resolved["lifecycle"],
        families=list((brief.get("taxonomy") or {}).get("families") or []),
        features=[],
        environments=[],
        density=None, formality=None, conservatism=None,
        modes=list((brief.get("bindings") or {}).get("modes_supported") or ["light"]),
    )
