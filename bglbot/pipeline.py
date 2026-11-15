"""Ablaufsteuerung: crawlen → parsen → extrahieren → auflösen → Graph."""

from __future__ import annotations

import json
from pathlib import Path

from collections import Counter

from . import config, discover, gazetteer, graph as G, lexicon, parse, preview, render, resolve
from . import text
from . import wayback, wiki, wikidata
from .extract import ExtractionContext, extract_article
from .http import Fetcher, FetchError


def _article_text(article: parse.Article) -> str:
    return "\n".join([article.title, article.lead, *article.paragraphs, *article.captions])


def read_extra_urls(log=print) -> list[str]:
    """Artikel, die der Nutzer in ``data/extra_urls.txt`` ergänzt hat."""
    path = config.EXTRA_URLS
    if not path.exists():
        return []
    urls: list[str] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        normalized = discover.normalize(line)
        if normalized:
            urls.append(normalized)
    if urls:
        log(f"  Zusatz-URLs: {len(urls)} aus {path.name}")
    return urls


def crawl(fetcher: Fetcher, pages: int, sections: bool, wayback_urls: int = 0,
          wayback_seed: int = 0, log=print) -> list[str]:
    """Sammelt Story-URLs aus Startseite, Ressorts, RSS und optional dem Webarchiv."""
    urls = discover.discover(fetcher, pages=pages, include_sections=sections, log=log)
    if wayback_urls:
        log(f"  Wayback: frage CDX-Index ab (Ziel {wayback_urls} URLs) …")
        archive = wayback.discover(fetcher, max_urls=wayback_urls, seed=wayback_seed, log=log)
        seen = set(urls)
        added = [u for u in archive if u not in seen]
        log(f"  Wayback: +{len(added)} zusätzliche URLs")
        urls.extend(added)
    for url in read_extra_urls(log=log):
        if url not in urls:
            urls.append(url)
    return urls


def load_articles(fetcher: Fetcher, urls: list[str], limit: int | None = None,
                  log=print) -> list[parse.Article]:
    articles: list[parse.Article] = []
    errors = 0
    for idx, url in enumerate(urls, 1):
        if limit and len(articles) >= limit:
            break
        try:
            page = fetcher.get(url)
        except FetchError as exc:
            errors += 1
            if errors <= 5:
                log(f"  ! {url}: {exc}")
            continue
        article = parse.parse_article(page, url)
        if article and (article.paragraphs or article.lead):
            articles.append(article)
        if idx % 50 == 0:
            log(f"  ... {idx}/{len(urls)} geladen ({len(articles)} Artikel)")
    log(f"  {len(articles)} Artikel geladen, {errors} Fehler")
    return articles


def load_articles_from_jsonl(path: Path, log=print) -> list[parse.Article]:
    """Liest die zuletzt geparsten Artikel – schneller Rebuild ohne HTTP/HTML."""
    articles: list[parse.Article] = []
    with path.open(encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if not line:
                continue
            record = json.loads(line)
            record.pop("date", None)
            record.pop("personen", None)
            try:
                articles.append(parse.Article(**record))
            except TypeError:
                continue
    log(f"  {len(articles)} Artikel aus {path.name} geladen")
    return articles


def learn_first_names(articles: list[parse.Article], ctx, exclude: set[str] | None = None,
                      log=print) -> set[str]:
    """Lernt Vornamen aus „unbekanntes Wort + bestätigter Nachname“ im Korpus.

    ``exclude`` erlaubt eine Holdout-Messung: Die Artikel der Evaluationsstichprobe
    werden dann nicht zum Lernen verwendet.
    """
    exclude = exclude or set()
    baseline = [extract_article(article, ctx) for article in articles
                if article.id not in exclude]
    surnames = {person.surname.lower() for extraction in baseline
                for person in extraction.persons if len(person.name.split()) >= 2}
    learned: Counter = Counter()
    for article in articles:
        if article.id in exclude:
            continue
        for block in (article.title, article.lead, *article.paragraphs, *article.captions):
            for sentence in text.split_sentences(block):
                tokens = text.tokenize(sentence)
                for index in range(len(tokens) - 1):
                    candidate, following = tokens[index].text, tokens[index + 1].text
                    if following.lower() not in surnames:
                        continue
                    if not (text.is_name_token(following) and text.is_name_token(candidate)):
                        continue
                    first = candidate.lower()
                    if len(first) < 3 or lexicon.is_generic(first) or first in ctx.geo:
                        continue
                    learned[first] += 1
    ctx.extra_first_names = {name for name, hits in learned.items() if hits >= 2}
    if ctx.extra_first_names:
        log(f"  Vornamen gelernt: {len(ctx.extra_first_names)} "
            f"(z. B. {', '.join(sorted(ctx.extra_first_names)[:5])})")
    return ctx.extra_first_names


def analyse(articles: list[parse.Article], log=print, wiki_refresh: bool = False,
            holdout_ids: set[str] | None = None):
    texts = [_article_text(a) for a in articles]
    learned = gazetteer.learn(texts)
    ctx = ExtractionContext(geo=gazetteer.combine(learned),
                            common_nouns=gazetteer.learn_common_nouns(texts))
    log(f"  Gazetteer: {len(ctx.geo)} Ortsnamen (davon {len(learned)} aus dem Korpus gelernt)")

    # Erster Durchlauf: bestätigte Nachnamen sammeln. Danach im gesamten Text
    # nach "unbekanntes Wort + bekannter Nachname" suchen – das sind fast immer
    # Vornamen ("Nikolaus Berlakovich", auch wenn "Nikolaus" in keiner Liste steht).
    learn_first_names(articles, ctx, exclude=holdout_ids, log=log)

    extractions = [extract_article(article, ctx) for article in articles]
    with_persons = [ext for ext in extractions if ext.persons]
    persons = resolve.resolve(with_persons)
    log(f"  {len(persons)} Personen, "
        f"{sum(len(e.mentions) for e in with_persons)} Nennungen in "
        f"{len(with_persons)} von {len(extractions)} Artikeln")
    client = wiki.WikiClient(refresh=wiki_refresh, log=log)
    wiki_data = client.enrich(persons, log=log)
    with_wiki = sum(1 for person in persons if wiki_data.get(person.name))
    log(f"  Wikipedia: {with_wiki} Personen mit Artikel")

    wd_client = wikidata.WikidataClient(log=log)
    wd_data = wd_client.enrich({name: entry for name, entry in wiki_data.items() if entry}, log=log)
    with_wd = sum(1 for person in persons if wd_data.get(person.name))
    log(f"  Wikidata: {with_wd} Personen mit Partei/Ämtern")
    return extractions, persons, wiki_data, wd_data


def write_outputs(extractions, persons, out_dir: Path = config.OUT_DIR, log=print,
                  wiki_data: dict | None = None, wikidata_data: dict | None = None) -> dict:
    out_dir.mkdir(parents=True, exist_ok=True)
    graph_data = G.build_graph(extractions, persons, wiki=wiki_data, wikidata=wikidata_data)
    G.write_json(graph_data, out_dir / "graph.json")
    G.write_csv(graph_data, out_dir / "personen.csv", out_dir / "beziehungen.csv")
    G.write_graphml(graph_data, out_dir / "graph.graphml")

    articles_path = out_dir / "artikel.jsonl"
    with articles_path.open("w", encoding="utf-8") as fh:
        for ext in extractions:
            record = ext.article.to_dict()
            record["personen"] = [
                {
                    "name": p.name,
                    "funktion": p.role_label,
                    "partei": p.party,
                    "nennungen": p.count,
                }
                for p in ext.persons
            ]
            fh.write(json.dumps(record, ensure_ascii=False) + "\n")

    html_path = render.render_html(graph_data, out_dir / "graph.html")
    try:
        preview.render_png(graph_data, out_dir / "netzwerk.png")
        preview_note = ", netzwerk.png"
    except Exception as exc:  # noqa: BLE001 - Vorschau ist optional
        preview_note = f" (PNG-Vorschau fehlgeschlagen: {exc})"
    log(f"  geschrieben: {html_path.name}, graph.json, personen.csv, "
        f"beziehungen.csv, graph.graphml, artikel.jsonl{preview_note}")
    return graph_data


def run(pages: int = 15, sections: bool = True, limit: int | None = None,
        refresh: bool = False, wayback_urls: int = 0, wiki_refresh: bool = False,
        skip_wiki: bool = False, rebuild: bool = False, incremental: bool = False,
        holdout: bool = False, wayback_seed: int = 0, log=print) -> dict:
    config.ensure_dirs()
    if rebuild:
        # Schneller Pfad: bereits geparste Artikel + zwischengespeicherte
        # Wikipedia-Daten, ohne Crawler und ohne 1.300 HTML-Dateien.
        source = config.OUT_DIR / "artikel.jsonl"
        if not source.exists():
            raise SystemExit(f"Kein {source} – bitte zuerst einen normalen Lauf machen.")
        articles = load_articles_from_jsonl(source, log=log)
        known = {article.url for article in articles}
        extras = [url for url in read_extra_urls(log=log) if url not in known]
        if extras:
            fetcher = Fetcher()
            for url in extras:
                try:
                    parsed = parse.parse_article(fetcher.get(url), url)
                except FetchError as exc:
                    log(f"  ! Zusatz-URL {url}: {exc}")
                    continue
                if parsed:
                    articles.append(parsed)
            log(f"  {len(extras)} Zusatz-Artikel ergänzt")
    else:
        fetcher = Fetcher(refresh=refresh)
        urls = crawl(fetcher, pages, sections, wayback_urls=wayback_urls,
                     wayback_seed=wayback_seed, log=log)
        existing: list[parse.Article] = []
        if incremental and (config.OUT_DIR / "artikel.jsonl").exists():
            existing = load_articles_from_jsonl(config.OUT_DIR / "artikel.jsonl", log=log)
            known = {article.id for article in existing}
            before = len(urls)
            urls = [url for url in urls
                    if parse.story_id_from_url(url) not in known]
            log(f"  inkrementell: {len(known)} Artikel bekannt, {len(urls)} neu "
                f"(von {before} URLs)")
        new_articles = load_articles(fetcher, urls, limit=limit, log=log)
        articles = existing + new_articles
        if incremental:
            log(f"  Korpus: {len(articles)} Artikel ({len(new_articles)} neu)")
    holdout_ids: set[str] = set()
    if holdout:
        gold_path = config.ROOT / "eval" / "gold.json"
        if gold_path.exists():
            holdout_ids = set(json.loads(gold_path.read_text(encoding="utf-8"))["articles"])
            log(f"  Holdout: {len(holdout_ids)} Artikel nicht zum Lernen verwendet")
    if skip_wiki:
        extractions, persons, _ = analyse(articles, log=log, holdout_ids=holdout_ids)
        wiki_data, wd_data = {}, {}
    else:
        extractions, persons, wiki_data, wd_data = analyse(articles, log=log,
                                                           wiki_refresh=wiki_refresh,
                                                           holdout_ids=holdout_ids)
    graph_data = write_outputs(extractions, persons, log=log, wiki_data=wiki_data,
                               wikidata_data=wd_data)
    if not rebuild:
        graph_data["fetch_stats"] = fetcher.stats
    return graph_data
