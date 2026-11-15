"""Auffinden von Artikel-URLs auf burgenland.ORF.at."""

from __future__ import annotations

import re
from typing import Iterable, Iterator
from urllib.parse import urljoin

from lxml import etree

from . import config
from .http import Fetcher, FetchError

#: Erlaubte Story-URLs der Burgenland-Redaktion (inkl. Unterressorts).
STORY_URL_RE = re.compile(
    r"https?://burgenland\.orf\.at/(?:(magazin|studio)/)?stories/(\d+)/?"
)

LISTING_PATHS = ("", "magazin/", "studio/")


def normalize(url: str) -> str | None:
    """Vereinheitlicht eine Story-URL; gibt None für unerwünschte Ziele."""
    m = STORY_URL_RE.search(url)
    if not m:
        return None
    section, sid = m.group(1) or "", m.group(2)
    if "/full" in url:
        return None
    return f"{config.BASE_URL}/{section + '/' if section else ''}stories/{sid}/"


def _story_links(page: str) -> list[str]:
    found: list[str] = []
    for m in STORY_URL_RE.finditer(page):
        section, sid = m.group(1) or "", m.group(2)
        found.append(f"{config.BASE_URL}/{section + '/' if section else ''}stories/{sid}/")
    # relative Links der Form href="/stories/1234567/"
    for m in re.finditer(r'href="(/(?:magazin/|studio/)?stories/\d+/?)"', page):
        found.append(urljoin(config.BASE_URL + "/", m.group(1)))
    for m in re.finditer(r'href="(//burgenland\.orf\.at/(?:magazin/|studio/)?stories/\d+/?)"', page):
        found.append("https:" + m.group(1))
    return found


def listing_pages(fetcher: Fetcher, pages: int, sections: Iterable[str] = LISTING_PATHS,
                  log=print) -> Iterator[str]:
    """Läuft die Startseiten-Paginierung durch (``/?page=N``)."""
    for section in sections:
        for page_no in range(1, pages + 1):
            if section == "":
                url = config.BASE_URL + "/" if page_no == 1 else f"{config.BASE_URL}/?page={page_no}"
            else:
                url = f"{config.BASE_URL}/{section}"
                if page_no > 1:
                    url += f"?page={page_no}"
            try:
                html = fetcher.get(url)
            except FetchError as exc:
                log(f"  ! Listing {url} fehlgeschlagen: {exc}")
                continue
            links = _story_links(html)
            yield from links
            if not links and page_no > 1:
                break


def rss_items(fetcher: Fetcher, log=print) -> Iterator[tuple[str, str, str]]:
    """Liefert (url, titel, datum) aus dem Burgenland-RSS-Feed."""
    try:
        raw = fetcher.get(config.RSS_URL)
    except FetchError as exc:
        log(f"  ! RSS nicht erreichbar: {exc}")
        return
    try:
        root = etree.fromstring(raw.encode("utf-8"))
    except etree.XMLSyntaxError:
        log("  ! RSS nicht parsebar")
        return
    for item in root.findall(".//item"):
        link = (item.findtext("link") or "").strip()
        title = (item.findtext("title") or "").strip()
        pub = (item.findtext("pubDate") or "").strip()
        norm = normalize(link)
        if norm:
            yield norm, title, pub


def discover(fetcher: Fetcher, pages: int = 12, include_sections: bool = True,
             log=print) -> list[str]:
    """Sammelt Story-URLs aus Startseiten, Ressortseiten und RSS-Feed."""
    sections = LISTING_PATHS if include_sections else ("",)
    seen: dict[str, None] = {}

    for url in listing_pages(fetcher, pages, sections, log=log):
        norm = normalize(url)
        if norm:
            seen.setdefault(norm, None)
    log(f"  Startseiten: {len(seen)} Story-URLs")

    rss_count = 0
    for url, _title, _pub in rss_items(fetcher, log=log):
        if url not in seen:
            seen[url] = None
            rss_count += 1
    log(f"  RSS: +{rss_count} neue URLs")

    return list(seen)
