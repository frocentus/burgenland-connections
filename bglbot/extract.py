"""Personen- und Funktionserkennung in ORF-Artikeln.

Der Ansatz ist bewusst regelbasiert und erklärbar:

* **Kandidaten** sind Folgen großgeschriebener Wörter (1–3 Tokens).
* **Evidenz** liefert der ORF-Stil selbst: „Landeshauptmann Hans Peter
  Doskozil (SPÖ) sagte …“ – Funktionsbezeichnung davor, Parteikürzel in
  Klammern, Rede-Verb danach.
* **Ausschluss** über generische Substantive, ein Korpus-Gazetteer und
  Partei-/Organisationsnamen.
* **Funktionen** werden aus der Bezeichnung davor oder aus Appositionen
  danach („, Bürgermeister von X“, „ist Bürgermeister in Y“) gelesen.
"""

from __future__ import annotations

import re
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from typing import Iterable

from . import lexicon, text as T
from .lexicon import Role
from .parse import Article

# --------------------------------------------------------------------------
# Regexe
# --------------------------------------------------------------------------
_SHORT_ROLES = sorted((s for s in lexicon.ROLE_SURFACES if len(s) < 5), key=len, reverse=True)
_LONG_ROLES = sorted((s for s in lexicon.ROLE_SURFACES if len(s) >= 5), key=len, reverse=True)
_ROLE_ALTERNATION = "|".join(
    [re.escape(s) for s in _SHORT_ROLES] + [re.escape(s) for s in _LONG_ROLES]
)
#: Kurze Bezeichnungen („Abt“, „Obmann“) brauchen eine linke Wortgrenze,
#: lange dürfen in Komposita stecken („Landesgeschäftsführerin“).
_BOUNDARY_GUARD = rf"(?:(?<![A-Za-zÄÖÜäöüß])(?:{'|'.join(re.escape(s) for s in _SHORT_ROLES)})|(?:{'|'.join(re.escape(s) for s in _LONG_ROLES)}))"
ROLE_RE = re.compile(rf"{_BOUNDARY_GUARD}(?![A-Za-zÄÖÜäöüß])", re.IGNORECASE)
ROLE_ANCHORED_RE = re.compile(rf"\s*{_BOUNDARY_GUARD}(?![A-Za-zÄÖÜäöüß])", re.IGNORECASE)

PARTY_RE = re.compile(r"\s*\(\s*(SPÖ|ÖVP|FPÖ|GRÜNE|Grüne|NEOS|KPÖ)\s*\)", re.IGNORECASE)
PARTY_PREFIX_RE = re.compile(r"(SPÖ|ÖVP|FPÖ|Grüne|GRÜNE|NEOS|KPÖ)-\s*$", re.IGNORECASE)

ATTRIBUTION_RE = re.compile(
    r"\s*(?:,\s*)*?(?:"
    + "|".join(sorted((re.escape(v) for v in lexicon.ATTRIBUTION_VERBS), key=len, reverse=True))
    + r")\b",
    re.IGNORECASE,
)

ROLE_AFTER_RES = [
    # „, Bürgermeister von Deutsch Jahrndorf“ / „, der neue Präsident“
    re.compile(
        r"\s*,\s*(?:(?:der|die|der neue|die neue|der designierte|die designierte|"
        r"der scheidende|die scheidende|der bisherige|die bisherige)\s+)?",
        re.IGNORECASE,
    ),
    # „ist Bürgermeister in …“, „war als Landesrätin tätig“
    re.compile(
        r"\s*(?:ist|war|bleibt|wird|wirkt|arbeitet|fungiert|gilt)\s+"
        r"(?:seit\s+[^,.]{0,20}?\s+)?(?:als\s+)?(?:der|die)?\s*",
        re.IGNORECASE,
    ),
    # „als Präsident des GVV“
    re.compile(r"\s+als\s+(?:der|die)?\s*", re.IGNORECASE),
]

ROLE_CONTEXT_RE = re.compile(
    r"\s+(?:von|der|des|in|im|am|bei|für|aus)\s+"
    r"((?:[A-ZÄÖÜ][\wäöüß.\-]+)"
    r"(?:\s+(?:[a-zäöü]{2,4}\s+)?[A-ZÄÖÜ][\wäöüß.\-]+){0,2})",
)

#: Füllwörter, die zwischen Funktion und Name stehen dürfen.
ROLE_FILLER = {
    "der", "die", "das", "den", "dem", "des", "ein", "eine", "einer", "eines",
    "neue", "neuer", "neuen", "designierte", "designierter", "amtierende",
    "amtierender", "bisherige", "bisheriger", "scheidende", "scheidender",
    "langjährige", "langjähriger", "zweite", "zweiter", "stellvertretende",
    "stellvertretender", "sozialdemokratische", "sozialdemokratischer",
    "christdemokratische", "burgenländische", "burgenländischer", "rote",
    "roter", "blaue", "blauer", "türkise", "türkiser", "grüne", "grüner",
    "erste", "erster", "ehemalige", "ehemaliger", "frühere", "früherer",
    "prominente", "prominenter", "bekannte", "bekannter", "zuständige",
    "zuständiger", "künftige", "künftiger", "neugewählte", "neugewählter",
    "gewählte", "gewählter", "stellvertretend",
}

#: Präpositionen, die auf eine Personennennung hindeuten („laut X“).
CUE_PREPS = {"laut", "für", "gegen", "mit", "bei", "von", "an", "auf", "über", "unter"}

WEAK_EVIDENCE = {
    "ist", "war", "wird", "bleibt", "hat", "hatte", "kann", "soll", "will",
    "sagt", "sagte", "meint", "findet", "sieht",
}

PARTICLES = {"von", "van", "de", "zu", "di", "la", "du"}

MAX_SPAN_TOKENS = 3
MIN_ACCEPT_SCORE = 3
MIN_MULTIWORD_SCORE = 4


# --------------------------------------------------------------------------
# Datenstrukturen
# --------------------------------------------------------------------------
@dataclass
class Mention:
    surface: str
    start: int
    sentence: int
    unit: str
    score: int
    evidence: tuple[str, ...] = ()
    role_id: str | None = None
    role_label: str | None = None
    role_surface: str | None = None
    role_context: str | None = None
    party: str | None = None
    person_key: str | None = None
    inferred: bool = False   # nur über Nachnamen zugeordnet

    @property
    def surname(self) -> str:
        return self.surface.split()[-1]

    @property
    def tokens(self) -> int:
        return len(self.surface.split())

    @property
    def is_full_name(self) -> bool:
        return self.tokens >= 2


@dataclass
class PersonInArticle:
    key: str
    name: str
    surname: str
    mentions: list[Mention] = field(default_factory=list)
    roles: Counter = field(default_factory=Counter)
    role_surfaces: Counter = field(default_factory=Counter)
    role_contexts: Counter = field(default_factory=Counter)
    parties: Counter = field(default_factory=Counter)

    @property
    def count(self) -> int:
        return len(self.mentions)

    @property
    def role_id(self) -> str | None:
        return self.roles.most_common(1)[0][0] if self.roles else None

    @property
    def role_label(self) -> str | None:
        if self.role_surfaces:
            return self.role_surfaces.most_common(1)[0][0]
        return None

    @property
    def role_context(self) -> str | None:
        if self.role_contexts:
            return self.role_contexts.most_common(1)[0][0]
        return None

    @property
    def party(self) -> str | None:
        return self.parties.most_common(1)[0][0] if self.parties else None


@dataclass
class ArticleExtraction:
    article: Article
    sentences: list[str]
    persons: list[PersonInArticle]
    mentions: list[Mention]
    window_pairs: list[tuple[str, str]] = field(default_factory=list)
    rejected: list[dict] = field(default_factory=list)
    #: Textbaustein je Satz (titel|lead|body|caption) – für die Unterscheidung
    #: zwischen Fließtext und Aufzählungen.
    units: list[str] = field(default_factory=list)
    #: Einzelnennungen ohne Personenzuordnung („… sagte Doskozil“), die erst
    #: korpusweit über den Nachnamen aufgelöst werden können.
    loose: list[Mention] = field(default_factory=list)

    @property
    def sentence_pairs(self) -> list[tuple[str, str]]:
        """Personenpaare, die im selben Satz vorkommen."""
        keys_per_sentence: list[set[str]] = [set() for _ in self.sentences]
        for m in self.mentions:
            if m.person_key and 0 <= m.sentence < len(keys_per_sentence):
                keys_per_sentence[m.sentence].add(m.person_key)
        pairs: set[tuple[str, str]] = set()
        for keys in keys_per_sentence:
            ordered = sorted(keys)
            for i, a in enumerate(ordered):
                for b in ordered[i + 1:]:
                    pairs.add((a, b))
        return sorted(pairs)


@dataclass
class ExtractionContext:
    geo: set[str]
    known: set[str] = field(default_factory=set)
    #: Wörter, die im Korpus klein vorkommen – also Substantive, keine Nachnamen.
    common_nouns: set[str] = field(default_factory=set)
    #: Vornamen, die erst im zweiten Durchlauf aus dem Korpus gelernt wurden.
    extra_first_names: set[str] = field(default_factory=set)


# --------------------------------------------------------------------------
# Hilfsfunktionen
# --------------------------------------------------------------------------
#: "SPÖ-Landeshauptmann", "Ex-Bürgermeister" – die Partei ist ein eigenes Feld.
_PARTY_PREFIX_RE = re.compile(r"^(?:SPÖ|ÖVP|FPÖ|Grüne|GRÜNE|NEOS|KPÖ|Ex)-")
_GENITIVE_SUFFIXES = ("s", "es", "en", "e")


def normalize_role_surface(surface: str) -> str:
    """Bringt Schreibvarianten einer Funktion auf eine Form.

    „SPÖ-Landeshauptmann“, „Landeshauptmanns“ und „Landeshauptmann“ sind
    dieselbe Funktion; die Partei steht bereits als eigenes Attribut am Knoten.
    """
    text = _PARTY_PREFIX_RE.sub("", surface.strip())
    low = text.lower()
    if low in lexicon.ROLE_SURFACES:
        return text
    for suffix in _GENITIVE_SUFFIXES:
        if low.endswith(suffix) and low[:-len(suffix)] in lexicon.ROLE_SURFACES:
            return text[:-len(suffix)]
    # Komposita ("Landesgeschäftsführer", "Bildungslandesrätin"): die
    # enthaltene Funktionsbezeichnung ist die Anzeigeform.
    for key in sorted(lexicon.ROLE_SURFACES, key=len, reverse=True):
        if low.endswith(key) and len(low) > len(key):
            return key[0].upper() + key[1:]
    return text


def _is_person_token(word: str) -> bool:
    return T.is_name_token(word) and len(word) >= 3


def _spans_in_run(run: list[T.Token], sentence: str) -> Iterable[list[T.Token]]:
    """Alle Kandidaten-Spans (Länge 1..3) in einem Lauf großgeschriebener Wörter.

    Zwischen zwei Namensgliedern darf nur Leerraum stehen – sonst würden
    Satzzeichen wie „Zsifkovics: Papst“ zu einem Namen verschmelzen.
    """
    n = len(run)

    def joined(a: int, b: int) -> bool:
        return all(sentence[run[k].end:run[k + 1].start].strip() == "" for k in range(a, b))
    for i in range(n):
        head = run[i].text.lower()
        if head in PARTICLES or head in lexicon.ACADEMIC_TITLES:
            continue
        # Steht hinter dem Token ein Vorname, ist das Token selbst kein Namensbeginn
        # ("Obstbauverbandes Johann Plemenschits" -> "Johann Plemenschits").
        if (i + 1 < n and run[i].text.lower() not in lexicon.FIRST_NAMES
                and run[i + 1].text.lower() in lexicon.FIRST_NAMES):
            continue
        for length in range(1, MAX_SPAN_TOKENS + 1):
            j = i + length - 1
            if j >= n:
                break
            # Dreiteilige Namen sind im ORF-Stil Vorname + Rufname + Nachname
            # ("Hans Peter Doskozil"); sonst steckt ein Substantiv dazwischen.
            if length == 3 and run[i + 1].text.lower() not in lexicon.FIRST_NAMES:
                break
            if not joined(i, j):
                continue
            span = run[i:j + 1]
            if span[-1].text.lower() in PARTICLES:
                continue
            # Ein Vorname am Span-Ende leitet die nächste Person ein
            # ("Rory McIlroy Jon Rahm" -> "Rory McIlroy"), der längere Span
            # darf aber weiter geprüft werden ("Hans Peter Doskozil").
            if length > 1 and span[-1].text.lower() in lexicon.FIRST_NAMES:
                continue
            if not all(_is_person_token(t.text) for t in span):
                break
            yield span


def _role_before(tokens: list[T.Token], i: int) -> tuple[Role, str, int] | None:
    """Sucht die Funktionsbezeichnung links vom Namen (max. 4 Tokens entfernt)."""
    for k in range(i - 1, max(-1, i - 5), -1):
        tok = tokens[k].text
        match = ROLE_RE.search(tok)
        if not match:
            # "Landwirtschaftskammerpräsidenten", "Bürgermeisters": Endung
            # abschneiden und erneut versuchen.
            for suffix in ("en", "s", "es", "n"):
                if tok.lower().endswith(suffix) and len(tok) - len(suffix) >= 5:
                    match = ROLE_RE.search(tok[:-len(suffix)])
                    if match:
                        break
        if match:
            role = lexicon.ROLE_SURFACES.get(match.group(0).lower())
            if role:
                # Bei Komposita ("Bildungslandesrätin") die ganze Wortform anzeigen.
                return role, tok, k
            return None
        if tok.lower() in ROLE_FILLER:
            continue
        return None
    return None


def _role_after(sentence: str, offset: int) -> tuple[Role, str, int] | None:
    for prefix in ROLE_AFTER_RES:
        m = prefix.match(sentence, offset)
        if not m:
            continue
        role_match = ROLE_ANCHORED_RE.match(sentence[m.end():])
        if role_match:
            surface = role_match.group(0).strip()
            role = lexicon.ROLE_SURFACES.get(surface.lower())
            if role:
                return role, surface, m.end() + (len(role_match.group(0)) - len(role_match.group(0).lstrip()))
    return None


def _role_context(sentence: str, offset: int) -> str | None:
    m = ROLE_CONTEXT_RE.match(sentence, offset)
    if not m:
        return None
    ctx = m.group(1).strip()
    return ctx[:60] if ctx else None


def _party_after(sentence: str, offset: int) -> str | None:
    m = PARTY_RE.match(sentence, offset)
    if not m:
        return None
    raw = m.group(1)
    return lexicon.PARTY_ALIASES.get(raw.lower(), raw.upper() if len(raw) > 3 else raw)


def _party_prefix(sentence: str, tokens: list[T.Token], pos: int) -> str | None:
    """Partei aus „SPÖ-Landesparteivorsitzender“ oder „SPÖ-Chef“."""
    in_token = re.match(r"^(SPÖ|ÖVP|FPÖ|Grüne|GRÜNE|NEOS|KPÖ)-", tokens[pos].text,
                        re.IGNORECASE)
    if in_token:
        raw = in_token.group(1)
        return lexicon.PARTY_ALIASES.get(raw.lower(), raw)
    before = PARTY_PREFIX_RE.search(sentence[:tokens[pos].start])
    if before:
        raw = before.group(1)
        return lexicon.PARTY_ALIASES.get(raw.lower(), raw)
    for k in (pos - 1, pos - 2):
        if k >= 0:
            inline = re.match(r"^(SPÖ|ÖVP|FPÖ|Grüne|GRÜNE|NEOS|KPÖ)-", tokens[k].text,
                              re.IGNORECASE)
            if inline:
                raw = inline.group(1)
                return lexicon.PARTY_ALIASES.get(raw.lower(), raw)
    return None


def _blocked(words: list[str], ctx: ExtractionContext) -> bool:
    for position, word in enumerate(words):
        low = word.lower()
        if low in ctx.geo or lexicon.is_generic(low) or len(low) < 3:
            return True
        # Nur das letzte Token ist die Nachnamen-Position; Vornamen wie
        # "Roland" (endet auf "land") dürfen nicht als Kompositum gelten.
        if position == len(words) - 1 and lexicon.ends_with_thing(low):
            return True
        if ROLE_RE.search(word):
            return True
        # Bindestrich-Komposita wie "Gelb-Rot" oder "Karl-Goldmark-Museums" prüfen.
        if "-" in low:
            parts = [p for p in low.split("-") if p]
            if any(lexicon.is_generic(p) or p in ctx.geo or len(p) < 3 for p in parts):
                return True
    return False


def _score_span(span: list[T.Token], sentence: str, tokens: list[T.Token],
                i: int, j: int, ctx: ExtractionContext,
                counts: Counter, unit: str = "body") -> tuple[int, list[str], dict] | None:
    words = [t.text for t in span]
    if _blocked(words, ctx):
        return None

    score = 0
    evidence: list[str] = []
    details: dict = {}

    # "Konrad Adenauer Stiftung", "Thomas-Morus-Preis": das folgende Wort
    # entlarvt den Kandidaten als Institution.
    if j + 1 < len(tokens) and tokens[j + 1].text.lower() in lexicon.INSTITUTION_WORDS:
        return None

    role_hit = _role_before(tokens, i)
    if role_hit:
        role, role_surface, pos = role_hit
        # „Geschäftsführer der Biowärme“: Genitivartikel -> Organisation, keine Person.
        between = tokens[pos + 1:i]
        if between and between[-1].text.lower() in {"der", "des", "dem", "den"}:
            return None
        score += 4
        evidence.append("funktion_davor")
        details["role"] = (role, role_surface, pos)
        party = _party_prefix(sentence, tokens, pos)
        if party:
            details["party"] = party

    name_end = tokens[j].end
    party = _party_after(sentence, name_end)
    if party:
        score += 3
        evidence.append("partei_klammer")
        details["party"] = party

    if ATTRIBUTION_RE.match(sentence, name_end):
        score += 2
        evidence.append("redeverb")

    if i > 0 and tokens[i - 1].text.lower() in CUE_PREPS:
        score += 1
        evidence.append("praeposition")

    # Bildzeilen liefern nur dann Evidenz, wenn der Name bereits durch Vorname,
    # Funktion oder Parteikürzel gedeckt ist – sonst würden Motive wie
    # "Alkoholfreies Bier" zu Personen.
    if unit == "caption" and len(words) >= 2 and (
            role_hit or "vorname" in evidence or "partei_klammer" in evidence):
        score += 1
        evidence.append("bildzeile")

    # Namen in Aufzählungen ("Martin Ganster, Elisabeth …, Raphaela Pint")
    if _in_enumeration(sentence, tokens[i].start, tokens[j].end):
        score += 2
        evidence.append("aufzaehlung")

    surface = " ".join(words)
    count = counts.get(surface, 0)
    if count >= 2:
        score += 1
        evidence.append(f"wiederholt_{count}")

    if surface.lower() in ctx.known:
        score += 4
        evidence.append("bekannt")

    if words[0].lower() in lexicon.FIRST_NAMES or words[0].lower() in ctx.extra_first_names:
        score += 2
        evidence.append("vorname" if words[0].lower() in lexicon.FIRST_NAMES else "vorname_gelernt")

    if len(words) >= 2:
        score += 1
        evidence.append("mehrteilig")
        if j + 1 < len(tokens) and tokens[j + 1].text.lower() in WEAK_EVIDENCE:
            score += 1
            evidence.append("verb_umgebung")

    details["score"] = score
    return score, evidence, details


def _in_enumeration(sentence: str, start: int, end: int) -> bool:
    """Prüft, ob der Kandidat Teil einer Komma-Aufzählung ist."""
    commas = sentence.count(",")
    if commas < 3:
        return False
    before = sentence[:start].rstrip()
    after = sentence[end:].lstrip()
    separators = (",", "und", "sowie", "bzw.")
    touches_after = any(after.startswith(sep) for sep in separators)
    touches_before = any(before.endswith(sep) for sep in separators)
    return touches_after or touches_before


def _accept(score: int, evidence: list[str], n_tokens: int, surface: str,
            shift: int) -> bool:
    strong = any(e in evidence for e in ("funktion_davor", "partei_klammer", "bekannt", "redeverb"))
    repeat = any(e.startswith("wiederholt_") for e in evidence)
    if n_tokens == 1:
        if surface.lower() in lexicon.FIRST_NAMES:
            return False  # unvollständiger Name („Carina“)
        return score >= MIN_ACCEPT_SCORE + shift and (
            "funktion_davor" in evidence or "bekannt" in evidence
        )

    if ("vorname" in evidence or "vorname_gelernt" in evidence) and score >= 3 + shift:
        return True
    if score >= MIN_MULTIWORD_SCORE + shift and (strong or "vorname" in evidence or "vorname_gelernt" in evidence):
        return True
    return score >= 6 + shift


# --------------------------------------------------------------------------
# Extraktion eines Artikels
# --------------------------------------------------------------------------
def extract_article(article: Article, ctx: ExtractionContext,
                    threshold_shift: int = 0, debug: bool = False) -> ArticleExtraction:
    units: list[tuple[str, str]] = [("titel", article.title)]
    if article.lead:
        units.append(("lead", article.lead))
    units.extend(("body", p) for p in article.paragraphs)
    units.extend(("caption", c) for c in article.captions)

    sentences: list[str] = []
    sentence_units: list[str] = []
    for unit, text_value in units:
        for sent in T.split_sentences(text_value):
            sentences.append(sent)
            sentence_units.append(unit)

    counts: Counter = Counter()
    for sent in sentences:
        tokens = T.tokenize(sent)
        for run in _runs(tokens):
            for span in _spans_in_run(run, sent):
                counts[" ".join(t.text for t in span)] += 1

    mentions: list[Mention] = []
    loose: list[Mention] = []
    rejected: list[dict] = []

    for s_idx, sent in enumerate(sentences):
        tokens = T.tokenize(sent)
        candidates: list[tuple[int, int, list[T.Token], int, list[str], dict]] = []
        for run in _runs(tokens):
            for span in _spans_in_run(run, sent):
                i = tokens.index(span[0])
                j = i + len(span) - 1
                scored = _score_span(span, sent, tokens, i, j, ctx, counts, sentence_units[s_idx])
                if scored is None:
                    continue
                score, evidence, details = scored
                if _accept(score, evidence, len(span), " ".join(t.text for t in span),
                           threshold_shift):
                    candidates.append((i, j, span, score, evidence, details))
                elif len(span) == 1 and score >= 2:
                    loose.append(_make_mention(span, s_idx, sentence_units[s_idx], score, evidence))
                elif debug and score >= 3:
                    rejected.append({
                        "surface": " ".join(t.text for t in span),
                        "score": score,
                        "evidence": evidence,
                        "sentence": sent[:160],
                    })

        # Überlappende Spans entfernen: längster, dann höchster Score gewinnt.
        candidates.sort(key=lambda c: (-(c[1] - c[0]), -c[3]))
        taken: list[tuple[int, int]] = []
        for i, j, span, score, evidence, details in candidates:
            if any(not (j < a or i > b) for a, b in taken):
                continue
            taken.append((i, j))
            mention = _make_mention(span, s_idx, sentence_units[s_idx], score, evidence)
            role_info = details.get("role")
            if role_info:
                role, role_surface, pos = role_info
                mention.role_id = role.canonical
                mention.role_label = role.label
                mention.role_surface = role_surface
                mention.role_context = _role_context(sent, tokens[pos].end)
            else:
                after = _role_after(sent, span[-1].end)
                if after:
                    role, role_surface, role_pos = after
                    mention.role_id = role.canonical
                    mention.role_label = role.label
                    mention.role_surface = role_surface
                    mention.role_context = _role_context(sent, role_pos + len(role_surface))
            if details.get("party"):
                mention.party = details["party"]
            mention = _strip_genitive(mention, sent, span)
            mentions.append(mention)

    persons, linked = _cluster_in_article(mentions, loose)
    linked_ids = {id(m) for m in linked}
    unlinked = [m for m in loose if id(m) not in linked_ids and m.person_key is None]
    # Akzeptierte, aber im Artikel nicht zuordenbare Einzeltokens ebenfalls
    # für die korpusweite Auflösung vormerken.
    unlinked += [m for m in mentions if m.person_key is None and not m.is_full_name]
    window_pairs = _build_window_pairs(linked, len(sentences))
    return ArticleExtraction(
        article=article,
        sentences=sentences,
        persons=persons,
        mentions=linked,
        window_pairs=window_pairs,
        rejected=rejected,
        loose=unlinked,
        units=sentence_units,
    )


GENITIVE_NOUN_RE = re.compile(r"\s+([A-ZÄÖÜ][a-zäöüß\-]{2,})")


def _strip_genitive(mention: Mention, sentence: str, span: list[T.Token]) -> Mention:
    """Entfernt ein Genitiv-s, wenn danach ein Substantiv steht.

    „Heinrich Knotzers Werk“ beschreibt die Person „Heinrich Knotzer“.
    """
    last = span[-1]
    word = last.text
    if not word.endswith("s") or len(word) < 6:
        return mention
    follow = GENITIVE_NOUN_RE.match(sentence, last.end)
    if not follow:
        return mention
    follower = follow.group(1)
    if follower.lower() in lexicon.FIRST_NAMES or not T.is_name_token(follower):
        return mention
    words = mention.surface.split()
    words[-1] = words[-1][:-1]
    mention.surface = " ".join(words)
    mention.evidence = mention.evidence + ("genitiv",)
    return mention


def _make_mention(span: list[T.Token], s_idx: int, unit: str, score: int,
                  evidence: list[str]) -> Mention:
    return Mention(
        surface=" ".join(t.text for t in span),
        start=span[0].start,
        sentence=s_idx,
        unit=unit,
        score=score,
        evidence=tuple(evidence),
    )


def _runs(tokens: list[T.Token]) -> list[list[T.Token]]:
    runs: list[list[T.Token]] = []
    current: list[T.Token] = []
    for tok in tokens:
        if T.is_name_token(tok.text) or (current and tok.text.lower() in PARTICLES):
            current.append(tok)
        else:
            if current:
                runs.append(current)
            current = []
    if current:
        runs.append(current)
    return runs


def _build_window_pairs(mentions: list[Mention], n_sentences: int) -> list[tuple[str, str]]:
    keys_per_sentence: list[set[str]] = [set() for _ in range(n_sentences)]
    for m in mentions:
        if m.person_key and 0 <= m.sentence < n_sentences:
            keys_per_sentence[m.sentence].add(m.person_key)
    pairs: set[tuple[str, str]] = set()
    for idx in range(n_sentences - 1):
        for a in keys_per_sentence[idx]:
            for b in keys_per_sentence[idx + 1]:
                if a != b:
                    pairs.add((min(a, b), max(a, b)))
    return sorted(pairs)


def _cluster_in_article(mentions: list[Mention], loose: list[Mention]
                        ) -> tuple[list[PersonInArticle], list[Mention]]:
    """Fasst Nennungen eines Artikels zu Personen zusammen und löst Nachnamen auf."""
    by_surface: dict[str, list[Mention]] = defaultdict(list)
    for m in mentions:
        by_surface[m.surface].append(m)

    clusters: dict[str, PersonInArticle] = {}
    surname_to_keys: dict[str, list[str]] = defaultdict(list)
    for surface, items in by_surface.items():
        if len(surface.split()) < 2:
            continue
        key = T.slug(surface)
        cluster = clusters.setdefault(
            key, PersonInArticle(key=key, name=surface, surname=items[0].surname)
        )
        surname = surface.split()[-1].lower()
        if key not in surname_to_keys[surname]:
            surname_to_keys[surname].append(key)
        cluster.mentions.extend(items)

    _merge_compatible(clusters, surname_to_keys)

    attached: list[Mention] = []
    for m in mentions:
        if m.is_full_name:
            attached.append(m)
            continue
        surname = m.surface.lower()
        keys = surname_to_keys.get(surname, [])
        if len(keys) == 1:
            clusters[keys[0]].mentions.append(m)
            attached.append(m)
        elif len(keys) > 1:
            best = max(keys, key=lambda k: len(clusters[k].mentions))
            clusters[best].mentions.append(m)
            attached.append(m)
        # Einzelne Nachnamen erzeugen keinen eigenen Knoten: Sie werden erst
        # korpusweit zugeordnet (eindeutiger Nachname) – sonst würden
        # Berufsbezeichnungen wie "Kapellmeister" zu Personen.

    _merge_compatible(clusters, surname_to_keys)

    # Nicht akzeptierte Einzeltokens („… sagte Doskozil“) als Namensverweis anhängen.
    inferred: list[Mention] = []
    for m in loose:
        keys = surname_to_keys.get(m.surface.lower(), [])
        if not keys:
            continue
        best = max(keys, key=lambda k: len(clusters[k].mentions))
        copy = Mention(**{**m.__dict__, "inferred": True, "person_key": best})
        clusters[best].mentions.append(copy)
        inferred.append(copy)
        m.person_key = best          # Original als verarbeitet markieren

    for cluster in clusters.values():
        if not cluster.mentions:
            continue
        full_names = [m.surface for m in cluster.mentions if m.is_full_name]
        if full_names:
            cluster.name = max(full_names, key=lambda s: (len(s.split()), len(s)))
            cluster.surname = cluster.name.split()[-1]
        for m in cluster.mentions:
            m.person_key = cluster.key
            if m.role_id and m.role_label:
                cluster.roles[m.role_id] += 1
                cluster.role_surfaces[normalize_role_surface(m.role_surface or m.role_label)] += 1
                if m.role_context:
                    cluster.role_contexts[m.role_context] += 1
            if m.party:
                cluster.parties[m.party] += 1

    persons = sorted(clusters.values(), key=lambda p: -p.count)
    return persons, attached + inferred


def _levenshtein(a: str, b: str) -> int:
    if a == b:
        return 0
    if not a:
        return len(b)
    if not b:
        return len(a)
    prev = list(range(len(b) + 1))
    for i, ca in enumerate(a, 1):
        cur = [i]
        for j, cb in enumerate(b, 1):
            cur.append(min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + (ca != cb)))
        prev = cur
    return prev[-1]


def _osa_distance(a: str, b: str) -> int:
    """Damerau-Levenshtein (Optimal String Alignment) für Tippfehler wie
    „Luisa“/„Lusia“."""
    if a == b:
        return 0
    d = [[0] * (len(b) + 1) for _ in range(len(a) + 1)]
    for i in range(len(a) + 1):
        d[i][0] = i
    for j in range(len(b) + 1):
        d[0][j] = j
    for i in range(1, len(a) + 1):
        for j in range(1, len(b) + 1):
            cost = 0 if a[i - 1] == b[j - 1] else 1
            d[i][j] = min(d[i - 1][j] + 1, d[i][j - 1] + 1, d[i - 1][j - 1] + cost)
            if i > 1 and j > 1 and a[i - 1] == b[j - 2] and a[i - 2] == b[j - 1]:
                d[i][j] = min(d[i][j], d[i - 2][j - 2] + 1)
    return d[len(a)][len(b)]


def _first_name(name: str) -> str:
    parts = name.split()
    return parts[0].lower() if len(parts) >= 2 else ""


def _merge_compatible(clusters: dict[str, PersonInArticle],
                      surname_to_keys: dict[str, list[str]]) -> None:
    """Führt Schreibweisen wie „Hans Doskozil“/„Hans Peter Doskozil“ zusammen.

    Zusätzlich werden Tippvarianten des Nachnamens („Sengstbratl“/„Sengsbratl“)
    zusammengelegt, sofern der Vorname passt oder auf einer Seite fehlt.
    """
    for surname, keys in list(surname_to_keys.items()):
        if len(keys) < 2:
            continue
        merged: list[str] = []
        for key in keys:
            name_parts = clusters[key].name.split()
            target = None
            for existing in merged:
                other_parts = clusters[existing].name.split()
                shorter, longer = sorted((name_parts, other_parts), key=len)
                if set(shorter[:-1]) <= set(longer[:-1]) and shorter[-1] == longer[-1]:
                    target = existing
                    break
            if target:
                clusters[target].mentions.extend(clusters[key].mentions)
                del clusters[key]
            else:
                merged.append(key)
        surname_to_keys[surname] = merged

    # Tippvarianten des Vornamens bei identischem Nachnamen (im selben Artikel
    # ist das fast immer dieselbe Person: „Stefan“/„Stephan“).
    for surname, keys in surname_to_keys.items():
        if len(keys) < 2:
            continue
        keep = keys[0]
        for other in keys[1:]:
            if keep not in clusters or other not in clusters:
                continue
            first_a = _first_name(clusters[keep].name) or clusters[keep].name.lower()
            first_b = _first_name(clusters[other].name) or clusters[other].name.lower()
            if abs(len(first_a) - len(first_b)) > 2:
                continue
            if len(first_a) < 4 or len(first_b) < 4:
                continue
            if _osa_distance(first_a, first_b) <= 2:
                clusters[keep].mentions.extend(clusters.pop(other).mentions)
        surname_to_keys[surname] = [keep]

    # Tippvarianten des Nachnamens zusammenführen.
    surnames = [s for s, keys in surname_to_keys.items() if len(keys) == 1]
    for idx, first in enumerate(surnames):
        for second in surnames[idx + 1:]:
            if abs(len(first) - len(second)) > 1:
                continue
            if _levenshtein(first, second) > 1:
                continue
            keys_a = surname_to_keys.get(first, [])
            keys_b = surname_to_keys.get(second, [])
            if len(keys_a) != 1 or len(keys_b) != 1 or keys_a[0] not in clusters or keys_b[0] not in clusters:
                continue
            cluster_a, cluster_b = clusters[keys_a[0]], clusters[keys_b[0]]
            name_a, name_b = _first_name(cluster_a.name), _first_name(cluster_b.name)
            if name_a and name_b and _levenshtein(name_a, name_b) > 1:
                continue
            keep, drop = (cluster_a, cluster_b) if cluster_a.count >= cluster_b.count else (cluster_b, cluster_a)
            keep.mentions.extend(drop.mentions)
            clusters.pop(drop.key, None)
            surname_to_keys[first] = [keep.key]
            surname_to_keys.pop(second, None)
