"""Technical drawing sheet for 3D-printed parts (brief §12.7): per part a front view, the view from the left placed to
its right and the top view placed below it (first-angle projection, ISO), plus an isometric view, visible edges only,
overall dimensions in mm. Needs trimesh, numpy, pillow."""
import argparse
import os

import numpy as np
import trimesh
from PIL import Image, ImageDraw, ImageFont

FEATURE_ANGLE = np.radians(20)


def camera(direction, up=(0, 0, 1)):
    d = np.asarray(direction, dtype=float)
    d /= np.linalg.norm(d)
    u = np.asarray(up, dtype=float) - np.dot(up, d) * d
    u /= np.linalg.norm(u)
    return d, np.cross(d, u), u


VIEWS = {
    "front": camera((0, 1, 0)),
    "left": camera((1, 0, 0)),
    "top": camera((0, 0, -1), up=(0, 1, 0)),
    "iso": camera((1, 1, -1)),
}


def zbuffer(xy, depth, faces, size):
    w, h = size
    zbuf = np.full((h, w), -np.inf)
    for f in faces:
        p, z = xy[f], depth[f]
        x0, y0 = np.floor(p.min(axis=0)).astype(int)
        x1, y1 = np.ceil(p.max(axis=0)).astype(int)
        x0, y0, x1, y1 = max(x0, 0), max(y0, 0), min(x1, w - 1), min(y1, h - 1)
        if x1 < x0 or y1 < y0:
            continue
        gx, gy = np.meshgrid(np.arange(x0, x1 + 1) + 0.5, np.arange(y0, y1 + 1) + 0.5)
        (ax, ay), (bx, by), (cx, cy) = p
        det = (by - cy) * (ax - cx) + (cx - bx) * (ay - cy)
        if abs(det) < 1e-9:
            continue
        l1 = ((by - cy) * (gx - cx) + (cx - bx) * (gy - cy)) / det
        l2 = ((cy - ay) * (gx - cx) + (ax - cx) * (gy - cy)) / det
        l3 = 1 - l1 - l2
        inside = (l1 >= -1e-3) & (l2 >= -1e-3) & (l3 >= -1e-3)
        zz = l1 * z[0] + l2 * z[1] + l3 * z[2]
        region = zbuf[y0:y1 + 1, x0:x1 + 1]
        np.copyto(region, np.where(inside & (zz > region), zz, region))
    return zbuf


def drawing_edges(mesh, d):
    """Feature edges, silhouette edges and open boundaries as vertex index pairs."""
    facing = mesh.face_normals @ d < 0
    adj = mesh.face_adjacency
    sharp = mesh.face_adjacency_angles > FEATURE_ANGLE
    silhouette = facing[adj[:, 0]] != facing[adj[:, 1]]
    visible_side = facing[adj[:, 0]] | facing[adj[:, 1]]
    edges = mesh.face_adjacency_edges[(sharp & visible_side) | silhouette]
    boundary = trimesh.grouping.group_rows(mesh.edges_sorted, require_count=1)
    return np.vstack([edges, mesh.edges_sorted[boundary]]) if len(boundary) else edges


def render_view(mesh, view, scale, margin_px=8):
    d, r, u = VIEWS[view]
    v = mesh.vertices
    sx, sy, depth = v @ r, v @ u, -(v @ d)
    x0, y1 = sx.min(), sy.max()
    w = int((sx.max() - x0) * scale) + 2 * margin_px + 1
    h = int((y1 - sy.min()) * scale) + 2 * margin_px + 1
    xy = np.column_stack([(sx - x0) * scale + margin_px, (y1 - sy) * scale + margin_px])
    faces = mesh.faces[mesh.face_normals @ d < 0]
    zbuf = zbuffer(xy, depth, faces, (w, h))
    img = Image.new("L", (w, h), 255)
    draw = ImageDraw.Draw(img)
    tol = 0.1 + 4.0 / scale
    for a, b in drawing_edges(mesh, d):
        n = max(int(np.hypot(*(xy[b] - xy[a]))) * 2, 2)
        t = np.linspace(0, 1, n)
        pts = xy[a] + np.outer(t, xy[b] - xy[a])
        zs = depth[a] + t * (depth[b] - depth[a])
        px = np.clip(pts.astype(int), 0, [w - 1, h - 1])
        near = np.max([zbuf[np.clip(px[:, 1] + dy, 0, h - 1), np.clip(px[:, 0] + dx, 0, w - 1)]
                       for dx in (-1, 0, 1) for dy in (-1, 0, 1)], axis=0)
        seen = zs >= near - tol
        start = None
        for k in range(n + 1):
            if k < n and seen[k]:
                start = k if start is None else start
            elif start is not None:
                if k - 1 > start:
                    draw.line([tuple(pts[start]), tuple(pts[k - 1])], fill=0, width=2)
                start = None
    return img, (sx.max() - x0, y1 - sy.min())


def load_font(size):
    for name in ("arial.ttf", "DejaVuSans.ttf", "LiberationSans-Regular.ttf", "Helvetica.ttc"):
        try:
            return ImageFont.truetype(name, size)
        except OSError:
            continue
    return ImageFont.load_default(size=size)


def fmt(value, comma):
    text = f"{value:.1f}"
    return text.replace(".", ",") if comma else text


def dimension(draw, font, a, b, offset, text, vertical=False):
    """Dimension line with arrows between a and b, offset outwards, text centred on it."""
    grey = (40, 40, 40)
    if vertical:
        x = offset
        draw.line([(a[0] + 4, a[1]), (x + 6, a[1])], fill=grey)
        draw.line([(b[0] + 4, b[1]), (x + 6, b[1])], fill=grey)
        draw.line([(x, a[1]), (x, b[1])], fill=grey, width=2)
        for y, s in ((a[1], 1), (b[1], -1)):
            draw.polygon([(x, y), (x - 5, y + 14 * s), (x + 5, y + 14 * s)], fill=grey)
        label = Image.new("RGBA", font.getbbox(text)[2:], (255, 255, 255, 0))
        ImageDraw.Draw(label).text((0, 0), text, font=font, fill=grey)
        label = label.rotate(90, expand=True)
        return label, (int(x + 6), int((a[1] + b[1]) / 2 - label.height / 2))
    y = offset
    draw.line([(a[0], a[1] + 4), (a[0], y + 6)], fill=grey)
    draw.line([(b[0], b[1] + 4), (b[0], y + 6)], fill=grey)
    draw.line([(a[0], y), (b[0], y)], fill=grey, width=2)
    for x, s in ((a[0], 1), (b[0], -1)):
        draw.polygon([(x, y), (x + 14 * s, y - 5), (x + 14 * s, y + 5)], fill=grey)
    tw = font.getbbox(text)[2]
    draw.text(((a[0] + b[0]) / 2 - tw / 2, y + 4), text, font=font, fill=grey)
    return None, None


def part_block(name, mesh, scale, font, small, comma, labels):
    views = {v: render_view(mesh, v, scale) for v in VIEWS}
    gap = 90
    fw, fh = views["front"][0].size
    lw, lh = views["left"][0].size
    tw, th = views["top"][0].size
    iw, ih = views["iso"][0].size
    left_col = max(fw, tw)
    width = left_col + gap + max(lw, iw) + gap
    height = 50 + max(fh, lh) + gap + max(th, ih) + gap
    block = Image.new("RGB", (int(width), int(height)), (255, 255, 255))
    draw = ImageDraw.Draw(block)
    draw.text((0, 0), name, font=font, fill=(0, 0, 0))
    spots = {"front": (0, 50), "left": (left_col + gap, 50), "top": (0, 50 + max(fh, lh) + gap),
             "iso": (left_col + gap, 50 + max(fh, lh) + gap)}
    for v, (img, extent) in views.items():
        x, y = spots[v]
        block.paste(img.convert("RGB"), (int(x), int(y)))
        draw.text((x, y + img.height + 50 if v != "iso" else y + img.height + 6), labels[v], font=small, fill=(110, 110, 110))
        if v == "iso":
            continue
        m = 8
        x_left, x_right = x + m, x + img.width - m
        y_top, y_bottom = y + m, y + img.height - m
        dimension(draw, small, (x_left, y_bottom), (x_right, y_bottom), y_bottom + 24, fmt(extent[0], comma))
        label, at = dimension(draw, small, (x_right, y_top), (x_right, y_bottom), x_right + 24, fmt(extent[1], comma),
                              vertical=True)
        block.paste(label, at, label)
    return block


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("parts", nargs="+", help="name=path.stl (any orientation; drawn as stored)")
    parser.add_argument("-o", "--output", default="tech-drawing.png")
    parser.add_argument("--scale", type=float, default=10, help="pixels per mm, default %(default)s")
    parser.add_argument("--title", default="")
    parser.add_argument("--decimal-comma", action="store_true")
    parser.add_argument("--labels", default="front,left,top,isometric", help="four view captions, comma separated")
    parser.add_argument("--note", default="First-angle projection (ISO). Dimensions in mm. Visible edges only.")
    args = parser.parse_args()
    labels = dict(zip(VIEWS, args.labels.split(",")))

    font, small = load_font(34), load_font(24)
    blocks = []
    for spec in args.parts:
        name, path = spec.split("=", 1)
        mesh = trimesh.load(path, force="mesh")
        mesh.merge_vertices()
        mesh.apply_translation(-mesh.bounds[0])
        blocks.append(part_block(name, mesh, args.scale, font, small, args.decimal_comma, labels))
    note = args.note
    width = max(b.width for b in blocks) + 80
    height = sum(b.height for b in blocks) + 140
    sheet = Image.new("RGB", (width, height), (255, 255, 255))
    draw = ImageDraw.Draw(sheet)
    draw.text((40, 20), args.title or os.path.splitext(os.path.basename(args.output))[0], font=font, fill=(0, 0, 0))
    draw.text((40, 64), note, font=small, fill=(90, 90, 90))
    y = 120
    for block in blocks:
        sheet.paste(block, (40, y))
        y += block.height
    sheet.save(args.output)
    print(f"{args.output}: {len(blocks)} parts, {width} x {height} px")


if __name__ == "__main__":
    main()
