#!/usr/bin/env python3
"""diagram render — 结构图的确定性渲染（批次 3-G）。

把 diagram.json（节点/边/方向）用 Pillow 自绘为 PNG，进入 strict input asset
通道：图片模型只做风格化合成，结构本身不依赖模型。

输入 JSON 结构：
  {
    "direction": "LR" | "TB",          # 默认 LR
    "nodes": [{"id": "a", "label": "采集"}],
    "edges": [{"from": "a", "to": "b", "label": "可选"}],
    "title": "可选标题"
  }

画法：分层布局（按依赖深度分层，LR 从左到右，TB 从上到下），圆角矩形节点 +
箭头连线 + 可选边标签；中文字体回退链（PingFang/Hiragino/系统默认）。
确定性：同输入逐字节确定（字体解析失败时用默认位图字体，仍确定）。

用法：python3 diagram_render.py diagram.json out.png
退出码：0 成功；2 用法/输入错误；3 渲染错误。
"""
import json
import sys
from pathlib import Path

W, H = 2560, 1440
PAD = 120
NODE_W, NODE_H = 300, 120
GAP_X, GAP_Y = 160, 80
BG = (255, 255, 255, 255)
NODE_FILL = (232, 238, 247, 255)
NODE_LINE = (27, 42, 74, 255)
ARROW = (90, 107, 132, 255)
TEXT = (30, 42, 59, 255)
FONT_SIZES = {"node": 34, "edge": 26, "title": 44}


def _load_font(size):
    try:
        from PIL import ImageFont
    except ImportError:
        return None
    for family in ("PingFang SC", "Hiragino Sans GB", "Arial Unicode MS",
                   "Microsoft YaHei", "DejaVuSans"):
        try:
            return ImageFont.truetype(family, size)
        except OSError:
            continue
    for p in ("/System/Library/Fonts/PingFang.ttc",
              "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"):
        try:
            from PIL import ImageFont
            return ImageFont.truetype(p, size)
        except OSError:
            continue
    try:
        from PIL import ImageFont
        return ImageFont.load_default()
    except Exception:
        return None


def _layers(nodes, edges):
    depth = {n["id"]: 0 for n in nodes}
    adj = {n["id"]: [] for n in nodes}
    for e in edges:
        if e["from"] in adj and e["to"] in adj:
            adj[e["from"]].append(e["to"])
    for _ in range(len(nodes)):
        changed = False
        for src, dsts in adj.items():
            for d in dsts:
                if depth[d] < depth[src] + 1:
                    depth[d] = depth[src] + 1
                    changed = True
        if not changed:
            break
    layers = {}
    for nid, d in depth.items():
        layers.setdefault(d, []).append(nid)
    return layers


def _validate_spec(spec):
    """Validate the small input contract before layout can discard bad data."""
    if not isinstance(spec, dict):
        raise ValueError("diagram_spec_not_object")
    direction = spec.get("direction", "LR")
    if direction not in ("LR", "TB"):
        raise ValueError(f"diagram_direction_invalid: {direction!r}")
    nodes = spec.get("nodes", [])
    edges = spec.get("edges", [])
    if not isinstance(nodes, list):
        raise ValueError("diagram_nodes_not_array")
    if not nodes:
        raise ValueError("diagram_has_no_nodes")
    node_ids = []
    for node in nodes:
        if (
            not isinstance(node, dict)
            or not isinstance(node.get("id"), str)
            or not node["id"].strip()
        ):
            raise ValueError("diagram_node_invalid")
        if "label" in node and not isinstance(node["label"], str):
            raise ValueError(f"diagram_node_label_invalid: {node['id']!r}")
        node_ids.append(node["id"])
    if len(set(node_ids)) != len(node_ids):
        raise ValueError("diagram_duplicate_node_id")
    if not isinstance(edges, list):
        raise ValueError("diagram_edges_not_array")
    known = set(node_ids)
    adjacency = {node_id: [] for node_id in node_ids}
    for edge in edges:
        if (
            not isinstance(edge, dict)
            or not isinstance(edge.get("from"), str)
            or not isinstance(edge.get("to"), str)
        ):
            raise ValueError("diagram_edge_invalid")
        source, target = edge["from"], edge["to"]
        if source not in known or target not in known:
            raise ValueError(f"diagram_edge_unknown_node: {source!r}->{target!r}")
        if "label" in edge and edge["label"] is not None and not isinstance(edge["label"], str):
            raise ValueError("diagram_edge_label_invalid")
        adjacency[source].append(target)
    # A cyclic graph has no finite dependency layering; reject it explicitly.
    indegree = {node_id: 0 for node_id in node_ids}
    for targets in adjacency.values():
        for target in targets:
            indegree[target] += 1
    queue = [node_id for node_id in node_ids if indegree[node_id] == 0]
    visited = 0
    while queue:
        source = queue.pop(0)
        visited += 1
        for target in adjacency[source]:
            indegree[target] -= 1
            if indegree[target] == 0:
                queue.append(target)
    if visited != len(node_ids):
        raise ValueError("diagram_cycle")


def render(spec, out_path):
    from PIL import Image, ImageDraw

    _validate_spec(spec)
    direction = spec.get("direction", "LR")
    nodes = spec.get("nodes", [])
    edges = spec.get("edges", [])
    if not nodes:
        raise ValueError("diagram_has_no_nodes")
    layers = _layers(nodes, edges)
    labels = {n["id"]: n.get("label", n["id"]) for n in nodes}

    img = Image.new("RGBA", (W, H), BG)
    d = ImageDraw.Draw(img)
    f_node = _load_font(FONT_SIZES["node"])
    f_edge = _load_font(FONT_SIZES["edge"])
    f_title = _load_font(FONT_SIZES["title"])

    n_layers, n_cols = len(layers), max(len(v) for v in layers.values())
    if direction == "TB":
        col_w, row_h = (W - 2 * PAD) / max(1, n_cols), (H - 2 * PAD) / max(1, n_layers)
    else:
        col_w, row_h = (W - 2 * PAD) / max(1, n_layers), (H - 2 * PAD) / max(1, n_cols)

    def node_box(nid):
        layer_idx = next(i for i, ls in enumerate(sorted(layers)) if nid in layers[ls])
        pos_in_layer = layers[sorted(layers)[layer_idx]].index(nid)
        if direction == "TB":
            cx = PAD + col_w * pos_in_layer + col_w / 2
            cy = PAD + row_h * layer_idx + row_h / 2
        else:
            cx = PAD + col_w * layer_idx + col_w / 2
            cy = PAD + row_h * pos_in_layer + row_h / 2
        return cx - NODE_W / 2, cy - NODE_H / 2, cx + NODE_W / 2, cy + NODE_H / 2

    def edge_anchor(nid, side):
        x0, y0, x1, y1 = node_box(nid)
        if direction == "TB":
            return ((x0 + x1) / 2, y1) if side == "out" else ((x0 + x1) / 2, y0)
        return (x1, (y0 + y1) / 2) if side == "out" else (x0, (y0 + y1) / 2)

    for e in edges:
        p0 = edge_anchor(e["from"], "out")
        p1 = edge_anchor(e["to"], "in")
        d.line([p0, p1], fill=ARROW, width=6)
        vx, vy = p1[0] - p0[0], p1[1] - p0[1]
        import math
        ln = max(1.0, math.hypot(vx, vy))
        ux, uy = vx / ln, vy / ln
        head = 26
        d.polygon([p1,
                   (p1[0] - ux * head - uy * head * 0.5, p1[1] - uy * head + ux * head * 0.5),
                   (p1[0] - ux * head + uy * head * 0.5, p1[1] - uy * head - ux * head * 0.5)],
                  fill=ARROW)
        if e.get("label"):
            mx, my = (p0[0] + p1[0]) / 2, (p0[1] + p1[1]) / 2
            if f_edge:
                d.text((mx, my - 18), e["label"], fill=ARROW, font=f_edge, anchor="mm")

    for nid in labels:
        x0, y0, x1, y1 = node_box(nid)
        d.rounded_rectangle([x0, y0, x1, y1], radius=18, fill=NODE_FILL,
                            outline=NODE_LINE, width=4)
        if f_node:
            d.text(((x0 + x1) / 2, (y0 + y1) / 2), labels[nid], fill=TEXT,
                   font=f_node, anchor="mm")

    if spec.get("title") and f_title:
        d.text((PAD, 40), spec["title"], fill=NODE_LINE, font=f_title)

    img.convert("RGB").save(out_path, "PNG")
    return len(nodes), len(edges)


def main():
    if len(sys.argv) != 3:
        print("usage: diagram_render.py <diagram.json> <out.png>", file=sys.stderr)
        return 2
    try:
        spec = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        print(f"diagram_input_invalid: {exc}", file=sys.stderr)
        return 2
    try:
        n, e = render(spec, sys.argv[2])
    except Exception as exc:  # noqa: BLE001
        print(f"diagram_render_failed: {exc}", file=sys.stderr)
        return 3
    print(f"OK: nodes={n} edges={e} -> {sys.argv[2]}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
