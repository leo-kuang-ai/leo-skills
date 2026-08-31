"""Named oxml escape hatches for the object builder.

Every helper here exists because the python-pptx high-level API cannot express
the legacy manifest contract (three font slots, truncating centipoint math,
byte-identical custGeom encoding, manually managed media parts, theme font
slots, opaque parts like docProps/app.xml). Each call site in
``object_builder.py`` must go through these named functions — no scattered raw
XML string concatenation — and every helper has a corresponding projection
assertion in ``tests/boundary/test_object_builder_equivalence.py``.
"""

from __future__ import annotations

import re
from typing import TYPE_CHECKING, Iterable

from pptx.oxml import parse_xml
from pptx.oxml.ns import nsdecls, nsuri, qn

if TYPE_CHECKING:
    from pptx.opc.package import Part

NS_A = nsuri("a")
DECL_A = nsdecls("a")
DECL_APR = nsdecls("a", "p", "r")


def set_cnvpr_id_name(element, shape_id: int, name: str) -> None:
    """Set ``p:cNvPr`` id/name on any shape-ish element (sp/pic/cxnSp/graphicFrame).

    python-pptx assigns ids lazily and names generically; the manifest contract
    needs the legacy deterministic ``next_id`` sequence and names.
    """
    cnvpr = element.find(".//" + qn("p:cNvPr"))
    if cnvpr is None:
        return
    cnvpr.set("id", str(int(shape_id)))
    cnvpr.set("name", str(name))


def configure_textbox_bodyPr(text_frame, wrap: str, anchor: str, autofit: str) -> None:
    """Force legacy ``a:bodyPr`` semantics on a textbox text frame.

    The high-level API cannot express: zero insets (it has no inset setters),
    the verbatim ``wrap`` authoring token, and the ``noAutofit`` element
    (``auto_size = None`` only removes the element, which the OOXML default
    then reads as square wrap + inherited autofit).
    """
    bodyPr = text_frame._txBody.bodyPr
    bodyPr.set("wrap", str(wrap))
    bodyPr.set("anchor", str(anchor))
    for attr in ("lIns", "tIns", "rIns", "bIns"):
        bodyPr.set(attr, "0")
    for tag in ("a:spAutoFit", "a:noAutofit", "a:normAutofit"):
        for child in bodyPr.findall(qn(tag)):
            bodyPr.remove(child)
    bodyPr.append(parse_xml(f'<a:{autofit} {DECL_A}/>'))


def set_run_sz(run, font_size) -> None:
    """Write ``rPr@sz`` with the legacy truncating centipoint math.

    ``run.font.size = Pt(v)`` rounds instead of truncating and differs from the
    vendored writer on fractional sizes (e.g. 14.3 → 1430 vs 1429).
    """
    rPr = run._r.get_or_add_rPr()
    rPr.set("sz", str(int(float(font_size) * 100)))


def set_run_font_slots(run, typeface: str) -> None:
    """Write ``a:latin``/``a:ea``/``a:cs`` with the same typeface.

    ``run.font.name`` only writes the latin slot; the legacy contract requires
    all three slots to carry the same face so CJK runs render identically.
    """
    rPr = run._r.get_or_add_rPr()
    for tag in ("a:latin", "a:ea", "a:cs"):
        for child in rPr.findall(qn(tag)):
            rPr.remove(child)
        rPr.append(parse_xml(f'<a:{tag[2:]} {DECL_A} typeface="{_xml_escape(typeface)}"/>'))


def set_run_baseline(run, baseline) -> None:
    """Write ``rPr@baseline`` (int per-mille-of-percent, legacy math)."""
    rPr = run._r.get_or_add_rPr()
    rPr.set("baseline", str(int(float(baseline))))


def set_xfrm_flip(element, flip_h: bool, flip_v: bool) -> None:
    """Set ``a:xfrm@flipH/flipV`` (no high-level flip API on autoshapes)."""
    xfrm = element.spPr.find(qn("a:xfrm"))
    if xfrm is None:
        return
    if flip_h:
        xfrm.set("flipH", "1")
    if flip_v:
        xfrm.set("flipV", "1")


def set_connector_fill(element, fill_hex: str | None) -> None:
    """Write the spPr fill of a connector (``Connector`` exposes no ``.fill``)."""
    spPr = element.spPr
    if not fill_hex or fill_hex == "none":
        spPr.append(parse_xml(f'<a:noFill {DECL_A}/>'))
        return
    spPr.append(
        parse_xml(f'<a:solidFill {DECL_A}><a:srgbClr val="{_xml_escape(fill_hex)}"/></a:solidFill>')
    )


def custgeom_xml(points: Iterable[tuple[float, float]], box: list[float] | None) -> str:
    """Replicate the vendored 21600x21600 normalized ``a:custGeom`` encoding.

    ``build_freeform`` uses local-unit path coordinates and recomputes its own
    bounding box; the legacy encoding (path w/h fixed at 21600, vertices
    relative to the source bounding box) is reproduced verbatim instead, which
    keeps the projection and the rendered geometry identical to legacy.
    """
    points = [(float(p[0]), float(p[1])) for p in points]
    if len(points) < 3:
        return ""
    if box and len(box) == 4:
        left, top, width, height = [float(value) for value in box]
    else:
        xs = [p[0] for p in points]
        ys = [p[1] for p in points]
        left, top = min(xs), min(ys)
        width, height = max(xs) - left, max(ys) - top
    width = max(width, 1.0)
    height = max(height, 1.0)

    def rel_coord(point):
        x, y = point
        return int(round((x - left) / width * 21600)), int(round((y - top) / height * 21600))

    first_x, first_y = rel_coord(points[0])
    segments = [f'<a:moveTo><a:pt x="{first_x}" y="{first_y}"/></a:moveTo>']
    for point in points[1:]:
        x, y = rel_coord(point)
        segments.append(f'<a:lnTo><a:pt x="{x}" y="{y}"/></a:lnTo>')
    segments.append("<a:close/>")
    return (
        '<a:custGeom><a:avLst/><a:gdLst/><a:ahLst/><a:cxnLst/>'
        '<a:rect l="l" t="t" r="r" b="b"/>'
        '<a:pathLst><a:path w="21600" h="21600">'
        + "".join(segments)
        + "</a:path></a:pathLst></a:custGeom>"
    )


def replace_geometry_with_custgeom(shape, points, box) -> bool:
    """Swap ``a:prstGeom`` for the legacy ``a:custGeom`` in ``spPr``."""
    xml = custgeom_xml(points, box)
    if not xml:
        return False
    spPr = shape._element.spPr
    prstGeom = spPr.find(qn("a:prstGeom"))
    custgeom = parse_xml(xml.replace("<a:custGeom>", f'<a:custGeom {DECL_A}>', 1))
    if prstGeom is not None:
        prstGeom.addnext(custgeom)
        spPr.remove(prstGeom)
    else:
        xfrm = spPr.find(qn("a:xfrm"))
        xfrm.addnext(custgeom)
    return True


def build_pic_element(shape_id: int, name: str, rel_id: str, left: int, top: int, width: int, height: int):
    """Build a ``p:pic`` bound to a manually managed media relationship.

    ``shapes.add_picture`` routes through the package-level sha1-deduping image
    machinery, which collapses repeated media references into one part; the
    validator's ``image{N}`` media contract requires one part per reference,
    and SVG assets are not supported by ``pptx.image.Image`` at all.
    """
    return parse_xml(
        "<p:pic"
        f" {DECL_APR}>"
        f'<p:nvPicPr><p:cNvPr id="{int(shape_id)}" name="{_xml_escape(name)}"/><p:cNvPicPr/><p:nvPr/></p:nvPicPr>'
        f'<p:blipFill><a:blip r:embed="{rel_id}"/><a:stretch><a:fillRect/></a:stretch></p:blipFill>'
        f'<p:spPr><a:xfrm><a:off x="{int(left)}" y="{int(top)}"/><a:ext cx="{int(width)}" cy="{int(height)}"/></a:xfrm>'
        '<a:prstGeom prst="rect"><a:avLst/></a:prstGeom></p:spPr>'
        "</p:pic>"
    )


def set_sldsz_type(presentation, width_in: float, height_in: float, is_wide: bool) -> None:
    """Rewrite ``p:sldSz@type`` after assigning slide dimensions.

    Setting ``slide_width/slide_height`` only updates cx/cy and leaves the
    template's ``screen4x3`` marker behind.
    """
    sldSz = presentation._element.find(qn("p:sldSz"))
    if sldSz is not None:
        sldSz.set("type", "wide" if is_wide else "custom")


def set_app_xml_application(package, application: str) -> None:
    """Rewrite ``docProps/app.xml`` Application identity.

    app.xml is an opaque blob part with no object API; the builder identity
    (``leo-ppt-generator/<builder-id>``) is what downstream fingerprinting
    reads. String surgery keeps the template bytes otherwise untouched.
    """
    for part in package.iter_parts():
        if str(part.partname) == "/docProps/app.xml":
            part._blob = re.sub(
                rb"<Application>[^<]*</Application>",
                f"<Application>{application}</Application>".encode("utf-8"),
                part.blob,
                count=1,
            )
            return


def set_theme_font_slots(theme_part: "Part", head_face: str | None, body_face: str | None) -> None:
    """Write the ``a:fontScheme`` major/minor double slots (F2-T1).

    python-pptx has no theme editing surface; the slide master's theme part is
    an opaque blob. Slots written: majorFont latin/ea/cs = head, minorFont
    latin/ea/cs = body (script-specific ``a:font`` entries are preserved).
    """
    from lxml import etree

    root = etree.fromstring(theme_part.blob)
    scheme = root.find(f".//{{{NS_A}}}fontScheme")
    if scheme is None:
        return
    for group, face in (("majorFont", head_face), ("minorFont", body_face)):
        if not face:
            continue
        container = scheme.find(f"{{{NS_A}}}{group}")
        if container is None:
            continue
        for tag in ("latin", "ea", "cs"):
            slot = container.find(f"{{{NS_A}}}{tag}")
            if slot is not None:
                slot.set("typeface", str(face))
    body = etree.tostring(root, xml_declaration=True, encoding="UTF-8", standalone=True)
    theme_part._blob = body


def _xml_escape(value) -> str:
    return (
        str(value)
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )
