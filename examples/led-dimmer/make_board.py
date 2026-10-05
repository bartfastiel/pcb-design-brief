"""Builds the example board: a 5 V LED-strip dimmer (low-side N-MOSFET, PWM input), 40 x 24 mm, hand-solder footprints.
Run with KiCad's Python: python make_board.py <KiCad footprint dir> led-dimmer.kicad_pcb"""
import sys

import pcbnew

OX, OY = 100.0, 100.0
W, H = 40.0, 24.0
PARTS = [
    ("J1", "Connector_PinHeader_2.54mm", "PinHeader_1x02_P2.54mm_Vertical", "5V in", (4, 8), 0, ["VIN", "GND"]),
    ("J2", "Connector_PinHeader_2.54mm", "PinHeader_1x02_P2.54mm_Vertical", "LED strip", (36, 8), 0, ["VIN", "DRAIN"]),
    ("J3", "Connector_PinHeader_2.54mm", "PinHeader_1x02_P2.54mm_Vertical", "PWM", (4, 16), 0, ["PWM", "GND"]),
    ("C1", "Capacitor_SMD", "C_0805_2012Metric_Pad1.18x1.45mm_HandSolder", "10u", (11, 5), 0, ["VIN", "GND"]),
    ("R1", "Resistor_SMD", "R_0805_2012Metric_Pad1.20x1.40mm_HandSolder", "100R", (12, 16), 0, ["PWM", "GATE"]),
    ("R2", "Resistor_SMD", "R_0805_2012Metric_Pad1.20x1.40mm_HandSolder", "100k", (19, 19), 0, ["GATE", "GND"]),
    ("Q1", "Package_TO_SOT_SMD", "SOT-23_Handsoldering", "AO3400A", (24, 14), 0, ["GATE", "GND", "DRAIN"]),
]
TRACKS = [
    ("VIN", "F", 1.0, [(4, 8), (36, 8)]), ("VIN", "F", 1.0, [(10, 5), (10, 8)]),
    ("GND", "F", 1.0, [(12, 5), (14, 5)]), ("GND", "B", 1.0, [(14, 5), (14, 10.54), (4, 10.54)]),
    ("GND", "B", 1.0, [(6.5, 10.54), (6.5, 21), (22.5, 21), (22.5, 17.5)]), ("GND", "B", 1.0, [(4, 18.54), (4, 21), (6.5, 21)]),
    ("GND", "F", 0.8, [(22.5, 14.95), (22.5, 17.5)]), ("GND", "F", 0.5, [(20, 19), (20, 21)]),
    ("PWM", "F", 0.5, [(4, 16), (11, 16)]),
    ("GATE", "F", 0.5, [(13, 16), (16, 16), (16, 13.05), (22.5, 13.05)]), ("GATE", "F", 0.5, [(16, 16), (16, 19), (18, 19)]),
    ("DRAIN", "F", 1.0, [(25.5, 14), (30, 14), (30, 10.54), (36, 10.54)]),
]
VIAS = [("GND", (14, 5)), ("GND", (22.5, 17.5)), ("GND", (20, 21))]


def at(x, y):
    return pcbnew.VECTOR2I(pcbnew.FromMM(OX + x), pcbnew.FromMM(OY + y))


def main():
    lib_dir, out = sys.argv[1], sys.argv[2]
    board = pcbnew.BOARD()
    board.GetDesignSettings().SetBoardThickness(pcbnew.FromMM(1.6))
    nets = {}
    for name in ("VIN", "GND", "PWM", "GATE", "DRAIN"):
        nets[name] = pcbnew.NETINFO_ITEM(board, name)
        board.Add(nets[name])
    corners = [(0, 0), (W, 0), (W, H), (0, H)]
    for (x0, y0), (x1, y1) in zip(corners, corners[1:] + corners[:1]):
        edge = pcbnew.PCB_SHAPE(board)
        edge.SetShape(pcbnew.SHAPE_T_SEGMENT)
        edge.SetStart(at(x0, y0))
        edge.SetEnd(at(x1, y1))
        edge.SetLayer(pcbnew.Edge_Cuts)
        edge.SetWidth(pcbnew.FromMM(0.1))
        board.Add(edge)
    for ref, lib, name, value, (x, y), rot, pad_nets in PARTS:
        fp = pcbnew.FootprintLoad(f"{lib_dir}/{lib}.pretty", name)
        fp.SetReference(ref)
        fp.SetValue(value)
        fp.Value().SetVisible(False)
        fp.SetPosition(at(x, y))
        fp.SetOrientationDegrees(rot)
        for pad, net in zip(sorted(fp.Pads(), key=lambda p: p.GetNumber()), pad_nets):
            pad.SetNet(nets[net])
        board.Add(fp)
    for net, side, width, points in TRACKS:
        for (x0, y0), (x1, y1) in zip(points, points[1:]):
            track = pcbnew.PCB_TRACK(board)
            track.SetStart(at(x0, y0))
            track.SetEnd(at(x1, y1))
            track.SetWidth(pcbnew.FromMM(width))
            track.SetLayer(pcbnew.F_Cu if side == "F" else pcbnew.B_Cu)
            track.SetNet(nets[net])
            board.Add(track)
    for net, (x, y) in VIAS:
        via = pcbnew.PCB_VIA(board)
        via.SetPosition(at(x, y))
        via.SetWidth(pcbnew.FromMM(1.2))
        via.SetDrill(pcbnew.FromMM(0.6))
        via.SetNet(nets[net])
        board.Add(via)
    for text, (x, y), layer, mirrored in (("5 V LED dimmer", (31, 19.5), pcbnew.F_SilkS, False),
                                          ("IN  OUT  PWM", (20, 3), pcbnew.B_SilkS, True)):
        label = pcbnew.PCB_TEXT(board)
        label.SetText(text)
        label.SetPosition(at(x, y))
        label.SetLayer(layer)
        label.SetTextSize(pcbnew.VECTOR2I(pcbnew.FromMM(1.2), pcbnew.FromMM(1.2)))
        label.SetTextThickness(pcbnew.FromMM(0.18))
        label.SetMirrored(mirrored)
        board.Add(label)
    board.Save(out)
    print(out)


if __name__ == "__main__":
    main()
