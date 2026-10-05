"""Part research through distributor APIs (docs/sourcing-apis.md): offers with stock, packaging and price breaks for a
manufacturer part number, normalised across suppliers and cached, so the design-to-cost search (cost.py) and the parts
list of the review PDF read the same data.

  python -m pcbtools parts search "ptc fuse 1206" --where "Current - Hold (Ih) (Max)>=0.5A" --qty 25
  python -m pcbtools parts offers ATMEGA32U4-AU USBLC6-2SC6 --cache offers.json
  python -m pcbtools parts compare bom-options.json --cache offers.json     table: part x supplier, cheapest marked
  python -m pcbtools parts fill bom-options.json --cache offers.json        writes the offers into the BOM options

Keys come from the environment, never from files in the repository:
  NEXAR_CLIENT_ID, NEXAR_CLIENT_SECRET     https://portal.nexar.com
  DIGIKEY_CLIENT_ID, DIGIKEY_CLIENT_SECRET https://developer.digikey.com
  MOUSER_API_KEY                           https://www.mouser.com/api-hub/
  FARNELL_API_KEY                          https://partner.element14.com
Providers without a key are skipped. One request per second and provider; results are cached with their date, a
cached part is not fetched again unless --refresh is given. Written against the providers' documentation; check the
first results against the shop page."""
import datetime
import json
import os
import time
import urllib.parse
import urllib.request

CURRENCY = os.environ.get("PARTS_CURRENCY", "EUR")
COUNTRY = os.environ.get("PARTS_COUNTRY", "DE")
_last = {}


def _wait(provider):
    delay = time.time() - _last.get(provider, 0)
    if delay < 1.0:
        time.sleep(1.0 - delay)
    _last[provider] = time.time()


def _post(url, data, headers):
    body = data if isinstance(data, bytes) else json.dumps(data).encode()
    with urllib.request.urlopen(urllib.request.Request(url, data=body, headers=headers), timeout=30) as response:
        return json.load(response)


def _get(url, headers=None):
    with urllib.request.urlopen(urllib.request.Request(url, headers=headers or {}), timeout=30) as response:
        return json.load(response)


def _token(url, client_id, secret):
    data = urllib.parse.urlencode({"grant_type": "client_credentials", "client_id": client_id,
                                   "client_secret": secret}).encode()
    return _post(url, data, {"Content-Type": "application/x-www-form-urlencoded"})["access_token"]


def nexar(mpn):
    _wait("nexar")
    token = _token("https://identity.nexar.com/connect/token", os.environ["NEXAR_CLIENT_ID"],
                   os.environ["NEXAR_CLIENT_SECRET"])
    query = """query ($q: String!, $country: String!, $currency: String!) {
      supSearchMpn(q: $q, limit: 1, country: $country, currency: $currency) { results { part { mpn
        manufacturer { name } sellers(authorizedOnly: true) { company { name } offers { sku clickUrl packaging moq
        inventoryLevel prices { quantity convertedPrice convertedCurrency } } } } } } }"""
    result = _post("https://api.nexar.com/graphql", {"query": query, "variables": {"q": mpn, "country": COUNTRY,
                                                                                  "currency": CURRENCY}},
                   {"Authorization": f"Bearer {token}", "Content-Type": "application/json"})
    offers = []
    for item in result["data"]["supSearchMpn"]["results"] or []:
        part = item["part"]
        for seller in part["sellers"]:
            for offer in seller["offers"]:
                breaks = [[p["quantity"], p["convertedPrice"]] for p in offer["prices"]]
                if breaks:
                    offers.append({"supplier": seller["company"]["name"], "via": "Nexar", "mpn": part["mpn"],
                                   "manufacturer": part["manufacturer"]["name"], "sku": offer["sku"],
                                   "url": offer["clickUrl"], "stock": offer["inventoryLevel"], "moq": offer["moq"],
                                   "packaging": offer["packaging"], "breaks": breaks, "currency": CURRENCY})
    return offers


def digikey(mpn):
    _wait("digikey")
    token = _token("https://api.digikey.com/v1/oauth2/token", os.environ["DIGIKEY_CLIENT_ID"],
                   os.environ["DIGIKEY_CLIENT_SECRET"])
    headers = {"Authorization": f"Bearer {token}", "X-DIGIKEY-Client-Id": os.environ["DIGIKEY_CLIENT_ID"],
               "X-DIGIKEY-Locale-Site": COUNTRY, "X-DIGIKEY-Locale-Currency": CURRENCY,
               "Content-Type": "application/json"}
    result = _post("https://api.digikey.com/products/v4/search/keyword", {"Keywords": mpn, "Limit": 5}, headers)
    offers = []
    for product in result.get("Products", []):
        if product.get("ManufacturerProductNumber", "").upper() != mpn.upper():
            continue
        for variation in product.get("ProductVariations", []):
            breaks = [[p["BreakQuantity"], p["UnitPrice"]] for p in variation.get("StandardPricing", [])]
            if breaks:
                offers.append({"supplier": "DigiKey", "via": "DigiKey API", "mpn": product["ManufacturerProductNumber"],
                               "manufacturer": product.get("Manufacturer", {}).get("Name"),
                               "sku": variation.get("DigiKeyProductNumber"), "url": product.get("ProductUrl"),
                               "stock": variation.get("QuantityAvailableforPackageType", product.get("QuantityAvailable")),
                               "moq": variation.get("MinimumOrderQuantity"),
                               "packaging": variation.get("PackageType", {}).get("Name"), "breaks": breaks,
                               "currency": CURRENCY,
                               "parameters": {p["ParameterText"]: p["ValueText"] for p in product.get("Parameters", [])}})
    return offers


def mouser(mpn):
    _wait("mouser")
    url = "https://api.mouser.com/api/v1/search/partnumber?apiKey=" + urllib.parse.quote(os.environ["MOUSER_API_KEY"])
    result = _post(url, {"SearchByPartRequest": {"mouserPartNumber": mpn, "partSearchOptions": "Exact"}},
                   {"Content-Type": "application/json"})
    offers = []
    for part in result.get("SearchResults", {}).get("Parts", []) or []:
        breaks = [[b["Quantity"], float(b["Price"].replace("€", "").replace(",", ".").strip())]
                  for b in part.get("PriceBreaks", []) if b.get("Price")]
        if breaks:
            stock = "".join(c for c in str(part.get("Availability", "")) if c.isdigit())
            offers.append({"supplier": "Mouser", "via": "Mouser API", "mpn": part["ManufacturerPartNumber"],
                           "manufacturer": part.get("Manufacturer"), "sku": part.get("MouserPartNumber"),
                           "url": part.get("ProductDetailUrl"), "stock": int(stock) if stock else None,
                           "moq": int(part.get("Min") or 1), "packaging": None, "breaks": breaks,
                           "currency": part.get("PriceBreaks", [{}])[0].get("Currency", CURRENCY)})
    return offers


def farnell(mpn):
    _wait("farnell")
    params = {"term": f"manuPartNum:{mpn}", "storeInfo.id": "de.farnell.com", "resultsSettings.offset": 0,
              "resultsSettings.numberOfResults": 5, "resultsSettings.responseGroup": "prices,inventory",
              "callInfo.omitXmlSchema": "false", "callInfo.responseDataFormat": "json",
              "callInfo.apiKey": os.environ["FARNELL_API_KEY"]}
    result = _get("https://api.element14.com/catalog/products?" + urllib.parse.urlencode(params))
    offers = []
    for product in result.get("manufacturerPartNumberSearchReturn", {}).get("products", []):
        breaks = [[p["from"], p["cost"]] for p in product.get("prices", [])]
        if breaks:
            offers.append({"supplier": "Farnell", "via": "element14 API", "mpn": product.get("translatedManufacturerPartNumber"),
                           "manufacturer": product.get("vendorName"), "sku": product.get("sku"), "url": None,
                           "stock": product.get("stock", {}).get("level"), "moq": product.get("translatedMinimumOrderQuality"),
                           "packaging": product.get("packSize"), "breaks": breaks, "currency": CURRENCY})
    return offers


UNITS = {"p": 1e-12, "n": 1e-9, "u": 1e-6, "µ": 1e-6, "m": 1e-3, "k": 1e3, "K": 1e3, "M": 1e6, "G": 1e9}


def quantity(text):
    """First number with an SI prefix in a parameter text: '500 mA' -> 0.5, '16V' -> 16, '±1%' -> 1."""
    import re
    found = re.search(r"([-+]?\d+(?:[.,]\d+)?)\s*([pnuµmkKMG]?)", str(text))
    if not found:
        return None
    return float(found.group(1).replace(",", ".")) * UNITS.get(found.group(2), 1)


def matches(parameters, conditions):
    """Conditions like 'Voltage - Rated>=16V', 'Package / Case=0805', 'Mounting Type~Surface'; all must hold."""
    import re
    for condition in conditions:
        name, op, wanted = re.match(r"(.+?)(>=|<=|=|~)(.+)", condition).groups()
        value = next((v for k, v in parameters.items() if k.lower() == name.strip().lower()), None)
        if value is None:
            return False
        if op == "~" and wanted.lower() not in value.lower():
            return False
        if op == "=" and wanted.lower() != value.lower() and quantity(wanted) != quantity(value):
            return False
        if op in (">=", "<=") and (quantity(value) is None or (quantity(value) < quantity(wanted) if op == ">="
                                                               else quantity(value) > quantity(wanted))):
            return False
    return True


def search(keywords, conditions, qty, limit=50):
    """Parametric search over DigiKey's catalogue (the only key-based API here with full parameters): in stock, all
    conditions met, sorted by the unit price at qty."""
    if "digikey" not in available():
        raise SystemExit("parts search needs DIGIKEY_CLIENT_ID and DIGIKEY_CLIENT_SECRET")
    _wait("digikey")
    token = _token("https://api.digikey.com/v1/oauth2/token", os.environ["DIGIKEY_CLIENT_ID"],
                   os.environ["DIGIKEY_CLIENT_SECRET"])
    headers = {"Authorization": f"Bearer {token}", "X-DIGIKEY-Client-Id": os.environ["DIGIKEY_CLIENT_ID"],
               "X-DIGIKEY-Locale-Site": COUNTRY, "X-DIGIKEY-Locale-Currency": CURRENCY,
               "Content-Type": "application/json"}
    body = {"Keywords": keywords, "Limit": limit, "FilterOptionsRequest": {"SearchOptions": ["InStock"]}}
    result = _post("https://api.digikey.com/products/v4/search/keyword", body, headers)
    from .cost import unit_cost
    rows = []
    for product in result.get("Products", []):
        parameters = {p["ParameterText"]: p["ValueText"] for p in product.get("Parameters", [])}
        if not matches(parameters, conditions):
            continue
        best = None
        for variation in product.get("ProductVariations", []):
            breaks = [[p["BreakQuantity"], p["UnitPrice"]] for p in variation.get("StandardPricing", [])]
            if breaks:
                cost, _ = unit_cost({"breaks": breaks, "pack": variation.get("MinimumOrderQuantity") or 1}, qty)
                best = cost if best is None else min(best, cost)
        if best is not None:
            rows.append((best, product["ManufacturerProductNumber"], product.get("Manufacturer", {}).get("Name", ""),
                         product.get("Description", {}).get("ProductDescription", ""), product.get("QuantityAvailable")))
    print(f"{'cost/' + str(qty):>8}  {'part':28} {'maker':18} {'stock':>8}  description")
    for cost, mpn, maker, text, stock in sorted(rows):
        print(f"{cost:8.3f}  {mpn:28} {maker[:18]:18} {str(stock):>8}  {text[:60]}")
    return rows


PROVIDERS = {"nexar": (nexar, ("NEXAR_CLIENT_ID", "NEXAR_CLIENT_SECRET")),
             "digikey": (digikey, ("DIGIKEY_CLIENT_ID", "DIGIKEY_CLIENT_SECRET")),
             "mouser": (mouser, ("MOUSER_API_KEY",)), "farnell": (farnell, ("FARNELL_API_KEY",))}


def available():
    return [name for name, (_, keys) in PROVIDERS.items() if all(os.environ.get(k) for k in keys)]


def offers(mpns, cache_path, refresh=False):
    cache = json.load(open(cache_path, encoding="utf-8")) if os.path.exists(cache_path) else {}
    providers = available()
    if not providers:
        print("no API keys in the environment; using the cache only")
    for mpn in mpns:
        if mpn in cache and not refresh:
            continue
        found, errors = [], []
        for name in providers:
            try:
                found += PROVIDERS[name][0](mpn)
            except Exception as error:
                errors.append(f"{name}: {error}")
        cache[mpn] = {"retrieved": datetime.datetime.now().isoformat(timespec="seconds"), "offers": found,
                      "errors": errors}
        print(f"{mpn}: {len(found)} offers" + (f", errors: {'; '.join(errors)}" if errors else ""))
    with open(cache_path, "w", encoding="utf-8") as handle:
        json.dump(cache, handle, indent=1)
    return cache


def bom_parts(bom):
    """(part name, mpn) for every part an option of the BOM can use; the mpn comes from bom["mpn"]."""
    names = []
    for line in bom["lines"]:
        for option in line["options"]:
            names += [option["part"]] if "part" in option else [p for p, _ in option["parts"]]
    return [(n, bom.get("mpn", {}).get(n)) for n in dict.fromkeys(names)]


def fill(bom_path, cache_path):
    bom = json.load(open(bom_path, encoding="utf-8"))
    cache = offers([m for _, m in bom_parts(bom) if m], cache_path)
    for name, mpn in bom_parts(bom):
        if mpn and cache.get(mpn, {}).get("offers"):
            bom["offers"][name] = cache[mpn]["offers"]
    with open(bom_path, "w", encoding="utf-8") as handle:
        json.dump(bom, handle, indent=1, ensure_ascii=False)


def compare(bom_path, series):
    bom = json.load(open(bom_path, encoding="utf-8"))
    from .cost import unit_cost
    suppliers = sorted({o["supplier"] for offers_ in bom["offers"].values() for o in offers_})
    print(f"cost for {series} pieces, packaging units and price breaks included; * cheapest")
    print("part".ljust(36) + "".join(s[:14].rjust(16) for s in suppliers))
    for name, _ in bom_parts(bom):
        cells = {}
        for offer in bom["offers"].get(name, []):
            cost, bought = unit_cost(offer, series)
            cells[offer["supplier"]] = min(cells.get(offer["supplier"], 1e9), cost)
        best = min(cells.values()) if cells else None
        print(name[:35].ljust(36) + "".join(
            (f"{cells[s]:.2f}{'*' if cells[s] == best else ' '}" if s in cells else "-").rjust(16) for s in suppliers))


def main(argv):
    import argparse
    parser = argparse.ArgumentParser(prog="pcbtools parts", description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("action", choices=["search", "offers", "compare", "fill"])
    parser.add_argument("--where", action="append", default=[], help="parameter condition, see search()")
    parser.add_argument("--qty", type=int, default=1, help="quantity the unit price is compared at")
    parser.add_argument("items", nargs="+")
    parser.add_argument("--cache", default="offers.json")
    parser.add_argument("--series", type=int, default=1)
    parser.add_argument("--refresh", action="store_true")
    args = parser.parse_args(argv)
    if args.action == "search":
        search(" ".join(args.items), args.where, args.qty)
    elif args.action == "offers":
        offers(args.items, args.cache, args.refresh)
    elif args.action == "fill":
        fill(args.items[0], args.cache)
    else:
        compare(args.items[0], args.series)
