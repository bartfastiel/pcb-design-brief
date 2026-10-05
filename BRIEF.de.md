# PCB-Designvorgaben

Was „fertig“ bei einer handgelöteten Kleinserien-Platine mit 3D-gedrucktem Gehäuse bedeutet und
wie ein Agent (oder ein Mensch) mit möglichst wenig Rückfragen dorthin kommt.

- **MUSS / SOLLTE / DARF** im Sinne von RFC 2119.
- Jede Regel hat eine ID. Abweichungen werden mit ID und Begründung gemeldet (`HS-4: 0,3 mm
  zwischen zwei Bahnen an U1, der Router wird mit mehr nicht fertig`).
- Projektantworten in der Intake-Datei gehen den Vorgaben hier vor. Jede Abweichung wird dort
  festgehalten.

Die englische Fassung [BRIEF.md](BRIEF.md) ist maßgeblich; diese Übersetzung folgt ihr.

## 1 Klärung vorab (Intake)

Alle offenen Fragen **einmal, gesammelt, zu Beginn** stellen. Danach selbstständig arbeiten.
Unbekanntes, das nichts blockiert, wird zur benannten, markierten Annahme statt zur Frage.

| ID | Frage | Wozu | Vorgabe ohne Antwort |
|---|---|---|---|
| IN-1 | Verwendungszweck, Anforderungen, Beispiele oder Referenzdesigns | alles | fragen |
| IN-2 | Von Hand löten oder maschinell bestücken? | Padgrößen, Bauformen, Jokerfelder | Hand |
| IN-3 | Seriengröße (und wie viele davon Prototypen) | Staffelpreise, Jokerfelder, Nutzen | fragen |
| IN-4 | Budget für die Serie und was es abdeckt (Teile, Platine, Gehäuse, Versand, MwSt.) | Teileauswahl | fragen |
| IN-5 | Bevorzugte Lieferanten für Teile, Platine, Bestückung | Beschaffung | fragen |
| IN-6 | Lieferland und Währung | Shops, MwSt., Versand | fragen |
| IN-7 | Feste Mechanik: Platinenumriss, Steckerpositionen, Gehäuse, Befestigung | Layout | nichts fest |
| IN-8 | Umgebung: Temperatur, innen/außen, Netzspannung, Funk, mechanische Last | Auslegung | innen, 0–40 °C |
| IN-9 | Dürfen Werkzeuge installiert werden? Darf für Lieferantendaten ein Browser im Namen des Nutzers gesteuert werden? | Voraussetzungen, Beschaffung | fragen |

## 2 Grundsätze, nach Rang

1. **Funktion und Sicherheit zuerst.** Funk, Wärme und Grenzwerte gehen vor Kompaktheit und
   Optik.
2. **Nichts geht verloren.** Keine Daten, kein Arbeitsstand, keine Platinenfläche. Freie Fläche
   wird zu Jokerfeldern (§7) oder Beschriftung. Jeder Stand liegt in git.
3. **Alles ist nachvollziehbar.** Quelldateien, Berechnungen, Herkunft jeder Zahl und ein
   Review-PDF (§12), das jede Entscheidung erklärt.
4. **Nur verifizierte Daten.** Maße, Footprints, Grenzwerte und Preise stammen aus Datenblättern,
   Herstellerdateien, Messungen oder der Shopseite. Nie raten. Fehlt ein Wert oder ist unklar,
   welches Maß gemeint ist: fragen; bis zur Antwort als benannter Parameter führen und im
   Review-PDF markieren.
5. **Robust statt am Limit.** Großzügige Reserven, Störabstände, tolerant gegen
   Bedienungsfehler, wenig Störaussendung.
6. **Gut für die Hände,** die löten, prüfen und nacharbeiten.

## 3 Voraussetzungen

Prüfen und Versionen nennen. Nur mit Erlaubnis installieren (IN-9).

- git
- KiCad ≥ 8 mit `kicad-cli` und dem mitgelieferten Python (`pcbnew`)
- ein PDF-Betrachter und eine Möglichkeit, PDF-Seiten für die eigene Sichtprüfung zu rastern
- 3D: KiCad-Raytracer für Platinenbilder, Blender für realistische Szenen, OpenSCAD oder ein
  anderes CAD für das Gehäuse
- Python: `pymupdf`, `reportlab`, `pillow`, `numpy`, `trimesh`, `manifold3d`
- Playwright, falls Browser-Automatisierung erlaubt ist

## 4 Ablauf und Prüftore

| Phase | Ergebnis | Tor vor der nächsten Phase |
|---|---|---|
| 1 Intake | Intake-Datei | jede IN-Frage beantwortet oder Vorgabe übernommen |
| 2 Schaltung | Schaltplan, Berechnungstabelle | ERC 0 (Fehler **und** Warnungen); jedes Bauteil per Rechnung ausgelegt (§6) |
| 3 Beschaffung | Stückliste mit Lieferanten | alles bestellbar, Budget hält, sonst zurück zu 2 |
| 4 Layout | Platine, Fertigungsdaten | DRC 0 inkl. Warnungen, Schaltplan-Parität 0, keine offenen Verbindungen |
| 5 Gehäuse | Druckdateien | Zusammenbaucheck (§9) bestanden |
| 6 Review-PDF | PDF | vollständig (§12), jede Seite angesehen |
| 7 Übergabe | Commit, Push, Zusammenfassung | Definition of Done (§14) |

Schadet ein späterer Befund einer früheren Phase, geht die Arbeit dorthin zurück.

- **PR-1** Eine Quelle der Wahrheit: ein Generator-Skript oder, bei Handzeichnung, das
  KiCad-Projekt. Die Quelle ändern und neu erzeugen. Nie nur erzeugte Dateien flicken; der
  nächste Lauf löscht es.
- **PR-2** Von Hand bearbeitete Kopien von Designdateien werden nie eingecheckt und nie von
  Werkzeugen gelesen (feste Dateinamen, keine Globs).
- **PR-3** Früh und oft committen, mindestens in ein lokales Repository; pushen, sobald es ein
  Remote gibt.
- **PR-4** Nach jeder Änderung: alle Tore erneut prüfen und jedes abgeleitete Bild neu erzeugen
  (Renderings, Layout, Schaltplan, PDF). Ein veraltetes Bild ist ein Fehler.
- **PR-5** Jedes Rendering und jede PDF-Seite selbst ansehen, bevor sie gezeigt wird.
- **PR-6** Die Skripte für Renderings, Prüfungen und PDF neben dem Design ablegen, sodass das
  ganze Paket mit einem Befehl neu entsteht.

## 5 Layout für Handlötung

Gilt, wenn IN-2 „Hand“ ist.

- **HS-1** Pads deutlich größer als üblich: Chip-Pads um 0,5–1 mm nach außen verlängert, damit
  die Lötspitze Kupfer statt Bauteil trifft. Wärmeintensive Bauteile (MOSFET-Tab, Stecker)
  bekommen zusätzlich eine blanke Kupferfläche zum Vorheizen.
- **HS-2** Bevorzugt 0805/1206, SOT-23, SMA, DPAK. Kleinere Bauformen, QFN oder BGA nur, wenn
  unvermeidbar, und begründet.
- **HS-3** Bauteile verteilen; Platz für die Lötspitze ist wichtiger als kurze Bahnen, auch
  wenn ein Bauteil dann nicht mehr direkt an seinem Pin sitzt.
- **HS-4** Ziel für Abstände ≥ 0,5 mm. Bis zum Fertigungsminimum nur, wo unvermeidbar, und jeder
  Fall im Review-PDF begründet.
- **HS-5** Vias offen (ohne Lötstopplack) auf beiden Seiten, auch die vom Router erzeugten:
  Messpunkte und Nacharbeit. Nicht unter Bauteilkörpern oder Metallgehäusen, nicht in Pads.
- **HS-6** Signale ≥ 0,4 mm, wo Platz ist, bevorzugt unten, wo man sie auftrennen kann.
  Strombahnen für ≤ 10 K Erwärmung bemessen (IPC-2152).
- **HS-7** Bestückungsdruck: für jedes Bauteil eine Referenz, wo sie passt, sonst im
  Bestückungsplan; Werte als Liste auf der Platine, wenn Platz ist. Nie Druck auf Pads oder
  offenen Vias (eine DRC-Warnung ist ein Fehler).
- **HS-8** Polaritäts- und Pin-1-Markierungen bleiben nach dem Bestücken sichtbar.

## 6 Schaltung

- **CI-1** Für jedes Bauteil Spannung, Strom, Leistung und Temperatur berechnen. Grenzwert und
  Reserve in einer Tabelle festhalten.
- **CI-2** Vorgaben für die Reserve:

  | Bauteil | Grenze im ungünstigsten Fall |
  |---|---|
  | Widerstand | ≤ 50 % der Nennleistung |
  | Keramikkondensator | ≤ 50 % der Nennspannung (DC-Bias) |
  | Elektrolytkondensator | ≤ 80 % der Nennspannung, 105-°C-Typ |
  | Halbleiter | ≤ 50–70 % der absoluten Grenzwerte für Spannung, Strom, Leistung; Tj ≤ 100 °C |
  | Steckverbinder, Leitung | ≤ 70 % des Nennstroms |

- **CI-3** Robuste Werte: keine unnötig hochohmigen Knoten, ADC-Quellen ≤ etwa 10 kΩ oder mit
  Kondensator gepuffert, Pull-ups 1–10 kΩ, keine µA-Ströme, die Störungen einfangen. Den sicheren
  Zustand ohne Firmware festlegen.
- **CI-4** Bedienungsfehler: Verpolung, Stecken unter Spannung, ESD an berührbaren Kontakten,
  kurzgeschlossene Ausgänge. Dagegen schützen oder begründen, warum nicht.
- **CI-5** Wenig Störaussendung: Lasten weich schalten, kurze Hochstromschleifen, Abblockung am
  Pin.
- **CI-6** Jede Wertänderung erneut gegen das Datenblatt prüfen und die Tabelle nachziehen.
- **CI-7** Teure oder schwer lieferbare Teile: die Schaltung überdenken (§10).

## 7 Jokerfelder auf Prototypen

- **JF-1** Freies Kupfer beider Seiten wird mit unbeschalteten, blanken Lötfeldern gefüllt, wie
  eine Lochrasterplatine, für im Design vergessene Bauteile oder Drähte.
- **JF-2** Raster 2,54 mm, 0,5 mm Spalt zwischen den Feldern (ein 0805 oder ein Lottropfen
  überbrückt ihn). Am Rand nehmen die Felder die Form der freien Fläche an. Mindestens 1,2 mm
  breit und 2 mm².
- **JF-3** ≥ 1 mm Abstand zu allem funktionalen Kupfer und jeder Bohrung, damit beim Löten
  nichts versehentlich berührt wird. Bestückungsdruck, Bauteilflächen und Klemmflächen des
  Gehäuses bleiben frei. Funk-Sperrzone plus 3 mm.
- **JF-4** Durchkontaktiert nur, wo beide Seiten Platz haben (Bohrung 0,8 mm, Restring
  ≥ 0,45 mm), mit mindestens 5,08 mm Abstand.
- **JF-5** Von einem Skript nach dem Routing berechnet, nie von Hand gesetzt. Ein reiner
  Platinen-Footprint, nicht in Stückliste und Bestückungsdaten.
- **JF-6** Entfällt bei Serienfertigung, außer auf Wunsch (IN-3).

## 8 Funk, Mechanik, Umgebung

- **EN-1** Funk: Antennen-Sperrzone aus den Layoutdaten des Modulherstellers (Footprint,
  Referenzdesign), nicht aus Wikis. Darin kein Kupfer, keine Massefläche, keine Schrauben oder
  Einsätze. Abstand zu Gehäusewänden prüfen. Im Zweifel geht Funktion vor Platz.
- **EN-2** Feste Vorgaben (IN-7) ändern sich nur mit Zustimmung des Nutzers.
- **EN-3** Wärme: Verlustleistung je Bauteil und gesamt, Temperaturanstieg im Gehäuse, daraus
  die maximale Umgebungstemperatur. Knappe Reserven: iterieren (Lüftung, weniger Verluste,
  andere Bauteile).
- **EN-4** Gehäuse: druckbar ohne Stützen, keine Wand dünner als zwei Perimeter in irgendeiner
  Schicht, Schrauben in Einschmelzgewinde. Platinen werden vom Gehäuse geklemmt.
  Steckkräfte gehen ins Gehäuse, nie in Lötstellen.

## 9 Zusammenbaucheck des Gehäuses

- **AC-1** Alles virtuell zusammensetzen: Gehäuseteile, Platinen, Module, Schrauben, Einsätze,
  Litzen.
- **AC-2** Schnittvolumen zwischen zwei Körpern ist 0. Nur ein Schraubengewinde in seinem
  Einsatz oder gedruckten Loch darf überlappen.
- **AC-3** Der Zusammenbau ist möglich: Jedes Teil lässt sich auf geradem Weg ohne Kollision an
  seinen Platz bringen. Reihenfolge dokumentieren.
- **AC-4** Schließansichten: Jedes Teil hat eine eigene Kontrastfarbe außen, jede nach innen
  zeigende Fläche (ein Strahl entlang ihrer Normalen trifft ein anderes Teil) ist signalrot.
  Sechs Ansichten in Parallelprojektion. Rot darf nur an geplanten Öffnungen sichtbar sein.
- **AC-5** Außenflächen bündig, Platinen innerhalb der Toleranz gehalten, Wände ≥ dem Minimum
  aus EN-4.

## 10 Beschaffung

- **SO-1** Die üblichen Elektronik-Shops des Lieferlands prüfen (IN-6), bevorzugte zuerst
  (IN-5). Je Lieferant: Verfügbarkeit für die Seriengröße, Lagerbestand, Liefertermin,
  Stückpreis netto, Versand, Mindestbestellwert, versandkostenfrei ab.
- **SO-2** Deeplinks auf die Produktseite. Bestellnummern von der Seite übernehmen, nie
  zusammensetzen.
- **SO-3** Teile mit wenigen Quellen (Module): weiter suchen (Herstellershop,
  Preisvergleichsportale, Marktplätze) und Alternativen nennen.
- **SO-4** Die Mechanik mitdenken: Schrauben, Einsätze, Filament, Litze, die Platine selbst.
- **SO-5** Keine API? Einmal fragen, ob ein Browser im Namen des Nutzers gesteuert werden darf
  (IN-9): keine Anmeldung, keine Käufe, gemäßigtes Tempo. Rohdaten mit Datum aufbewahren.
- **SO-6** Mit der Seriengröße samt Verpackungseinheiten und Staffelpreisen rechnen. Kosten je
  Gerät und je Serie dem Budget gegenüberstellen.

## 11 Arbeitsergebnisse

- KiCad-Schaltplan und -Platine, dazu das Generator-Skript, falls eines verwendet wird
- Fertigungsdaten, wie der Platinenhersteller sie will (Gerber-/Bohr-Zip; Stückliste und
  Positionen für die Bestückung)
- Druckdateien des Gehäuses (STL oder 3MF) und ihre Quelle (SCAD, STEP, …)
- das Review-PDF
- Berechnungstabelle und Lieferantendaten mit Abrufdatum

## 12 Review-PDF

Je ein Abschnitt, A4. Hochformat, außer Querformat liest sich deutlich besser. Alle Bilder
frisch aus den aktuellen Quellen erzeugt (PR-4).

1. **Überblick.** Titel, Verwendungszweck (1–3 Sätze), Seriengröße, Kosten je Gerät und je
   Serie gegenüber dem Budget. Eine perspektivische Explosionsdarstellung von schräg oben im
   realistischen Stil eines Produktfotos: alle Gehäuseteile, Platinen, Module, Schrauben,
   Einsätze, Litzen, Netzteil, so angeordnet, wie es zusammengebaut und benutzt wird. Jedes
   Teil ist ein Link: zu seiner Gehäuseseite, zum Lagenaufbau oder zu seiner Zeile in der
   Teileliste.
2. **Schaltplan** aus KiCad: kein Text über Linien oder Symbolen, nach Funktion gruppiert,
   ausgerichtet und gleichmäßig verteilt. Danach die Berechnungstabelle (CI-1).
3. **Platine.** Perspektivisches Rendering von schräg oben, bestückt, so nah wie möglich am
   echten Ergebnis.
4. **Lagenaufbau (Sandwich).** Perspektivische Explosionsdarstellung, Lagen auseinandergezogen,
   realistische Optik. Von oben: Bauteile oben, Bestückungsdruck oben, Lötstopplack oben, Kupfer
   oben, Kern (dicker dargestellt, Bohrungen gut erkennbar), Kupfer unten, Lötstopplack unten,
   Bestückungsdruck unten, Bauteile unten. Mehr Lagen bei Mehrlagenplatinen; leere Lagen
   entfallen. Jede Lage erscheint so, wie sie im Produkt gestapelt ist, die Unterseite also
   von oben gesehen (gespiegelte Schrift). Jede Lage hat einen schwarzen Punkt mit waagrechter
   Linie zu ihrer Beschriftung: Name, Material, Eigenschaften, Dicke. Lage und Beschriftung
   verlinken auf das Lagendetail.
5. **Lagen im Detail.** Je Lage eine Drittelseite: ausführlichere Beschriftung, dann die Lage in
   derselben Ausrichtung wie im Sandwich. Der Bestückungsdruck unten zusätzlich als kleinere,
   lesbare Ansicht. Farben zeigen nur „vorhanden“: Lack grün, Kupfer kupferfarben, Kern ocker,
   Bestückungsdruck dunkelgrau, alles andere weiß; ein hellgrauer Platinenumriss zur
   Orientierung. Nichts aus anderen Lagen.
6. **Teileliste.** Je Lieferant eine Tabelle, der attraktivste zuerst. Überschrift: Lieferant,
   lieferbare Teile (x von n), spätester Liefertermin, Versandkosten für diese Bestellung
   (Mindestbestellwert, versandkostenfrei ab). Spalten: Ref, Teil (Deeplink), wichtige Daten und
   Funktion, Bestellnummer, Bedarf der Serie / Lagerbestand, Liefertermin für diese Menge,
   Stückpreis netto. Unter jeder Tabelle in Rot die dort nicht lieferbaren Teile.
   Spezialteile als eigene Punkte mit ihren zusätzlichen Quellen. Mechanik einschließen (SO-4).
7. **Gehäuse, technisch.** Ein Blatt mit allen gedruckten Teilen: je drei Ansichten in
   Parallelprojektion plus eine isometrische, Hauptmaße, Projektionsmethode 1 (ISO). Schrauben
   und Einsätze im Detail mit Belastungsrechnung und Material. Materialempfehlung und -kosten.
   Wärmerechnung mit maximaler Umgebungstemperatur (EN-3). Funkprüfung (EN-1).
8. **Zusammenbaucheck.** Die sechs Ansichten aus AC-4, die Schnittmengentabelle (AC-2), die
   Montagereihenfolge (AC-3).
9. **Vorgehensanweisungen.**
   - was sich als unmöglich herausgestellt hat und warum
   - offene Punkte: keine. Jetzt erledigen und das PDF neu erzeugen. Nur Punkte, die die
     physische Welt brauchen (eine Messung am echten Teil, ein Probedruck), dürfen bleiben, je
     mit dem, was zum Abschluss nötig ist.
   - wo die Teile bestellen: Lieferanten, Summen
   - wo die Platine bestellen: Hersteller, Lagen, Dicke, Material, Oberfläche, Lack- und
     Druckfarbe, minimale Bahn und Bohrung, Menge, hochzuladende Dateien

## 13 Kommunikation

- **CO-1** Kurze Antworten. Unsicheres als unsicher kennzeichnen. Offene Punkte ausdrücklich
  nennen („RSSI noch nicht gemessen“).
- **CO-2** Abweichungen von diesen Vorgaben mit Regel-ID und Begründung melden.
- **CO-3** Fließtext in der Sprache des Nutzers; Code, Logs und Dateinamen auf Englisch. Einheiten
  und Dezimaltrennzeichen nach Gebietsschema.

## 14 Definition of Done

- [ ] Intake vollständig, Abweichungen festgehalten
- [ ] ERC, DRC, Parität, offene Verbindungen: 0, Warnungen eingeschlossen
- [ ] Berechnungstabelle vollständig, jedes Bauteil innerhalb CI-2
- [ ] alle Teile bestellbar, Kosten im Budget
- [ ] Zusammenbaucheck des Gehäuses bestanden (AC-1 … AC-5)
- [ ] jedes abgeleitete Bild und das PDF aus den aktuellen Quellen neu erzeugt und angesehen
- [ ] Review-PDF vollständig nach §12, keine offenen Punkte außer physischen
- [ ] Arbeitsergebnisse (§11) vorhanden, alles committet und gepusht
- [ ] Abweichungen von diesen Vorgaben mit Regel-ID aufgelistet
