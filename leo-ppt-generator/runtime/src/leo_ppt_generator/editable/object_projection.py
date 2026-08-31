"""Structural projection of a PPTX package (F3-T1).

The projection reduces a .pptx to a normalized, order-sensitive dict that both
the legacy builder and the object builder products can be compared on — this
is the assertion substrate for the migration equivalence suite and will be
reused by the object-level diff (F3-T4). It is deliberately host-agnostic:
zipfile + ElementTree only, no python-pptx, so it reads legacy byte packages
exactly the same as object-API packages.

Comparison semantics (not byte comparison):
- objects are listed in spTree document order (z-order);
- custGeom vertices are normalized to the path box (0..1, 5 decimals) so the
  legacy 21600-unit encoding and any equivalent encoding compare equal;
- absent fill/line and ``noFill`` both project to ``"none"`` (the OOXML
  inheritance default for spPr is theme-driven; builders always write
  explicit values, so absence equals none for this contract);
- ``endParaRPr`` and package chrome (template layouts, notes master, extra
  docProps parts) are out of scope by design.
"""

from __future__ import annotations

import hashlib
import io
import re
import zipfile
from pathlib import Path

NS = {
    "a": "http://schemas.openxmlformats.org/drawingml/2006/main",
    "p": "http://schemas.openxmlformats.org/presentationml/2006/main",
    "r": "http://schemas.openxmlformats.org/officeDocument/2006/relationships",
    "rel": "http://schemas.openxmlformats.org/package/2006/relationships",
}

SLIDE_RE = re.compile(r"^ppt/slides/slide(\d+)\.xml$")
_NOTES_RE = re.compile(r"^ppt/notesSlides/notesSlide(\d+)\.xml$")


def _q(tag: str) -> str:
    prefix, local = tag.split(":")
    return f"{{{NS[prefix]}}}{local}"


def _slide_sort_key(name: str) -> int:
    match = SLIDE_RE.match(name)
    return int(match.group(1)) if match else 0


def _hash_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _color_of(element):
    if element is None:
        return "none"
    srgb = element.find(_q("a:srgbClr"))
    if srgb is not None:
        return str(srgb.get("val", "")).upper()
    scheme = element.find(_q("a:schemeClr"))
    if scheme is not None:
        return f"scheme:{scheme.get('val', '')}"
    return "none"


def _fill_projection(spPr):
    if spPr is None:
        return "none"
    return _color_of(spPr.find(_q("a:solidFill")) if spPr.find(_q("a:noFill")) is None else None)


def _line_projection(spPr):
    if spPr is None:
        return {"color": "none", "width_emu": None, "dash": None}
    ln = spPr.find(_q("a:ln"))
    if ln is None or ln.find(_q("a:noFill")) is not None:
        return {"color": "none", "width_emu": None, "dash": None}
    dash = ln.find(_q("a:prstDash"))
    return {
        "color": _color_of(ln.find(_q("a:solidFill"))),
        "width_emu": int(ln.get("w")) if ln.get("w") is not None else None,
        "dash": dash.get("val") if dash is not None else None,
    }


def _geometry_projection(spPr):
    if spPr is None:
        return {"prst": None}
    prst = spPr.find(_q("a:prstGeom"))
    if prst is not None:
        adjustments = {}
        avLst = prst.find(_q("a:avLst"))
        if avLst is not None:
            for gd in avLst.findall(_q("a:gd")):
                adjustments[gd.get("name", "")] = gd.get("fmla", "")
        return {"prst": prst.get("prst"), "adj": adjustments}
    cust = spPr.find(_q("a:custGeom"))
    if cust is None:
        return {"prst": None}
    vertices = []
    for path in cust.findall(f"{_q('a:pathLst')}/{_q('a:path')}"):
        width = float(path.get("w", "1") or 1)
        height = float(path.get("h", "1") or 1)
        for segment in path:
            local = segment.tag.split("}")[1]
            if local not in ("moveTo", "lnTo"):
                continue
            point = segment.find(_q("a:pt"))
            if point is None:
                continue
            vertices.append(
                (round(float(point.get("x", "0")) / width, 5), round(float(point.get("y", "0")) / height, 5))
            )
    return {"prst": "custGeom", "vertices": vertices}


def _run_projection(run) -> dict:
    text = run.find(_q("a:t"))
    rPr = run.find(_q("a:rPr"))
    result = {"text": (text.text or "") if text is not None else ""}
    if rPr is None:
        result.update({"sz": None, "font_latin": None, "font_ea": None, "font_cs": None, "color": "none", "bold": False, "italic": False, "baseline": None})
        return result
    slots = {}
    for tag in ("latin", "ea", "cs"):
        slot = rPr.find(_q(f"a:{tag}"))
        slots[tag] = slot.get("typeface") if slot is not None else None
    result.update(
        {
            "sz": int(rPr.get("sz")) if rPr.get("sz") is not None else None,
            "font_latin": slots["latin"],
            "font_ea": slots["ea"],
            "font_cs": slots["cs"],
            "color": _color_of(rPr.find(_q("a:solidFill"))),
            "bold": rPr.get("b") == "1",
            "italic": rPr.get("i") == "1",
            "baseline": int(rPr.get("baseline")) if rPr.get("baseline") is not None else None,
        }
    )
    return result


def _paragraph_projection(paragraph) -> dict:
    pPr = paragraph.find(_q("a:pPr"))
    runs = [_run_projection(run) for run in paragraph.findall(_q("a:r"))]
    return {"align": pPr.get("algn") if pPr is not None else None, "runs": runs}


def _body_projection(sp) -> dict | None:
    txBody = sp.find(_q("p:txBody"))
    if txBody is None:
        return None
    bodyPr = txBody.find(_q("a:bodyPr"))
    autofit = None
    if bodyPr is not None:
        for child in bodyPr:
            if child.tag.split("}")[1] in ("spAutoFit", "noAutofit", "normAutofit"):
                autofit = child.tag.split("}")[1]
    return {
        "wrap": bodyPr.get("wrap") if bodyPr is not None else None,
        "anchor": bodyPr.get("anchor") if bodyPr is not None else None,
        "insets_zero": (
            bodyPr is not None
            and all(bodyPr.get(attr) == "0" for attr in ("lIns", "tIns", "rIns", "bIns"))
        )
        if _is_textbox(sp)
        else None,
        "autofit": autofit,
        "paragraphs": [_paragraph_projection(p) for p in txBody.findall(_q("a:p"))],
    }


def _is_textbox(sp) -> bool:
    cNvSpPr = sp.find(f"{_q('p:nvSpPr')}/{_q('p:cNvSpPr')}")
    return cNvSpPr is not None and cNvSpPr.get("txBox") == "1"


def _transform_projection(element) -> dict:
    spPr = element.find(_q("p:spPr"))
    xfrm = None
    if spPr is not None:
        xfrm = spPr.find(_q("a:xfrm"))
    if xfrm is None:
        # graphicFrame carries p:xfrm directly (no spPr wrapper)
        xfrm = element.find(_q("p:xfrm"))
    off = xfrm.find(_q("a:off")) if xfrm is not None else None
    ext = xfrm.find(_q("a:ext")) if xfrm is not None else None
    return {
        "off": [int(off.get("x", "0")), int(off.get("y", "0"))] if off is not None else None,
        "ext": [int(ext.get("cx", "0")), int(ext.get("cy", "0"))] if ext is not None else None,
        "rot": int(xfrm.get("rot")) if xfrm is not None and xfrm.get("rot") is not None else None,
        "flip_h": xfrm.get("flipH") == "1" if xfrm is not None else False,
        "flip_v": xfrm.get("flipV") == "1" if xfrm is not None else False,
    }


def _object_projection(element, rels_by_id) -> dict | None:
    tag = element.tag.split("}")[1]
    name_element = element.find(f".//{_q('p:cNvPr')}")
    name = name_element.get("name", "") if name_element is not None else ""
    base = {"name": name, **_transform_projection(element)}
    if tag == "sp":
        is_text = _is_textbox(element)
        spPr = element.find(_q("p:spPr"))
        base.update(
            {
                "kind": "text" if is_text else "shape",
                "geometry": _geometry_projection(spPr),
                "fill": _fill_projection(spPr),
                "line": _line_projection(spPr),
                "body": _body_projection(element) if is_text else None,
            }
        )
        return base
    if tag == "pic":
        blip = element.find(f"{_q('p:blipFill')}/{_q('a:blip')}")
        embed = blip.get(f"{{{NS['r']}}}embed") if blip is not None else None
        target = rels_by_id.get(embed, "")
        base.update({"kind": "image", "media_part": target.rsplit("/", 1)[-1]})
        return base
    if tag == "graphicFrame":
        table = element.find(f".//{_q('a:tbl')}")
        if table is not None:
            grid = [int(col.get("w", "0")) for col in table.findall(f"{_q('a:tblGrid')}/{_q('a:gridCol')}")]
            rows = []
            for tr in table.findall(_q("a:tr")):
                rows.append(
                    [
                        "".join(t.text or "" for t in tc.findall(f".//{_q('a:t')}"))
                        for tc in tr.findall(_q("a:tc"))
                    ]
                )
            base.update({"kind": "table", "grid": grid, "rows": rows})
            return base
        base.update({"kind": "graphicFrame"})
        return base
    if tag == "cxnSp":
        spPr = element.find(_q("p:spPr"))
        base.update(
            {
                "kind": "shape",
                "geometry": _geometry_projection(spPr),
                "fill": _fill_projection(spPr),
                "line": _line_projection(spPr),
                "body": None,
            }
        )
        return base
    return None


def _rels_targets(package: zipfile.ZipFile, slide_name: str) -> dict[str, str]:
    rels_name = f"ppt/slides/_rels/{slide_name.split('/')[-1]}.rels"
    result = {}
    try:
        raw = package.read(rels_name)
    except KeyError:
        return result
    import xml.etree.ElementTree as ET

    root = ET.fromstring(raw)
    for rel in root.findall("rel:Relationship", NS):
        result[rel.get("Id", "")] = rel.get("Target", "")
    return result


def _notes_paragraph_text(xml_bytes: bytes) -> str:
    import xml.etree.ElementTree as ET

    root = ET.fromstring(xml_bytes)
    paragraphs = []
    for paragraph in root.findall(".//a:p", NS):
        text = "".join(node.text or "" for node in paragraph.findall(".//a:t", NS))
        if text:
            paragraphs.append(text)
    return "\n".join(paragraphs)


def _background_projection(slide_root):
    bg = slide_root.find(f"{_q('p:cSld')}/{_q('p:bg')}")
    if bg is None:
        return None
    bgPr = bg.find(_q("p:bgPr"))
    if bgPr is None:
        return None
    return _color_of(bgPr.find(_q("a:solidFill")))


def project_pptx(source: str | Path | bytes) -> dict:
    """Project a PPTX package (path or raw bytes) to its normalized structure."""
    import xml.etree.ElementTree as ET

    if isinstance(source, bytes):
        package = zipfile.ZipFile(io.BytesIO(source))
    else:
        package = zipfile.ZipFile(str(source))
    with package:
        names = package.namelist()
        slide_names = sorted((n for n in names if SLIDE_RE.match(n)), key=_slide_sort_key)
        presentation_root = ET.fromstring(package.read("ppt/presentation.xml"))
        sldSz = presentation_root.find(_q("p:sldSz"))
        notes_by_index = {}
        for name in names:
            match = _NOTES_RE.match(name)
            if match:
                notes_by_index[int(match.group(1))] = _notes_paragraph_text(package.read(name))
        slides = []
        for position, slide_name in enumerate(slide_names, start=1):
            root = ET.fromstring(package.read(slide_name))
            rels_by_id = _rels_targets(package, slide_name)
            spTree = root.find(f"{_q('p:cSld')}/{_q('p:spTree')}")
            objects = []
            if spTree is not None:
                for element in spTree:
                    local = element.tag.split("}")[1]
                    if local in ("nvGrpSpPr", "grpSpPr"):
                        continue
                    projection = _object_projection(element, rels_by_id)
                    if projection is not None:
                        objects.append(projection)
            notes_text = notes_by_index.get(position)
            slides.append(
                {
                    "objects": objects,
                    "background": _background_projection(root),
                    "notes_text_sha256": _hash_text(notes_text) if notes_text is not None else None,
                }
            )
        media_hashes = sorted(
            hashlib.sha256(package.read(name)).hexdigest() for name in names if name.startswith("ppt/media/")
        )
        return {
            "slides": slides,
            "slide_size_emu": [int(sldSz.get("cx", "0")), int(sldSz.get("cy", "0"))] if sldSz is not None else None,
            "media_hash_multiset": media_hashes,
        }
