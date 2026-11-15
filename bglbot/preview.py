"""Statische Vorschau des Netzwerks als PNG (ohne Browser)."""

from __future__ import annotations

import math
from pathlib import Path

# numpy/Pillow sind optional: ohne sie läuft die Auswertung weiter, nur die
# PNG-Vorschau entfällt. Deshalb wird erst in render_png importiert.

SENTI_COLORS = {
    "feindselig": (255, 86, 86), "negativ": (255, 150, 94), "gemischt": (214, 178, 70),
    "positiv": (86, 214, 140), "neutral": (159, 182, 204),
}

PARTY_COLORS = {
    "SPÖ": (255, 77, 90), "ÖVP": (63, 208, 201), "FPÖ": (77, 141, 255),
    "Grüne": (126, 217, 87), "NEOS": (255, 110, 199), "KPÖ": (192, 80, 77),
}
CATEGORY_COLORS = {
    "politik": (255, 138, 92), "verwaltung": (108, 196, 161),
    "sicherheit": (126, 166, 240), "wirtschaft": (217, 192, 107),
    "justiz": (176, 139, 217), "kirche": (201, 183, 160),
    "bildung": (143, 211, 244), "gesundheit": (242, 139, 168),
    "sport": (154, 211, 107), "organisation": (169, 180, 194),
    "kultur": (224, 163, 255), "sonstiges": (154, 167, 180),
}
BG = (13, 17, 23)


def _color(node: dict) -> tuple[int, int, int]:
    if node.get("party") in PARTY_COLORS:
        return PARTY_COLORS[node["party"]]
    return CATEGORY_COLORS.get(node.get("role_category") or "", (140, 152, 165))


def _layout(nodes: list[dict], edges: list[dict], iterations: int = 1200):
    import numpy as np

    n = len(nodes)
    rng = np.random.default_rng(7)
    pos = rng.normal(0, 260, size=(n, 2))
    index = {node["id"]: i for i, node in enumerate(nodes)}
    src = np.array([index[e["source"]] for e in edges], dtype=int)
    dst = np.array([index[e["target"]] for e in edges], dtype=int)
    weights = np.array([min(4.0, 1 + math.log1p(e["weight"])) for e in edges])

    for step in range(iterations):
        alpha = max(0.02, 1 - step / iterations)
        delta = pos[:, None, :] - pos[None, :, :]
        dist2 = np.einsum("ijk,ijk->ij", delta, delta)
        np.fill_diagonal(dist2, np.inf)
        dist2 = np.maximum(dist2, 25.0)
        force = delta / (dist2 ** 1.5)[:, :, None] * 24000 * alpha
        disp = force.sum(axis=1)
        # Federn
        if len(src):
            d = pos[dst] - pos[src]
            length = np.maximum(np.linalg.norm(d, axis=1), 1.0)
            target = 130 + 45 * weights
            pull = (length - target)[:, None] / length[:, None] * d * 0.30 * weights[:, None]
            np.add.at(disp, src, pull)
            np.add.at(disp, dst, -pull)
        disp -= pos * 0.004 * alpha
        pos += np.clip(disp, -25, 25)

    pos -= pos.mean(axis=0)
    return pos


def _font(size: int):
    from PIL import ImageFont
    for name in ("segoeuib.ttf", "segoeui.ttf", "arialbd.ttf", "arial.ttf"):
        try:
            return ImageFont.truetype(name, size)
        except OSError:
            continue
    return ImageFont.load_default()


def render_png(graph: dict, path: Path, width: int = 2000, height: int = 1300,
               min_weight: int = 1, min_articles: int = 3, max_nodes: int = 45) -> Path:
    nodes = [n for n in graph["nodes"] if n["articles"] >= min_articles]
    nodes.sort(key=lambda n: (-n["articles"], -n["degree"]))
    nodes = nodes[:max_nodes]
    keep = {n["id"] for n in nodes}
    edges = [e for e in graph["edges"]
             if e["weight"] >= min_weight and e["source"] in keep and e["target"] in keep]
    # Personen ohne sichtbare Beziehung weglassen (außer sehr präsente).
    linked = {e["source"] for e in edges} | {e["target"] for e in edges}
    nodes = [n for n in nodes if n["id"] in linked]
    if not nodes:
        raise ValueError("Keine Knoten für die Vorschau")

    import numpy as np
    from PIL import Image, ImageDraw

    pos = _layout(nodes, edges)
    pos -= pos.min(axis=0)
    span_x, span_y = max(np.ptp(pos[:, 0]), 1.0), max(np.ptp(pos[:, 1]), 1.0)
    pad_x, pad_y = 220, 190
    # Achsen getrennt skalieren: füllt die Fläche und entzerrt dichte Cluster.
    scale_x = (width - 2 * pad_x) / span_x
    scale_y = (height - 2 * pad_y) / span_y
    xy = np.column_stack([pad_x + (pos[:, 0] - pos[:, 0].min()) * scale_x,
                          pad_y + (pos[:, 1] - pos[:, 1].min()) * scale_y])
    index = {n["id"]: i for i, n in enumerate(nodes)}

    img = Image.new("RGB", (width, height), BG)
    draw = ImageDraw.Draw(img, "RGBA")

    for e in edges:
        a, b = xy[index[e["source"]]], xy[index[e["target"]]]
        label = (e.get("sentiment") or {}).get("label", "neutral")
        rgb = SENTI_COLORS.get(label, SENTI_COLORS["neutral"])
        alpha = int(min(190, (70 if label != "neutral" else 45) + e["weight"] * 20))
        draw.line([tuple(a), tuple(b)], fill=rgb + (alpha,), width=1 + min(3, e["weight"] // 2))

    font = _font(19)
    small = _font(16)
    radius = {}
    for node in nodes:
        radius[node["id"]] = 7 + math.sqrt(node["articles"]) * 4 + min(9, node["mentions"] * 0.3)
    for node in nodes:                       # Knoten
        x, y = xy[index[node["id"]]]
        r = radius[node["id"]]
        draw.ellipse([x - r, y - r, x + r, y + r], fill=_color(node) + (255,),
                     outline=(255, 255, 255, 180), width=1)

    placed: list[tuple[float, float, float, float]] = []
    label_order = sorted(nodes, key=lambda n: (-n["articles"], -n["degree"]))
    labelled = {n["id"] for n in label_order[:12]}
    for node in label_order:                 # Labels
        if node["id"] not in labelled:
            continue
        x, y = xy[index[node["id"]]]
        r = radius[node["id"]]
        if True:
            label = node["name"]
            f = font if node["articles"] >= 5 else small
            bbox = draw.textbbox((0, 0), label, font=f)
            tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
            box = (x - tw / 2 - 4, y + r + 2, x + tw / 2 + 4, y + r + th + 8)
            if any(not (box[2] < p[0] or box[0] > p[2] or box[3] < p[1] or box[1] > p[3])
                   for p in placed):
                continue
            placed.append(box)
            draw.rectangle(list(box), fill=(8, 12, 18, 205))
            draw.text((x - tw / 2, y + r + 3), label, font=f, fill=(232, 240, 248))

    meta = graph["meta"]
    title_font = _font(28)
    draw.text((38, 30), "Personennetzwerk burgenland.ORF.at", font=title_font, fill=(235, 242, 250))
    draw.text((38, 70),
              f"{meta['articles_crawled']} Artikel · {meta['persons']} Personen · "
              f"{meta['edges']} Beziehungen · {meta['date_from']} – {meta['date_to']}",
              font=small, fill=(150, 165, 180))
    draw.text((38, height - 44),
              f"Knoten: {len(nodes)} Personen (≥{min_articles} Artikel) · "
              f"Kanten: {len(edges)} Beziehungen (≥{min_weight} gemeinsame Artikel) · "
              "Knotenfarbe = Partei/Funktion · Kantenfarbe = Beziehungston",
              font=small, fill=(130, 145, 160))

    path.parent.mkdir(parents=True, exist_ok=True)
    img.save(path)
    return path
