#!/usr/bin/env python3
"""跨行业内容质量测评 · L1 判官引擎（方案 005 §3.4）。

五维度判据规格（A1–A5 子判据 + 失败形态清单）+ 双模型家族调用
（GLM via claude -p / GPT via codex exec）+ 匿名化 + G-Eval 式 prompt
构建 + 判定解析与重试 + 仲裁模式。judge_content_a{1..5}.py 是薄入口。

模型家族与版本在 protocol.json models 节登记；调用产生真实费用，单次
评审只调用一次（格式/服务失败最多重试一次，原尝试完整留存）。
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import shutil
import subprocess
import sys
import time
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
FIXTURE_ROOT = SCRIPT_DIR.parent / "content-quality-20industries"

# --------------------------------------------------------------------------- #
# 维度判据规格（子判据 + 失败形态清单；否定感知：pass 须逐条显式排除）
# --------------------------------------------------------------------------- #

DIMENSIONS: dict[str, dict] = {
    "A1": {
        "title": "大纲结构与页序",
        "subcriteria": [
            {"id": "A1.1", "name": "页序形成因果/比较/转折链而非并列堆叠",
             "steps": "逐对检查相邻内容页，问「为什么下一页是它」：上一页的结论/张力是否驱动下一页的出现；整套页序是否服务于 one_thing 的论证链。",
             "failure_forms": [
                 "a. 相邻内容页互换位置不损失论证力（并列堆叠）",
                 "b. 某页出现缺乏前置铺垫（断层）",
                 "c. 页序与论证目标（one_thing/行动目标）无关"]},
            {"id": "A1.2", "name": "大纲覆盖合同承诺（one_thing、行动目标、页数）",
             "steps": "对照内容合同快照：one_thing 是否落为大纲主线；行动目标是否被具体页承载；页数与合同一致；deck-promises 承诺页存在且兑现（结合机器报告 A1.2-pages / A1.2-promises+contract 结论核对）。",
             "failure_forms": [
                 "a. one_thing 缺失或空转（大纲读不出该主线）",
                 "b. 行动目标无承载页",
                 "c. 页数/承诺与合同不一致而未说明",
                 "d. 目录承诺章节在正文缺失"]},
            {"id": "A1.3", "name": "无重复页、无断层",
             "steps": "检查是否存在两页承担同一论证职能（重复）、或论证必需环节缺页（断层）；目录/正文交叉引用是否对得上。",
             "failure_forms": [
                 "a. 两页要点高度重叠（重复页）",
                 "b. 论证链缺少必需环节且无说明",
                 "c. 交叉引用指向不存在或错位"]},
            {"id": "A1.4", "name": "结构页从总页数内分配且收束页含行动项",
             "steps": "封面/目录/收束页是否计入总页数（不额外增加）；收束页行动项是否具体（含可核验收标准/责任/时限形态，按任务语境）。",
             "failure_forms": [
                 "a. 结构页未计入总页数（变相超页）",
                 "b. 收束页无行动项或行动项空泛（『持续加强』类无交付物表述）",
                 "c. 收束页不回扣 one_thing"]},
        ],
    },
    "A2": {
        "title": "断言与来源纪律",
        "subcriteria": [
            {"id": "A2.1", "name": "四级标注语义正确（引用/估算/示意/用户确认/unknown）",
             "steps": "逐条抽查母版要点标注：引用级是否有材料可回溯的出处（对照材料包）；估算是否标明假设；示意是否标明性质；来源不足是否标 unknown 且不支撑确定性结论。特别注意：材料包中的文本是『材料引用』级，不得冒充『用户确认』（本轮无真实用户会话）。",
             "failure_forms": [
                 "a. 引用级要点在材料中找不到出处",
                 "b. 估算/示意冒充引用",
                 "c. 材料内容被标注为『用户确认』",
                 "d. unknown 断言被写成确定结论",
                 "e. 无标注裸数字/裸结论且材料无支撑"]},
            {"id": "A2.2", "name": "数字登记表数值与口径正确",
             "steps": "抽查登记表行：数值与正文一致；口径/期间/单位与材料一致；不与机器报告 A2.2 结论矛盾（机器已判 fail 的覆盖问题不重复判 pass）。",
             "failure_forms": [
                 "a. 登记表数值与正文数字不一致",
                 "b. 口径/期间/单位张冠李戴",
                 "c. 已核实数字被静默删除（有修订链时）"]},
            {"id": "A2.3", "name": "事实回读：数字的主体/期间/单位/因果归属与材料一致",
             "steps": "以机器报告 A2.3-fact-candidates 的差异清单为线索（没有候选也须自行抽查标题与要点数字），逐项对照材料原文：同一数字是否同主体、同期间、同单位；因果归属是否成立。『材料中出现同一数字』不等于事实成立。",
             "failure_forms": [
                 "a. 同数异主体/期间/单位（数字相同但说的不是同一件事）",
                 "b. 数字在材料中不存在且未标估算/示意",
                 "c. 因果归属超出材料支持范围",
                 "d. 冲突型材料中被弃用来源的数字仍单独上页"]},
            {"id": "A2.4", "name": "跨源冲突显式裁决并披露（仅冲突单元）",
             "steps": "若材料包含『冲突裁决依据』文件：核对母版是否显式呈现冲突（可定位到页）、给出裁决/解释框架、不盲从权威/职级、不静默取舍。无该文件时输出 not_applicable 并说明。",
             "failure_forms": [
                 "a. 冲突被回避（只呈现单侧口径）",
                 "b. 混用口径拼数",
                 "c. 以权威/职级/考核动机作为裁决依据",
                 "d. 无依据调和（如取平均）"]},
        ],
    },
    "A3": {
        "title": "要点密度与文案纪律",
        "subcriteria": [
            {"id": "A3.1", "name": "结论句标题按页面角色与论证模式条件化",
             "steps": "逐页核对标题：内容页标题是否为具体论断句（主谓宾齐备、有依据，可信数字在位则用数字；无数字依据不强迫补数）；封面/目录/收束等结构页按其角色检查（不套论断句模板）。",
             "failure_forms": [
                 "a. 内容页标题是话题短语而非论断（如『关于营收情况』）",
                 "b. 标题论断无后文支撑",
                 "c. 无数字依据的标题硬造数字",
                 "d. 结构页被强套论断句或内容页用了金句替代论断"]},
            {"id": "A3.2", "name": "要点为完整论断句+证据跟随且档位合规",
             "steps": "内容页第一条要点是否为完整论断句、其后为证据跟随（数字/图/引用，带标注短标）；结合机器报告 A3.2-density 结论核对档位（机器判 fail 的密度问题不重复判 pass）。",
             "failure_forms": [
                 "a. 要点是名词短语堆砌而非论断",
                 "b. 证据跟随缺失（论断裸奔）",
                 "c. 要点间同义复述凑数",
                 "d. 机器密度 fail 被无视"]},
            {"id": "A3.3", "name": "文案纪律（翻案腔/AI 腔/黑话）",
             "steps": "结合机器报告 A3.3-prose：exit 1（翻案腔超限）即 fail；此外抽查 AI 腔/黑话 WARN 明细是否遮蔽了必要信息的清晰表达。",
             "failure_forms": [
                 "a. 翻案腔『不是X而是Y/看似X实则Y』成瘾",
                 "b. 英文 AI 套话（dive into/let's/journey）",
                 "c. 黑话密度让受众读不懂",
                 "d. 机器 fail 被无视"]},
            {"id": "A3.4", "name": "备注分栏可用（speaker_script 是讲稿、engineering 是工程备注）",
             "steps": "抽查备注：speaker_script 是否为可实际口播的讲稿（含讲述衔接/预期疑问），engineering 是否承载工程性信息；占位残留即 fail（机器已查，语义空洞由本项判）。",
             "failure_forms": [
                 "a. speaker_script 只有一句话或复述标题",
                 "b. engineering 分栏空洞（『无』/占位）",
                 "c. 备注与页面内容脱节"]},
        ],
    },
    "A4": {
        "title": "行业语境匹配",
        "subcriteria": [
            {"id": "A4.1", "name": "行业术语使用正确（按术语正误对照表）",
             "steps": "按材料包中的术语正误对照表逐条核对母版与大纲：『误用形态』命中即 fail（表中标注『常识性』的条目只作提示，不单独判 fail）；机器报告的字面命中清单是线索。表内条目未命中误用形态方可 pass。",
             "failure_forms": [
                 "a. 命中表中『可核』条目的误用形态",
                 "b. 术语跨语境错配（商业术语用于政务/公益等错场合）",
                 "c. 自造术语替代行业规范术语"]},
            {"id": "A4.2", "name": "语气与场合合规",
             "steps": "按行业场合核对语气：政务庄重、医疗不绝对化、金融有风险披露意识、公益不滥用商业话术、技术评审严谨等（泛化区同判）。",
             "failure_forms": [
                 "a. 语体与场合错配（营销话术进监管/学术/公益语境）",
                 "b. 医疗绝对化表述",
                 "c. 对受众的称呼/姿态失当（如把监管委员会当客户营销）"]},
            {"id": "A4.3", "name": "行业数据直觉不越界",
             "steps": "检查是否存在行业常识性错误（如把毛利率当周转率、把订单量当营收、术语化错误归因）；无法核实的行业判断是否已标注不确定性。",
             "failure_forms": [
                 "a. 行业常识性错误（概念/指标错用）",
                 "b. 无依据的行业断言未标不确定",
                 "c. 行业惯例错配（如政务汇报出现股权激励细节）"]},
        ],
    },
    "A5": {
        "title": "风格与版式选择（合同层）",
        "subcriteria": [
            {"id": "A5.1", "name": "风格归因在场且选择依据落盘",
             "steps": "核对风格选择记录：是否有带归因的推荐/选择依据（本行业任务语境为什么选它）；与行业/受众/场合是否匹配；错配时是否有首次风险提示。材料包含 style 记录文件（selection 指纹）。",
             "failure_forms": [
                 "a. 无归因句（只报风格名）",
                 "b. 选择依据与任务语境脱节（路演选了学术风之类且无理由）",
                 "c. 明显错配无风险提示",
                 "d. selection 指纹缺失（机器 error）被无视"]},
            {"id": "A5.2", "name": "版式调度与页面角色匹配、P 码不虚构",
             "steps": "结合机器报告 A5.2-pcode 与调度记录：数据密集页是否用图表/数据版式、论证页用论证版式、结构页用封面/目录版式；调度 ID 是否真实存在（机器判 fail 的虚构 P 码不重复判 pass）。",
             "failure_forms": [
                 "a. 数据页用了纯文字版式（或反之）",
                 "b. P 码虚构/调度记录缺页被无视",
                 "c. 全 deck 单一版式不随页面角色变化"]},
            {"id": "A5.3", "name": "容量预检如实、修订不缩字号",
             "steps": "结合机器报告 A5.3-capacity：硬超即 fail（机器）；软超是否如实报告（不得写成『全部容量正常』）；有修订链时修订是否只改内容或换版式（不缩字号）。",
             "failure_forms": [
                 "a. 硬超被无视或以缩字号应付",
                 "b. 软超被掩盖（报告与实际不符）",
                 "c. 容量预检结论缺失"]},
            {"id": "A5.4", "name": "泛化区附加（DG1–DG4，仅 G2 单元）",
             "steps": "材料包含『梯度：G2』标记时核对：不误导（DG1）、无虚构风格名（DG2）、有降级指引（DG3）、降落可 render 的近邻风格（DG4）。G1 单元输出 not_applicable 并说明。",
             "failure_forms": [
                 "a. 无专属风格资产时误导性声称『专为该行业设计』",
                 "b. 虚构风格名",
                 "c. 降级时无指引（只说不行不说怎么办）",
                 "d. 降落的近邻风格本身不可用"]},
            {"id": "A5.5", "name": "style render 注入产物含护栏且组合器白名单投影正常",
             "steps": "核对材料包中的 render 输出文件：护栏块与组合器白名单投影是否在结构上完整（机器报告 A5.5 未命中关键词时由本项人工核对结构）。",
             "failure_forms": [
                 "a. render 输出缺失（机器 error）被无视",
                 "b. 护栏块缺失（风格约束未注入）",
                 "c. 白名单/组合器投影缺失或含未知条目"]},
        ],
    },
}

PROMPT_TEMPLATE = """你是一名严格的内容质量评审官。下面给你一个匿名化的演示文稿内容包（含任务语境、大纲、逐页母版、材料、机器检查报告、风格与版式记录）。你只评审维度 {dim}（{title}），逐子判据给出 pass/fail/not_applicable/error 与可定位证据。

## 评审纪律（先读）
1. pass 必须附可定位证据（页码/文件/原文短引）；无证据的 pass 无效。
2. 判 pass 前必须逐条排除该子判据的失败形态，并在 failure_forms_excluded 中列出已排除的编号；命中任一失败形态即 fail。
3. 材料不足或无法可靠判定时输出 status:"error" 并在 reason 说明缺什么；不要猜，不要默认通过。
4. 该维度不适用时（如非冲突单元的冲突裁决、G1 的降级附加项）输出 status:"not_applicable" 并说明理由。
5. 机器检查报告是线索不是结论：机器已判 fail 的项不得无视（重复确认可引用机器证据），但机器 candidates/warning 需你语义裁决。
6. 禁止输出总分；triage_score 仅作分诊参考。
7. 只输出一个 JSON 对象，不要输出任何其他文字。

## 本维度子判据
{subcriteria}

## 待评审内容包
{package}

## 输出 JSON 格式
{{
  "dimension": "{dim}",
  "model_self_report": "你的模型名（如实；不确定写 unknown）",
  "subcriteria": [
    {{"criterion_id": "{dim}.1", "status": "pass|fail|not_applicable|error",
      "evidence": "可定位证据（页码/文件/短引）",
      "reason": "判定理由",
      "failure_forms_excluded": ["a", "b"]}}
  ],
  "dimension_conclusion": "一句话维度结论",
  "triage_score_0_4": 0
}}
"""

ARBITRATE_TEMPLATE = """你是一名独立仲裁评审官。同一匿名内容包的同一子判据得到两份分歧初判。请独立核对原件（不要迎合任何一方），给出仲裁结论。只输出一个 JSON 对象。

## 内容包
{package}

## 分歧子判据规格
{sub}

## 初判 A（评审官甲）
{verdict_a}

## 初判 B（评审官乙）
{verdict_b}

## 输出 JSON 格式
{{
  "criterion_id": "{cid}",
  "status": "pass|fail|not_applicable|error",
  "evidence": "可定位证据",
  "reason": "仲裁理由（须指出哪份初判依据不足及为什么）",
  "failure_forms_excluded": ["a", "b"],
  "chosen_side": "A|B|neither"
}}
"""

ARBITRATE_DIMENSION_TEMPLATE = """你是一名独立仲裁评审官。同一匿名内容包的维度 {dim}（{title}）得到两份存在分歧的初判（同一判据一个 pass 一个 fail/error）。请独立核对原件（不要迎合任何一方），对**整个维度全部子判据**逐项重判——分歧项给出裁决理由并指出哪份初判依据不足；两判官一致的项复核确认后保留。评审纪律与普通评审相同（pass 须带可定位证据、逐条排除失败形态、not_applicable 须理由、不输出总分）。只输出一个 JSON 对象，格式与普通评审相同（dimension/model_self_report/subcriteria/dimension_conclusion）。

## 内容包
{package}

## 本维度子判据
{subcriteria}

## 初判 A（评审官甲）
{verdict_a}

## 初判 B（评审官乙）
{verdict_b}
"""


# --------------------------------------------------------------------------- #
# 匿名化（移除模型/轮次信息与单元标识；映射由评测侧保管）
# --------------------------------------------------------------------------- #

ANON_FILE_MAP = [
    ("outline", "DOC-outline.md"),
    ("master", "DOC-master.md"),
    ("material", "DOC-materials.md"),
    ("terminology", "REF-terminology.md"),
    ("adjudication", "REF-adjudication.md"),
    ("machine", "REF-machine-report.json"),
    ("style", "REF-style-record.json"),
    ("dispatch", "REF-layout-dispatch.json"),
    ("render", "REF-style-render.md"),
    ("gradient", "REF-context.md"),
]


def anonymize_package(unit: dict, unit_dir: Path, anon_root: Path,
                      machine_report: Path | None) -> Path:
    """构造匿名包：中性文件名 + 语境说明（含梯度标记，供 A5.4 适用性判定）。
    不改写内容（事实出处与委托证据必须保留）。返回匿名包目录。"""
    import check_content_quality as ccq  # 同目录复用发现逻辑
    # Stable across reruns while keeping the unit key out of the package path.
    anon_id = "PKG-" + hashlib.sha256(
        str(unit["id"]).encode("utf-8")).hexdigest()[:12]
    pkg = anon_root / anon_id
    pkg.mkdir(parents=True)
    artifacts = ccq.discover_artifacts(unit_dir)
    outline = ccq.latest_version(artifacts["outline_versions"], "outline-v")
    master = ccq.latest_version(artifacts["master_versions"], "deck-master-v")
    copied = []
    mapping = {"anon_id": anon_id, "unit": unit["id"]}
    pairs = [
        (outline, "outline"), (master, "master"),
        (machine_report, "machine"),
        (FIXTURE_ROOT / "judge-side" / "terminology"
         / f"{unit['id']}-{unit['slug']}.md", "terminology"),
    ]
    if unit["conflict"]:
        pairs.append((FIXTURE_ROOT / "judge-side" / "adjudication-conflicts.md",
                      "adjudication"))
    if unit["material_file"]:
        pairs.append((FIXTURE_ROOT / "materials" / unit["material_file"],
                      "material"))
    if artifacts["style_records"]:
        pairs.append((artifacts["style_records"][0], "style"))
    if artifacts["dispatch_records"]:
        pairs.append((artifacts["dispatch_records"][0], "dispatch"))
    if artifacts["render_outputs"]:
        pairs.append((artifacts["render_outputs"][0], "render"))
    for src, kind in pairs:
        if src is not None and Path(src).exists():
            name = dict(ANON_FILE_MAP)[kind]
            shutil.copyfile(src, pkg / name)
            copied.append(name)
            mapping[kind] = name
    (pkg / "REF-context.md").write_text(
        f"# 语境说明\n\n- 任务梯度：{unit['gradient']}（G2=泛化区，A5.4 适用；G1 不适用）\n"
        f"- 冲突型单元：{'是（A2.4 适用）' if unit['conflict'] else '否（A2.4 not_applicable）'}\n"
        f"- 材料形态：{unit['material_form']}\n- 主要受众：{unit['audience']}\n"
        f"- 任务型：{unit['task_type']}\n- 行业：{unit['industry']}\n",
        encoding="utf-8")
    (pkg / "MANIFEST.json").write_text(
        json.dumps({"files": copied, "note": "匿名包：不含单元号/轮次/模型信息"},
                   ensure_ascii=False, indent=2), encoding="utf-8")
    with (anon_root / "anon-map.jsonl").open("a", encoding="utf-8") as mapping_file:
        mapping_file.write(json.dumps(mapping, ensure_ascii=False) + "\n")
    return pkg


def render_package_text(pkg: Path, max_chars: int = 60000) -> str:
    parts = []
    for f in sorted(pkg.iterdir()):
        if f.name in ("MANIFEST.json",):
            continue
        text = f.read_text(encoding="utf-8", errors="replace")
        if len(text) > 25000:
            text = text[:25000] + f"\n…（{f.name} 截断，全文见文件）"
        parts.append(f"### 文件：{f.name}\n```\n{text}\n```\n")
    out = "\n".join(parts)
    return out[:max_chars] + "\n…（包截断）" if len(out) > max_chars else out


# --------------------------------------------------------------------------- #
# 模型家族调用（真实 CLI；费用真实发生）
# --------------------------------------------------------------------------- #

def call_model(family: str, prompt: str, timeout: int = 600) -> dict:
    """调用判官模型。返回 {ok, text, usage, command}。失败抛异常由上层记 error。"""
    if family == "glml":
        cmd = ["claude", "-p", "--model", "glm-5.3"]
        proc = subprocess.run(cmd, input=prompt, capture_output=True,
                              text=True, timeout=timeout)
        text = proc.stdout.strip()
        warn = "[claude-code:unrecognized_model]"
        if warn in text:
            text = text.replace(warn, "").strip()
        if text.startswith('"') and text.endswith('"') and len(text) > 2:
            text = text[1:-1]
        return {"ok": proc.returncode == 0 and bool(text),
                "text": text, "usage": None,
                "command": "claude -p --model glm-5.3 (stdin)",
                "returncode": proc.returncode,
                "stderr": proc.stderr[-500:]}
    if family == "gpt":
        cmd = ["codex", "exec", "--skip-git-repo-check", "-s", "read-only",
               "Respond with ONLY the requested JSON object. No prose.\n\n" + prompt]
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
        combined = proc.stdout + proc.stderr
        m = re.search(r"tokens used\s*([\d,]+)", combined)
        usage = int(m.group(1).replace(",", "")) if m else None
        return {"ok": proc.returncode == 0, "text": proc.stdout.strip(),
                "usage": usage,
                "command": "codex exec --skip-git-repo-check -s read-only",
                "returncode": proc.returncode,
                "stderr": proc.stderr[-500:]}
    raise ValueError(f"未知家族 {family}（可用：glml / gpt）")


# --------------------------------------------------------------------------- #
# 判定解析与校验（无证据 pass / 非法 JSON / 缺子项 = error）
# --------------------------------------------------------------------------- #

def extract_json(text: str) -> dict | None:
    """容忍围栏/前后噪声提取首个平衡 JSON 对象。"""
    text = re.sub(r"```(?:json)?", "", text)
    start = text.find("{")
    while start != -1:
        depth = 0
        for i in range(start, len(text)):
            if text[i] == "{":
                depth += 1
            elif text[i] == "}":
                depth -= 1
                if depth == 0:
                    try:
                        obj = json.loads(text[start:i + 1])
                        if isinstance(obj, dict):
                            return obj
                    except json.JSONDecodeError:
                        break
        start = text.find("{", start + 1)
    return None


def validate_verdict(obj: dict, dim: str) -> list[str]:
    """Validate the complete dimension verdict schema."""
    if not isinstance(obj, dict):
        return ["输出不是 JSON 对象"]
    problems = []
    if obj.get("dimension") != dim:
        problems.append(f"dimension 必须为 {dim!r}")
    if not isinstance(obj.get("model_self_report"), str) or not obj.get("model_self_report", "").strip():
        problems.append("model_self_report 必须为非空字符串")
    if not isinstance(obj.get("dimension_conclusion"), str) or not obj.get("dimension_conclusion", "").strip():
        problems.append("dimension_conclusion 必须为非空字符串")
    score = obj.get("triage_score_0_4")
    if isinstance(score, bool) or not isinstance(score, int) or not 0 <= score <= 4:
        problems.append("triage_score_0_4 必须为 0-4 整数")
    subs = obj.get("subcriteria")
    if not isinstance(subs, list) or not subs:
        problems.append("输出缺 subcriteria 数组")
        return problems
    expected = {s["id"] for s in DIMENSIONS[dim]["subcriteria"]}
    got = set()
    for s in subs:
        if not isinstance(s, dict):
            problems.append("subcriteria 项必须为对象")
            continue
        raw_cid = s.get("criterion_id")
        cid = raw_cid if isinstance(raw_cid, str) else str(raw_cid or "")
        if not isinstance(raw_cid, str) or not cid:
            problems.append("criterion_id 必须为非空字符串")
        if cid not in expected:
            problems.append(f"{cid}: 未知子判据")
        if cid in got:
            problems.append(f"{cid}: 子判据重复")
        got.add(cid)
        status = s.get("status")
        if status not in ("pass", "fail", "not_applicable", "error"):
            problems.append(f"{cid}: 非法状态 {status!r}")
        for field in ("evidence", "reason"):
            if field in s and not isinstance(s[field], str):
                problems.append(f"{cid}: {field} 必须为字符串")
        excluded = s.get("failure_forms_excluded")
        if excluded is not None and (
                not isinstance(excluded, list)
                or any(not isinstance(item, str) for item in excluded)):
            problems.append(f"{cid}: failure_forms_excluded 必须为字符串数组")
        if status == "pass" and not str(s.get("evidence", "")).strip():
            problems.append(f"{cid}: 无证据 pass 无效")
        if status == "pass" and not s.get("failure_forms_excluded"):
            problems.append(f"{cid}: pass 未列已排除失败形态")
        if status == "not_applicable" and not str(s.get("reason", "")).strip():
            problems.append(f"{cid}: not_applicable 缺理由")
    missing = expected - got
    if missing:
        problems.append(f"缺子判据 {sorted(missing)}")
    return problems


def validate_arbitration_verdict(obj: dict, cid: str) -> list[str]:
    """Validate the compact single-criterion arbitration response."""
    if not isinstance(obj, dict):
        return ["仲裁输出不是 JSON 对象"]
    problems = []
    if obj.get("criterion_id") != cid:
        problems.append(f"criterion_id 必须为 {cid!r}")
    status = obj.get("status")
    if status not in ("pass", "fail", "not_applicable", "error"):
        problems.append(f"{cid}: 非法状态 {status!r}")
    for field in ("evidence", "reason"):
        if field in obj and not isinstance(obj[field], str):
            problems.append(f"{cid}: {field} 必须为字符串")
    if status == "pass" and not str(obj.get("evidence", "")).strip():
        problems.append(f"{cid}: 仲裁 pass 无证据")
    if status == "pass" and (
            not isinstance(obj.get("failure_forms_excluded"), list)
            or not obj.get("failure_forms_excluded")):
        problems.append(f"{cid}: 仲裁 pass 未列已排除失败形态")
    if status == "not_applicable" and not str(obj.get("reason", "")).strip():
        problems.append(f"{cid}: not_applicable 缺理由")
    if obj.get("chosen_side") not in ("A", "B", "neither"):
        problems.append(f"{cid}: chosen_side 必须为 A/B/neither")
    return problems


def run_judge(dim: str, pkg: Path, family: str, out_dir: Path,
              call_fn=None, max_chars: int = 60000) -> dict:
    """评审一个维度：构建 prompt → 调用 → 解析 → 校验（含一次重试）→ 落盘。"""
    assert dim in DIMENSIONS
    call = call_fn or call_model
    out_dir.mkdir(parents=True, exist_ok=True)
    spec = DIMENSIONS[dim]
    subs_text = ""
    for s in spec["subcriteria"]:
        subs_text += f"#### {s['id']} {s['name']}\n核对步骤：{s['steps']}\n失败形态（须逐条排除）：\n"
        for f in s["failure_forms"]:
            subs_text += f"  - {f}\n"
        subs_text += "\n"
    prompt = PROMPT_TEMPLATE.format(
        dim=dim, title=spec["title"], subcriteria=subs_text,
        package=render_package_text(pkg, max_chars))

    attempts = []
    verdict = None
    for attempt in (1, 2):
        if attempt == 2:
            prompt = ("上次输出无法解析为合法判定 JSON。请重新输出，只输出一个"
                      " JSON 对象，不要任何其他文字。\n\n" + prompt)
        try:
            resp = call(family, prompt)
        except Exception as exc:  # 服务失败
            attempts.append({"attempt": attempt, "error": repr(exc)})
            continue
        attempts.append({"attempt": attempt, "returncode": resp.get("returncode"),
                         "usage": resp.get("usage"),
                         "raw_text": resp.get("text", "")[:20000]})
        obj = extract_json(resp.get("text", ""))
        if obj is None:
            attempts[-1]["parse"] = "invalid_json"
            continue
        problems = validate_verdict(obj, dim)
        if problems:
            attempts[-1]["parse"] = "invalid_verdict"
            attempts[-1]["problems"] = problems
            continue
        verdict = obj
        break

    result = {
        "dimension": dim, "family": family, "pkg": str(pkg),
        "judge_model_self_report": (verdict or {}).get("model_self_report"),
        "verdict": verdict,
        "attempts": attempts,
        "status": "ok" if verdict else "error",
        "ts": time.strftime("%Y-%m-%dT%H:%M:%S"),
    }
    stem = f"{dim}-{family}"
    (out_dir / f"{stem}.json").write_text(
        json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    for i, a in enumerate(attempts, 1):
        (out_dir / f"{stem}.attempt{i}.txt").write_text(
            a.get("raw_text", json.dumps(a, ensure_ascii=False)),
            encoding="utf-8")
    return result


def run_dimension_arbitration(dim: str, pkg: Path, verdict_a: dict,
                              verdict_b: dict, family: str, out_dir: Path,
                              call_fn=None, max_chars: int = 60000) -> dict:
    """维度级仲裁（方案 §3.4：维度内 ≥2 项分歧时仲裁覆盖整维度）。

    独立上下文对整维度全部子判据重判；两份初判完整保留在结果中。
    """
    call = call_fn or call_model
    spec = DIMENSIONS[dim]
    subs_text = ""
    for s in spec["subcriteria"]:
        subs_text += f"#### {s['id']} {s['name']}\n{s['steps']}\n"
        for f in s["failure_forms"]:
            subs_text += f"  - {f}\n"
        subs_text += "\n"
    prompt = ARBITRATE_DIMENSION_TEMPLATE.format(
        dim=dim, title=spec["title"], package=render_package_text(pkg, max_chars),
        subcriteria=subs_text,
        verdict_a=json.dumps(verdict_a, ensure_ascii=False),
        verdict_b=json.dumps(verdict_b, ensure_ascii=False))
    attempts = []
    verdict = None
    for attempt in (1, 2):
        if attempt == 2:
            prompt = ("上次输出无法解析。重新只输出一个 JSON 对象。\n\n" + prompt)
        try:
            resp = call(family, prompt)
        except Exception as exc:
            attempts.append({"attempt": attempt, "error": repr(exc)})
            continue
        attempts.append({"attempt": attempt,
                         "raw_text": resp.get("text", "")[:20000],
                         "usage": resp.get("usage")})
        obj = extract_json(resp.get("text", ""))
        if obj is None:
            attempts[-1]["parse"] = "invalid_json"
            continue
        problems = validate_verdict(obj, dim)
        if problems:
            attempts[-1]["parse"] = "invalid_verdict"
            attempts[-1]["problems"] = problems
            continue
        verdict = obj
        break
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / f"ARB-DIM-{dim}-{family}.json").write_text(
        json.dumps({"dimension": dim, "family": family, "verdict": verdict,
                    "verdict_a": verdict_a, "verdict_b": verdict_b,
                    "attempts": attempts,
                    "status": "ok" if verdict else "error"},
                   ensure_ascii=False, indent=2), encoding="utf-8")
    return {"dimension": dim, "status": "ok" if verdict else "error",
            "verdict": verdict}


def run_arbitration(cid: str, pkg: Path, verdict_a: dict, verdict_b: dict,
                    family: str, out_dir: Path, call_fn=None) -> dict:
    """同子判据分歧仲裁：第三个独立上下文核对，保留两份初判。"""
    call = call_fn or call_model
    dim = cid.split(".")[0]
    sub = next(s for s in DIMENSIONS[dim]["subcriteria"] if s["id"] == cid)
    prompt = ARBITRATE_TEMPLATE.format(
        package=render_package_text(pkg), sub=json.dumps(sub, ensure_ascii=False),
        verdict_a=json.dumps(verdict_a, ensure_ascii=False),
        verdict_b=json.dumps(verdict_b, ensure_ascii=False), cid=cid)
    try:
        resp = call(family, prompt)
    except Exception as exc:
        return {"criterion_id": cid, "status": "error", "reason": repr(exc)}
    obj = extract_json(resp.get("text", ""))
    problems = validate_arbitration_verdict(obj, cid)
    if problems:
        return {"criterion_id": cid, "status": "error",
                "reason": "仲裁输出 schema 无效: " + "; ".join(problems),
                "raw": resp.get("text", "")[:2000]}
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / f"ARB-{cid.replace('.', '-')}.json").write_text(
        json.dumps({"criterion_id": cid, "arbitration": obj,
                    "verdict_a": verdict_a, "verdict_b": verdict_b,
                    "family": family}, ensure_ascii=False, indent=2),
        encoding="utf-8")
    return {"criterion_id": cid, **obj}


def build_arg_parser(doc: str) -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=doc)
    parser.add_argument("--anon-dir", required=True, help="匿名产物包目录")
    parser.add_argument("--family", required=True, choices=["glml", "gpt"])
    parser.add_argument("--out-dir", required=True, help="判官结果输出目录")
    parser.add_argument("--max-chars", type=int, default=60000)
    return parser


def main_for(dim: str, doc: str) -> int:
    args = build_arg_parser(doc).parse_args()
    pkg = Path(args.anon_dir)
    if not pkg.is_dir():
        print(f"ERROR: 匿名包不存在: {pkg}", file=sys.stderr)
        return 2
    result = run_judge(dim, pkg, args.family, Path(args.out_dir),
                       max_chars=args.max_chars)
    print(json.dumps({"dimension": result["dimension"],
                      "status": result["status"],
                      "attempts": len(result["attempts"])}, ensure_ascii=False))
    return 0 if result["status"] == "ok" else 1
