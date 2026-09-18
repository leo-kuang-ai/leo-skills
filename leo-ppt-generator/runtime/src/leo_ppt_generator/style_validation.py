"""style_validation/v1：证据集合、新鲜度与派生质量状态（F1/F5，方案 §6/§9）。

职责：
  - 枚举每个有效库根下全部已发布验证包（evidence/<validation-id>/）与不可变
    撤销记录（evidence/revocations/），按相对路径 + 文件 hash 计算
    ``evidence_set_digest``（包含尚未被 catalog 引用的新失败）；
  - 从证据派生质量状态：必查项通过 + 真实评审 + 依赖匹配才 verified；
    supersedes 显式取代；未裁决矛盾取消通过；撤销按范围失效；
  - deck-style 整稿资格（F5）：声明范围内封面/正文/复杂证据/结尾四角色齐备，
    同一已解析主题；只有封面等局部能力 → page-component。

不拥有：作者事实、任务接受状态、推荐政策。staging 不参加集合；正式目录
内坏 manifest、缺文件、重复 ID 均报告完整性错误，不当空集合。
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

from .asset_resolver import ResolverError, builtin_library_root, user_library_root

DECK_ROLES = ("cover", "content", "evidence", "closing")


class EvidenceIntegrityError(ResolverError):
    """证据集合完整性错误（不是空集合，不是通过）。"""

    reason_code = "evidence_integrity_invalid"


class QualityUnavailableError(ResolverError):
    """读取中集合不稳定，质量结论不可用。"""

    reason_code = "quality_unavailable"


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _load_json(path: Path) -> dict:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise EvidenceIntegrityError(
            f"evidence_integrity_invalid: {path.name} 不可解析") from exc
    if not isinstance(data, dict):
        raise EvidenceIntegrityError(
            f"evidence_integrity_invalid: {path.name} 非对象")
    return data


def scan_evidence_set(library_root: Path) -> dict:
    """完整证据集合扫描：记录清单 + 集合摘要（确定性：排序路径，无时间戳）。"""
    library_root = Path(library_root)
    evidence = library_root / "evidence"
    problems: list[str] = []
    records: list[dict] = []
    seen_ids: set[str] = set()
    if evidence.is_dir():
        for manifest_path in sorted(evidence.glob("*/manifest.json")):
            validation_id = manifest_path.parent.name
            if validation_id in {"revocations", "staging"}:
                problems.append(f"reserved_dir_used:{validation_id}")
                continue
            if validation_id in seen_ids:
                problems.append(f"duplicate_validation_id:{validation_id}")
                continue
            seen_ids.add(validation_id)
            record = _load_json(manifest_path)
            problems.extend(_check_package(record, manifest_path.parent, validation_id))
            record["_validation_id"] = validation_id
            records.append(record)
    revocations: list[dict] = []
    rev_dir = evidence / "revocations"
    if rev_dir.is_dir():
        for path in sorted(rev_dir.glob("*.json")):
            record = _load_json(path)
            record["_file"] = path.name
            revocations.append(record)
    digest_input = {
        "records": sorted((r["_validation_id"], json.dumps(r, sort_keys=True, ensure_ascii=False))
                          for r in records),
        "revocations": sorted(json.dumps(r, sort_keys=True, ensure_ascii=False)
                              for r in revocations),
    }
    digest = hashlib.sha256(
        json.dumps(digest_input, ensure_ascii=False, sort_keys=True).encode("utf-8")
    ).hexdigest()
    return {"records": records, "revocations": revocations,
            "evidence_set_digest": digest, "problems": problems}


def _check_package(record: dict, package_dir: Path, validation_id: str) -> list[str]:
    problems: list[str] = []
    if record.get("kind") != "style-validation":
        problems.append(f"{validation_id}:kind_invalid")
    for required in ("validation_id", "assets", "lane", "result", "checks", "review"):
        if required not in record:
            problems.append(f"{validation_id}:missing:{required}")
    if record.get("validation_id") != validation_id:
        problems.append(f"{validation_id}:id_mismatch")
    outputs = record.get("outputs") or {}
    if not isinstance(outputs, dict) or not outputs:
        problems.append(f"{validation_id}:outputs_missing")
        return problems
    for name, expected_hash in sorted(outputs.items()):
        if not isinstance(name, str) or not name.strip():
            problems.append(f"{validation_id}:output_name_invalid:{name!r}")
            continue
        candidate = Path(name)
        out = (package_dir / candidate).resolve()
        if candidate.is_absolute() or not out.is_relative_to(package_dir.resolve()):
            problems.append(f"{validation_id}:output_outside_package:{name}")
            continue
        if not out.is_file():
            problems.append(f"{validation_id}:output_missing:{name}")
        elif _sha(out) != expected_hash:
            problems.append(f"{validation_id}:output_hash_mismatch:{name}")
    for check in record.get("checks", []):
        if not isinstance(check, dict) or "id" not in check or "result" not in check:
            problems.append(f"{validation_id}:check_malformed")
            break
    return problems


def derive_quality(evidence_set: dict) -> dict:
    """从证据集合派生质量状态（不读 catalog；新旧失败都计入）。"""
    by_key: dict[tuple, list[dict]] = {}

    def scope_of(record: dict) -> tuple:
        assets = record.get("assets") or {}
        return (record.get("lane"), assets.get("style"),
                assets.get("theme"), record.get("mode"),
                assets.get("layout") or assets.get("template"))

    for record in evidence_set["records"]:
        key = scope_of(record)
        by_key.setdefault(key, []).append(record)

    revoked = set()
    for revocation in evidence_set["revocations"]:
        target = revocation.get("validation_id")
        if isinstance(target, str):
            revoked.add(target)
        for scope_key in revocation.get("scopes", []) if isinstance(revocation.get("scopes"), list) else []:
            for record in by_key.get(tuple(scope_key) if isinstance(scope_key, list) else scope_key, []):
                revoked.add(record["_validation_id"])

    verified: dict[tuple, dict] = {}
    conflicts: list[tuple] = []
    superseded = set()
    for record in evidence_set["records"]:
        for target in record.get("supersedes", []) if isinstance(record.get("supersedes"), list) else []:
            if isinstance(target, str):
                superseded.add(target)
    for key, records in sorted(by_key.items(), key=lambda kv: repr(kv[0])):
        active = [r for r in records if r["_validation_id"] not in revoked]
        results = {str(r.get("result")) for r in active if r["_validation_id"] not in superseded}
        passes = [r for r in active
                  if r.get("result") == "pass" and _checks_pass(r) and _review_valid(r)
                  and r["_validation_id"] not in superseded]
        if len(results) > 1:
            conflicts.append(key)
            continue  # 未裁决矛盾：取消通过加成
        if passes:
            verified[key] = sorted(r["_validation_id"] for r in passes)[-1]
    return {
        "verified_scopes": {repr(k): v for k, v in sorted(verified.items(), key=lambda kv: repr(kv[0]))},
        "conflict_scopes": [repr(k) for k in conflicts],
        "revoked_validation_ids": sorted(revoked),
        "superseded_validation_ids": sorted(superseded),
    }


def _checks_pass(record: dict) -> bool:
    checks = record.get("checks")
    if not isinstance(checks, list) or not checks:
        return False
    for check in checks:
        if not isinstance(check, dict) or check.get("result") != "pass":
            return False
    return True


def _review_valid(record: dict) -> bool:
    review = record.get("review")
    return isinstance(review, dict) and bool(review.get("source")) \
        and review.get("result") == "pass"


def deck_style_eligibility(evidence_set: dict, style_id: str) -> dict:
    """F5 整稿资格：同一 (style, theme, lane, mode) 组合覆盖四角色。

    跨主题/跨 lane 借证据不得凑覆盖；四角色缺一即只能 page-component。
    """
    roles_covered: dict[str, set] = {}
    theme_by_role: dict[str, set] = {}
    for record in evidence_set["records"]:
        assets = record.get("assets") or {}
        if assets.get("style") != style_id:
            continue
        if not (_checks_pass(record) and _review_valid(record)
                and record.get("result") == "pass"):
            continue
        for role in record.get("page_roles", []) if isinstance(record.get("page_roles"), list) else []:
            roles_covered.setdefault(role, set()).add(record["_validation_id"])
            theme_by_role.setdefault(role, set()).add(str(assets.get("theme")))
    themes = set().union(*theme_by_role.values()) if theme_by_role else set()
    same_theme = all(v == {min(themes)} for v in theme_by_role.values()) if themes else False
    missing = [role for role in DECK_ROLES if role not in roles_covered]
    if not missing and same_theme and len(themes) == 1:
        return {"kind": "deck-style", "eligible": True,
                "roles": {role: sorted(ids) for role, ids in sorted(roles_covered.items())}}
    return {"kind": "page-component", "eligible": False,
            "missing_roles": missing,
            "themes": sorted(themes),
            "reason": "roles_incomplete" if missing else "theme_mismatch"}


def quality_view(*, home: Path | None = None, library: Path | None = None) -> dict:
    """质量查询入口：重算当前集合摘要并与 catalog 记录比较。

    不一致 → stale 并给出重算结果（旧 verified 不再对外返回）；读取前后
    集合变化 → quality_unavailable。
    """
    roots = []
    if library is not None:
        roots = [Path(library)]
    else:
        roots = [builtin_library_root()]
        user = user_library_root(home)
        if user is not None:
            roots.append(user)
    views = []
    for root in roots:
        first = scan_evidence_set(root)
        derived = derive_quality(first)
        second = scan_evidence_set(root)
        if first["evidence_set_digest"] != second["evidence_set_digest"]:
            raise QualityUnavailableError(
                "quality_unavailable: 证据集合读取中变化（有界重读仍不稳定）")
        catalog_digest = _catalog_evidence_digest(root)
        views.append({
            "library_root": str(root),
            "evidence_set_digest": first["evidence_set_digest"],
            "catalog_evidence_digest": catalog_digest,
            "stale": catalog_digest is not None and catalog_digest != first["evidence_set_digest"],
            "problems": first["problems"],
            "quality": derived,
            "records": len(first["records"]),
        })
    return {"kind": "style-quality-view", "schema_version": 1, "views": views}


def _catalog_evidence_digest(library_root: Path) -> str | None:
    import os

    catalog = library_root / "catalog"
    pointer = catalog / "current.json"
    try:
        generation = json.loads(pointer.read_text(encoding="utf-8")).get("generation")
        registry = json.loads(
            (catalog / "generations" / str(generation) / "registry.json").read_text(encoding="utf-8"))
        return registry.get("evidence_set_digest")
    except (OSError, ValueError, TypeError):
        return None
