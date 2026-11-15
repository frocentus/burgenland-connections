"""Erzeugt die interaktive HTML-Grafik (eine Datei, ohne CDN-Abhängigkeiten)."""

from __future__ import annotations

import json
from pathlib import Path

TEMPLATE = Path(__file__).resolve().parent / "templates" / "graph.html"


def render_html(graph: dict, path: Path) -> Path:
    template = TEMPLATE.read_text(encoding="utf-8")
    payload = json.dumps(graph, ensure_ascii=False, separators=(",", ":"))
    # Verhindert ein vorzeitiges Schließen des <script>-Tags durch Inhalte.
    payload = payload.replace("</", "<\\/")
    html = template.replace("__DATA__", payload)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(html, encoding="utf-8")
    return path
