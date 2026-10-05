"""Project skeleton: the intake form, a design.json with board, rules and one example part, an empty BOM options file
and a .gitignore for the generated files. Existing files are never overwritten."""
import json
import os
import shutil

from .design import dump

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def init(folder, name=None):
    name = name or os.path.basename(os.path.abspath(folder))
    os.makedirs(folder, exist_ok=True)
    files = {
        "intake.md": lambda path: shutil.copy(os.path.join(REPO, "templates", "intake.md"), path),
        "design.json": lambda path: dump({
            "project": name, "title": name.replace("-", " "), "revision": "rev 1",
            "board": {"width": 50, "height": 30, "corner": 3, "thickness": 1.6},
            "rules": {"clearance": 0.2, "track_width": 0.3, "via_diameter": 0.9, "via_drill": 0.45, "min_track": 0.2},
            "netclasses": [{"name": "Power", "track_width": 0.6, "nets": ["+5V"]},
                           {"name": "Ground", "track_width": 0.6, "nets": ["GND"], "pour": True, "route": False}],
            "fanout": {"net": "GND"},
            "texts": [{"text": "{title} {revision} {month}", "at": [25, 28], "side": "B", "size": 1.0}],
            "flags": [], "notes": [],
            "parts": [
                {"ref": "J1", "symbol": "Connector_Generic:Conn_01x02", "value": "5V in",
                 "footprint": "Connector_PinHeader_2.54mm:PinHeader_1x02_P2.54mm_Vertical", "sch": [38.1, 50.8],
                 "at": [6, 15], "rot": 0, "side": "F", "pins": {"1": "+5V", "2": "GND"}, "caption": "ref"},
                {"ref": "R1", "symbol": "Device:R", "value": "1k",
                 "footprint": "Resistor_SMD:R_0805_2012Metric_Pad1.20x1.40mm_HandSolder", "sch": [63.5, 50.8],
                 "at": [22, 15], "rot": 0, "side": "F", "pins": {"1": "+5V", "2": "LED_A"}},
                {"ref": "D1", "symbol": "Device:LED", "value": "red",
                 "footprint": "LED_SMD:LED_0805_2012Metric_Pad1.15x1.40mm_HandSolder", "sch": [88.9, 50.8],
                 "at": [32, 15], "rot": 0, "side": "F", "pins": {"1": "GND", "2": "LED_A"}}]},
            path),
        "bom-options.json": lambda path: json.dump({"series": 1, "costs": {"unique_part": 0.0, "placement": 0.0,
                                                                           "shipping": {}},
                                                    "lines": [], "mpn": {}, "offers": {}}, open(path, "w"), indent=1),
        ".gitignore": lambda path: open(path, "w").write("build/\n*-backups/\n*.kicad_prl\nfp-info-cache\n"
                                                         "offers.json\n"),
    }
    for filename, write in files.items():
        path = os.path.join(folder, filename)
        if os.path.exists(path):
            print(f"kept     {path}")
        else:
            write(path)
            print(f"created  {path}")
    print("next: fill in intake.md, then edit design.json and run `python -m pcbtools schematic design.json`")
