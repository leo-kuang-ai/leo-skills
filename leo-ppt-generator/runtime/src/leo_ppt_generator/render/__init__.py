"""渲染与质量闭环层（D 柱渲染 lane + E 柱交付收据）的运行时模块。

M0 仅落地 E1 交付指纹收据（``receipt``）；D 柱渲染 backend 在后续里程碑
按设计文档 §3.1-§3.5 增补 ``page`` / ``chart`` / ``raster`` / ``variants``。
"""

from .receipt import (
    FINGERPRINT_CLASSES,
    RECEIPT_RELATIVE_PATH,
    ReceiptError,
    create_delivery_receipt,
    verify_delivery_receipt,
)

__all__ = [
    "FINGERPRINT_CLASSES",
    "RECEIPT_RELATIVE_PATH",
    "ReceiptError",
    "create_delivery_receipt",
    "verify_delivery_receipt",
]
