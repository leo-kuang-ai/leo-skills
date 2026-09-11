"""渠道探针不得把已知不合法的尺寸或缺少凭据报告为就绪。"""
import importlib.util
import io
import json
import os
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "provider_health.py"
spec = importlib.util.spec_from_file_location("provider_health", SCRIPT)
health = importlib.util.module_from_spec(spec)
spec.loader.exec_module(health)


class ProviderHealthTests(unittest.TestCase):
    def test_l3_is_not_called_after_parameter_preflight_rejects(self):
        with patch.object(health.sys, "argv", ["health", "--level", "3", "--providers", "qianxing"]), \
             patch.object(health, "_level1", return_value={"registered": True, "status": "ok"}), \
             patch.object(health, "_level2", return_value={"status": "param_face_rejected"}), \
             patch.object(health, "_level3") as live, \
             patch.object(health.sys, "stdout", new_callable=io.StringIO):
            self.assertEqual(health.main(), 1)
            live.assert_not_called()

    def test_no_legal_aspect_stops_before_subprocess(self):
        compat = SimpleNamespace(size=(("multiples_of", 512), ("min_edge", 1024),
                                       ("max_edge", 1536)), rejects=(),
                                 as_env_json=lambda: "{}")
        channel = SimpleNamespace(param_compat=compat, default_model="gpt-image-1")
        with patch.object(health, "channel_by_name", return_value=channel), \
             patch.object(health.subprocess, "run") as run:
            self.assertIsNone(health._probe_size("fixture"))
            for probe in (health._level2, health._level3):
                self.assertEqual(probe("fixture")["status"], "aspect_ratio_unsupported")
            run.assert_not_called()

    def test_size_solver_finds_legal_non_menu_size(self):
        channel = SimpleNamespace(param_compat=SimpleNamespace(
            size=(("multiples_of", 8), ("min_edge", 576), ("max_edge", 1024))))
        with patch.object(health, "channel_by_name", return_value=channel):
            self.assertEqual(health._probe_size("fixture"), "1024x576")

    def test_missing_credentials_are_explicit(self):
        with patch.object(health, "_credential_state", return_value={
            "in_process_env": False, "keychain_resolved": False,
        }):
            self.assertEqual(health._level1("zhipu")["status"], "credentials_missing")

    def test_dry_run_clears_inherited_channel_constraints(self):
        channel = SimpleNamespace(default_model="fixture-model", param_compat=SimpleNamespace(
            size=(), rejects=(), as_env_json=lambda: "{}"))
        def dry_run(*args, **kwargs):
            self.assertFalse("LEO_PPT_PARAM_COMPAT" in kwargs["env"], "继承了其他渠道约束")
            return SimpleNamespace(returncode=0, stdout=json.dumps({"model": "fixture-model"}))
        with patch.object(health, "channel_by_name", return_value=channel), \
             patch.dict(os.environ, {"LEO_PPT_PARAM_COMPAT": '{"size":{"max_edge":1}}'}), \
             patch.object(health.subprocess, "run", side_effect=dry_run):
            self.assertEqual(health._level2("fixture")["status"], "ok")


if __name__ == "__main__":
    unittest.main()
