"""Enclosure of the USB gamepad from design.json and the board's 3D export: base, top, ten button caps, screws, inserts,
board and parts, all in the assembled position; base, top and caps also in print orientation. The screw holes above the
head seats start with a 0.2 mm membrane, so the seat prints as a bridge; the first screw pushes through it.
Usage: python make_enclosure.py <parts.glb from kicad-cli --no-board-body> <out dir>
Lengths in mm; case frame: x along the board, y up the board (KiCad y mirrored), z up, z = 0 on the table."""
import json
import os
import sys

import manifold3d as m3d
import numpy as np
import trimesh

DESIGN = json.load(open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "design.json"), encoding="utf-8"))
BOARD_W, BOARD_H, CORNER = (DESIGN["board"][k] for k in ("width", "height", "corner"))
PARTS = {p["ref"]: p for p in DESIGN["parts"]}
BUTTONS = [p for p in DESIGN["parts"] if p["symbol"] == "Switch:SW_Push" and p["side"] == "F"]
LEDS = [p for p in DESIGN["parts"] if p["symbol"] == "Device:LED"]

GAP, WALL, FLOOR, PLATE = 1.6, 2.0, 2.0, 1.6
MEMBRANE = 0.2
BELOW = 3.0
BOARD_T = 1.6
Z_BOARD = FLOOR + BELOW
Z_TOP = Z_BOARD + BOARD_T
LIP, LIP_T, FIT = 1.5, 1.2, 0.2
CAP_D, CAP_HOLE, FLANGE_D, FLANGE_T, CAP_RISE = 7.0, 7.6, 9.0, 0.8, 1.5
SMALL_CAP_D, SMALL_CAP_HOLE = 5.5, 6.1
BOSS_D, SCREW_HOLE, INSERT_HOLE, INSERT_DEPTH = 6.0, 2.8, 3.6, 4.2
HEAD_D, HEAD_SEAT = 5.0, 1.6
SCREW_LEN, INSERT_LEN, INSERT_OD = 8.0, 4.0, 3.5
USB_OPENING = (12.4, 7.0)
LED_HOLE, RESET_HOLE = 1.8, 1.6


def case_xy(x, y):
    return x, BOARD_H - y


def cylinder(x, y, z0, z1, d, segments=48):
    return m3d.Manifold.cylinder(z1 - z0, d / 2, d / 2, segments).translate([x, y, z0])


def box(x0, y0, z0, x1, y1, z1):
    return m3d.Manifold.cube([x1 - x0, y1 - y0, z1 - z0]).translate([x0, y0, z0])


def outline(grow):
    """Board outline (rounded rectangle) grown by grow mm."""
    inner = m3d.CrossSection.square([BOARD_W - 2 * CORNER, BOARD_H - 2 * CORNER]).translate([CORNER, CORNER])
    return inner.offset(CORNER + grow, m3d.JoinType.Round, circular_segments=64)


def slab(section, z0, z1):
    return m3d.Manifold.extrude(section, z1 - z0).translate([0, 0, z0])


def holes():
    return [case_xy(*p["at"]) for ref, p in PARTS.items() if ref.startswith("H")]


def build(parts_glb, out):
    os.makedirs(out, exist_ok=True)
    outer, inner = outline(GAP + WALL), outline(GAP)
    plate_top = None
    plunger = parts_height(parts_glb)
    cap_bottom = Z_BOARD + plunger
    plate_under = cap_bottom + FLANGE_T + 0.2
    plate_top = plate_under + PLATE

    base = slab(outer, 0, Z_TOP) - slab(inner, FLOOR, Z_TOP + 1)
    top = slab(outer, Z_TOP, plate_top) - slab(outline(GAP - FIT - LIP_T), Z_TOP - 1, plate_under)
    lip = slab(outline(GAP - FIT), Z_TOP - LIP, Z_TOP + 0.01) - slab(outline(GAP - FIT - LIP_T), Z_TOP - LIP - 1, Z_TOP + 1)
    top = top + lip
    screws, inserts = [], []
    for x, y in holes():
        base = base + cylinder(x, y, FLOOR - 0.01, Z_BOARD, BOSS_D)
        base = base - cylinder(x, y, HEAD_SEAT + MEMBRANE, Z_BOARD + 1, SCREW_HOLE) - cylinder(x, y, -1, HEAD_SEAT, HEAD_D)
        top = top + cylinder(x, y, Z_TOP, plate_under + 0.01, BOSS_D)
        top = top - cylinder(x, y, Z_TOP - 1, Z_TOP + INSERT_DEPTH, INSERT_HOLE)
        screws.append(cylinder(x, y, HEAD_SEAT - 1.5, HEAD_SEAT, HEAD_D - 0.4) +
                      cylinder(x, y, HEAD_SEAT, HEAD_SEAT + SCREW_LEN, 2.4))
        inserts.append(cylinder(x, y, Z_TOP, Z_TOP + INSERT_LEN, INSERT_OD) - cylinder(x, y, Z_TOP - 1, Z_TOP + 5, 2.5))
    caps = []
    for button in BUTTONS:
        x, y = case_xy(*button["at"])
        small = button["label"] in ("START", "SELECT")
        hole, d = (SMALL_CAP_HOLE, SMALL_CAP_D) if small else (CAP_HOLE, CAP_D)
        top = top - cylinder(x, y, plate_under - 1, plate_top + 1, hole)
        caps.append(cylinder(x, y, cap_bottom, cap_bottom + FLANGE_T, FLANGE_D if not small else d + 2) +
                    cylinder(x, y, cap_bottom + FLANGE_T - 0.01, plate_top + CAP_RISE, d))
    for led in LEDS:
        x, y = case_xy(*led["at"])
        top = top - cylinder(x, y, plate_under - 1, plate_top + 1, LED_HOLE, 24)
    reset = PARTS["SW11"]["at"]
    base = base - cylinder(*case_xy(*reset), -1, FLOOR + 1, RESET_HOLE, 24)
    usb_x = PARTS["J1"]["at"][0] - 2.975
    z_usb = Z_TOP + 1.63
    w, h = USB_OPENING
    opening = box(usb_x - w / 2, BOARD_H - 1, z_usb - h / 2, usb_x + w / 2, BOARD_H + GAP + WALL + 1, z_usb + h / 2)
    base, top = base - opening, top - opening
    board = slab(outline(0), Z_BOARD, Z_TOP)
    for x, y in holes():
        board = board - cylinder(x, y, Z_BOARD - 1, Z_TOP + 1, 2.7)

    meshes = {"base": base, "top": top, "caps": sum(caps[1:], caps[0]), "screws": sum(screws[1:], screws[0]),
              "inserts": sum(inserts[1:], inserts[0]), "board": board}
    for name, solid in meshes.items():
        to_mesh(solid).export(os.path.join(out, name + ".stl"))
    parts = parts_mesh(parts_glb)
    parts.export(os.path.join(out, "parts.stl"))
    flipped = to_mesh(top)
    flipped.apply_transform(trimesh.transformations.rotation_matrix(np.pi, [1, 0, 0]))
    flipped.apply_translation(-flipped.bounds[0])
    flipped.export(os.path.join(out, "top-print.stl"))
    cap_print = to_mesh(caps[0])
    cap_print.apply_translation(-cap_print.bounds[0])
    cap_print.export(os.path.join(out, "cap-print.stl"))
    small = to_mesh(caps[-1])
    small.apply_translation(-small.bounds[0])
    small.export(os.path.join(out, "cap-small-print.stl"))
    info = {"outer_mm": [round(BOARD_W + 2 * (GAP + WALL), 1), round(BOARD_H + 2 * (GAP + WALL), 1), round(plate_top, 1)],
            "z_board": Z_BOARD, "plunger_above_board_bottom": round(plunger, 2), "plate_top": round(plate_top, 2),
            "volume_cm3": {k: round(to_mesh(v).volume / 1000, 2) for k, v in meshes.items() if k in ("base", "top", "caps")}}
    with open(os.path.join(out, "enclosure.json"), "w", encoding="utf-8") as handle:
        json.dump(info, handle, indent=1)
    print(json.dumps(info))


def gltf_to_case(points):
    """glTF from KiCad: x right, y up from the board's bottom face, z = KiCad y; to the case frame."""
    return np.column_stack([points[:, 0], BOARD_H - points[:, 2], Z_BOARD + points[:, 1]])


def parts_mesh(parts_glb):
    mesh = trimesh.load(parts_glb).to_geometry()
    mesh.vertices = gltf_to_case(mesh.vertices * 1000)
    mesh.fix_normals()
    return mesh


def parts_height(parts_glb):
    """Height of the button plungers above the board's bottom face, from the 3D models."""
    points = trimesh.load(parts_glb).to_geometry().vertices * 1000
    heights = []
    for button in BUTTONS:
        x, y = button["at"]
        near = (abs(points[:, 0] - x) < 1.5) & (abs(points[:, 2] - y) < 1.5)
        heights.append(points[near, 1].max())
    return max(heights)


def to_mesh(solid):
    mesh = solid.to_mesh()
    return trimesh.Trimesh(np.asarray(mesh.vert_properties)[:, :3], np.asarray(mesh.tri_verts))


if __name__ == "__main__":
    build(sys.argv[1], sys.argv[2])
