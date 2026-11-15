"""Artikelübergreifende Personenauflösung.

Innerhalb eines Artikels löst :mod:`bglbot.extract` Nachnamen auf. Über den
gesamten Korpus hinweg müssen zusätzlich Schreibvarianten, Tippfehler und
reine Nachnamen-Nennungen („Doskozil“) zusammengeführt werden.
"""

from __future__ import annotations

import re
from collections import Counter, defaultdict
from dataclasses import dataclass, field

from . import lexicon
from . import text as T
from .extract import ArticleExtraction, PersonInArticle, _levenshtein, _osa_distance

Entry = tuple[ArticleExtraction, PersonInArticle]


@dataclass
class Person:
    id: str
    name: str
    surname: str
    variants: Counter = field(default_factory=Counter)
    roles: Counter = field(default_factory=Counter)
    role_surfaces: Counter = field(default_factory=Counter)
    role_contexts: Counter = field(default_factory=Counter)
    parties: Counter = field(default_factory=Counter)
    articles: list[str] = field(default_factory=list)
    mentions: int = 0
    first_seen: str = ""
    last_seen: str = ""
    ambiguous: bool = False

    # -- abgeleitete Anzeigefelder -------------------------------------
    @property
    def article_count(self) -> int:
        return len(self.articles)

    @property
    def role_label(self) -> str | None:
        """Anzeigeform der häufigsten Funktion (nicht der häufigsten Schreibweise)."""
        grouped = self._roles_by_canonical()
        return grouped[0]["label"] if grouped else None

    def _roles_by_canonical(self) -> list[dict]:
        """Fasst Schreibvarianten je kanonischer Funktion zusammen."""
        by_id: dict[str, dict] = {}
        for role_id, count in self.roles.most_common():
            surfaces = [s for s in self.role_surfaces
                        if (lexicon.ROLE_SURFACES.get(s.lower())
                            and lexicon.ROLE_SURFACES[s.lower()].canonical == role_id)]
            label = max(surfaces, key=lambda s: self.role_surfaces[s]) if surfaces else role_id[:1].upper() + role_id[1:]
            by_id[role_id] = {"label": label, "count": count}
        return sorted(by_id.values(), key=lambda item: -item["count"])

    @property
    def role_id(self) -> str | None:
        return self.roles.most_common(1)[0][0] if self.roles else None

    @property
    def role_context(self) -> str | None:
        return self.role_contexts.most_common(1)[0][0] if self.role_contexts else None

    @property
    def party(self) -> str | None:
        return self.parties.most_common(1)[0][0] if self.parties else None

    @property
    def role_category(self) -> str:
        return lexicon.ROLE_CATEGORY.get(self.role_id or "", "sonstiges")

    @property
    def confidence(self) -> str:
        if self.ambiguous:
            return "niedrig"
        if self.article_count >= 3 and self.mentions >= 5:
            return "hoch"
        if self.article_count >= 2:
            return "mittel"
        return "niedrig"

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "surname": self.surname,
            "party": self.party,
            "role": self.role_label,
            "role_id": self.role_id,
            "role_category": self.role_category,
            "role_context": self.role_context,
            "articles": self.article_count,
            "mentions": self.mentions,
            "first_seen": self.first_seen,
            "last_seen": self.last_seen,
            "confidence": self.confidence,
            "ambiguous": self.ambiguous,
            "variants": [v for v, _ in self.variants.most_common(6)],
            "roles": self._roles_by_canonical()[:6],
            "contexts": [c for c, _ in self.role_contexts.most_common(4)],
        }


def _merge_subset_groups(full_groups: dict[tuple[str, str], list[Entry]]) -> None:
    """Führt Namensgruppen zusammen, deren Vornamen ineinander enthalten sind.

    „Peter Doskozil“ und „Hans Peter Doskozil“ beschreiben dieselbe Person;
    die längere Schreibweise setzt sich als Anzeigename durch.
    """
    by_surname: dict[str, list[tuple[str, str]]] = defaultdict(list)
    for key in full_groups:
        by_surname[key[1]].append(key)

    for surname_keys in by_surname.values():
        if len(surname_keys) < 2:
            continue
        keys = sorted(surname_keys, key=lambda k: -len(full_groups[k]))
        for idx, base in enumerate(keys):
            if base not in full_groups:
                continue
            base_tokens = {part.lower() for ext, local in full_groups[base]
                           for p in local.name.split()[:-1] for part in re.split(r"[-\\s]+", p)}
            base_variants = {m.surface.lower() for _, local in full_groups[base]
                             for m in local.mentions if m.is_full_name}
            for other in keys[idx + 1:]:
                if other not in full_groups:
                    continue
                other_tokens = {part.lower() for ext, local in full_groups[other]
                                for p in local.name.split()[:-1] for part in re.split(r"[-\\s]+", p)}
                other_variants = {m.surface.lower() for _, local in full_groups[other]
                                  for m in local.mentions if m.is_full_name}
                if other_tokens and other_tokens <= base_tokens:
                    full_groups[base].extend(full_groups.pop(other))
                    continue
                # Schreibvariante, die im selben Artikel bereits als alternative
                # Form derselben Person belegt ist ("Stefan"/"Stephan Laszlo").
                if (other[-1].lower() in base_variants
                        or (" ".join(base).lower() in other_variants)):
                    full_groups[base].extend(full_groups.pop(other))
                    continue
                # Tippfehler im Vornamen („Luisa“/„Lusia“, „Stefan“/„Stephan“).
                if len(base_tokens) == 1 and len(other_tokens) == 1:
                    first_a = next(iter(base_tokens))
                    first_b = next(iter(other_tokens))
                    if (len(first_a) > 3 and len(first_b) > 3
                            and _osa_distance(first_a, first_b) <= 1):
                        full_groups[base].extend(full_groups.pop(other))


def _key_of(person: PersonInArticle) -> tuple[str, str]:
    parts = person.name.split()
    if len(parts) >= 2:
        return parts[0].lower(), parts[-1].lower()
    return "", person.surname.lower()


def resolve(extractions: list[ArticleExtraction]) -> list[Person]:
    """Führt alle artikel-lokalen Personengruppen zu globalen Personen zusammen."""
    entries: list[Entry] = [(ext, p) for ext in extractions for p in ext.persons]

    full_groups: dict[tuple[str, str], list[Entry]] = defaultdict(list)
    surname_only: list[Entry] = []
    for entry in entries:
        first, last = _key_of(entry[1])
        if first:
            full_groups[(first, last)].append(entry)
        else:
            surname_only.append(entry)

    # Tippvarianten des Nachnamens zusammenführen (gleicher Vorname, Distanz <= 1).
    keys = sorted(full_groups)
    for idx, (first_a, last_a) in enumerate(keys):
        if (first_a, last_a) not in full_groups:
            continue
        for first_b, last_b in keys[idx + 1:]:
            if (first_b, last_b) not in full_groups:
                continue
            if first_a != first_b or last_a == last_b:
                continue
            if abs(len(last_a) - len(last_b)) <= 1 and _osa_distance(last_a, last_b) <= 1:
                full_groups[(first_a, last_a)].extend(full_groups.pop((first_b, last_b)))

    _merge_subset_groups(full_groups)

    by_surname: dict[str, list[tuple[str, str]]] = defaultdict(list)
    for group_key in full_groups:
        by_surname[group_key[1]].append(group_key)

    unresolved: list[Entry] = []
    for entry in surname_only:
        surname = entry[1].surname.lower()
        candidates: set[tuple[str, str]] = set(by_surname.get(surname, []))
        if not candidates:
            for other, group_keys in by_surname.items():
                if abs(len(other) - len(surname)) <= 1 and _levenshtein(other, surname) <= 1:
                    candidates.update(group_keys)
        if len(candidates) == 1:
            full_groups[next(iter(candidates))].append(entry)
        elif len(candidates) > 1:
            # Mehrdeutig: nur bei klarer Dominanz zuordnen, sonst eigener Knoten.
            def weight(key: tuple[str, str]) -> int:
                return len({ext.article.id for ext, _ in full_groups[key]})

            ranked = sorted(candidates, key=weight, reverse=True)
            if weight(ranked[0]) >= 3 * max(1, weight(ranked[1])):
                full_groups[ranked[0]].append(entry)
            else:
                unresolved.append(entry)
        else:
            unresolved.append(entry)

    persons: list[Person] = []
    local_to_person: dict[int, Person] = {}
    for group in full_groups.values():
        person = _make_person(group)
        persons.append(person)
        for entry in group:
            local_to_person[id(entry[1])] = person
    for entry in unresolved:
        person = _make_person([entry], ambiguous=True)
        persons.append(person)
        local_to_person[id(entry[1])] = person

    _assign_unique_ids(persons)

    for ext in extractions:
        for local in ext.persons:
            person = local_to_person.get(id(local))
            if person is None:
                continue
            for mention in local.mentions:
                mention.person_key = person.id

    _attach_loose_mentions(persons, extractions)
    _compute_dates(persons, extractions)
    persons.sort(key=lambda p: (-p.article_count, -p.mentions, p.name))
    return persons


def _make_person(group: list[Entry], ambiguous: bool = False) -> Person:
    name_counts: Counter = Counter()
    person = Person(id="", name="", surname="", ambiguous=ambiguous)
    for ext, local in group:
        name_counts[local.name] += local.count
        person.variants[local.name] += local.count
        person.roles.update(local.roles)
        person.role_surfaces.update(local.role_surfaces)
        person.role_contexts.update(local.role_contexts)
        person.parties.update(local.parties)
        person.mentions += local.count
        if ext.article.id not in person.articles:
            person.articles.append(ext.article.id)
    # Mehrteilige Namen bevorzugen („Hans Peter Doskozil“ vor „Peter Doskozil“),
    # danach die häufigste Schreibweise.
    best = max(name_counts, key=lambda n: (len(n.split()), name_counts[n], len(n)))
    person.name = best
    person.surname = best.split()[-1]
    return person


def _assign_unique_ids(persons: list[Person]) -> None:
    seen: Counter = Counter()
    for person in sorted(persons, key=lambda p: p.name):
        base = T.slug(person.name) or "person"
        seen[base] += 1
        person.id = base if seen[base] == 1 else f"{base}-{seen[base]}"


def _attach_loose_mentions(persons: list[Person], extractions: list[ArticleExtraction]) -> None:
    """Ordnet reine Nachnamen-Nennungen („… sagte Doskozil“) global zu.

    Das gelingt nur, wenn der Nachname im gesamten Korpus zu genau einer Person
    mit vollem Namen gehört – sonst bliebe die Zuordnung Spekulation.
    """
    by_surname: dict[str, list[Person]] = defaultdict(list)
    for person in persons:
        if len(person.name.split()) >= 2:
            by_surname[person.surname.lower()].append(person)

    for ext in extractions:
        for mention in ext.loose:
            candidates = by_surname.get(mention.surface.lower(), [])
            if len(candidates) != 1:
                continue
            person = candidates[0]
            mention.person_key = person.id
            ext.mentions.append(mention)
            person.mentions += 1
            if ext.article.id not in person.articles:
                person.articles.append(ext.article.id)


def _compute_dates(persons: list[Person], extractions: list[ArticleExtraction]) -> None:
    dates: dict[str, str] = {}
    for ext in extractions:
        if ext.article.date:
            dates[ext.article.id] = ext.article.date
    for person in persons:
        seen = sorted(dates[a] for a in person.articles if a in dates)
        person.first_seen = seen[0] if seen else ""
        person.last_seen = seen[-1] if seen else ""
