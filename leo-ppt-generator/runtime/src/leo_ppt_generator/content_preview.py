"""冻结绑定的零外部调用骨架预览；缓存与状态均为可重建派生物。"""
from __future__ import annotations

import base64
from contextlib import ExitStack
import hashlib
from html import escape
import json
import os
from pathlib import Path
import tempfile
from time import monotonic

from filelock import FileLock

from .content_pack import verify_content_pack
from .content_projection import load_run_binding, materialize_html
from .render.page import RenderSession, render_page, _playwright_version
from .render.errors import RenderError
from .storage import atomic_write_bytes, atomic_write_json, canonical_json_bytes, sha256_file

PREVIEW_VERSION = 1


class PreviewError(RenderError):
    """预览失败复用 CLI 已登记的合同错误出口。"""


def _digest(value):
    return hashlib.sha256(canonical_json_bytes(value)).hexdigest()


def _safe_destination(root, output_dir):
    target = root / "previews"
    if output_dir is not None and Path(output_dir).absolute() != target:
        raise PreviewError("preview_output_must_be_run_previews")
    if target.is_symlink() or (target.exists() and not target.is_dir()):
        raise PreviewError("preview_output_unsafe")
    if target.exists() and any(p.is_symlink() for p in target.rglob("*")):
        raise PreviewError("preview_output_unsafe")
    return target


def _cached_page(previous, cache_key, destination):
    if previous.get("status") != "ready" or previous.get("cache_key") != cache_key:
        return False
    for name, hash_key in (("artifact", "artifact_sha256"), ("sidecar", "sidecar_sha256")):
        filename = previous.get(name)
        if not isinstance(filename, str) or Path(filename).name != filename:
            return False
        path = destination / filename
        if path.is_symlink() or not path.is_file() or sha256_file(path) != previous.get(hash_key):
            return False
    try:
        receipt = json.loads((destination / previous["sidecar"]).read_text(encoding="utf-8"))
        if (receipt.get("binding_digest") != previous.get("binding_digest")
                or receipt.get("out_sha256") != previous["artifact_sha256"]
                or receipt.get("preview_kind") != "skeleton"):
            return False
    except (OSError, ValueError, AttributeError):
        return False
    return True


def _write_overview(destination, report):
    cards = []
    labels = {"pending": "待生成", "ready": "可查看", "failed": "需处理", "unsupported": "暂不支持"}
    for item in report["pages"]:
        title = escape(item["title"] or "无标题")
        status = item["status"]
        image = ""
        if status == "ready":
            data = base64.b64encode((destination / item["artifact"]).read_bytes()).decode("ascii")
            image = f'<img src="data:image/png;base64,{data}" alt="第 {item["number"]} 页骨架预览：{title}">'
        note = escape(item.get("message", "仅用于检查内容层次与布局，图片占位不代表成品。"))
        cards.append(f'<article class="{status}"><h2>第 {item["number"]} 页 · {title}</h2>'
                     f'<p class="status">{labels[status]}</p>{image}<details><summary>查看说明</summary><p>{note}</p></details></article>')
    risks = sum(p["status"] in {"failed", "unsupported"} for p in report["pages"])
    html = '''<!doctype html><html lang="zh-CN"><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<meta http-equiv="Content-Security-Policy" content="default-src 'none'; img-src data:; style-src 'unsafe-inline'">
<title>全册骨架预览</title><style>
*{box-sizing:border-box}body{margin:0;background:#f2f4f7;color:#182434;font:16px/1.6 system-ui,sans-serif}
header,main{max-width:1200px;margin:auto;padding:24px}h1{margin:0;font-size:28px}h2{font-size:18px;overflow-wrap:anywhere}
main{display:grid;grid-template-columns:repeat(auto-fit,minmax(min(100%,320px),1fr));gap:16px}article{background:white;padding:20px;border:1px solid #ccd4dc;border-radius:10px;min-width:0}
img{display:block;width:100%;height:auto;margin-top:12px}.failed,.unsupported{border:2px solid #a62929}.status{font-weight:700}
summary{cursor:pointer;color:#184d85}summary:focus-visible{outline:3px solid #2469ab;outline-offset:4px}@media(max-width:500px){header,main{padding:16px}h1{font-size:24px}}
</style><header><h1>全册骨架预览</h1>'''
    html += f'<p>共 {len(report["pages"])} 页 · 需处理 {risks} 页</p><p>检查标题、层次、密度和版式；骨架不是最终成品，也不代表视觉验收通过。</p></header><main>'
    html += "".join(cards) + "</main></html>"
    atomic_write_bytes(destination / "index.html", html.encode("utf-8"))


def render_run_preview(run_path: str | Path, *, output_dir: str | Path | None = None,
                       pages: list[str] | None = None) -> dict:
    """整册总览保持完整页集；pages 只指定此次允许重渲的页，其余有效缓存可复用。"""
    root = Path(run_path).resolve()
    destination = _safe_destination(root, output_dir)
    pack_path = root / "input/page-content-pack.json"
    if not pack_path.is_file():
        raise PreviewError("preview_content_pack_missing")
    raw_pack = pack_path.read_bytes()
    pack = json.loads(raw_pack)
    verify_content_pack(pack)
    ids = {p["page_id"] for p in pack["pages"]}
    if not ids or (pages is not None and (not pages or not set(pages).issubset(ids))):
        raise PreviewError("preview_page_selection_invalid")
    lock_path = root / ".preview.lock"
    if lock_path.is_symlink():
        raise PreviewError("preview_output_unsafe")
    started = monotonic()
    with FileLock(str(lock_path)):
        destination = _safe_destination(root, output_dir)
        destination.mkdir(parents=True, exist_ok=True)
        previous = {}
        try:
            old = json.loads((destination / "manifest.json").read_text(encoding="utf-8"))
            previous = {p["page_id"]: p for p in old["pages"]}
        except (OSError, ValueError, KeyError, TypeError):
            pass
        report = {"schema_version": PREVIEW_VERSION, "kind": "content-preview", "status": "partial",
                  "content_digest": pack["content_digest"], "design_digest": None,
                  "pages": [{"page_id": p["page_id"], "number": p["number"], "title": p.get("claim"),
                             "status": "pending", "cached": False} for p in pack["pages"]],
                  "external_calls": 0, "output_dir": str(destination)}
        design = root / "input/resolved-design.json"
        if design.exists():
            report["design_digest"] = json.loads(design.read_text())["design_digest"]
        _write_overview(destination, report)
        report["first_screen_ms"] = int((monotonic() - started) * 1000)
        renderer_files = [Path(__file__), Path(__file__).with_name("content_projection.py"),
                          *[Path(__file__).parent / "render" / f for f in ("page.py", "fonts.py", "assets.py", "layout.py")]]
        renderer_version = _digest([sha256_file(p) for p in renderer_files] + [_playwright_version()])
        with ExitStack() as resources:
            session = None
            for item in report["pages"]:
                try:
                    if pack_path.read_bytes() != raw_pack:
                        raise PreviewError("preview_inputs_changed")
                    loaded = load_run_binding(root, item["page_id"])
                    if loaded is None:
                        raise PreviewError("preview_binding_missing")
                    binding, page, resolver = loaded["binding"], loaded["pack_page"], loaded["resolver"]
                    item["binding_digest"] = binding["binding_digest"]
                    if binding["backend"] != "render:html":
                        item.update(status="unsupported", reason_code="preview_unsupported",
                                    message="此页尚无通过验证的确定性骨架，未替换为其他版式。")
                        continue
                    data = materialize_html(binding, page, resolver=resolver)
                    # 整册内容摘要变化不会让其他页面像素缓存失效；每次仍核验当前完整绑定。
                    cache_key = _digest({"data": data, "effective": binding["effective"],
                                         "slots": binding["slot_map"], "renderer": renderer_version,
                                         "overflow": os.environ.get("LEO_PPT_RENDER_OVERFLOW", "enforce")})
                    item["cache_key"] = cache_key
                    old = previous.get(item["page_id"], {})
                    if _cached_page(old, cache_key, destination):
                        item.update({k: old[k] for k in ("artifact", "artifact_sha256", "sidecar", "sidecar_sha256")})
                        receipt_path = destination / item["sidecar"]
                        receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
                        if receipt["binding_digest"] != binding["binding_digest"]:
                            # 像素不变但整册绑定已变；保留首次渲染身份，明确这是缓存复用。
                            receipt.setdefault("preview_cache", {
                                "rendered_binding_digest": receipt["binding_digest"],
                                "rendered_content_digest": receipt["content_digest"],
                                "cache_key": cache_key,
                            })
                            receipt.update(binding_digest=binding["binding_digest"],
                                           content_digest=binding["content_digest"])
                            atomic_write_json(receipt_path, receipt)
                            item["sidecar_sha256"] = sha256_file(receipt_path)
                        item.update(status="ready", cached=True)
                        continue
                    if pages is not None and item["page_id"] not in pages:
                        item.update(status="pending", message="此页没有有效缓存，本次未选择重渲。")
                        continue
                    if session is None:
                        session = resources.enter_context(RenderSession())
                    with tempfile.TemporaryDirectory(prefix=".render-", dir=destination) as temp:
                        temp = Path(temp)
                        data_path = temp / "data.json"
                        atomic_write_json(data_path, data)
                        png_path = temp / "page.png"
                        provenance = render_page(binding["template_id"], data_path, png_path,
                                                 size=(1280, 720), session=session, **loaded)
                        filename = "page-" + _digest(item["page_id"])[:20] + ".png"
                        sidecar = filename + ".render.json"
                        atomic_write_bytes(destination / filename, png_path.read_bytes())
                        provenance.update(out=str(destination / filename), sidecar=str(destination / sidecar),
                                          preview_kind="skeleton", preview_version=PREVIEW_VERSION)
                        atomic_write_json(destination / sidecar, provenance)
                        item.update(status="ready", artifact=filename, sidecar=sidecar,
                                    artifact_sha256=sha256_file(destination / filename),
                                    sidecar_sha256=sha256_file(destination / sidecar))
                except Exception as exc:
                    item.update(status="failed", reason_code=getattr(exc, "reason_code", "preview_page_failed"),
                                message="此页预览失败，修正内容或绑定后可单独重试。", error=str(exc)[:300])
                finally:
                    atomic_write_json(destination / "manifest.json", report)
                    _write_overview(destination, report)
        report["status"] = "ready" if all(p["status"] == "ready" for p in report["pages"]) else "partial"
        report["elapsed_ms"] = int((monotonic() - started) * 1000)
        report["performance_gate"] = {"first_screen_passed": report["first_screen_ms"] <= 30000,
                                      "deck_passed": report["elapsed_ms"] <= 60000}
        atomic_write_json(destination / "manifest.json", report)
        return report
