"""从实际文字位置和连线测量判断关系；不读取能力声明或资格结果。"""
from __future__ import annotations

import math
import re


class OracleError(ValueError):
    pass


# 用 Range 获取实际文字矩形，不把隐藏 DOM、data 属性或输入 JSON 当作可见文字。
DOM_MEASURE_JS = r"""() => {
  const rect = r => [r.x,r.y,r.width,r.height];
  const visible = e => {
    for(let p=e;p;p=p.parentElement) {
      const s=getComputedStyle(p);
      if(s.display==='none'||s.visibility!=='visible'||Number(s.opacity)===0) return false;
    }
    return true;
  };
  const texts=[], edges=[], blocks=[];
  const walker=document.createTreeWalker(document.body,NodeFilter.SHOW_TEXT);
  let n;
  while(n=walker.nextNode()) {
    const e=n.parentElement;
    if(!e||['SCRIPT','STYLE','NOSCRIPT'].includes(e.tagName)||!n.textContent.trim()||!visible(e)) continue;
    const range=document.createRange();range.selectNodeContents(n);
    const boxes=Array.from(range.getClientRects()).filter(r=>r.width>0&&r.height>0);
    if(!boxes.length) continue;
    const s=getComputedStyle(e);
    texts.push({text:n.textContent.trim(),box:rect(range.getBoundingClientRect()),
      boxes:boxes.map(rect),font_size:parseFloat(s.fontSize),font_weight:s.fontWeight,
      color:s.color,order:texts.length});
  }
  for(const e of document.querySelectorAll('svg path,svg line,svg polyline')) {
    if(!visible(e)||typeof e.getTotalLength!=='function') continue;
    const s=getComputedStyle(e),m=e.getScreenCTM();
    if(!m||s.stroke==='none'||parseFloat(s.strokeWidth)<=0) continue;
    const len=e.getTotalLength(); if(!len) continue;
    const a=e.getPointAtLength(0).matrixTransform(m),b=e.getPointAtLength(len).matrixTransform(m);
    edges.push({start:[a.x,a.y],end:[b.x,b.y],directed:s.markerEnd!=='none',
      reverse:s.markerStart!=='none',box:rect(e.getBoundingClientRect())});
  }
  for(const e of document.querySelectorAll('[data-leo-block],[data-leo-block-item],th,td')) {
    if(!visible(e)) continue;
    const r=e.getBoundingClientRect();if(!r.width||!r.height)continue;
    blocks.push({box:rect(r),overflow:e.scrollWidth>e.clientWidth+1||e.scrollHeight>e.clientHeight+1});
  }
  return {schema_version:1,kind:'render-measurement',source:'browser-dom',
    viewport:[innerWidth,innerHeight],texts,edges,blocks};
}"""


def _normal(value):
    return re.sub(r"\s+", "", str(value))


def _box(value):
    if not isinstance(value, list) or len(value) != 4 or any(
        type(v) not in (int, float) or not math.isfinite(v) for v in value
    ) or value[2] <= 0 or value[3] <= 0:
        raise OracleError("oracle_measurement_invalid")
    return value


def _strings(value, *, nonempty=False):
    if not isinstance(value, list) or (nonempty and not value) or any(
        not isinstance(v, str) or not v.strip() for v in value
    ):
        raise OracleError("oracle_expectation_invalid")
    return value


def validate_expectation(expected, relation):
    """具体预期由输入用例冻结；枚举和必需判断来自独立 oracle。"""
    if not isinstance(expected, dict) or set(expected) != {
        "required_text", "facts", "focus", "reading_order", "structure"
    }:
        raise OracleError("oracle_expectation_invalid")
    _strings(expected["required_text"], nonempty=True)
    _strings(expected["facts"])
    _strings(expected["reading_order"], nonempty=True)
    if not isinstance(expected["focus"], str) or not expected["focus"].strip():
        raise OracleError("oracle_expectation_invalid")
    s = expected["structure"]
    fields = {
        "independent": {"items", "edges"},
        "comparison": {"items", "dimensions", "cells"},
        "trend": {"samples", "unit", "period", "baseline"},
        "process": {"nodes", "edges", "parallel"},
        "causal": {"nodes", "edges", "uncertainty"},
    }
    if relation not in fields or not isinstance(s, dict) or set(s) != fields[relation]:
        raise OracleError("oracle_expectation_invalid")
    if relation in {"independent", "comparison"}:
        _strings(s["items"], nonempty=True)
    if relation == "independent" and s["edges"] != []:
        raise OracleError("oracle_expectation_invalid")
    if relation == "comparison":
        _strings(s["dimensions"], nonempty=True)
        pairs = set()
        for cell in s["cells"]:
            if set(cell) != {"item", "dimension", "text", "unknown"} or type(cell["unknown"]) is not bool:
                raise OracleError("oracle_expectation_invalid")
            _strings([cell["text"]])
            pair = (cell["item"], cell["dimension"])
            if pair in pairs or pair[0] not in s["items"] or pair[1] not in s["dimensions"]:
                raise OracleError("oracle_expectation_invalid")
            pairs.add(pair)
        if pairs != {(i, d) for i in s["items"] for d in s["dimensions"]}:
            raise OracleError("oracle_expectation_invalid")
    if relation == "trend":
        if not isinstance(s["samples"], list) or len(s["samples"]) < 2:
            raise OracleError("oracle_expectation_invalid")
        _strings([s["unit"], s["period"]])
        for sample in s["samples"]:
            if set(sample) != {"time", "value"}:
                raise OracleError("oracle_expectation_invalid")
            _strings([sample["time"], sample["value"]])
            try:
                if not math.isfinite(float(sample["value"])):
                    raise ValueError()
            except ValueError as exc:
                raise OracleError("oracle_expectation_invalid") from exc
        if len({p["time"] for p in s["samples"]}) != len(s["samples"]):
            raise OracleError("oracle_expectation_invalid")
        if s["baseline"] is not None:
            _strings([s["baseline"]])
    if relation in {"process", "causal"}:
        _strings(s["nodes"], nonempty=True)
        if not isinstance(s["edges"], list) or not s["edges"]:
            raise OracleError("oracle_expectation_invalid")
        for edge in s["edges"]:
            keys = {"from", "to"} | ({"meaning", "support"} if relation == "causal" else set())
            if set(edge) != keys or any(edge[k] not in s["nodes"] for k in ("from", "to")) or edge["from"] == edge["to"]:
                raise OracleError("oracle_expectation_invalid")
            _strings(list(edge.values()))
        if relation == "causal":
            _strings(s["uncertainty"], nonempty=True)
        else:
            if not isinstance(s["parallel"], list):
                raise OracleError("oracle_expectation_invalid")
            for branch in s["parallel"]:
                if len(_strings(branch, nonempty=True)) < 2 or not set(branch).issubset(s["nodes"]):
                    raise OracleError("oracle_expectation_invalid")


def evaluate_output(expected, measurement, *, relation, oracle):
    validate_expectation(expected, relation)
    if (not isinstance(measurement, dict) or measurement.get("schema_version") != 1
            or measurement.get("kind") != "render-measurement"
            or measurement.get("source") not in {"browser-dom", "raster-ocr-reviewed"}):
        raise OracleError("oracle_measurement_missing")
    width, height = measurement["viewport"]
    if (width, height) != (1280, 720):
        raise OracleError("oracle_viewport_invalid")
    texts = measurement["texts"]
    if not isinstance(texts, list) or not isinstance(measurement["edges"], list) or not isinstance(measurement["blocks"], list):
        raise OracleError("oracle_measurement_invalid")
    for entry in texts:
        _strings([entry["text"]]); _box(entry["box"])
        if type(entry["font_size"]) not in (int, float) or not math.isfinite(entry["font_size"]):
            raise OracleError("oracle_measurement_invalid")

    def matches(text):
        needle = _normal(text)
        if re.fullmatch(r"[-+]?\d+(?:\.\d+)?", needle):
            pattern = re.compile(r"(?<![\d.])" + re.escape(needle) + r"(?![\d.])")
            return [t for t in texts if pattern.search(_normal(t["text"]))]
        return [t for t in texts if needle in _normal(t["text"])]

    def present(text):
        return bool(matches(text))

    def all_present(values):
        return all(present(v) for v in values)

    def ordered(values):
        # 以真实 DOM 阅读顺序验证；几何对齐在关系分支独立判断。
        positions = [next((i for i, t in enumerate(texts) if _normal(v) in _normal(t["text"])), -1) for v in values]
        return all(p >= 0 for p in positions) and positions == sorted(positions)

    def near(point, box):
        x, y, w, h = box
        return math.hypot(max(x-point[0], 0, point[0]-x-w), max(y-point[1], 0, point[1]-y-h)) <= 48

    def connected(edge, *, directed=False):
        for segment in measurement["edges"]:
            directions = [(segment["start"], segment["end"])] if not directed or segment["directed"] else []
            if segment.get("reverse"):
                directions.append((segment["end"], segment["start"]))
            for start, end in directions:
                if any(near(start, a["box"]) and near(end, b["box"])
                       for a in matches(edge["from"]) for b in matches(edge["to"])):
                    return True
        return False

    def no_conflicting_edges(structure):
        allowed = {(edge["from"], edge["to"]) for edge in structure["edges"]}
        for segment in measurement["edges"]:
            starts = [node for node in structure["nodes"] if any(near(segment["start"], t["box"]) for t in matches(node))]
            ends = [node for node in structure["nodes"] if any(near(segment["end"], t["box"]) for t in matches(node))]
            for start in starts:
                for end in ends:
                    if start == end:
                        continue
                    if ((segment["directed"] and (start, end) not in allowed)
                            or (segment.get("reverse") and (end, start) not in allowed)):
                        return False
        return True

    def contained(box):
        x,y,w,h = _box(box)
        return x >= -1 and y >= -1 and x+w <= width+1 and y+h <= height+1

    checks = {
        "all_required_text": all_present(expected["required_text"]),
        "all_facts": all_present(expected["facts"]),
        "focus_visible": present(expected["focus"]),
        "reading_order": ordered(expected["reading_order"]),
        "within_canvas": all(contained(t["box"]) for t in texts),
        "no_overflow": all(not b["overflow"] and contained(b["box"]) for b in measurement["blocks"]),
    }
    s = expected["structure"]
    if relation == "independent":
        checks.update(item_set=all_present(s["items"]), no_directed_edges=(
            not any(e["directed"] or e.get("reverse") for e in measurement["edges"])
            and not any(re.search(r"[→⇒⟶➜➔↓↑←]|->|=>", t["text"]) for t in texts)))
    elif relation == "comparison":
        alignment = True
        for dimension in s["dimensions"]:
            cells = [c for c in s["cells"] if c["dimension"] == dimension]
            boxes = [matches(c["text"]) for c in cells]
            if not all(boxes):
                alignment = False
                continue
            chosen = [b[0]["box"] for b in boxes]
            # 同维度必须在同一行且位于不同列，不能把一个值复用到多个格。
            alignment &= max(b[1] for b in chosen)-min(b[1] for b in chosen) <= 8
            alignment &= len({round(b[0]) for b in chosen}) == len(chosen)
            alignment &= any(all(abs(t["box"][1]-b[1]) <= 8 for b in chosen) for t in matches(dimension))
        checks.update(same_dimensions=all_present(s["dimensions"]),
            complete_grid=all_present(s["items"]+[c["text"] for c in s["cells"]]),
            aligned_cells=bool(alignment), unknown_preserved=all_present([c["text"] for c in s["cells"] if c["unknown"]]))
    elif relation == "trend":
        checks.update(ordered_samples=ordered([p["time"] for p in s["samples"]]),
            numeric_values=all(any(abs(t["box"][1]-v["box"][1]) <= 8 and abs(t["box"][0]-v["box"][0]) > 8
                                  for t in matches(p["time"]) for v in matches(p["value"])) for p in s["samples"]),
            unit_visible=present(s["unit"]), period_visible=present(s["period"]),
            baseline_preserved=s["baseline"] is None or present(s["baseline"]))
    elif relation == "process":
        parallel = True
        for branch in s["parallel"]:
            boxes = [matches(n) for n in branch]
            parallel &= bool(all(boxes) and max(b[0]["box"][1] for b in boxes)-min(b[0]["box"][1] for b in boxes) <= 8)
        checks.update(nodes_visible=all_present(s["nodes"]),
            dependency_edges=all(connected(e) for e in s["edges"]) and no_conflicting_edges(s), parallel_branches=bool(parallel))
    elif relation == "causal":
        checks.update(directed_edges=all(connected(e, directed=True) for e in s["edges"]) and no_conflicting_edges(s),
            edge_meaning=all_present([e["meaning"] for e in s["edges"]]),
            source_support=all_present([e["support"] for e in s["edges"]]),
            causal_uncertainty=all_present(s["uncertainty"]))
    required = set(oracle["common"] + oracle["relations"][relation]["required_checks"])
    if set(checks) != required:
        raise OracleError("oracle_rule_mismatch")
    return checks
