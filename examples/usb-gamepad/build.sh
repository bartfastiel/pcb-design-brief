#!/usr/bin/env bash
# Builds the example from scratch: schematic, board, checks, enclosure, design to cost, renders and the review PDF.
# Programs are found by `python -m pcbtools doctor`; run that first if a step complains.
set -euo pipefail
cd "$(dirname "$0")"
export PYTHONPATH="$(cd ../.. && pwd)${PYTHONPATH:+:$PYTHONPATH}"
PYTHON="${PYTHON:-python}"
T="$PYTHON -m pcbtools"
B=build
mkdir -p $B/layers $B/3d

$T schematic design.json --out $B
$T board design.json --out $B
CLI="$($PYTHON -c 'from pcbtools.tools import kicad_cli; print(kicad_cli())')"

"$CLI" sch export pdf -o $B/schematic.pdf $B/usb-gamepad.kicad_sch > /dev/null
"$CLI" pcb export glb -f --user-origin 100x100mm --include-tracks --include-pads --include-silkscreen \
    --include-soldermask -o $B/3d/board.glb $B/usb-gamepad.kicad_pcb > /dev/null
"$CLI" pcb export glb -f --user-origin 100x100mm --no-board-body -o $B/3d/parts.glb $B/usb-gamepad.kicad_pcb > /dev/null
"$CLI" pcb export gerbers -o $B/gerbers/ $B/usb-gamepad.kicad_pcb > /dev/null
"$CLI" pcb export drill -o $B/gerbers/ $B/usb-gamepad.kicad_pcb > /dev/null
$T layer_images --kicad-cli "$CLI" $B/usb-gamepad.kicad_pcb $B/layers

"$PYTHON" make_enclosure.py $B/3d/parts.glb $B/enclosure
E=$B/enclosure
$T assembly_check -o $B/assembly base=$E/base.stl top=$E/top.stl caps=$E/caps.stl \
    board=$E/board.stl parts=$E/parts.stl screws=$E/screws.stl inserts=$E/inserts.stl \
    --allow screws:inserts --allow top:inserts --allow screws:base --check-only parts
$T printability -o $B/printability base=$E/base.stl top=$E/top-print.stl cap=$E/cap-print.stl \
    cap-small=$E/cap-small-print.stl
$T tech_drawing -o $B/tech-drawing.png --title "USB gamepad enclosure, PETG" \
    Base=$E/base.stl Top=$E/top-print.stl Cap=$E/cap-print.stl
$T cost bom-options.json -o $B/bom-result.json

"$PYTHON" make_review.py $B
$T render $B/3d/scene-overview.json $B/3d/overview.png
$T render $B/3d/scene-board.json $B/3d/board.png
$T render $B/3d/scene-parts-top.json $B/3d/parts-top.png
$T render $B/3d/board.glb $B/3d/stack.png --size 1300x2300 --gap 16 --elevation 26 --stack
"$PYTHON" make_review.py $B --compose
$T review_pdf review.json usb-gamepad-review.pdf
