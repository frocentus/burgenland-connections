"""Automatisch gelerntes Ortsnamen-Verzeichnis (Gazetteer).

Deutsche Nachrichtentexte schreiben alle Substantive groß, deshalb sehen
Ortsnamen für einen reinen Großschreibungs-Filter wie Personennamen aus.
Statt hunderte Gemeinden manuell zu pflegen, lernt der Bot Toponyme aus dem
eigenen Korpus: Ein Token gilt als Ort, wenn es gehäuft nach einer
Ortspräposition („in Raiding“) oder nach ``Bezirk``/``Gemeinde`` steht und
nie hinter einer Funktionsbezeichnung auftaucht.
"""

from __future__ import annotations

import re
from collections import Counter

from . import lexicon

PLACE_CUE_RE = re.compile(
    r"\b(?:in|aus|nach|bei|von|gegen|um|durch|über|nahe|Richtung)\s+"
    r"([A-ZÄÖÜ][A-Za-zÄöüß\-]{2,})"
)
ADMIN_CUE_RE = re.compile(
    r"\b(?:Bezirk|Bezirks|Gemeinde|Marktgemeinde|Stadt|Stadtgemeinde|Ort|Ortschaft|"
    r"Region|Dorf|Katastralgemeinde|Land)\s+([A-ZÄÖÜ][A-Za-zÄöüß\-]{2,})"
)
#: Ein Name direkt hinter einer Funktionsbezeichnung spricht gegen einen Ort.
ROLE_CUE_RE = re.compile(
    r"(?:" + "|".join(sorted((re.escape(s) for s in lexicon.ROLE_SURFACES), key=len, reverse=True)) + r")\s+"
    r"([A-ZÄÖÜ][A-Za-zÄöüß\-]{2,}(?:\s+[A-ZÄÖÜ][A-Za-zÄöüß\-]{2,})?)",
    re.IGNORECASE,
)

MIN_PLACE_HITS = 3


def learn(texts: list[str]) -> set[str]:
    """Liefert die Menge gelernter Ortsnamen (klein geschrieben, einzelne Tokens)."""
    place_hits: Counter[str] = Counter()
    role_hits: Counter[str] = Counter()

    for text in texts:
        for token in PLACE_CUE_RE.findall(text):
            place_hits[token.lower()] += 1
        for token in ADMIN_CUE_RE.findall(text):
            place_hits[token.lower()] += 3
        for match in ROLE_CUE_RE.finditer(text):
            for word in match.group(1).split():
                role_hits[word.lower()] += 1

    learned = set()
    for token, hits in place_hits.items():
        if hits < MIN_PLACE_HITS:
            continue
        # Vornamen sind keine Orte – sonst verschwinden Personen wie
        # "Wolfgang Unger", weil "Wolfgang" als Ortsname gelernt wurde.
        if token in lexicon.FIRST_NAMES:
            continue
        # Taucht das Token nie als Personenname auf, ist es sehr wahrscheinlich ein Ort.
        if role_hits[token] == 0:
            learned.add(token)
        # Grenzfall: überwiegend ortsgebunden (z. B. Nachname == Ortsname)
        elif hits >= 4 * role_hits[token]:
            learned.add(token)
    return learned


LOWERCASE_WORD_RE = re.compile(r"(?<![A-Za-zÄÖÜäöüß])[a-zäöüß]{4,}(?![A-Za-zÄÖÜäöüß])")


def learn_common_nouns(texts: list[str], min_hits: int = 3) -> set[str]:
    """Wörter, die im Korpus auch klein geschrieben vorkommen.

    Deutsche Substantive stehen im Satz groß, tauchen aber in anderer Form
    („ein Bier“, „die Anfrage“) klein auf. Nachnamen tun das praktisch nie –
    damit lassen sich Bildzeilen wie „Alkoholfreies Bier“ aussortieren.
    """
    counts: Counter[str] = Counter()
    for text in texts:
        lower = text.lower()
        for word in LOWERCASE_WORD_RE.findall(lower):
            counts[word] += 1
    return {word for word, hits in counts.items() if hits >= min_hits}


def combine(learned: set[str]) -> set[str]:
    """Vereinigt manuelle Liste und Korpuswissen."""
    return set(lexicon.GEO_WORDS) | learned
