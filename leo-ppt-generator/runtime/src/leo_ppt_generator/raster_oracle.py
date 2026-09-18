"""独立图片输出检测：像素 OCR 重算事实，具名视觉观测提供连线与裁切几何。"""
from __future__ import annotations

import hashlib
import io
import json
import math
from pathlib import Path
import platform
import shutil
import subprocess
import tempfile
from functools import lru_cache

from PIL import Image

from .qualification import digest, verify_reference
from .relation_oracle import OracleError, evaluate_output, validate_expectation


class RasterOracleError(ValueError):
    pass


def image_probe_input(recipe, fixture, relation):
    """冻结 recipe 的探针输入；负例保留其错误数据，不注入 oracle 标准答案。"""
    values = {"content": fixture["data"], "expression": {"relation": relation},
              "theme": {}, "layout": recipe["slot_map"]}
    return {"kind": "image-recipe-input", "canvas": recipe["canvas"], "recipe_id": recipe["asset_id"],
            "page_id": fixture["case_id"] + "-" + fixture["probe"],
            "prompt": recipe["prompt_skeleton"].format(**{k: json.dumps(v, ensure_ascii=False, sort_keys=True)
                                                          for k, v in values.items()})}


def verify_image_probe_source(*, root, fixture, relation, artifact, render_input, provider_reference, dependencies):
    """贯通冻结 recipe → 请求 → 响应原图 → 实际 PNG；本地协议证据不得晋升。"""
    from .image_deck.expression_adapter import verify_provider_export
    if not provider_reference:
        raise RasterOracleError("image_provider_evidence_required")
    provider = json.loads(verify_reference(root, provider_reference))
    provider_root = Path(root) / Path(provider_reference["path"]).parent
    verify_provider_export(provider, root=provider_root)
    if provider.get("evidence_source") != "provider-http" or provider.get("purpose") != "capability-probe":
        raise RasterOracleError("image_real_provider_evidence_required")
    reference = provider["artifact"]
    if artifact != {"path": (Path(provider_reference["path"]).parent / reference["path"]).as_posix(),
                    "sha256": reference["sha256"]}:
        raise RasterOracleError("image_provider_artifact_mismatch")
    recipes = [path for path in dependencies if path.endswith("/recipe.json")]
    if len(recipes) != 1:
        raise RasterOracleError("image_probe_recipe_dependency_invalid")
    recipe = json.loads(verify_reference(root, {"path": recipes[0], "sha256": dependencies[recipes[0]]}))
    expected = image_probe_input(recipe, fixture, relation)
    actual = json.loads(verify_reference(root, render_input))
    request = json.loads(verify_reference(provider_root, provider["request"]))
    if (actual != expected or request.get("prompt") != expected["prompt"]
            or provider.get("page_id") != expected["page_id"] or provider.get("recipe_id") != recipe["asset_id"]):
        raise RasterOracleError("image_probe_input_mismatch")
    return provider


@lru_cache(maxsize=4)
def _ocr_executable(source_hash):
    if platform.system() != "Darwin" or not shutil.which("swiftc"):
        raise RasterOracleError("image_ocr_backend_unavailable")
    source = Path(__file__).with_name("raster_text.swift")
    if hashlib.sha256(source.read_bytes()).hexdigest() != source_hash:
        raise RasterOracleError("image_ocr_source_changed")
    temporary = tempfile.TemporaryDirectory(prefix="leo-image-ocr-")
    root = Path(temporary.name)
    executable = root / "image-ocr"
    try:
        result = subprocess.run([shutil.which("swiftc"), "-module-cache-path", str(root / "modules"),
                                 str(source), "-o", str(executable)], capture_output=True, timeout=60)
    except (OSError, subprocess.TimeoutExpired) as exc:
        temporary.cleanup()
        raise RasterOracleError("image_ocr_build_unavailable") from exc
    if result.returncode:
        temporary.cleanup()
        raise RasterOracleError("image_ocr_build_failed")
    return temporary, executable


@lru_cache(maxsize=32)
def _recognize(image_bytes, source_hash):
    _, executable = _ocr_executable(source_hash)
    with tempfile.TemporaryDirectory(prefix="leo-image-ocr-input-") as temporary:
        path = Path(temporary) / "page.png"
        path.write_bytes(image_bytes)
        try:
            result = subprocess.run([str(executable), str(path)], capture_output=True, timeout=60)
        except (OSError, subprocess.TimeoutExpired) as exc:
            raise RasterOracleError("image_ocr_execution_unavailable") from exc
        if result.returncode:
            raise RasterOracleError("image_ocr_execution_failed")
        try:
            rows = json.loads(result.stdout)
        except ValueError as exc:
            raise RasterOracleError("image_ocr_output_invalid") from exc
    return rows


def measure_raster(image_bytes):
    """不把输入 JSON、DOM、旧 OCR 文本或 passed 字段当作图片中的可见事实。"""
    with Image.open(io.BytesIO(image_bytes)) as image:
        if image.format != "PNG" or image.size != (2560, 1440):
            raise RasterOracleError("image_oracle_dimensions_invalid")
        image.verify()
    source_hash = hashlib.sha256(Path(__file__).with_name("raster_text.swift").read_bytes()).hexdigest()
    texts = []
    for row in _recognize(image_bytes, source_hash):
        x, y, width, height = row["box"]
        if (not isinstance(row["text"], str) or not row["text"].strip()
                or not all(math.isfinite(v) for v in (x, y, width, height, row["confidence"]))
                or width <= 0 or height <= 0):
            raise RasterOracleError("image_ocr_output_invalid")
        texts.append({"text": row["text"], "confidence": row["confidence"],
                      "box": [x * 1280, y * 720, width * 1280, height * 720], "font_size": height * 720})
    # OCR 经常按列返回；阅读顺序按实际行分组，再由左至右，与预期顺序无关。
    lines = []
    for text in sorted(texts, key=lambda t: (t["box"][1], t["box"][0])):
        line = next((line for line in lines if abs(line[0]["box"][1] - text["box"][1]) <= 8), None)
        if line is None:
            lines.append([text])
        else:
            line.append(text)
    ordered = [text for line in lines for text in sorted(line, key=lambda t: t["box"][0])]
    return {"schema_version": 1, "kind": "raster-text-measurement", "source": "apple-vision-revision-3",
            "artifact_sha256": hashlib.sha256(image_bytes).hexdigest(), "viewport": [1280, 720],
            "extractor_sha256": source_hash, "texts": ordered}


def evaluate_raster_output(expected, image_bytes, review, *, relation, oracle, environment_sha256):
    """OCR 不能证明连线/裁切不存在；缺具名、图片绑定的完整观测时拒绝准入。"""
    validate_expectation(expected, relation)
    fields = {"schema_version", "kind", "artifact_sha256", "expectation_digest", "oracle_digest",
              "environment_sha256", "reviewer", "method", "observations", "edges", "blocks", "complete"}
    if (not isinstance(review, dict) or set(review) != fields or review["schema_version"] != 1
            or review["kind"] != "raster-geometry-observation" or review["complete"] is not True
            or review["method"] not in {"human", "model"}
            or not isinstance(review["reviewer"], str) or not review["reviewer"].strip()
            or not isinstance(review["observations"], str) or not review["observations"].strip()
            or not isinstance(review["edges"], list) or not isinstance(review["blocks"], list)
            or not review["blocks"]):
        raise RasterOracleError("image_geometry_observation_required")
    if (review["artifact_sha256"] != hashlib.sha256(image_bytes).hexdigest()
            or review["expectation_digest"] != digest(expected) or review["oracle_digest"] != digest(oracle)
            or review["environment_sha256"] != environment_sha256):
        raise RasterOracleError("image_geometry_observation_stale")

    def vector(value, size):
        if (not isinstance(value, list) or len(value) != size
                or any(type(v) not in (int, float) or not math.isfinite(v) for v in value)):
            raise RasterOracleError("image_geometry_observation_invalid")

    for edge in review["edges"]:
        if (not isinstance(edge, dict) or set(edge) != {"start", "end", "directed", "reverse"}
                or type(edge["directed"]) is not bool or type(edge["reverse"]) is not bool):
            raise RasterOracleError("image_geometry_observation_invalid")
        for key in ("start", "end"):
            vector(edge[key], 2)
            if not (0 <= edge[key][0] <= 1280 and 0 <= edge[key][1] <= 720):
                raise RasterOracleError("image_geometry_observation_invalid")
    for block in review["blocks"]:
        if (not isinstance(block, dict) or set(block) != {"box", "overflow"}
                or type(block["overflow"]) is not bool):
            raise RasterOracleError("image_geometry_observation_invalid")
        vector(block["box"], 4)
        if block["box"][2] <= 0 or block["box"][3] <= 0:
            raise RasterOracleError("image_geometry_observation_invalid")
    measured = measure_raster(image_bytes)
    if not measured["texts"] or any(text["confidence"] < 0.8 for text in measured["texts"]):
        raise RasterOracleError("image_ocr_low_confidence")
    measurement = {"schema_version": 1, "kind": "render-measurement", "source": "raster-ocr-reviewed",
                   "viewport": measured["viewport"], "texts": measured["texts"],
                   "edges": review["edges"], "blocks": review["blocks"]}
    try:
        checks = evaluate_output(expected, measurement, relation=relation, oracle=oracle)
    except OracleError as exc:
        raise RasterOracleError(str(exc)) from exc
    return {"measurement": measured, "checks": checks, "geometry_observation_digest": digest(review)}
