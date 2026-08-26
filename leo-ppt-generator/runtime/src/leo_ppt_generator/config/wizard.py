"""`leo-ppt config` 的交互式向导。

ConfigWizard 只负责 TTY 提问、已有配置预填、安全取消与提交分流；
不直接写文件。所有持久化与状态计算由 ConfigService 承担。
"""

from __future__ import annotations

import sys
import uuid
from dataclasses import dataclass
from typing import Callable, Mapping, Sequence

from ..credentials import (
    CredentialError,
    CredentialInputChannel,
    CredentialInputResolver,
    CredentialInputSelection,
)
from .models import ConfigReport, ConfigStatus, ProviderName, VerificationState
from .runtime_config import RuntimeConfigError, validate_endpoint_origin
from .service import (
    ConfigOverview,
    ConfigureRequest,
    ConfigService,
    ConfigServiceError,
    StatusRequest,
)


class WizardCancelled(Exception):
    reason_code = "wizard_cancelled"


@dataclass(frozen=True)
class WizardResult:
    report: ConfigReport
    cancelled: bool = False


class ConfigWizard:
    """终端配置向导；所有提示默认安全（不默认同意付费、不默认覆盖）。"""

    def __init__(
        self,
        service: ConfigService,
        resolver: CredentialInputResolver,
        *,
        input_stream=None,
        output_stream=None,
        prompt: Callable[[str], str] | None = None,
        confirm: Callable[[str, bool], bool] | None = None,
        menu: Callable[[Sequence[str], str], int | None] | None = None,
        key_stdin: bool = False,
        fixed_provider: ProviderName | str | None = None,
    ) -> None:
        self.service = service
        self.resolver = resolver
        self.input_stream = input_stream
        self.output_stream = output_stream
        self.key_stdin = key_stdin
        self.fixed_provider = (
            ProviderName(fixed_provider) if fixed_provider is not None else None
        )
        self._menu_injected = menu is not None
        self.prompt = prompt or self._default_prompt
        self.confirm = confirm or self._default_confirm
        self.menu = menu or self._default_menu

    def run(self, request: StatusRequest | None = None) -> WizardResult:
        """执行向导；交互调用始终允许检查并编辑已有配置。"""

        status_request = request or StatusRequest()
        if not self._has_interactive_input():
            # 安装器等非交互调用仍可安全读取已有状态，但不得尝试打开向导。
            report = self.service.status(status_request)
            if report.status.value in {"ready", "configured_unverified"}:
                return WizardResult(report=report)
            raise ConfigServiceError("credential_input_channel_unavailable")
        try:
            return self._configure(status_request)
        except (EOFError, KeyboardInterrupt):
            raise WizardCancelled() from None

    def _configure(self, request: StatusRequest) -> WizardResult:
        if self.fixed_provider is not None:
            return self._configure_provider(self.fixed_provider, request)

        last_result: WizardResult | None = None
        while True:
            overview = self.service.overview(request)
            if not any(item.configured for item in overview.providers):
                provider = self._quick_start()
                if provider is None:
                    raise WizardCancelled()
                last_result = self._configure_provider(provider, request)
                continue

            action = self._choose_home_action(overview)
            if action is None:
                if last_result is not None:
                    return last_result
                return WizardResult(report=overview.report, cancelled=True)
            if action == "edit_selected":
                if overview.selection is not None and overview.selection.provider is not ProviderName.BUILTIN_IMAGEGEN:
                    last_result = self._configure_provider(overview.selection.provider, request)
                continue
            if action == "add_provider":
                provider = self._choose_provider()
                if provider is not None:
                    last_result = self._configure_provider(provider, request)
                continue
            if action == "reorder":
                self._reorder(overview)
                continue
            if action == "prefer":
                provider = self._choose_provider()
                if provider is not None:
                    if self.confirm(
                        f"新任务将固定使用 {self._provider_label(provider)}，是否继续？",
                        False,
                    ):
                        self.service.set_preferred_provider(
                            request,
                            provider=provider,
                            operation_id=f"config-wizard-prefer-{provider.value}-{uuid.uuid4().hex}",
                        )
                continue
            if action == "clear_preference":
                if self.confirm("恢复自动选择，是否继续？", False):
                    self.service.clear_preferred_provider(
                        request,
                        operation_id=f"config-wizard-auto-{uuid.uuid4().hex}",
                    )
                continue
            if action == "list_providers":
                self._render_provider_list(overview)
                continue
            raise ConfigServiceError("config_wizard_action_invalid")

    def _configure_provider(
        self,
        provider: ProviderName,
        request: StatusRequest,
    ) -> WizardResult:
        snapshot = self.service.config_store.read()
        profiles = snapshot.values.get("provider_profiles", {})

        existing_profile = profiles.get(provider.value)
        endpoint_origin, model = self._profile_inputs(provider, existing_profile)
        selection, credential_kept = self._credential_selection(
            provider, existing_profile
        )
        operation_id = f"config-wizard-{provider.value}-{uuid.uuid4().hex}"
        changed = True
        try:
            if selection.credential_ref is None and selection.secret is None:
                raise ConfigServiceError("credential_input_channel_unavailable")

            profile_unchanged = self._profile_unchanged(
                provider,
                existing_profile,
                endpoint_origin=endpoint_origin,
                model=model,
            )
            if existing_profile is not None and credential_kept and profile_unchanged:
                changed = False
                report = self.service.status(request)
            else:
                report = self.service.configure(
                    ConfigureRequest(
                        provider=provider,
                        credential=selection,
                        endpoint_origin=endpoint_origin,
                        model=model,
                        status_request=request,
                        operation_id=operation_id,
                        overwrite_credential=(
                            existing_profile is not None and not credential_kept
                        ),
                    )
                )
        finally:
            # ConfigService 也在边界关闭 secret；这里保持适配层异常路径同样清零。
            selection.close()

        if not changed:
            self._write("配置未修改，已保留当前设置。")
        elif report.status == ConfigStatus.READY:
            self._write("配置完成，已验证可用，可以开始生成。")
        elif report.status == ConfigStatus.CONFIGURED_UNVERIFIED:
            if report.verification_state == VerificationState.STALE:
                self._write(
                    "配置已更新；此前的验证已失效（配置、模型或凭据已变化），"
                    "下次生成图片时会重新验证。"
                )
            else:
                self._write(
                    "配置已保存，但尚未真实验证；首次生成图片时会完成验证。"
                )
        return WizardResult(report=report)

    def _profile_inputs(
        self,
        provider: ProviderName,
        existing_profile: Mapping[str, object] | None,
    ) -> tuple[str | None, str]:
        endpoint_origin: str | None = None
        current_origin = (
            str(existing_profile.get("endpoint_origin"))
            if existing_profile is not None
            and existing_profile.get("endpoint_origin")
            else None
        )
        if provider is ProviderName.OPENAI_COMPATIBLE:
            while endpoint_origin is None:
                if current_origin is not None:
                    raw = self.prompt(
                        "请输入中转站 HTTPS 地址"
                        f"（当前 {current_origin}，回车保留）："
                    ).strip()
                    candidate = raw or current_origin
                else:
                    candidate = self.prompt(
                        "请输入中转站 HTTPS 地址（仅 origin，例如 https://api.example.com）："
                    ).strip()
                try:
                    endpoint_origin = validate_endpoint_origin(candidate)
                except RuntimeConfigError:
                    self._write(
                        "地址无效：请输入不含路径、用户名、查询串或片段的 HTTPS 地址。"
                    )

        definition = self.service.registry.provider(provider, endpoint_origin)
        current_model = (
            str(existing_profile.get("model"))
            if existing_profile is not None and existing_profile.get("model")
            else definition.default_model
        )
        model = current_model
        if existing_profile is not None:
            entered = self.prompt(
                f"请输入图片模型（当前 {current_model}，回车保留）："
            ).strip()
            if entered:
                model = entered
        elif provider is ProviderName.OPENAI_COMPATIBLE:
            entered = self.prompt(
                f"请输入图片模型（默认 {definition.default_model}）："
            ).strip()
            if entered:
                model = entered
        return endpoint_origin, model

    def _quick_start(self) -> ProviderName | None:
        if self._menu_injected:
            return self._choose_provider()
        choices = ("开始配置图片服务", "查看支持的服务", "退出")
        index = self.menu(choices, "图片服务设置")
        if index is None or index == 2:
            return None
        if index == 1:
            self._write("支持 OpenAI、OpenAI-compatible 中转站和 AtlasCloud。")
            return self._quick_start()
        self._write("请选择你已有账号的图片服务。完成配置后，Leo PPT 会自动记住你的选择。")
        return self._choose_provider()

    def _choose_provider(self) -> ProviderName | None:
        providers = (
            ProviderName.OPENAI,
            ProviderName.OPENAI_COMPATIBLE,
            ProviderName.ATLASCLOUD,
        )
        labels = [
            "OpenAI - 使用 OpenAI 官方图片服务",
            "OpenAI-compatible 中转站 - 使用已有的兼容服务商账号",
            "AtlasCloud - 使用 AtlasCloud 图片服务",
        ]
        if self.fixed_provider is not None:
            if self.fixed_provider not in providers:
                raise ConfigServiceError("unknown_provider")
            return self.fixed_provider
        choices = (*labels, "退出")
        if self._menu_injected:
            index = self.menu(choices, "选择图片服务 Provider")
        else:
            index = self._default_menu(
                choices,
                "选择图片服务 Provider",
            )
        if index is None or index >= len(providers):
            return None
        provider = providers[index]
        self._write_provider_setup_guide(provider)
        return provider

    def _write_provider_setup_guide(self, provider: ProviderName) -> None:
        guides = {
            ProviderName.OPENAI: (
                "OpenAI：用于直接使用 OpenAI 官方图片生成服务。\n"
                "没有账号或 API Key：请访问 https://platform.openai.com/ 注册、创建 API Key，并确认账号已开通 API 计费。\n"
                "接下来需要输入 API Key。"
            ),
            ProviderName.OPENAI_COMPATIBLE: (
                "OpenAI-compatible 中转站：用于接入兼容 OpenAI 图片接口的第三方或企业服务。\n"
                "请向中转站服务商或组织管理员申请：HTTPS 地址、API Key 和图片模型名称。\n"
                "接下来依次输入地址、模型和 API Key。"
            ),
            ProviderName.ATLASCLOUD: (
                "AtlasCloud：用于接入 AtlasCloud 图片服务。\n"
                "没有账号或 API Key：请向 AtlasCloud 服务商或组织管理员申请开通，并获取 API Key。\n"
                "接下来需要输入 API Key。"
            ),
        }
        self._write(guides[provider])

    def _choose_home_action(self, overview: ConfigOverview) -> str | None:
        self._render_overview(overview)
        labels = {
            "edit_selected": "修改当前服务",
            "add_provider": "添加备用服务",
            "reorder": "调整自动选择顺序",
            "prefer": "固定使用某个服务",
            "clear_preference": "恢复自动选择",
            "list_providers": "查看全部服务",
            "exit": "退出",
        }
        actions = overview.actions
        choices = tuple(labels[action] for action in actions)
        index = self.menu(choices, "请选择操作")
        if index is None or index >= len(actions) or actions[index] == "exit":
            return None
        return actions[index]

    def _render_overview(self, overview: ConfigOverview) -> None:
        if overview.selection is not None:
            status = (
                "可开始生成"
                if overview.report.status is ConfigStatus.READY
                else "已保存，首次生成图片时验证"
            )
            self._write("图片服务设置")
            self._write(f"状态：{status}")
            self._write(
                f"当前将使用：{self._provider_label(overview.selection.provider)}"
            )
            if overview.mode == "fixed":
                self._write("选择方式：固定首选")
            else:
                self._write(f"选择方式：自动选择（优先级 {overview.selection.priority}）")
            self._write("说明：新任务会优先使用此服务；添加备用服务不会影响当前设置。")
        else:
            self._write("图片服务设置")
            self._write("状态：需要处理")
            if overview.selection_error == "provider_priority_tie":
                self._write("两个服务的优先级相同，请调整顺序或固定使用其中一个服务。")
            else:
                self._write("尚未找到可用于生成图片的服务。")
        self._render_provider_list(overview)

    def _render_provider_list(self, overview: ConfigOverview) -> None:
        self._write("已配置服务")
        for item in overview.providers:
            if not item.configured:
                continue
            state = "已启用" if item.enabled else "未启用"
            credential = "已设置" if item.credential_available else "凭据缺失"
            current = " [当前]" if item.selected else ""
            priority = f" priority {item.priority}" if item.priority is not None else ""
            self._write(
                f"- {self._provider_label(item.provider)}  {state}{priority}  {credential}{current}"
            )

    def _reorder(self, overview: ConfigOverview) -> None:
        enabled = [item for item in overview.providers if item.enabled]
        if len(enabled) < 2:
            self._write("只有一个已启用服务，无需调整顺序。")
            return
        names = ", ".join(item.provider.value for item in enabled)
        raw = self.prompt(
            f"请输入自动选择顺序（逗号分隔，当前 {names}）："
        ).strip()
        if not raw:
            return
        providers = tuple(item.strip() for item in raw.split(",") if item.strip())
        try:
            self.service.reorder_provider_priorities(providers)
        except ConfigServiceError:
            self._write("顺序无效：请包含每个已启用服务一次，且不要重复。")

    @staticmethod
    def _provider_label(provider: ProviderName) -> str:
        return {
            ProviderName.OPENAI: "OpenAI",
            ProviderName.OPENAI_COMPATIBLE: "OpenAI-compatible 中转站",
            ProviderName.ATLASCLOUD: "AtlasCloud",
        }[provider]

    def _credential_selection(
        self,
        provider: ProviderName,
        existing_profile: Mapping[str, object] | None,
    ) -> tuple[CredentialInputSelection, bool]:
        if existing_profile is not None:
            source = str(existing_profile.get("credential_source", ""))
            reference = str(existing_profile.get("credential_ref", ""))
            if self.confirm(
                "当前凭据已设置。是否保留？",
                True,
            ):
                return self._preserved_credential(source, reference), True
            return self._resolve_credential(provider, force_new_secret=True), False
        return self._resolve_credential(provider), False

    @staticmethod
    def _preserved_credential(
        source: str, reference: str
    ) -> CredentialInputSelection:
        if source == "environment-reference":
            channel = CredentialInputChannel.ENVIRONMENT
            reason_code = "credential_environment_reference_preserved"
        elif source == "os-store-reference":
            channel = CredentialInputChannel.EXISTING_STORE
            reason_code = "credential_store_reference_preserved"
        else:
            raise ConfigServiceError("provider_profile_invalid")
        return CredentialInputSelection(
            channel=channel,
            reason_code=reason_code,
            credential_ref=reference,
        )

    @staticmethod
    def _profile_unchanged(
        provider: ProviderName,
        existing_profile: Mapping[str, object] | None,
        *,
        endpoint_origin: str | None,
        model: str,
    ) -> bool:
        if existing_profile is None or existing_profile.get("model") != model:
            return False
        if provider is ProviderName.OPENAI_COMPATIBLE:
            return existing_profile.get("endpoint_origin") == endpoint_origin
        return True

    def _resolve_credential(
        self,
        provider: ProviderName,
        *,
        force_new_secret: bool = False,
    ) -> CredentialInputSelection:
        renew = force_new_secret
        try:
            return self.resolver.select(
                provider.value,
                key_stdin=self.key_stdin,
                input_stream=self.input_stream,
                tty_stream=self.input_stream,
                force_new_secret=renew,
            )
        except CredentialError as error:
            raise ConfigServiceError(str(error)) from error

    def _has_interactive_input(self) -> bool:
        if self.input_stream is not None:
            return _is_tty(self.input_stream)
        # 注入 menu 的测试/宿主已显式承担交互；生产默认菜单仍要求真实 TTY。
        return self._menu_injected or _is_tty(sys.stdin)

    def _read_line(self, text: str) -> str:
        stream = self.input_stream or sys.stdin
        output = self.output_stream or sys.stdout
        print(text, end="", file=output, flush=True)
        value = stream.readline()
        if value == "":
            raise EOFError
        return value.rstrip("\r\n")

    def _default_prompt(self, text: str) -> str:
        return self._read_line(text)

    def _default_confirm(self, text: str, default: bool) -> bool:
        suffix = " [Y/n]" if default else " [y/N]"
        raw = self._read_line(f"{text}{suffix} ").strip().lower()
        if not raw:
            return default
        return raw in {"y", "yes"}

    def _default_menu(
        self,
        choices: Sequence[str],
        title: str,
        *,
        default_index: int | None = None,
    ) -> int | None:
        self._write(title)
        for index, choice in enumerate(choices, start=1):
            self._write(f"  {index}. {choice}")
        default_text = (
            f"，默认 {default_index + 1}" if default_index is not None else ""
        )
        raw = self._read_line(
            f"请选择 (1-{len(choices)}{default_text}): "
        ).strip()
        if not raw and default_index is not None:
            return default_index
        try:
            value = int(raw)
        except ValueError:
            return None
        if value < 1 or value > len(choices):
            return None
        return value - 1

    def _write(self, text: str) -> None:
        print(text, file=self.output_stream or sys.stdout)


def _is_tty(stream) -> bool:
    try:
        return bool(stream.isatty())
    except (AttributeError, OSError):
        return False


__all__ = ["ConfigWizard", "WizardCancelled", "WizardResult"]
