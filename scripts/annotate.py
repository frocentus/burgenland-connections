"""Erzeugt eine statische Annotationsseite für den Goldstandard.

    python scripts/annotate.py --count 12

Erzeugt ``eval/annotate.html``: links der Artikeltext, rechts die vom Bot
erkannten Personen (anklickbar) plus ein Feld für fehlende Namen. Der Knopf
„Goldstandard exportieren“ lädt eine ``gold.json`` herunter, die nach
``eval/gold.json`` kopiert wird. Alles läuft lokal im Browser, es werden keine
Daten verschickt.
"""

from __future__ import annotations

import argparse
import json
import random
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from bglbot import config  # noqa: E402

TEMPLATE = """<!DOCTYPE html>
<html lang="de"><head><meta charset="utf-8"><title>Goldstandard annotieren</title>
<style>
 body{font:14px/1.5 "Segoe UI",sans-serif;background:#0d1117;color:#e6edf3;margin:0;padding:24px}
 h1{font-size:18px;margin:0 0 6px} .hint{color:#8b98a5;font-size:12.5px;margin-bottom:18px}
 article{border:1px solid #26303d;border-radius:10px;background:#151b24;padding:14px 16px;margin-bottom:16px}
 h2{font-size:15px;margin:0 0 4px} .meta{color:#8b98a5;font-size:12px;margin-bottom:10px}
 .text{background:#0f141b;border-radius:8px;padding:10px 12px;margin-bottom:10px;white-space:pre-wrap;font-size:13px}
 .people{display:flex;flex-wrap:wrap;gap:8px;margin-bottom:8px}
 label.p{background:#1b2430;border:1px solid #2d3a4a;border-radius:999px;padding:3px 10px;cursor:pointer;font-size:13px}
 label.p.ok{border-color:#2f6b4a;background:#16281f}
 input[type=text]{width:100%;padding:7px 9px;border-radius:7px;border:1px solid #2d3a4a;background:#0f141b;color:#e6edf3}
 button{background:#1b2430;color:#e6edf3;border:1px solid #2d3a4a;border-radius:8px;padding:9px 16px;font-size:14px;cursor:pointer}
 button:hover{border-color:#4da3ff}
 .bar{position:sticky;bottom:0;background:#0d1117;padding:12px 0;border-top:1px solid #26303d;margin-top:8px}
</style></head><body>
<h1>Goldstandard annotieren</h1>
<div class="hint">Personen anklicken, die im Artikel wirklich vorkommen. Fehlende Namen ins Textfeld (Komma-getrennt).
Am Ende exportieren und als <code>eval/gold.json</code> speichern.</div>
<div id="list"></div>
<div class="bar"><button id="export">Goldstandard exportieren (gold.json)</button>
 <span id="status" class="hint"></span></div>
<script>
const DATA = __DATA__;
const state = {};
const list = document.getElementById("list");
DATA.forEach(a => {
  state[a.id] = {keep: new Set(a.persons), extra: ""};
  const el = document.createElement("article");
  el.innerHTML = `<h2>${escapeHtml(a.title)}</h2>
    <div class="meta">${a.id} · ${a.date} · ${a.category || ""}</div>
    <div class="text">${escapeHtml(a.text)}</div>
    <div class="people"></div>
    <input type="text" placeholder="Fehlende Personen, mit Komma getrennt …">`;
  const people = el.querySelector(".people");
  a.persons.forEach(name => {
    const label = document.createElement("label");
    label.className = "p ok";
    label.textContent = name;
    label.onclick = () => {
      const keep = state[a.id].keep;
      if (keep.has(name)) { keep.delete(name); label.classList.remove("ok"); }
      else { keep.add(name); label.classList.add("ok"); }
    };
    people.appendChild(label);
  });
  el.querySelector("input").addEventListener("input", e => { state[a.id].extra = e.target.value; });
  list.appendChild(el);
});
function escapeHtml(s){ return String(s).replace(/[&<>"]/g, c => ({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;"}[c])); }
document.getElementById("export").onclick = () => {
  const articles = {};
  for (const [id, s] of Object.entries(state)){
    const names = [...s.keep];
    s.extra.split(",").map(x => x.trim()).filter(Boolean).forEach(n => names.push(n));
    articles[id] = names;
  }
  const blob = new Blob([JSON.stringify({notes: "manuell annotiert", articles}, null, 1)], {type: "application/json"});
  const link = document.createElement("a");
  link.href = URL.createObjectURL(blob);
  link.download = "gold.json";
  link.click();
  document.getElementById("status").textContent = " exportiert";
};
</script></body></html>
"""


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--count", type=int, default=12)
    parser.add_argument("--seed", type=int, default=7)
    parser.add_argument("--articles", type=Path, default=config.OUT_DIR / "artikel.jsonl")
    parser.add_argument("--out", type=Path, default=ROOT / "eval" / "annotate.html")
    args = parser.parse_args(argv)

    records = [json.loads(line) for line in args.articles.open(encoding="utf-8")]
    pool = [r for r in records if 2 <= len(r.get("personen", [])) <= 8
            and 400 < sum(len(p) for p in r["paragraphs"]) < 2200]
    random.Random(args.seed).shuffle(pool)
    picked = pool[:args.count]

    payload = [{
        "id": r["id"], "title": r["title"], "date": r.get("date", ""),
        "category": r.get("category", ""),
        "text": "\n\n".join([r.get("lead", ""), *r["paragraphs"]]).strip(),
        "persons": [p["name"] for p in r.get("personen", [])],
    } for r in picked]

    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(TEMPLATE.replace("__DATA__", json.dumps(payload, ensure_ascii=False)),
                        encoding="utf-8")
    print(f"{len(payload)} Artikel → {args.out}")
    print("Im Browser öffnen, annotieren, exportieren, nach eval/gold.json kopieren.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
