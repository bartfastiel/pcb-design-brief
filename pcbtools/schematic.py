"""KiCad schematic from design.json: library symbols (derived ones flattened the way eeschema stores them), every used
pin a short wire with a net label, unused pins marked no-connect, power flags, a note per functional group.
Readable by construction: no wire crosses a symbol, labels sit at pin ends, references and values beside the body."""
import re

from .design import Design

STUB = 5.08


def block(text, name):
    start = text.index(f'(symbol "{name}"')
    depth = 0
    for end in range(start, len(text)):
        depth += {"(": 1, ")": -1}.get(text[end], 0)
        if depth == 0:
            return text[start:end + 1]
    raise ValueError(name)


def units(text, name):
    found, start = [], 0
    while True:
        start = text.find(f'(symbol "{name}_', start)
        if start < 0:
            return found
        found.append(block(text[start:], text[start + 9:text.index('"', start + 9)]))
        start += len(found[-1])


def library(sym_dir, lib_id):
    """Symbol text for lib_symbols and its pins {number: (x, y, angle)}; derived symbols get their parent's units."""
    lib, name = lib_id.split(":")
    source_lib = open(f"{sym_dir}/{lib}.kicad_sym", encoding="utf-8").read()
    source = block(source_lib, name)
    parent = re.search(r'\(extends "([^"]*)"\)', source)
    if parent:
        parent = parent.group(1)
        base = block(source_lib, parent)
        source = re.sub(r'\s*\(extends "[^"]*"\)', "", source)
        head = base[:base.index("(property")]
        own = source[source.index("(property"):source.rindex(")")]
        own = re.sub(r'\(symbol "' + re.escape(name) + r'_[\s\S]*', "", own)
        body = "\n".join(u.replace(f'(symbol "{parent}_', f'(symbol "{name}_') for u in units(base, parent))
        source = head.replace(f'(symbol "{parent}"', f'(symbol "{name}"', 1) + own + body + ")"
    text = source.replace(f'(symbol "{name}"', f'(symbol "{lib_id}"', 1)
    pins = {num: (float(x), float(y), int(a)) for x, y, a, num in
            re.findall(r'\(pin \w+ \w+\s*\(at ([-\d.]+) ([-\d.]+) (\d+)\)[\s\S]*?\(number "([^"]+)"', text)}
    return text, pins


def prop(name, value, x, y, hide=False):
    hidden = "\n\t\t\t\t(hide yes)" if hide else ""
    return (f'\t\t(property "{name}" "{value}"\n\t\t\t(at {x:.2f} {y:.2f} 0)\n\t\t\t(effects\n\t\t\t\t(font\n'
            f'\t\t\t\t\t(size 1.27 1.27)\n\t\t\t\t)\n\t\t\t\t(justify left){hidden}\n\t\t\t)\n\t\t)\n')


def text_spot(x, y, pins):
    """Reference and value right of the body, or above it when the symbol has pins on both sides."""
    left = any(a == 0 for _, _, a in pins.values())
    right = any(a == 180 for _, _, a in pins.values())
    if left and right:
        top = max([py for _, py, _ in pins.values()] + [0])
        return x - 2.54, y - top - 6.35
    reach = max([abs(px) for px, _, _ in pins.values()] + [0])
    return x + max(3.81, reach + 2.54), y


def symbol(design, ref, lib_id, value, footprint, x, y, pins, power=False, bom=True):
    tx, ty = text_spot(x, y, pins)
    pin_xml = "".join(f'\t\t(pin "{n}"\n\t\t\t(uuid "{design.uid(ref, n)}")\n\t\t)\n' for n in pins)
    return (f'\t(symbol\n\t\t(lib_id "{lib_id}")\n\t\t(at {x:.2f} {y:.2f} 0)\n\t\t(unit 1)\n\t\t(exclude_from_sim no)\n'
            f'\t\t(in_bom {"yes" if bom and not power else "no"})\n\t\t(on_board {"no" if power else "yes"})\n'
            f'\t\t(dnp no)\n\t\t(uuid "{design.uid(ref)}")\n'
            + prop("Reference", ref, tx, ty - 1.27, hide=power) + prop("Value", value, tx, ty + 1.27)
            + prop("Footprint", footprint, x, y, True) + prop("Datasheet", "", x, y, True)
            + prop("Description", "", x, y, True) + pin_xml
            + f'\t\t(instances\n\t\t\t(project "{design["project"]}"\n\t\t\t\t(path "/{design.root}"\n'
              f'\t\t\t\t\t(reference "{ref}")\n\t\t\t\t\t(unit 1)\n\t\t\t\t)\n\t\t\t)\n\t\t)\n\t)\n')


def stub(design, ref, number, x, y, angle, net):
    dx, dy = {0: (-1, 0), 180: (1, 0), 90: (0, 1), 270: (0, -1)}[angle]
    ex, ey = x + dx * STUB, y + dy * STUB
    label_angle = {(-1, 0): 180, (1, 0): 0, (0, 1): 270, (0, -1): 90}[(dx, dy)]
    justify = "right bottom" if label_angle in (180, 270) else "left bottom"
    return (f'\t(wire\n\t\t(pts\n\t\t\t(xy {x:.2f} {y:.2f})\n\t\t\t(xy {ex:.2f} {ey:.2f})\n\t\t)\n'
            f'\t\t(stroke\n\t\t\t(width 0)\n\t\t\t(type default)\n\t\t)\n\t\t(uuid "{design.uid(ref, number, "w")}")\n\t)\n'
            f'\t(label "{net}"\n\t\t(at {ex:.2f} {ey:.2f} {label_angle})\n\t\t(effects\n\t\t\t(font\n'
            f'\t\t\t\t(size 1.27 1.27)\n\t\t\t)\n\t\t\t(justify {justify})\n\t\t)\n'
            f'\t\t(uuid "{design.uid(ref, number, "l")}")\n\t)\n')


def write(design_path, sym_dir, out):
    design = Design(design_path)
    lib_ids = sorted({p["symbol"] for p in design.parts} | ({"power:PWR_FLAG"} if design.get("flags") else set()))
    libs = {lib_id: library(sym_dir, lib_id) for lib_id in lib_ids}
    body = [f'(kicad_sch\n\t(version 20250114)\n\t(generator "eeschema")\n\t(generator_version "10.0")\n'
            f'\t(uuid "{design.root}")\n\t(paper "{design.get("paper", "A3")}")\n\t(title_block\n'
            f'\t\t(title "{design.get("title", design["project"])}")\n\t\t(rev "{design.get("revision", "")}")\n'
            f'\t\t(comment 1 "Generated from design.json by pcbtools")\n\t)\n'
            "\t(lib_symbols\n" + "\n".join("\t\t" + libs[i][0].replace("\n", "\n\t") for i in lib_ids) + "\n\t)\n"]
    for part in design.parts:
        pins = libs[part["symbol"]][1]
        sx, sy = part["sch"]
        body.append(symbol(design, part["ref"], part["symbol"], part["value"], part["footprint"], sx, sy, pins,
                           bom=part.get("bom", True)))
        done = set()
        for number, (px, py, angle) in pins.items():
            ax, ay = sx + px, sy - py
            if number in part.get("pins", {}):
                if (ax, ay) not in done:
                    body.append(stub(design, part["ref"], number, ax, ay, angle, part["pins"][number]))
                    done.add((ax, ay))
            elif number in part.get("nc", {}):
                body.append(f'\t(no_connect\n\t\t(at {ax:.2f} {ay:.2f})\n\t\t(uuid "{design.uid(part["ref"], number, "nc")}")\n\t)\n')
    for k, flag in enumerate(design.get("flags", []), 1):
        ref = f"#FLG{k:02d}"
        px, py, angle = libs["power:PWR_FLAG"][1]["1"]
        x, y = flag["sch"]
        body.append(symbol(design, ref, "power:PWR_FLAG", "PWR_FLAG", "", x, y, {"1": (px, py, angle)}, power=True))
        body.append(stub(design, ref, "1", x + px, y - py, angle, flag["net"]))
    for note in design.get("notes", []):
        x, y = note["sch"]
        body.append(f'\t(text "{note["text"]}"\n\t\t(exclude_from_sim no)\n\t\t(at {x:.2f} {y:.2f} 0)\n\t\t(effects\n'
                    f'\t\t\t(font\n\t\t\t\t(size 1.524 1.524)\n\t\t\t)\n\t\t\t(justify left bottom)\n\t\t)\n'
                    f'\t\t(uuid "{design.uid("note", note["text"])}")\n\t)\n')
    body.append('\t(sheet_instances\n\t\t(path "/"\n\t\t\t(page "1")\n\t\t)\n\t)\n\t(embedded_fonts no)\n)\n')
    with open(out, "w", encoding="utf-8", newline="\n") as handle:
        handle.write("".join(body))
    return out
