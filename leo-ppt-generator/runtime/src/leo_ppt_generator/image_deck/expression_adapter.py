"""真实 image HTTP 导出及字节收据；传输成功与语义、视觉验收分别记录。"""
from __future__ import annotations

import base64
import hashlib
import io
import json
from pathlib import Path
from urllib.parse import urlsplit

from filelock import FileLock

from ..qualification import digest, file_reference, read_evidence_bytes, verify_reference
from ..storage import atomic_write_bytes, atomic_write_json


class ImageExportError(ValueError):
    pass


def verify_provider_export(receipt, *, root, binding=None):
    if (receipt.get("kind") != "provider-export-receipt" or receipt.get("status") != "succeeded"
            or receipt.get("lane") != "image" or receipt.get("receipt_digest") != digest({k: v for k, v in receipt.items() if k != "receipt_digest"})):
        raise ImageExportError("provider_receipt_invalid")
    for name in ("artifact", "provider_image", "response", "request"):
        verify_reference(root, receipt[name])
    from PIL import Image
    with Image.open(io.BytesIO(verify_reference(root, receipt["artifact"]))) as image:
        if image.format != "PNG" or image.size != (2560, 1440):
            raise ImageExportError("provider_export_dimensions_invalid")
        image.verify()
    if binding is not None:
        from ..content_projection import verify_binding_reference
        verify_binding_reference(receipt, binding)
        if receipt["purpose"] != binding["qualification_purpose"]:
            raise ImageExportError("provider_export_purpose_mismatch")
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
        projected = project_recipe(resolver.resolve(binding["recipe_id"])["data"], page=pack_page,
            layout=resolver.resolve(binding["layout_id"])["data"], theme=binding["effective"]["theme"],
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
        atomic_write_json(receipt_path, receipt)
        verify_provider_export(receipt, root=root, binding=binding)
        check("after_receipt")
        return receipt
