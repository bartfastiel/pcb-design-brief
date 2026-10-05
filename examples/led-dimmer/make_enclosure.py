"""Minimal two-part enclosure for the example board, as STL in the assembled position (needs manifold3d, trimesh).
Base with four seats and three connector slots, lid with a locating lip. Usage: python make_enclosure.py <out dir>"""
import os
import sys

import manifold3d as m3d
import numpy as np
import trimesh

BOARD = (40.0, 24.0, 1.6)
WALL, FLOOR, GAP = 1.6, 1.6, 0.3
SEAT_H = 3.0
INNER = (BOARD[0] + 2 * GAP, BOARD[1] + 2 * GAP)
OUTER = (INNER[0] + 2 * WALL, INNER[1] + 2 * WALL)
BASE_H = FLOOR + SEAT_H + BOARD[2] + 9.0
LID_T, LIP = 1.6, 2.0


def box(x0, y0, z0, x1, y1, z1):
    return m3d.Manifold.cube([x1 - x0, y1 - y0, z1 - z0]).translate([x0, y0, z0])


def to_trimesh(solid):
    mesh = solid.to_mesh()
    return trimesh.Trimesh(np.asarray(mesh.vert_properties)[:, :3], np.asarray(mesh.tri_verts))


def main():
    out = sys.argv[1]
    os.makedirs(out, exist_ok=True)
    ox, oy = WALL + GAP, WALL + GAP
    board_z = FLOOR + SEAT_H
    base = box(0, 0, 0, OUTER[0], OUTER[1], BASE_H) - box(WALL, WALL, FLOOR, WALL + INNER[0], WALL + INNER[1], BASE_H + 1)
    for cx, cy in ((ox + 2, oy + 2), (ox + BOARD[0] - 2, oy + 2), (ox + 2, oy + BOARD[1] - 2),
                   (ox + BOARD[0] - 2, oy + BOARD[1] - 2)):
        base = base + box(cx - 2, cy - 2, FLOOR - 0.01, cx + 2, cy + 2, board_z)
    for x, y0 in ((-1, oy + 8 - 1.6), (-1, oy + 16 - 1.6), (OUTER[0] - WALL - 1, oy + 8 - 1.6)):
        base = base - box(x, y0, board_z + BOARD[2], x + WALL + 2, y0 + 2.54 + 3.2, BASE_H + 1)
    lid = box(0, 0, BASE_H, OUTER[0], OUTER[1], BASE_H + LID_T) + \
        (box(WALL + GAP, WALL + GAP, BASE_H - LIP, WALL + INNER[0] - GAP, WALL + INNER[1] - GAP, BASE_H + 0.01) -
         box(WALL + GAP + 1.2, WALL + GAP + 1.2, BASE_H - LIP - 1, WALL + INNER[0] - GAP - 1.2,
             WALL + INNER[1] - GAP - 1.2, BASE_H + 0.5))
    board = box(ox, oy, board_z, ox + BOARD[0], oy + BOARD[1], board_z + BOARD[2])
    for name, solid in (("base", base), ("lid", lid), ("board", board)):
        to_trimesh(solid).export(os.path.join(out, name + ".stl"))
    print(f"outer {OUTER[0]:.1f} x {OUTER[1]:.1f} x {BASE_H + LID_T:.1f} mm")


if __name__ == "__main__":
    main()
