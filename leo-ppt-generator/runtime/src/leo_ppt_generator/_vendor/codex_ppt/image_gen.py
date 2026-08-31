#!/usr/bin/env python3
"""Fallback CLI for codex-ppt image generation or editing with GPT Image models.

Used when Codex's built-in image tool is unavailable, when the user explicitly
opts into API mode, or when explicit transparent output requires the
`gpt-image-1.5` fallback path.

Defaults to gpt-image-2 and a structured prompt augmentation workflow.
Reads OPENAI_API_KEY, and optionally OPENAI_BASE_URL for provider adapters or
OpenAI-compatible proxy providers.
"""

from __future__ import annotations

import argparse
import asyncio
import base64
from io import BytesIO
import json
import mimetypes
import os
from pathlib import Path
import re
import shutil
import sys
import tempfile
import threading
import time
from typing import Any, Dict, Iterable, List, Optional, Tuple
from urllib.parse import urlparse
from urllib.request import urlopen

from image_providers import create_image_provider
from image_providers.atlascloud import atlascloud_model_for_operation

DEFAULT_MODEL = "gpt-image-2"
DEFAULT_SIZE = "2560x1440"
DEFAULT_QUALITY = "medium"
DEFAULT_OUTPUT_FORMAT = "png"
DEFAULT_CONCURRENCY = 5
DEFAULT_DOWNSCALE_SUFFIX = "-web"
DEFAULT_OUTPUT_PATH = "output/imagegen/output.png"
GPT_IMAGE_MODEL_PREFIX = "gpt-image-"

ALLOWED_LEGACY_SIZES = frozenset({"1024x1024", "1536x1024", "1024x1536", "auto"})
ALLOWED_QUALITIES = {"low", "medium", "high", "auto"}
ALLOWED_BACKGROUNDS = {"transparent", "opaque", "auto", None}
ALLOWED_INPUT_FIDELITIES = {"low", "high", None}

GPT_IMAGE_2_MODEL = "gpt-image-2"
GPT_IMAGE_2_MIN_PIXELS = 655_360
GPT_IMAGE_2_MAX_PIXELS = 8_294_400
GPT_IMAGE_2_MAX_EDGE = 3840
GPT_IMAGE_2_MAX_RATIO = 3.0

MAX_IMAGE_BYTES = 50 * 1024 * 1024
MAX_BATCH_JOBS = 500
DEFAULT_RUNTIME_HOME = "~/.codex-ppt-skill"
ENV_FIELDS = ("OPENAI_API_KEY", "OPENAI_BASE_URL", "CODEX_PPT_IMAGE_MODEL")

# Rate-limit policy (mirrors the geekai image adapter semantics): retry ONLY
# HTTP 429, with a fixed 2s/4s/8s exponential backoff ladder, and throttle all
# provider calls through a process-wide QPS limiter.
HTTP_TOO_MANY_REQUESTS = 429
RATE_LIMIT_BACKOFF_SECONDS = (2.0, 4.0, 8.0)
IMAGE_QPS_ENV = "LEO_PPT_IMAGE_QPS"
DEFAULT_IMAGE_QPS = 4.0

# Batch resume (mirrors the geekai ppt-service semantics: persist each slide's
# image as soon as it lands, and on resume regenerate only the slides whose
# persisted record plus on-disk output are missing). The manifest is an
# append-only JSONL log in the batch out-dir; one complete JSON object per
# line, written immediately after each job's outcome is known.
BATCH_MANIFEST_NAME = "batch-manifest.jsonl"
MANIFEST_ERROR_SUMMARY_MAX_CHARS = 300

# Version retention (--keep-versions): rotate a pre-existing output to
# <stem>.v<N><ext> instead of overwriting it, and log every version to an
# append-only image-history.jsonl next to the outputs (mirrors geekai's
# slide image_history + SetActiveSlideVersion semantics).
IMAGE_HISTORY_NAME = "image-history.jsonl"

# Reference-image preprocessing (geekai PrepareReferenceInputsForImg2Img
# semantics): local files become data URLs, remote/data URLs pass through.
REFERENCE_MIME_TYPES = {
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".webp": "image/webp",
    ".gif": "image/gif",
}
_MIME_TO_EXTENSION = {
    "image/png": ".png",
    "image/jpeg": ".jpg",
    "image/webp": ".webp",
    "image/gif": ".gif",
}


def _die(message: str, code: int = 1) -> None:
    print(f"Error: {message}", file=sys.stderr)
    raise SystemExit(code)


def _warn(message: str) -> None:
    print(f"Warning: {message}", file=sys.stderr)


class _QpsLimiter:
    """Thread-safe fixed-interval throttle with no burst allowance.

    Mirrors Go's rate.NewLimiter(qps, 1): at most `qps` acquisitions per
    second, spaced `1/qps` apart. `reserve` plans the wait under the lock and
    returns it; the caller sleeps outside the lock so concurrent threads never
    serialize on the mutex while waiting. Clock and sleep are injectable for
    tests.
    """

    def __init__(self, qps: float, *, clock=time.monotonic, sleep=time.sleep) -> None:
        self._interval = 1.0 / qps if qps > 0 else 0.0
        self._clock = clock
        self._sleep = sleep
        self._lock = threading.Lock()
        self._next_ok = 0.0

    def reserve(self) -> float:
        """Reserve the next call slot and return how long to wait first."""
        if self._interval <= 0.0:
            return 0.0
        with self._lock:
            now = self._clock()
            wait = max(0.0, self._next_ok - now)
            self._next_ok = max(now, self._next_ok) + self._interval
            return wait

    def acquire(self) -> None:
        wait = self.reserve()
        if wait > 0:
            self._sleep(wait)


_RATE_LIMITER: Optional[_QpsLimiter] = None


def _configured_qps() -> float:
    raw = os.getenv(IMAGE_QPS_ENV, "").strip()
    if not raw:
        return DEFAULT_IMAGE_QPS
    try:
        qps = float(raw)
    except ValueError:
        _warn(f"Invalid {IMAGE_QPS_ENV}={raw!r}; using default {DEFAULT_IMAGE_QPS} QPS.")
        return DEFAULT_IMAGE_QPS
    if qps <= 0:
        _warn(f"{IMAGE_QPS_ENV}={raw!r} must be > 0; using default {DEFAULT_IMAGE_QPS} QPS.")
        return DEFAULT_IMAGE_QPS
    return qps


def _rate_limiter() -> _QpsLimiter:
    global _RATE_LIMITER
    if _RATE_LIMITER is None:
        _RATE_LIMITER = _QpsLimiter(_configured_qps())
    return _RATE_LIMITER


def _is_rate_limit_error(exc: Exception) -> bool:
    """True only for HTTP 429 rate limiting, not for other failures."""
    status = getattr(exc, "status_code", None)
    if isinstance(status, int) and status == HTTP_TOO_MANY_REQUESTS:
        return True
    name = exc.__class__.__name__.lower()
    if "ratelimit" in name or "rate_limit" in name:
        return True
    msg = str(exc).lower()
    return "429" in msg or "too many requests" in msg or "rate limit" in msg


def _call_rate_limited(func, *, sleep=time.sleep):
    """Run func() under the global QPS limiter with 429-only backoff retry.

    Retries only HTTP 429 errors, sleeping 2s/4s/8s between attempts (one
    initial call plus at most three retries). Any other exception propagates
    immediately, and after the final retry the 429 itself propagates unwrapped
    — errors are never swallowed. `sleep` is injectable for tests.
    """
    backoffs = RATE_LIMIT_BACKOFF_SECONDS
    for attempt in range(len(backoffs) + 1):
        _rate_limiter().acquire()
        try:
            return func()
        except Exception as exc:
            if attempt == len(backoffs) or not _is_rate_limit_error(exc):
                raise
            wait_s = backoffs[attempt]
            _warn(
                f"HTTP 429 rate limited; backing off {wait_s:.0f}s "
                f"(retry {attempt + 1}/{len(backoffs)})"
            )
            sleep(wait_s)
    raise RuntimeError("unreachable")  # pragma: no cover


def _runtime_home() -> Path:
    return Path(os.getenv("CODEX_PPT_HOME", DEFAULT_RUNTIME_HOME)).expanduser()


def _runtime_env_path() -> Path:
    return _runtime_home() / ".env"


def _load_runtime_env() -> None:
    path = _runtime_env_path()
    if not path.exists():
        return
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        if key not in ENV_FIELDS or os.getenv(key):
            continue
        value = value.strip().strip('"').strip("'")
        os.environ[key] = value


def _default_model() -> str:
    return os.getenv("CODEX_PPT_IMAGE_MODEL", DEFAULT_MODEL)


def _api_base_url() -> Optional[str]:
    return os.getenv("OPENAI_BASE_URL") or None


def _api_target_label() -> str:
    base_url = _api_base_url()
    if base_url:
        if _is_atlascloud_base_url(base_url):
            return f"AtlasCloud provider adapter (OPENAI_BASE_URL={base_url})"
        return f"third-party image API or OpenAI-compatible proxy (OPENAI_BASE_URL={base_url})"
    return "official OpenAI API (OPENAI_BASE_URL unset)"


def _is_atlascloud_base_url(base_url: str) -> bool:
    hostname = urlparse(base_url).hostname or ""
    return "atlascloud.ai" in hostname.lower()


def _preview_endpoint(kind: str) -> str:
    base_url = _api_base_url()
    if base_url and _is_atlascloud_base_url(base_url):
        return "/api/v1/model/generateImage"
    if kind == "edit":
        return "/v1/images/edits"
    return "/v1/images/generations"


def _preview_model(model: str, kind: str) -> str:
    base_url = _api_base_url()
    if base_url and _is_atlascloud_base_url(base_url):
        operation = "edit" if kind == "edit" else "text-to-image"
        return atlascloud_model_for_operation(model, operation)
    return model


def _runtime_python_path() -> str:
    home = _runtime_home()
    if os.name == "nt":
        return str(home / ".venv" / "Scripts" / "python.exe")
    return str(home / ".venv" / "bin" / "python")


def _skill_root() -> Path:
    return Path(__file__).resolve().parents[1]


def _dependency_hint(package: str, *, upgrade: bool = False) -> str:
    package_arg = f"-U {package}" if upgrade else package
    runtime_python = _runtime_python_path()
    requirements = _skill_root() / "requirements.txt"
    return (
        "Install codex-ppt dependencies in the shared runtime first, for example "
        f"`python3 {_skill_root() / 'scripts' / 'codex_ppt_runtime.py'} bootstrap`, "
        f"or install {package} directly with `{runtime_python} -m pip install "
        f"{package_arg}`. Requirements file: `{requirements}`."
    )


def _ensure_api_key(dry_run: bool) -> None:
    if os.getenv("OPENAI_API_KEY"):
        print(f"OPENAI_API_KEY is set. API target: {_api_target_label()}.", file=sys.stderr)
        return
    if dry_run:
        _warn(f"OPENAI_API_KEY is not set; dry-run only. API target: {_api_target_label()}.")
        return
    runtime_script = _skill_root() / "scripts" / "codex_ppt_runtime.py"
    config_doc = _skill_root() / "docs" / "image-model-configuration.md"
    base_url = _api_base_url()
    model = _default_model()
    if base_url:
        command = (
            f'python3 {runtime_script} config --api-key "your-api-key" '
            f'--base-url "{base_url}" --model {model}'
        )
        target_hint = f"Detected third-party OpenAI-compatible API via OPENAI_BASE_URL={base_url}."
    else:
        command = f'python3 {runtime_script} config --api-key "your-api-key" --model {model}'
        target_hint = "Detected official OpenAI API mode because OPENAI_BASE_URL is not set."
    _die(
        "OPENAI_API_KEY is not set for codex-ppt CLI/API fallback.\n"
        f"{target_hint}\n"
        "Use the built-in image tool if it is available. Otherwise configure the shared runtime once:\n"
        f"  {command}\n"
        "To use a third-party proxy, set OPENAI_BASE_URL and the provider's model name.\n"
        f"Details: {config_doc}"
    )


def _read_prompt(prompt: Optional[str], prompt_file: Optional[str]) -> str:
    if prompt and prompt_file:
        _die("Use --prompt or --prompt-file, not both.")
    if prompt_file:
        if prompt_file == "-":
            return sys.stdin.read().strip()
        path = Path(prompt_file)
        if not path.exists():
            _die(f"Prompt file not found: {path}")
        return path.read_text(encoding="utf-8").strip()
    if prompt:
        return prompt.strip()
    _die("Missing prompt. Use --prompt or --prompt-file.")
    return ""  # unreachable


def _check_image_paths(paths: Iterable[str]) -> List[Path]:
    resolved: List[Path] = []
    for raw in paths:
        path = Path(raw)
        if not path.exists():
            _die(f"Image file not found: {path}")
        if path.stat().st_size > MAX_IMAGE_BYTES:
            _warn(f"Image exceeds 50MB limit: {path}")
        resolved.append(path)
    return resolved


def prepare_reference_inputs(items: Iterable[str]) -> List[str]:
    """Normalize img2img reference inputs into provider-consumable strings.

    Mirrors geekai's PrepareReferenceInputsForImg2Img: an existing local file
    becomes a ``data:<mime>;base64,...`` URL (MIME inferred from the file
    extension); http(s) URLs and already-encoded data URLs pass through
    unchanged. Raises ValueError with a clear message for missing files or
    extensions without a known image MIME type.
    """
    prepared: List[str] = []
    for raw in items:
        item = str(raw).strip()
        if not item:
            raise ValueError("empty reference image input")
        if item.startswith("data:"):
            prepared.append(item)
            continue
        if item.lower().startswith(("http://", "https://")):
            prepared.append(item)
            continue
        path = Path(item).expanduser()
        if not path.exists():
            raise ValueError(f"reference image file not found: {item}")
        mime = REFERENCE_MIME_TYPES.get(path.suffix.lower())
        if mime is None:
            supported = ", ".join(sorted(REFERENCE_MIME_TYPES))
            raise ValueError(
                f"unsupported reference image extension {path.suffix!r} for {item}; "
                f"expected one of: {supported}"
            )
        encoded = base64.b64encode(path.read_bytes()).decode("ascii")
        prepared.append(f"data:{mime};base64,{encoded}")
    return prepared


def _is_remote_reference(raw: str) -> bool:
    item = str(raw).strip()
    return item.startswith("data:") or item.lower().startswith(("http://", "https://"))


def _materialize_reference(prepared: str, tmp_dir: Path) -> Path:
    """Stage one prepared reference (data URL or http URL) as a local file.

    Both bundled providers' edit() contract requires local file Paths (they
    re-encode to data URLs themselves where needed), so non-file references
    normalized by prepare_reference_inputs are materialized to temp files for
    the duration of the provider call.
    """
    if prepared.startswith("data:"):
        header, _, payload = prepared.partition(",")
        mime = header[len("data:") :].split(";", 1)[0] or "image/png"
        data = base64.b64decode(payload)
    else:
        mime = mimetypes.guess_type(prepared)[0] or "image/png"
        with urlopen(prepared, timeout=60) as response:
            data = response.read()
    suffix = _MIME_TO_EXTENSION.get(mime, ".png")
    fd, name = tempfile.mkstemp(dir=str(tmp_dir), prefix="ref-", suffix=suffix)
    with os.fdopen(fd, "wb") as fh:
        fh.write(data)
    return Path(name)


def _normalize_output_format(fmt: Optional[str]) -> str:
    if not fmt:
        return DEFAULT_OUTPUT_FORMAT
    fmt = fmt.lower()
    if fmt not in {"png", "jpeg", "jpg", "webp"}:
        _die("output-format must be png, jpeg, jpg, or webp.")
    return "jpeg" if fmt == "jpg" else fmt


def _parse_size(size: str) -> Optional[Tuple[int, int]]:
    match = re.fullmatch(r"([1-9][0-9]*)x([1-9][0-9]*)", size)
    if not match:
        return None
    return int(match.group(1)), int(match.group(2))


def _validate_gpt_image_2_size(size: str) -> None:
    if size == "auto":
        return

    parsed = _parse_size(size)
    if parsed is None:
        _die("gpt-image-2 size must be auto or WIDTHxHEIGHT, for example 1024x1024.")

    width, height = parsed
    max_edge = max(width, height)
    min_edge = min(width, height)
    total_pixels = width * height

    if max_edge > GPT_IMAGE_2_MAX_EDGE:
        _die("gpt-image-2 size maximum edge length must be less than or equal to 3840px.")
    if width % 16 != 0 or height % 16 != 0:
        _die("gpt-image-2 size width and height must be multiples of 16px.")
    if max_edge / min_edge > GPT_IMAGE_2_MAX_RATIO:
        _die("gpt-image-2 size long edge to short edge ratio must not exceed 3:1.")
    if total_pixels < GPT_IMAGE_2_MIN_PIXELS or total_pixels > GPT_IMAGE_2_MAX_PIXELS:
        _die(
            "gpt-image-2 size total pixels must be at least 655,360 and no more than 8,294,400."
        )


def _validate_size(size: str, model: str) -> None:
    if GPT_IMAGE_2_MODEL in model:
        _validate_gpt_image_2_size(size)
        return

    if size not in ALLOWED_LEGACY_SIZES:
        _die(
            "size must be one of 1024x1024, 1536x1024, 1024x1536, or auto for this GPT Image model."
        )


def _validate_quality(quality: str) -> None:
    if quality not in ALLOWED_QUALITIES:
        _die("quality must be one of low, medium, high, or auto.")


def _validate_background(background: Optional[str]) -> None:
    if background not in ALLOWED_BACKGROUNDS:
        _die("background must be one of transparent, opaque, or auto.")


def _validate_input_fidelity(input_fidelity: Optional[str]) -> None:
    if input_fidelity not in ALLOWED_INPUT_FIDELITIES:
        _die("input-fidelity must be one of low or high.")


def _validate_model(model: str) -> None:
    if GPT_IMAGE_MODEL_PREFIX not in model:
        _die(
            "model must be a GPT Image model name containing 'gpt-image-' "
            "(for example gpt-image-2, openai/gpt-image-2, gpt-image-1.5, "
            "gpt-image-1, or gpt-image-1-mini)."
        )


def _is_gpt_image_2_model(model: str) -> bool:
    return GPT_IMAGE_2_MODEL in model


def _validate_transparency(background: Optional[str], output_format: str) -> None:
    if background == "transparent" and output_format not in {"png", "webp"}:
        _die("transparent background requires output-format png or webp.")


def _validate_model_specific_options(
    *,
    model: str,
    background: Optional[str],
    input_fidelity: Optional[str] = None,
) -> None:
    if not _is_gpt_image_2_model(model):
        return
    if background == "transparent":
        _die(
            "transparent backgrounds are not supported in gpt-image-2, the latest model. "
            "Use --model gpt-image-1.5 --background transparent --output-format png instead."
        )
    if input_fidelity is not None:
        _die(
            "input_fidelity is not supported in gpt-image-2 because image inputs always use high fidelity for this model."
        )


def _validate_generate_payload(payload: Dict[str, Any]) -> None:
    model = str(payload.get("model", DEFAULT_MODEL))
    _validate_model(model)
    n = int(payload.get("n", 1))
    if n < 1 or n > 10:
        _die("n must be between 1 and 10")
    size = str(payload.get("size", DEFAULT_SIZE))
    quality = str(payload.get("quality", DEFAULT_QUALITY))
    background = payload.get("background")
    _validate_size(size, model)
    _validate_quality(quality)
    _validate_background(background)
    _validate_model_specific_options(model=model, background=background)
    oc = payload.get("output_compression")
    if oc is not None and not (0 <= int(oc) <= 100):
        _die("output_compression must be between 0 and 100")


def _build_output_paths(
    out: str,
    output_format: str,
    count: int,
    out_dir: Optional[str],
) -> List[Path]:
    ext = "." + output_format

    if out_dir:
        out_base = Path(out_dir)
        out_base.mkdir(parents=True, exist_ok=True)
        return [out_base / f"image_{i}{ext}" for i in range(1, count + 1)]

    out_path = Path(out)
    if out_path.exists() and out_path.is_dir():
        out_path.mkdir(parents=True, exist_ok=True)
        return [out_path / f"image_{i}{ext}" for i in range(1, count + 1)]

    if out_path.suffix == "":
        out_path = out_path.with_suffix(ext)
    elif output_format and out_path.suffix.lstrip(".").lower() != output_format:
        _warn(
            f"Output extension {out_path.suffix} does not match output-format {output_format}."
        )

    if count == 1:
        return [out_path]

    return [
        out_path.with_name(f"{out_path.stem}-{i}{out_path.suffix}")
        for i in range(1, count + 1)
    ]


def _augment_prompt(args: argparse.Namespace, prompt: str) -> str:
    fields = _fields_from_args(args)
    return _augment_prompt_fields(args.augment, prompt, fields)


def _augment_prompt_fields(augment: bool, prompt: str, fields: Dict[str, Optional[str]]) -> str:
    if not augment:
        return prompt

    sections: List[str] = []
    if fields.get("use_case"):
        sections.append(f"Use case: {fields['use_case']}")
    sections.append(f"Primary request: {prompt}")
    if fields.get("scene"):
        sections.append(f"Scene/background: {fields['scene']}")
    if fields.get("subject"):
        sections.append(f"Subject: {fields['subject']}")
    if fields.get("style"):
        sections.append(f"Style/medium: {fields['style']}")
    if fields.get("composition"):
        sections.append(f"Composition/framing: {fields['composition']}")
    if fields.get("lighting"):
        sections.append(f"Lighting/mood: {fields['lighting']}")
    if fields.get("palette"):
        sections.append(f"Color palette: {fields['palette']}")
    if fields.get("materials"):
        sections.append(f"Materials/textures: {fields['materials']}")
    if fields.get("text"):
        sections.append(f"Text (verbatim): \"{fields['text']}\"")
    if fields.get("constraints"):
        sections.append(f"Constraints: {fields['constraints']}")
    if fields.get("negative"):
        sections.append(f"Avoid: {fields['negative']}")

    return "\n".join(sections)


def _fields_from_args(args: argparse.Namespace) -> Dict[str, Optional[str]]:
    return {
        "use_case": getattr(args, "use_case", None),
        "scene": getattr(args, "scene", None),
        "subject": getattr(args, "subject", None),
        "style": getattr(args, "style", None),
        "composition": getattr(args, "composition", None),
        "lighting": getattr(args, "lighting", None),
        "palette": getattr(args, "palette", None),
        "materials": getattr(args, "materials", None),
        "text": getattr(args, "text", None),
        "constraints": getattr(args, "constraints", None),
        "negative": getattr(args, "negative", None),
    }


def _print_request(payload: dict) -> None:
    print(json.dumps(payload, indent=2, sort_keys=True))


def _validate_generated_image_bytes(image_bytes: bytes, expected_size: str) -> None:
    try:
        from PIL import Image
    except Exception:
        _die(f"Slide image validation requires Pillow. {_dependency_hint('pillow')}")
    try:
        with Image.open(BytesIO(image_bytes)) as image:
            image.load()
            actual = f"{image.width}x{image.height}"
    except Exception:
        _die("Provider returned an unreadable image.")
    if expected_size != "auto" and actual != expected_size:
        _die(
            f"Provider returned an unexpected image size ({actual}); required {expected_size}."
        )


def _derive_downscale_path(path: Path, suffix: str) -> Path:
    if suffix and not suffix.startswith("-") and not suffix.startswith("_"):
        suffix = "-" + suffix
    return path.with_name(f"{path.stem}{suffix}{path.suffix}")


def _downscale_image_bytes(image_bytes: bytes, *, max_dim: int, output_format: str) -> bytes:
    try:
        from PIL import Image
    except Exception:
        _die(f"Downscaling requires Pillow. {_dependency_hint('pillow')}")

    if max_dim < 1:
        _die("--downscale-max-dim must be >= 1")

    with Image.open(BytesIO(image_bytes)) as img:
        img.load()
        w, h = img.size
        scale = min(1.0, float(max_dim) / float(max(w, h)))
        target = (max(1, int(round(w * scale))), max(1, int(round(h * scale))))

        resized = img if target == (w, h) else img.resize(target, Image.Resampling.LANCZOS)

        fmt = output_format.lower()
        if fmt == "jpg":
            fmt = "jpeg"

        if fmt == "jpeg":
            if resized.mode in ("RGBA", "LA") or ("transparency" in getattr(resized, "info", {})):
                bg = Image.new("RGB", resized.size, (255, 255, 255))
                bg.paste(resized.convert("RGBA"), mask=resized.convert("RGBA").split()[-1])
                resized = bg
            else:
                resized = resized.convert("RGB")

        out = BytesIO()
        resized.save(out, format=fmt.upper())
        return out.getvalue()


def _decode_write_and_downscale(
    images: List[str],
    outputs: List[Path],
    *,
    force: bool,
    downscale_max_dim: Optional[int],
    downscale_suffix: str,
    output_format: str,
    expected_size: str,
    keep_versions: bool = False,
) -> None:
    for idx, image_b64 in enumerate(images):
        if idx >= len(outputs):
            break
        out_path = outputs[idx]
        # --keep-versions implies overwrite permission: the current file is
        # preserved as a version first, so replacing it is lossless.
        if out_path.exists() and not (force or keep_versions):
            _die(f"Output already exists: {out_path} (use --force to overwrite)")
        out_path.parent.mkdir(parents=True, exist_ok=True)
        history_path = out_path.parent / IMAGE_HISTORY_NAME

        if keep_versions and out_path.exists():
            # Rotate atomically (os.replace): the active path either holds the
            # old bytes or the new bytes, never a half-written mix.
            slot = _next_version_slot(out_path)
            archived = _version_file_path(out_path, slot)
            os.replace(out_path, archived)
            _append_history_record(
                history_path,
                {
                    "output": out_path.name,
                    "version": f"v{slot}",
                    "file": archived.name,
                    "bytes": archived.stat().st_size,
                    "timestamp": _utc_now_iso(),
                    "active": False,
                },
            )

        raw = base64.b64decode(image_b64)
        _validate_generated_image_bytes(raw, expected_size)
        if keep_versions:
            _write_bytes_atomic(out_path, raw)
        else:
            out_path.write_bytes(raw)
        print(f"Wrote {out_path}")

        if keep_versions:
            # The new active content is labeled with the slot it would occupy
            # when archived later, keeping version labels and .vN files in
            # lockstep across rotations and set-active switches.
            _append_history_record(
                history_path,
                {
                    "output": out_path.name,
                    "version": f"v{_next_version_slot(out_path)}",
                    "file": out_path.name,
                    "bytes": out_path.stat().st_size,
                    "timestamp": _utc_now_iso(),
                    "active": True,
                },
            )

        if downscale_max_dim is None:
            continue

        derived = _derive_downscale_path(out_path, downscale_suffix)
        if derived.exists() and not (force or keep_versions):
            _die(f"Output already exists: {derived} (use --force to overwrite)")
        derived.parent.mkdir(parents=True, exist_ok=True)
        resized = _downscale_image_bytes(raw, max_dim=downscale_max_dim, output_format=output_format)
        derived.write_bytes(resized)
        print(f"Wrote {derived}")


def _slugify(value: str) -> str:
    value = value.strip().lower()
    value = re.sub(r"[^a-z0-9]+", "-", value)
    value = re.sub(r"-{2,}", "-", value).strip("-")
    return value[:60] if value else "job"


def _normalize_job(job: Any, idx: int) -> Dict[str, Any]:
    if isinstance(job, str):
        prompt = job.strip()
        if not prompt:
            _die(f"Empty prompt at job {idx}")
        return {"prompt": prompt}
    if isinstance(job, dict):
        if "prompt" not in job or not str(job["prompt"]).strip():
            _die(f"Missing prompt for job {idx}")
        return job
    _die(f"Invalid job at index {idx}: expected string or object.")
    return {}  # unreachable


def _read_jobs_jsonl(path: str) -> List[Dict[str, Any]]:
    p = Path(path)
    if not p.exists():
        _die(f"Input file not found: {p}")
    jobs: List[Dict[str, Any]] = []
    for line_no, raw in enumerate(p.read_text(encoding="utf-8").splitlines(), start=1):
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        try:
            item: Any
            if line.startswith("{"):
                item = json.loads(line)
            else:
                item = line
            jobs.append(_normalize_job(item, idx=line_no))
        except json.JSONDecodeError as exc:
            _die(f"Invalid JSON on line {line_no}: {exc}")
    if not jobs:
        _die("No jobs found in input file.")
    if len(jobs) > MAX_BATCH_JOBS:
        _die(f"Too many jobs ({len(jobs)}). Max is {MAX_BATCH_JOBS}.")
    return jobs


def _merge_non_null(dst: Dict[str, Any], src: Dict[str, Any]) -> Dict[str, Any]:
    merged = dict(dst)
    for k, v in src.items():
        if v is not None:
            merged[k] = v
    return merged


def _job_output_paths(
    *,
    out_dir: Path,
    output_format: str,
    idx: int,
    prompt: str,
    n: int,
    explicit_out: Optional[str],
) -> List[Path]:
    out_dir.mkdir(parents=True, exist_ok=True)
    ext = "." + output_format

    if explicit_out:
        base = Path(explicit_out)
        if base.suffix == "":
            base = base.with_suffix(ext)
        elif base.suffix.lstrip(".").lower() != output_format:
            _warn(
                f"Job {idx}: output extension {base.suffix} does not match output-format {output_format}."
            )
        base = out_dir / base.name
    else:
        slug = _slugify(prompt[:80])
        base = out_dir / f"{idx:03d}-{slug}{ext}"

    if n == 1:
        return [base]
    return [
        base.with_name(f"{base.stem}-{i}{base.suffix}")
        for i in range(1, n + 1)
    ]


def _manifest_path(out_dir: Path) -> Path:
    return out_dir / BATCH_MANIFEST_NAME


def _utc_now_iso() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def _error_summary(exc: Exception) -> str:
    # Collapse whitespace so multi-line provider errors stay readable on one
    # manifest line; truncate to keep lines bounded.
    text = " ".join(str(exc).split())
    return text[:MANIFEST_ERROR_SUMMARY_MAX_CHARS]


def _load_manifest_success_jobs(manifest_path: Path) -> set:
    """Return job indexes that have a success record in the batch manifest.

    The manifest is the resume truth, mirroring geekai's per-slide image
    records: only a persisted "ok" line counts as done. A crash can leave a
    truncated trailing line, so malformed lines are skipped with a warning
    instead of aborting the resume.
    """
    done: set = set()
    if not manifest_path.exists():
        return done
    for line_no, raw in enumerate(manifest_path.read_text(encoding="utf-8").splitlines(), start=1):
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        try:
            record = json.loads(line)
        except json.JSONDecodeError as exc:
            _warn(f"Batch manifest line {line_no} is not valid JSON ({exc}); ignoring it.")
            continue
        if not isinstance(record, dict):
            _warn(f"Batch manifest line {line_no} is not a JSON object; ignoring it.")
            continue
        if record.get("status") != "ok":
            continue
        try:
            done.add(int(record["job"]))
        except (KeyError, TypeError, ValueError):
            _warn(f"Batch manifest line {line_no} has no usable job index; ignoring it.")
    return done


class _BatchManifestWriter:
    """Append-only JSONL manifest writer; one complete line per job outcome.

    Each record is serialized to a single string and appended with one write
    followed by flush, so a crash can at most truncate the final line — every
    fully written line stays parseable on resume. If a previous crash left a
    partial trailing line without its newline, a separator newline is written
    first so the new record does not get glued onto the broken line.
    """

    def __init__(self, path: Path) -> None:
        self._path = path
        self._lock = threading.Lock()

    def append(self, record: Dict[str, Any]) -> None:
        line = json.dumps(record, ensure_ascii=False)
        with self._lock:
            self._path.parent.mkdir(parents=True, exist_ok=True)
            needs_separator = False
            if self._path.exists() and self._path.stat().st_size > 0:
                with self._path.open("rb") as probe:
                    probe.seek(-1, os.SEEK_END)
                    needs_separator = probe.read(1) != b"\n"
            with self._path.open("a", encoding="utf-8") as fh:
                if needs_separator:
                    fh.write("\n")
                fh.write(line + "\n")
                fh.flush()


def _write_bytes_atomic(path: Path, data: bytes) -> None:
    """Write bytes via a sibling temp file + os.replace so a crash never
    leaves a half-written active file."""
    fd, tmp_name = tempfile.mkstemp(dir=str(path.parent), prefix=path.name + ".", suffix=".tmp")
    try:
        with os.fdopen(fd, "wb") as fh:
            fh.write(data)
        os.replace(tmp_name, path)
    except BaseException:
        try:
            os.unlink(tmp_name)
        except OSError:
            pass
        raise


def _version_file_path(output: Path, slot: int) -> Path:
    return output.with_name(f"{output.stem}.v{slot}{output.suffix}")


def _next_version_slot(output: Path) -> int:
    """First unclaimed version slot (v1, v2, ...) for this output."""
    slot = 1
    while _version_file_path(output, slot).exists():
        slot += 1
    return slot


def _append_history_record(history_path: Path, record: Dict[str, Any]) -> None:
    # Reuse the crash-safe append-only JSONL writer from the batch manifest.
    _BatchManifestWriter(history_path).append(record)


def set_active(history_file: Path, output_name: str, version: str) -> Path:
    """Re-activate a previously archived version of an output image.

    Copies (never moves — the version file itself stays) the recorded
    version file over the active output path via temp copy + os.replace, then
    appends an active:true line to the history. The history is append-only:
    for a given output the LAST active:true line is the activation truth and
    every earlier line is implicitly superseded (inactive), so rotation never
    rewrites history rows. Raises ValueError with a clear message when the
    history file, the version record, or the version file is missing.
    """
    if not history_file.exists():
        raise ValueError(f"image history file not found: {history_file}")
    records: List[Dict[str, Any]] = []
    for line_no, raw in enumerate(history_file.read_text(encoding="utf-8").splitlines(), start=1):
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        try:
            record = json.loads(line)
        except json.JSONDecodeError as exc:
            _warn(f"Image history line {line_no} is not valid JSON ({exc}); ignoring it.")
            continue
        if isinstance(record, dict):
            records.append(record)
    matches = [
        rec
        for rec in records
        if rec.get("output") == output_name and str(rec.get("version")) == version
    ]
    if not matches:
        raise ValueError(
            f"version {version} not found in {history_file} for output {output_name}"
        )
    file_name = str(matches[-1].get("file") or "")
    version_file = history_file.parent / file_name
    if not file_name or not version_file.exists():
        raise ValueError(f"version file for {version} is missing: {version_file}")
    active_path = history_file.parent / output_name
    fd, tmp_name = tempfile.mkstemp(
        dir=str(history_file.parent), prefix=active_path.name + ".", suffix=".tmp"
    )
    os.close(fd)
    try:
        shutil.copyfile(version_file, tmp_name)
        os.replace(tmp_name, active_path)
    except BaseException:
        try:
            os.unlink(tmp_name)
        except OSError:
            pass
        raise
    _append_history_record(
        history_file,
        {
            "output": output_name,
            "version": version,
            "file": active_path.name,
            "bytes": active_path.stat().st_size,
            "timestamp": _utc_now_iso(),
            "active": True,
        },
    )
    return active_path


def _job_outputs_complete(outputs: List[Path]) -> bool:
    """True when every declared output exists and is non-empty."""
    return all(p.exists() and p.stat().st_size > 0 for p in outputs)


def _success_record(job_index: int, outputs: List[Path], job: Dict[str, Any]) -> Dict[str, Any]:
    record: Dict[str, Any] = {
        "status": "ok",
        "job": job_index,
        # `output` names the primary output; for n>1 jobs `bytes` is the total
        # across all outputs written by this job (informational only — resume
        # completeness is re-checked against the files themselves).
        "output": outputs[0].name,
        "bytes": sum(p.stat().st_size for p in outputs),
        "timestamp": _utc_now_iso(),
    }
    page_type = job.get("page_type")
    if page_type:
        record["page_type"] = str(page_type)
    return record


async def _run_generate_batch(args: argparse.Namespace) -> int:
    jobs = _read_jobs_jsonl(args.input)
    out_dir = Path(args.out_dir)

    base_fields = _fields_from_args(args)
    base_payload = {
        "model": args.model,
        "n": args.n,
        "size": args.size,
        "quality": args.quality,
        "background": args.background,
        "output_format": args.output_format,
        "output_compression": args.output_compression,
        "moderation": args.moderation,
    }

    if args.dry_run:
        for i, job in enumerate(jobs, start=1):
            prompt = str(job["prompt"]).strip()
            fields = _merge_non_null(base_fields, job.get("fields", {}))
            # Allow flat job keys as well (use_case, scene, etc.)
            fields = _merge_non_null(fields, {k: job.get(k) for k in base_fields.keys()})
            augmented = _augment_prompt_fields(args.augment, prompt, fields)

            job_payload = dict(base_payload)
            job_payload["prompt"] = augmented
            job_payload = _merge_non_null(job_payload, {k: job.get(k) for k in base_payload.keys()})
            job_payload = {k: v for k, v in job_payload.items() if v is not None}

            _validate_generate_payload(job_payload)
            effective_output_format = _normalize_output_format(job_payload.get("output_format"))
            _validate_transparency(job_payload.get("background"), effective_output_format)
            job_payload["output_format"] = effective_output_format

            n = int(job_payload.get("n", 1))
            outputs = _job_output_paths(
                out_dir=out_dir,
                output_format=effective_output_format,
                idx=i,
                prompt=prompt,
                n=n,
                explicit_out=job.get("out"),
            )
            downscaled = None
            if args.downscale_max_dim is not None:
                downscaled = [
                    str(_derive_downscale_path(p, args.downscale_suffix)) for p in outputs
                ]
            _print_request(
                {
                    "endpoint": _preview_endpoint("generate"),
                    "job": i,
                    "outputs": [str(p) for p in outputs],
                    "outputs_downscaled": downscaled,
                    **{
                        **job_payload,
                        "model": _preview_model(str(job_payload["model"]), "generate"),
                    },
                }
            )
        return 0

    provider = create_image_provider(api_key=os.getenv("OPENAI_API_KEY"), base_url=_api_base_url())
    sem = asyncio.Semaphore(args.concurrency)

    # Per-page persistence: every job outcome is appended to the manifest as
    # soon as it is known, so an interrupted batch leaves an exact record of
    # which pages are done. --resume then trusts only persisted "ok" records
    # whose outputs are still present and non-empty (the file check guards
    # against outputs deleted or truncated after the manifest was written).
    resume = bool(getattr(args, "resume", False))
    manifest = _BatchManifestWriter(_manifest_path(out_dir))
    done_jobs = _load_manifest_success_jobs(_manifest_path(out_dir)) if resume else set()

    any_failed = False
    stats = {"resumed": 0, "skipped": 0, "generated": 0, "failed": 0}

    async def run_job(i: int, job: Dict[str, Any]) -> Tuple[int, Optional[str]]:
        nonlocal any_failed
        prompt = str(job["prompt"]).strip()
        job_label = f"[job {i}/{len(jobs)}]"

        fields = _merge_non_null(base_fields, job.get("fields", {}))
        fields = _merge_non_null(fields, {k: job.get(k) for k in base_fields.keys()})
        augmented = _augment_prompt_fields(args.augment, prompt, fields)

        payload = dict(base_payload)
        payload["prompt"] = augmented
        payload = _merge_non_null(payload, {k: job.get(k) for k in base_payload.keys()})
        payload = {k: v for k, v in payload.items() if v is not None}

        n = int(payload.get("n", 1))
        _validate_generate_payload(payload)
        effective_output_format = _normalize_output_format(payload.get("output_format"))
        _validate_transparency(payload.get("background"), effective_output_format)
        payload["output_format"] = effective_output_format
        outputs = _job_output_paths(
            out_dir=out_dir,
            output_format=effective_output_format,
            idx=i,
            prompt=prompt,
            n=n,
            explicit_out=job.get("out"),
        )
        if resume and i in done_jobs and _job_outputs_complete(outputs):
            stats["resumed"] += 1
            stats["skipped"] += 1
            print(
                f"{job_label} output already complete per {BATCH_MANIFEST_NAME}; skipping",
                file=sys.stderr,
            )
            return i, None
        try:
            async with sem:
                print(f"{job_label} starting", file=sys.stderr)
                # Global QPS throttle for the batch path too. The 429 backoff
                # itself stays inside provider.generate_batch, which already
                # retries transient errors (including 429) on a 2/4/8s ladder
                # honoring Retry-After; stacking another retry loop here would
                # multiply the attempt count per job.
                throttle_s = _rate_limiter().reserve()
                if throttle_s > 0:
                    await asyncio.sleep(throttle_s)
                started = time.time()
                images = await provider.generate_batch(
                    payload,
                    attempts=args.max_attempts,
                    job_label=job_label,
                )
                elapsed = time.time() - started
                print(f"{job_label} completed in {elapsed:.1f}s", file=sys.stderr)
            _decode_write_and_downscale(
                images,
                outputs,
                # --resume owns the missing pages, so overwriting a stale,
                # orphaned, or truncated target when regenerating a job is
                # intentional even without an explicit --force.
                force=args.force or resume,
                downscale_max_dim=args.downscale_max_dim,
                downscale_suffix=args.downscale_suffix,
                output_format=effective_output_format,
                expected_size=str(payload["size"]),
                keep_versions=getattr(args, "keep_versions", False),
            )
            manifest.append(_success_record(i, outputs, job))
            stats["generated"] += 1
            return i, None
        except Exception as exc:
            any_failed = True
            stats["failed"] += 1
            # Failure lines are audit-only: resume keys strictly on "ok"
            # records, so recording errors can never cause a page to be
            # skipped (mirrors geekai persisting err_msg on failed tasks).
            manifest.append(
                {
                    "status": "error",
                    "job": i,
                    "error": _error_summary(exc),
                    "timestamp": _utc_now_iso(),
                }
            )
            print(f"{job_label} failed: {exc}", file=sys.stderr)
            if args.fail_fast:
                raise
            return i, str(exc)

    tasks = [asyncio.create_task(run_job(i, job)) for i, job in enumerate(jobs, start=1)]

    try:
        await asyncio.gather(*tasks)
    except Exception:
        for t in tasks:
            if not t.done():
                t.cancel()
        raise

    # `resumed` counts jobs reused from a prior run via --resume; `skipped` is
    # the general did-not-call-the-provider bucket and currently equals it.
    print(
        f"Batch summary: jobs={len(jobs)} resumed={stats['resumed']} "
        f"skipped={stats['skipped']} generated={stats['generated']} "
        f"failed={stats['failed']}",
        file=sys.stderr,
    )
    return 1 if any_failed else 0


def _generate_batch(args: argparse.Namespace) -> None:
    exit_code = asyncio.run(_run_generate_batch(args))
    if exit_code:
        raise SystemExit(exit_code)


def _generate(args: argparse.Namespace) -> None:
    prompt = _read_prompt(args.prompt, args.prompt_file)
    prompt = _augment_prompt(args, prompt)

    payload = {
        "model": args.model,
        "prompt": prompt,
        "n": args.n,
        "size": args.size,
        "quality": args.quality,
        "background": args.background,
        "output_format": args.output_format,
        "output_compression": args.output_compression,
        "moderation": args.moderation,
    }
    payload = {k: v for k, v in payload.items() if v is not None}

    output_format = _normalize_output_format(args.output_format)
    _validate_transparency(args.background, output_format)
    payload["output_format"] = output_format
    output_paths = _build_output_paths(args.out, output_format, args.n, args.out_dir)
    downscaled = None
    if args.downscale_max_dim is not None:
        downscaled = [str(_derive_downscale_path(p, args.downscale_suffix)) for p in output_paths]

    if args.dry_run:
        _print_request(
            {
                "endpoint": _preview_endpoint("generate"),
                "outputs": [str(p) for p in output_paths],
                "outputs_downscaled": downscaled,
                **{
                    **payload,
                    "model": _preview_model(str(payload["model"]), "generate"),
                },
            }
        )
        return

    print(
        "Calling Image API (generation). This can take up to a couple of minutes.",
        file=sys.stderr,
    )
    started = time.time()
    provider = create_image_provider(api_key=os.getenv("OPENAI_API_KEY"), base_url=_api_base_url())
    images = _call_rate_limited(lambda: provider.generate(payload))
    elapsed = time.time() - started
    print(f"Generation completed in {elapsed:.1f}s.", file=sys.stderr)

    _decode_write_and_downscale(
        images,
        output_paths,
        force=args.force,
        downscale_max_dim=args.downscale_max_dim,
        downscale_suffix=args.downscale_suffix,
        output_format=output_format,
        expected_size=args.size,
        keep_versions=getattr(args, "keep_versions", False),
    )


def _edit(args: argparse.Namespace) -> None:
    prompt = _read_prompt(args.prompt, args.prompt_file)
    prompt = _augment_prompt(args, prompt)

    local_images = [raw for raw in args.image if not _is_remote_reference(raw)]
    remote_images = [raw for raw in args.image if _is_remote_reference(raw)]
    image_paths = _check_image_paths(local_images)
    # Local files pass through as Paths directly (both bundled providers
    # consume file Paths natively). http(s)/data: references are normalized
    # through prepare_reference_inputs and staged as temp files, because the
    # provider edit() contract requires local files.
    ref_tmpdir: Optional[tempfile.TemporaryDirectory] = None
    if remote_images:
        ref_tmpdir = tempfile.TemporaryDirectory(prefix="codex-ppt-refs-")
        try:
            staged = prepare_reference_inputs(remote_images)
        except ValueError as exc:
            ref_tmpdir.cleanup()
            _die(str(exc))
        for prepared in staged:
            image_paths.append(_materialize_reference(prepared, Path(ref_tmpdir.name)))
    try:
        _edit_with_images(args, prompt, image_paths)
    finally:
        if ref_tmpdir is not None:
            ref_tmpdir.cleanup()


def _edit_with_images(
    args: argparse.Namespace,
    prompt: str,
    image_paths: List[Path],
) -> None:
    mask_path = Path(args.mask) if args.mask else None
    if mask_path:
        if not mask_path.exists():
            _die(f"Mask file not found: {mask_path}")
        if mask_path.suffix.lower() != ".png":
            _warn(f"Mask should be a PNG with an alpha channel: {mask_path}")
        if mask_path.stat().st_size > MAX_IMAGE_BYTES:
            _warn(f"Mask exceeds 50MB limit: {mask_path}")

    payload = {
        "model": args.model,
        "prompt": prompt,
        "n": args.n,
        "size": args.size,
        "quality": args.quality,
        "background": args.background,
        "output_format": args.output_format,
        "output_compression": args.output_compression,
        "input_fidelity": args.input_fidelity,
        "moderation": args.moderation,
    }
    payload = {k: v for k, v in payload.items() if v is not None}

    output_format = _normalize_output_format(args.output_format)
    _validate_transparency(args.background, output_format)
    payload["output_format"] = output_format
    _validate_input_fidelity(args.input_fidelity)
    output_paths = _build_output_paths(args.out, output_format, args.n, args.out_dir)
    downscaled = None
    if args.downscale_max_dim is not None:
        downscaled = [str(_derive_downscale_path(p, args.downscale_suffix)) for p in output_paths]

    if args.dry_run:
        payload_preview = dict(payload)
        payload_preview["image"] = [str(p) for p in image_paths]
        if mask_path:
            payload_preview["mask"] = str(mask_path)
        _print_request(
            {
                "endpoint": _preview_endpoint("edit"),
                "outputs": [str(p) for p in output_paths],
                "outputs_downscaled": downscaled,
                **{
                    **payload_preview,
                    "model": _preview_model(str(payload_preview["model"]), "edit"),
                },
            }
        )
        return

    print(
        f"Calling Image API (edit) with {len(image_paths)} image(s).",
        file=sys.stderr,
    )
    started = time.time()
    provider = create_image_provider(api_key=os.getenv("OPENAI_API_KEY"), base_url=_api_base_url())
    images = _call_rate_limited(lambda: provider.edit(payload, image_paths, mask_path))

    elapsed = time.time() - started
    print(f"Edit completed in {elapsed:.1f}s.", file=sys.stderr)
    _decode_write_and_downscale(
        images,
        output_paths,
        force=args.force,
        downscale_max_dim=args.downscale_max_dim,
        downscale_suffix=args.downscale_suffix,
        output_format=output_format,
        expected_size=str(payload["size"]),
        keep_versions=getattr(args, "keep_versions", False),
    )


def _set_active_cli(args: argparse.Namespace) -> None:
    out_path = Path(args.out)
    history_file = out_path.parent / IMAGE_HISTORY_NAME
    try:
        active_path = set_active(history_file, out_path.name, args.version)
    except ValueError as exc:
        _die(str(exc))
    print(f"Activated {args.version} at {active_path}")


def _add_shared_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--model", default=_default_model())
    parser.add_argument("--prompt")
    parser.add_argument("--prompt-file")
    parser.add_argument("--n", type=int, default=1)
    parser.add_argument("--size", default=DEFAULT_SIZE)
    parser.add_argument("--quality", default=DEFAULT_QUALITY)
    parser.add_argument("--background")
    parser.add_argument("--output-format")
    parser.add_argument("--output-compression", type=int)
    parser.add_argument("--moderation")
    parser.add_argument("--out", default=DEFAULT_OUTPUT_PATH)
    parser.add_argument("--out-dir")
    parser.add_argument("--force", action="store_true")
    parser.add_argument(
        "--keep-versions",
        action="store_true",
        help=(
            "When an output file already exists, rotate it to <stem>.vN<ext> "
            f"(atomic rename) and log every version to {IMAGE_HISTORY_NAME} "
            "instead of overwriting; implies overwrite permission"
        ),
    )
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--augment", dest="augment", action="store_true")
    parser.add_argument("--no-augment", dest="augment", action="store_false")
    parser.set_defaults(augment=True)

    # Prompt augmentation hints
    parser.add_argument("--use-case")
    parser.add_argument("--scene")
    parser.add_argument("--subject")
    parser.add_argument("--style")
    parser.add_argument("--composition")
    parser.add_argument("--lighting")
    parser.add_argument("--palette")
    parser.add_argument("--materials")
    parser.add_argument("--text")
    parser.add_argument("--constraints")
    parser.add_argument("--negative")

    # Post-processing (optional): generate an additional downscaled copy for fast web loading.
    parser.add_argument("--downscale-max-dim", type=int)
    parser.add_argument("--downscale-suffix", default=DEFAULT_DOWNSCALE_SUFFIX)


def main() -> int:
    _load_runtime_env()
    parser = argparse.ArgumentParser(
        description="Fallback CLI for explicit image generation or editing via GPT Image models"
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    gen_parser = subparsers.add_parser("generate", help="Create a new image")
    _add_shared_args(gen_parser)
    gen_parser.set_defaults(func=_generate)

    batch_parser = subparsers.add_parser(
        "generate-batch",
        help="Generate multiple prompts concurrently (JSONL input)",
    )
    _add_shared_args(batch_parser)
    batch_parser.add_argument("--input", required=True, help="Path to JSONL file (one job per line)")
    batch_parser.add_argument("--concurrency", type=int, default=DEFAULT_CONCURRENCY)
    batch_parser.add_argument("--max-attempts", type=int, default=3)
    batch_parser.add_argument("--fail-fast", action="store_true")
    batch_parser.add_argument(
        "--resume",
        action="store_true",
        help=(
            "Skip jobs whose outputs already exist and are recorded as complete "
            f"in {BATCH_MANIFEST_NAME}; only missing pages are generated"
        ),
    )
    batch_parser.set_defaults(func=_generate_batch)

    edit_parser = subparsers.add_parser("edit", help="Edit an existing image")
    _add_shared_args(edit_parser)
    edit_parser.add_argument("--image", action="append", required=True)
    edit_parser.add_argument("--mask")
    edit_parser.add_argument("--input-fidelity")
    edit_parser.set_defaults(func=_edit)

    activate_parser = subparsers.add_parser(
        "set-active",
        help="Switch an output image back to a recorded version (requires --keep-versions history)",
    )
    activate_parser.add_argument(
        "--out",
        required=True,
        help="Path of the active output image (history is read from its directory)",
    )
    activate_parser.add_argument(
        "--version",
        required=True,
        help="Version label to activate, for example v1",
    )
    activate_parser.set_defaults(func=_set_active_cli)

    args = parser.parse_args()
    if args.command == "set-active":
        args.func(args)
        return 0
    if args.n < 1 or args.n > 10:
        _die("--n must be between 1 and 10")
    if getattr(args, "concurrency", 1) < 1 or getattr(args, "concurrency", 1) > 25:
        _die("--concurrency must be between 1 and 25")
    if getattr(args, "max_attempts", 3) < 1 or getattr(args, "max_attempts", 3) > 10:
        _die("--max-attempts must be between 1 and 10")
    if args.output_compression is not None and not (0 <= args.output_compression <= 100):
        _die("--output-compression must be between 0 and 100")
    if args.command == "generate-batch" and not args.out_dir:
        _die("generate-batch requires --out-dir")
    if getattr(args, "downscale_max_dim", None) is not None and args.downscale_max_dim < 1:
        _die("--downscale-max-dim must be >= 1")

    _validate_model(args.model)
    _validate_size(args.size, args.model)
    _validate_quality(args.quality)
    _validate_background(args.background)
    _validate_model_specific_options(
        model=args.model,
        background=args.background,
        input_fidelity=getattr(args, "input_fidelity", None),
    )
    _ensure_api_key(args.dry_run)

    args.func(args)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
