"""Gütemessung der Personenerkennung gegen einen Goldstandard.

Ohne Vergleich mit einer manuell geprüften Stichprobe bleibt jede Regeländerung
Bauchgefühl. Der Goldstandard liegt als ``eval/gold.json`` im Repository:

    {"articles": {"<story-id>": ["Vorname Nachname", ...]}, "notes": "..."}

Gemessen werden Precision (wie viele erkannte Personen sind richtig) und Recall
(wie viele der tatsächlichen Personen wurden gefunden), je Artikel und insgesamt.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from . import config
from .extract import ExtractionContext, extract_article
from .parse import Article


def normalize(name: str) -> str:
    return " ".join(name.lower().replace("-", " ").split())


def evaluate(articles: list[Article], gold: dict[str, list[str]],
             ctx: ExtractionContext) -> dict:
    rows = []
    totals = {"tp": 0, "fp": 0, "fn": 0}
    by_id = {article.id: article for article in articles}
    for article_id, expected in gold.items():
        article = by_id.get(article_id)
        if article is None:
            rows.append({"id": article_id, "missing": True, "tp": 0, "fp": 0, "fn": len(expected)})
            totals["fn"] += len(expected)
            continue
        result = extract_article(article, ctx)
        found = {normalize(person.name) for person in result.persons}
        wanted = {normalize(name) for name in expected}
        tp = len(found & wanted)
        fp = sorted(found - wanted)
        fn = sorted(wanted - found)
        totals["tp"] += tp
        totals["fp"] += len(fp)
        totals["fn"] += len(fn)
        rows.append({"id": article_id, "title": article.title, "tp": tp,
                     "fp": fp, "fn": fn, "found": sorted(found), "wanted": sorted(wanted)})
    precision = totals["tp"] / (totals["tp"] + totals["fp"]) if totals["tp"] + totals["fp"] else 0.0
    recall = totals["tp"] / (totals["tp"] + totals["fn"]) if totals["tp"] + totals["fn"] else 0.0
    f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
    return {"rows": rows, "totals": totals,
            "precision": round(precision, 3), "recall": round(recall, 3), "f1": round(f1, 3)}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m bglbot.evaluate")
    parser.add_argument("--gold", type=Path, default=config.ROOT / "eval" / "gold.json")
    parser.add_argument("--articles", type=Path, default=config.OUT_DIR / "artikel.jsonl")
    parser.add_argument("--verbose", action="store_true")
    args = parser.parse_args(argv)

    gold = json.loads(args.gold.read_text(encoding="utf-8"))["articles"]
    articles: list[Article] = []
    with args.articles.open(encoding="utf-8") as handle:
        for line in handle:
            record = json.loads(line)
            record.pop("date", None)
            record.pop("personen", None)
            articles.append(Article(**record))

    from . import gazetteer
    texts = [a.title + "\n" + a.lead + "\n" + "\n".join(a.paragraphs) for a in articles]
    ctx = ExtractionContext(geo=gazetteer.combine(gazetteer.learn(texts)),
                            common_nouns=gazetteer.learn_common_nouns(texts))
    result = evaluate(articles, gold, ctx)

    print(f"Goldstandard: {len(gold)} Artikel")
    for row in result["rows"]:
        if row.get("missing"):
            print(f"  {row['id']}: nicht im Korpus")
            continue
        if args.verbose or row["fp"] or row["fn"]:
            print(f"  {row['id']} {row['title'][:40]:<40} tp={row['tp']} "
                  f"fp={row['fp']} fn={row['fn']}")
    print(f"\nPrecision {result['precision']:.3f} · Recall {result['recall']:.3f} "
          f"· F1 {result['f1']:.3f} (tp={result['totals']['tp']}, "
          f"fp={result['totals']['fp']}, fn={result['totals']['fn']})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
