"""Zentrale Konfiguration: Basis-URLs, Pfade, Crawl-Politik."""

from __future__ import annotations

import os
from pathlib import Path

BASE_URL = "https://burgenland.orf.at"
RSS_URL = "https://rss.orf.at/burgenland.xml"

#: Unterverzeichnisse, in denen Story-IDs der Burgenland-Redaktion liegen.
SECTIONS = ("", "magazin/", "studio/")

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0 Safari/537.36 "
    "BurgenlandConnectionsBot/0.1 (+lokales Forschungsprojekt)"
)

#: Mindestabstand zwischen zwei HTTP-Anfragen an den ORF (Sekunden).
MIN_REQUEST_INTERVAL = 0.8
REQUEST_TIMEOUT = 30
MAX_RETRIES = 3

ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = Path(os.environ.get("BGLBOT_DATA", ROOT / "data"))
CACHE_DIR = DATA_DIR / "cache"
OUT_DIR = DATA_DIR / "out"
#: Vom Nutzer ergänzte Artikel-URLs (eine pro Zeile), die nicht im Archiv-Sample liegen.
EXTRA_URLS = DATA_DIR / "extra_urls.txt"


def ensure_dirs() -> None:
    for d in (DATA_DIR, CACHE_DIR, OUT_DIR):
        d.mkdir(parents=True, exist_ok=True)
