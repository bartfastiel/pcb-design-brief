# Sourcing APIs

Machine-readable price, stock and specification data, for the design-to-cost loop (brief §6a) and the parts lists
(§10, §12). Use an API wherever one exists; read public product pages only for single parts, slowly, and stop at any
bot protection, marking the part "check manually" with its link. Keys belong in environment variables, never in the
repository.

Checked against each provider's own developer documentation in October 2026. Access models change; read the
linked terms before use.

| Provider | Kind | Access | What it returns | Docs |
|---|---|---|---|---|
| Nexar (Octopart data) | Aggregator | self-service key | GraphQL: offers, stock and price breaks from many distributors, parametric specs | [docs](https://www.altium.com/documentation/altium-developer-center/octopart/api) |
| Farnell / element14 / Newark | Distributor | self-service key | Product Search API (REST and SOAP, XML/JSON; keyword, element14 part number, MPN search; tiered prices, stock per warehouse, lead time, attributes, datasheets) | [docs](https://partner.element14.com/docs) |
| Mouser | Distributor | self-service key | REST: keyword and part-number search with price breaks, stock, lead time; cart and orders | [docs](https://api.mouser.com/api/docs/ui/index) |
| TME (Transfer Multisort Elektronik) | Distributor | self-service key | Product API: catalogue and technical data, prices (with or without customer discounts, multiple currencies), real-time warehouse stock, parametric search. | [docs](https://developers.tme.eu/) |
| Arrow Electronics (incl. Verical) | Distributor | on request | REST: pricing and availability; orders | [docs](https://developers.arrow.com/api/) |
| Avnet (Avnet EMEA: Abacus, Silica, EBV) | Distributor | on request | REST: real-time price and availability | [docs](https://apiportal.avnet.com/) |
| Conrad Electronic | Distributor | on request (self-registration, key active after approval) | REST: product search, price and availability | [docs](https://developer.conrad.com/get-started) |
| DigiKey | Distributor | self-service, OAuth2 | REST: product information v4 (search, prices, stock, parameters), quotes, ordering | [docs](https://developer.digikey.com/products/product-information-v4) |
| Future Electronics | Distributor | on request | Real-time inventory, pricing, availability and lead-time API (documentation downloadable from the page). | [docs](https://www.futureelectronics.com/api-solutions) |
| Rutronik (Rutronik24) | Distributor | on request | XML or JSON API: unit and graduated prices in several currencies, daily stock, standard lead time, MOQ, packing unit, package, description. | [docs](https://www.rutronik.com/article/api-interface-on-the-way-to-automated-procurement) |
| Würth Elektronik (eiSos) Customer API | Distributor | on request | REST: product/article data, current and future availability/stock, commercial information, datasheets/files, lifecycle status. | [docs](https://www.we-online.com/en/support/collaboration/api) |
| JLCPCB (JLC API Platform) | PCB fab | on request | PCB API (Gerber upload, real-time quote, order, tracking), Stencil API, 3D Printing API, Components API (JLC/LCSC library: real-time price, inventory, specs). | [docs](https://api.jlcpcb.com/) |
| PCBWay Partner API | PCB fab / assembly | partner only | REST: PCB and SMT assembly quotes, freight, orders, production status | [docs](https://api-partner.pcbway.com/Help) |
| SnapMagic Search (SnapEDA) API | CAD data | on request | HTTP API for symbols, footprints and 3D models (Altium, KiCad, Eagle, OrCAD, ...). | [docs](https://www.snapeda.com/get-api/) |
| Ultra Librarian | CAD data | OAuth | REST/OpenAPI v1: part search/findpart, symbol/footprint/3D previews, export to CAD formats, reference designs, CIP endpoints (distributor lists, part status). | [docs](https://api.ultralibrarian.com/api-docs/) |

## Which to start with

- **Nexar** first: one GraphQL query returns offers, stock and price breaks from many distributors plus
  parametric specs; the free evaluation plan covers a small BOM.
- **DigiKey, Mouser, Farnell, TME**: self-service keys; per-distributor prices with packaging units and lead times,
  and parametric data to verify a candidate against the requirement (voltage, tolerance, temperature range).
- **Conrad, Arrow, Avnet, Future, Rutronik, Würth Elektronik**: documented APIs, access after the provider
  approves it.
- **PCB and assembly**: JLCPCB and PCBWay document quote APIs (on request / partner); for other fabs use their
  public price calculators by hand.
- **CAD data** (symbols, footprints, 3D models): Ultra Librarian, SnapMagic.

`scripts/sourcing/bom_cost.py` reads offers from these APIs (or from a cached JSON) and searches for the cheapest
consistent BOM for a series size.
