"""Spare solder fields ("joker fields") in the copper left free after routing, so a forgotten part or wire
can be added by hand. Run with the Python that ships with KiCad (needs pcbnew), KiCad 9 or newer."""
import argparse
import math
import re

import pcbnew

ERR = pcbnew.FromMM(0.005)
ROUND = pcbnew.CORNER_STRATEGY_ROUND_ALL_CORNERS
CHAMFER = pcbnew.CORNER_STRATEGY_CHAMFER_ALL_CORNERS


class Rules:
    copper = 1.0
    silk = 0.2
    edge = 0.55
    hole = 1.0
    courtyard = 0.3
    rf_margin = 3.0
    rf_pattern = "antenna|rf"
    gap = 0.5
    pitch = 2.54
    min_width = 1.2
    min_area = 2.0
    whole_area = 6.5
    offset_steps = 8
    drill = 0.8
    ring = 0.45
    through_spacing = 5.08
    smooth = 0.15
    plated = True


def mm(value):
    return pcbnew.FromMM(value)


def to_mm(value):
    return pcbnew.ToMM(value)


def rect(x0, y0, x1, y1):
    poly = pcbnew.SHAPE_POLY_SET()
    poly.NewOutline()
    for x, y in ((x0, y0), (x1, y0), (x1, y1), (x0, y1)):
        poly.Append(mm(x), mm(y))
    return poly


def disk(x, y, r):
    poly = pcbnew.SHAPE_POLY_SET()
    poly.NewOutline()
    for i in range(48):
        a = 2 * math.pi * i / 48
        poly.Append(mm(x + r * math.cos(a)), mm(y + r * math.sin(a)))
    return poly


def grown(poly, by):
    copy = pcbnew.SHAPE_POLY_SET(poly)
    if by > 0:
        copy.Inflate(mm(by), ROUND, ERR)
    return copy


def shrunk(poly, by):
    copy = pcbnew.SHAPE_POLY_SET(poly)
    copy.Deflate(mm(by), CHAMFER, ERR)
    return copy


def area(poly):
    return poly.Area() / 1e12


def box_of(bb, grow):
    return rect(to_mm(bb.GetLeft()) - grow, to_mm(bb.GetTop()) - grow,
                to_mm(bb.GetRight()) + grow, to_mm(bb.GetBottom()) + grow)


def obstacles(board, side, skip_ref, rules):
    copper = pcbnew.F_Cu if side == "F" else pcbnew.B_Cu
    silk = pcbnew.F_SilkS if side == "F" else pcbnew.B_SilkS
    courtyard = pcbnew.F_CrtYd if side == "F" else pcbnew.B_CrtYd
    rf = re.compile(rules.rf_pattern, re.IGNORECASE)
    obs = pcbnew.SHAPE_POLY_SET()

    def add(item, layer, clearance):
        if isinstance(item, pcbnew.PCB_TEXT):
            obs.Append(box_of(item.GetBoundingBox(), clearance))
        else:
            item.TransformShapeToPolygon(obs, layer, mm(clearance), ERR, pcbnew.ERROR_OUTSIDE)

    for fp in board.GetFootprints():
        if fp.GetReference() == skip_ref:
            continue
        for pad in fp.Pads():
            if pad.IsOnLayer(copper):
                add(pad, copper, rules.copper)
            if pad.GetDrillSizeX() > 0:
                p = pad.GetPosition()
                obs.Append(disk(to_mm(p.x), to_mm(p.y), to_mm(pad.GetDrillSizeX()) / 2 + rules.hole))
        for item in list(fp.GraphicalItems()) + list(fp.GetFields()):
            if item.GetLayer() == silk and (not isinstance(item, pcbnew.PCB_TEXT) or item.IsVisible()):
                add(item, silk, rules.silk)
        if fp.GetCourtyard(courtyard).OutlineCount():
            obs.Append(grown(fp.GetCourtyard(courtyard), rules.courtyard))
    for track in board.GetTracks():
        if track.IsOnLayer(copper):
            add(track, copper, rules.copper)
        if track.Type() == pcbnew.PCB_VIA_T:
            p = track.GetPosition()
            obs.Append(disk(to_mm(p.x), to_mm(p.y), to_mm(track.GetDrillValue()) / 2 + rules.hole))
    for drawing in board.GetDrawings():
        if drawing.GetLayer() == silk:
            add(drawing, silk, rules.silk)
        elif drawing.GetLayer() == copper:
            add(drawing, copper, rules.copper)
    for zone in board.Zones():
        if not zone.IsOnLayer(copper):
            continue
        if zone.GetIsRuleArea():
            obs.Append(grown(zone.Outline(), rules.rf_margin if rf.search(zone.GetZoneName() or "") else 0.0))
        else:
            obs.Append(grown(zone.GetFilledPolysList(copper), rules.copper))
    obs.Simplify()
    return obs


def board_area(board, rules):
    outline = pcbnew.SHAPE_POLY_SET()
    if not board.GetBoardPolygonOutlines(outline, False):
        raise SystemExit("board outline (Edge.Cuts) is not closed")
    return shrunk(outline, rules.edge)


def free_space(board, side, skip_ref, rules):
    free = board_area(board, rules)
    free.BooleanSubtract(obstacles(board, side, skip_ref, rules))
    return free


def pieces(poly):
    return [poly.Subset(i, i + 1) for i in range(poly.OutlineCount())]


def usable(piece, rules):
    return area(piece) >= rules.min_area and shrunk(piece, rules.min_width / 2).OutlineCount() > 0


def grid_split(region, ox, oy, rules):
    bb = region.BBox()
    p, g = rules.pitch, rules.gap
    found = []
    for i in range(math.floor((to_mm(bb.GetLeft()) - ox) / p), math.ceil((to_mm(bb.GetRight()) - ox) / p) + 1):
        for j in range(math.floor((to_mm(bb.GetTop()) - oy) / p), math.ceil((to_mm(bb.GetBottom()) - oy) / p) + 1):
            x, y = ox + i * p, oy + j * p
            cell = rect(x + g / 2, y + g / 2, x + p - g / 2, y + p - g / 2)
            cell.BooleanIntersection(region)
            found += [piece for piece in pieces(cell) if usable(piece, rules)]
    return found


def offsets(rules):
    n = rules.offset_steps
    return [(a * rules.pitch / n, c * rules.pitch / n) for a in range(n) for c in range(n)]


def split_fields(free, rules):
    """Small islands stay whole; larger ones are cut on the grid whose offset keeps the most copper."""
    fields = []
    for region in pieces(free):
        if not usable(region, rules):
            continue
        if area(region) <= rules.whole_area:
            fields.append(region)
            continue
        fields += max((grid_split(region, ox, oy, rules) for ox, oy in offsets(rules)),
                      key=lambda got: sum(area(piece) for piece in got))
    return fields


def through_sites(free_top, free_bottom, rules):
    both = pcbnew.SHAPE_POLY_SET(free_top)
    both.BooleanIntersection(free_bottom)
    core = shrunk(both, rules.drill / 2 + rules.ring)
    if not core.OutlineCount():
        return []
    bb = core.BBox()
    p = rules.pitch
    best = []
    for ox, oy in offsets(rules):
        picked = []
        for j in range(math.floor((to_mm(bb.GetTop()) - oy) / p), math.ceil((to_mm(bb.GetBottom()) - oy) / p) + 1):
            for i in range(math.floor((to_mm(bb.GetLeft()) - ox) / p), math.ceil((to_mm(bb.GetRight()) - ox) / p) + 1):
                x, y = ox + i * p, oy + j * p
                spaced = all(math.hypot(x - px, y - py) >= rules.through_spacing - 1e-6 for px, py in picked)
                if spaced and core.Contains(pcbnew.VECTOR2I(mm(x), mm(y))):
                    picked.append((x, y))
        if len(picked) > len(best):
            best = picked
    return best


def field_at(free, x, y, rules):
    half = (rules.pitch - rules.gap) / 2
    cell = rect(x - half, y - half, x + half, y + half)
    cell.BooleanIntersection(free)
    at = pcbnew.VECTOR2I(mm(x), mm(y))
    return next(piece for piece in pieces(cell) if piece.Contains(at))


def outline(poly, rules):
    copy = shrunk(poly, rules.smooth)
    copy.Inflate(mm(rules.smooth), ROUND, ERR)
    copy.Fracture()
    line = copy.COutline(0)
    return [(to_mm(line.CPoint(k).x), to_mm(line.CPoint(k).y)) for k in range(line.PointCount())]


def anchor(poly):
    vertex = shrunk(poly, 0.3).CVertex(0)
    return to_mm(vertex.x), to_mm(vertex.y)


def compute(board, rules, skip_ref=None):
    """Returns plated fields ((x, y), top outline, bottom outline) and one-sided fields (side, anchor, outline), in mm."""
    free_top, free_bottom = free_space(board, "F", skip_ref, rules), free_space(board, "B", skip_ref, rules)
    sites = through_sites(free_top, free_bottom, rules) if rules.plated else []
    plated = [((x, y), outline(field_at(free_top, x, y, rules), rules), outline(field_at(free_bottom, x, y, rules), rules))
              for x, y in sites]
    half = (rules.pitch - rules.gap) / 2 + rules.gap
    for x, y in sites:
        free_top.BooleanSubtract(rect(x - half, y - half, x + half, y + half))
        free_bottom.BooleanSubtract(rect(x - half, y - half, x + half, y + half))
    single = [("F", anchor(p), outline(p, rules)) for p in split_fields(free_top, rules)]
    single += [("B", anchor(p), outline(p, rules)) for p in split_fields(free_bottom, rules)]
    return plated, single


def custom_pad(fp, number, side, at, points):
    copper, mask = (pcbnew.F_Cu, pcbnew.F_Mask) if side == "F" else (pcbnew.B_Cu, pcbnew.B_Mask)
    pad = pcbnew.PAD(fp)
    pad.SetNumber(number)
    pad.SetAttribute(pcbnew.PAD_ATTRIB_SMD)
    layers = pcbnew.LSET()
    layers.AddLayer(copper)
    layers.AddLayer(mask)
    pad.SetLayerSet(layers)
    pad.SetPosition(pcbnew.VECTOR2I(mm(at[0]), mm(at[1])))
    pad.SetShape(copper, pcbnew.PAD_SHAPE_CUSTOM)
    pad.SetAnchorPadShape(copper, pcbnew.PAD_SHAPE_CIRCLE)
    pad.SetSize(copper, pcbnew.VECTOR2I(mm(0.6), mm(0.6)))
    relative = pcbnew.VECTOR_VECTOR2I([pcbnew.VECTOR2I(mm(x - at[0]), mm(y - at[1])) for x, y in points])
    pad.AddPrimitivePoly(copper, relative, 0, True)
    pad.SetCustomShapeInZoneOpt(pcbnew.CUSTOM_SHAPE_ZONE_MODE_OUTLINE)
    fp.Add(pad)


def through_pad(fp, number, at, rules):
    pad = pcbnew.PAD(fp)
    pad.SetNumber(number)
    pad.SetAttribute(pcbnew.PAD_ATTRIB_PTH)
    pad.SetLayerSet(pcbnew.PAD.PTHMask())
    pad.SetPosition(pcbnew.VECTOR2I(mm(at[0]), mm(at[1])))
    size = rules.drill + 2 * rules.ring
    pad.SetShape(pcbnew.PAD_SHAPE_CIRCLE)
    pad.SetSize(pcbnew.VECTOR2I(mm(size), mm(size)))
    pad.SetDrillSize(pcbnew.VECTOR2I(mm(rules.drill), mm(rules.drill)))
    fp.Add(pad)


def add_footprint(board, plated, single, ref):
    """One board-only footprint at the origin; a plated field is a round PTH pad plus one shaped pad per side, same number."""
    fp = pcbnew.FOOTPRINT(board)
    fp.SetFPID(pcbnew.LIB_ID("", "Joker_Fields"))
    fp.SetReference(ref)
    fp.SetValue("Joker_Fields")
    for field in (fp.Reference(), fp.Value()):
        field.SetVisible(False)
        field.SetLayer(pcbnew.F_Fab)
    fp.SetAttributes(pcbnew.FP_SMD | pcbnew.FP_BOARD_ONLY | pcbnew.FP_EXCLUDE_FROM_POS_FILES | pcbnew.FP_EXCLUDE_FROM_BOM)
    board.Add(fp)
    return fp


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("board", help=".kicad_pcb to fill; routing must be finished")
    parser.add_argument("-o", "--output", help="write here instead of overwriting the input")
    parser.add_argument("--ref", default="JK", help="reference of the generated footprint; an existing one is replaced")
    for name in ("copper", "hole", "silk", "edge", "courtyard", "rf_margin", "gap", "pitch", "min_width", "min_area",
                 "drill", "ring", "through_spacing"):
        parser.add_argument("--" + name.replace("_", "-"), type=float, default=getattr(Rules, name),
                            help=f"mm, default {getattr(Rules, name)}")
    parser.add_argument("--rf-pattern", default=Rules.rf_pattern,
                        help="regex on rule-area names that get the RF margin, default %(default)r")
    parser.add_argument("--no-plated", action="store_true", help="one-sided fields only")
    args = parser.parse_args()

    rules = Rules()
    for name, value in vars(args).items():
        if hasattr(Rules, name):
            setattr(rules, name, value)
    rules.plated = not args.no_plated

    board = pcbnew.LoadBoard(args.board)
    plated, single = compute(board, rules, skip_ref=args.ref)
    for old in [fp for fp in board.GetFootprints() if fp.GetReference() == args.ref]:
        board.Delete(old)
    fp = add_footprint(board, plated, single, args.ref)
    for index, (at, top, bottom) in enumerate(plated, 1):
        through_pad(fp, f"P{index}", at, rules)
        custom_pad(fp, f"P{index}", "F", at, top)
        custom_pad(fp, f"P{index}", "B", at, bottom)
    for index, (side, at, points) in enumerate(single, 1):
        custom_pad(fp, f"{side}{index}", side, at, points)
    out = args.output or args.board
    board.Save(out)
    print(f"{out}: {len(plated)} plated, {sum(1 for f in single if f[0] == 'F')} top, "
          f"{sum(1 for f in single if f[0] == 'B')} bottom fields")


if __name__ == "__main__":
    main()
