# pcb-design-brief

An agent-ready design brief for **small-series, hand-soldered PCBs** in KiCad with a
**3D-printed enclosure**: rules with IDs, workflow gates, a page-by-page review-PDF specification,
and helper scripts that do the tedious parts.

Hand it to a coding agent together with your project and the agent knows what "done" means:
which questions to ask once at the start, which checks must be green, how the documentation looks,
and how to report where it deviated. The aim is a design that needs hardly any feedback rounds.

## What is in it

| File | Purpose |
|---|---|
| [BRIEF.md](BRIEF.md) | the brief itself (English, normative) |
| [templates/intake.md](templates/intake.md) | the intake questions, project overrides and open assumptions; copy into the project |
| [skills/pcb-design-brief/SKILL.md](skills/pcb-design-brief/SKILL.md) | entry point for agents that load skills (e.g. Claude Code) |
| [scripts/](scripts/) | KiCad and review helpers, see below |

The brief in one breath: ask once, then work alone; function and safety first; nothing lost,
everything traceable; verified data only; derate generously; big exposed pads and open vias for
the soldering iron; spare solder fields in free copper on prototypes; zero ERC/DRC warnings; a
virtual enclosure assembly with zero intersections; a review PDF from the exploded product
render down to per-supplier parts lists and the fab order settings.

## Using it with an agent

Pick one:

- **Reference it** from the project's `AGENTS.md` / `CLAUDE.md`:
  `Follow https://github.com/bartfastiel/pcb-design-brief/blob/main/BRIEF.md for all PCB and enclosure work. Our answers: intake.md.`
- **Copy** `BRIEF.md` and `templates/intake.md` into the project and commit them (pins the
  version you agreed on).
- **As a skill** (Claude Code): copy `skills/pcb-design-brief/` into `.claude/skills/` of the
  project or of your home directory, together with `BRIEF.md`.

Then start with: *"Design the board for … following the PCB design brief."* The agent fills
`intake.md`, asks the open questions in one batch and continues on its own.

## Scripts

Install the Python packages with `pip install -r requirements.txt`. All scripts are standalone, take paths as arguments and write nothing outside the given output
directory. KiCad scripts need the Python that ships with KiCad (it contains `pcbnew`), e.g.
`"C:\Program Files\KiCad\9.0\bin\python.exe"` on Windows or `/usr/lib/kicad/bin/python3` style
paths elsewhere.

| Script | Rule | What it does |
|---|---|---|
| [scripts/kicad/check.py](scripts/kicad/check.py) | §4 gates | ERC, DRC with parity, fails on any warning, prints a summary |
| [scripts/kicad/untent_vias.py](scripts/kicad/untent_vias.py) | HS-5 | removes solder mask from every via on both sides |
| [scripts/kicad/joker_fields.py](scripts/kicad/joker_fields.py) | JF-1 … JF-5 | computes spare solder fields in the free copper and adds them as one board-only footprint |
| [scripts/review/layer_images.py](scripts/review/layer_images.py) | §12.5 | one presence-coloured PNG per board layer from `kicad-cli` SVG exports |
| [scripts/review/assembly_check.py](scripts/review/assembly_check.py) | AC-2, AC-4 | pairwise intersection volumes and six orthographic views with inward faces in signal red |
| [scripts/review/tech_drawing.py](scripts/review/tech_drawing.py) | §12.7 | technical drawing sheet (three views plus isometric, main dimensions) from STL files |
| [scripts/blender/layer_stack.py](scripts/blender/layer_stack.py) | §12.4 | photo-realistic exploded layer stack from a KiCad GLB export, with label anchors and link boxes as JSON |
| [scripts/blender/exploded_scene.py](scripts/blender/exploded_scene.py) | §12.1, §12.3 | studio render of a JSON scene (STL, GLB, simple boxes, cables), screen boxes per part as JSON for PDF links |

Python scripts print `--help`; the Blender scripts take their arguments after `--` (`blender -b --python script.py -- …`) and document them in their docstring. Tested with KiCad 10 and Blender 4.5.

## Questions this brief answers on purpose

- *Why spare solder fields?* Prototypes always miss a part. Exposed fields on a 2.54 mm grid turn
  free copper into perfboard, without touching the functional circuit (1 mm clearance).
- *Why open vias?* They are free test points and rework spots on a hand-soldered board.
- *Why zero warnings?* A warning that is "fine" today hides the one that is not tomorrow. If a
  rule cannot be met, the deviation is reported by ID instead.
- *Why a 30-page PDF for a small board?* Because it replaces the review meeting: every decision,
  every number and its origin, and the order settings are in one place.

## Contributing

Issues and pull requests are welcome, especially rules that saved you a board revision. Keep rules
short, give them an ID, state the reason in one line.

## License

[MIT](LICENSE)
