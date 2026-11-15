"""Textwerkzeuge: Satzzerlegung, Tokenisierung, Normalisierung."""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass

ABBREVIATIONS = {
    "z.b", "u.a", "bzw", "ca", "dr", "mag", "ing", "di", "nr", "abs", "bzgl",
    "ggü", "inkl", "lt", "max", "min", "mio", "mrd", "prof", "sog", "std",
    "u.ä", "v.a", "vgl", "z.t", "kost", "ehem", "evtl", "allg", "gem", "jh",
    "jhdt", "mill", "tsd", "usw", "etc", "ff", "st", "str", "tel", "www",
}

SENT_SPLIT_RE = re.compile(r"(?<=[.!?])[\"'”’»)]*\s+")

TOKEN_RE = re.compile(r"[A-Za-zÄÖÜäöüßÉéÈèÁáÍíÓóÚúĆćČčŠšŽžĐđĞğ\-']+|\d+(?:[.,]\d+)*")

#: Tokens, die als Namensteil grundsätzlich in Frage kommen.
NAME_TOKEN_RE = re.compile(r"^[A-ZÄÖÜ][a-zäöüßéèáíóúćčšžđ'\-]+$")
#: Namensteile mit Bindestrich („Haider-Wallner“), aber keine Akronym-Komposita
#: wie „SPÖ-Chef“ oder „NS-Opfer“.
HYPHEN_NAME_RE = re.compile(r"^[A-ZÄÖÜ][a-zäöüßéèáíóúćčšžđ']*(?:-[A-ZÄÖÜ][a-zäöüßéèáíóúćčšžđ']+)+$")
#: Namen mit Binnenmajuskel („McIlroy“, „McCarthy“).
CAMEL_NAME_RE = re.compile(r"^[A-ZÄÖÜ][a-zäöüß]{1,3}[A-ZÄÖÜ][a-zäöüßéèáíóúćčšžđ']+$")


def fold(text: str) -> str:
    """Vergleichsform ohne Groß-/Kleinschreibung (Umlaute bleiben)."""
    return text.strip().lower()


def slug(text: str) -> str:
    """ASCII-Slug für IDs und Dateinamen."""
    text = unicodedata.normalize("NFKD", text)
    text = "".join(c for c in text if not unicodedata.combining(c))
    text = text.lower().replace("ß", "ss")
    text = re.sub(r"[^a-z0-9]+", "-", text)
    return text.strip("-")


def _ends_with_abbreviation(fragment: str) -> bool:
    words = fragment.split()
    if not words:
        return False
    last = re.sub(r"[^\w.äöüß]", "", words[-1].lower()).rstrip(".")
    # Ordinalzahlen („zum 18. Mal“) und Datumsangaben („14. November“) trennen nicht.
    if last.isdigit():
        return True
    return last in ABBREVIATIONS or (len(last) == 1 and last.isalpha())


def split_sentences(text: str) -> list[str]:
    """Grobe, aber robuste Satzzerlegung für deutsche Nachrichtentexte.

    Abkürzungen (``z.B.``, ``Dr.``, Initialen) führen zu keinem Satzbruch.
    """
    text = text.replace("\n", " ")
    text = re.sub(r"\s{2,}", " ", text)
    sentences: list[str] = []
    buf = ""
    for part in SENT_SPLIT_RE.split(text):
        buf = f"{buf} {part}".strip() if buf else part
        if _ends_with_abbreviation(buf):
            continue
        if buf:
            sentences.append(buf)
        buf = ""
    if buf:
        sentences.append(buf)
    return sentences


@dataclass(frozen=True)
class Token:
    text: str
    start: int
    end: int
    index: int


def tokenize(sentence: str) -> list[Token]:
    return [
        Token(m.group(0), m.start(), m.end(), i)
        for i, m in enumerate(TOKEN_RE.finditer(sentence))
    ]


def is_name_token(token: str) -> bool:
    if NAME_TOKEN_RE.match(token) or HYPHEN_NAME_RE.match(token):
        return True
    return bool(CAMEL_NAME_RE.match(token))


def sentence_windows(text: str, size: int = 2, stride: int = 1) -> list[str]:
    """Satzfenster für ko-lokale Ko-Erwähnung (Standard: 2 Sätze)."""
    sents = split_sentences(text)
    out = []
    for i in range(0, len(sents), stride):
        chunk = sents[i:i + size]
        if chunk:
            out.append(" ".join(chunk))
    return out
