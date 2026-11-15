"""Zerlegung einer ORF-Story-Seite in strukturierte Felder."""

from __future__ import annotations

import datetime as dt
import re
from dataclasses import dataclass, field, asdict

from lxml import html as LH

DATE_RE = re.compile(r"(\d{1,2})\.(\d{1,2})\.(\d{4})\s+(\d{1,2})[.:](\d{2})")
STORY_ID_RE = re.compile(r"/stories/(\d+)")


def story_id_from_url(url: str) -> str | None:
    m = STORY_ID_RE.search(url)
    return m.group(1) if m else None


def clean(text: str | None) -> str:
    if not text:
        return ""
    text = text.replace("\u00ad", "").replace("\u200b", "")
    text = re.sub(r"[\t\r\f\v]+", " ", text)
    text = re.sub(r" {2,}", " ", text)
    return text.strip()


@dataclass
class Article:
    id: str
    url: str
    title: str
    section: str = "news"
    category: str = ""
    lead: str = ""
    paragraphs: list[str] = field(default_factory=list)
    captions: list[str] = field(default_factory=list)
    byline: str = ""
    published: str = ""          # ISO-Zeitstempel, falls vorhanden
    published_raw: str = ""
    tags: list[str] = field(default_factory=list)
    related_ids: list[str] = field(default_factory=list)

    @property
    def text(self) -> str:
        return "\n".join([self.lead, *self.paragraphs])

    @property
    def date(self) -> str:
        return self.published[:10] if self.published else ""

    @property
    def kind(self) -> str:
        """Vereinfachte Ressort-Einordnung für Filter im Graphen."""
        return self.category or "Chronik"

    def to_dict(self) -> dict:
        d = asdict(self)
        d["date"] = self.date
        return d


def _section_of(url: str) -> str:
    if "/magazin/" in url:
        return "magazin"
    if "/studio/" in url:
        return "studio"
    return "news"


def _text(el) -> str:
    return clean(" ".join(el.text_content().split()))


def _parse_datetime(doc) -> tuple[str, str]:
    raw = ""
    for el in doc.xpath('//div[contains(@class,"story-meta-dates")]//div[contains(@class,"print-only")]'):
        t = _text(el)
        if DATE_RE.search(t):
            raw = t
            break
    if not raw:
        meta = doc.xpath('//meta[@name="dc.date"]/@content')
        if meta:
            try:
                d = dt.date.fromisoformat(meta[0][:10])
                return f"{d.isoformat()}T00:00:00", meta[0]
            except ValueError:
                return "", meta[0]
        return "", ""
    m = DATE_RE.search(raw)
    assert m
    day, month, year, hour, minute = (int(g) for g in m.groups())
    try:
        stamp = dt.datetime(year, month, day, hour, minute)
    except ValueError:
        return "", raw
    # ORF liefert österreichische Lokalzeit (Europe/Vienna)
    return stamp.isoformat(), raw


def parse_article(page: str, url: str) -> Article | None:
    doc = LH.fromstring(page)
    sid = story_id_from_url(url)
    if not sid:
        return None

    title = ""
    for el in doc.xpath('//h1[contains(@class,"story-lead-headline")]') or doc.xpath("//h1"):
        title = _text(el)
        if title:
            break
    if not title:
        title = clean(doc.findtext(".//title") or "")

    category = ""
    for el in doc.xpath('//div[contains(@class,"keyword")]'):
        category = _text(el)
        if category:
            break

    lead = ""
    for el in doc.xpath('//p[contains(@class,"story-lead-text")]'):
        lead = _text(el)
        break

    paragraphs: list[str] = []
    body_nodes = doc.xpath('//div[contains(@class,"story-story")]')
    container = body_nodes[0] if body_nodes else None
    if container is not None:
        for p in container.xpath("./p | .//p"):
            t = _text(p)
            if len(t) > 1:
                paragraphs.append(t)
    else:
        for p in doc.xpath("//main//p"):
            t = _text(p)
            if len(t) > 40:
                paragraphs.append(t)

    # Bildunterschriften enthalten oft zusätzliche Personennennungen
    captions = [_text(c) for c in doc.xpath('//figcaption[contains(@class,"caption")]')]
    captions = [c for c in captions if c]

    byline = ""
    for el in doc.xpath('//div[contains(@class,"byline")]'):
        byline = _text(el)
        if byline:
            break

    published, published_raw = _parse_datetime(doc)

    tags = []
    for el in doc.xpath('//div[contains(@class,"story-footer")]//a'):
        t = _text(el)
        if 2 < len(t) < 40:
            tags.append(t)
    if category:
        tags.insert(0, category)

    related: list[str] = []
    for raw in doc.xpath('//script[@id="more-to-read-data"]/text()'):
        for m in re.finditer(r'"storyId"\s*:\s*(\d+)', raw):
            related.append(m.group(1))
        for m in re.finditer(r'/stories/(\d+)/', raw):
            related.append(m.group(1))

    return Article(
        id=sid,
        url=url,
        title=title,
        section=_section_of(url),
        category=category,
        lead=lead,
        paragraphs=paragraphs,
        captions=captions,
        byline=byline,
        published=published,
        published_raw=published_raw,
        tags=sorted(set(tags)),
        related_ids=sorted(set(r for r in related if r != sid)),
    )
