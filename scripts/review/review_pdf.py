"""Review PDF per brief §12 from a JSON description; every image path is relative to that file.

  python review_pdf.py review.json out.pdf

Sections, each optional: overview, schematic, calculations, board, stack, layers, parts, enclosure, printability,
assembly, instructions. See examples/led-dimmer/review.json for every key. Needs reportlab, pymupdf, pillow."""
import datetime
import json
import os
import sys

import pymupdf
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.lib.utils import ImageReader
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen import canvas
from reportlab.platypus import Paragraph, Table, TableStyle

LINK = "#1a55a8"
P_W, P_H = A4
L_W, L_H = landscape(A4)
M = 14 * mm


def register_fonts():
    for regular, bold in ((r"C:\Windows\Fonts\arial.ttf", r"C:\Windows\Fonts\arialbd.ttf"),
                          ("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
                           "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"),
                          ("/Library/Fonts/Arial.ttf", "/Library/Fonts/Arial Bold.ttf")):
        if os.path.exists(regular) and os.path.exists(bold):
            pdfmetrics.registerFont(TTFont("Body", regular))
            pdfmetrics.registerFont(TTFont("Body-Bold", bold))
            pdfmetrics.registerFontFamily("Body", normal="Body", bold="Body-Bold")
            return "Body", "Body-Bold"
    return "Helvetica", "Helvetica-Bold"


FONT, BOLD = register_fonts()
BODY = ParagraphStyle("body", fontName=FONT, fontSize=10, leading=13.5)
SMALL = ParagraphStyle("small", fontName=FONT, fontSize=8.3, leading=10.8, textColor=colors.HexColor("#333333"))
CELL = ParagraphStyle("cell", fontName=FONT, fontSize=7.6, leading=9.2)
CELL_B = ParagraphStyle("cellb", parent=CELL, fontName=BOLD)
RED = ParagraphStyle("red", parent=SMALL, textColor=colors.HexColor("#b00020"))


class Doc:
    def __init__(self, path, spec, base):
        self.c = canvas.Canvas(path, pagesize=A4)
        self.c.setTitle(spec["title"])
        self.spec, self.base, self.page = spec, base, 0
        self.footer = f"{spec['title']} · {spec.get('footer', 'Review')} · {datetime.date.today().isoformat()}"
        self.vectors = []

    def path(self, rel):
        return os.path.join(self.base, rel)

    def new(self, key, title, land=False):
        if self.page:
            self.c.showPage()
        self.page += 1
        self.w, self.h = (L_W, L_H) if land else (P_W, P_H)
        self.c.setPageSize((self.w, self.h))
        self.c.bookmarkPage(key)
        self.c.addOutlineEntry(title, key, level=0)
        self.c.setFont(BOLD, 15)
        self.c.drawString(M, self.h - M - 3 * mm, title)
        self.c.setFont(FONT, 7.5)
        self.c.setFillColor(colors.grey)
        self.c.drawRightString(self.w - M, M - 7 * mm, f"{self.footer} · page {self.page}")
        self.c.setFillColor(colors.black)
        return self.h - M - 10 * mm

    def para(self, text, x, y, width, style=SMALL):
        p = Paragraph(text, style)
        _, h = p.wrap(width, 1000 * mm)
        p.drawOn(self.c, x, y - h)
        return y - h

    def image(self, rel, x, y_top, width, height):
        reader = ImageReader(self.path(rel))
        iw, ih = reader.getSize()
        s = min(width / iw, height / ih)
        self.c.drawImage(reader, x, y_top - ih * s, iw * s, ih * s, mask="auto")
        return x, y_top - ih * s, iw * s, ih * s

    def table(self, rows, widths, x, y, header=True, extra=()):
        t = Table(rows, colWidths=widths, repeatRows=1 if header else 0)
        t.setStyle(TableStyle([
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("LINEBELOW", (0, 0), (-1, 0), 0.8 if header else 0.25, colors.black),
            ("LINEBELOW", (0, 1), (-1, -1), 0.25, colors.HexColor("#bbbbbb")),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f4f4f4")]),
            ("TOPPADDING", (0, 0), (-1, -1), 1.6), ("BOTTOMPADDING", (0, 0), (-1, -1), 1.6), *extra]))
        _, h = t.wrap(sum(widths), 1000 * mm)
        t.drawOn(self.c, x, y - h)
        return y - h

    def link(self, key, x0, y0, x1, y1):
        self.c.linkRect("", key, (x0, y0, x1, y1), relative=0, thickness=0)


def cells(values, style=CELL):
    return [Paragraph(str(v), style) for v in values]


def url(text, href):
    return f'<link href="{href}" color="{LINK}"><u>{text}</u></link>' if href else text


def overview(d, s):
    y = d.new("overview", s.get("heading", d.spec["title"]), land=True)
    y = d.para(s["text"], M, y, L_W - 2 * M, BODY)
    legend_h = 16 * mm
    x, y0, w, h = d.image(s["image"], M, y - 2 * mm, L_W - 2 * M, y - 2 * mm - M - legend_h)
    info = json.load(open(d.path(s["boxes"]), encoding="utf-8"))
    sx, sy = w / info["size"][0], h / info["size"][1]
    legend = []
    for n, item in enumerate(s["callouts"], 1):
        bx0, by0, bx1, by1 = info["boxes"][item["group"]]
        px0, px1, py0, py1 = x + bx0 * sx, x + bx1 * sx, y0 + h - by1 * sy, y0 + h - by0 * sy
        d.link(item["target"], px0, py0, px1, py1)
        cx, cy = (px0 + px1) / 2, min(py1 + 2.5 * mm, y0 + h - 2 * mm)
        d.c.setFillColor(colors.HexColor(LINK))
        d.c.circle(cx, cy, 2.3 * mm, stroke=0, fill=1)
        d.c.setFillColor(colors.white)
        d.c.setFont(BOLD, 7.5)
        d.c.drawCentredString(cx, cy - 2.6, str(n))
        d.c.setFillColor(colors.black)
        legend.append(f'<b>{n}</b> <a href="#{item["target"]}" color="{LINK}"><u>{item["label"]}</u></a>')
    d.para(" · ".join(legend) + (". " + s["caption"] if s.get("caption") else ""), M, M + legend_h - 4 * mm,
           L_W - 2 * M)


def schematic(d, s):
    d.new("schematic", "Schematic", land=True)
    d.vectors.append((d.page - 1, d.path(s["pdf"])))
    if s.get("caption"):
        d.para(s["caption"], M, M + 4 * mm, L_W - 2 * M)


def calculations(d, s):
    y = d.new("calculations", "Operating points per part", land=True)
    y = d.para(s["text"], M, y, L_W - 2 * M)
    rows = [cells(("Ref", "Function", "Case", "Load", "Limit", "Use", "Verdict"), CELL_B)]
    extra = []
    for i, r in enumerate(s["rows"], 1):
        ok = r["share"] <= r.get("allowed", 0.5)
        rows.append(cells((r["ref"], r["function"], r["case"], r["load"], r["limit"], f"{r['share'] * 100:.0f} %",
                           ("within CI-2" if ok else "above CI-2") + (f"; {r['note']}" if r.get("note") else ""))))
        if not ok:
            extra += [("TEXTCOLOR", (5, i), (6, i), colors.HexColor("#b00020")),
                      ("BACKGROUND", (5, i), (6, i), colors.HexColor("#fde8ea"))]
    y = d.table(rows, [16 * mm, 40 * mm, 38 * mm, 58 * mm, 46 * mm, 16 * mm, 55 * mm], M, y - 3 * mm, extra=extra)
    if s.get("after"):
        d.para(s["after"], M, y - 3 * mm, L_W - 2 * M)


def board(d, s):
    y = d.new("board", "Board, assembled", land=True)
    d.image(s["image"], M, y, L_W - 2 * M, y - M - 10 * mm)
    d.para(s.get("caption", ""), M, M + 7 * mm, L_W - 2 * M)


def stack(d, s, layer_keys):
    y = d.new("stack", "Layer stack")
    info = json.load(open(d.path(s["anchors"]), encoding="utf-8"))
    img_w = (P_W - 2 * M) * 0.6
    x, y0, w, h = d.image(s["image"], M - 4 * mm, y, img_w, y - M - 26 * mm)
    k = w / info["size"][0]
    label_x = M + img_w + 2 * mm
    for name in info["order"]:
        layer = info["layers"][name]
        ax, ay = x + layer["anchor"][0] * k, y0 + h - layer["anchor"][1] * k
        bx0, by0, bx1, by1 = layer["bbox"]
        target = "layer-" + name if name in layer_keys else "stack"
        d.link(target, x + bx0 * k, y0 + h - by1 * k, x + bx1 * k, y0 + h - by0 * k)
        d.c.setLineWidth(0.6)
        d.c.line(ax, ay, label_x - 1.5 * mm, ay)
        d.c.circle(ax, ay, 1.1 * mm, stroke=0, fill=1)
        title, material, props, thick = s["labels"][name]
        d.c.setFont(BOLD, 8.6)
        d.c.setFillColor(colors.HexColor(LINK))
        d.c.drawString(label_x, ay + 1.2 * mm, title)
        d.c.setFillColor(colors.black)
        d.c.setFont(FONT, 7.2)
        d.c.drawString(label_x, ay - 2.2 * mm, f"{material}; {props}")
        d.c.drawString(label_x, ay - 5.2 * mm, f"thickness {thick}")
        d.link(target, label_x, ay - 6 * mm, P_W - M, ay + 4 * mm)
    d.para(s["caption"], M, M + 22 * mm, P_W - 2 * M)


def layers(d, s):
    for start in range(0, len(s), 3):
        y = d.new(f"layers-{start}", "Layers in detail, top to bottom")
        for layer in s[start:start + 3]:
            d.c.bookmarkPage("layer-" + layer["key"], fit="XYZ", top=y + 4 * mm)
            d.c.setFont(BOLD, 11)
            d.c.drawString(M, y, layer["title"])
            yy = d.para(layer["text"], M, y - 2 * mm, P_W - 2 * M)
            width = (P_W - 2 * M) * (0.62 if layer.get("readable") else 1)
            _, by, _, _ = d.image(layer["image"], M, yy - 2 * mm, width, 62 * mm)
            if layer.get("readable"):
                rx = M + width + 4 * mm
                d.image(layer["readable"], rx, yy - 2 * mm, P_W - M - rx, 62 * mm)
                d.c.setFont(FONT, 7)
                d.c.drawString(rx, by - 3 * mm, "readable, board turned over")
            y = by - 9 * mm


def parts(d, s):
    for n, sup in enumerate(s["suppliers"]):
        y = d.new("parts" if n == 0 else f"parts-{n}", f"Parts list: {sup['name']}", land=True)
        y = d.para(sup["heading"], M, y, L_W - 2 * M, BODY)
        rows = [cells(("Ref", "Part", "Data / function", "Order no.", "Series need / stock", "Delivery",
                       "Unit price, net"), CELL_B)]
        for r in sup["rows"]:
            rows.append(cells((r["ref"], url(r["part"], r.get("url")), r["data"], r["order_no"], r["qty"], r["delivery"],
                               r["price"])))
        y = d.table(rows, [17 * mm, 60 * mm, 72 * mm, 30 * mm, 30 * mm, 30 * mm, 30 * mm], M, y - 2 * mm)
        if sup.get("missing"):
            y = d.para(f"<b>Not available at {sup['name']}:</b> {sup['missing']}", M, y - 3 * mm, L_W - 2 * M, RED)
        if sup.get("note"):
            d.para(sup["note"], M, y - 2 * mm, L_W - 2 * M)
    if s.get("special"):
        y = d.new("parts-special", "Parts list: special parts, PCB, enclosure material", land=True)
        for block in s["special"]:
            y = d.para(block, M, y, L_W - 2 * M) - 2.5 * mm


def enclosure(d, s):
    y = d.new("enclosure", "Enclosure, technical drawing", land=True)
    d.image(s["drawing"], M, y, L_W - 2 * M, y - M - 2 * mm)
    y = d.new("enclosure-2", "Enclosure: fasteners, material, heat, radio", land=True)
    col = (L_W - 2 * M - 8 * mm) / 2
    yl = y
    for text in s["left"]:
        yl = d.para(text, M, yl, col) - 2.5 * mm
    yr = y
    for text in s["right"]:
        yr = d.para(text, M + col + 8 * mm, yr, col) - 2.5 * mm


def printability(d, s):
    y = d.new("printability", "Enclosure: printability (FDM)", land=True)
    report = json.load(open(d.path(s["report"]), encoding="utf-8"))
    names = list(report)
    col = (L_W - 2 * M - 6 * mm * (len(names) - 1)) / max(len(names), 1)
    for k, name in enumerate(names):
        d.image(os.path.join(os.path.dirname(s["report"]), name + ".png"), M + k * (col + 6 * mm), y, col, 115 * mm)
    yy = y - 120 * mm
    for name, r in report.items():
        bridge = r["bridges"]["longest"]
        yy = d.para(
            f"<b>{name}: {'PASS' if r['pass'] else 'FAIL'}</b> – overhang beyond {r['overhang']['limit_deg']:g}°: "
            f"{r['overhang']['area_mm2']} mm²; longest bridge {bridge['span'] if bridge else 0} mm "
            f"(limit {r['bridges']['limit_mm']:g}); islands {r['islands']['count']}; layers with features below "
            f"{r['thin']['limit_mm']} mm: {r['thin']['layers']}; first layer {r['bed']['first_layer_mm2']} of "
            f"{r['bed']['footprint_mm2']} mm².", M, yy, L_W - 2 * M) - 1.5 * mm
    if s.get("caption"):
        d.para(s["caption"], M, yy - 1 * mm, L_W - 2 * M)


def assembly(d, s):
    y = d.new("assembly", "Enclosure: virtual assembly", land=True)
    col = (L_W - 2 * M) * 0.6
    d.image(s["views"], M, y, col, y - M - 4 * mm)
    report = json.load(open(d.path(s["report"]), encoding="utf-8"))
    xr, wr = M + col + 6 * mm, L_W - M - (M + col + 6 * mm)
    rows = report["intersections"]
    yy = d.para(f"<b>Intersections:</b> {len(rows)} pairs checked, {sum(r['pass'] for r in rows)} pass.", xr, y, wr)
    data = [cells(("Pair", "Volume", "Result"), CELL_B)]
    for r in rows:
        data.append(cells((f"{r['a']} / {r['b']}", f"{r['volume_mm3']} mm³",
                           "allowed" if r["allowed"] else ("pass" if r["pass"] else "FAIL"))))
    yy = d.table(data, [wr * 0.5, wr * 0.22, wr * 0.28], xr, yy - 2 * mm)
    share = ", ".join(f"{k} {v * 100:.1f} %" for k, v in report["red_share"].items())
    yy = d.para(f"<b>Closure views:</b> inward-facing surfaces in red; visible red per view: {share}.", xr, yy - 3 * mm, wr)
    for text in s.get("text", []):
        yy = d.para(text, xr, yy - 3 * mm, wr)


def instructions(d, s):
    y = d.new("instructions", "Instructions")
    for block in s:
        d.c.setFont(BOLD, 11)
        d.c.drawString(M, y, block["title"])
        y -= 2 * mm
        for item in block["items"]:
            y = d.para("• " + item, M + 3 * mm, y, P_W - 2 * M - 3 * mm) - 1.2 * mm
        y -= 4 * mm


def place_vectors(path, vectors):
    doc = pymupdf.open(path)
    for index, pdf in vectors:
        page = doc[index]
        src = pymupdf.open(pdf)
        r = page.rect
        page.show_pdf_page(pymupdf.Rect(M * 0.6, M + 6 * mm, r.width - M * 0.6, r.height - M - 6 * mm), src, 0)
    doc.save(path + ".tmp", garbage=3, deflate=True)
    doc.close()
    os.replace(path + ".tmp", path)


def main():
    spec_path, out = sys.argv[1], sys.argv[2]
    spec = json.load(open(spec_path, encoding="utf-8"))
    d = Doc(out, spec, os.path.dirname(os.path.abspath(spec_path)))
    layer_keys = [layer["key"] for layer in spec.get("layers", [])]
    for key, fn in (("overview", overview), ("schematic", schematic), ("calculations", calculations),
                    ("board", board)):
        if key in spec:
            fn(d, spec[key])
    if "stack" in spec:
        stack(d, spec["stack"], layer_keys)
    for key, fn in (("layers", layers), ("parts", parts), ("enclosure", enclosure), ("printability", printability),
                    ("assembly", assembly), ("instructions", instructions)):
        if key in spec:
            fn(d, spec[key])
    d.c.save()
    place_vectors(out, d.vectors)
    print(out)


if __name__ == "__main__":
    main()
