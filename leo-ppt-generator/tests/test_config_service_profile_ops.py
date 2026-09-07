"""ConfigService profile 治理操作（remove/enabled）的单元测试。

覆盖计划 U1 的七条场景：移除语义（preferred 清理 / not_found no-op /
receipt invalidation）、启停语义（字段保留 / 未配置报错）、CAS 冲突不半写。
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path
from types import SimpleNamespace

SKILL_DIR = Path(__file__).resolve().parents[1]
RUNTIME_SRC = SKILL_DIR / "runtime" / "src"
if str(RUNTIME_SRC) not in sys.path:
    sys.path.insert(0, str(RUNTIME_SRC))

from leo_ppt_generator.config.models import ProviderName  # noqa: E402
from leo_ppt_generator.config.runtime_config import RuntimeConfigError  # noqa: E402
from leo_ppt_generator.config.service import (  # noqa: E402
    ConfigService,
    ConfigServiceError,
    StatusRequest,
)


class FakeConfigStore:
    def __init__(self, document, *, conflict=False):
        self._document = document
        self._conflict = conflict
        self.commits: list[dict] = []

    @property
    def document(self):
        return self._document

    def read(self):
        return SimpleNamespace(
            document=self._document,
            values=self._document,
            canonical_digest="digest-1",
            validation_issues=(),
        )

    def compare_and_swap(self, expected_digest, candidate):
        if self._conflict or expected_digest != "digest-1":
            raise RuntimeConfigError("config_write_conflict")
        self._document = dict(candidate)
        self.commits.append(dict(candidate))


class FakeCredentialStore:
    def status(self, provider):
        return "missing"

    def reference(self, provider):
        return None

    def fingerprint_key(self, create=False):
        return None


class FakeReceiptStore:
    def __init__(self):
        self.invalidations: list[tuple] = []

    def invalidate(self, provider, reason, operation_id):
        self.invalidations.append((provider, reason, operation_id))

    def inspect(self, provider, fingerprint, now):
        return None


def make_service(document, *, conflict=False):
    store = FakeConfigStore(document, conflict=conflict)
    registry = SimpleNamespace(
        provider=lambda name, endpoint_origin=None: SimpleNamespace(
            supported_capabilities=frozenset(), default_model="gpt-image-2"
        )
    )
    receipts = FakeReceiptStore()
    service = ConfigService(store, FakeCredentialStore(), registry, receipts)
    return service, store, receipts


def profile(**overrides):
    base = {
        "model": "cogview-4",
        "enabled": True,
        "priority": 10,
        "credential_source": "environment-reference",
        "credential_ref": "ZHIPU_API_KEY",
    }
    base.update(overrides)
    return base


class RemoveProviderTests(unittest.TestCase):
    def test_remove_deletes_profile_and_keeps_siblings(self):
        service, store, _ = make_service(
            {"schema_version": 2, "provider_profiles": {"zhipu": profile(), "ark": profile()}}
        )
        result = service.remove_provider(
            "zhipu", operation_id="op-remove-zhipu"
        )
        self.assertEqual(result, "provider_removed")
        self.assertEqual(
            set(store.document["provider_profiles"]), {"ark"}
        )
        self.assertEqual(len(store.commits), 1)

    def test_remove_clears_preference_pointing_at_removed_provider(self):
        service, store, _ = make_service(
            {
                "schema_version": 2,
                "preferred_provider": "zhipu",
                "provider_profiles": {"zhipu": profile(), "ark": profile()},
            }
        )
        service.remove_provider("zhipu", operation_id="op-remove-zhipu")
        self.assertNotIn("preferred_provider", store.document)

    def test_remove_keeps_preference_for_other_providers(self):
        service, store, _ = make_service(
            {
                "schema_version": 2,
                "preferred_provider": "ark",
                "provider_profiles": {"zhipu": profile(), "ark": profile()},
            }
        )
        service.remove_provider("zhipu", operation_id="op-remove-zhipu")
        self.assertEqual(store.document.get("preferred_provider"), "ark")

    def test_remove_unknown_provider_is_noop(self):
        service, store, receipts = make_service(
            {"schema_version": 2, "provider_profiles": {}}
        )
        result = service.remove_provider("zhipu", operation_id="op-remove-zhipu")
        self.assertEqual(result, "provider_not_found")
        self.assertEqual(store.commits, [])
        self.assertEqual(receipts.invalidations, [])

    def test_remove_invalidates_verification_receipt(self):
        service, _, receipts = make_service(
            {"schema_version": 2, "provider_profiles": {"zhipu": profile()}}
        )
        service.remove_provider("zhipu", operation_id="op-remove-zhipu")
        self.assertEqual(
            receipts.invalidations,
            [(ProviderName.ZHIPU, "provider_removed", "op-remove-zhipu")],
        )

    def test_remove_surfaces_cas_conflict_without_write(self):
        service, store, receipts = make_service(
            {"schema_version": 2, "provider_profiles": {"zhipu": profile()}},
            conflict=True,
        )
        with self.assertRaises(ConfigServiceError) as ctx:
            service.remove_provider("zhipu", operation_id="op-remove-zhipu")
        self.assertEqual(ctx.exception.reason_code, "config_write_conflict")
        self.assertEqual(store.commits, [])
        self.assertEqual(receipts.invalidations, [])


class SetProviderEnabledTests(unittest.TestCase):
    def test_enabled_toggle_writes_flag_and_preserves_fields(self):
        service, store, _ = make_service(
            {"schema_version": 2, "provider_profiles": {"zhipu": profile()}}
        )
        service.set_provider_enabled("zhipu", enabled=False)
        updated = store.document["provider_profiles"]["zhipu"]
        self.assertIs(updated["enabled"], False)
        self.assertEqual(updated["model"], "cogview-4")
        self.assertEqual(updated["priority"], 10)
        self.assertEqual(updated["credential_source"], "environment-reference")

    def test_enabled_toggle_back_to_true(self):
        service, store, _ = make_service(
            {
                "schema_version": 2,
                "provider_profiles": {"zhipu": profile(enabled=False)},
            }
        )
        service.set_provider_enabled("zhipu", enabled=True)
        self.assertIs(store.document["provider_profiles"]["zhipu"]["enabled"], True)

    def test_enabled_requires_existing_profile(self):
        service, _, _ = make_service({"schema_version": 2, "provider_profiles": {}})
        with self.assertRaises(ConfigServiceError) as ctx:
            service.set_provider_enabled("zhipu", enabled=True)
        self.assertEqual(ctx.exception.reason_code, "provider_profile_invalid")

    def test_enabled_surfaces_cas_conflict(self):
        service, store, _ = make_service(
            {"schema_version": 2, "provider_profiles": {"zhipu": profile()}},
            conflict=True,
        )
        with self.assertRaises(ConfigServiceError) as ctx:
            service.set_provider_enabled("zhipu", enabled=False)
        self.assertEqual(ctx.exception.reason_code, "config_write_conflict")
        self.assertEqual(store.commits, [])


class SetProviderPriorityTests(unittest.TestCase):
    def test_priority_write_preserves_other_fields(self):
        service, store, _ = make_service(
            {"schema_version": 2, "provider_profiles": {"zhipu": profile(priority=10)}}
        )
        service.set_provider_priority("zhipu", priority=5)
        updated = store.document["provider_profiles"]["zhipu"]
        self.assertEqual(updated["priority"], 5)
        self.assertEqual(updated["model"], "cogview-4")
        self.assertIs(updated["enabled"], True)

    def test_priority_rejects_out_of_range_and_non_int(self):
        service, store, _ = make_service(
            {"schema_version": 2, "provider_profiles": {"zhipu": profile()}}
        )
        for bad in (0, 1001, -1, True, "10", 1.5, None):
            with self.subTest(bad=bad):
                with self.assertRaises(ConfigServiceError) as ctx:
                    service.set_provider_priority("zhipu", priority=bad)
                self.assertEqual(ctx.exception.reason_code, "provider_priority_invalid")
        self.assertEqual(store.commits, [])

    def test_priority_requires_existing_profile(self):
        service, _, _ = make_service({"schema_version": 2, "provider_profiles": {}})
        with self.assertRaises(ConfigServiceError) as ctx:
            service.set_provider_priority("zhipu", priority=10)
        self.assertEqual(ctx.exception.reason_code, "provider_profile_invalid")

    def test_priority_surfaces_cas_conflict(self):
        service, store, _ = make_service(
            {"schema_version": 2, "provider_profiles": {"zhipu": profile()}},
            conflict=True,
        )
        with self.assertRaises(ConfigServiceError) as ctx:
            service.set_provider_priority("zhipu", priority=7)
        self.assertEqual(ctx.exception.reason_code, "config_write_conflict")
        self.assertEqual(store.commits, [])

    def test_priority_allows_duplicate_values(self):
        # 重复权重交由选择层 tie 语义处理，服务层不拒绝。
        service, store, _ = make_service(
            {"schema_version": 2, "provider_profiles": {"zhipu": profile(), "ark": profile()}}
        )
        service.set_provider_priority("zhipu", priority=10)
        service.set_provider_priority("ark", priority=10)
        self.assertEqual(
            [p["priority"] for p in store.document["provider_profiles"].values()],
            [10, 10],
        )


class StatusRequestImportTests(unittest.TestCase):
    def test_status_request_remains_importable_contract(self):
        self.assertIsNotNone(StatusRequest())


if __name__ == "__main__":
    unittest.main()
