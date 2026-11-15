# burgenland-connections

Scraping- und Analyse-Bot für **burgenland.ORF.at**: Der Bot lädt die
Nachrichten der Burgenland-Redaktion, erkennt darin **Personen und ihre
Funktionen** (Landeshauptmann, Bürgermeisterin, Geschäftsführer …) und baut aus
den gemeinsamen Erwähnungen ein **interaktives Beziehungsnetzwerk**.

```
burgenland.ORF.at ──► Crawler ──► Parser ──► Personen-/Funktionserkennung
                                                │
                                                ├─► data/out/personen.csv
                                                ├─► data/out/beziehungen.csv
                                                ├─► data/out/graph.json + graph.graphml
                                                └─► data/out/graph.html  ← interaktive Grafik
```

## Live-Seite

Die jeweils aktuelle Grafik wird über GitHub Pages veröffentlicht:

**https://frocentus.github.io/burgenland-connections/**

Ein GitHub-Actions-Workflow (`.github/workflows/pages.yml`) prüft bei jedem
Push die Tests, crawlt anschließend und lädt `graph.html` als `index.html`
hoch. Zusätzlich läuft er **täglich um 05:00 UTC** und lässt sich manuell über
*Actions → CI und GitHub Pages → Run workflow* starten. HTTP- und
Wikipedia-Antworten werden zwischen den Läufen gecacht.

## Schnellstart

```bash
python run.py --pages 20 --open     # crawlen, auswerten, Grafik im Browser öffnen
python run.py --report              # Ergebnis des letzten Laufs zusammenfassen
```

Es werden **keine** externen Pakete benötigt – nur Python 3.10+ und `lxml`
(im Projekt-Interpreter vorhanden). Alle HTTP-Antworten landen im Cache unter
`data/cache/`, sodass ein zweiter Lauf ohne Netzzugriff reproduzierbar ist.
`--refresh` erzwingt neue Downloads.

| Option | Bedeutung |
|---|---|
| `--pages N` | Startseiten-Paginierung `/?page=N`; je Seite ~10 neue Artikel (Standard 15) |
| `--limit N` | Höchstzahl verarbeiteter Artikel (zum Testen) |
| `--no-magazin` | nur Nachrichten-Startseite, ohne `magazin/` und `studio/` |
| `--wayback N` | zusätzlich N Story-URLs aus der Wayback Machine (CDX-API) |
| `--refresh` | HTTP-Cache ignorieren |
| `--out DIR` | Zielverzeichnis (Standard `data/out`) |
| `--open` | Grafik nach dem Lauf im Browser öffnen |

## Tieferes Archiv über die Wayback Machine

Die Startseite gibt nur rund zwei Wochen her. Über die CDX-Schnittstelle des
Internet Archive lassen sich dagegen tausende Story-URLs finden:

```bash
python run.py --pages 5 --wayback 1200
```

Der Bot fragt den Index je Jahresfenster ab
(`burgenland.orf.at/stories/*`, `statuscode:200`, `collapse=urlkey`), prüft die
URLs streng gegen das Story-Muster (die Rohdaten enthalten auch Spam- und
Redirect-URLs, bei denen Ziffern wie eine Story-ID aussehen), behält die
Ressortangabe (`/magazin/stories/`, `/studio/stories/`) bei und lädt dann die
**lebende** Seite – nicht den alten Snapshot, denn ältere Snapshots nutzen ein
anderes HTML.

### Warum die Abdeckung nicht lückenhaft ist

Eine frühere Version dieses Bots berichtete von „Lücken 2022–2025“. Das war ein
Artefakt der Abfrage, kein Befund über das Archiv. Drei Ursachen:

1. **`limit` + `collapse=urlkey`**: CDX liefert die Zeilen nach *URL* sortiert,
   nicht nach Datum. Ein `limit=5000` schneidet daher die niedrigen Story-IDs
   ab – spätere Jahre wirken leer, obwohl sie es nicht sind.
2. **Abbruch nach dem ersten Jahr**: Die Schleife stoppte, sobald das Budget
   erreicht war. 2026 allein lieferte genug Treffer, sodass die übrigen Jahre
   nie abgefragt wurden.
3. **Aufnahme- ≠ Erscheinungsdatum**: `from`/`to` filtern den *Capture*-
   Zeitpunkt. 2026 aufgenommene Seiten können von 2019 stammen.

Sauber pro Jahr gemessen (Story-URLs mit HTTP 200):

| Jahr | eindeutige URLs | Captures gesamt |
|---|---|---|
| 2019 | 1.466 | 3.170 |
| 2020 | 3.010 | 6.377 |
| 2021 | 4.186 | 10.565 |
| 2022 | 6.452 | 20.892 |
| 2023 | 7.094 | 23.258 |
| 2024 | 4.869 | 12.241 |
| 2025 | 4.331 | 10.106 |
| 2026 | 3.453 | 9.592 |

Die Discovery verteilt das Budget deshalb **gleichmäßig über die Jahre**
(Standard: `--wayback 1200` → 150 URLs pro Jahr) und sampelt die nach URL
sortierte Liste gleichmäßig durch, statt die ersten N Zeilen zu nehmen.

Grenzen: Die *Live*-Verfügbarkeit ist das Nadelöhr, nicht das Archiv – gelöschte
Storys liefern 404, der Bot überspringt sie. Und die Stichprobe ist eine
Stichprobe: 20.000+ archivierte Story-IDs lassen sich nicht in einem Lauf
abrufen, ohne den ORF zu belasten.

Die Trefferliste wird als `data/wayback-<jahre>-<n>.json` zwischengespeichert –
die CDX-Antworten sind bei `limit`-Kürzung nicht stabil sortiert. Mit
Index und HTTP-Cache läuft derselbe Aufbau danach in wenigen Sekunden
(1021 Artikel: ~10 s statt ~20 min).

## Ergebnis des Referenzlaufs

```
1298 Artikel · 1292 Personen · 3789 Beziehungen · 4924 Nennungen
Zeitraum 2019-06-03 – 2026-11-14 · 990 Artikel mit Personennennungen
davon 60 Beziehungen mit erkennbarem Beziehungston · 405 mit Wikipedia-Artikel
```

Spitzenreiter: Hans Peter Doskozil (73 Artikel, 138 Beziehungen),
Anja Haider-Wallner (28), Heinrich Dorner (25), Leonhard Schneemann (25),
Christian Sagartz (22, ÖVP), Robert Hergovich (20), Astrid Eisenkopf (18),
Norbert Hofer (16, FPÖ), Daniela Winkler (15), Alexander Petschnig (13).
Stärkste Paare: Sagartz ↔ Doskozil (10 gemeinsame Artikel),
Haider-Wallner ↔ Doskozil (8), Haider-Wallner ↔ Sagartz (8).

## Was der Bot erkennt

**Personen** werden regelbasiert aus dem ORF-Stil gelesen, nicht aus einem
fremden NER-Modell. Die Evidenzquellen pro Kandidatennennung:

| Evidenz | Beispiel | Gewicht |
|---|---|---|
| Funktionsbezeichnung davor | „**Landeshauptmann** Hans Peter Doskozil“ | +4 |
| Parteikürzel in Klammern | „Hans Peter Doskozil **(SPÖ)**“ | +3 |
| Partei-Präfix am Titel | „**SPÖ**-Landesparteivorsitzender Doskozil“ | +1 |
| Rede-Verb danach | „Doskozil **sagte** …“ | +2 |
| Vorname im Kandidaten | „**Roman** Kainrath“ | +2 |
| Wiederholung im Artikel | 4× im selben Text | +1 |
| Korpus-Lexikon (gelernt) | in anderen Artikeln bereits bestätigt | +4 |

Gegen **Falschpositive** wirken mehrere Filter:

* Liste generischer Substantive inkl. deutscher Flexionsendungen
  („Krankenhauses“ → „krankenhaus“)
* ein **Gazetteer**, der Ortsnamen automatisch aus dem eigenen Korpus lernt
  („in Raiding“, „Bezirk Oberpullendorf“) – Vornamen sind dabei ausgenommen
* **Kompositum-Köpfe**: Endet der Kandidat auf „…zustand“, „…werk“,
  „…kosten“, ist es ein Ding („Norbert Hofers Gesundheitszustand“)
* **Satzzeichen-Grenzen**: Namen werden nie über Kommas, Doppelpunkte oder
  Anführungszeichen hinweg zusammengezogen – sonst würde aus der Bildzeile
  „Elisabeth Pauer-Gerbavsits, Marin Berlakovich“ ein Fantasiename
* **Genitiv-Auflösung**: „Heinrich Knotzers Werk“ wird zu „Heinrich Knotzer“
* „Geschäftsführer **der** Biowärme“ = Organisation, nicht Person

**Bildtexte und Aufzählungen** sind eine eigene Quelle: In
„Thomas Prunner, Raphaela Pint, … Marin Berlakovich“ stehen Personen ohne
Funktion, aber in einer Komma-Liste. Diese Struktur zählt als Evidenz (+2) –
so werden auch Moderatoren- und Vorstandsteams erkannt.

Schreibvarianten werden auf die **kanonische Funktion** abgebildet:
„SPÖ-Landeshauptmann“, „Landeshauptmanns“ und „Landeshauptmann“ ergeben einen
Eintrag (die Partei steht ohnehin als eigenes Attribut am Knoten), ebenso
„Landeshauptmannstellvertreterin“ und „Landeshauptmann-Stellvertreterin“.
Angezeigt wird die häufigste Schreibweise der Funktion, nicht jede Form
einzeln.

**Funktionen** stammen aus der Bezeichnung vor dem Namen oder aus Appositionen
danach („, Bürgermeister von Deutsch Jahrndorf“, „ist Bürgermeisterin in …“,
„als Präsident des GVV“) und werden auf kanonische Rollen abgebildet
(`landeshauptmann`, `bürgermeister`, `geschäftsführer` … inkl. Kategorie und
Rang). Erkannt werden u. a. Landes- und Bundespolitik, Gemeinde, Verwaltung,
Polizei/Feuerwehr, Justiz, Wirtschaft, Kirche, Bildung, Gesundheit, Sport,
Vereine und Kultur.

**Beziehungen** entstehen durch gemeinsame Nennung:

* `weight` – Anzahl der Artikel, in denen beide vorkommen (Hauptkriterium)
* `sentences` – Sätze, in denen beide gemeinsam genannt werden (Nähe)
* `windows` – benachbarte Sätze (schwächere Nähe)
* `signals` – Themen im gemeinsamen Satz: `nachfolge`, `zuspruch`,
  `konflikt`, `kooperation`, `wahl`, `vertretung`
* `sentiment` – Beziehungston: `feindselig`, `negativ`, `gemischt`,
  `positiv`, `neutral` (siehe unten)

## Beziehungston (Sentiment)

Jede Kante kann einen Ton tragen. Grundlage ist ein gewichtetes Signalwort-
Lexikon (`lexicon.SENTIMENT_CUES`):

| Kategorie | Gewicht | Beispiele |
|---|---|---|
| feindselig | 1,2 | attackiert, beschuldigt, Vorwürfe, Konfrontation |
| negativ | 1,0 | kritisiert, wehrt sich, weist zurück, Streit, Klage |
| positiv | 1,0 | lobt, gratuliert, dankt, würdigt, unterstützt |
| kooperativ | 0,8 | Einigung, Kooperation, Partnerschaft, Bündnis |

Vier Feinheiten, die den Unterschied zwischen Brauchbarkeit und Rauschen
ausmachen:

* **Wortgrenzen** – sonst wird aus „angelobt“ ein Lob und aus „Wettstreit“ ein
  Streit.
* **Flexion** – „lobt/lobte/gelobt“ wird über ein optionales Endungsmuster
  erfasst, nicht über Teilstrings.
* **Negation** – „nicht zufrieden“ oder „Zusammenarbeit ausgeschlossen“ kippt
  die Polarität (vor und nach dem Signalwort geprüft).
* **Kontext** – ein Signalwort im selben Satz zählt voll, im Absatzumfeld
  (±2 Sätze) mit 45 %. In Nachrichten steht die Wertung oft in einem Satz, der
  nur einen der beiden Namen nennt.

Zusätzlich wird eine **Tendenz** geschätzt („wer → wen“): Anker ist das
Signalwort, die nächstgelegene Person davor gilt als Akteur, danach als
Adressat; Passivkonstruktionen („wurde von X kritisiert“) werden gedreht.

**Warum nur so wenige Kanten bewertet sind:** Von rund 18.000 Sätzen nennen nur
etwa 350 zwei Personen, und davon enthält ein Bruchteil ein Wertungswort. Der
Ton ist damit eine *qualitative Zusatzinformation*, keine vollständige
Vermessung. Ein Beispiel: Roland Fürst (SPÖ-Klubobmann) hat 66 Kanten, und seine
Kritik gilt in den gewerteten Sätzen fast nie einer zweiten Person, sondern
Kollektiven („die ÖVP“, „die Bundesregierung“, „die Opposition“).

## Tonlage der Person

Weil Kritik oft keinem Gegenüber gilt, wird der Ton zusätzlich **pro Person**
erfasst – aus allen Sätzen, in denen sie vorkommt, unabhängig vom Gegenüber.
Zwei Kennzahlen: `critical` (Sätze mit Kritik) und `praising` (Sätze mit
Zustimmung), dazu die **Angriffsziele** (Parteien/Institutionen im selben
Satz). Die eigene Partei wird nicht als Ziel gezählt – dort handelt es sich
meist um Verteidigung.

Labels ab einem Mindestbeleg von 0,7: `überwiegend kritisch` (Zustimmungsanteil
≤ 25 %), `eher kritisch` (≤ 42 %), `ausgewogen`, `eher zustimmend` (≥ 58 %),
`überwiegend zustimmend` (≥ 75 %), sonst `zu wenig Belege`.

Beispiele aus dem Korpus:

| Person | Tonlage | Belege | Ziele |
|---|---|---|---|
| Roland Fürst | überwiegend kritisch | 3 kritisch / 1 zustimmend | Opposition, ÖVP |
| Hans Peter Doskozil | eher kritisch | 7 / 5 | ÖVP, FPÖ, Opposition |
| Christian Sagartz | ausgewogen | 3 / 3 | SPÖ, Bundesregierung |

62 Personen haben genug Belege für ein Label; bei den übrigen bleibt es bei
„zu wenig Belege“. In der Grafik: Filter „Tonlage der Person“, Abschnitt
*Tonlage im Korpus* im Detailpanel, Spalten `tonlage`, `kritische_belege`,
`zustimmende_belege`, `angriffsziele` in `personen.csv`. In der Grafik: Kantenfarbe, Filter „nur konfliktär“,
Belegstellen und Tendenz im Detailpanel; in `beziehungen.csv` als eigene
Spalten.

## Wikipedia-Kurzfassungen

Zu jeder erkannten Person wird – falls vorhanden – der deutsche Wikipedia-
Artikel gesucht und die Kurzfassung (REST-API `page/summary`) übernommen:
Titel, Kurzbeschreibung, Einleitungstext, Vorschaubild und Link. Angezeigt wird
das im Detailpanel der Grafik; `personen.csv` enthält zusätzlich
`wikipedia_titel` und `wikipedia_url`.

Die Zuordnung ist der heikle Teil, denn die Wikipedia-Suche liefert für
„Roland Fürst“ zuerst die Begriffsklärungsseite und für „Thomas Steiner“
mehrere Personen. Deshalb:

* **Begriffsklärungsseiten** werden anhand des Snippets („ist der Name
  folgender Personen“) verworfen.
* Der Artikelname muss der Person entsprechen – nicht ihrer Partei, ihrem
  Verein oder ihrem Ort (sonst wurde „Regina Petrik“ zu „Die Grünen
  Burgenland“).
* Mehrere Kandidaten werden bewertet: unqualifizierter Titel (Hauptartikel),
  Qualifikator wie „(Politiker, 1969)“, Personen-Hinweise im Snippet, sowie
  Bezug zu **Burgenland**, Partei und Funktion aus dem eigenen Korpus.
* **Kurzformen** werden aufgelöst: Der ORF schreibt „Grete Krojer“, Wikipedia
  führt „Margarethe Krojer“; ebenso „Didi“ → Dietmar, „Hans“ → Johann,
  „Sepp“ → Josef, „Resi“ → Therese (rund 50 Zuordnungen in
  `wiki.NICKNAMES`).
* Bei Gleichstand entscheidet der höhere Score; unter 4 Punkten bleibt es bei
  „kein Artikel“.

Alle Antworten liegen in `data/wiki.json` (Namensschlüssel → Treffer). Ein
zweiter Lauf kostet keine Anfragen; `--wiki-refresh` erzwingt neue Abfragen,
`--no-wiki` überspringt die Anreicherung.

Grenzen: Es wird nur die **deutsche** Wikipedia abgefragt, und Personen ohne
öffentliche Relevanz haben keinen Artikel – bei Kommunalpolitikern ist das die
Mehrheit (im Referenzlauf 405 von 1.292, rund 31 %). Namensvettern sind das
größte Risiko: „Roland Koch“ führt zur CDU, „Kurt Fischer“ zur SED. Deshalb
werden Artikel mit **deutschen Parteikürzeln** und ohne jeden
**Österreich-/Burgenland-Bezug** verworfen. Der Score bleibt im Datensatz
(`match_score`), ersetzt aber keine Prüfung im Einzelfall.

Schneller Rebuild ohne Crawling: `python run.py --rebuild` nutzt
`data/out/artikel.jsonl` und den Wikipedia-Cache (rund 20 s statt 15 min).

## Fehlende Artikel ergänzen

Das Archiv-Sample umfasst rund 150 URLs pro Jahr – nicht jeder Artikel ist
dabei. Einzelne Seiten lassen sich in `data/extra_urls.txt` eintragen (eine URL
pro Zeile, `#` als Kommentar); sie werden bei jedem Lauf mitgeladen und beim
`--rebuild` in `artikel.jsonl` ergänzt.

## Ausgabedateien

| Datei | Inhalt |
|---|---|
| `data/out/graph.html` | interaktive Grafik (eine Datei, offline nutzbar) |
| `data/out/netzwerk.png` | statische Vorschau des Netzwerks (2000×1300) |
| `data/out/graph.json` | Knoten, Kanten, Artikel-Metadaten, Statistik |
| `data/out/personen.csv` | Personen mit Funktion, Partei, Artikelzahl, Konfidenz |
| `data/out/beziehungen.csv` | Paare mit Gewicht und Beziehungssignalen |
| `data/out/graph.graphml` | Import in Gephi / yEd / NetworkX |
| `data/out/artikel.jsonl` | jeder Artikel mit den erkannten Personen |

## Die Grafik

`graph.html` ist eigenständig (kein CDN, keine Serververbindung nötig):

* Kraft-Layout auf Canvas, Zoom (Mausrad), Verschieben, Knoten ziehen
* Knotengröße = Artikelanzahl, Kantenstärke = gemeinsame Artikel
* Farbe = Partei, sonst Funktionskategorie
* Klick auf Person: Funktion, Parteien, Schreibweisen, Beziehungen, Artikelliste
* Klick auf Kante: gemeinsame Artikel und Belegsätze mit Signalwörtern
* Suche mit anklickbarer Trefferliste (Pfeiltasten + Enter, Escape leert),
  Treffer werden im Graphen hervorgehoben und die Personenliste gefiltert
* Filter: Parteien, Mindestzahl gemeinsamer Artikel, Mindestartikelzahl
* Export als PNG und JSON

## Aufbau des Codes

```
run.py                  CLI-Einstieg
bglbot/config.py        Basis-URLs, Pfade, Crawl-Politik (Rate-Limit, User-Agent)
bglbot/http.py          HTTP-Client mit Cache, Retries, Drosselung
bglbot/discover.py      Artikel-URLs: Startseiten-Paginierung, Ressorts, RSS
bglbot/parse.py         Story-HTML → Titel, Lead, Body, Bildtexte, Datum, Tags
bglbot/gazetteer.py     lernt Ortsnamen aus dem Korpus
bglbot/lexicon.py       Funktionen, Parteien, Vornamen, Stoppwörter, Signalwörter
bglbot/extract.py       Kandidaten, Evidenz-Scoring, Funktionslesung, Clustering
bglbot/resolve.py       artikelübergreifende Personenauflösung (Varianten, Nachnamen)
bglbot/graph.py         Graphaufbau und Exporte (JSON/CSV/GraphML)
bglbot/render.py        HTML-Erzeugung
bglbot/templates/       Frontend der Grafik
```

## Grenzen und Güte

* Die Erkennung ist **evidenzbasiert, nicht wahrheitsfähig**: Sie gibt wieder,
  wie die Redaktion Personen darstellt. Fehlt eine Funktion im Text, bleibt sie
  leer; „Präsident“ kann Vereins-, Gerichts- oder Staatspräsident sein.
* Reine Nachnamen werden **keinem eigenen Knoten** zugeordnet, sondern nur
  einer bereits belegten Person mit vollem Namen (im Artikel oder – bei
  eindeutigem Nachnamen – korpusweit). Grund: Eine Einzelwort-Nennung ist nicht
  von einer Berufsbezeichnung zu unterscheiden – „Kapellmeister“ in einer
  Aufzählung von Berufen („Komponist, Musiker, Kapellmeister und
  Musikpädagoge“) wurde sonst zur Person. Der Preis: Personen, die im ganzen
  Korpus nur mit Nachnamen auftreten, fehlen.
* Gleiche Nachnamen verschiedener Personen bleiben getrennt, solange die
  Vornamen abweichen. Schreibvarianten („Stefan“/„Stephan“, „Luisa“/„Lusia“)
  werden nur zusammengeführt, wenn ein Artikel beide Formen belegt.
* Das Startseiten-Archiv reicht nur rund zwei Wochen zurück (`?page=15` liefert
  keine neuen Artikel mehr). Für längere Zeitreihen `--wayback N` nutzen; ohne
  diesen Schalter deckt der Lauf ~100–150 Artikel ab.
* Gelöschte Artikel sind über die Wayback-Liste auffindbar, live aber 404 –
  sie zählen als Ladefehler und fehlen in der Auswertung.
* Sport-, Service- und Rezeptartikel enthalten oft keine relevanten Personen –
  sie fallen aus der Auswertung, werden aber mitgezählt.
* Die Zahlen sind Momentaufnahmen des gecrawlten Zeitraums (siehe `meta`).
* Die veröffentlichte Seite ist eine Auswertung öffentlicher Berichterstattung,
  keine Aussage über die Personen selbst. Sentiment und Tonlage sind
  regelbasierte Heuristiken, keine redaktionelle Bewertung.

## Was nicht im Repository liegt

`data/cache/`, `data/out/` und `data/wiki.json` sind bewusst ignoriert:
Erstere enthalten vollständige ORF-Seiten, letztere Wikipedia-Texte. Im
Repository steht nur der Code; die veröffentlichte Seite enthält Personen,
Funktionen und kurze Belegzitate aus der Berichterstattung.

## Fairness gegenüber der Quelle

Der Bot hält `robots.txt` ein (kein Zugriff auf `/full`), sendet einen
erkennbaren User-Agent, drosselt auf eine Anfrage pro ~0,8 s, wiederholt
Fehler mit Backoff und cached alles lokal. Für regelmäßige Läufe genügen
wenige Startseiten-Seiten; das Archiv dient der Zeitreihe. Bitte die Inhalte
nicht weiterverbreiten – die Rechte liegen beim ORF.

## Tests

```bash
python -m unittest discover -s tests -v
```

Die 13 Tests laufen ohne Netzzugriff und decken Satzzerlegung, Rollen- und
Parteierkennung, Bildzeilen-Aufzählungen, Ausschlussregeln (Genitiv,
Organisation, Ortsname) sowie die artikelübergreifende Zusammenführung ab.

## Anpassen

* Andere Region: `config.BASE_URL` ändern; `lexicon.GEO_WORDS` und
  `lexicon.ROLE_SURFACES` ergänzen.
* Strengere Ausbeute: in `extract.py` `MIN_ACCEPT_SCORE` /
  `MIN_MULTIWORD_SCORE` erhöhen.
* Neue Beziehungsdimension: `lexicon.RELATION_CUES` erweitern – die Signale
  erscheinen automatisch in Graph, CSV und Detailpanel.
