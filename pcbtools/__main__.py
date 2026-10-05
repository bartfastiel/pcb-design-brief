"""pcbtools: the deterministic half of the brief's workflow (docs/automation.md). The agent writes design.json,
bom-options.json and review.json; these commands do the rest.

  python -m pcbtools doctor                       what is installed, what is missing, where to get it
  python -m pcbtools init <dir> <name>            project skeleton: intake.md, design.json, bom-options.json
  python -m pcbtools schematic design.json        KiCad schematic, then ERC (all design steps take --out DIR)
  python -m pcbtools board design.json            place, route, finish, untent, check: a routed, labelled board
  python -m pcbtools place|route|finish design.json   the single steps of "board"
  python -m pcbtools check <project>              ERC, DRC, schematic parity; non-zero exit on findings
  python -m pcbtools calc led 5 2.0 0.003         sizing formulas (see pcbtools/calc.py)
  python -m pcbtools parts offers <MPN>...        distributor APIs, cached offers
  python -m pcbtools cost bom-options.json        design-to-cost search
  python -m pcbtools render <scene.json> <out>    Blender exploded view (scripts/blender/exploded_scene.py)
  python -m pcbtools render <board.glb> <out> --stack    to-scale layer stack (scripts/blender/layer_stack.py)
  python -m pcbtools <script> ...                 any script in scripts/: layer_images, assembly_check, printability,
                                                  tech_drawing, review_pdf, untent_vias, joker_fields, autoroute

Board commands need KiCad's Python; when this interpreter cannot import pcbnew, they re-run under KiCad's."""
import glob
import importlib.util
import os
import runpy
import subprocess
import sys

from . import tools

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCRIPTS = {os.path.splitext(os.path.basename(p))[0]: p for p in glob.glob(os.path.join(REPO, "scripts", "*", "*.py"))}
NEEDS_PCBNEW = {"place", "route", "finish", "board", "untent_vias", "joker_fields", "autoroute"}


def in_kicad_python(argv):
    if importlib.util.find_spec("pcbnew"):
        return False
    python = tools.kicad_python()
    if not python:
        raise SystemExit("this step needs KiCad's Python (pcbnew); run `python -m pcbtools doctor`")
    bootstrap = f"import sys; sys.path.insert(0, {REPO!r}); from pcbtools.__main__ import main; main(sys.argv[1:])"
    raise SystemExit(subprocess.run([python, "-c", bootstrap] + argv).returncode)


def script(name, args):
    sys.argv = [SCRIPTS[name]] + args
    sys.path.insert(0, os.path.dirname(SCRIPTS[name]))
    runpy.run_path(SCRIPTS[name], run_name="__main__")


OUT = {"dir": None}


def out_dir(design_path):
    folder = OUT["dir"] or os.path.dirname(os.path.abspath(design_path))
    os.makedirs(folder, exist_ok=True)
    return folder


def pcb_of(design_path):
    from .design import Design
    design = Design(design_path)
    return design, os.path.join(out_dir(design_path), design["project"] + ".kicad_pcb")


def route(design_path, attempts="25", passes="100"):
    design, pcb = pcb_of(design_path)
    jar, java, docker = tools.freerouting()
    if not jar or not (java or docker):
        raise SystemExit("Freerouting or Java missing; run `python -m pcbtools doctor`")
    args = [pcb, "--jar", jar, "--passes", passes, "--attempts", attempts]
    args += ["--docker", docker] if docker and not java else []
    for nc in design.get("netclasses", []):
        if nc.get("route") is False:
            args += ["--ignore-netclass", nc["name"]] + [a for n in nc["nets"] for a in ("--ignore-net", "/" + n)]
    script("autoroute", args)


def check(target, extra=()):
    cli = tools.kicad_cli()
    sys.argv = [SCRIPTS["check"], target, "--kicad-cli", cli] + list(extra)
    sys.path.insert(0, os.path.dirname(SCRIPTS["check"]))
    try:
        runpy.run_path(SCRIPTS["check"], run_name="__main__")
    except SystemExit as stop:
        return stop.code or 0
    return 0


def main(argv):
    if not argv or argv[0] in ("-h", "--help", "help"):
        print(__doc__)
        return
    command, args = argv[0], argv[1:]
    if "--out" in args and command in ("schematic", "place", "route", "finish", "board"):
        k = args.index("--out")
        OUT["dir"] = os.path.abspath(args[k + 1])
        del args[k:k + 2]
    if command in NEEDS_PCBNEW:
        in_kicad_python(argv)
    if command == "doctor":
        raise SystemExit(0 if tools.report() else 1)
    if command == "init":
        from .init import init
        init(*args)
    elif command == "schematic":
        from .design import Design
        from .schematic import write
        design = Design(args[0])
        out = os.path.join(out_dir(args[0]), design["project"] + ".kicad_sch")
        print(write(args[0], tools.kicad_share()["symbols"], out))
        if os.path.exists(out.replace(".kicad_sch", ".kicad_pcb")):
            raise SystemExit(check(out))
        raise SystemExit(check(out, ["--sch-only"]))
    elif command == "place":
        from .board import place
        design, pcb = pcb_of(args[0])
        place(args[0], tools.kicad_share()["footprints"], pcb)
        print(f"placed: {pcb}")
    elif command == "route":
        route(args[0])
    elif command == "finish":
        from .board import finish
        design, pcb = pcb_of(args[0])
        print("only in the assembly drawing:", " ".join(finish(args[0], pcb)) or "nothing")
    elif command == "board":
        from .board import finish, place
        design, pcb = pcb_of(args[0])
        place(args[0], tools.kicad_share()["footprints"], pcb)
        route(args[0])
        print("only in the assembly drawing:", " ".join(finish(args[0], pcb)) or "nothing")
        script("untent_vias", [pcb])
        from .board import write_project
        write_project(design, pcb)
        raise SystemExit(check(pcb))
    elif command == "check":
        raise SystemExit(check(args[0], args[1:]))
    elif command == "calc":
        from .calc import main as calc
        calc(args)
    elif command == "parts":
        from .parts import main as parts
        parts(args)
    elif command == "cost":
        from .cost import main as cost
        cost(args)
    elif command == "render":
        exe = tools.blender()
        if not exe:
            raise SystemExit("Blender not found; run `python -m pcbtools doctor`")
        stack = "--stack" in args
        args = [a for a in args if a != "--stack"]
        blend = SCRIPTS["layer_stack" if stack else "exploded_scene"]
        run = subprocess.run([exe, "--background", "--python", blend, "--"] + args, capture_output=True, text=True,
                             encoding="utf-8", errors="replace")
        if run.returncode or "Error" in run.stderr:
            print(run.stdout[-3000:], run.stderr[-3000:])
        raise SystemExit(run.returncode)
    elif command in SCRIPTS:
        script(command, args)
    else:
        raise SystemExit(f"unknown command {command}\n\n{__doc__}")


if __name__ == "__main__":
    main(sys.argv[1:])
