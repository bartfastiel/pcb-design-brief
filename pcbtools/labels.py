"""Silkscreen labelling (brief §5a): texts placed one after the other where they hit no pad, via, silkscreen, board
edge or earlier text, and only where their own part is the nearest one. Needs pcbnew."""
import math

import pcbnew

TEXT, STROKE, MARGIN = 1.0, 0.15, 0.2


def mm(v):
    return pcbnew.FromMM(v)


def new_text(board, value, layer, size=TEXT):
    label = pcbnew.PCB_TEXT(board)
    label.SetText(value)
    label.SetLayer(layer)
    label.SetTextSize(pcbnew.VECTOR2I(mm(size), mm(size)))
    label.SetTextThickness(mm(STROKE * max(size, 1.0)))
    label.SetMirrored(layer == pcbnew.B_SilkS)
    return label


def around(fp, item):
    """Candidate centres around a footprint, nearest first: above, below, left, right, corners, then further out."""
    box = fp.GetBoundingBox(False)
    w, h = item.GetBoundingBox().GetWidth(), item.GetBoundingBox().GetHeight()
    cx, cy = box.GetCenter().x, box.GetCenter().y
    spots = []
    for gap in (0.3, 0.9, 1.5):
        g = mm(gap)
        left, right = box.GetLeft() - g - w // 2, box.GetRight() + g + w // 2
        top, bottom = box.GetTop() - g - h // 2, box.GetBottom() + g + h // 2
        spots += [(cx, top), (cx, bottom), (left, cy), (right, cy), (left, top), (right, top), (left, bottom),
                  (right, bottom)]
    return spots


class Labeller:
    def __init__(self, board, origin, width, height):
        self.taken = {pcbnew.F_SilkS: [], pcbnew.B_SilkS: []}
        self.footprints = [fp for fp in board.GetFootprints() if not fp.GetReference().startswith(("JK", "H"))]
        self.inner = pcbnew.BOX2I(origin, pcbnew.VECTOR2I(width, height))
        margin = mm(MARGIN)
        for fp in board.GetFootprints():
            for pad in fp.Pads():
                for layer, copper in ((pcbnew.F_SilkS, pcbnew.F_Cu), (pcbnew.B_SilkS, pcbnew.B_Cu)):
                    if pad.IsOnLayer(copper):
                        self.block(layer, pad.GetBoundingBox(), margin)
            for item in fp.GraphicalItems():
                if item.GetLayer() in self.taken:
                    self.block(item.GetLayer(), item.GetBoundingBox(), margin)
        for track in board.GetTracks():
            if track.Type() == pcbnew.PCB_VIA_T:
                for layer in self.taken:
                    self.block(layer, track.GetBoundingBox(), margin)
        for item in board.GetDrawings():
            if item.GetLayer() in self.taken:
                self.block(item.GetLayer(), item.GetBoundingBox(), margin)

    def block(self, layer, box, margin):
        box = pcbnew.BOX2I(box.GetOrigin(), box.GetSize())
        box.Inflate(margin)
        self.taken[layer].append(box)

    def fits(self, item):
        box = item.GetBoundingBox()
        return self.inner.Contains(box.GetOrigin()) and self.inner.Contains(box.GetEnd()) and \
            not any(box.Intersects(t) for t in self.taken[item.GetLayer()])

    def nearest_is(self, item, owner):
        """A label belongs to the part it is closest to (within 1.5 mm); otherwise a reader pins it on a neighbour."""
        if owner is None:
            return True
        centre = item.GetBoundingBox().GetCenter()

        def distance(fp):
            box = fp.GetBoundingBox(False)
            dx = max(box.GetLeft() - centre.x, 0, centre.x - box.GetRight())
            dy = max(box.GetTop() - centre.y, 0, centre.y - box.GetBottom())
            return math.hypot(dx, dy)

        same_side = [fp for fp in self.footprints
                     if fp.GetLayer() == owner.GetLayer() or fp.GetAttributes() & pcbnew.FP_THROUGH_HOLE]
        return distance(owner) <= min(distance(fp) for fp in same_side) + mm(1.5)

    def place(self, item, spots, owner=None):
        for x, y in spots:
            item.SetPosition(pcbnew.VECTOR2I(int(x), int(y)))
            if self.fits(item) and self.nearest_is(item, owner):
                self.block(item.GetLayer(), item.GetBoundingBox(), mm(MARGIN))
                return True
        return False
