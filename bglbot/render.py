"""Erzeugt die interaktive HTML-Grafik (eine Datei, ohne CDN-Abhängigkeiten)."""

from __future__ import annotations

import json
from pathlib import Path

TEMPLATE = Path(__file__).resolve().parent / "templates" / "graph.html"


VENDOR = Path(__file__).resolve().parent / "vendor" / "d3.v7.min.js"


def render_html(graph: dict, path: Path) -> Path:
    template = TEMPLATE.read_text(encoding="utf-8")
    payload = json.dumps(graph, ensure_ascii=False, separators=(",", ":"))
    # Verhindert ein vorzeitiges Schließen des <script>-Tags durch Inhalte.
    payload = payload.replace("</", "<\\/")
    # d3-force wird eingebettet statt vom CDN geladen: Die Seite bleibt
    # eigenständig und funktioniert auch offline.
    d3 = VENDOR.read_text(encoding="utf-8") if VENDOR.exists() else ""
    html = template.replace("__D3__", d3).replace("__DATA__", payload)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(html, encoding="utf-8")
    return path
