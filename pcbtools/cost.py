"""Design-to-cost search over a BOM (brief §6a): every line lists the parts that would do the job, the script picks
the combination with the lowest cost for the series and reports the step from the first choice.

  python -m pcbtools cost bom.json [--series 25] [--live] [-o result.json]

bom.json
  {"series": 25,
   "costs": {"unique_part": 1.50, "placement": 0.02, "shipping": {"Distributor A": 4.95}},
   "lines": [{"refs": ["R1", "R2"], "function": "USB series resistor",
              "options": [{"part": "R0805 22R"}, {"name": "2 x 47R parallel", "parts": [["R0805 47R", 4]]}]}],
   "area_mm2": {"R0805 22R": 6.1},  "mpn": {"R0805 22R": "<manufacturer part number for --live>"},
   "offers": {"R0805 22R": [{"supplier": "Distributor A", "mpn": "...", "pack": 1,
                             "breaks": [[1, 0.05], [100, 0.012]], "stock": 5000}]}}

An option is one part per reference, or an explicit list of parts and counts per device ("parts"), so one line can
cover a group whose alternatives differ in structure (4 x 100 nF + 1 x 10 uF against 5 x 1 uF). Lines that end up on
the same part consolidate: one distinct part instead of two, one line fee and one feeder less. Only list options that
meet the requirement; the script compares cost, it does not check the circuit. Costs: parts at the series quantity with packaging units and price breaks, a fee per distinct part
(reel set-up, feeder, picking), a fee per placement, and shipping for every supplier used.

--live fills "offers" for parts that carry an "mpn" from every distributor API with keys in the environment
(pcbtools parts, cached in offers.json next to the BOM); without it the offers in the file are used as they are."""
import argparse
import itertools
import json
import math
import os

NEXAR_QUERY = """query ($mpn: String!) { supSearchMpn(q: $mpn, limit: 3) { results { part { mpn sellers {
  company { name } offers { packaging moq inventoryLevel prices { quantity price currency } } } } } } }"""


def unit_cost(offer, qty):
    """Cost of qty parts from one offer: rounded up to the packaging unit, at the price break that quantity reaches."""
    pack = max(offer.get("pack") or 1, offer.get("moq") or 1)
    bought = math.ceil(qty / pack) * pack
    price = None
    for brk, value in sorted(offer["breaks"]):
        if bought >= brk:
            price = value
    if price is None:
        price = sorted(offer["breaks"])[0][1]
    return bought * price, bought


def parts_of(line, option):
    """(part, count per device) of an option: one part per reference by default, or an explicit list."""
    if "parts" in option:
        return [(part, count) for part, count in option["parts"]]
    return [(option["part"], len(line["refs"]) * option.get("per_ref", 1))]


def name_of(option):
    return option.get("name") or option.get("part") or " + ".join(f"{c} x {p}" for p, c in option["parts"])


def best_offer(offers, qty):
    usable = [o for o in offers if (o.get("stock") is None or o["stock"] >= qty) and o.get("breaks")]
    if not usable:
        return None
    return min(((unit_cost(o, qty), o) for o in usable), key=lambda t: t[0][0])


def evaluate(bom, choice, series):
    """Total cost of one choice (option index per line) and its breakdown."""
    need = {}
    places = 0
    for line, index in zip(bom["lines"], choice):
        for part, count in parts_of(line, line["options"][index]):
            need[part] = need.get(part, 0) + count * series
            places += count
    costs = bom.get("costs", {})
    parts, suppliers, missing = 0.0, set(), []
    detail = {}
    for part, qty in need.items():
        found = best_offer(bom["offers"].get(part, []), qty)
        if not found:
            missing.append(part)
            continue
        (cost, bought), offer = found
        parts += cost
        suppliers.add(offer["supplier"])
        detail[part] = {"qty": qty, "bought": bought, "cost": round(cost, 2), "supplier": offer["supplier"],
                        "mpn": offer.get("mpn")}
    shipping = sum(costs.get("shipping", {}).get(s, 0.0) for s in suppliers)
    fixed = costs.get("unique_part", 0.0) * len(need) + costs.get("placement", 0.0) * places * series
    total = parts + shipping + fixed + (1e9 if missing else 0)
    area = sum(bom.get("area_mm2", {}).get(part, 0) * count
               for line, i in zip(bom["lines"], choice) for part, count in parts_of(line, line["options"][i]))
    return {"total": round(total, 2), "parts": round(parts, 2), "shipping": round(shipping, 2),
            "fixed": round(fixed, 2), "distinct": len(need), "placements": places, "area_mm2": round(area, 1),
            "suppliers": sorted(suppliers), "missing": missing, "detail": detail}


def search(bom, series):
    """Exhaustive for small option spaces, otherwise coordinate descent from the first choice until nothing improves."""
    sizes = [len(line["options"]) for line in bom["lines"]]
    if math.prod(sizes) <= 50000:
        best = min(itertools.product(*[range(n) for n in sizes]), key=lambda c: evaluate(bom, c, series)["total"])
        return list(best)
    choice = [0] * len(sizes)
    improved = True
    while improved:
        improved = False
        for k, n in enumerate(sizes):
            for option in range(n):
                trial = choice[:k] + [option] + choice[k + 1:]
                if evaluate(bom, trial, series)["total"] < evaluate(bom, choice, series)["total"] - 1e-9:
                    choice, improved = trial, True
    return choice


def main(argv=None):
    parser = argparse.ArgumentParser(prog="pcbtools cost", description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("bom")
    parser.add_argument("--series", type=int)
    parser.add_argument("--live", action="store_true")
    parser.add_argument("-o", "--output")
    args = parser.parse_args(argv)
    bom = json.load(open(args.bom, encoding="utf-8"))
    series = args.series or bom.get("series", 1)
    if args.live:
        from .parts import fill
        fill(args.bom, os.path.join(os.path.dirname(os.path.abspath(args.bom)), "offers.json"))
        bom = json.load(open(args.bom, encoding="utf-8"))
    first = [0] * len(bom["lines"])
    best = search(bom, series)
    before, after = evaluate(bom, first, series), evaluate(bom, best, series)
    changes = [{"refs": line["refs"], "function": line.get("function", ""), "from": name_of(line["options"][0]),
                "to": name_of(line["options"][i]), "why": line["options"][i].get("note", "")}
               for line, i in zip(bom["lines"], best) if i != 0]
    result = {"series": series, "first": before, "optimised": after, "changes": changes,
              "choice": {", ".join(line["refs"]): name_of(line["options"][i]) for line, i in zip(bom["lines"], best)}}
    if args.output:
        with open(args.output, "w", encoding="utf-8") as handle:
            json.dump(result, handle, indent=1)
    print(f"series {series}: first choice {before['total']:.2f}, optimised {after['total']:.2f} "
          f"({before['distinct']} -> {after['distinct']} distinct parts, {before['area_mm2']} -> {after['area_mm2']} mm2)")
    for change in changes:
        print(f"  {', '.join(change['refs'])}: {change['from']} -> {change['to']}")


if __name__ == "__main__":
    main()
