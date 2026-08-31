"""render lane 的稳定 reason code 错误类型。

与 ``contracts.ContractError`` 同族（子类），因此既有 CLI 错误映射
（``cli.ERRORS`` → stderr envelope + exit 2）无需扩展即可捕获；
区别在于 reason code 落在**实例**上，保证 ``render_*`` 命名稳定透传，
而不是被类级默认值 ``contract_error`` 吞掉。
"""

from __future__ import annotations

from ..contracts import ContractError


class RenderError(ContractError):
    """确定性渲染 lane 的合同失败；``reason_code`` 为稳定命名。"""

    def __init__(self, reason_code: str, detail: str = "") -> None:
        super().__init__(detail or reason_code)
        self.reason_code = reason_code
        self.detail = detail
