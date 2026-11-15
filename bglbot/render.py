"""Erzeugt die interaktive HTML-Grafik.

Die Seite besteht aus vier Dateien, damit der Browser Daten und Code getrennt
zwischenspeichern kann: ``index.html`` (Hülle), ``app.js`` (Logik),
``d3.v7.min.js`` (Layout) und ``graph.json`` (Daten). d3 liegt im Repository,
es wird nichts von einem CDN geladen.
"""

from __future__ import annotations

import json
import shutil
from pathlib import Path

TEMPLATE_DIR = Path(__file__).resolve().parent / "templates"
TEMPLATE = TEMPLATE_DIR / "graph.html"
APP = TEMPLATE_DIR / "app.js"
VENDOR = Path(__file__).resolve().parent / "vendor" / "d3.v7.min.js"


def render_html(graph: dict, path: Path) -> Path:
    """Schreibt index.html, app.js, d3.v7.min.js und graph.json in ein Verzeichnis."""
    out_dir = path.parent
    out_dir.mkdir(parents=True, exist_ok=True)

    # Daten als eigene Datei: Der Browser kann sie getrennt cachen.
    (out_dir / "graph.json").write_text(
        json.dumps(graph, ensure_ascii=False, separators=(",", ":")), encoding="utf-8"
    )
    shutil.copy2(APP, out_dir / "app.js")
    shutil.copy2(VENDOR, out_dir / "d3.v7.min.js")

    index = path if path.suffix == ".html" else out_dir / "index.html"
    index.write_text(TEMPLATE.read_text(encoding="utf-8"), encoding="utf-8")
    return index
