"""聚焦回归（patches/0009）：渠道模型的执行面参数合同。

覆盖三处 vendored 修改：
  ① _validate_model 接受渠道合同模型（doubao-seedream / cogview 等）；
  ② _validate_size 对非 gpt-image-2 模型接受 WIDTHxHEIGHT 渠道尺寸档；
  ③ generate --dry-run 的请求体：quality 仅对 gpt-image 家族发送。
"""
from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
import unittest
from pathlib import Path

SKILL_ROOT = Path(__file__).resolve().parents[1]
IMAGE_GEN = (
    SKILL_ROOT / "runtime" / "src" / "leo_ppt_generator" / "_vendor"
    / "codex_ppt" / "image_gen.py"
)


def _load_module():
    # vendored 脚本以平级 import 引用同目录模块（image_providers 等），
    # 需先把其目录挂上 sys.path 再按路径加载。
    sys.path.insert(0, str(IMAGE_GEN.parent))
    try:
        spec = importlib.util.spec_from_file_location("leo_vendored_image_gen", IMAGE_GEN)
        module = importlib.util.module_from_spec(spec)
        sys.modules.setdefault("leo_vendored_image_gen", module)
        spec.loader.exec_module(module)
        return module
    finally:
        sys.path.remove(str(IMAGE_GEN.parent))


class ChannelModelValidationTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.mod = _load_module()

    def test_channel_contract_models_are_legal(self):
        # D-DEF-02 回归：不再要求模型名含 gpt-image-。
        for model in ("cogview-4", "doubao-seedream-4-0-250828", "gpt-image-2"):
            self.assertIsNone(self.mod._validate_model(model))

    def test_empty_model_still_rejected(self):
        with self.assertRaises(SystemExit):
            self.mod._validate_model("   ")


class ChannelSizeValidationTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.mod = _load_module()

    def test_channel_model_accepts_custom_width_height(self):
        # 渠道尺寸档（16:9 交付画布基准）交由服务端终裁。
        self.assertIsNone(
            self.mod._validate_size("2560x1440", "doubao-seedream-4-0-250828")
        )

    def test_gpt_image_2_size_rules_unchanged(self):
        with self.assertRaises(SystemExit):
            self.mod._validate_size("2500x1440", "gpt-image-2")  # 非 16 倍数


class ChannelCompatLookupTest(unittest.TestCase):
    """WS1 回归：LEO_PPT_PARAM_COMPAT 查表优先于家族推断。"""

    def _dry_run(self, model: str, compat: dict | None) -> dict:
        import subprocess
        env = {"PATH": "/usr/bin:/bin", "CODEX_PPT_IMAGE_MODEL": model}
        if compat is not None:
            env["LEO_PPT_PARAM_COMPAT"] = json.dumps(compat)
        result = subprocess.run(
            [sys.executable, str(IMAGE_GEN), "generate", "--dry-run",
             "--model", model, "--size", "1792x1008",
             "--prompt", "probe", "--out", "/tmp/leo-compat-probe.png"],
            capture_output=True, text=True, timeout=60, env=env,
        )
        return result

    def test_registered_rejects_beat_family_default(self):
        # gpt-image-2 默认发送 quality；渠道矩阵拒收则必须省略。
        result = self._dry_run("gpt-image-2", {"rejects": ["quality"]})
        self.assertEqual(result.returncode, 0, result.stderr[-200:])
        request = json.loads(result.stdout)
        self.assertNotIn("quality", request)
        self.assertIn("output_format", request)

    def test_registered_size_constraints_reject_violations(self):
        # cogview-4 实测约束：2560x1440 超 2^21 像素 → 渲染前清晰报错。
        result = self._dry_run(
            "cogview-4",
            {"size": {"multiples_of": 16, "min_edge": 512, "max_edge": 2880,
                      "max_pixels": 2097152}},
        )
        # 该用例直接用 2560x1440 触发约束（覆盖 _dry_run 的 1792x1008）。
        import subprocess
        env = {"PATH": "/usr/bin:/bin", "CODEX_PPT_IMAGE_MODEL": "cogview-4",
               "LEO_PPT_PARAM_COMPAT": json.dumps(
                   {"size": {"multiples_of": 16, "min_edge": 512,
                             "max_edge": 2880, "max_pixels": 2097152}})}
        result = subprocess.run(
            [sys.executable, str(IMAGE_GEN), "generate", "--dry-run",
             "--model", "cogview-4", "--size", "2560x1440",
             "--prompt", "probe", "--out", "/tmp/leo-compat-probe2.png"],
            capture_output=True, text=True, timeout=60, env=env,
        )
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("channel size menu violated", result.stderr)


class BatchCompatGatingTest(unittest.TestCase):
    """批处理每任务回写点：渠道模型不上行 output_format（回归核对③）。"""

    def test_batch_channel_model_omits_output_format(self):
        import subprocess, tempfile, json
        from pathlib import Path
        with tempfile.TemporaryDirectory() as tmp:
            jobs = Path(tmp) / "jobs.jsonl"
            jobs.write_text(
                json.dumps({"prompt": "probe"}) + "\n", encoding="utf-8")
            result = subprocess.run(
                [sys.executable, str(IMAGE_GEN), "generate-batch", "--dry-run",
                 "--model", "cogview-4", "--size", "1792x1008",
                 "--input", str(jobs), "--out-dir", tmp],
                capture_output=True, text=True, timeout=60,
                env={"PATH": "/usr/bin:/bin", "CODEX_PPT_IMAGE_MODEL": "cogview-4",
                     "LEO_PPT_PARAM_COMPAT": json.dumps({"rejects": ["quality"]})},
            )
            self.assertEqual(result.returncode, 0, result.stderr[-200:])
            body = result.stdout
            self.assertNotIn('"output_format"', body)
            self.assertNotIn("quality", body)


class QualityParamFamilyGatingTest(unittest.TestCase):
    def _dry_run_request(self, model: str) -> dict:
        result = subprocess.run(
            [sys.executable, str(IMAGE_GEN), "generate", "--dry-run",
             "--model", model, "--size", "2560x1440",
             "--prompt", "probe", "--out", "/tmp/leo-0009-probe.png"],
            capture_output=True, text=True, timeout=60,
            env={"PATH": "/usr/bin:/bin", "CODEX_PPT_IMAGE_MODEL": model},
        )
        self.assertEqual(result.returncode, 0, result.stderr[-300:])
        return json.loads(result.stdout)

    def test_quality_omitted_for_channel_model(self):
        # D-DEF-03 回归：cogview-4 拒收 quality（zhipu 400 code 1214）。
        request = self._dry_run_request("cogview-4")
        self.assertEqual(request["model"], "cogview-4")
        self.assertNotIn("quality", request)

    def test_quality_kept_for_gpt_image_family(self):
        request = self._dry_run_request("gpt-image-2")
        self.assertEqual(request["quality"], "medium")


if __name__ == "__main__":
    unittest.main()
