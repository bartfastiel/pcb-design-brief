"""Release gate for a KiCad project: ERC and DRC with schematic parity, every severity counts (warnings included).
Exits non-zero on any finding. Runs with any Python 3; needs kicad-cli."""
import argparse
import glob
import json
import os
import shutil
import subprocess
import sys
import tempfile


def find_cli(given):
    candidates = [given, os.environ.get("KICAD_CLI"), shutil.which("kicad-cli")]
    candidates += sorted(glob.glob(r"C:\Program Files\KiCad\*\bin\kicad-cli.exe"), reverse=True)
    candidates += sorted(glob.glob(os.path.expanduser(r"~\AppData\Local\Programs\KiCad\*\bin\kicad-cli.exe")), reverse=True)
    candidates += ["/Applications/KiCad/KiCad.app/Contents/MacOS/kicad-cli"]
    for path in candidates:
        if path and os.path.isfile(path):
            return path
    raise SystemExit("kicad-cli not found; pass --kicad-cli or set KICAD_CLI")


def run(cli, kind, source, report, parity=True):
    args = [cli, kind, "erc" if kind == "sch" else "drc", "--severity-all", "--format", "json", "-o", report]
    if kind == "pcb" and parity:
        args.insert(3, "--schematic-parity")
    subprocess.run(args + [source], capture_output=True, text=True)
    with open(report, encoding="utf-8") as handle:
        return json.load(handle)


def findings(data):
    items = []
    for sheet in data.get("sheets", []):
        items += sheet.get("violations", [])
    for key in ("violations", "unconnected_items", "schematic_parity"):
        items += data.get(key, [])
    return items


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("project", help=".kicad_pro, .kicad_sch or .kicad_pcb (the others are found by name)")
    parser.add_argument("--kicad-cli")
    parser.add_argument("--keep", help="directory for the JSON reports")
    parser.add_argument("--pcb-only", action="store_true", help="no schematic: DRC without parity, no ERC")
    parser.add_argument("--sch-only", action="store_true", help="no board yet: ERC only")
    args = parser.parse_args()
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

    stem = os.path.splitext(args.project)[0]
    cli = find_cli(args.kicad_cli)
    out = args.keep or tempfile.mkdtemp()
    os.makedirs(out, exist_ok=True)
    total = 0
    kinds = [("sch", ".kicad_sch"), ("pcb", ".kicad_pcb")]
    kinds = kinds[1:] if args.pcb_only else kinds[:1] if args.sch_only else kinds
    for kind, ext in kinds:
        source = stem + ext
        if not os.path.exists(source):
            print(f"{ext}: missing")
            total += 1
            continue
        items = findings(run(cli, kind, source, os.path.join(out, f"{kind}.json"), not args.pcb_only))
        total += len(items)
        print(f"{'ERC' if kind == 'sch' else 'DRC'}: {len(items)} finding(s)")
        for item in items:
            where = "; ".join(i.get("description", "") for i in item.get("items", []))
            print(f"  [{item.get('severity')}] {item.get('type')}: {item.get('description')} {where}".rstrip())
    sys.exit(1 if total else 0)


if __name__ == "__main__":
    main()
