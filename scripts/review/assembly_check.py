"""Virtual assembly check of an enclosure (brief AC-2, AC-4). Input: meshes already placed in the assembled
position. Output: pairwise intersection volumes, and six orthographic views in which every part has its own
colour and every inward-facing surface is signal red (a ray along its normal hits any part). In a closed,
flush enclosure red shows only at planned openings. Needs trimesh, manifold3d, numpy, pillow."""
import argparse
import colorsys
import itertools
import json
import os

import manifold3d as m3d
import numpy as np
import trimesh
from PIL import Image, ImageDraw, ImageFont

RED = (160, 33, 40)
VIEWS = {
    "top": (np.array([0, 0, -1]), (0, 1)),
    "bottom": (np.array([0, 0, 1]), (0, 1)),
    "front": (np.array([0, 1, 0]), (0, 2)),
    "back": (np.array([0, -1, 0]), (0, 2)),
    "left": (np.array([1, 0, 0]), (1, 2)),
    "right": (np.array([-1, 0, 0]), (1, 2)),
}


def palette(n):
    hues = [(0.07 + i * 0.618) % 1.0 for i in range(n)]
    hues = [h if not (h < 0.05 or h > 0.93) else (h + 0.3) % 1.0 for h in hues]
    return [tuple(int(255 * c) for c in colorsys.hsv_to_rgb(h, 0.65, 0.85)) for h in hues]


def to_manifold(mesh):
    return m3d.Manifold(m3d.Mesh(vert_properties=np.asarray(mesh.vertices, dtype=np.float32),
                                 tri_verts=np.asarray(mesh.faces, dtype=np.uint32)))


def intersections(meshes, allowed):
    solids = {name: to_manifold(mesh) for name, mesh in meshes.items()}
    rows = []
    for a, b in itertools.combinations(meshes, 2):
        volume = (solids[a] ^ solids[b]).volume()
        ok = volume < 1e-3 or frozenset((a, b)) in allowed
        rows.append({"a": a, "b": b, "volume_mm3": round(volume, 3), "allowed": frozenset((a, b)) in allowed, "pass": ok})
    return rows


def inward_faces(meshes):
    scene = trimesh.util.concatenate(list(meshes.values()))
    ray = trimesh.ray.ray_triangle.RayMeshIntersector(scene)
    result = {}
    for name, mesh in meshes.items():
        normals = mesh.face_normals
        origins = mesh.triangles_center + normals * 0.02
        result[name] = ray.intersects_any(origins, normals)
    return result


def shade(colour, normal, view):
    light = -view + np.array([0.3, 0.2, 0.0]) * 0.5
    light = light / np.linalg.norm(light)
    k = 0.45 + 0.55 * abs(float(np.dot(normal, light)))
    return tuple(int(c * k) for c in colour)


def render(meshes, colours, inward, view, scale, margin=4.0):
    direction, (u, v) = VIEWS[view]
    allv = np.vstack([m.vertices for m in meshes.values()])
    lo, hi = allv.min(axis=0), allv.max(axis=0)
    flip_u = view in ("bottom", "back", "right")
    width = int((hi[u] - lo[u] + 2 * margin) * scale)
    height = int((hi[v] - lo[v] + 2 * margin) * scale)
    img = Image.new("RGB", (width, height), (255, 255, 255))
    flat = Image.new("RGB", (width, height), (255, 255, 255))
    draw, flat_draw = ImageDraw.Draw(img), ImageDraw.Draw(flat)
    polys = []
    for name, mesh in meshes.items():
        tri = mesh.triangles
        facing = mesh.face_normals @ direction < 1e-6
        depth = -(tri.mean(axis=1) @ direction)
        for i in np.nonzero(facing)[0]:
            polys.append((depth[i], name, i))
    polys.sort(key=lambda p: p[0])
    for _, name, i in polys:
        tri = meshes[name].triangles[i]
        xs = (tri[:, u] - lo[u] + margin) * scale
        if flip_u:
            xs = width - xs
        ys = height - (tri[:, v] - lo[v] + margin) * scale
        if view == "bottom":
            ys = height - ys
        pts = list(zip(xs.tolist(), ys.tolist()))
        base = RED if inward[name][i] else colours[name]
        draw.polygon(pts, fill=shade(base, meshes[name].face_normals[i], direction))
        flat_draw.polygon(pts, fill=base)
    a = np.asarray(flat).reshape(-1, 3)
    body = np.any(a != 255, axis=1)
    red = np.all(a == RED, axis=1)
    return img, float(red.sum() / max(body.sum(), 1))


def try_font(name):
    try:
        return ImageFont.truetype(name, 28)
    except OSError:
        return None


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("parts", nargs="+", help="name=path.stl, already in assembled position")
    parser.add_argument("--allow", action="append", default=[], help="a:b pair whose overlap is intended (screw:insert)")
    parser.add_argument("--colour", action="append", default=[], help="name=#rrggbb to override the palette")
    parser.add_argument("--check-only", action="append", default=[], help="name of a part used for intersections only")
    parser.add_argument("--scale", type=float, default=8, help="pixels per mm, default %(default)s")
    parser.add_argument("--max-edge", type=float, default=2.0,
                        help="mm; long triangles are split so each piece is classified on its own, default %(default)s")
    parser.add_argument("--view-names", default="top,bottom,front,back,left,right",
                        help="captions for the six views, comma separated")
    parser.add_argument("--caption", default="{view}: red {share} % of visible area")
    parser.add_argument("-o", "--out", default="assembly-check")
    args = parser.parse_args()

    os.makedirs(args.out, exist_ok=True)
    meshes = {}
    for spec in args.parts:
        name, path = spec.split("=", 1)
        mesh = trimesh.load(path, force="mesh")
        mesh.merge_vertices()
        meshes[name] = mesh
    allowed = {frozenset(pair.split(":")) for pair in args.allow}
    rows = intersections(meshes, allowed)

    shown = {name: trimesh.Trimesh(*trimesh.remesh.subdivide_to_size(mesh.vertices, mesh.faces, args.max_edge))
             for name, mesh in meshes.items() if name not in args.check_only}
    colours = dict(zip(shown, palette(len(shown))))
    for spec in args.colour:
        name, value = spec.split("=")
        colours[name] = tuple(int(value.lstrip("#")[i:i + 2], 16) for i in (0, 2, 4))
    inward = inward_faces(shown)

    font = next((f for f in (try_font(n) for n in ("arial.ttf", "DejaVuSans.ttf")) if f), ImageFont.load_default(size=28))
    tiles, red = [], {}
    for view in VIEWS:
        img, red[view] = render(shown, colours, inward, view, args.scale)
        img.save(os.path.join(args.out, f"view-{view}.png"))
        tiles.append((view, img))
    cols = 2
    tw = max(t.width for _, t in tiles)
    th = max(t.height for _, t in tiles) + 40
    sheet = Image.new("RGB", (cols * tw, (len(tiles) + cols - 1) // cols * th), (255, 255, 255))
    d = ImageDraw.Draw(sheet)
    names = dict(zip(VIEWS, args.view_names.split(",")))
    for k, (view, img) in enumerate(tiles):
        x, y = (k % cols) * tw, (k // cols) * th
        d.text((x + 10, y + 4), args.caption.format(view=names[view], share=f"{red[view] * 100:.1f}"), fill=(0, 0, 0),
               font=font)
        sheet.paste(img, (x, y + 40))
    sheet.save(os.path.join(args.out, "views.png"))

    report = {"intersections": rows, "red_share": red, "colours": {k: "#%02x%02x%02x" % v for k, v in colours.items()}}
    with open(os.path.join(args.out, "report.json"), "w", encoding="utf-8") as handle:
        json.dump(report, handle, indent=1)
    failed = [r for r in rows if not r["pass"]]
    for r in rows:
        if r["volume_mm3"] >= 1e-3 or not r["pass"]:
            print(f"{'PASS' if r['pass'] else 'FAIL'}  {r['a']} / {r['b']}: {r['volume_mm3']} mm3"
                  f"{' (allowed)' if r['allowed'] else ''}")
    print(f"{len(rows) - len(failed)}/{len(rows)} pairs pass; red share per view: "
          + ", ".join(f"{v} {s * 100:.1f} %" for v, s in red.items()))
    raise SystemExit(1 if failed else 0)


if __name__ == "__main__":
    main()
