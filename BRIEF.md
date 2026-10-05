# PCB Design Brief

What "done" means for a small-series, hand-soldered PCB with a 3D-printed enclosure, and how an
agent (or a person) gets there with as little back-and-forth as possible.

- **MUST / SHOULD / MAY** as in RFC 2119.
- Every rule has an ID. Reports name deviations by ID and give the reason (`HS-4: 0.3 mm between
  two tracks at U1, the router cannot finish with more`).
- Project answers in the intake file override the defaults here. Record every override there.

## 1 Intake

Ask every open question **once, in one batch, at the start**. After that, work autonomously.
Anything unknown that blocks nothing becomes a named, flagged assumption, not a question.

| ID | Question | Why | Default if unanswered |
|---|---|---|---|
| IN-1 | Purpose, requirements, examples or reference designs | everything | ask |
| IN-2 | Hand soldering or machine assembly? | pad sizes, part sizes, joker fields | hand |
| IN-3 | Series size (and how many are prototypes) | price breaks, spare fields, panel | ask |
| IN-4 | Budget for the series, and what it covers (parts, PCB, enclosure, shipping, VAT) | part choice | ask |
| IN-5 | Preferred suppliers for parts, PCB, assembly | sourcing | ask |
| IN-6 | Delivery country and currency | shops, VAT, shipping | ask |
| IN-7 | Fixed mechanics: board outline, connector positions, enclosure, mounting | layout | none fixed |
| IN-8 | Environment: temperature, indoor/outdoor, mains, radio, mechanical load | ratings | indoor, 0–40 °C |
| IN-9 | May tools be installed? May a browser be automated on the user's behalf for supplier data? | prerequisites, sourcing | ask |

## 2 Principles, in priority order

1. **Function and safety first.** Radio, heat and ratings come before compactness or looks.
2. **Nothing is lost.** No data, no work state, no board area. Free area becomes spare solder
   fields (§7) or labelling. Every state is in git.
3. **Everything is traceable.** Source files, calculations, origin of every number, and a review
   PDF (§12) that explains each decision.
4. **Verified data only.** Dimensions, footprints, ratings and prices come from datasheets,
   manufacturer files, measurements or the shop page. Never guess. If a value is missing or it is
   unclear which dimension is meant, ask; until answered, keep it as a named parameter and flag
   it in the review PDF.
5. **Robust, not at the limit.** Generous derating, noise margins, tolerant of operator errors,
   low emissions.
6. **Easy for the hands** that solder, test and rework it.

## 3 Prerequisites

Check and report versions. Install only with permission (IN-9).

- git
- KiCad ≥ 8 with `kicad-cli` and its bundled Python (`pcbnew`)
- a PDF viewer, and a way to rasterise PDF pages for your own visual check
- 3D: KiCad raytracer for board renders, Blender for realistic scenes, OpenSCAD or another CAD
  for the enclosure
- Python: `pymupdf`, `reportlab`, `pillow`, `numpy`, `trimesh`, `manifold3d`
- Playwright, if browser automation is allowed

## 4 Workflow and gates

| Phase | Output | Gate before the next phase |
|---|---|---|
| 1 Intake | intake file | every IN answered or defaulted |
| 2 Circuit | schematic, calculation table | ERC 0 (errors **and** warnings); every part sized by calculation (§6) |
| 3 Sourcing | BOM with suppliers | everything orderable, budget holds, otherwise back to 2 |
| 4 Layout | PCB, fab files | DRC 0 incl. warnings, schematic parity 0, unconnected 0 |
| 5 Enclosure | print files | assembly check (§9) and printability check (FDM-8) pass |
| 6 Review PDF | PDF | complete (§12), every page looked at |
| 7 Handover | commit, push, summary | definition of done (§14) |

A later finding that hurts an earlier phase sends the work back there.

- **PR-1** One source of truth: a generator script, or the KiCad project if drawn by hand. Change
  the source and regenerate. Never patch generated files only; the next run erases it.
- **PR-2** Hand-edited copies of design files are never committed and never read by tools (fixed
  file names, no globs).
- **PR-3** Commit early and often, at least to a local repository; push whenever a remote exists.
- **PR-4** After every change: rerun all gates and regenerate every derived image (renders,
  layout, schematic, PDF). A stale image is a bug.
- **PR-5** Look at every render and PDF page yourself before showing it.
- **PR-6** Save the scripts that produce renders, checks and the PDF next to the design, so the
  whole package rebuilds with one command.

## 5 Layout for hand soldering

Applies when IN-2 is "hand".

- **HS-1** Pads clearly larger than nominal: chip pads extended outwards by 0.5–1 mm so the tip
  touches copper, not the part. Thermally heavy parts (MOSFET tab, connectors) get an extra
  exposed copper area to preheat.
- **HS-2** Prefer 0805/1206, SOT-23, SMA, DPAK. Smaller packages, QFN or BGA only when
  unavoidable, and justified.
- **HS-3** Spread parts out; room for the iron beats short tracks, even if a part no longer sits
  right at its pin.
- **HS-4** Clearance target ≥ 0.5 mm. Go down to the fab minimum only where unavoidable, and
  justify each case in the review PDF.
- **HS-5** Vias untented (no solder mask) on both sides, including those a router creates:
  probing and rework. Not under part bodies or metal cans, not in pads.
- **HS-6** Signals ≥ 0.4 mm where space allows, preferably on the bottom where they can be cut.
  Power tracks sized for ≤ 10 K temperature rise (IPC-2152).
- **HS-7** Silkscreen: a reference for every part where it fits, otherwise in the assembly
  drawing; values listed on the board if space allows. Silk never on pads or open vias (a DRC
  warning is a failure).
- **HS-8** Polarity and pin-1 marks stay visible after assembly.

## 6 Circuit

- **CI-1** Calculate voltage, current, power and temperature for every part. Record rating and
  margin in a table.
- **CI-2** Derating defaults:

  | Part | Limit at worst case |
  |---|---|
  | resistor | ≤ 50 % of rated power |
  | ceramic capacitor | ≤ 50 % of rated voltage (DC bias) |
  | electrolytic capacitor | ≤ 80 % of rated voltage, 105 °C type |
  | semiconductor | ≤ 50–70 % of absolute-maximum voltage, current, power; Tj ≤ 100 °C |
  | connector, wire | ≤ 70 % of rated current |

- **CI-3** Robust values: no needlessly high-impedance nodes, ADC sources ≤ about 10 kΩ or
  buffered by a capacitor, pull-ups 1–10 kΩ, no µA currents that pick up noise. Define the safe
  state without firmware.
- **CI-4** Operator errors: reverse polarity, hot plugging, ESD on exposed contacts, shorted
  outputs. Protect against them or state why not.
- **CI-5** Low emissions: soft switching of loads, short high-current loops, decoupling at the
  pin.
- **CI-6** Every value change is checked against the datasheet again and updates the table.
- **CI-7** Expensive or hard-to-get parts: reconsider the circuit (§10).

## 7 Spare solder fields ("joker fields") on prototypes

- **JF-1** Free copper on both sides is filled with unconnected, exposed solder fields, like
  perfboard, for parts or wires forgotten in the design.
- **JF-2** Grid 2.54 mm, 0.5 mm gap between fields (an 0805 or a solder blob bridges it). At the
  edges the fields take the shape of the free area. Minimum 1.2 mm wide and 2 mm².
- **JF-3** Clearance ≥ 1 mm to all functional copper and every hole, so nothing gets touched
  by accident while soldering. Silkscreen, part outlines and enclosure clamp areas stay free.
  Radio keep-out plus 3 mm.
- **JF-4** Plated through only where both sides have room (drill 0.8 mm, ring ≥ 0.45 mm), at
  least 5.08 mm apart.
- **JF-5** Computed by a script after routing, never placed by hand. A board-only footprint,
  excluded from BOM and position files.
- **JF-6** Left out for production runs unless asked for (IN-3).

## 8 Radio, mechanics, environment

- **EN-1** Radio: take the antenna keep-out from the module maker's layout data (footprint,
  reference design), not from wikis. No copper, ground pour, screws or inserts inside it. Check the
  distance to enclosure walls. When in doubt, function beats space.
- **EN-2** Fixed constraints (IN-7) change only after the user agrees.
- **EN-3** Heat: dissipation per part and in total, temperature rise inside the enclosure,
  resulting maximum ambient temperature. Thin margins: iterate (vents, lower losses, other
  parts).
- **EN-4** Enclosure: prints without supports, no wall thinner than two perimeters in any
  layer, screws into heat-set inserts. Boards are clamped by the enclosure. Plugging forces go
  into the enclosure, never into solder joints.

## 9 Enclosure assembly check

- **AC-1** Assemble everything virtually: enclosure parts, boards, modules, screws, inserts,
  wires.
- **AC-2** Intersection volume between any two bodies is 0. Only a screw thread inside its
  insert or printed hole may overlap.
- **AC-3** Assembly is possible: every part can be moved into place along a straight path
  without collision. Document the order.
- **AC-4** Closure views: every part gets its own contrasting outside colour, and every surface
  that faces inwards (a ray along its normal hits another part) is signal red. Six orthographic
  views. Red may show only at planned openings.
- **AC-5** Outer faces flush, boards held within tolerance, walls ≥ the minimum of EN-4.

## 9a 3D printing (FDM)

Printability is decided by geometry, not by hope. Design every printed part for one print orientation, check it
with numbers, and show the result as a picture.

- **FDM-1** Choose the print orientation before modelling. It is part of the source; the STL is exported in it
  (z up, bed face at the bottom).
- **FDM-2** Overhang ≤ 45° from vertical without support. Downward-facing edges get 45° chamfers, not fillets or
  horizontal ledges; holes in vertical walls get a teardrop or flat top.
- **FDM-3** Bridges ≤ 10 mm and only between two supported ends. Counterbores that end in a head seat print the
  first bridging layer as a slot, the next as a square, then the hole.
- **FDM-4** No floating islands: every region of every layer rests on the layer below.
- **FDM-5** Every feature in every layer ≥ 2 × nozzle width (0.8 mm with a 0.4 mm nozzle); load-bearing walls
  ≥ 1.2 mm. Fits: 0.2 mm clearance per side; heat-set insert holes per the maker's table.
- **FDM-6** Text only where it prints well: raised (≥ 0.6 mm) or engraved on faces that are on top while printing,
  or on vertical walls; never on the bed face. Cap height ≥ 5 mm, bold sans serif, strokes ≥ 0.8 mm.
- **FDM-7** A flat bed face of ≥ 15 % of the footprint. No thin plates with free corners (they warp): close the
  walls into rings or add ribs.
- **FDM-8** Proof: an automatic check of FDM-2 … FDM-7 per part (PASS required) plus four views with every downward
  face coloured by what the printer has to do there (support needed red, bridge orange, too-long bridge violet, bed
  blue) and the layer with the thinnest features. Numbers and coordinates for the agent, the picture for the
  human. Cross-check once in the slicer: no support generated.

## 10 Sourcing

- **SO-1** Check the usual electronics shops for the delivery country (IN-6), preferred ones
  first (IN-5). Per supplier: availability for the series quantity, stock, delivery date, net
  unit price, shipping, minimum order value, free-shipping threshold.
- **SO-2** Deep links to the product page. Order numbers copied from the page, never assembled.
- **SO-3** Parts with few sources (modules): search further (maker's shop, price comparison
  sites, marketplaces) and list alternatives.
- **SO-4** Include the mechanics: screws, inserts, filament, wire, the PCB itself.
- **SO-5** No API? Ask once whether a browser may be automated on the user's behalf (IN-9):
  no logins, no purchases, polite pace. Keep the raw data with its date.
- **SO-6** Use the series quantity with packaging units and price breaks. Show cost per device
  and per series against the budget.

## 11 Deliverables

- KiCad schematic and PCB, plus the generator script if one is used
- fab files as the PCB maker wants them (Gerber/drill zip; BOM and positions for assembly)
- enclosure print files (STL or 3MF) and their source (SCAD, STEP, …)
- the review PDF
- calculation table and supplier data with retrieval date

## 12 Review PDF

One section each, A4. Portrait unless landscape clearly reads better. All images rendered fresh
from the current sources (PR-4).

1. **Overview.** Title, purpose (1–3 sentences), series size, cost per device and per series
   against the budget. A perspective exploded render from above in a realistic, product-photo
   style: all enclosure parts, boards, modules, screws, inserts, wires, power supply, arranged
   the way it is assembled and used. Every item is a link: to its enclosure page, to the
   layer stack, or to its row in the parts list.
2. **Schematic** from KiCad: no text over lines or symbols, grouped by function, aligned and
   evenly spaced. Followed by the calculation table (CI-1).
3. **Board.** Perspective render from above, assembled, as close to the real thing as possible.
4. **Layer stack.** Perspective exploded view, layers pulled apart, realistic look. From top:
   top parts, top silkscreen, top mask, top copper, core (holes clearly visible),
   bottom copper, bottom mask, bottom silkscreen, bottom parts. More layers for multilayer
   boards; empty layers are left out. Every layer keeps its true thickness relative to length and width;
   only the gaps between the layers are invented. Every layer is shown as it is stacked in the product, so
   the bottom side appears as seen from above (mirrored text). Each layer has a black dot with a
   horizontal leader line to its label: name, material, properties, thickness. Layer and label
   link to the layer detail.
5. **Layer details.** One third of a page per layer: a more detailed label, then the layer in
   the same orientation as in the stack. Bottom silkscreen additionally as a smaller, readable
   view. Colours show presence only: mask green, copper copper-coloured, core ochre, silkscreen
   dark grey, everything else white; a light grey board outline for orientation. Nothing from
   other layers.
6. **Parts list.** One table per supplier, the most attractive first. Heading: supplier, parts
   available (x of n), latest delivery date, shipping cost for this order (minimum order value,
   free-shipping threshold). Columns: Ref, part (deep link), key data and function, order
   number, series demand / supplier stock, delivery date for that quantity, net unit price.
   Below each table a red list of parts not available there. Special parts as separate entries
   with their extra sources. Include the mechanics (SO-4).
7. **Enclosure, technical.** One sheet with all printed parts: three orthographic views plus
   one isometric view each, main dimensions, first-angle projection (ISO). The printability sheets
   of FDM-8. Screws and inserts in
   detail with load calculation and material. Material recommendation and cost. Heat
   calculation with maximum ambient temperature (EN-3). Radio check (EN-1).
8. **Assembly check.** The six views of AC-4, the intersection table (AC-2), the assembly order
   (AC-3).
9. **Instructions.**
   - what was found impossible, and why
   - open items: none. Do them now and rebuild the PDF. Only items that need the physical world
     (a measurement on a real part, a test print) may stay, each with what is needed to close it.
   - where to order the parts: suppliers, totals
   - where to order the PCB: maker, layers, thickness, material, surface finish, mask and silk
     colour, minimum track and drill, quantity, files to upload

## 13 Communication

- **CO-1** Short answers. Mark uncertainty as uncertain. Name open points explicitly
  ("RSSI not measured yet").
- **CO-2** Report deviations from this brief by rule ID with the reason.
- **CO-3** Prose in the user's language; code, logs and file names in English. Units and decimal
  separator per locale.

## 14 Definition of done

- [ ] intake complete, overrides recorded
- [ ] ERC, DRC, parity, unconnected: 0, warnings included
- [ ] calculation table complete, every part within CI-2
- [ ] all parts orderable, cost within budget
- [ ] enclosure assembly check passes (AC-1 … AC-5), printability PASS for every printed part (FDM-8)
- [ ] every derived image and the PDF regenerated from the current sources and looked at
- [ ] review PDF complete per §12, no open items except physical ones
- [ ] deliverables (§11) present, everything committed and pushed
- [ ] deviations from this brief listed by rule ID
