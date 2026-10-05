"""The design as data: one JSON file the agent writes, read by every tool. Lengths in mm, board origin top-left,
y down (KiCad convention).

{
  "project": "usb-gamepad", "title": "USB gamepad", "revision": "rev 1",
  "board": {"width": 86, "height": 40, "corner": 6, "thickness": 1.6},
  "rules": {"clearance": 0.2, "track_width": 0.3, "via_diameter": 0.9, "via_drill": 0.45, "min_track": 0.2},
  "netclasses": [{"name": "Power", "track_width": 0.6, "nets": ["VBUS", "+5V"]},
                 {"name": "Ground", "track_width": 0.6, "nets": ["GND"], "pour": true}],
  "dru": "(rule ...)",                                    optional KiCad custom rules, written to <project>.kicad_dru
  "parts": [{"ref": "R1", "symbol": "Device:R", "value": "22R",
             "footprint": "Resistor_SMD:R_0805_2012Metric_Pad1.20x1.40mm_HandSolder",
             "sch": [106.68, 71.12],                          schematic position (A3 sheet, mm)
             "at": [45, 22.5], "rot": 0, "side": "F",          board position of the part's centre
             "anchor": "centre",                               or "pin1": "at" is the footprint origin
             "pins": {"1": "USB_DM_C", "2": "USB_DM"},
             "nc": {"A8": "SBU1"},                             unused pins: number -> pin name
             "label": "UP",                                    optional function text next to the reference
             "bom": true}],
  "flags": [{"net": "GND", "sch": [215.9, 200.66]}],          power flags for nets fed from a connector
  "notes": [{"sch": [25.4, 27.94], "text": "..."}],          schematic notes per functional group
  "texts": [{"text": "USB gamepad", "at": [58.2, 4], "side": "B", "size": 1.2}],   fixed silkscreen texts
  "keepouts": [{"name": "bottom title", "box": [52.8, 2, 65, 17.2], "side": "B"}], no vias or tracks
  "preroutes": [{"net": "VBUS", "side": "B", "width": 0.6,
                 "path": ["J1.A9", ["J1.A9", 0, 1.5], ["J1.A4", 0, 1.5], "J1.A4"]}],   pad, or pad plus offset
  "fanout": {"net": "GND"},                                 a via next to every top SMD pad of that net
  "trim_silk_outside": ["J1"]                               footprints whose silkscreen beyond the edge is removed
}"""
import json
import uuid


class Design:
    def __init__(self, path):
        self.path = path
        self.data = json.load(open(path, encoding="utf-8"))
        self.root = uuid.uuid5(uuid.NAMESPACE_URL, "pcbtools/" + self.data["project"])

    def __getitem__(self, key):
        return self.data[key]

    def get(self, key, default=None):
        return self.data.get(key, default)

    @property
    def parts(self):
        return self.data["parts"]

    def part(self, ref):
        return next(p for p in self.parts if p["ref"] == ref)

    def uid(self, *parts):
        return str(uuid.uuid5(self.root, "/".join(parts)))

    def netclass_of(self, net):
        for nc in self.data.get("netclasses", []):
            if net in nc["nets"]:
                return nc["name"]
        return "Default"

    def nets(self):
        found = []
        for part in self.parts:
            for net in part.get("pins", {}).values():
                if net not in found:
                    found.append(net)
        return found


def dump(data, path):
    """One line per part, note or text, so a diff shows which part moved."""
    lines = ["{"]
    keys = list(data)
    for k, key in enumerate(keys):
        value = data[key]
        end = "," if k < len(keys) - 1 else ""
        if isinstance(value, list) and value and isinstance(value[0], dict):
            lines.append(f' "{key}": [')
            lines += [f"  {json.dumps(item, ensure_ascii=False)}{',' if i < len(value) - 1 else ''}"
                      for i, item in enumerate(value)]
            lines.append(f" ]{end}")
        else:
            lines.append(f' "{key}": {json.dumps(value, ensure_ascii=False)}{end}')
    lines.append("}")
    with open(path, "w", encoding="utf-8", newline="\n") as handle:
        handle.write("\n".join(lines) + "\n")
