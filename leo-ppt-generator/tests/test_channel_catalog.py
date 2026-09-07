"""渠道目录（providers.yaml）组合行为的单元测试。

覆盖四条红线：
  1. 目录加载 fail-closed，registry / 凭据 / 配置映射全部从目录派生；
  2. backend contract 对渠道回填默认端点与默认模型，端点覆盖仍 origin-only；
  3. 执行上下文按 origin + 渠道固定 api_path 派生 base URL，不猜 /v1；
  4. schemas provider enum 与目录一致；通用模块不出现渠道名硬编码
     （配置与通用代码隔离）。
另含 vendor 补丁 0008（url→b64 回退）的聚焦回归。
"""

from __future__ import annotations

import json
import os
import re
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

SKILL_DIR = Path(__file__).resolve().parents[1]
RUNTIME_SRC = SKILL_DIR / "runtime" / "src"
if str(RUNTIME_SRC) not in sys.path:
    sys.path.insert(0, str(RUNTIME_SRC))

from leo_ppt_generator.backend_execution import (  # noqa: E402
    BackendExecutionError,
    build_execution_context,
)
from leo_ppt_generator.config.backend_contract import (  # noqa: E402
    BackendContractError,
    BackendRegistry,
)
from leo_ppt_generator.config import channel_catalog  # noqa: E402
from leo_ppt_generator.config.runtime_config import (  # noqa: E402
    EXTERNAL_PROVIDERS,
    ENVIRONMENT_REFERENCES,
    configure_provider_profile,
    load_runtime_config,
)
from leo_ppt_generator.credentials import PROVIDERS  # noqa: E402

CHANNEL_IDS = frozenset(
    {
        "qianxing", "zhipu", "dashscope", "ark", "qianfan", "hunyuan", "modelscope",
        # 2026-09 业界调研接入批：OpenAI 兼容聚合/厂商通道 + 原生协议通道。
        "siliconflow", "stepfun", "xai", "deepinfra", "together",
        "gemini", "minimax", "ideogram",
    }
)
BUILTIN_PROVIDER_IDS = frozenset(
    {"openai", "openai-compatible", "atlascloud", "builtin-imagegen", "fixture"}
)


class ChannelCatalogCompositionTest(unittest.TestCase):
    def test_catalog_loads_expected_channels_with_derived_maps(self):
        names = set(channel_catalog.channel_names())
        self.assertEqual(names, CHANNEL_IDS)
        for channel in channel_catalog.channels():
            self.assertEqual(channel.api_base_url, f"{channel.endpoint_origin}{channel.api_path}")
            self.assertIn(channel.default_model, channel.models)
            self.assertIn(channel.id, PROVIDERS)
            self.assertIn(channel.id, EXTERNAL_PROVIDERS)
            self.assertEqual(
                ENVIRONMENT_REFERENCES[channel.id],
                f"env:{channel.credential_environment}",
            )
            self.assertEqual(PROVIDERS[channel.id], channel.credential_environment)

    def test_channel_environment_variables_do_not_collide(self):
        environments = [c.credential_environment for c in channel_catalog.channels()]
        self.assertEqual(len(environments), len(set(environments)))

    def test_registry_channels_are_generate_only(self):
        registry = BackendRegistry.default()
        generate_candidates = {b.name for b in registry.candidates({"generate"})}
        edit_candidates = {b.name for b in registry.candidates({"edit"})}
        self.assertTrue(CHANNEL_IDS.issubset(generate_candidates))
        self.assertFalse(CHANNEL_IDS & edit_candidates)
        for channel_id in CHANNEL_IDS:
            definition = registry.provider_registry.provider(channel_id)
            self.assertEqual(definition.default_model, channel_catalog.channel_by_name(channel_id).default_model)


class ChannelBackendContractTest(unittest.TestCase):
    def setUp(self):
        self.registry = BackendRegistry.default()

    def test_create_contract_fills_channel_defaults(self):
        contract = self.registry.create_contract("zhipu", mode="generate")
        channel = channel_catalog.channel_by_name("zhipu")
        self.assertEqual(contract["endpoint_origin"], channel.endpoint_origin)
        self.assertEqual(contract["model"], channel.default_model)
        self.assertEqual(contract["credential_ref"], "env:ZHIPU_API_KEY")
        self.assertEqual(contract["backend_kind"], "openai-compatible")
        self.assertFalse(contract["capabilities"]["edit"])
        # 自校验通过（load 复核全部声明）。
        self.registry.load(contract, required={"generate"})

    def test_channel_endpoint_override_must_be_origin_only(self):
        contract = self.registry.create_contract(
            "zhipu", mode="generate", endpoint_origin="https://open.bigmodel.cn"
        )
        self.assertEqual(contract["endpoint_origin"], "https://open.bigmodel.cn")
        bad = dict(contract)
        bad["endpoint_origin"] = "https://evil.example.com/api/paas/v4"
        with self.assertRaises(BackendContractError):
            self.registry.load(bad, required={"generate"})

    def test_channel_endpoint_is_optional_at_load_time(self):
        contract = self.registry.create_contract("ark", mode="generate")
        without_endpoint = {k: v for k, v in contract.items() if k != "endpoint_origin"}
        self.registry.load(without_endpoint, required={"generate"})

    def test_openai_compatible_still_requires_endpoint(self):
        with self.assertRaises(BackendContractError):
            self.registry.create_contract("openai-compatible", mode="generate")


class ChannelExecutionContextTest(unittest.TestCase):
    def _write_contract(self, provider: str, *, drop_endpoint: bool = False) -> Path:
        registry = BackendRegistry.default()
        contract = registry.create_contract(provider, mode="generate")
        if drop_endpoint:
            contract.pop("endpoint_origin", None)
        handle = tempfile.NamedTemporaryFile(
            "w", suffix=".json", delete=False, encoding="utf-8"
        )
        json.dump(contract, handle)
        handle.close()
        return Path(handle.name)

    def setUp(self):
        self._previous = os.environ.get("ZHIPU_API_KEY")
        os.environ["ZHIPU_API_KEY"] = "sk-zhipu-test-key"
        self._isolated = tempfile.TemporaryDirectory(prefix="leo-ppt-exec-")

    def tearDown(self):
        if self._previous is None:
            os.environ.pop("ZHIPU_API_KEY", None)
        else:
            os.environ["ZHIPU_API_KEY"] = self._previous
        self._isolated.cleanup()

    def test_execution_context_derives_channel_base_url_without_v1_guess(self):
        contract_path = self._write_contract("zhipu")
        context = build_execution_context(contract_path, self._isolated.name)
        self.assertEqual(
            context.environment["OPENAI_BASE_URL"],
            "https://open.bigmodel.cn/api/paas/v4",
        )
        self.assertEqual(context.environment["OPENAI_API_KEY"], "sk-zhipu-test-key")
        self.assertNotIn("sk-zhipu-test-key", json.dumps(context.receipt))

    def test_execution_context_injects_channel_param_compat(self):
        # WS1 回归：目录登记的实测兼容矩阵随执行上下文注入 vendored 环境。
        from leo_ppt_generator.config.channel_catalog import reset_cache
        reset_cache()
        contract_path = self._write_contract("zhipu")
        context = build_execution_context(contract_path, self._isolated.name)
        compat = context.environment.get("LEO_PPT_PARAM_COMPAT", "")
        self.assertIn('"rejects"', compat)
        self.assertIn("quality", compat)
        self.assertIn("2097152", compat)

    def test_execution_context_injects_contract_model_into_vendor_env(self):
        # D-DEF-01 回归：合同 model 必须显式进入 vendored 工具读取的环境变量，
        # 否则渠道合同（如 ark 的 doubao-seedream）会静默回落 gpt-image-2。
        contract_path = self._write_contract("zhipu")
        context = build_execution_context(contract_path, self._isolated.name)
        self.assertEqual(
            context.environment["CODEX_PPT_IMAGE_MODEL"],
            "cogview-4",
        )
        self.assertEqual(context.model, "cogview-4")
        self.assertEqual(context.receipt["model"], "cogview-4")

    def test_execution_context_falls_back_to_catalog_default_origin(self):
        contract_path = self._write_contract("zhipu", drop_endpoint=True)
        context = build_execution_context(contract_path, self._isolated.name)
        self.assertEqual(
            context.environment["OPENAI_BASE_URL"],
            "https://open.bigmodel.cn/api/paas/v4",
        )

    def test_execution_context_supports_every_channel(self):
        expected = {
            channel.id: f"{channel.endpoint_origin}{channel.api_path}"
            for channel in channel_catalog.channels()
        }
        for provider, base_url in expected.items():
            with self.subTest(provider=provider):
                env_key = PROVIDERS[provider]
                previous = os.environ.get(env_key)
                os.environ[env_key] = f"sk-{provider}-test"
                try:
                    contract_path = self._write_contract(provider)
                    context = build_execution_context(contract_path, self._isolated.name)
                    self.assertEqual(context.environment["OPENAI_BASE_URL"], base_url)
                finally:
                    if previous is None:
                        os.environ.pop(env_key, None)
                    else:
                        os.environ[env_key] = previous


class ChannelProfileRoundtripTest(unittest.TestCase):
    def test_configure_provider_profile_writes_normalized_channel_profile(self):
        with tempfile.TemporaryDirectory(prefix="leo-ppt-config-") as home:
            configure_provider_profile(
                "zhipu", model="cogview-3-flash", home=home
            )
            profile = load_runtime_config(home=home).values["provider_profiles"]["zhipu"]
            self.assertEqual(profile["model"], "cogview-3-flash")
            self.assertEqual(profile["credential_ref"], "env:ZHIPU_API_KEY")
            self.assertNotIn("endpoint_origin", profile)


class SchemaSyncTest(unittest.TestCase):
    """schemas 的 provider enum 必须覆盖目录渠道；新增渠道两处同步。"""

    SCHEMA_FILES = (
        "backend-contract-v1.schema.json",
        "verification-receipt-v1.json",
        "config-report-v1.json",
        "credential-status-v1.schema.json",
    )

    def test_schema_enums_cover_channel_providers(self):
        schemas_dir = RUNTIME_SRC / "leo_ppt_generator" / "schemas"
        expected = {"openai", "openai-compatible", "atlascloud"} | CHANNEL_IDS
        for name in self.SCHEMA_FILES:
            with self.subTest(schema=name):
                document = json.loads((schemas_dir / name).read_text(encoding="utf-8"))
                enum = self._find_provider_enum(document)
                self.assertIsNotNone(enum, name)
                self.assertTrue(expected.issubset(set(enum)), f"{name}: {enum}")

    @staticmethod
    def _find_provider_enum(node):
        if isinstance(node, dict):
            if node.get("enum") and "openai" in node["enum"]:
                return node["enum"]
            for value in node.values():
                found = SchemaSyncTest._find_provider_enum(value)
                if found is not None:
                    return found
        elif isinstance(node, list):
            for value in node:
                found = SchemaSyncTest._find_provider_enum(value)
                if found is not None:
                    return found
        return None


class ConfigCodeIsolationTest(unittest.TestCase):
    """配置与通用代码隔离：通用模块不得硬编码渠道名。"""

    def test_generic_runtime_modules_do_not_hardcode_channel_ids(self):
        pattern = re.compile(
            r"\b(" + "|".join(sorted(CHANNEL_IDS)) + r")\b"
        )
        src_root = RUNTIME_SRC / "leo_ppt_generator"
        offenders = []
        for path in sorted(src_root.rglob("*.py")):
            if "__pycache__" in path.parts:
                continue
            # 厂商适配器目录按厂商命名文件/类/hostname 是设计意图
            # （atlascloud.py 同范式）；渠道 id 只在此目录作为分发键出现。
            if "_vendor" in path.parts and "image_providers" in path.parts:
                continue
            text = path.read_text(encoding="utf-8")
            if pattern.search(text):
                offenders.append(str(path.relative_to(src_root)))
        self.assertEqual(offenders, [], f"渠道名泄漏进通用代码: {offenders}")


class VendorUrlFallbackPatchTest(unittest.TestCase):
    """patches/0008 聚焦回归：_image_payload 优先 b64，缺失时按 url 下载。"""

    @classmethod
    def setUpClass(cls):
        vendor_root = RUNTIME_SRC / "leo_ppt_generator" / "_vendor" / "codex_ppt"
        if str(vendor_root) not in sys.path:
            sys.path.insert(0, str(vendor_root))
        from image_providers import openai_compatible as module

        cls.module = module

    def test_image_payload_prefers_b64_and_downloads_url(self):
        module = self.module
        self.assertEqual(
            module._image_payload(SimpleNamespace(b64_json="QUJD", url="https://x/y.png")),
            "QUJD",
        )
        original = module._download_image_b64
        module._download_image_b64 = lambda url, timeout_seconds=120.0: "REdBQg=="
        try:
            self.assertEqual(
                module._image_payload(SimpleNamespace(b64_json=None, url="https://x/y.png")),
                "REdBQg==",
            )
        finally:
            module._download_image_b64 = original
        with self.assertRaises(ValueError):
            module._image_payload(SimpleNamespace(b64_json=None, url=None))


class WizardChannelMenuTest(unittest.TestCase):
    """向导菜单与引导：渠道条目从目录派生，布局遵循用户约定。"""

    @classmethod
    def setUpClass(cls):
        from leo_ppt_generator.config.models import ProviderName
        from leo_ppt_generator.config.wizard import ConfigWizard

        cls.ProviderName = ProviderName
        cls.ConfigWizard = ConfigWizard
        cls.registry = BackendRegistry.default().provider_registry

    def _wizard(self, *, menu_answers=(), prompts=()):
        menu_calls: list[tuple[str, ...]] = []
        prompt_answers = list(prompts)

        def menu(choices, title):
            menu_calls.append(choices)
            return menu_answers[len(menu_calls) - 1] if len(menu_calls) <= len(menu_answers) else None

        def prompt(text):
            return prompt_answers.pop(0) if prompt_answers else ""

        wizard = self.ConfigWizard(
            service=SimpleNamespace(registry=self.registry),
            resolver=SimpleNamespace(select=lambda *a, **k: (_ for _ in ()).throw(AssertionError("unused"))),
            menu=menu,
            prompt=prompt,
            confirm=lambda *a, **k: False,
        )
        return wizard, menu_calls

    def test_provider_menu_lists_channels_with_key_page_layout(self):
        wizard, menu_calls = self._wizard(menu_answers=(None,))
        self.assertIsNone(wizard._choose_provider())
        choices = menu_calls[0]
        self.assertEqual(choices[-1], "返回上级")
        self.assertIn(
            "智谱渠道（open.bigmodel.cn/usercenter/apikeys）- 使用智谱官方图片服务",
            choices,
        )
        channel_lines = [c for c in choices if "渠道（" in c]
        self.assertEqual(len(channel_lines), len(CHANNEL_IDS))
        # featured 渠道排菜单第一位；其余渠道跟在三个内置 provider 之后。
        featured = channel_catalog.featured_channel()
        self.assertIsNotNone(featured)
        self.assertTrue(choices[0].startswith(featured.display_name))
        self.assertTrue(choices[0].endswith("（推荐）"))
        self.assertEqual(
            choices.index(next(c for c in channel_lines if featured.display_name not in c)),
            4,
        )

    def test_choose_featured_channel_is_menu_first(self):
        wizard, _ = self._wizard(menu_answers=(0,))
        provider = wizard._choose_provider()
        self.assertEqual(provider.value, channel_catalog.featured_channel().id)

    def test_choose_channel_returns_catalog_member(self):
        wizard, _ = self._wizard(menu_answers=(4,))  # 首个非 featured 渠道
        provider = wizard._choose_provider()
        channel = channel_catalog.channel_by_name(provider.value)
        self.assertIsNotNone(channel)
        self.assertFalse(channel.featured)
        self.assertEqual(provider, self.ProviderName(channel.id))

    def test_overview_exposes_profile_model(self):
        import tempfile

        from leo_ppt_generator.config.runtime_config import (
            configure_provider_profile,
            load_runtime_config,
        )
        from leo_ppt_generator.config.service import ConfigService
        from leo_ppt_generator.config.wizard import ConfigWizard
        from leo_ppt_generator.config.service import StatusRequest
        from leo_ppt_generator.credentials import CredentialInputResolver, credential_manager
        from leo_ppt_generator import cli as leo_cli

        with tempfile.TemporaryDirectory(prefix="leo-ov-") as home:
            leo_cli.default_home = lambda *a, **k: Path(home)
            configure_provider_profile(
                "qianxing", model="gpt-image-1", home=home
            )
            service = leo_cli._config_service()
            overview = service.overview(StatusRequest())
            item = next(
                i for i in overview.providers if i.provider.value == "qianxing"
            )
            self.assertEqual(item.model, "gpt-image-1")
            self.assertEqual(
                overview.to_dict()["providers"][0].get("model")
                if overview.to_dict()["providers"]
                and overview.to_dict()["providers"][0].get("provider") == "qianxing"
                else None,
                "gpt-image-1",
            )

    def test_overview_actions_offer_featured_shortcut(self):
        from leo_ppt_generator.config.service import ConfigService

        without = ConfigService._overview_actions(
            profiles={"openai": {"priority": 100}},
            mode="automatic",
            selection_error=None,
        )
        self.assertEqual(without[0], "configure_featured")
        with_featured = ConfigService._overview_actions(
            profiles={"openai": {}, "qianxing": {}},
            mode="automatic",
            selection_error=None,
        )
        self.assertNotIn("configure_featured", with_featured)
        # 固定模式下仍提供切换入口（prefer），恢复自动选择并存。
        fixed = ConfigService._overview_actions(
            profiles={"openai": {}, "qianxing": {}},
            mode="fixed",
            selection_error=None,
        )
        self.assertIn("prefer", fixed)
        self.assertIn("clear_preference", fixed)

    def test_featured_channel_is_unique_in_catalog(self):
        featured = [c for c in channel_catalog.channels() if c.featured]
        self.assertEqual(len(featured), 1)
        self.assertEqual(featured[0].credential_environment, "QIANXING_API_KEY")

    def test_channel_setup_guide_mentions_portal_env_and_models(self):
        wizard, _ = self._wizard()
        import io

        buffer = io.StringIO()
        wizard.output_stream = buffer
        wizard._write_provider_setup_guide(self.ProviderName("zhipu"))
        guide = buffer.getvalue()
        for expected in (
            "https://open.bigmodel.cn/",
            "https://open.bigmodel.cn/usercenter/apikeys",
            "ZHIPU_API_KEY",
            "cogview-4",
        ):
            self.assertIn(expected, guide)

    def test_channel_profile_inputs_default_endpoint_and_model(self):
        wizard, _ = self._wizard(prompts=("", ""))
        endpoint, model = wizard._profile_inputs(
            self.ProviderName("zhipu"), existing_profile=None
        )
        self.assertEqual(endpoint, "https://open.bigmodel.cn")
        self.assertEqual(model, "cogview-4")

    def test_provider_name_composes_channels(self):
        members = {member.value for member in self.ProviderName}
        self.assertTrue(CHANNEL_IDS.issubset(members))
        self.assertIn("builtin-imagegen", members)


class ChannelCatalogFailClosedTest(unittest.TestCase):
    def test_invalid_catalog_entries_are_rejected(self):
        with tempfile.TemporaryDirectory(prefix="leo-ppt-catalog-") as tmp:
            base = channel_catalog.load_channels()
            good = base[0]
            base_fields = {k: v for k, v in vars(good).items() if k != "param_compat"}
            cases = {
                "channel_id_invalid": {
                    **base_fields,
                    "id": "OpenAI",
                },
                "channel_endpoint_origin_invalid": {
                    **base_fields,
                    "endpoint_origin": "https://host/path",
                },
                "channel_api_path_invalid": {**base_fields, "api_path": "v4"},
                "channel_default_model_not_listed": {
                    **base_fields,
                    "default_model": "not-in-models",
                },
            }
            for reason_code, entry in cases.items():
                path = Path(tmp) / f"{reason_code}.yaml"
                path.write_text(
                    json.dumps(
                        {"schema_version": 1, "channels": [entry]}, ensure_ascii=False
                    ),
                    encoding="utf-8",
                )
                with self.subTest(case=reason_code):
                    with self.assertRaises(channel_catalog.ChannelCatalogError) as caught:
                        channel_catalog.load_channels(path)
                    self.assertEqual(caught.exception.reason_code, reason_code)


if __name__ == "__main__":
    unittest.main()
