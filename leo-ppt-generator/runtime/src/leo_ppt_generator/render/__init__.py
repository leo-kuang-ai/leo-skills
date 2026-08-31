"""渲染与质量闭环层（D 柱渲染 lane + E 柱交付收据）的运行时模块。

- M0（E1）：``receipt`` 交付指纹收据。
- M1（γ）：D 柱确定性渲染 lane——``readiness``（三态探测）、``page``
  （HTML 模板 → PNG）、``chart``（mermaid → SVG）、``raster``（resvg
  SVG → PNG）、``fonts``（渲染期 HTTP 字体服务）、``provenance``
  （sidecar 校验与 slide entry 并入）。
"""

from .errors import RenderError
from .receipt import (
    FINGERPRINT_CLASSES,
    RECEIPT_RELATIVE_PATH,
    ReceiptError,
    create_delivery_receipt,
    verify_delivery_receipt,
)
from .readiness import ReadinessReport, render_ready
from .provenance import (
    RENDER_BACKENDS,
    attach_provenance_to_slide,
    load_render_receipt,
    verify_receipt_matches_artifact,
)

__all__ = [
    "FINGERPRINT_CLASSES",
    "RECEIPT_RELATIVE_PATH",
    "ReceiptError",
    "RenderError",
    "ReadinessReport",
    "RENDER_BACKENDS",
    "create_delivery_receipt",
    "verify_delivery_receipt",
    "render_ready",
    "attach_provenance_to_slide",
    "load_render_receipt",
    "verify_receipt_matches_artifact",
]
