"""Removes the solder mask from every via on both sides (rule HS-5), including vias a router created. Vias under a part
(inside a courtyard) or under silkscreen stay covered, as HS-5 allows. Run with the Python that ships with KiCad 9+."""
import argparse

import pcbnew


def _disjoint(a, b):
    both = pcbnew.SHAPE_POLY_SET(a)
    both.BooleanIntersection(b)
    return both.OutlineCount() == 0


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("board", help=".kicad_pcb")
    parser.add_argument("-o", "--output", help="write here instead of overwriting the input")
    args = parser.parse_args()

    board = pcbnew.LoadBoard(args.board)
    covered = []
    for fp in board.GetFootprints():
        for layer in (pcbnew.F_CrtYd, pcbnew.B_CrtYd):
            if fp.GetCourtyard(layer).OutlineCount():
                covered.append(fp.GetCourtyard(layer))
        for item in list(fp.GraphicalItems()) + [fp.Reference(), fp.Value()]:
            if item.GetLayer() in (pcbnew.F_SilkS, pcbnew.B_SilkS) and (not hasattr(item, "IsVisible") or item.IsVisible()):
                poly = pcbnew.SHAPE_POLY_SET()
                item.TransformShapeToPolygon(poly, item.GetLayer(), pcbnew.FromMM(0.15), pcbnew.FromMM(0.01),
                                             pcbnew.ERROR_OUTSIDE)
                covered.append(poly)
    for item in board.GetDrawings():
        if item.GetLayer() in (pcbnew.F_SilkS, pcbnew.B_SilkS):
            poly = pcbnew.SHAPE_POLY_SET()
            item.TransformShapeToPolygon(poly, item.GetLayer(), pcbnew.FromMM(0.15), pcbnew.FromMM(0.01),
                                         pcbnew.ERROR_OUTSIDE)
            covered.append(poly)
    opened = kept = 0
    for track in board.GetTracks():
        if track.Type() != pcbnew.PCB_VIA_T:
            continue
        ring = pcbnew.SHAPE_POLY_SET()
        track.TransformShapeToPolygon(ring, pcbnew.F_Cu, 0, pcbnew.FromMM(0.01), pcbnew.ERROR_OUTSIDE)
        hidden = any(ring.BBox().Intersects(c.BBox()) and not _disjoint(ring, c) for c in covered)
        mode = pcbnew.TENTING_MODE_TENTED if hidden else pcbnew.TENTING_MODE_NOT_TENTED
        track.SetFrontTentingMode(mode)
        track.SetBackTentingMode(mode)
        kept += hidden
        opened += not hidden
    board.Save(args.output or args.board)
    print(f"{opened} vias untented, {kept} under parts or silkscreen kept covered")


if __name__ == "__main__":
    main()
