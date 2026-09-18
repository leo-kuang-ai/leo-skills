"""真实 image HTTP 导出及字节收据；传输成功与语义、视觉验收分别记录。"""
from __future__ import annotations

import base64
import hashlib
import io
import json
import re
from pathlib import Path
from urllib.parse import urlsplit

from filelock import FileLock

from ..qualification import digest, file_reference, read_evidence_bytes, verify_reference
from ..storage import atomic_write_bytes, atomic_write_json


class ImageExportError(ValueError):
    pass


def verify_provider_export(receipt, *, root, binding=None):
    if (receipt.get("schema_version") != 1 or receipt.get("kind") != "provider-export-receipt" or receipt.get("status") != "succeeded"
            or receipt.get("lane") != "image" or receipt.get("receipt_digest") != digest({k: v for k, v in receipt.items() if k != "receipt_digest"})):
        raise ImageExportError("provider_receipt_invalid")
    if (not isinstance(receipt.get("request_id"), str) or not receipt["request_id"].strip()
            or type(receipt.get("http_status")) is not int or not 200 <= receipt["http_status"] < 300
            or receipt.get("evidence_source") not in {"local-protocol-test", "provider-http"}
            or not receipt.get("provider") or not receipt.get("model")):
        raise ImageExportError("provider_response_identity_invalid")
    if not re.fullmatch(r"[0-9a-f]{64}", str(receipt.get("contract_sha256", ""))):
        raise ImageExportError("provider_contract_digest_invalid")
    bodies = {name: verify_reference(root, receipt[name])
              for name in ("artifact", "provider_image", "response", "request")}
    try:
        request, response = json.loads(bodies["request"]), json.loads(bodies["response"])
        if (request.get("model") != receipt["model"] or request.get("n") != 1
                or not isinstance(request.get("prompt"), str) or not request["prompt"].strip()):
            raise ImageExportError("provider_request_mismatch")
        data = response["data"]
        if not isinstance(data, list) or len(data) != 1:
            raise ImageExportError("provider_output_count_invalid")
        # URL 响应没有冻结的下载传输证据时，不能用任意本地图片补足原始字节。
        encoded = data[0].get("b64_json")
        if not isinstance(encoded, str) or not encoded:
            raise ImageExportError("provider_response_image_bytes_unavailable")
        if base64.b64decode(encoded, validate=True) != bodies["provider_image"]:
            raise ImageExportError("provider_response_image_mismatch")
    except (KeyError, TypeError, AttributeError, ValueError) as exc:
        if isinstance(exc, ImageExportError):
            raise
        raise ImageExportError("provider_response_invalid") from exc
    from PIL import Image, ImageOps
    with Image.open(io.BytesIO(bodies["provider_image"])) as original, Image.open(io.BytesIO(bodies["artifact"])) as image:
        original.load()
        image.load()
        if (image.format != "PNG" or image.size != (2560, 1440) or image.mode != "RGB"
                or (receipt.get("width"), receipt.get("height")) != image.size):
            raise ImageExportError("provider_export_dimensions_invalid")
        if receipt.get("postprocess") != {"operation": "contain", "background": "#FFFFFF",
                "source_size": list(original.size), "output_size": [2560, 1440]}:
            raise ImageExportError("provider_postprocess_mismatch")
        expected = ImageOps.pad(original.convert("RGB"), (2560, 1440), method=Image.Resampling.LANCZOS, color="#FFFFFF")
        if expected.tobytes() != image.tobytes():
            raise ImageExportError("provider_export_pixels_mismatch")
    if receipt.get("out_sha256") != receipt["artifact"]["sha256"]:
        raise ImageExportError("provider_export_hash_mismatch")
    if binding is not None:
        from ..content_projection import verify_binding_reference
        verify_binding_reference(receipt, binding)
        if receipt["purpose"] != binding["qualification_purpose"]:
            raise ImageExportError("provider_export_purpose_mismatch")
        if (receipt.get("page_id") != binding["page_id"] or receipt.get("recipe_id") != binding["recipe_id"]
                or receipt.get("contract_sha256") != binding["effective"].get("provider_contract_sha256")):
            raise ImageExportError("provider_binding_contract_mismatch")
    return receipt


def export_provider_image(recipe_input, *, context, output_root, binding=None,
                          pack_page=None, resolver=None, run_id=None, input_generation=None, checkpoint=None):
    """无 binding 的调用仅生成 capability-probe；生产调用必须重验冻结资格。"""
    from .._vendor.codex_ppt.image_providers.factory import create_image_provider
    from .._vendor.codex_ppt.image_providers.openai_compatible import OpenAICompatibleImageProvider
    from PIL import Image, ImageOps
    if recipe_input.get("kind") != "image-recipe-input" or recipe_input.get("canvas") != {"width": 2560, "height": 1440}:
        raise ImageExportError("image_recipe_input_invalid")
    if context.mode != "generate":
        raise ImageExportError("provider_contract_mode_mismatch")
    if binding is not None:
        from ..content_projection import verify_effective_binding
        if pack_page is None or binding["backend"] != "image" or not run_id or not input_generation:
            raise ImageExportError("provider_binding_missing")
        verify_effective_binding(binding, pack_page, resolver=resolver)
        if (binding["recipe_id"] != recipe_input["recipe_id"] or binding["page_id"] != recipe_input["page_id"]
                or binding["effective"].get("provider_contract_sha256") != context.contract_sha256):
            raise ImageExportError("provider_binding_contract_mismatch")
        from .recipe import project_recipe
        from ..task_local_layout_proposals import effective_layout_profile
        projected = project_recipe(resolver.resolve(binding["recipe_id"])["data"], page=pack_page,
            layout=effective_layout_profile(binding, resolver=resolver), theme=binding["effective"]["theme"],
            numbers=binding["effective"]["number_facts"])
        if any(recipe_input.get(key) != value for key, value in projected.items()):
            raise ImageExportError("provider_input_projection_mismatch")
    root = Path(output_root).absolute()
    if any(p.is_symlink() for p in (root, *root.parents)):
        raise ImageExportError("provider_output_path_invalid")
    root.mkdir(parents=True, exist_ok=True)
    check = checkpoint or (lambda _phase: None)
    request = {"model": context.model, "prompt": recipe_input["prompt"], "n": 1, "size": "auto"}
    identity = digest({"request": request, "recipe_input": recipe_input, "contract": context.contract_sha256,
                       "materialization_binding_digest": binding["materialization_binding_digest"] if binding else None,
                       "run_id": run_id, "input_generation": input_generation})
    receipt_path = root / "page.png.provider.json"
    lock = root / ".provider.lock"
    if lock.is_symlink():
        raise ImageExportError("provider_output_path_invalid")
    with FileLock(str(lock)):
        if receipt_path.exists() or receipt_path.is_symlink():
            receipt = json.loads(read_evidence_bytes(root, receipt_path.name))
            if receipt.get("input_digest") != identity:
                raise ImageExportError("provider_input_conflict")
            return verify_provider_export(receipt, root=root, binding=binding)
        inflight = root / "provider-inflight.json"
        if inflight.exists() or inflight.is_symlink():
            # 响应未知时禁止重复发起；显式新 revision 才能决定下一次调用。
            raise ImageExportError("provider_outcome_unknown")
        provider = create_image_provider(api_key=context.environment.get("OPENAI_API_KEY"),
                                         base_url=context.environment.get("OPENAI_BASE_URL"))
        if not isinstance(provider, OpenAICompatibleImageProvider):
            raise ImageExportError("provider_receipt_adapter_unsupported")
        atomic_write_json(root / "provider-request.json", request)
        atomic_write_json(inflight, {"input_digest": identity, "status": "in_flight"})
        check("before_provider")
        try:
            response = provider.generate_with_receipt(request, timeout_seconds=context.timeout_seconds)
        except Exception as exc:
            # SDK 错误可能包含端点或凭据，只保留稳定错误类别。
            raise ImageExportError("provider_outcome_unknown: " + type(exc).__name__) from None
        if len(response["images"]) != 1:
            raise ImageExportError("provider_output_count_invalid")
        raw = base64.b64decode(response["images"][0], validate=True)
        atomic_write_bytes(root / "provider-response.json", response["response_bytes"])
        atomic_write_bytes(root / "provider-image.bin", raw)
        with Image.open(io.BytesIO(raw)) as image:
            image.load()
            source_size = list(image.size)
            # 等比留边保留全部像素，禁止裁剪事实；质量由独立输出 oracle 检查。
            normalized = ImageOps.pad(image.convert("RGB"), (2560, 1440), method=Image.Resampling.LANCZOS, color="#FFFFFF")
            buffer = io.BytesIO()
            normalized.save(buffer, format="PNG")
        atomic_write_bytes(root / "page.png", buffer.getvalue())
        check("after_artifact")
        host = urlsplit(context.environment.get("OPENAI_BASE_URL") or "https://api.openai.com").hostname or ""
        local = host in {"localhost", "127.0.0.1", "::1"} or host.endswith((".test", ".invalid"))
        receipt = {"schema_version": 1, "kind": "provider-export-receipt", "status": "succeeded", "lane": "image",
            "purpose": binding["qualification_purpose"] if binding else "capability-probe",
            "evidence_source": "local-protocol-test" if local else "provider-http",
            "provider": context.provider, "model": context.model, "contract_sha256": context.contract_sha256,
            "request_id": response["request_id"], "http_status": response["status_code"], "input_digest": identity,
            "page_id": recipe_input["page_id"], "recipe_id": recipe_input["recipe_id"],
            "run_id": run_id, "input_generation": input_generation,
            "out_sha256": hashlib.sha256(buffer.getvalue()).hexdigest(), "width": 2560, "height": 1440,
            "artifact": file_reference(root, "page.png"), "provider_image": file_reference(root, "provider-image.bin"),
            "response": file_reference(root, "provider-response.json"), "request": file_reference(root, "provider-request.json"),
            "postprocess": {"operation": "contain", "background": "#FFFFFF", "source_size": source_size, "output_size": [2560, 1440]},
            "semantic_status": "not_run", "visual_status": "not_run"}
        if binding is not None:
            for name in ("expression_binding_digest", "materialization_binding_digest"):
                receipt[name] = binding[name]
        receipt["receipt_digest"] = digest(receipt)
        verify_provider_export(receipt, root=root, binding=binding)
        atomic_write_json(receipt_path, receipt)
        check("after_receipt")
        return receipt
