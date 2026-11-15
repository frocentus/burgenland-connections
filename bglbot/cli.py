"""Kommandozeile: ``python run.py …``."""

from __future__ import annotations

import argparse
import json
import sys
import time
import webbrowser
from pathlib import Path

from . import config, pipeline


def _print_summary(graph: dict) -> None:
    meta = graph["meta"]
    print()
    print("=" * 72)
    print(f"  Artikel: {meta['articles_crawled']:>5}   "
          f"Personen: {meta['persons']:>4}   "
          f"Beziehungen: {meta['edges']:>4}   Nennungen: {meta['mentions']:>4}")
    print(f"  Zeitraum: {meta['date_from']} – {meta['date_to']}")
    print("=" * 72)

    names = {n["id"]: n["name"] for n in graph["nodes"]}
    print("\nHäufigste Personen:")
    for node in graph["nodes"][:12]:
        party = f" ({node['party']})" if node.get("party") else ""
        role = f" – {node['role']}" if node.get("role") else ""
        print(f"  {node['name']:<28}{party:<8} {node['articles']:>3} Artikel, "
              f"{node['degree']:>3} Beziehungen{role}")

    print("\nStärkste Beziehungen:")
    for edge in graph["edges"][:12]:
        signals = ", ".join(f"{k}:{v}" for k, v in sorted(edge["signals"].items()))
        print(f"  {names.get(edge['source'], '?'):<24} ↔ {names.get(edge['target'], '?'):<24} "
              f"{edge['weight']:>2} Artikel, {edge['sentences']:>2} Sätze "
              f"{('[' + signals + ']') if signals else ''}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="run.py",
        description="Scrapt burgenland.ORF.at, erkennt Personen und baut ein Beziehungsnetzwerk.",
    )
    parser.add_argument("--pages", type=int, default=15,
                        help="Startseiten-Seiten à ~10 Artikel (Standard: 15)")
    parser.add_argument("--limit", type=int, default=None,
                        help="Höchstzahl zu verarbeitender Artikel")
    parser.add_argument("--refresh", action="store_true",
                        help="HTTP-Cache ignorieren und neu laden")
    parser.add_argument("--wayback", type=int, default=0, metavar="N",
                        help="zusätzlich N Story-URLs aus dem Webarchiv (CDX-API) beziehen")
    parser.add_argument("--wiki-refresh", action="store_true",
                        help="Wikipedia-Zusammenfassungen neu abfragen (Cache in data/wiki.json)")
    parser.add_argument("--no-wiki", action="store_true",
                        help="Wikipedia-Anreicherung überspringen")
    parser.add_argument("--no-magazin", action="store_true",
                        help="Nur die Nachrichten-Startseite, ohne Magazin/Studio")
    parser.add_argument("--open", action="store_true",
                        help="Ergebnisgrafik nach dem Lauf im Browser öffnen")
    parser.add_argument("--report", action="store_true",
                        help="Nur den vorhandenen Graphen zusammenfassen")
    parser.add_argument("--rebuild", action="store_true",
                        help="Aus data/out/artikel.jsonl neu auswerten (ohne Crawling)")
    parser.add_argument("--holdout", action="store_true",
                        help="Goldstandard-Artikel vom Vornamen-Lernen ausnehmen (ehrliche Messung)")
    parser.add_argument("--incremental", action="store_true",
                        help="Nur neue Artikel laden und an den bestehenden Korpus anhängen")
    parser.add_argument("--out", type=Path, default=config.OUT_DIR,
                        help="Zielverzeichnis für Ergebnisse")
    args = parser.parse_args(argv)

    started = time.time()
    if args.report:
        path = args.out / "graph.json"
        if not path.exists():
            print(f"Kein Graph gefunden: {path}. Bitte zuerst ohne --report laufen lassen.")
            return 1
        _print_summary(json.loads(path.read_text(encoding="utf-8")))
        return 0

    print(f"burgenland.ORF.at – Scrape & Netzwerkanalyse (Ziel: {args.out})")
    graph = pipeline.run(
        pages=args.pages,
        sections=not args.no_magazin,
        limit=args.limit,
        refresh=args.refresh,
        wayback_urls=args.wayback,
        wiki_refresh=args.wiki_refresh,
        skip_wiki=args.no_wiki,
        rebuild=args.rebuild,
        incremental=args.incremental,
        holdout=args.holdout,
    )
    _print_summary(graph)
    print(f"\nFertig in {time.time() - started:.1f}s")
    html = args.out / "graph.html"
    print(f"Grafik: {html}")
    if args.open:
        webbrowser.open(html.resolve().as_uri())
    return 0


if __name__ == "__main__":
    sys.exit(main())
