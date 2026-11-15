"""Archiv-Discovery über die Wayback Machine (CDX-API).

Die Startseite von burgenland.ORF.at zeigt nur rund zwei Wochen zurück. Die
Wayback Machine hat über Jahre hinweg Story-URLs mitgeschnitten – diese Liste
lässt sich über die CDX-Schnittstelle abfragen und als Fundstelle für
*aktuelle* Artikel nutzen (der ORF hält seine Story-IDs online).

Die archivierten HTML-Snapshots selbst werden bewusst nicht ausgewertet: Alte
Seiten haben ein anderes Markup. Wir nutzen das Archiv also als Wegweiser,
geladen wird die lebende Seite.
"""

from __future__ import annotations

import json
import re
import urllib.parse


from .http import Fetcher, FetchError
from .config import DATA_DIR

CDX_ENDPOINT = "https://web.archive.org/cdx/search/cdx"
#: Strenge Prüfung: Die URL muss direkt nach der Story-ID enden. Die CDX-Daten
#: enthalten auch Spam- und Redirect-URLs, bei denen Ziffern zufällig wie eine
#: Story-ID aussehen (".../stories/103389www.asfinag.at").
STRICT_URL_RE = re.compile(
    r"^https?://burgenland\.orf\.at(?::80)?/(?:(?:magazin|studio)/)?stories/(\d+)/?(?:\?.*)?$"
)

#: Reihenfolge der Jahre für die Stichprobe (aktuellere zuerst).
DEFAULT_YEARS = (2026, 2025, 2024, 2023, 2022, 2021, 2020, 2019)


def _query(fetcher: Fetcher, pattern: str, year: int, limit: int) -> list[tuple[str, str]]:
    params = {
        "url": pattern,
        "from": f"{year}0101",
        "to": f"{year}1231",
        "output": "json",
        "fl": "original,timestamp",
        "filter": "statuscode:200",
        "collapse": "urlkey",
        "limit": str(limit),
    }
    url = f"{CDX_ENDPOINT}?{urllib.parse.urlencode(params)}"
    try:
        raw = fetcher.get(url, timeout=120)
    except FetchError:
        return []
    try:
        rows = json.loads(raw)
    except json.JSONDecodeError:
        return []
    if not rows:
        return []
    header = rows[0]
    try:
        i_original = header.index("original")
        i_timestamp = header.index("timestamp")
    except ValueError:
        return []
    return [(row[i_original], row[i_timestamp]) for row in rows[1:]]


def _cache_file(max_urls: int, years: tuple[int, ...], seed: int = 0):
    tag = "-".join(str(y) for y in years)
    suffix = f"-s{seed}" if seed else ""
    return DATA_DIR / f"wayback-{tag}-{max_urls}{suffix}.json"


def _collect_year(fetcher: Fetcher, year: int, budget: int, seed: int = 0,
                  log=print) -> list[str]:
    """Sammelt bis zu ``budget`` Story-URLs, die im Jahr ``year`` aufgenommen wurden.

    Die CDX-Antwort ist nach URL sortiert, nicht nach Datum. Würde man einfach
    die ersten N Zeilen nehmen, bekäme man nur niedrige Story-IDs. Deshalb wird
    die (deduplizierte) Liste gleichmäßig durchgesampelt.
    """
    found: dict[str, str] = {}
    for pattern in ("burgenland.orf.at/stories/*", "burgenland.orf.at/magazin/stories/*"):
        for original, _timestamp in _query(fetcher, pattern, year, max(2000, budget * 12)):
            match = STRICT_URL_RE.match(original)
            if not match:
                continue
            story_id = match.group(1)
            if story_id in found:
                continue
            section = ""
            if "/magazin/stories/" in original:
                section = "magazin/"
            elif "/studio/stories/" in original:
                section = "studio/"
            found[story_id] = f"https://burgenland.orf.at/{section}stories/{story_id}/"
    urls = sorted(found.values())
    if len(urls) <= budget:
        return urls
    # Gleichmäßig durchsampeln, aber mit seed-abhängigem Startpunkt: Ein neuer
    # Seed liefert eine andere Stichprobe desselben Jahres, sodass wiederholte
    # inkrementelle Läufe den Korpus tatsächlich erweitern.
    step = len(urls) / budget
    offset = (seed * 7919) % len(urls)
    return [urls[(int(index * step) + offset) % len(urls)] for index in range(budget)]


def discover(fetcher: Fetcher, max_urls: int = 600, per_year: int | None = None,
             years: tuple[int, ...] = DEFAULT_YEARS, seed: int = 0,
             log=print) -> list[str]:
    """Liefert bis zu ``max_urls`` archivierte Story-URLs, gleichmäßig über die Jahre.

    Wichtig: Die CDX-Filter ``from``/``to`` beziehen sich auf den
    **Aufnahme**zeitpunkt, nicht auf das Erscheinungsdatum. Ein 2026 aufgenommener
    Artikel kann von 2019 stammen. Deshalb wird das Budget auf die Jahre verteilt,
    statt (wie zuvor) nach dem ersten produktiven Jahr abzubrechen.
    """
    cache_path = _cache_file(max_urls, years, seed)
    if cache_path.exists() and not fetcher.refresh:
        try:
            data = json.loads(cache_path.read_text(encoding="utf-8"))
            if isinstance(data, list) and data:
                log(f"  Wayback: {len(data)} URLs aus lokalem Index ({cache_path.name})")
                return data
        except (json.JSONDecodeError, OSError):
            pass

    budget_per_year = max(20, max_urls // max(1, len(years)))
    collected: list[str] = []
    seen: set[str] = set()
    for year in years:
        if len(collected) >= max_urls:
            break
        urls = _collect_year(fetcher, year, budget_per_year, seed=seed, log=log)
        added = 0
        for url in urls:
            if url in seen:
                continue
            seen.add(url)
            collected.append(url)
            added += 1
        log(f"  Wayback {year}: +{added} URLs (Gesamt {len(collected)})")

    urls = collected[:max_urls]
    if urls:
        try:
            cache_path.write_text(json.dumps(urls, indent=0), encoding="utf-8")
            log(f"  Wayback: Index lokal gespeichert ({cache_path.name})")
        except OSError:
            pass
    return urls
