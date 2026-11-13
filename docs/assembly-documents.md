# Hand assembly documents

Details for §12a of the brief: the assembly sheet, the bag labels and the commissioning test table. They come from
building a small board by hand from loose parts, and from what went wrong there. All three are printed and used
at the bench, next to a hot iron, so they are designed for paper: black and white, large type where it matters,
nothing that needs a screen or colour to read.

There is no generator in `pcbtools` yet (TL-3: so far this was built once, by hand). A generator needs the pads
from the board (`kicad-cli` or `pcbnew`), the BOM grouped into bags, and per bag a package drawing type and its
pin roles. Everything below is written so that it can become one.

## Assembly sheet (AS)

Page: A4 landscape, 8 mm margins. Top band: board name, side, scale, orientation reference ("USB-C at the bottom").
Below it the board, as wide as the page allows. The lower half holds the legend boxes in a grid (four columns
fit A4 landscape), filled column by column in soldering order.

Board drawing:

| Element | Drawing |
|---|---|
| pad | dashed hairline outline |
| part body | solid hairline outline, white fill |
| reference | bold, black, white halo, centred on the part (AS-2) |
| electrolytic | circle, the minus half hatched, a large `+` outside on the plus side |
| diode | solid black band at the cathode end, labelled |
| SOT-23 transistor / FET | the pin that goes to GND marked bold `E` or `S` next to its pad |
| DPAK | `tab = D` on the tab, `G` and `S` at the legs |
| module | outline only, with its orientation features (USB, antenna, "components up") |
| off-board wire pad | signal name bold, wire colour in italics below, a 0.9 mm line from the pad into the margin |

Legend box per bag (one box per bag label, same order as the labels):

1. reference designators, bold
2. the text printed on the supplier's bag, so the bag can be found ("which bag is this?"), and quantity
3. part type and main specs, one line
4. order or article number; references not on the silkscreen
5. one bold line with the placement hint ("tab (drain) right · source bottom left")

Plus three boxes without a bag: *check before powering up* (the first rows of the test table), *rules* (open one
bag at a time; unmarked ceramics; parts that look alike; the same value in two sizes; what E, S, G, D mean) and
*symbols* (what dashed, solid, hatched and the band mean). Keep every legend line short (about 60 characters at
2.4 mm type); the generator wraps long lines and reports any box that still overflows instead of shrinking type.

Off-board wires (AS-4): use the colour convention of the wire stock you have and say it in the legend. With
standard USB cable colours D− is white; with three-colour hook-up wire, blue for D− works. Give the length (a
few centimetres more than the route, EN-5) and the order: tin all ends, solder the module or breakout end first
while it lies flat, then the board end, from the top side.

## Bag labels (BG)

Sheet: A4 portrait, 3 × 5 labels of 65 × 56 mm, centred (7.5 mm side and 8.5 mm top margin), thin cut lines.
Page 2 is the same labels with the columns mirrored, so a long-edge duplex print puts each label's back
behind its front. Print a test sheet against the light to check alignment before the real one.

Label anatomy, top to bottom:

```
+-------------------------------------------------------------+
| board name · revision                       article number  |
| R4 R6 R7                                         100 kΩ     |   refs large, value large
| resistor · 0805 · 3 pcs · "<text on the bag>"               |   one line, never wraps
| +-------------+  hint, 2–3 lines, key words bold            |
| | package     |  "The LEFT of the two SOT-23. E = bottom    |
| | drawing     |   left (GND)."                              |
| +-------------+  minor specs small: 1 % · 0805 · "1003"     |
| +---------------------------------------------------------+ |
| | mini-map: all pads grey, these pads black, boxed, + ref | |
| +---------------------------------------------------------+ |
| view: component side, <orientation feature> at the bottom   |
+-------------------------------------------------------------+
```

Package drawings are to the real proportions, enlarged and drawn as the part lies on the board in that spot
(same rotation as on the mini-map), with simple shading so they look like the part in the bag:

| Package | Shown |
|---|---|
| 0805 / 1206 chip | ceramic brown body for capacitors, black for resistors, tinned ends; a 1206 next to an 0805 at the same scale when both sizes exist with one value |
| SOT-23 | three legs on the true sides, every leg named, the GND leg bold with "→ GND" |
| SMA / SOD | the cathode band, "band = cathode" |
| DPAK | the tab with "tab = D", legs G and S, S bold when it goes to the supply or GND |
| SMD electrolytic | the plastic base with its chamfered + corners, the black minus segment on the can, a large `+`; one drawing per orientation if the parts sit in different directions |

Mini-map: the whole board outline at label width, every pad in light grey, the target pads black, a box (or
circle for an electrolytic) around each target part with its reference in bold next to it. Default label side is
right, then left if there is no room; a per-reference override (left, right, below) handles crowded spots. Show
the orientation features (module outline, connector names) in grey so the map reads the same way as the sheet.

Checks before printing (BG-4): the reference line, value and kind line fit on one line; no hint text is cut at
the bottom; map labels do not overlap each other, pads of other targets or the outline; page 2 equals page 1
mirrored.

## Commissioning test table (CT)

One row per measurement, in the order they are done:

| Step | Instrument | Probes | Expected | If not |
|---|---|---|---|---|
| 1 | multimeter, continuity (beeper); COM and VΩ sockets | VIN – GND | no beep | short at the input: check C1, the FET tab |
| 2 | diode test, select button until the diode symbol shows | red on GND, black on 3V3 | 0.4–0.7 V (supply clamp of the MCU) | OL: MCU not soldered at its GND or 3V3 pin |
| 3 | DC volts, 20 V range; supply 5 V, current limit 100 mA | OUT 5V – GND | 5.0 V ± 0.2 V | … |

Name the instrument steps the way the user's meter is labelled (mode dial position, function button, which
socket). Diode test and continuity often share one dial position and a select button.

Deriving expected values (CT-2): for every pair of probe points, walk all paths between the two nets in the
schematic, not only the part under test. A diode-test reading is the lowest forward voltage of any chain that
conducts in that direction, a resistance reading is all paths in parallel. Typical hidden paths:

- MOSFET body diodes (a load switch conducts backwards by one diode drop);
- ESD and clamp diodes of MCU and interface pins to their supply rail, and from there on through the MCU's
  own supply regulator or decoupling;
- discharge resistors, dividers and pull-ups that tie a net to GND or a rail.

Example: a test between a supply net and GND was expected as "OL" because the only intended path was an open
FET. The meter showed about 2.4 V, through the FET's body diode, a discharge resistor and an MCU input clamp in
series. A cross-check (measuring the chain's pieces one by one) confirmed it, so the board was fine. Write such
values into the table with the path that causes them.

After closing the case (CT-3), repeat: continuity of every off-board wire end to end, and the device's own link
diagnostics (FW-3). In the build these rules come from, closing the lid tore off one data wire; the device had
power and no data, and only the per-line "idle level / bytes seen" readout made that visible without opening it
again.
