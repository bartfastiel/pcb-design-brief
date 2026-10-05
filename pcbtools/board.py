"""KiCad board from design.json, in two steps around the autorouter. Needs KiCad's Python (pcbnew).
  place:  outline, footprints at their centres on either side, nets, net classes, custom rules, keepouts, fixed texts,
          pre-routes (locked: the autorouter keeps them), fan-out vias, labels
  finish: router necks widened where clearance allows, labels again around the new vias, pours with stitching"""
import datetime
import json
import math

import pcbnew

from .design import Design
from .labels import Labeller, around, new_text

OX, OY = 100.0, 100.0


def mm(v):
    return pcbnew.FromMM(v)


def at(x, y):
    return pcbnew.VECTOR2I(mm(OX + x), mm(OY + y))


def outline(board, w, h, r):
    def edge(shape, start, end, mid=None):
        item = pcbnew.PCB_SHAPE(board)
        item.SetShape(shape)
        if mid is None:
            item.SetStart(at(*start))
            item.SetEnd(at(*end))
        else:
            item.SetArcGeometry(at(*start), at(*mid), at(*end))
        item.SetLayer(pcbnew.Edge_Cuts)
        item.SetWidth(mm(0.1))
        board.Add(item)

    d = r * (1 - math.sqrt(0.5))
    for start, end in (((r, 0), (w - r, 0)), ((w, r), (w, h - r)), ((w - r, h), (r, h)), ((0, h - r), (0, r))):
        edge(pcbnew.SHAPE_T_SEGMENT, start, end)
    if r > 0:
        for start, mid, end in (((w - r, 0), (w - d, d), (w, r)), ((w, h - r), (w - d, h - d), (w - r, h)),
                                ((r, h), (d, h - d), (0, h - r)), ((0, r), (d, d), (r, 0))):
            edge(pcbnew.SHAPE_T_ARC, start, end, mid)


def rule_area(board, box, side, name, vias=False):
    """No tracks (and no vias unless allowed) inside the box on one side; pours still fill it."""
    zone = pcbnew.ZONE(board)
    zone.SetIsRuleArea(True)
    zone.SetDoNotAllowVias(not vias)
    zone.SetDoNotAllowTracks(True)
    zone.SetDoNotAllowZoneFills(False)
    zone.SetDoNotAllowPads(False)
    zone.SetDoNotAllowFootprints(False)
    zone.SetLayer(pcbnew.F_Cu if side == "F" else pcbnew.B_Cu)
    zone.SetZoneName(name)
    poly = zone.Outline()
    poly.NewOutline()
    x0, y0, x1, y1 = box
    for x, y in ((x0, y0), (x1, y0), (x1, y1), (x0, y1)):
        poly.Append(mm(OX + x), mm(OY + y))
    board.Add(zone)


def write_project(design, pcb_path):
    """Net classes live in the project file, which a first save writes with defaults; they are merged in afterwards
    and every later load and save keeps them. Footprints changed on purpose skip the library comparison."""
    rules = design["rules"]
    path = pcb_path.replace(".kicad_pcb", ".kicad_pro")
    project = json.load(open(path, encoding="utf-8"))
    classes = [{"name": "Default", "clearance": rules["clearance"], "track_width": rules["track_width"],
                "via_diameter": rules["via_diameter"], "via_drill": rules["via_drill"], "priority": 2147483647}]
    patterns = []
    for k, nc in enumerate(design.get("netclasses", [])):
        classes.append({"name": nc["name"], "clearance": nc.get("clearance", rules["clearance"]),
                        "track_width": nc.get("track_width", rules["track_width"]),
                        "via_diameter": rules["via_diameter"], "via_drill": rules["via_drill"], "priority": k})
        patterns += [{"netclass": nc["name"], "pattern": "/" + n} for n in nc["nets"]]
    project["net_settings"].update({"classes": classes, "netclass_patterns": patterns})
    if design.get("trim_silk_outside"):
        project["board"]["design_settings"]["rule_severities"]["lib_footprint_mismatch"] = "ignore"
    with open(path, "w", encoding="utf-8") as handle:
        json.dump(project, handle, indent=2)
    if design.get("dru"):
        with open(pcb_path.replace(".kicad_pcb", ".kicad_dru"), "w", encoding="utf-8") as handle:
            handle.write("(version 1)\n" + design["dru"].strip() + "\n")


def pad_point(board, spec):
    """'J1.A9' or ['J1.A9', dx, dy] (offset in mm) to a board position."""
    name, dx, dy = (spec, 0, 0) if isinstance(spec, str) else spec
    ref, number = name.split(".")
    pad = next(p for p in board.FindFootprintByReference(ref).Pads() if p.GetNumber() == number)
    pos = pad.GetPosition()
    return pcbnew.VECTOR2I(pos.x + mm(dx), pos.y + mm(dy))


def preroutes(board, design):
    """Fixed tracks for what an autorouter cannot do well (pin fields of fine-pitch connectors, pairs). A path is a list
    of pads ("J1.A4"), pads with an offset in mm (["J1.A4", 0, 1.5]) and "via", which drops a via at the current
    point and continues on the other side."""
    rules = design["rules"]
    for route in design.get("preroutes", []):
        side = route.get("side", "F")
        net = board.FindNet("/" + route["net"])
        last = None
        for step in route["path"]:
            if step == "via":
                via = pcbnew.PCB_VIA(board)
                via.SetPosition(last)
                via.SetWidth(mm(rules["via_diameter"]))
                via.SetDrill(mm(rules["via_drill"]))
                via.SetNet(net)
                via.SetLocked(True)
                board.Add(via)
                side = "B" if side == "F" else "F"
                continue
            point = pad_point(board, step)
            if last is not None:
                track = pcbnew.PCB_TRACK(board)
                track.SetStart(last)
                track.SetEnd(point)
                track.SetLayer(pcbnew.F_Cu if side == "F" else pcbnew.B_Cu)
                track.SetWidth(mm(route.get("width", rules["track_width"])))
                track.SetNet(net)
                track.SetLocked(True)
                board.Add(track)
            last = point


def fanout(board, design):
    """Every top-side SMD pad of the fan-out net gets a short track to its own via, straight away from its part, or
    sideways if that spot is taken (ICs: under their own body first); the pour on the other side connects it, so the
    router can leave the net alone. A small track keepout around the via on the other side keeps room for that pour."""
    spec = design.get("fanout")
    if not spec:
        return
    rules = design["rules"]
    via_d, clear = mm(rules["via_diameter"]), mm(rules["clearance"])
    net = board.FindNet("/" + spec["net"])
    pads = [p for fp in board.GetFootprints() for p in fp.Pads()]
    obstacles = pads + list(board.GetTracks())
    areas = [z.Outline() for z in board.Zones() if z.GetIsRuleArea() and z.GetDoNotAllowVias()]
    inside = pcbnew.BOX2I(at(0, 0), pcbnew.VECTOR2I(mm(design["board"]["width"]), mm(design["board"]["height"])))
    inside.Inflate(-(mm(0.5) + via_d // 2))
    placed = []
    for fp in board.GetFootprints():
        centre = fp.GetBoundingBox(False).GetCenter()
        for pad in fp.Pads():
            if pad.GetNetCode() != net.GetNetCode() or pad.GetAttribute() != pcbnew.PAD_ATTRIB_SMD \
                    or not pad.IsOnLayer(pcbnew.F_Cu):
                continue
            p = pad.GetPosition()
            dx, dy = p.x - centre.x, p.y - centre.y
            out = (1 if dx >= 0 else -1, 0) if abs(dx) >= abs(dy) else (0, 1 if dy >= 0 else -1)
            box = pad.GetBoundingBox()
            reach = max(box.GetWidth(), box.GetHeight()) / 2 + via_d / 2 + mm(0.5)
            directions = [out, (out[1], out[0]), (-out[1], -out[0])]
            if len(fp.Pads()) > 8:
                directions.insert(0, (-out[0], -out[1]))
            directions += [(out[0] + out[1], out[1] + out[0]), (out[0] - out[1], out[1] - out[0])]
            done = False
            for extra in (0, mm(0.6), mm(1.2), mm(2.0)):
                for ox, oy in directions:
                    norm = math.hypot(ox, oy)
                    spot = pcbnew.VECTOR2I(int(p.x + ox / norm * (reach + extra)), int(p.y + oy / norm * (reach + extra)))
                    via = pcbnew.PCB_VIA(board)
                    via.SetPosition(spot)
                    via.SetWidth(via_d)
                    via.SetDrill(mm(rules["via_drill"]))
                    via.SetNet(net)
                    track = pcbnew.PCB_TRACK(board)
                    track.SetStart(p)
                    track.SetEnd(spot)
                    track.SetWidth(mm(0.4 if extra == 0 else rules["track_width"]))
                    track.SetLayer(pcbnew.F_Cu)
                    track.SetNet(net)
                    shapes = [via.GetEffectiveShape(pcbnew.F_Cu), track.GetEffectiveShape(pcbnew.F_Cu)]
                    blocked = not inside.Contains(spot) or any(a.Contains(spot) for a in areas) or any(
                        o.GetNetCode() != net.GetNetCode() and o.IsOnLayer(pcbnew.F_Cu) and
                        any(o.GetEffectiveShape(pcbnew.F_Cu).Collide(sh, clear) for sh in shapes) for o in obstacles)                         or any((v - spot).EuclideanNorm() < via_d + clear for v in placed)                         or any(o.GetNetCode() != net.GetNetCode() and o.IsOnLayer(pcbnew.B_Cu) and
                               o.GetEffectiveShape(pcbnew.B_Cu).Collide(via.GetEffectiveShape(pcbnew.B_Cu), clear)
                               for o in obstacles)
                    if blocked:
                        continue
                    board.Add(via)
                    board.Add(track)
                    placed.append(spot)
                    ring = mm(rules["via_diameter"] / 2 + 0.6)
                    x, y = pcbnew.ToMM(spot.x) - OX, pcbnew.ToMM(spot.y) - OY
                    r = pcbnew.ToMM(ring)
                    rule_area(board, (x - r, y - r, x + r, y + r), "B", "fan-out " + net.GetNetname(), vias=True)
                    done = True
                    break
                if done:
                    break
            if not done:
                print(f"no fan-out via for {fp.GetReference()} pad {pad.GetNumber()}; it relies on the pour of its layer")


def trim_silk(board, design):
    edge_y = at(0, 0.6).y
    for ref in design.get("trim_silk_outside", []):
        fp = board.FindFootprintByReference(ref)
        for item in list(fp.GraphicalItems()):
            box = item.GetBoundingBox()
            if item.GetLayer() in (pcbnew.F_SilkS, pcbnew.B_SilkS) and box.GetTop() < edge_y:
                fp.Remove(item)


def place(design_path, lib_dir, out):
    design = Design(design_path)
    b = design["board"]
    board = pcbnew.BOARD()
    board.GetDesignSettings().SetBoardThickness(mm(b.get("thickness", 1.6)))
    outline(board, b["width"], b["height"], b.get("corner", 0))
    nets = {}
    for net in design.nets():
        nets[net] = pcbnew.NETINFO_ITEM(board, "/" + net)
        board.Add(nets[net])
    for part in design.parts:
        ref = part["ref"]
        pin_nets = dict(part.get("pins", {}))
        for number, name in part.get("nc", {}).items():
            key = f"nc:{ref}:{number}"
            nets[key] = pcbnew.NETINFO_ITEM(board, f"unconnected-({ref}-{name}-Pad{number})")
            board.Add(nets[key])
            pin_nets[number] = key
        lib, name = part["footprint"].split(":")
        fp = pcbnew.FootprintLoad(f"{lib_dir}/{lib}.pretty", name)
        fp.SetFPID(pcbnew.LIB_ID(lib, name))
        fp.SetReference(ref)
        fp.SetValue(part["value"])
        fp.Value().SetVisible(False)
        fp.SetPath(pcbnew.KIID_PATH("/" + design.uid(ref)))
        bom = pcbnew.FP_EXCLUDE_FROM_BOM
        fp.SetAttributes(fp.GetAttributes() & ~bom if part.get("bom", True) else fp.GetAttributes() | bom)
        board.Add(fp)
        fp.SetPosition(at(*part["at"]))
        fp.SetOrientationDegrees(part.get("rot", 0))
        if part.get("side", "F") == "B":
            fp.Flip(fp.GetPosition(), pcbnew.FLIP_DIRECTION_LEFT_RIGHT)
        if part.get("anchor", "centre") != "pin1":
            centre = fp.GetBoundingBox(False).GetCenter()
            target = at(*part["at"])
            fp.Move(pcbnew.VECTOR2I(target.x - centre.x, target.y - centre.y))
        for pad in fp.Pads():
            if pad.GetNumber() in pin_nets:
                pad.SetNet(nets[pin_nets[pad.GetNumber()]])
    preroutes(board, design)
    trim_silk(board, design)
    for text in design.get("texts", []):
        label = new_text(board, fill_text(design, text["text"]), pcbnew.F_SilkS if text.get("side", "F") == "F" else pcbnew.B_SilkS,
                         text.get("size", 1.0))
        label.SetPosition(at(*text["at"]))
        board.Add(label)
    for keepout in design.get("keepouts", []):
        rule_area(board, keepout["box"], keepout.get("side", "F"), keepout["name"])
    fanout(board, design)
    missing = label_board(board, design)
    board.Save(out)
    write_project(design, out)
    return missing


def fill_text(design, text):
    return text.format(revision=design.get("revision", ""), month=datetime.date.today().strftime("%Y-%m"),
                       title=design.get("title", design["project"]))


def label_board(board, design):
    """References with value or function next to each part (LB-1, LB-2); returns what only fits the assembly
    drawing. Texts from design.json stay; everything else on the silkscreen layers is placed again."""
    fixed = {fill_text(design, t["text"]) for t in design.get("texts", [])}
    for item in list(board.GetDrawings()):
        if isinstance(item, pcbnew.PCB_TEXT) and item.GetLayer() in (pcbnew.F_SilkS, pcbnew.B_SilkS) \
                and item.GetText() not in fixed:
            board.Delete(item)
    b = design["board"]
    labeller = Labeller(board, at(0.6, 0.6), mm(b["width"] - 1.2), mm(b["height"] - 1.2))
    missing = []
    connectors_first = sorted(design.parts, key=lambda p: (not p["ref"].startswith("J"), p["ref"]))
    for part in connectors_first:
        fp = board.FindFootprintByReference(part["ref"])
        fp.Reference().SetVisible(False)
        layer = pcbnew.B_SilkS if fp.GetLayer() == pcbnew.B_Cu else pcbnew.F_SilkS
        ref = part["ref"]
        caption = ref if part.get("caption") == "ref" else f"{ref} {part.get('label') or part['value']}"
        done = False
        for value in dict.fromkeys((caption, ref)):
            for angle in (0, 90):
                text = new_text(board, value, layer)
                text.SetTextAngleDegrees(angle)
                if labeller.place(text, around(fp, text), fp):
                    board.Add(text)
                    done = True
                    break
            if done:
                if value != caption:
                    missing.append(f"{ref} (value)")
                break
        if not done:
            for angle in (0, 90):
                text = new_text(board, ref, layer)
                text.SetTextAngleDegrees(angle)
                if labeller.place(text, around(fp, text)[:16]):
                    board.Add(text)
                    done = True
                    missing.append(f"{ref} (value)" if caption != ref else ref)
                    break
        if not done:
            missing.append(ref)
    return missing


def pour(board, design):
    """Pours on both layers for every net class marked "pour", stitched with vias on a 5 mm grid wherever both pours
    cover the spot; without stitching, tracks cut a two-layer board's pour into islands. Earlier pours and free-standing
    stitching vias of the net are replaced, so the step can run again after a change."""
    rules = design["rules"]
    nets = [n for nc in design.get("netclasses", []) if nc.get("pour") for n in nc["nets"]]
    b = design["board"]
    for net_name in nets:
        net = board.FindNet("/" + net_name)
        for zone in list(board.Zones()):
            if not zone.GetIsRuleArea() and zone.GetNetCode() == net.GetNetCode():
                board.Delete(zone)
        ends = {(p.x, p.y) for t in board.GetTracks() if t.Type() == pcbnew.PCB_TRACE_T
                and t.GetNetCode() == net.GetNetCode() for p in (t.GetStart(), t.GetEnd())}
        for via in [t for t in board.GetTracks() if t.Type() == pcbnew.PCB_VIA_T]:
            if via.GetNetCode() == net.GetNetCode() and not via.IsLocked() and                     (via.GetPosition().x, via.GetPosition().y) not in ends:
                board.Delete(via)
        for layer, priority in ((pcbnew.B_Cu, 0), (pcbnew.F_Cu, 1)):
            zone = pcbnew.ZONE(board)
            zone.SetLayer(layer)
            zone.SetNet(net)
            zone.SetLocalClearance(mm(0.3))
            zone.SetMinThickness(mm(0.3))
            zone.SetPadConnection(pcbnew.ZONE_CONNECTION_THERMAL)
            zone.SetThermalReliefSpokeWidth(mm(0.5))
            zone.SetThermalReliefGap(mm(0.4))
            zone.SetAssignedPriority(priority)
            zone.SetIslandRemovalMode(pcbnew.ISLAND_REMOVAL_MODE_ALWAYS)
            poly = zone.Outline()
            poly.NewOutline()
            for x, y in ((0, 0), (b["width"], 0), (b["width"], b["height"]), (0, b["height"])):
                poly.Append(mm(OX + x), mm(OY + y))
            board.Add(zone)
        for fp in board.GetFootprints():
            for pad in fp.Pads():
                solid = (pad.GetAttribute() == pcbnew.PAD_ATTRIB_SMD and pad.IsOnLayer(pcbnew.B_Cu)) \
                    or fp.GetReference() in design.get("solid_pads", [])
                if solid and pad.GetNetCode() == net.GetNetCode():
                    pad.SetLocalZoneConnection(pcbnew.ZONE_CONNECTION_FULL)
        filler = pcbnew.ZONE_FILLER(board)
        filler.Fill(board.Zones())
        keep = mm(rules["via_diameter"] / 2 + 0.35)
        pours = [z for z in board.Zones() if not z.GetIsRuleArea() and z.GetNetCode() == net.GetNetCode()]
        areas = [z.Outline() for z in board.Zones() if z.GetIsRuleArea() and z.GetDoNotAllowVias()]
        for gx in range(4, int(b["width"]) - 2, 5):
            for gy in range(3, int(b["height"]) - 2, 5):
                spot = at(gx, gy)
                if any(a.Contains(spot) for a in areas):
                    continue
                ring = pcbnew.SHAPE_POLY_SET()
                ring.NewOutline()
                for k in range(16):
                    angle = 2 * math.pi * k / 16
                    ring.Append(int(spot.x + keep * math.cos(angle)), int(spot.y + keep * math.sin(angle)))
                if all(covers(z, ring) for z in pours):
                    via = pcbnew.PCB_VIA(board)
                    via.SetPosition(spot)
                    via.SetWidth(mm(rules["via_diameter"]))
                    via.SetDrill(mm(rules["via_drill"]))
                    via.SetNet(net)
                    board.Add(via)
        filler.Fill(board.Zones())
        for _ in range(3):
            if not stitch_islands(board, net, pours, rules):
                break
            filler.Fill(board.Zones())


def pour_groups(board, net, pours):
    """Pour pieces grouped by what joins them: vias and through-hole pads (both layers), SMD pads and tracks (own
    layer), track ends meeting at a pad, via or other track. Returns [(layer, filled set, piece index, group)]."""
    parent = {}

    def find(a):
        parent.setdefault(a, a)
        while parent[a] != a:
            parent[a] = parent[parent[a]]
            a = parent[a]
        return a

    def union(a, b):
        parent[find(a)] = find(b)

    pieces = []
    for zone in pours:
        filled = zone.GetFilledPolysList(zone.GetLayer())
        for k in range(filled.OutlineCount()):
            pieces.append((zone.GetLayer(), filled.UnitSet(k), ("piece", zone.GetLayer(), k)))
    code = net.GetNetCode()
    items = [("pad", p) for fp in board.GetFootprints() for p in fp.Pads() if p.GetNetCode() == code]
    items += [("track", t) for t in board.GetTracks() if t.GetNetCode() == code]
    for kind, item in items:
        for layer, shape_set, key in pieces:
            if item.IsOnLayer(layer) and shape_set.Collide(item.GetEffectiveShape(layer)):
                union(key, id(item))
    tracks = [t for kind, t in items if kind == "track"]
    for a in tracks:
        for b in items:
            if b[1] is not a and any(b[1].IsOnLayer(l) and a.IsOnLayer(l) and
                                     b[1].GetEffectiveShape(l).Collide(a.GetEffectiveShape(l)) for l in (pcbnew.F_Cu, pcbnew.B_Cu)):
                union(id(a), id(b[1]))
    return [(layer, shape_set, key, find(key)) for layer, shape_set, key in pieces]


def stitch_islands(board, net, pours, rules):
    """Pour pieces not joined to the largest group get a via where they overlap a piece of that group on the other
    layer. Returns whether any via was added."""
    groups = pour_groups(board, net, pours)
    sizes = {}
    for layer, shape_set, key, group in groups:
        sizes[group] = sizes.get(group, 0) + shape_set.Area()
    if len(sizes) < 2:
        return False
    main = max(sizes, key=sizes.get)
    added, fixed = False, set()
    for layer, shape_set, key, group in groups:
        if group == main or group in fixed:
            continue
        targets = [g[1] for g in groups if g[3] == main and g[0] != layer]
        box = shape_set.BBox()
        spot = None
        for margin in (0.35, 0.05):
            keep = mm(rules["via_diameter"] / 2 + margin)
            for x in range(box.GetLeft(), box.GetRight(), mm(0.1)):
                for y in range(box.GetTop(), box.GetBottom(), mm(0.1)):
                    ring = [pcbnew.VECTOR2I(int(x + keep * math.cos(2 * math.pi * k / 16)),
                                            int(y + keep * math.sin(2 * math.pi * k / 16))) for k in range(16)]
                    ring.append(pcbnew.VECTOR2I(x, y))
                    if all(shape_set.Contains(p) for p in ring) and                             any(all(t.Contains(p) for p in ring) for t in targets):
                        spot = pcbnew.VECTOR2I(x, y)
                        break
                if spot:
                    break
            if spot:
                break
        if spot:
            via = pcbnew.PCB_VIA(board)
            via.SetPosition(spot)
            via.SetWidth(mm(rules["via_diameter"]))
            via.SetDrill(mm(rules["via_drill"]))
            via.SetNet(net)
            board.Add(via)
            fixed.add(group)
            added = True
        else:
            print(f"pour island of {net.GetNetname()} on {board.GetLayerName(layer)} near "
                  f"({pcbnew.ToMM(box.GetCenter().x) - OX:.1f}, {pcbnew.ToMM(box.GetCenter().y) - OY:.1f}) "
                  "has no spot for a stitching via")
    return added


def covers(zone, ring):
    rest = pcbnew.SHAPE_POLY_SET(ring)
    rest.BooleanSubtract(pcbnew.SHAPE_POLY_SET(zone.GetFilledPolysList(zone.GetLayer())))
    return rest.OutlineCount() == 0


def finish(design_path, pcb_path):
    design = Design(design_path)
    board = pcbnew.LoadBoard(pcb_path)
    clearance = mm(design["rules"]["clearance"])
    pads = [p for fp in board.GetFootprints() for p in fp.Pads()]
    for track in board.GetTracks():
        if track.Type() == pcbnew.PCB_TRACE_T and track.GetWidth() < mm(design["rules"].get("min_track", 0.2)):
            old = track.GetWidth()
            track.SetWidth(mm(design["rules"].get("min_track", 0.2)))
            shape = track.GetEffectiveShape(track.GetLayer())
            if any(p.GetNetCode() != track.GetNetCode() and p.IsOnLayer(track.GetLayer())
                   and p.GetEffectiveShape(track.GetLayer()).Collide(shape, clearance) for p in pads):
                track.SetWidth(old)
    missing = label_board(board, design)
    pour(board, design)
    board.Save(pcb_path)
    write_project(design, pcb_path)
    with open(pcb_path.replace(".kicad_pcb", "-labels.txt"), "w", encoding="utf-8") as handle:
        handle.write("\n".join(missing))
    return missing
