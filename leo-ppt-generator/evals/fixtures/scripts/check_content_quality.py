#!/usr/bin/env python3
"""跨行业内容质量测评 · L0 机检编排器（方案 005 §3.3/§3.5）。

评测侧 thin-glue：复用技能自带检查器（check_number_ledger / check_master_contract
/ check_deck_prose / check_content_facts / check_deck_geometry --capacity），
只补输入转换（容量投影）、覆盖缺口（同页 ledger 对账、页数一致、密度档、备注分栏、
P 码存在性）、错误分类与 machine-report 聚合。不复制领域规则。

用法（在 leo-ppt-generator/ 目录内执行）：
  python3 evals/fixtures/scripts/check_content_quality.py --unit u01 \
      --unit-dir <case 工作区（含 project/ 子树）> [--out machine-report.json]

退出码：0 = 适用项全部通过（允许 warning / not_applicable / candidates_for_judge）
        1 = 存在 quality_fail 或 error
        2 = 用法/输入错误（unit 目录不存在、protocol 不可读等）
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import re
import struct
import subprocess
import sys
import tempfile
import xml.etree.ElementTree as ET
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent          # evals/fixtures/scripts
SKILL_ROOT = SCRIPT_DIR.parents[2]                    # leo-ppt-generator/
FIXTURE_ROOT = SCRIPT_DIR.parent / "content-quality-20industries"
SCRIPTS_DIR = SKILL_ROOT / "scripts"

# 复用 check_content_facts 的数字归一化（同一 NUM_TOKEN_RE / 万亿换算 / 年份豁免）
sys.path.insert(0, str(SCRIPTS_DIR))
import check_content_facts as _facts  # noqa: E402

PROTOCOL_PATH = FIXTURE_ROOT / "protocol.json"
RENDER_BACKENDS = {"render:html", "render:mermaid", "render:echarts"}

PAGE_RE = re.compile(r"^##\s+(S(\d+)|附)[^\n]*$", re.M)
ROLE_RE = re.compile(r"(?:页面角色|角色|role)[：:]\s*([^\s,，;；。]+)", re.I)
FUNCTIONAL_ROLE_WORDS = ("开场", "封面", "目录", "章节", "隔断", "过渡", "收束", "结尾", "致谢", "问答")
LEDGER_PAGE_RE = re.compile(r"^##\s+S(\d+)")
PCODE_RE = re.compile(r"\bP(\d{1,2})\b")
# 占位残留：作者 TODO 形态。「待补数据/待补工作」是 U15 等单元的领域用语，
# 只有括注形态（（待补））才算占位符
PLACEHOLDER_RE = re.compile(r"TODO|TBD|待补充|待填写|占位符|XXX|[（(]待补[）)]")
MAPPING_RE = re.compile(r"(?:要点\s*)?(\d+)\s*→")
LEDGER_TIER_MISMATCH_RE = re.compile(r"用户确认")


def sha256_of(path: Path) -> str:
    h = hashlib.sha256()
    h.update(path.read_bytes())
    return h.hexdigest()[:16]


def sha256_full(path: Path) -> str:
    h = hashlib.sha256()
    h.update(path.read_bytes())
    return h.hexdigest()


def _artifact_format_and_dimensions(path: Path) -> tuple[str, tuple[int, int] | None]:
    """Validate the on-disk artifact instead of trusting its suffix or receipt."""

    raw = path.read_bytes()
    suffix = path.suffix.lower()
    if suffix == ".png":
        if len(raw) < 24 or raw[:8] != b"\x89PNG\r\n\x1a\n" or raw[12:16] != b"IHDR":
            raise ValueError("不是合法 PNG（缺少 PNG/IHDR 签名）")
        width, height = struct.unpack(">II", raw[16:24])
        if width < 1 or height < 1:
            raise ValueError("PNG 尺寸非法")
        return "png", (width, height)
    if suffix == ".svg":
        try:
            root = ET.fromstring(raw)
        except (UnicodeError, ET.ParseError) as exc:
            raise ValueError(f"不是合法 SVG XML: {exc}") from exc
        if root.tag.rsplit("}", 1)[-1].lower() != "svg":
            raise ValueError("SVG 根元素不是 svg")
        view_box = root.attrib.get("viewBox", "").replace(",", " ").split()
        if len(view_box) == 4:
            try:
                width, height = float(view_box[2]), float(view_box[3])
            except ValueError as exc:
                raise ValueError("SVG viewBox 尺寸非法") from exc
            if width > 0 and height > 0:
                return "svg", (round(width), round(height))
        dimensions = []
        for key in ("width", "height"):
            match = re.fullmatch(r"\s*(\d+(?:\.\d+)?)\s*(?:px)?\s*", root.attrib.get(key, ""))
            if not match:
                raise ValueError("SVG 缺少可验证的 width/height 或 viewBox")
            dimensions.append(round(float(match.group(1))))
        if all(value > 0 for value in dimensions):
            return "svg", (dimensions[0], dimensions[1])
        raise ValueError("SVG 尺寸非法")
    if suffix in {".html", ".htm"}:
        try:
            text = raw.decode("utf-8")
        except UnicodeDecodeError as exc:
            raise ValueError(f"HTML 不是 UTF-8: {exc}") from exc
        lowered = text.lower()
        if not re.search(r"<\s*(?:!doctype\s+html|html\b)", lowered) or not re.search(
            r"<\s*(?:head|body)\b", lowered
        ):
            raise ValueError("HTML 缺少 doctype/html 与 head/body 结构")
        # HTML has no intrinsic raster dimensions; the receipt viewport is
        # checked by the caller as width/height > 0.
        return "html", None
    raise ValueError(f"不支持的产物扩展名: {suffix or '<none>'}")


def load_protocol() -> dict:
    if not PROTOCOL_PATH.exists():
        print(f"ERROR: protocol 不可读: {PROTOCOL_PATH}", file=sys.stderr)
        raise SystemExit(2)
    return json.loads(PROTOCOL_PATH.read_text(encoding="utf-8"))


def find_unit(protocol: dict, unit_id: str) -> dict:
    for u in protocol["units"]:
        if u["id"] == unit_id:
            return u
    print(f"ERROR: 未知单元 {unit_id}", file=sys.stderr)
    raise SystemExit(2)


# --------------------------------------------------------------------------- #
# 产物发现
# --------------------------------------------------------------------------- #

def discover_artifacts(unit_dir: Path) -> dict:
    """在 ``unit_dir/project`` 内发现冻结产物，不读取工作区其他区域。"""
    project_root = unit_dir / "project"
    if not project_root.is_dir():
        return {"outline_versions": [], "master_versions": [],
                "dispatch_records": [], "style_records": [], "render_outputs": []}

    def in_project(path: Path) -> bool:
        try:
            path.resolve(strict=False).relative_to(project_root.resolve())
            return True
        except ValueError:
            return False

    def scoped(paths, **kwargs):
        return sorted((p for p in paths if in_project(p)), **kwargs)

    found = {
        "outline_versions": scoped(project_root.rglob("outline-v*.md")),
        "master_versions": scoped(project_root.rglob("deck-master-v*.md")),
        "dispatch_records": scoped(
            (p for p in project_root.rglob("*.json") if _looks_like_dispatch(p)),
            key=lambda p: ("draft" in p.name, p.name)),  # 非 draft 优先、字母序
        "style_records": [p for p in project_root.rglob("*")
                          if p.is_file()
                          and in_project(p)
                          and ("style-selection" in p.name.lower()
                               or "selection" in p.name.lower())
                          and p.suffix.lower() in (".md", ".json", ".txt")],
        "render_outputs": [p for p in project_root.rglob("*")
                           if p.is_file() and in_project(p)
                           and "render" in p.name.lower()
                           and p.suffix.lower() in (".md", ".json", ".txt")],
    }
    return found


def find_scope_violations(unit_dir: Path, ignored: set[Path] | None = None) -> list[str]:
    """列出 project 外的所有文件及 project 内越界 symlink。

    评测 workspace 的允许写入根只有 ``project/``；使用文件名启发式会让
    ``notes.txt``、无后缀或改名后的工件绕过范围门，因此这里按规范化路径
    做完整 containment 检查。
    """
    project_root = unit_dir / "project"
    project_abs = project_root.resolve(strict=False)
    ignored = {p.resolve(strict=False) for p in (ignored or set())}
    violations: list[str] = []
    for path in unit_dir.rglob("*"):
        if not path.is_file():
            continue
        resolved = path.resolve(strict=False)
        if resolved in ignored:
            continue
        try:
            path.absolute().relative_to(project_root.absolute())
            lexical_in_project = True
        except ValueError:
            lexical_in_project = False
        if not lexical_in_project:
            violations.append(str(path.relative_to(unit_dir)))
            continue
        try:
            resolved.relative_to(project_abs)
        except ValueError:
            violations.append(str(path.relative_to(unit_dir)))
    return sorted(set(violations))


def _looks_like_dispatch(path: Path) -> bool:
    """版式调度记录启发式：JSON 且含 layout/P 码逐页映射。"""
    try:
        text = path.read_text(encoding="utf-8", errors="strict")
        data = json.loads(text)
    except (OSError, UnicodeError, json.JSONDecodeError):
        return False
    if isinstance(data, dict) and isinstance(data.get("slides"), list):
        return True
    return False


def latest_version(paths: list[Path], stem_prefix: str) -> Path | None:
    def version_no(p: Path) -> int:
        m = re.search(r"-v(\d+)", p.stem)
        return int(m.group(1)) if m else -1
    candidates = [p for p in paths if p.stem.startswith(stem_prefix)]
    return max(candidates, key=version_no) if candidates else None


# --------------------------------------------------------------------------- #
# 检查器包装（保留退出码与明细，按真实语义分类）
# --------------------------------------------------------------------------- #

def run_checker(label: str, cmd: list[str]) -> dict:
    proc = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
    return {
        "criterion_id": label,
        "command": " ".join(cmd),
        "exit_code": proc.returncode,
        "stdout_tail": proc.stdout[-2000:],
        "stderr_tail": proc.stderr[-2000:],
    }


def split_master_pages(text: str) -> list[tuple[str, str]]:
    matches = list(PAGE_RE.finditer(text))
    pages = []
    for i, m in enumerate(matches):
        end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        pages.append((m.group(0).strip(), text[m.start():end]))
    return pages


def page_number(header: str) -> int | None:
    m = LEDGER_PAGE_RE.match(header)
    return int(m.group(1)) if m else None


def parse_ledger_rows(text: str) -> list[dict]:
    rows, err = _import_ledger().parse_ledger_rows(text)
    if err:
        return []
    return rows


_ledger_mod = None


def _import_ledger():
    global _ledger_mod
    if _ledger_mod is None:
        spec = importlib.util.spec_from_file_location(
            "check_number_ledger", SCRIPTS_DIR / "check_number_ledger.py")
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        _ledger_mod = mod
    return _ledger_mod


def page_is_functional(body: str) -> bool:
    for m in ROLE_RE.finditer(body):
        if any(w in m.group(1) for w in FUNCTIONAL_ROLE_WORDS):
            return True
    return False


POINT_LINE_RE = re.compile(r"^(?:[-•]|\d+[.、])\s+(.+)$", re.M)  # 缩进 0 要点行：- / • / 1. / 1、（视觉行子弹为缩进注释）
POINT_LABEL_RE = re.compile(r"^要点\s*\d+\s*[：:]\s*")
_NON_POINT = ("标题", "备注", "视觉行", "argument_role", "数字登记表", "页面角色",
              "负面词条", "风格约束", "约束摘抄", "固定件")  # 末四类为渲染护栏元数据行
TITLE_RE = re.compile(r"[-•]\s*标题[：:]\s*(.+)")

# 非指标性数字噪声：日期/期间、版式 P 码、槽位字数注记、部件/测点标识符
# （TP-07、F-1 等编号是 ID 不是数值；登记表期间列承载日期）
DATE_RE = re.compile(r"\d{4}[-/.]\d{1,2}(?:[-/.]\d{1,2})?")
PCODE_TOKEN_RE = re.compile(r"\bP\d{1,2}\b")
SLOT_CHARS_RE = re.compile(r"≤?\d+(?:\.\d+)?\s*字")
SENSOR_ID_RE = re.compile(r"\b[A-Z]{1,4}-\d{1,3}\b")
CANVAS_RE = re.compile(r"\b\d{3,4}\s*[×x]\s*\d{3,4}\b")


def strip_non_metric(line: str) -> str:
    line = DATE_RE.sub(" ", line)
    line = PCODE_TOKEN_RE.sub(" ", line)
    line = re.sub(r"\bS\d{1,2}\b", " ", line)  # 页码引用（与 S10 一致）
    line = SLOT_CHARS_RE.sub(" ", line)
    line = SENSOR_ID_RE.sub(" ", line)
    line = CANVAS_RE.sub(" ", line)
    return re.sub(r"注\s*\d+", " ", line)  # 「材料红线注 2」类引用标号非数据


def page_bullets(body: str) -> list[str]:
    out = []
    for m in POINT_LINE_RE.finditer(body):
        raw = m.group(1)
        if raw.strip("—-– ") == "":  # 页分隔符 --- 不是要点
            continue
        if any(k in raw for k in _NON_POINT):
            continue
        out.append(POINT_LABEL_RE.sub("", raw))
    return out


def strip_machine_marks(text: str) -> str:
    """去机器标签（【…】/（…）/level 标记）与空白后的正文。"""
    text = re.sub(r"[【（(]\s*(?:用户确认|引用|估算|示意)(?:\s*[|｜][^】）)]*)?\s*[】）)]", "", text)
    text = re.sub(r"\[\s*src\s*[：:][^\]]*\]", "", text)
    return re.sub(r"\s+", "", text)


# --------------------------------------------------------------------------- #
# 评测侧补测项
# --------------------------------------------------------------------------- #

def outline_page_count(outline_text: str) -> int:
    """大纲页数：支持三种真实格式——分页表（| N |…）、S 码页头/列表项
    （## S1 / - S1 …）、「第 N 页」标题（### 第 1 页 · …）。取最大计数。"""
    counts = [
        len(re.findall(r"^\|\s*\d+\s*\|", outline_text, re.M)),
        len(re.findall(r"^(?:##\s+|- )S\d+", outline_text, re.M)),
        len(re.findall(r"^###?\s*第\s*\d+\s*页", outline_text, re.M)),
    ]
    return max(counts) if counts else 0


def check_page_counts(outline: str, master: str, expected_pages: int) -> dict:
    n_out = outline_page_count(outline)
    n_mas = len(split_master_pages(master))
    detail = f"outline={n_out} master={n_mas} brief={expected_pages}"
    ok = n_out == n_mas == expected_pages and n_out > 0
    return {"criterion_id": "A1.2-pages", "status": "pass" if ok else "fail",
            "detail": detail}


def check_ledger_coverage(master_text: str) -> dict:
    """A2.2 补测：标题+要点数字归一化后须有同页 ledger 行（年份豁免；估算/示意
    级数字同样须登记——登记表以证据等级区分来源，覆盖不因 tier 豁免）。
    登记表键 = 数值列 ⊕ 单位列；正文行先剥离日期/期间、P 码、槽位字数注记。"""
    rows_by_page: dict[int, set] = {}
    for row in parse_ledger_rows(master_text):
        cell = str(row.get("页", "")).strip()
        page_nos = []
        for part in re.split(r"[,，、/]", cell):
            m = re.match(r"S?(\d+)$", part.strip())
            if m:
                page_nos.append(int(m.group(1)))
        if not page_nos:
            continue
        raw_val = str(row.get("数值", "")).strip()
        if not raw_val:
            continue
        unit = str(row.get("单位", "")).strip()
        if unit == "%" and "%" not in raw_val:
            # 数值列为斜杠组合（如 40/35/15/10）时按 % 逐数拼装
            val = re.sub(r"(\d+(?:\.\d+)?)", r"\1%", raw_val)
        elif "/" in raw_val and unit:
            # 斜杠清单（如 28/15/9 亿）逐数拼单位，避免只有末数带上量级
            val = re.sub(r"(\d+(?:\.\d+)?)", rf"\1 {unit}", raw_val)
        else:
            val = (raw_val + " " + unit).strip()
        for _, key in _facts.extract_number_keys(val):
            for pg in page_nos:
                rows_by_page.setdefault(pg, set()).add(key)
    misses = []
    for header, body in split_master_pages(master_text):
        pg = page_number(header)
        if pg is None:
            continue
        title = TITLE_RE.search(body)
        lines = ([title.group(1)] if title else []) + page_bullets(body)
        for line in lines:
            for display, key in _facts.extract_number_keys(strip_non_metric(line)):
                if key not in rows_by_page.get(pg, set()):
                    misses.append(f"S{pg}『{display}』未登记同页")
    status = "fail" if misses else "pass"
    return {"criterion_id": "A2.2-coverage", "status": status,
            "detail": "; ".join(misses[:10]) or "标题/要点数字均有同页登记行",
            "miss_count": len(misses)}


def check_density(master_text: str) -> dict:
    """A3.2 补测：功能页豁免；台账页 ≤6 条、论点页 ≤3 条（产品禅档位硬规则）；
    每条 ≤2 显式行。论点页正文合计 >80 字为如实报告的 warning（M0 校准：产品
    合同 deck-master.md 为行数制而非字数制，80 字硬线系统性误伤合规证据页——
    原冻结值保留于 protocol.json m0_calibrations，不降为通过）。"""
    problems, char_warnings = [], []
    for header, body in split_master_pages(master_text):
        if page_is_functional(body):
            continue
        bullets = page_bullets(body)
        is_ledger_page = bool(re.search(r"台账|表格|数据表|对照表", body))
        limit = 6 if is_ledger_page else 3
        if len(bullets) > limit:
            problems.append(f"{header}: 要点 {len(bullets)} 条超 {limit} 条档位")
        if not is_ledger_page:
            total = sum(len(strip_machine_marks(b)) for b in bullets)
            if total > 80:
                char_warnings.append(f"{header}: {total} 字")
        for i, b in enumerate(bullets, 1):
            explicit_lines = b.count("\n") + 1  # 母版显式分行（bullet 内换行）
            if explicit_lines > 2:
                problems.append(f"{header} 要点{i}: 显式 {explicit_lines} 行 > 2")
    return {"criterion_id": "A3.2-density",
            "status": "fail" if problems else "pass",
            "detail": "; ".join(problems[:10]) or "档位与分行全部合规"
                      + (f"；论点页字数超 80 报告项: {char_warnings}"
                         if char_warnings else ""),
            "problem_count": len(problems),
            "char_over_80": char_warnings}


def check_notes_columns(master_text: str) -> dict:
    """A3.4 补测：备注分栏（speaker_script/engineering）+ 无占位残留。"""
    problems, placeholders = [], []
    for header, body in split_master_pages(master_text):
        if "speaker_script" not in body:
            problems.append(f"{header}: 缺 speaker_script 分栏")
        if "engineering" not in body:
            problems.append(f"{header}: 缺 engineering 分栏")
        for m in PLACEHOLDER_RE.finditer(body):
            placeholders.append(f"{header}: 占位残留『{m.group(0)}』")
    status = "fail" if (problems or placeholders) else "pass"
    return {"criterion_id": "A3.4-notes", "status": status,
            "detail": "; ".join((problems + placeholders)[:10]) or "备注分栏完整、无占位残留"}


def check_pcode_and_project(master_text: str, dispatch_paths: list[Path],
                            layout_bank: set[str]) -> tuple[dict, dict, list[dict]]:
    """A5.2 P 码存在性 + A5.3 容量投影原料。

    版式来源优先级：母版视觉行 P 码（confirmed 内容真值）> dispatch JSON
    （非 draft 优先；草案记录可能含已被容量预检否决的旧映射）。
    两者皆缺的页计入 missing_pages。
    """
    page_layout: dict[int, str] = {}
    used_fallback = False
    for header, body in split_master_pages(master_text):
        pg = page_number(header)
        if pg is None:
            continue
        m = PCODE_RE.search(body)
        if m:
            page_layout[pg] = f"P{m.group(1)}"
    for path in dispatch_paths:
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        for slide in data.get("slides", []):
            try:
                pg, layout = int(slide["page"]), str(slide["layout"])
            except (KeyError, TypeError, ValueError):
                continue
            if pg not in page_layout:
                page_layout[pg] = layout
                used_fallback = True
    unknown, missing_pages = [], []
    pages = [page_number(h) for h, _ in split_master_pages(master_text)]
    pages = [p for p in pages if p is not None]
    for pg in pages:
        layout = page_layout.get(pg)
        if layout is None:
            missing_pages.append(pg)
        elif layout not in layout_bank:
            unknown.append(f"S{pg}:{layout}")
    pcode = {
        "criterion_id": "A5.2-pcode",
        "status": "fail" if unknown else ("error" if missing_pages else "pass"),
        "detail": (f"未知 P 码 {unknown}" if unknown else
                   f"无版式调度的页 {missing_pages}" if missing_pages else
                   f"全部 {len(pages)} 页 P 码存在于版式库（36 个 layout_id）"
                   + ("；调度取自母版视觉行回退" if used_fallback else "")),
    }
    projection = []
    for header, body in split_master_pages(master_text):
        pg = page_number(header)
        if pg is None:
            continue
        layout = page_layout.get(pg)
        if layout is None:
            continue  # 投影缺页在 A5.3 记 error
        bullets = page_bullets(body)
        # 容量投影只含视觉行落位映射声明的要点（未映射行如审计注记不进渲染；
        # 无映射声明时退回全部要点——无点无家由产品检查器 ② 承担）
        visual = re.search(r"(?:视觉行|视觉)[：:]\s*(.+)", body)
        mapped = set()
        if visual:
            mapped = {int(n) for n in MAPPING_RE.findall(visual.group(1))}
        if mapped:
            bullets = [b for i, b in enumerate(bullets, 1) if i in mapped]
        slide: dict = {"page": pg, "layout": layout,
                       "points": [strip_machine_marks(b) for b in bullets]}
        projection.append(slide)
    return pcode, {"slides": projection}, missing_pages


def check_term_literals(unit: dict, outline_text: str, master_text: str) -> dict:
    """A4.1 机检词面扫描：术语表误用列「」字面量命中 → candidates_for_judge。"""
    term_path = FIXTURE_ROOT / "judge-side" / "terminology" / f"{unit['id']}-{unit['slug']}.md"
    if not term_path.exists():
        return {"criterion_id": "A4.1-term-literal", "status": "error",
                "detail": f"术语表缺失: {term_path.name}"}
    hits = []
    corpus = outline_text + "\n" + master_text
    for line in term_path.read_text(encoding="utf-8").splitlines():
        if not line.strip().startswith("|"):
            continue
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        if len(cells) < 4 or cells[0] in ("#", "---", "场景"):
            continue
        misuse_cell = cells[3]
        for lit in re.findall(r"「([^」]{2,18})」", misuse_cell):
            if lit in corpus:
                hits.append(f"{cells[0]}:『{lit}』")
    return {"criterion_id": "A4.1-term-literal", "status": "candidates_for_judge",
            "detail": f"字面命中 {len(hits)} 处（advisory，语义判定归 L1）: "
                      + "; ".join(hits[:8]),
            "hit_count": len(hits)}


def check_render_structure(render_paths: list[Path],
                           project_root: Path | None = None) -> dict:
    """A5.5 机检：结构化收据必须绑定真实 render 产物。

    纯文本关键词只能作为候选提示，不能单独给 pass；否则任意说明文件都能
    伪造“护栏+白名单”命中。收据还必须满足 render contract 的核心结构，
    ``out`` 文件存在且其 SHA-256 与收据一致；若指定 ``project_root``，产物
    不得越出本次评测的 project/ 根目录。
    """
    if not render_paths:
        return {"criterion_id": "A5.5-render-structure", "status": "error",
                "detail": "未发现 render provenance 收据（仅扫描 project/）"}
    valid_receipts = []
    hard_errors = []
    project_root = project_root.resolve() if project_root is not None else None
    for path in render_paths:
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, UnicodeError, json.JSONDecodeError):
            continue
        if not isinstance(data, dict) or data.get("kind") != "render_provenance":
            continue
        if data.get("schema_version") != 1:
            hard_errors.append(f"{path.name}: schema_version 非 1")
            continue
        if data.get("backend") not in RENDER_BACKENDS:
            hard_errors.append(f"{path.name}: backend 非法")
            continue
        if not isinstance(data.get("renderer"), str) or not data.get("renderer"):
            hard_errors.append(f"{path.name}: renderer 缺失")
            continue
        if not re.fullmatch(r"[0-9a-f]{64}", str(data.get("out_sha256", ""))):
            hard_errors.append(f"{path.name}: out_sha256 非 64 位十六进制")
            continue
        if not all(isinstance(data.get(key), int) and data[key] > 0
                   for key in ("width", "height")):
            hard_errors.append(f"{path.name}: width/height 非正整数")
            continue
        raw_out = data.get("out")
        if not isinstance(raw_out, str) or not raw_out.strip():
            hard_errors.append(f"{path.name}: out 缺失")
            continue
        artifact = Path(raw_out).expanduser()
        if not artifact.is_absolute():
            artifact = path.parent / artifact
        artifact = artifact.resolve()
        if project_root is not None and not artifact.is_relative_to(project_root):
            hard_errors.append(f"{path.name}: out 越出 project/ ({artifact})")
            continue
        if not artifact.is_file():
            hard_errors.append(f"{path.name}: out 文件不存在 ({artifact})")
            continue
        try:
            artifact_format, artifact_dimensions = _artifact_format_and_dimensions(artifact)
        except (OSError, ValueError) as exc:
            hard_errors.append(f"{path.name}: 产物格式无效 ({exc})")
            continue
        allowed_suffixes = {
            "render:html": {"png", "html"},
            "render:mermaid": {"svg"},
            "render:echarts": {"png", "svg", "html"},
        }[data["backend"]]
        if artifact_format not in allowed_suffixes:
            hard_errors.append(
                f"{path.name}: backend={data['backend']} 不允许 {artifact_format} 产物"
            )
            continue
        if artifact_dimensions is not None and artifact_dimensions != (data["width"], data["height"]):
            hard_errors.append(
                f"{path.name}: 收据尺寸 {data['width']}x{data['height']} "
                f"!= 产物尺寸 {artifact_dimensions[0]}x{artifact_dimensions[1]}"
            )
            continue
        actual_sha256 = sha256_full(artifact)
        if actual_sha256 != data["out_sha256"]:
            hard_errors.append(f"{path.name}: out_sha256 与文件不一致")
            continue
        valid_receipts.append(path)
    if valid_receipts:
        return {"criterion_id": "A5.5-render-structure", "status": "pass",
                "detail": f"结构化 render provenance 收据 {len(valid_receipts)} 个"
                           f"（候选文件 {len(render_paths)} 个）"}
    if hard_errors:
        return {"criterion_id": "A5.5-render-structure", "status": "error",
                "error_kind": "render_provenance",
                "detail": "; ".join(hard_errors[:8])}
    return {"criterion_id": "A5.5-render-structure", "status": "candidates_for_judge",
            "detail": f"render 文件 {len(render_paths)} 个但没有合法 provenance 收据，"
                      "交 L1 核对结构"}


def check_style_record(style_paths: list[Path]) -> dict:
    if not style_paths:
        return {"criterion_id": "A5.1-style-attribution", "status": "error",
                "detail": "未发现 style selection 记录文件（selection_fingerprint 落盘）"}
    structured = []
    for path in style_paths:
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, UnicodeError, json.JSONDecodeError):
            continue
        if not isinstance(data, dict):
            continue
        if (isinstance(data.get("selection_fingerprint"), str)
                and data.get("selection_fingerprint")
                and isinstance(data.get("source"), str)
                and data.get("source")
                and (data.get("asset_id") or data.get("style_id") or data.get("name"))):
            structured.append(path)
    return {"criterion_id": "A5.1-style-attribution", "status":
            "pass" if structured else "candidates_for_judge",
            "detail": (f"结构化 selection 归因收据 {len(structured)} 个"
                       f"（候选文件 {len(style_paths)} 个）"
                       if structured else
                       f"style 记录文件 {len(style_paths)} 个但没有完整归因收据，"
                       "交 L1 核对结构")}


# --------------------------------------------------------------------------- #
# 主流程
# --------------------------------------------------------------------------- #

def normalize(item: dict) -> dict:
    """机检结果归一化：补 normalized_status（pass/fail/error/warning/
    candidates_for_judge/not_applicable）与 evidence 提示。"""
    item.setdefault("normalized_status", item["status"])
    return item


def classify_checker(label: str, run: dict) -> dict:
    """按检查器真实语义归一化退出码（非零 ≠ 一律内容失败）。"""
    rc = run["exit_code"]
    item = dict(run)
    item["criterion_id"] = label
    if rc == 0:
        item["status"] = "pass"
        if "over:" in run["stdout_tail"]:  # 容量软超：exit 0 但如实报告
            item["status"] = "warning"
            item["normalized_status"] = "warning"
        elif re.search(r"^WARN", run["stdout_tail"], re.M):
            item["status"] = "warning"
            item["normalized_status"] = "warning"
    elif rc == 1:
        if label == "A2.3-fact-candidates":
            item["status"] = "candidates_for_judge"
        elif label == "A2.2-ledger-structure" and LEDGER_TIER_MISMATCH_RE.search(
                run["stderr_tail"] + run["stdout_tail"]):
            # 已知兼容性边界：VALID_TIERS 三级 vs 四级「用户确认」
            item["status"] = "error"
            item["error_kind"] = "tool_contract_mismatch"
        else:
            item["status"] = "fail"
    else:
        item["status"] = "error"
        item["error_kind"] = "tool"
    return normalize(item)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--unit", required=True, help="单元 id，如 u01")
    parser.add_argument("--unit-dir", required=True,
                        help="case 工作区根（其内含 project/ 子树或直接为产物根）")
    parser.add_argument("--out", default=None, help="machine-report.json 输出路径")
    parser.add_argument("--keep-projection", default=None,
                        help="保存投影 capacity-spec.json 的路径（默认临时目录内即弃）")
    args = parser.parse_args()

    protocol = load_protocol()
    unit = find_unit(protocol, args.unit)
    unit_dir = Path(args.unit_dir).resolve()
    if not unit_dir.is_dir():
        print(f"ERROR: unit 目录不存在: {unit_dir}", file=sys.stderr)
        return 2

    artifacts = discover_artifacts(unit_dir)
    outline = latest_version(artifacts["outline_versions"], "outline-v")
    master = latest_version(artifacts["master_versions"], "deck-master-v")

    items: list[dict] = []
    inventory = {k: [{"path": str(p.relative_to(unit_dir)), "sha256_16": sha256_of(p)}
                     for p in v] for k, v in artifacts.items()}

    ignored_outputs = {Path(raw) for raw in (args.out, args.keep_projection) if raw}
    scope_violations = find_scope_violations(unit_dir, ignored=ignored_outputs)
    project_root = unit_dir / "project"
    items.append(normalize({
        "criterion_id": "VETO-project-scope",
        "status": "pass" if project_root.is_dir() and not scope_violations else "error",
        "error_kind": "input" if not project_root.is_dir() else "scope"
        if scope_violations else None,
        "detail": (f"产物根固定为 project/，越界项 {scope_violations[:8]}"
                   if scope_violations else
                   "产物根固定为 project/" if project_root.is_dir()
                   else "缺少 project/ 产物根，拒绝从 unit workspace 其他目录取证"),
    }))

    # 一票否决：content 文档全部落盘
    veto = {"criterion_id": "VETO-docs-on-disk",
            "status": "pass" if (outline and master) else "error",
            "detail": (f"outline={outline.name if outline else '缺失'}, "
                       f"master={master.name if master else '缺失'}（缺 → 阻断 L1）")}
    items.append(normalize(veto))
    if not (outline and master):
        report = {"unit": unit["id"], "unit_dir": str(unit_dir),
                  "inventory": inventory, "items": items,
                  "summary": _summarize(items)}
        _emit(args, report)
        return 1

    outline_text = outline.read_text(encoding="utf-8")
    master_text = master.read_text(encoding="utf-8")

    # —— 评测侧补测（无外部依赖）——
    items.append(normalize(check_page_counts(outline_text, master_text, unit["pages"])))
    items.append(normalize(check_ledger_coverage(master_text)))
    items.append(normalize(check_density(master_text)))
    items.append(normalize(check_notes_columns(master_text)))
    items.append(normalize(check_term_literals(unit, outline_text, master_text)))
    items.append(normalize(check_style_record(artifacts["style_records"])))
    items.append(normalize(check_render_structure(artifacts["render_outputs"],
                                                   project_root)))

    # —— 版式库 & 容量投影 ——
    layout_bank = _load_layout_bank()
    pcode, projection, missing_pages = check_pcode_and_project(
        master_text, artifacts["dispatch_records"],
        {lid for lid, _ in layout_bank})
    items.append(normalize(pcode))
    style_name = _extract_style_name(artifacts["style_records"])
    proj_item = _run_capacity(projection, missing_pages, args.keep_projection,
                              style_name)
    items.append(proj_item)

    # —— 包装既有检查器 ——
    py = sys.executable
    items.append(classify_checker(
        "A2.2-ledger-structure",
        run_checker("A2.2-ledger-structure",
                    [py, str(SCRIPTS_DIR / "check_number_ledger.py"), str(master)])))
    older_master = _previous_master(artifacts["master_versions"], master)
    if older_master is not None:
        items.append(classify_checker(
            "A2.2-diff-retention",
            run_checker("A2.2-diff-retention",
                        [py, str(SCRIPTS_DIR / "check_number_ledger.py"),
                         "--diff", str(older_master), str(master)])))
    else:
        items.append(normalize({
            "criterion_id": "A2.2-diff-retention", "status": "not_applicable",
            "detail": "无真实修订对（仅一个母版版本），留存检查不适用"}))
    items.append(classify_checker(
        "A1.2-promises+contract",
        run_checker("A1.2-promises+contract",
                    [py, str(SCRIPTS_DIR / "check_master_contract.py"), str(master)])))
    items.append(classify_checker(
        "A3.3-prose",
        run_checker("A3.3-prose",
                    [py, str(SCRIPTS_DIR / "check_deck_prose.py"), str(master)])))
    if unit["material_file"]:
        material = FIXTURE_ROOT / "materials" / unit["material_file"]
        if material.exists():
            items.append(classify_checker(
                "A2.3-fact-candidates",
                run_checker("A2.3-fact-candidates",
                            [py, str(SCRIPTS_DIR / "check_content_facts.py"),
                             str(master), str(material)])))
        else:
            items.append(normalize({
                "criterion_id": "A2.3-fact-candidates", "status": "error",
                "error_kind": "input",
                "detail": f"材料文件缺失: {material}"}))
    else:
        items.append(normalize({
            "criterion_id": "A2.3-fact-candidates", "status": "not_applicable",
            "detail": "只给目标单元：无材料文件，事实回读由 L1 对照简报语义核对"}))

    report = {"unit": unit["id"], "unit_dir": str(unit_dir),
              "protocol_version": protocol["version"],
              "artifacts": {"outline_used": outline.name, "master_used": master.name},
              "inventory": inventory, "items": items, "summary": _summarize(items)}
    _emit(args, report)

    hard = [i for i in items if i["status"] in ("fail", "error")]
    return 1 if hard else 0


def _extract_style_name(style_paths: list[Path]) -> str | None:
    """从 style selection 记录提取选定风格名（投影容量系数用）；取不到返回
    None（checker 按系数 1.0 处理，局限随 A5.3 明细披露）。"""
    for p in style_paths[:5]:
        try:
            data = json.loads(p.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        for key in ("style", "style_name", "selected_style", "name"):
            v = data.get(key) if isinstance(data, dict) else None
            if isinstance(v, str) and v:
                return v
    return None


def _load_layout_bank() -> list[tuple[str, str]]:
    """读取活动 canonical layout profiles；retired sidecar 仅保留作迁移输入。"""
    bank_file = SKILL_ROOT / "template-library/canonical/layouts"
    out = []
    for p in sorted(bank_file.glob("*/layout.json")):
        try:
            data = json.loads(p.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        aliases = data.get("aliases") if isinstance(data.get("aliases"), list) else []
        layout_id = next((str(value) for value in aliases
                          if re.fullmatch(r"P\d+", str(value))), None)
        if not layout_id:
            asset_id = str(data.get("asset_id", ""))
            layout_id = asset_id.rsplit(":", 1)[-1] if ":" in asset_id else p.stem
        out.append((layout_id, str(data.get("name", ""))))
    return out


def _previous_master(versions: list[Path], current: Path) -> Path | None:
    def version_no(p: Path) -> int:
        m = re.search(r"-v(\d+)", p.stem)
        return int(m.group(1)) if m else -1
    older = [p for p in versions if p != current and version_no(p) < version_no(current)]
    return max(older, key=version_no) if older else None


def _run_capacity(projection: dict, missing_pages: list[int], keep: str | None,
                  style_name: str | None = None) -> dict:
    if missing_pages:
        return normalize({"criterion_id": "A5.3-capacity", "status": "error",
                          "error_kind": "input",
                          "detail": f"版式调度缺页 {missing_pages}，投影不完整，不做假投影"})
    if not projection["slides"]:
        return normalize({"criterion_id": "A5.3-capacity", "status": "error",
                          "error_kind": "input",
                          "detail": "无可投影页面（调度记录与母版 P 码均缺失）"})
    spec = {"style": style_name, "slides": projection["slides"]}
    if keep:
        Path(keep).write_text(json.dumps(spec, ensure_ascii=False, indent=2),
                              encoding="utf-8")
        spec_path = Path(keep)
    else:
        fd = tempfile.NamedTemporaryFile("w", suffix=".json", delete=False,
                                         encoding="utf-8")
        json.dump(spec, fd, ensure_ascii=False)
        fd.close()
        spec_path = Path(fd.name)
    run = run_checker("A5.3-capacity",
                      [sys.executable, str(SCRIPTS_DIR / "check_deck_geometry.py"),
                       "--capacity", str(spec_path)])
    run["detail_limitation"] = (
        f"style 容量系数投影 style={style_name!r}"
        + ("" if style_name else "（未提取到选定风格名，按系数 1.0）")
        + "；风格系数与逐 slot 语义复核归 L1")
    return classify_checker("A5.3-capacity", run)


def _summarize(items: list[dict]) -> dict:
    counts: dict[str, int] = {}
    for i in items:
        counts[i["status"]] = counts.get(i["status"], 0) + 1
    return {"counts": counts,
            "hard_fail_or_error": [i["criterion_id"] for i in items
                                   if i["status"] in ("fail", "error")]}


def _emit(args, report: dict) -> None:
    if args.out:
        Path(args.out).write_text(
            json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"machine-report → {args.out}")
    print(json.dumps(report["summary"], ensure_ascii=False))


if __name__ == "__main__":
    raise SystemExit(main())
