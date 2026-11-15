"""Wikipedia-Kurzfassungen zu erkannten Personen.

Die Zuordnung ist der heikle Teil: Die Wikipedia-Suche liefert für „Roland
Fürst“ zuerst die Begriffsklärungsseite, für „Thomas Steiner“ mehrere Personen.
Deshalb werden mehrere Kandidaten bewertet (Titel, Kurzbeschreibung, Bezug zu
Burgenland/Partei/Funktion) und Begriffsklärungsseiten ausgeschlossen.

Alle Antworten werden in ``data/wiki.json`` zwischengespeichert – ein zweiter
Lauf kostet keine Anfragen.
"""

from __future__ import annotations

import json
import re
import ssl
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

from . import config
from .extract import _osa_distance
from .resolve import Person

API = "https://de.wikipedia.org/w/api.php"
SUMMARY = "https://de.wikipedia.org/api/rest_v1/page/summary/"
USER_AGENT = (
    "burgenland-connections/0.2 (Forschungsprototyp, lokale Auswertung; "
    "https://burgenland.orf.at/ Datenquelle)"
)
MIN_MATCH_SCORE = 4
REQUEST_INTERVAL = 0.28

#: Wörter, die auf eine Personen-Biografie hindeuten.
PERSON_HINTS = (
    "politiker", "politikerin", "bürgermeister", "landeshauptmann", "minister",
    "abgeordnete", "abgeordneter", "fußballspieler", "fußballspielerin",
    "sportler", "trainer", "schriftsteller", "autor", "künstler", "musiker",
    "sänger", "schauspieler", "regisseur", "journalist", "unternehmer",
    "manager", "architekt", "pfarrer", "bischof", "general", "offizier",
    "historiker", "wissenschaftler", "professor", "richter", "anwalt",
    "geboren", "ist ein", "ist eine",
)
DISAMBIGUATION_HINTS = ("ist der name folgender", "begriffsklärung", "kann sich beziehen auf")

#: Deutsche Parteien – ein Treffer mit diesen Kürzeln ist fast immer ein
#: Namensvetter, kein burgenländischer Mandatar.
FOREIGN_PARTIES = ("cdu", "csu", "spd", "sed", "afd", "fdp", "die linke", "bündnis 90")

#: Kontextwörter, die einen Bezug zu Österreich/Burgenland belegen.
AUSTRIAN_HINTS = ("österreich", "burgenland", "wien", "niederösterreich", "steiermark")

#: Kurzformen liegen zentral im Lexikon (auch für die Personen-Zusammenführung).
from .lexicon import NICKNAMES


def name_variants(name: str) -> list[str]:
    """Bürgerlicher Name plus die aufgelösten Kurzformen („Grete“ → „Margarethe“)."""
    parts = name.split()
    if len(parts) < 2:
        return [name]
    first, rest = parts[0], parts[1:]
    variants = [name]
    for target in NICKNAMES.get(first.lower(), ()):
        candidate = " ".join([target.capitalize(), *rest])
        if candidate not in variants:
            variants.append(candidate)
    return variants


def _ssl_context():
    return ssl.create_default_context()


class WikiClient:
    def __init__(self, cache_path: Path | None = None, refresh: bool = False,
                 interval: float = REQUEST_INTERVAL, log=print) -> None:
        self.cache_path = cache_path or (config.DATA_DIR / "wiki.json")
        self.refresh = refresh
        self.interval = interval
        self.log = log
        self._last = 0.0
        self.context = _ssl_context()
        self.cache: dict[str, dict] = {}
        if self.cache_path.exists():
            try:
                self.cache = json.loads(self.cache_path.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, OSError):
                self.cache = {}

    # -- HTTP ---------------------------------------------------------
    def _get(self, url: str, timeout: int = 30) -> dict:
        wait = self.interval - (time.monotonic() - self._last)
        if wait > 0:
            time.sleep(wait)
        self._last = time.monotonic()
        request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
        with urllib.request.urlopen(request, timeout=timeout, context=self.context) as response:
            return json.loads(response.read().decode("utf-8"))

    def _search(self, query: str, limit: int = 6) -> list[dict]:
        params = {
            "action": "query", "list": "search", "srsearch": query,
            "srlimit": str(limit), "srnamespace": "0", "format": "json", "utf8": "1",
            "srprop": "snippet",
        }
        data = self._get(f"{API}?{urllib.parse.urlencode(params)}")
        return data.get("query", {}).get("search", [])

    def _summary(self, title: str) -> dict | None:
        url = SUMMARY + urllib.parse.quote(title.replace(" ", "_"))
        try:
            return self._get(url)
        except urllib.error.HTTPError:
            return None

    # -- Zuordnung ----------------------------------------------------
    def lookup(self, name: str, party: str | None = None,
               role: str | None = None, context_words: tuple[str, ...] = ("burgenland",)) -> dict | None:
        variants = name_variants(name)
        hits: list[dict] = []
        seen_titles: set[str] = set()
        for query_name in variants:
            for hit in (self._search(f'"{query_name}"') or self._search(query_name)):
                title = hit.get("title", "")
                if title in seen_titles:
                    continue
                seen_titles.add(title)
                hits.append(hit)
        if not hits:
            return None

        wanted_list = [re.sub(r"\s+", " ", variant.lower().replace("-", " ")).strip()
                       for variant in variants]
        wanted = wanted_list[0]
        surname = wanted.split()[-1]
        scored: list[tuple[int, str]] = []
        for hit in hits:
            title = hit.get("title", "")
            snippet = re.sub(r"<[^>]+>", "", hit.get("snippet", "")).lower()
            if any(hint in snippet for hint in DISAMBIGUATION_HINTS):
                continue                     # Begriffsklärungsseite
            base = re.sub(r"\s+", " ", title.split(" (")[0].lower().replace("-", " ")).strip()
            # Der Artikel muss die Person selbst sein – nicht ihre Partei, ihr
            # Verein oder ihr Ort ("Regina Petrik" != "Die Grünen Burgenland").
            similar = any(base == candidate
                          or (len(base) > 6 and _osa_distance(base, candidate) <= 2)
                          for candidate in wanted_list)
            if not similar:
                continue
            score = 2
            if "(" in title:
                score += 1                   # Qualifikator, z. B. "(Politiker, 1969)"
            else:
                score += 2                   # unqualifizierter Titel = Hauptartikel
            if surname in base:
                score += 1
            if any(hint in snippet for hint in PERSON_HINTS):
                score += 2
            if any(word in snippet for word in context_words):
                score += 3
            if party and party.lower() in snippet:
                score += 2
            if role and role.lower() in snippet:
                score += 1
            if score >= MIN_MATCH_SCORE:
                scored.append((score, title))

        if not scored:
            return None
        scored.sort(key=lambda item: (-item[0], len(item[1])))
        for score, title in scored[:2]:
            payload = self._summary(title)
            if not payload:
                continue
            description = (payload.get("description") or "").lower()
            extract = payload.get("extract") or ""
            text = f"{description} {extract}".lower()
            if any(hint in description for hint in DISAMBIGUATION_HINTS):
                continue
            if any(party_code in text for party_code in FOREIGN_PARTIES):
                continue                     # deutscher Namensvetter
            austrian = any(hint in text for hint in AUSTRIAN_HINTS)
            if austrian:
                score += 2
            if any(word in text for word in context_words):
                score += 2
            # Ohne Österreich-Bezug und ohne Parteisignal bleibt es zu unsicher.
            if not austrian and not party and score < MIN_MATCH_SCORE + 4:
                continue
            return {
                "title": payload.get("title") or title,
                "url": (payload.get("content_urls", {}).get("desktop", {}) or {}).get("page")
                        or f"https://de.wikipedia.org/wiki/{urllib.parse.quote(title.replace(' ', '_'))}",
                "description": payload.get("description") or "",
                "extract": extract,
                "thumbnail": (payload.get("thumbnail") or {}).get("source"),
                "match_score": score,
                "query": name,
            }
        return None

    # -- Massenlauf ---------------------------------------------------
    def enrich(self, persons: list[Person], log=print) -> dict[str, dict]:
        todo = [p for p in persons if self.refresh or p.name not in self.cache]
        log(f"  Wikipedia: {len(persons)} Personen, {len(todo)} offen, "
            f"{len(self.cache)} im Cache")
        for index, person in enumerate(todo, 1):
            try:
                self.cache[person.name] = self.lookup(
                    person.name, party=person.party, role=person.role_label,
                ) or {}
            except Exception as exc:  # noqa: BLE001 - Netzfehler dürfen den Lauf nicht stoppen
                log(f"    ! {person.name}: {exc}")
                continue
            if index % 100 == 0:
                self.save()
                found = sum(1 for v in self.cache.values() if v)
                log(f"    ... {index}/{len(todo)} geprüft, {found} mit Artikel")
        self.save()
        return self.cache

    def save(self) -> None:
        try:
            self.cache_path.parent.mkdir(parents=True, exist_ok=True)
            self.cache_path.write_text(json.dumps(self.cache, ensure_ascii=False, indent=0),
                                       encoding="utf-8")
        except OSError:
            pass

def main(argv: list[str] | None = None) -> int:
    """Eigenständiger Lauf: ``python -m bglbot.wiki [--refresh]``.

    Liest die Personen aus ``data/out/graph.json`` und füllt ``data/wiki.json``,
    ohne den Crawler erneut zu starten.
    """
    import argparse

    parser = argparse.ArgumentParser(prog="python -m bglbot.wiki")
    parser.add_argument("--refresh", action="store_true", help="Cache ignorieren")
    parser.add_argument("--graph", type=Path, default=config.OUT_DIR / "graph.json")
    args = parser.parse_args(argv)

    graph = json.loads(args.graph.read_text(encoding="utf-8"))

    class _Stub:
        __slots__ = ("name", "party", "role_label")

        def __init__(self, node: dict) -> None:
            self.name = node["name"]
            self.party = node.get("party")
            self.role_label = node.get("role")

    persons = [_Stub(node) for node in graph["nodes"]]
    client = WikiClient(refresh=args.refresh)
    client.enrich(persons)
    found = sum(1 for entry in client.cache.values() if entry)
    print(f"Wikipedia: {found} von {len(persons)} Personen mit Artikel")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
