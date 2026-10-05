---
name: pcb-design-brief
description: Rules, workflow gates and review-PDF specification for designing a small-series, hand-soldered PCB with KiCad and a 3D-printed enclosure. Use when designing, reviewing or documenting a PCB or its enclosure.
---

# PCB design brief

1. Read `BRIEF.md` in full (repository root of pcb-design-brief, or the copy in this project).
2. Find the project's intake file (`intake.md`). Missing: copy `templates/intake.md`, ask every
   open IN question in one batch, then work autonomously.
3. Run `python -m pcbtools doctor`; report what is missing. Write the design as data (`design.json`) and let
   `pcbtools` generate and check everything (§3 TL-1 … TL-4, `docs/automation.md`).
4. Follow the phases and gates of §4. Do not show results before PR-5 (look at them yourself).
5. Finish with the definition of done (§14) and list every deviation by rule ID.
