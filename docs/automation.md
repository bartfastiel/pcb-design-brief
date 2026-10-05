# What the agent decides, what the tools do

Tokens are expensive and slow; a script is cheap, fast and gives the same answer twice. The agent should only do
what needs judgement, and hand everything else to a tool with a clear input and output. The tools in `pcbtools/`
take data files the agent writes, and produce files and numbers the agent reads.

| Step | Agent (judgement) | Tool (deterministic) |
|---|---|---|
| Intake | ask the IN questions, interpret answers, set the optimisation order | `pcbtools init` writes the project skeleton and `intake.md` |
| Circuit concept | topology, protection, safe states, which interfaces | — |
| Part candidates | requirement per part (voltage, tolerance, package family) | `pcbtools parts search` queries distributor APIs, filters by parameters, caches offers |
| Part sizing | review the numbers, decide margins | `pcbtools.calc` formulas (power, dividers, LED and crystal parts, track width, heat), table for the PDF |
| Design to cost | list acceptable alternatives per line | `pcbtools cost` finds the cheapest consistent BOM for the series |
| Schematic | parts, pins → nets, groups and notes in `design.json` | `pcbtools schematic` writes the KiCad schematic (symbols from the libraries, net labels, no-connects, power flags) |
| Placement | positions and sides of the parts | `pcbtools board place`: outline, footprints, nets, net classes, DRC exceptions, labels |
| Routing | pre-routes only where a footprint needs a pattern | `pcbtools board route` (Freerouting, retried), `fanout`, `pour` (both layers, stitching) |
| Labelling | names and texts that need meaning (button names, the first check) | `pcbtools board label`: references and values next to their parts, nearest-part rule, fallbacks, report |
| Checks | read the report, fix causes | `pcbtools check` (ERC, DRC, parity), `untent`, `joker` |
| Enclosure | concept: split plane, fixing, openings | SCAD or Python model; `assembly_check`, `printability`, `tech_drawing` |
| Renders | look at them (PR-5) | `layer_images`, Blender `exploded_scene`, `layer_stack` |
| Review PDF | the prose: purpose, decisions, deviations | `review_pdf` lays out everything from `review.json` |
| Firmware | the prompt's content | — |

Rules of thumb for the agent:

- Write data, not KiCad files: a part list with pins and nets, positions, texts. Tools turn data into files.
- Run the whole pipeline after every change (`pcbtools build`), read its summary, and only open files when a
  number looks wrong.
- Never retype numbers from tool output into prose by hand; let `review.json` reference the result files.
