"""Anreicherung mit strukturierten Daten aus Wikidata.

Die Wikipedia-Kurzfassung ist Prosa; Partei, Amt und Amtszeiten stehen
strukturiert in Wikidata. Für Personen mit Wikipedia-Artikel werden daher
Q-ID, Partei (P102), Ämter (P39 inkl. Start/Ende) und Geburtsdatum (P569)
geholt – gebündelt, damit nur wenige Anfragen nötig sind.
"""

from __future__ import annotations

import json
import ssl
import time
import urllib.parse
import urllib.request
from pathlib import Path

from . import config

API = "https://www.wikidata.org/w/api.php"
SPARQL = "https://query.wikidata.org/sparql"
USER_AGENT = "burgenland-connections/0.2 (Forschungsprototyp; lokale Auswertung)"

#: Wikidata-Parteien auf die im Projekt verwendeten Kürzel abbilden.
PARTY_MAP = {
    "sozialdemokratische partei österreichs": "SPÖ",
    "österreichische volkspartei": "ÖVP",
    "freiheitliche partei österreichs": "FPÖ",
    "die grünen – die grüne alternative": "Grüne",
    "die grünen": "Grüne",
    "neos – das neue österreich und liberales forum": "NEOS",
    "neos": "NEOS",
    "kommunistische partei österreichs": "KPÖ",
}

BATCH = 45


class WikidataClient:
    def __init__(self, cache_path: Path | None = None, refresh: bool = False, log=print):
        self.cache_path = cache_path or (config.DATA_DIR / "wikidata.json")
        self.refresh = refresh
        self.log = log
        self.context = ssl.create_default_context()
        self.cache: dict[str, dict] = {}
        if self.cache_path.exists():
            try:
                self.cache = json.loads(self.cache_path.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, OSError):
                self.cache = {}

    # -- HTTP ---------------------------------------------------------
    def _json(self, url: str, timeout: int = 60) -> dict:
        request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
        with urllib.request.urlopen(request, timeout=timeout, context=self.context) as response:
            return json.loads(response.read().decode("utf-8"))

    def _qids_for_titles(self, titles: list[str]) -> dict[str, str]:
        """dewiki-Titel -> Wikidata-QID (gebündelt, 45 pro Anfrage)."""
        mapping: dict[str, str] = {}
        for start in range(0, len(titles), BATCH):
            chunk = titles[start:start + BATCH]
            params = {
                "action": "wbgetentities", "sites": "dewiki",
                "titles": "|".join(chunk), "props": "sitelinks", "format": "json",
            }
            try:
                data = self._json(f"{API}?{urllib.parse.urlencode(params)}")
            except Exception as exc:  # noqa: BLE001 - Netzfehler überspringen
                self.log(f"    ! Wikidata-Titel: {exc}")
                continue
            for qid, entity in (data.get("entities") or {}).items():
                if not isinstance(entity, dict) or qid.startswith("-"):
                    continue
                title = ((entity.get("sitelinks") or {}).get("dewiki") or {}).get("title")
                if title:
                    mapping[title] = qid
            time.sleep(0.3)
        return mapping

    def _details(self, qids: list[str]) -> dict[str, dict]:
        """Partei, Ämter und Geburtsdatum zu QIDs (eine SPARQL-Abfrage je Block)."""
        result: dict[str, dict] = {}
        for start in range(0, len(qids), 120):
            chunk = qids[start:start + 120]
            values = " ".join(f"wd:{qid}" for qid in chunk)
            query = f"""
SELECT ?person ?partyLabel ?officeLabel ?start ?end ?birth WHERE {{
  VALUES ?person {{ {values} }}
  OPTIONAL {{ ?person wdt:P102 ?party . }}
  OPTIONAL {{ ?person p:P39 ?statement . ?statement ps:P39 ?office .
             OPTIONAL {{ ?statement pq:P580 ?start }}
             OPTIONAL {{ ?statement pq:P582 ?end }} }}
  OPTIONAL {{ ?person wdt:P569 ?birth . }}
  SERVICE wikibase:label {{ bd:serviceParam wikibase:language "de,en". }}
}}
"""
            url = f"{SPARQL}?{urllib.parse.urlencode({'query': query, 'format': 'json'})}"
            try:
                data = self._json(url, timeout=90)
            except Exception as exc:  # noqa: BLE001
                self.log(f"    ! Wikidata-SPARQL: {exc}")
                continue
            for row in data.get("results", {}).get("bindings", []):
                qid = row["person"]["value"].rsplit("/", 1)[-1]
                entry = result.setdefault(qid, {"party": None, "birth": None, "offices": []})
                party = row.get("partyLabel", {}).get("value")
                if party:
                    entry["party"] = entry["party"] or party
                birth = row.get("birth", {}).get("value")
                if birth:
                    entry["birth"] = birth[:10]
                office = row.get("officeLabel", {}).get("value")
                if office and not office.startswith("Q"):
                    period = {
                        "label": office,
                        "start": (row.get("start", {}).get("value") or "")[:4],
                        "end": (row.get("end", {}).get("value") or "")[:4],
                    }
                    if period not in entry["offices"]:
                        entry["offices"].append(period)
            time.sleep(0.4)
        return result

    # -- Öffentliche Schnittstelle ------------------------------------
    def enrich(self, wiki: dict[str, dict], log=print) -> dict[str, dict]:
        """Reichert alle Personen an, für die eine Wikipedia-Seite bekannt ist."""
        titles = {entry["title"]: name for name, entry in wiki.items() if entry and entry.get("title")}
        if not titles:
            return self.cache
        pending = [name for name in titles.values()
                   if self.refresh or name not in self.cache]
        log(f"  Wikidata: {len(titles)} Wikipedia-Titel, {len(pending)} offen")
        if not pending:
            return self.cache

        title_to_qid = self._qids_for_titles(list(titles))
        name_to_qid = {titles[title]: qid for title, qid in title_to_qid.items()}
        details = self._details(list(name_to_qid.values()))
        for name, qid in name_to_qid.items():
            if qid in details:
                self.cache[name] = {"qid": qid, **details[qid]}
        self.save()
        found = sum(1 for name in pending if self.cache.get(name))
        log(f"  Wikidata: {found} Personen mit strukturierten Daten")
        return self.cache

    def save(self) -> None:
        try:
            self.cache_path.parent.mkdir(parents=True, exist_ok=True)
            self.cache_path.write_text(json.dumps(self.cache, ensure_ascii=False, indent=0),
                                       encoding="utf-8")
        except OSError:
            pass


def party_code(label: str | None) -> str | None:
    if not label:
        return None
    return PARTY_MAP.get(label.strip().lower())


if __name__ == "__main__":
    graph = json.loads((config.OUT_DIR / "graph.json").read_text(encoding="utf-8"))
    wiki = {n["name"]: n["wikipedia"] for n in graph["nodes"] if n.get("wikipedia")}
    client = WikidataClient()
    client.enrich(wiki)
    print(f"{sum(1 for v in client.cache.values() if v)} Personen mit Wikidata-Daten")
