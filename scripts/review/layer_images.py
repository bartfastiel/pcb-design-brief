"""One PNG per board layer for a review document (brief §12.5): each layer shows only its own content, coloured
by presence (mask green, copper copper-coloured, core ochre, silkscreen dark grey, white elsewhere) on a light grey
board outline. All images share one frame, seen from the top; bottom silkscreen also comes as a readable mirror.
Needs kicad-cli, pymupdf, pillow, numpy."""
import argparse
import json
import os
import re
import subprocess
import sys
import tempfile

import numpy as np
import pymupdf
from PIL import Image, ImageDraw, ImageFilter

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "kicad"))
from check import find_cli  # noqa: E402

COLOURS = {"copper": (205, 133, 63), "mask": (46, 139, 87), "core": (204, 160, 60), "silk": (70, 70, 70),
           "outline": (190, 190, 190)}
LAYERS = ["F.Cu", "B.Cu", "F.Mask", "B.Mask", "F.SilkS", "B.SilkS", "Edge.Cuts"]
STACK = [("1-silk-top", "F.SilkS", "silk"), ("2-mask-top", "F.Mask", "mask"), ("3-copper-top", "F.Cu", "copper"),
         ("4-core", None, "core"), ("5-copper-bottom", "B.Cu", "copper"), ("6-mask-bottom", "B.Mask", "mask"),
         ("7-silk-bottom", "B.SilkS", "silk")]


def export_svgs(cli, board, out):
    for layer in LAYERS:
        subprocess.run([cli, "pcb", "export", "svg", "--mode-single", "--page-size-mode", "0", "--exclude-drawing-sheet",
                        "--drill-shape-opt", "0", "--layers", layer, "-o", os.path.join(out, layer + ".svg"), board],
                       check=True, capture_output=True)


def export_holes(cli, board, out):
    """Drill files carry every hole with its real size; coordinates in mm, absolute, y pointing up."""
    subprocess.run([cli, "pcb", "export", "drill", "--format", "excellon", "--drill-origin", "absolute",
                    "--excellon-units", "mm", "--excellon-separate-th", "--generate-map", "--map-format", "svg",
                    "-o", out + os.sep, board], check=True, capture_output=True)
    holes = []
    for name in os.listdir(out):
        if not name.lower().endswith(".drl"):
            continue
        plated = "NPTH" not in name.upper()
        tools, size = {}, 0.0
        for line in open(os.path.join(out, name), encoding="ascii", errors="ignore"):
            line = line.strip()
            m = re.match(r"T(\d+)C([\d.]+)", line)
            if m:
                tools[m.group(1)] = float(m.group(2))
                continue
            m = re.fullmatch(r"T(\d+)", line)
            if m:
                size = tools.get(m.group(1), 0.0)
                continue
            coords = re.findall(r"X(-?[\d.]+)Y(-?[\d.]+)", line)
            if coords:
                points = [(float(x), -float(y)) for x, y in coords]
                holes.append({"points": points, "d": size, "plated": plated})
    return holes


class Frame:
    def __init__(self, svg_dir, scale, pad):
        doc = pymupdf.open(os.path.join(svg_dir, "Edge.Cuts.svg"))
        self.page_w, self.page_h = doc[0].rect.width, doc[0].rect.height
        self.scale, self.pad = scale, pad
        edge = self.raster(svg_dir, "Edge.Cuts", crop=False)
        x0, y0, x1, y1 = edge.getbbox()
        p = int(pad * scale)
        self.box = (x0 - p, y0 - p, x1 + p, y1 + p)

    def raster(self, svg_dir, layer, crop=True):
        doc = pymupdf.open(os.path.join(svg_dir, layer + ".svg"))
        k = self.scale * 25.4 / 72
        pix = doc[0].get_pixmap(matrix=pymupdf.Matrix(k, k), alpha=True)
        alpha = Image.frombytes("RGBA", (pix.width, pix.height), pix.samples).getchannel("A")
        alpha = alpha.point(lambda v: 255 if v > 24 else 0)
        return alpha.crop(self.box) if crop else alpha

    def px(self, x, y):
        return x * self.scale - self.box[0], y * self.scale - self.box[1]

    @property
    def size(self):
        return self.box[2] - self.box[0], self.box[3] - self.box[1]


def mask_and(a, b_not):
    return Image.fromarray(np.where((np.array(a) > 0) & (np.array(b_not) == 0), 255, 0).astype("uint8"))


def build(board, out_dir, scale, pad, cli, readable_flip="lr"):
    os.makedirs(out_dir, exist_ok=True)
    work = tempfile.mkdtemp()
    export_svgs(cli, board, work)
    holes = export_holes(cli, board, work)
    frame = Frame(work, scale, pad)
    w, h = frame.size
    layers = {name: frame.raster(work, name) for name in LAYERS}

    edge = layers["Edge.Cuts"]
    fill = edge.copy()
    ImageDraw.floodfill(fill, (0, 0), 128)
    inside = fill.point(lambda v: 255 if v != 128 else 0)
    drilled = Image.new("L", (w, h), 0)
    ring = Image.new("L", (w, h), 0)
    dd, rd = ImageDraw.Draw(drilled), ImageDraw.Draw(ring)
    for hole in holes:
        r = hole["d"] / 2 * scale
        pts = [frame.px(x, y) for x, y in hole["points"]]
        for cx, cy in pts:
            dd.ellipse([cx - r, cy - r, cx + r, cy + r], fill=255)
            if hole["plated"]:
                rd.ellipse([cx - r - 3, cy - r - 3, cx + r + 3, cy + r + 3], fill=255)
        if len(pts) == 2:
            dd.line(pts, fill=255, width=int(2 * r))
    ring = mask_and(ring, drilled)
    board_area = mask_and(inside, drilled)
    outline = mask_and(edge, drilled.filter(ImageFilter.MaxFilter(9)))

    def solid(mask, colour):
        img = Image.new("RGBA", (w, h), colour + (0,))
        img.putalpha(mask)
        return img

    written = {}
    for name, layer, kind in STACK:
        if kind == "core":
            img = solid(board_area, COLOURS["core"])
            img.alpha_composite(solid(ring, COLOURS["copper"]))
        elif kind == "mask":
            img = solid(mask_and(board_area, layers[layer]), COLOURS["mask"])
        else:
            img = solid(mask_and(layers[layer], drilled), COLOURS[kind])
        page = Image.new("RGBA", (w, h), (255, 255, 255, 255))
        page.alpha_composite(solid(outline, COLOURS["outline"]))
        page.alpha_composite(img)
        img.save(os.path.join(out_dir, name + ".rgba.png"))
        page.convert("RGB").save(os.path.join(out_dir, name + ".png"))
        written[name] = {"layer": layer, "kind": kind}
    readable = Image.open(os.path.join(out_dir, "7-silk-bottom.png")).transpose(Image.FLIP_LEFT_RIGHT if readable_flip == "lr" else Image.FLIP_TOP_BOTTOM)
    readable.save(os.path.join(out_dir, "7-silk-bottom-readable.png"))
    meta = {"px_per_mm": scale, "size_px": [w, h], "origin_mm": [frame.box[0] / scale, frame.box[1] / scale],
            "holes": len(holes), "layers": written}
    with open(os.path.join(out_dir, "layers.json"), "w", encoding="utf-8") as handle:
        json.dump(meta, handle, indent=1)
    return meta


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("board", help=".kicad_pcb")
    parser.add_argument("out_dir")
    parser.add_argument("--scale", type=float, default=20, help="pixels per mm, default %(default)s")
    parser.add_argument("--pad", type=float, default=1.0, help="margin around the board in mm, default %(default)s")
    parser.add_argument("--readable-flip", choices=["lr", "tb"], default="lr",
                        help="axis to mirror the bottom silkscreen so it reads: lr if its text runs along the "
                             "board when turned over sideways, tb if turned over end to end")
    parser.add_argument("--kicad-cli")
    args = parser.parse_args()
    meta = build(args.board, args.out_dir, args.scale, args.pad, find_cli(args.kicad_cli), args.readable_flip)
    print(f"{len(meta['layers'])} layers, {meta['holes']} holes, {meta['size_px'][0]} x {meta['size_px'][1]} px")


if __name__ == "__main__":
    main()
