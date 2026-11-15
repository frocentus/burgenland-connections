"""Aufbau des Personen-Beziehungsgraphen und Export der Daten."""

from __future__ import annotations

import csv
import datetime as dt
import json
import re
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from xml.sax.saxutils import escape

from . import lexicon
from .extract import ArticleExtraction, _build_window_pairs
from .resolve import Person


@dataclass
class Edge:
    a: str
    b: str
    articles: set[str] = field(default_factory=set)
    sentences: int = 0
    windows: int = 0
    signals: Counter = field(default_factory=Counter)
    examples: list[dict] = field(default_factory=list)
    positive: float = 0.0
    negative: float = 0.0
    hostile: int = 0
    sentiment_sentences: int = 0
    direction: Counter = field(default_factory=Counter)

    @property
    def weight(self) -> int:
        return len(self.articles)

    @property
    def dominant_signal(self) -> str | None:
        return self.signals.most_common(1)[0][0] if self.signals else None

    @property
    def sentiment_label(self) -> str:
        return _sentiment_label(self.positive, self.negative, self.hostile)

    @property
    def sentiment_score(self) -> float:
        if self.sentiment_label == "neutral":
            return 0.0        # zu wenig Belege für eine Aussage
        total = self.positive + self.negative
        if total <= 0:
            return 0.0
        return round((self.positive - self.negative) / total, 3)

    @property
    def direction_tendency(self) -> str | None:
        if not self.direction:
            return None
        (key, count), = self.direction.most_common(1)
        return f"{key}:{count}"


def _article_meta(ext: ArticleExtraction) -> dict:
    a = ext.article
    return {
        "id": a.id,
        "title": a.title,
        "date": a.date,
        "url": a.url,
        "category": a.category,
    }


def _signals_in(sentence_lower: str) -> list[str]:
    return [name for name, cues in lexicon.RELATION_CUES.items()
            if any(cue in sentence_lower for cue in cues)]


#: Mindestintensität, damit ein Signalwort überhaupt zählt. Schwache Marker wie
#: "Gespäch" oder "gemeinsam" sind als Beleg für Sympathie zu unspezifisch.
MIN_CUE_WEIGHT = 0.45
MIN_EVIDENCE_WEIGHT = 0.45

#: Wortgrenzen-Matching verhindert Treffer in Komposita ("angelobt" -> "lobt",
#: "Wettstreit" -> "streit").
#: Deutsche Verben werden gebeugt ("lobt", "lobte", "gelobt"); die Endung wird
#: mitgematcht, die Wortgrenzen bleiben aber erhalten.
_INFLECTION = r"(?:e|en|et|est|st|t|te|ten|test)?"

_CUE_PATTERNS: list[tuple[str, str, float, re.Pattern[str]]] = [
    (category, cue, weight,
     re.compile(rf"(?<![a-zäöüß]){re.escape(cue)}{_INFLECTION}(?![a-zäöüß])", re.IGNORECASE))
    for category, cues in lexicon.SENTIMENT_CUES.items()
    for cue, weight in cues
    if weight >= MIN_CUE_WEIGHT
]


#: Negationen im Vorfeld eines Signalworts kippen die Polarität
#: („nicht zufrieden“, „Zusammenarbeit ausgeschlossen“).
NEGATION_RE = re.compile(
    r"\b(nicht|kein|keine|keinen|keinem|keiner|niemals|nie|ohne|ausgeschlossen|"
    r"verweigert|absage|ablehnung)\b",
    re.IGNORECASE,
)


#: Verneinungen, die dem Signalwort nachfolgen ("Zusammenarbeit ausgeschlossen").
FORWARD_NEGATION_RE = re.compile(
    r"\b(ausgeschlossen|gescheitert|geplatzt|abgelehnt|zurückgewiesen|"
    r"nicht\s+zustande|keine\s+einigung)\b",
    re.IGNORECASE,
)


def _negated(sentence_lower: str, position: int, cue_length: int = 0) -> bool:
    window = sentence_lower[max(0, position - 60):position]
    if re.search(r"nicht\s+nur\b", window):
        return False          # "nicht nur gelungen" ist keine Verneinung
    if NEGATION_RE.search(window):
        return True
    after = sentence_lower[position + cue_length:position + cue_length + 70]
    return bool(FORWARD_NEGATION_RE.search(after))


def _sentiment_in(sentence_lower: str) -> dict[str, tuple[str, float]]:
    """Stärkster Sentiment-Treffer je Kategorie (max. ein Treffer pro Kategorie)."""
    hits: dict[str, tuple[str, float]] = {}
    for category, cue, weight, pattern in _CUE_PATTERNS:
        match = pattern.search(sentence_lower)
        if not match:
            continue
        polarity, value = category, weight
        if _negated(sentence_lower, match.start(), len(match.group(0))):
            if category in ("positiv", "kooperativ"):
                polarity, value = "negativ", round(weight * 0.9, 2)
            else:
                continue      # "nicht kritisiert" ist kein Konfliktbeleg
        if value > hits.get(polarity, ("", 0.0))[1]:
            hits[polarity] = (cue, value)
    return hits


def _sentiment_label(positive: float, negative: float, hostile: int) -> str:
    total = positive + negative
    if total < MIN_EVIDENCE_WEIGHT:
        return "neutral"          # ein einzelnes schwaches Signal genügt nicht
    ratio = (positive - negative) / total
    if hostile >= 2 or (hostile >= 1 and ratio <= -0.25):
        return "feindselig"
    if ratio <= -0.34:
        return "negativ"
    if ratio >= 0.34:
        return "positiv"
    return "gemischt"


#: Verben, bei denen sich Akteur und Adressat im Satz zuordnen lassen.
DIRECTION_VERB_RE = re.compile(
    r"\b(kritisiert|attackiert|beschuldigt|beschimpft|diffamiert|lobt|würdigt|dankt|"
    r"gratuliert|unterstützt|verteidigt|wirft|kontert|widerspricht|beglückwünscht)\b",
    re.IGNORECASE,
)


#: Parteinamen, die als Angriffsziel in Frage kommen ("Kritik an der ÖVP").
_TARGET_PARTIES = (
    ("SPÖ", ("spö", "sozialdemokraten", "sozialdemokratie", "roten")),
    ("ÖVP", ("övp", "volkspartei", "türkisen", "schwarzen")),
    ("FPÖ", ("fpö", "freiheitlichen", "blauen")),
    ("Grüne", ("grüne", "grünen")),
    ("NEOS", ("neos", "pinken")),
    ("Bundesregierung", ("bundesregierung", "regierung")),
    ("Opposition", ("opposition",)),
)


def _parties_in(sentence_lower: str) -> list[str]:
    found = []
    for party, aliases in _TARGET_PARTIES:
        if any(re.search(rf"(?<![a-zäöüß]){re.escape(alias)}(?![a-zäöüß])", sentence_lower)
               for alias in aliases):
            found.append(party)
    return found


#: Mindestbeleg für eine Tonlagen-Aussage (ein einzelnes Signalwort genügt nicht).
MIN_TONE_EVIDENCE = 0.7


def _tone_label(positive: float, negative: float) -> str:
    total = positive + negative
    if total < MIN_TONE_EVIDENCE:
        return "zu wenig Belege"
    ratio = positive / total
    if ratio <= 0.25:
        return "überwiegend kritisch"
    if ratio <= 0.42:
        return "eher kritisch"
    if ratio >= 0.75:
        return "überwiegend zustimmend"
    if ratio >= 0.58:
        return "eher zustimmend"
    return "ausgewogen"


def _direction_of(sentence: str, positions: dict[str, int]) -> str | None:
    """Heuristik: Wer handelt, wer ist Adressat?

    Nächstgelegene Person vor dem Verb = Akteur, danach = Adressat. Bei
    Passivkonstruktionen („wurde von X kritisiert“) wird getauscht.
    """
    if len(positions) < 2:
        return None
    # Anker ist die Stelle des Signalworts, nicht ein festes Verb: auch
    # „richtete seine Kritik an …“ ist damit zuordenbar.
    anchor = None
    for category, cue, weight, pattern in _CUE_PATTERNS:
        found = pattern.search(sentence)
        if found:
            anchor = found.start()
            break
    if anchor is None:
        match = DIRECTION_VERB_RE.search(sentence)
        if not match:
            return None
        anchor = match.start()
    verb = anchor
    before = [(pid, pos) for pid, pos in positions.items() if pos < verb]
    after = [(pid, pos) for pid, pos in positions.items() if pos >= verb]
    if not before or not after:
        return None
    actor = max(before, key=lambda item: item[1])[0]
    target = min(after, key=lambda item: item[1])[0]
    if re.search(r"\bwurde\b[^.]{0,60}\bvon\b", sentence[:verb], re.IGNORECASE):
        actor, target = target, actor
    if actor == target:
        return None
    return f"{actor}>{target}"



def edge_list_sentiment(edge_list: list[dict]) -> list[str]:
    return [(e.get("sentiment") or {}).get("label", "neutral") for e in edge_list]


def build_graph(extractions: list[ArticleExtraction], persons: list[Person],
                wiki: dict[str, dict] | None = None) -> dict:
    by_id = {p.id: p for p in persons}
    edges: dict[tuple[str, str], Edge] = {}
    articles_meta: dict[str, dict] = {}
    person_articles: dict[str, list[dict]] = defaultdict(list)
    co_article_count: Counter = Counter()
    tone: dict[str, dict] = defaultdict(lambda: {
        "positive": 0.0, "negative": 0.0, "critical": 0, "praising": 0,
        "parties": Counter(), "examples": [],
    })

    def edge(a: str, b: str) -> Edge:
        key = (a, b) if a < b else (b, a)
        if key not in edges:
            edges[key] = Edge(a=key[0], b=key[1])
        return edges[key]

    for ext in extractions:
        meta = _article_meta(ext)
        articles_meta[ext.article.id] = meta
        pids = sorted({m.person_key for m in ext.mentions if m.person_key})
        if not pids:
            continue
        for pid in pids:
            co_article_count[pid] += 1
            if meta not in person_articles[pid]:
                person_articles[pid].append(meta)

        for i, a in enumerate(pids):
            for b in pids[i + 1:]:
                edges_key = edge(a, b)
                edges_key.articles.add(ext.article.id)

        for a, b in ext.sentence_pairs:
            e = edge(a, b)
            e.sentences += 1
        for a, b in _build_window_pairs(ext.mentions, len(ext.sentences)):
            edge(a, b).windows += 1

        # Beziehungssignale und Sentiment aus Sätzen mit gemeinsamer Nennung
        for idx, sentence in enumerate(ext.sentences):
            mentions = [m for m in ext.mentions if m.sentence == idx and m.person_key]
            present = sorted({m.person_key for m in mentions})
            if not present:
                continue
            lower = sentence.lower()
            signals = _signals_in(lower)
            sentiment = _sentiment_in(lower)
            if not signals and not sentiment:
                continue

            cues = [cue for cue, _w in sentiment.values()]
            label = _sentiment_label(
                sum(max(0.0, lexicon.SENTIMENT_WEIGHT[cat] * w) for cat, (_c, w) in sentiment.items()),
                sum(max(0.0, -lexicon.SENTIMENT_WEIGHT[cat] * w) for cat, (_c, w) in sentiment.items()),
                sum(1 for cat in sentiment if cat == "feindselig"),
            ) if sentiment else "neutral"

            # Personen-Tonalität: unabhängig vom Gegenüber, denn Kritik richtet
            # sich oft an Parteien oder Institutionen statt an Einzelpersonen.
            if sentiment:
                tone_parties = _parties_in(lower)
                for pid in present:
                    entry = tone[pid]
                    # Die eigene Partei ist kein Angriffsziel (meist Verteidigung).
                    own = by_id[pid].party if pid in by_id else None
                    targets = [party for party in tone_parties if party != own]
                    for cat, (_cue, w) in sentiment.items():
                        signed = lexicon.SENTIMENT_WEIGHT[cat] * w
                        if signed >= 0:
                            entry["positive"] += signed
                        else:
                            entry["negative"] += -signed
                    has_neg = any(lexicon.SENTIMENT_WEIGHT[c] < 0 for c in sentiment)
                    has_pos = any(lexicon.SENTIMENT_WEIGHT[c] > 0 for c in sentiment)
                    if has_neg:
                        entry["critical"] += 1
                        for party in targets:
                            entry["parties"][party] += 1
                    if has_pos and not has_neg:
                        entry["praising"] += 1
                    if len(entry["examples"]) < 3:
                        entry["examples"].append({
                            "sentence": sentence[:260],
                            "article": meta["title"],
                            "date": meta["date"],
                            "label": label,
                            "cues": cues,
                        })

            if len(present) < 2:
                continue
            positions: dict[str, int] = {}
            for mention in mentions:
                positions.setdefault(mention.person_key, mention.start)
            direction = _direction_of(sentence, positions) if sentiment else None
            for i, a in enumerate(present):
                for b in present[i + 1:]:
                    e = edge(a, b)
                    for sig in signals:
                        e.signals[sig] += 1
                    if sentiment:
                        e.sentiment_sentences += 1
                        for cat, (_cue, weight) in sentiment.items():
                            signed = lexicon.SENTIMENT_WEIGHT[cat] * weight
                            if signed >= 0:
                                e.positive += signed
                            else:
                                e.negative += -signed
                            if cat == "feindselig":
                                e.hostile += 1
                        if direction:
                            e.direction[direction] += 1
                    if len(e.examples) < 3:
                        e.examples.append({
                            "article": meta["title"],
                            "date": meta["date"],
                            "url": meta["url"],
                            "sentence": sentence[:400],
                            "signals": signals,
                            "sentiment": label,
                            "cues": cues,
                        })

    # Schwächere Evidenz: Signalwort im Absatzumfeld (±2 Sätze), halbe Gewichtung.
    # In Nachrichten steht die Wertung oft in einem Satz, der nur einen der
    # beiden Namen nennt.
    for ext in extractions:
        mentions = [m for m in ext.mentions if m.person_key]
        if not mentions:
            continue
        per_sentence: dict[int, set[str]] = defaultdict(set)
        for mention in mentions:
            per_sentence[mention.sentence].add(mention.person_key)
        total_sentences = len(ext.sentences)
        for idx, sentence in enumerate(ext.sentences):
            sentiment = _sentiment_in(sentence.lower())
            anchors = per_sentence.get(idx, set())
            if not sentiment or not anchors:
                continue
            nearby: set[str] = set()
            for j in range(max(0, idx - 2), min(total_sentences, idx + 3)):
                nearby |= per_sentence.get(j, set())
            if len(nearby) < 2:
                continue
            label = _sentiment_label(
                sum(max(0.0, lexicon.SENTIMENT_WEIGHT[cat] * w) for cat, (_c, w) in sentiment.items()),
                sum(max(0.0, -lexicon.SENTIMENT_WEIGHT[cat] * w) for cat, (_c, w) in sentiment.items()),
                sum(1 for cat in sentiment if cat == "feindselig"),
            )
            for a in anchors:
                for b in nearby:
                    if a == b or b in anchors:
                        continue      # Paar im selben Satz bereits gezählt
                    e = edge(a, b)
                    e.sentiment_sentences += 1
                    for cat, (cue, weight) in sentiment.items():
                        signed = lexicon.SENTIMENT_WEIGHT[cat] * weight * 0.45
                        if signed >= 0:
                            e.positive += signed
                        else:
                            e.negative += -signed
                        if cat == "feindselig":
                            e.hostile += 1
                    if len(e.examples) < 3:
                        e.examples.append({
                            "article": ext.article.title,
                            "date": ext.article.date,
                            "url": ext.article.url,
                            "sentence": sentence[:400],
                            "signals": _signals_in(sentence.lower()),
                            "sentiment": label,
                            "cues": [cue for cue, _w in sentiment.values()],
                            "context": "Absatzumfeld",
                        })

    # Beispielsätze auch ohne Signalwörter nachliefern.
    for ext in extractions:
        pids = {m.person_key for m in ext.mentions if m.person_key}
        if len(pids) < 2:
            continue
        for idx, sentence in enumerate(ext.sentences):
            present = sorted({m.person_key for m in ext.mentions
                              if m.sentence == idx and m.person_key})
            for i, a in enumerate(present):
                for b in present[i + 1:]:
                    e = edge(a, b)
                    if len(e.examples) < 3:
                        e.examples.append({
                            "article": ext.article.title,
                            "date": ext.article.date,
                            "url": ext.article.url,
                            "sentence": sentence[:400],
                            "signals": _signals_in(sentence.lower()),
                        })

    nodes = []
    degree: Counter = Counter()
    for e in edges.values():
        degree[e.a] += 1
        degree[e.b] += 1

    for person in persons:
        pid = person.id
        neighbours = [e for e in edges.values() if pid in (e.a, e.b)]
        top = sorted(neighbours, key=lambda e: (-e.weight, -e.sentences))[:5]
        data = person.to_dict()
        data["wikipedia"] = (wiki or {}).get(person.name) or None
        entry = tone.get(pid) or {"positive": 0.0, "negative": 0.0, "critical": 0,
                                  "praising": 0, "parties": Counter(), "examples": []}
        total = entry["positive"] + entry["negative"]
        data["tone"] = {
            "label": _tone_label(entry["positive"], entry["negative"]),
            "score": round((entry["positive"] - entry["negative"]) / total, 2) if total else 0.0,
            "positive": round(entry["positive"], 2),
            "negative": round(entry["negative"], 2),
            "critical": entry["critical"],
            "praising": entry["praising"],
            "parties": [{"party": k, "count": v} for k, v in entry["parties"].most_common(4)],
            "examples": entry["examples"][:2],
        }
        neighbours_all = [e for e in edges.values() if pid in (e.a, e.b)]
        data.update({
            "degree": degree[pid],
            "conflict_edges": sum(1 for e in neighbours_all
                                  if e.sentiment_label in ("feindselig", "negativ")),
            "positive_edges": sum(1 for e in neighbours_all
                                  if e.sentiment_label in ("positiv", "gemischt") and e.sentiment_label != "gemischt"),
            "co_articles": co_article_count[pid],
            "top_partners": [
                {"id": (e.b if e.a == pid else e.a), "weight": e.weight} for e in top
            ],
            "article_list": sorted(person_articles[pid], key=lambda m: m["date"],
                                   reverse=True)[:40],
        })
        nodes.append(data)

    edge_list = []
    for e in edges.values():
        if not e.articles:
            continue
        edge_list.append({
            "source": e.a,
            "target": e.b,
            "weight": e.weight,
            "sentences": e.sentences,
            "windows": e.windows,
            "signals": dict(e.signals),
            "dominant_signal": e.dominant_signal,
            "sentiment": {
                "label": e.sentiment_label,
                "score": e.sentiment_score,
                "positive": round(e.positive, 2),
                "negative": round(e.negative, 2),
                "hostile": e.hostile,
                "evidence": round(e.positive + e.negative, 2),
                "sentences": e.sentiment_sentences,
                "direction": dict(e.direction),
            },
            "articles": sorted(e.articles)[:24],
            "examples": e.examples[:2],
        })
    edge_list.sort(key=lambda x: (-x["weight"], -x["sentences"]))

    dates = sorted(m["date"] for m in articles_meta.values() if m.get("date"))
    meta = {
        "generated": dt.datetime.now().isoformat(timespec="seconds"),
        "source": "https://burgenland.orf.at/",
        "articles_crawled": len(articles_meta),
        "articles_with_persons": 0,
        "persons": len(nodes),
        "edges": len(edge_list),
        "mentions": sum(n["mentions"] for n in nodes),
        "date_from": dates[0] if dates else "",
        "date_to": dates[-1] if dates else "",
        "categories": dict(Counter(m.get("category") or "Chronik"
                                   for m in articles_meta.values()).most_common()),
    }
    # Klar getrennt: Artikel mit mindestens einer Person vs. mit mindestens
    # einer Beziehung (zwei Personen im selben Artikel).
    meta["articles_with_persons"] = len({ext.article.id for ext in extractions if ext.persons})
    meta["articles_with_relations"] = len({aid for e in edges.values() for aid in e.articles})
    meta["sentiment"] = dict(Counter(edge_list_sentiment(edge_list)))

    return {
        "meta": meta,
        "nodes": nodes,
        "edges": edge_list,
        "articles": articles_meta,
        "parties": sorted({n["party"] for n in nodes if n["party"]}),
        "roles": sorted({n["role"] for n in nodes if n["role"]}),
    }


# --------------------------------------------------------------------------
# Exporte
# --------------------------------------------------------------------------
def write_json(graph: dict, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(graph, ensure_ascii=False, indent=1), encoding="utf-8")


def write_csv(graph: dict, nodes_path: Path, edges_path: Path) -> None:
    nodes_path.parent.mkdir(parents=True, exist_ok=True)
    with nodes_path.open("w", encoding="utf-8-sig", newline="") as fh:
        writer = csv.writer(fh, delimiter=";")
        writer.writerow(["id", "name", "funktion", "partei", "artikel", "nennungen",
                         "grad", "erste_nennung", "letzte_nennung", "konfidenz",
                         "funktionskontext", "varianten", "tonlage", "ton_score",
                         "kritische_belege", "zustimmende_belege", "angriffsziele",
                         "wikipedia_titel", "wikipedia_url"])
        for n in graph["nodes"]:
            tone = n.get("tone") or {}
            targets = ", ".join(f"{t['party']} ({t['count']})" for t in tone.get("parties", []))
            writer.writerow([
                n["id"], n["name"], n.get("role") or "", n.get("party") or "",
                n["articles"], n["mentions"], n["degree"], n["first_seen"],
                n["last_seen"], n["confidence"], n.get("role_context") or "",
                " | ".join(n.get("variants", [])), tone.get("label", ""),
                tone.get("score", 0), tone.get("critical", 0), tone.get("praising", 0),
                targets, (n.get("wikipedia") or {}).get("title", ""),
                (n.get("wikipedia") or {}).get("url", ""),
            ])
    with edges_path.open("w", encoding="utf-8-sig", newline="") as fh:
        writer = csv.writer(fh, delimiter=";")
        writer.writerow(["person_a", "person_b", "gemeinsame_artikel", "gemeinsame_saetze",
                         "benachbarte_saetze", "beziehungssignale", "sentiment",
                         "sentiment_score", "positiv", "negativ", "feindselig", "tendenz"])
        names = {n["id"]: n["name"] for n in graph["nodes"]}
        for e in graph["edges"]:
            signals = ", ".join(f"{k}:{v}" for k, v in sorted(e["signals"].items()))
            senti = e.get("sentiment") or {}
            direction = ", ".join(f"{k}:{v}" for k, v in sorted((senti.get("direction") or {}).items()))
            writer.writerow([names.get(e["source"], e["source"]),
                             names.get(e["target"], e["target"]),
                             e["weight"], e["sentences"], e["windows"], signals,
                             senti.get("label", "neutral"), senti.get("score", 0),
                             senti.get("positive", 0), senti.get("negative", 0),
                             senti.get("hostile", 0), direction])


def write_graphml(graph: dict, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        '<graphml xmlns="http://graphml.graphdrawing.org/xmlns">',
        '  <key id="label" for="node" attr.name="label" attr.type="string"/>',
        '  <key id="role" for="node" attr.name="role" attr.type="string"/>',
        '  <key id="party" for="node" attr.name="party" attr.type="string"/>',
        '  <key id="articles" for="node" attr.name="articles" attr.type="int"/>',
        '  <key id="weight" for="edge" attr.name="weight" attr.type="int"/>',
        '  <key id="signals" for="edge" attr.name="signals" attr.type="string"/>',
        '  <key id="sentiment" for="edge" attr.name="sentiment" attr.type="string"/>',
        '  <graph id="burgenland" edgedefault="undirected">',
    ]
    for n in graph["nodes"]:
        lines.append(f'    <node id="{escape(n["id"])}">')
        lines.append(f'      <data key="label">{escape(n["name"])}</data>')
        lines.append(f'      <data key="role">{escape(n.get("role") or "")}</data>')
        lines.append(f'      <data key="party">{escape(n.get("party") or "")}</data>')
        lines.append(f'      <data key="articles">{n["articles"]}</data>')
        lines.append("    </node>")
    for e in graph["edges"]:
        signals = ", ".join(f"{k}:{v}" for k, v in sorted(e["signals"].items()))
        lines.append(f'    <edge source="{escape(e["source"])}" target="{escape(e["target"])}">')
        lines.append(f'      <data key="weight">{e["weight"]}</data>')
        lines.append(f'      <data key="signals">{escape(signals)}</data>')
        senti = e.get("sentiment") or {}
        lines.append(f'      <data key="sentiment">{escape(str(senti.get("label", "neutral")))}</data>')
        lines.append("    </edge>")
    lines.append("  </graph>")
    lines.append("</graphml>")
    path.write_text("\n".join(lines), encoding="utf-8")
