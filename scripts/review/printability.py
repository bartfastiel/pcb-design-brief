"""FDM printability check of parts in their print orientation (brief §9a, rules FDM-1 … FDM-7).

Per part it checks overhangs steeper than the limit, bridges longer than the limit, floating islands (a layer region
with nothing below it), features thinner than the minimum width in any layer (walls, ribs, text strokes) and the bed
contact. It writes report.json (pass/fail with locations) and one image per part: four views with every downward
face coloured by what the printer has to do there, plus the layer with the worst thin features.
Needs trimesh, shapely, numpy, pillow. STL in mm, print orientation as stored (z up, bed at the lowest point)."""
import argparse
import json
import math
import os

import numpy as np
import shapely
import trimesh
from PIL import Image, ImageDraw, ImageFont
from shapely.geometry import MultiPolygon, Polygon
from shapely.ops import unary_union

COLOURS = {"ok": (175, 180, 188), "bed": (70, 120, 200), "overhang": (200, 30, 40), "bridge": (240, 150, 30),
           "long_bridge": (150, 30, 160), "top": (210, 214, 220)}
VIEWS = [("front left", (-1, -1, 0.8)), ("front right", (1, -1, 0.8)), ("back", (0.3, 1, 0.7)),
         ("from below, bed face hidden", (0.4, -0.5, -1))]


class Limits:
    layer = 0.2
    overhang_deg = 45.0
    bridge = 10.0
    min_width = 0.8
    thin_area = 0.05
    island_area = 0.3
    bed_share = 0.15


def font(size):
    for name in ("arial.ttf", "DejaVuSans.ttf", "LiberationSans-Regular.ttf"):
        try:
            return ImageFont.truetype(name, size)
        except OSError:
            continue
    return ImageFont.load_default(size=size)


def classify_faces(mesh, lim):
    nz = mesh.face_normals[:, 2]
    z = mesh.triangles_center[:, 2]
    limit = -math.sin(math.radians(90 - lim.overhang_deg)) - 1e-3
    kind = np.full(len(mesh.faces), "ok", dtype=object)
    kind[nz > 0.98] = "top"
    downward = nz < limit
    flat = nz < -0.98
    kind[downward & ~flat] = "overhang"
    kind[flat] = "bridge"
    kind[flat & (z < lim.layer * 0.5)] = "bed"
    return kind


def strands(poly, held, step=0.3):
    """Best bridging direction: the share of strands across the region that end on supported edges at both ends,
    and the longest of those strands."""
    best = (0.0, 0.0)
    minx, miny, maxx, maxy = poly.bounds
    reach = math.hypot(maxx - minx, maxy - miny)
    cx, cy = (minx + maxx) / 2, (miny + maxy) / 2
    anchor = held.buffer(0.35)
    for deg in range(0, 180, 15):
        a = math.radians(deg)
        dx, dy, nx, ny = math.cos(a), math.sin(a), -math.sin(a), math.cos(a)
        total = good = 0
        longest = 0.0
        for k in np.arange(-reach / 2, reach / 2, step):
            line = shapely.LineString([(cx + nx * k - dx * reach, cy + ny * k - dy * reach),
                                       (cx + nx * k + dx * reach, cy + ny * k + dy * reach)])
            cut = poly.intersection(line)
            for seg in getattr(cut, "geoms", [cut]):
                if seg.is_empty or seg.geom_type != "LineString" or seg.length < 0.05:
                    continue
                total += 1
                ends = [shapely.Point(seg.coords[0]), shapely.Point(seg.coords[-1])]
                if all(anchor.contains(e) for e in ends):
                    good += 1
                    longest = max(longest, seg.length)
        if total and good / total > best[0]:
            best = (good / total, longest)
    return best


def bridge_spans(mesh, kind, lim, stack):
    """Flat downward regions per height. If strands in one direction can end on supported edges at both ends it is a
    bridge with that strand length; otherwise it is a ledge, which needs support once it is wider than min_width."""
    spans = []
    idx = np.nonzero(kind == "bridge")[0]
    heights = np.round(mesh.triangles_center[idx, 2], 2)
    zs = np.array([h for h, _ in stack])
    for h in np.unique(heights):
        tris = [Polygon(mesh.triangles[i][:, :2]) for i in idx[heights == h]]
        region = unary_union([t.buffer(1e-4) for t in tris if t.area > 1e-9])
        below = stack[int(np.searchsorted(zs, h)) - 1][1] if h > lim.layer else Polygon()
        for poly in getattr(region, "geoms", [region]):
            if poly.is_empty:
                continue
            held = poly.boundary.intersection(below.buffer(0.3)) if not below.is_empty else shapely.LineString()
            share, length = strands(poly, held)
            ledge = share < 0.9
            width = 2 * shapely.maximum_inscribed_circle(poly, 0.05).length
            span = width if ledge else length
            spans.append({"z": float(h), "span": round(span, 2), "ledge": ledge, "area": round(poly.area, 2),
                          "at": [round(poly.centroid.x, 1), round(poly.centroid.y, 1)], "poly": poly,
                          "fail": span > (lim.min_width if ledge else lim.bridge)})
    for span in spans:
        if span["fail"]:
            mark = "overhang" if span["ledge"] else "long_bridge"
            for i in idx:
                c = mesh.triangles_center[i]
                if abs(c[2] - span["z"]) < 0.006 and span["poly"].buffer(0.01).contains(shapely.Point(c[0], c[1])):
                    kind[i] = mark
    return [s for s in spans if not s["ledge"]], [s for s in spans if s["ledge"] and s["fail"]]


def layers(mesh, lim):
    top = mesh.bounds[1][2]
    heights = np.arange(lim.layer / 2, top, lim.layer)
    sections = mesh.section_multiplane(plane_origin=[0, 0, 0], plane_normal=[0, 0, 1], heights=heights)
    result = []
    for h, sec in zip(heights, sections):
        if sec is None:
            result.append((h, Polygon()))
            continue
        polys = [p for p in sec.polygons_full if p.is_valid and p.area > 1e-6]
        result.append((h, unary_union(polys) if polys else Polygon()))
    return result


def as_list(geom):
    if geom.is_empty:
        return []
    return list(geom.geoms) if isinstance(geom, MultiPolygon) else [geom]


def layer_checks(stack, lim):
    islands, thin = [], []
    reach = lim.layer * math.tan(math.radians(lim.overhang_deg))
    previous = None
    for h, region in stack:
        if previous is not None:
            below = previous.buffer(reach + 0.05)
            for poly in as_list(region):
                if poly.area >= lim.island_area and not poly.intersects(below):
                    islands.append({"z": round(float(h), 2), "area": round(poly.area, 2),
                                    "at": [round(poly.centroid.x, 1), round(poly.centroid.y, 1)]})
        if not region.is_empty:
            opened = region.buffer(-lim.min_width / 2, join_style="mitre").buffer(lim.min_width / 2, join_style="mitre")
            lost = region.difference(opened.buffer(0.02))
            parts = [p for p in as_list(lost) if p.area >= lim.thin_area]
            if parts:
                thin.append({"z": round(float(h), 2), "area": round(sum(p.area for p in parts), 2), "geom": parts,
                             "at": [round(parts[0].centroid.x, 1), round(parts[0].centroid.y, 1)]})
        previous = region
    return islands, thin


def project(points, direction):
    d = np.asarray(direction, float)
    d /= np.linalg.norm(d)
    up = np.array([0, 0, 1.0]) - np.dot([0, 0, 1.0], d) * d
    if np.linalg.norm(up) < 1e-6:
        up = np.array([0, 1.0, 0])
    up /= np.linalg.norm(up)
    right = np.cross(up, d)
    return np.column_stack([points @ right, points @ up, points @ d])


def render(mesh, kind, direction, size):
    tri = mesh.triangles
    flat = tri.reshape(-1, 3)
    p = project(flat, direction).reshape(-1, 3, 3)
    lo, hi = p[:, :, :2].reshape(-1, 2).min(axis=0), p[:, :, :2].reshape(-1, 2).max(axis=0)
    scale = (size - 20) / max(hi - lo)
    img = Image.new("RGB", (int((hi[0] - lo[0]) * scale) + 20, int((hi[1] - lo[1]) * scale) + 20), (255, 255, 255))
    draw = ImageDraw.Draw(img)
    d = np.asarray(direction, float) / np.linalg.norm(direction)
    facing = mesh.face_normals @ d > 0
    order = np.argsort(p[:, :, 2].mean(axis=1))
    hide_bed = direction[2] < 0
    for i in order:
        if not facing[i] or (hide_bed and kind[i] == "bed"):
            continue
        pts = [((x - lo[0]) * scale + 10, img.height - ((y - lo[1]) * scale + 10)) for x, y, _ in p[i]]
        shade = 0.55 + 0.45 * abs(float(mesh.face_normals[i] @ d))
        draw.polygon(pts, fill=tuple(int(c * shade) for c in COLOURS[kind[i]]))
    return img


def thin_map(stack, thin, size):
    worst = max(thin, key=lambda t: t["area"])
    region = dict((round(float(h), 2), r) for h, r in stack)[worst["z"]]
    minx, miny, maxx, maxy = region.bounds
    scale = (size - 20) / max(maxx - minx, maxy - miny)
    img = Image.new("RGB", (int((maxx - minx) * scale) + 20, int((maxy - miny) * scale) + 20), (255, 255, 255))
    draw = ImageDraw.Draw(img)

    def pts(poly):
        return [((x - minx) * scale + 10, img.height - ((y - miny) * scale + 10)) for x, y in poly.exterior.coords]

    for poly in as_list(region):
        draw.polygon(pts(poly), fill=(205, 208, 214))
        for hole in poly.interiors:
            draw.polygon(pts(Polygon(hole)), fill=(255, 255, 255))
    for poly in worst["geom"]:
        draw.polygon(pts(poly), fill=COLOURS["overhang"])
    return img, worst["z"]


def check_part(name, path, lim, out_dir, size):
    mesh = trimesh.load(path, force="mesh")
    mesh.merge_vertices()
    mesh.apply_translation([0, 0, -mesh.bounds[0][2]])
    mesh = trimesh.Trimesh(*trimesh.remesh.subdivide_to_size(mesh.vertices, mesh.faces, 3.0))
    kind = classify_faces(mesh, lim)
    stack = layers(mesh, lim)
    spans, ledges = bridge_spans(mesh, kind, lim, stack)
    islands, thin = layer_checks(stack, lim)
    footprint = unary_union([Polygon(t[:, :2]).buffer(1e-4) for t in mesh.triangles if Polygon(t[:, :2]).area > 1e-9])
    bed = stack[0][1].area if stack else 0.0
    areas = {k: float(mesh.area_faces[kind == k].sum()) for k in COLOURS}
    result = {
        "overhang": {"pass": areas["overhang"] < 1.0, "area_mm2": round(areas["overhang"], 1),
                     "limit_deg": lim.overhang_deg, "ledges": [{k: v for k, v in s.items() if k != "poly"}
                                                               for s in ledges[:3]]},
        "bridges": {"pass": not any(s["fail"] for s in spans), "limit_mm": lim.bridge,
                    "longest": max([{k: v for k, v in s.items() if k != "poly"} for s in spans],
                                   key=lambda s: s["span"], default=None)},
        "islands": {"pass": not islands, "count": len(islands), "first": islands[:3]},
        "thin": {"pass": not thin, "limit_mm": lim.min_width, "layers": len(thin),
                 "worst": [{k: v for k, v in t.items() if k != "geom"} for t in
                           sorted(thin, key=lambda t: -t["area"])[:3]]},
        "bed": {"pass": bed >= lim.bed_share * footprint.area, "first_layer_mm2": round(bed, 1),
                "footprint_mm2": round(footprint.area, 1)},
    }
    result["pass"] = all(v["pass"] for v in result.values())

    tiles = [(label, render(mesh, kind, d, size)) for label, d in VIEWS]
    if thin:
        img, z = thin_map(stack, thin, size)
        tiles.append((f"thinnest layer z = {z} mm (red: narrower than {lim.min_width} mm)", img))
    f, small = font(26), font(20)
    tw = max(t.width for _, t in tiles)
    th = max(t.height for _, t in tiles) + 40
    cols = 3 if len(tiles) > 4 else 2
    rows = (len(tiles) + cols - 1) // cols
    sheet = Image.new("RGB", (cols * tw, rows * th + 110), (255, 255, 255))
    d = ImageDraw.Draw(sheet)
    verdict = "PASS" if result["pass"] else "FAIL"
    d.text((10, 8), f"{name}: {verdict}", font=f, fill=(0, 120, 0) if result["pass"] else (190, 0, 0))
    x = 10
    for label, key in (("support needed", "overhang"), ("bridge ok", "bridge"),
                       (f"bridge > {lim.bridge:g} mm", "long_bridge"), ("on the bed", "bed")):
        d.rectangle([x, 50, x + 22, 72], fill=COLOURS[key])
        d.text((x + 30, 50), label, font=small, fill=(40, 40, 40))
        x += 60 + int(d.textlength(label, font=small))
    for k, (label, img) in enumerate(tiles):
        cx, cy = (k % cols) * tw, 110 + (k // cols) * th
        d.text((cx + 10, cy + 4), label, font=small, fill=(60, 60, 60))
        sheet.paste(img, (cx, cy + 36))
    image = os.path.join(out_dir, f"{name}.png")
    sheet.save(image)
    result["image"] = image
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("parts", nargs="+", help="name=path.stl in print orientation")
    for key in ("layer", "overhang_deg", "bridge", "min_width", "thin_area", "island_area", "bed_share"):
        parser.add_argument("--" + key.replace("_", "-"), type=float, default=getattr(Limits, key),
                            help=f"default {getattr(Limits, key)}")
    parser.add_argument("--size", type=int, default=520, help="pixels per view, default %(default)s")
    parser.add_argument("-o", "--out", default="printability")
    args = parser.parse_args()
    lim = Limits()
    for key in vars(Limits):
        if not key.startswith("_"):
            setattr(lim, key, getattr(args, key))
    os.makedirs(args.out, exist_ok=True)
    report = {}
    for spec in args.parts:
        name, path = spec.split("=", 1)
        report[name] = check_part(name, path, lim, args.out, args.size)
        r = report[name]
        print(f"{name}: {'PASS' if r['pass'] else 'FAIL'}  overhang {r['overhang']['area_mm2']} mm2, "
              f"longest bridge {r['bridges']['longest']['span'] if r['bridges']['longest'] else 0} mm, "
              f"islands {r['islands']['count']}, thin layers {r['thin']['layers']}, "
              f"bed {r['bed']['first_layer_mm2']} of {r['bed']['footprint_mm2']} mm2")
    with open(os.path.join(args.out, "report.json"), "w", encoding="utf-8") as handle:
        json.dump(report, handle, indent=1)
    raise SystemExit(0 if all(r["pass"] for r in report.values()) else 1)


if __name__ == "__main__":
    main()
