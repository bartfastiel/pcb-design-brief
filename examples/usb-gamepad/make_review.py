"""Collects the build results of the example into the Blender scenes and review.json for scripts/review/review_pdf.py.
Usage: python make_review.py <build dir>. Suppliers, fabs, assemblers and prices in this example are fictional."""
import hashlib
import json
import os
import sys

DESIGN = json.load(open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "design.json"), encoding="utf-8"))
BOARD_W, BOARD_H = DESIGN["board"]["width"], DESIGN["board"]["height"]

BUILD = sys.argv[1]
HERE = os.path.dirname(os.path.abspath(__file__))
SERIES = 25
GREY = {"color": [0.12, 0.12, 0.13], "roughness": 0.45}
CAP = {"color": [0.55, 0.08, 0.06], "roughness": 0.35}
NYLON = {"color": [0.86, 0.85, 0.8], "roughness": 0.45}
BRASS = {"color": [0.78, 0.56, 0.22], "metallic": 1.0, "roughness": 0.3}
Z_BOARD = 5.0


def rel(path):
    return os.path.relpath(os.path.join(BUILD, path), HERE).replace("\\", "/")


def scenes():
    enclosure = "../enclosure/"
    explode = {"screws": -16, "base": 0, "board": 16, "inserts": 30, "caps": 32, "top": 44}
    parts = [
        {"name": "base", "file": enclosure + "base.stl", "offset": [0, 0, explode["base"]], "material": GREY},
        {"name": "board", "file": "board.glb", "offset": [0, BOARD_H, Z_BOARD + explode["board"]], "uniform_finish": True},
        {"name": "caps", "file": enclosure + "caps.stl", "offset": [0, 0, explode["caps"]], "material": CAP, "smooth": True},
        {"name": "inserts", "file": enclosure + "inserts.stl", "offset": [0, 0, explode["inserts"]], "material": BRASS,
         "smooth": True},
        {"name": "top", "file": enclosure + "top.stl", "offset": [0, 0, explode["top"]], "material": GREY},
        {"name": "screws", "file": enclosure + "screws.stl", "offset": [0, 0, explode["screws"]], "material": NYLON,
         "smooth": True},
        {"name": "cable", "box": [[37.6, BOARD_H + 14, Z_BOARD + 2.3 + explode["board"] - 1.3],
                                  [48.4, BOARD_H + 34, Z_BOARD + 2.3 + explode["board"] + 1.3]], "bevel": 1.2,
         "material": GREY},
        {"name": "cable", "box": [[39.0, BOARD_H + 6, Z_BOARD + 2.3 + explode["board"] - 1.0],
                                  [47.0, BOARD_H + 14, Z_BOARD + 2.3 + explode["board"] + 1.0]],
         "material": {"color": [0.8, 0.8, 0.82], "metallic": 1.0, "roughness": 0.25}},
        {"name": "cable", "curve": [[43, BOARD_H + 33, Z_BOARD + 18.3], [43, BOARD_H + 55, Z_BOARD + 18.3],
                                    [60, BOARD_H + 75, Z_BOARD + 5]], "radius": 1.6, "material": GREY},
    ]
    os.makedirs(os.path.join(BUILD, "3d"), exist_ok=True)
    common = {"samples": 128, "light": 0.5, "ambient": 0.3}
    for name, spec in (
            ("scene-overview.json", dict(common, size="2400x1500", camera={"elevation": 32, "azimuth": -30, "lens": 55,
                                                                           "margin": 1.04}, parts=parts)),
            ("scene-board.json", dict(common, size="2200x1300", light=0.18, camera={"elevation": 38, "azimuth": -25,
                                                                                    "lens": 70, "margin": 1.04},
                                      parts=[{"name": "board", "file": "board.glb", "uniform_finish": True}])),
            ("scene-parts-top.json", {"size": f"{int((BOARD_W + 2) * 20)}x{int((BOARD_H + 2) * 20)}", "samples": 64,
                                      "light": 0.08, "ambient": 0.6,
                                      "camera": {"elevation": 90, "azimuth": 0, "roll": 180,
                                                 "ortho": [BOARD_W / 2, -BOARD_H / 2, BOARD_W + 2]},
                                      "parts": [{"name": "parts", "file": "parts.glb"}]})):
        with open(os.path.join(BUILD, "3d", name), "w", encoding="utf-8") as handle:
            json.dump(spec, handle, indent=1)


def load(name):
    return json.load(open(os.path.join(BUILD, name), encoding="utf-8"))


def review():
    bom = json.load(open(os.path.join(HERE, "bom-options.json"), encoding="utf-8"))
    cost = load("bom-result.json")
    enclosure = load("enclosure/enclosure.json")
    missing = open(os.path.join(BUILD, "usb-gamepad-labels.txt"), encoding="utf-8").read().splitlines()
    parts_net = cost["optimised"]["parts"] + cost["optimised"]["shipping"]
    pcb, assembly_kit, case = 61.90, 0.0, 0.62 * SERIES
    total = parts_net * 1.19 + pcb + case
    w, h, t = enclosure["outer_mm"]
    by_supplier = {}
    for part, d in cost["optimised"]["detail"].items():
        by_supplier.setdefault(d["supplier"], []).append((part, d))
    refs = {}
    for line in bom["lines"]:
        for option in line["options"]:
            for part in ([option["part"]] if "part" in option else [p for p, _ in option["parts"]]):
                refs.setdefault(part, set()).update(line["refs"])
    choice_refs = {}
    for line in bom["lines"]:
        chosen = cost["choice"][", ".join(line["refs"])]
        for part in chosen.split(" + ") if " x " not in chosen else [p for p, _ in
                                                                      next(o for o in line["options"] if o.get("name") == chosen)["parts"]]:
            choice_refs.setdefault(part, []).extend(line["refs"])
    suppliers = []
    for name, rows in sorted(by_supplier.items(), key=lambda kv: -len(kv[1])):
        table = []
        for part, d in sorted(rows):
            offer = next(o for o in bom["offers"][part] if o["supplier"] == name)
            unit = d["cost"] / d["bought"]
            table.append({"ref": " ".join(sorted(set(choice_refs.get(part, [])), key=lambda r: (r[0], int(''.join(c for c in r if c.isdigit()) or 0)))),
                          "part": part, "url": "https://example.com/" + part.lower().replace(" ", "-"),
                          "data": "", "order_no": "EX-" + hashlib.md5(part.encode()).hexdigest()[:5].upper(),
                          "qty": f"{d['qty']} → {d['bought']} / 10 000+", "delivery": "2 working days",
                          "price": f"{unit:.3f}"})
        suppliers.append({"name": name, "heading": f"<b>{name}</b> (fictional): {len(rows)} of {cost['optimised']['distinct']} "
                                                   f"distinct parts, shipping {bom['costs']['shipping'][name]:.2f} € net.",
                          "rows": table, "missing": "", "note": "Example data: supplier, links, order numbers and prices "
                                                                "are invented."})
    return {
        "title": "USB gamepad", "footer": "Example review, pcb-design-brief",
        "overview": {
            "heading": "USB gamepad – overview",
            "text": f"<b>Purpose:</b> a small USB gamepad for PC games: D-pad, A/B/X/Y, START, SELECT, three status LEDs, "
                    f"USB-C to the PC, recognised without a driver (HID). <b>Series:</b> {SERIES} devices, hand soldered. "
                    f"<b>Budget:</b> 450 € for the series (fictional). <b>Cost:</b> ≈ {total:.0f} € for {SERIES} devices "
                    f"({total / SERIES:.2f} € each): parts {parts_net * 1.19:.0f} €, boards {pcb:.0f} €, PETG {case:.0f} €.",
            "image": rel("3d/overview.png"), "boxes": rel("3d/overview.json"),
            "callouts": [{"group": "top", "label": "top shell, PETG", "target": "enclosure"},
                         {"group": "caps", "label": "button caps, PETG", "target": "enclosure"},
                         {"group": "inserts", "label": "heat-set inserts M2.5", "target": "enclosure-2"},
                         {"group": "board", "label": "board, 86 × 40 mm", "target": "stack"},
                         {"group": "base", "label": "base shell, PETG", "target": "enclosure"},
                         {"group": "screws", "label": "screws M2.5 × 8", "target": "enclosure-2"},
                         {"group": "cable", "label": "USB-C cable (symbolic)", "target": "instructions"}],
            "caption": "Exploded in assembly order: base, board, inserts and caps, top; screws from below."},
        "schematic": {"pdf": rel("schematic.pdf")},
        "calculations": calc(),
        "board": {"image": rel("3d/board.png"),
                  "caption": "Rendered from the KiCad 3D export: 86 × 40 × 1.6 mm, 2 layers, ENIG. Hand-solder footprints, "
                             "THT buttons and USB-C, decoupling, crystal and reset button on the bottom."},
        "stack": {"image": rel("3d/stack.png"), "anchors": rel("3d/stack.json"),
                  "dimensions": f"{BOARD_W:.1f} × {BOARD_H:.1f} × 1.6 mm",
                  "dimensions_note": f"{BOARD_W * BOARD_H / 100 - 0.31:.1f} cm², bare ≈ "
                                     f"{(BOARD_W * BOARD_H / 100 - 0.31) * 0.16 * 1.85:.0f} g (FR-4 1.85 g/cm³)",
                  "labels": STACK_LABELS,
                  "caption": "Exploded view from above; every layer to scale, only the gaps are invented. The bottom side "
                             "is shown as it lies in the product (seen from above). Each layer and label links to its "
                             "detail."},
        "layers": layers(),
        "parts": {"suppliers": suppliers,
                  "special": ["<b>Mechanics</b> (fictional prices): 4 × M2.5 × 8 screws, 4 × heat-set inserts M2.5 × 4, "
                              f"PETG ≈ {sum(enclosure['volume_cm3'].values()) * 1.27:.0f} g per device at full infill "
                              "(≈ 15 g with 3 walls and 20 % infill)."]},
        "offers": OFFERS,
        "design_to_cost": {"text": "Every line of the BOM lists the parts that would meet the requirement; "
                                   "pcbtools cost prices each combination for the series and keeps the "
                                   "cheapest. Per-part fee 2.00 € for each distinct part (reel, feeder, sorting), placement "
                                   "0.01 €. The board was then laid out with the optimised parts.",
                           "versions": [("first version", cost["first"]), ("optimised, built", cost["optimised"])],
                           "changes": cost["changes"]},
        "enclosure": {"drawing": rel("tech-drawing.png"), "left": enclosure_left(w, h, t), "right": enclosure_right()},
        "printability": {"report": rel("printability/report.json"),
                         "caption": "Base printed floor down, top printed plate down, caps flange down; 0.2 mm layers, "
                                    "0.4 mm nozzle. The screw seats print as a bridge over a 0.2 mm membrane."},
        "assembly": {"views": rel("assembly/views.png"), "report": rel("assembly/report.json"),
                     "text": ["<b>Order:</b> 1. solder the board (bottom side first), 2. press the inserts into the top "
                              "bosses, 3. caps into the top, 4. board onto the caps, 5. base over it, 6. four screws "
                              "from below, hand-tight."]},
        "firmware": {"prompt": "firmware-prompt.md", "flashing": "flashing.md"},
        "instructions": instructions(missing),
    }


STACK_LABELS = {
    "parts_top": ["Parts, top", "THT buttons, USB-C, SMD", "soldered by hand", "up to 4.3 mm"],
    "silk_top": ["Silkscreen, top", "epoxy ink, white", "not conductive", "≈ 0.01–0.02 mm"],
    "mask_top": ["Solder mask, top", "epoxy, green", "pads and vias open", "≈ 0.02 mm"],
    "copper_top": ["Copper, top", "copper, ENIG where open", "signals, pads", "0.035 mm"],
    "core": ["Core", "FR-4", "plated holes join the layers", "1.6 mm total"],
    "copper_bottom": ["Copper, bottom", "copper, ENIG where open", "ground pour, signals", "0.035 mm"],
    "mask_bottom": ["Solder mask, bottom", "epoxy, green", "pads and vias open", "≈ 0.02 mm"],
    "silk_bottom": ["Silkscreen, bottom", "epoxy ink, white", "title, test points, check", "≈ 0.01–0.02 mm"],
    "parts_bottom": ["Parts, bottom", "SMD", "decoupling, crystal, reset", "up to 1.9 mm"],
}


def layers():
    text = {
        "parts_top": ("Parts, top", "Buttons, USB-C receptacle, MCU, USB resistors and ESD, LEDs. Plan view of the 3D models at "
                                    "the scale of the layers below.", "layers/0-parts-top.png"),
        "silk_top": ("Silkscreen, top (F.SilkS)", "Every reference with its value or function next to its part; button "
                                                  "names under the buttons.", "layers/1-silk-top.png"),
        "mask_top": ("Solder mask, top (F.Mask)", "Green = mask. Open at every pad and at the vias not under a part.",
                     "layers/2-mask-top.png"),
        "copper_top": ("Copper, top (F.Cu)", "Signals 0.3 mm, supply 0.6 mm, clearance 0.2 mm (0.15 mm only between the "
                                             "USB-C pins).", "layers/3-copper-top.png"),
        "core": ("Core with holes", "FR-4 1.6 mm; THT buttons, USB-C pins and shield, vias, four M2.5 holes.",
                 "layers/4-core.png"),
        "copper_bottom": ("Copper, bottom (B.Cu)", "Ground pour with the remaining signals; seen from above.",
                          "layers/5-copper-bottom.png"),
        "mask_bottom": ("Solder mask, bottom (B.Mask)", "Open at the pads, test points and open vias.",
                        "layers/6-mask-bottom.png"),
        "silk_bottom": ("Silkscreen, bottom (B.SilkS)", "Title, revision, the first check after soldering, test point names, "
                                                        "references of the bottom parts. Left as stacked, right readable.",
                        "layers/7-silk-bottom.png"),
    }
    out = []
    text["parts_top"] = (text["parts_top"][0], text["parts_top"][1], "layers/0-parts-top.png")
    for key, (title, body, image) in text.items():
        item = {"key": key, "title": title, "text": body, "image": rel(image)}
        if key == "silk_bottom":
            item["readable"] = rel("layers/7-silk-bottom-readable.png")
        out.append(item)
    return out


def calc():
    rows = [
        ("U1", "MCU supply", "VBUS 5.25 V max.", "5.25 V", "operating 2.7–5.5 V", 0.95, 1.0, "inside the operating range"),
        ("U1", "MCU current", "16 MHz, USB active", "≈ 15 mA", "USB budget 50 mA declared", 0.30, 0.7, ""),
        ("D2–D4", "status LEDs", "on", "3 mA each", "20 mA", 0.15, 0.7, ""),
        ("R5–R7", "LED resistors 1 k", "LED on", "9 mW", "125 mW", 0.07, 0.5, ""),
        ("R3", "reset pull-up 5.1 k", "button pressed", "4.9 mW", "125 mW", 0.04, 0.5, ""),
        ("R8, R9", "CC pull-downs 5.1 k", "host 5 V on CC", "≈ 0.2 mW", "125 mW", 0.01, 0.5, "value set by USB-C"),
        ("F1", "PTC 500 mA", "normal operation", "≈ 25 mA", "hold 500 mA", 0.05, 0.7, "trips at a short"),
        ("C3–C7", "1 µF X7R 25 V", "supply", "5.25 V", "25 V", 0.21, 0.5, "5 µF in total, USB limit 10 µF"),
        ("C1, C2", "22 pF C0G 50 V", "crystal", "≈ 5 V peak", "50 V", 0.10, 0.5, "2 × (18 − 5) pF = 26 pF → 22 pF"),
        ("J1", "USB-C receptacle", "device current", "≈ 25 mA", "≥ 1.5 A per pin", 0.02, 0.7, ""),
        ("SW1–SW11", "tactile switches", "pull-up current", "0.14 mA", "50 mA", 0.01, 0.7, ""),
    ]
    return {"text": "Worst case VBUS 5.25 V. Example values from typical datasheets; for a real build each one comes "
                    "from the datasheet of the bought part (CI-1). Total dissipation ≈ 0.13 W: no thermal limit inside "
                    "the case (rise < 1 K).",
            "rows": [{"ref": r, "function": f, "case": c, "load": l, "limit": lim, "share": sh, "allowed": al, "note": n}
                     for r, f, c, l, lim, sh, al, n in rows]}


OFFERS = {
    "text": "Board 86 × 40 mm, 2 layers, FR-4 1.6 mm, 35 µm, ENIG, green mask, white silkscreen, 25 pieces. Example "
            "offers, names and prices fictional; landed totals include shipping and import costs to the delivery "
            "country.",
    "pcb": [{"name": "Fab 1 (EU)", "url": "https://example.com/fab-1", "settings": "2 L, 1.6 mm, ENIG, green/white",
             "qty": "25", "total": "61.90 €", "lead_time": "10 working days", "notes": "cheapest; shipping included"},
            {"name": "Fab 2 (overseas)", "url": "https://example.com/fab-2", "settings": "2 L, 1.6 mm, ENIG",
             "qty": "25", "total": "68.40 €", "lead_time": "4 days + 8 days shipping", "notes": "ENIG surcharge, import VAT"},
            {"name": "Fab 3 (local express)", "url": "https://example.com/fab-3", "settings": "2 L, 1.6 mm, ENIG",
             "qty": "25", "total": "182.00 €", "lead_time": "3 working days", "notes": "only worth it when time matters"}],
    "assembly": [{"name": "Assembler 1 (overseas, turnkey)", "url": "https://example.com/assembler-1",
                  "settings": "both sides, THT by hand at the assembler", "qty": "25", "total": "≈ 240 €",
                  "lead_time": "3 weeks", "notes": "parts sourced by the assembler; two-sided adds a set-up fee"},
                 {"name": "Assembler 2 (EU)", "url": "https://example.com/assembler-2", "settings": "consigned parts",
                  "qty": "25", "total": "≈ 410 €", "lead_time": "2 weeks", "notes": "parts from the distributor list"}],
}


def enclosure_left(w, h, t):
    return [f"<b>Size:</b> {w} × {h} × {t} mm; base 2 mm floor, 2 mm walls; the top's lip (1.2 mm) locates it inside "
            "the base walls. Board clamped between the base bosses and the top bosses.",
            "<b>Screws and inserts:</b> 4 × M2.5 × 8 from below into heat-set inserts M2.5 × 4 in the top bosses; 3 mm "
            "of thread in the insert. Load: a dropped gamepad (≈ 60 g, 1 m onto a hard floor) stays far below the "
            "pull-out force of M2.5 inserts in PETG; hand-tight only.",
            "<b>Caps:</b> ten printed caps with a retaining flange under the top plate; the plunger of each tactile "
            "switch carries its cap, 1.5 mm proud of the surface.",
            "<b>Material:</b> PETG (impact resistant, 70 °C service temperature), ≈ 15 g per device with 20 % infill; "
            "≈ 0.62 € at 25 €/kg (fictional)."]


def enclosure_right():
    return ["<b>Heat:</b> ≈ 0.13 W in a 93 × 47 × 14 mm case: temperature rise below 1 K; no vents needed.",
            "<b>Radio:</b> none on the board. USB-C shield to GND.",
            "<b>Openings:</b> USB-C 12.4 × 7 mm for the cable's overmould, three Ø 1.8 mm LED windows, a Ø 1.6 mm "
            "hole in the base for the reset button (paper clip)."]


def instructions(missing):
    return [
        {"title": "Found impossible", "items": ["Nothing."]},
        {"title": "Open items (need the physical world)", "items": [
            "First prototype: check that every cap moves freely and the case closes flush.",
            "Firmware: confirm that the reset button starts the DFU bootloader (HWBE fuse)."]},
        {"title": "Where to order", "items": [
            "Parts: the two distributor tables (fictional), one order each.",
            "PCB: Fab 1, settings below. Assembly: by hand; see the offers page for the make-or-buy comparison."]},
        {"title": "PCB order settings", "items": [
            "2 layers, FR-4, 1.6 mm, 35 µm copper, ENIG, green solder mask, white silkscreen; min. track 0.2 mm, "
            "clearance 0.15 mm (USB-C pins only), min. drill 0.45 mm; quantity 25.",
            "Upload the Gerber/drill zip or the .kicad_pcb."]},
        {"title": "Deviations from the brief", "items": [
            "HS-2: TQFP-44 with 0.8 mm pitch and a USB-C receptacle with 0.85 mm pin pitch; no hand-friendlier MCU with "
            "native USB exists in a larger package.",
            "HS-4: clearance 0.2 mm (0.15 mm inside the USB-C footprint) instead of 0.5 mm; the TQFP pads force it.",
            "LB-1/LB-2: the board has no room next to the part for the value of "
            + (", ".join(m.split()[0] for m in missing if "(value)" in m) or "no part")
            + "; it is in the assembly drawing. "
            + (", ".join(m for m in missing if "(value)" not in m) + ": reference only in the assembly drawing."
               if any("(value)" not in m for m in missing) else ""),
            "JF-6: no spare solder fields; series product, the bottom is a ground pour."]},
    ]


def compose():
    """The parts in plan view on the board outline of the layer images, as the top layer of the details."""
    import numpy as np
    from PIL import Image
    silk = np.asarray(Image.open(os.path.join(BUILD, "layers", "1-silk-top.png")).convert("RGB"))
    page = np.full(silk.shape, 255, dtype=np.uint8)
    page[np.all(silk == (190, 190, 190), axis=2)] = (190, 190, 190)
    img = Image.fromarray(page).convert("RGBA")
    parts = Image.open(os.path.join(BUILD, "3d", "parts-top.png")).convert("RGBA").resize(img.size)
    img.alpha_composite(parts)
    img.convert("RGB").save(os.path.join(BUILD, "layers", "0-parts-top.png"))


if __name__ == "__main__":
    if "--compose" in sys.argv:
        compose()
        sys.exit()
    scenes()
    if os.path.exists(os.path.join(BUILD, "bom-result.json")):
        with open(os.path.join(HERE, "review.json"), "w", encoding="utf-8") as handle:
            json.dump(review(), handle, indent=1, ensure_ascii=False)
