"""Veröffentlicht die lokal erzeugte Auswertung über GitHub Pages.

Das Crawling passiert ausschließlich lokal (voller Umfang, ohne Zeitlimit).
Dieses Skript packt die fertige Seite, lädt sie als Asset eines Releases mit
dem festen Tag ``data`` hoch und stößt den Deploy-Workflow an. Damit bleibt das
Repository frei von generierten Daten und ORF-Inhalten, während GitHub Pages
immer den letzten lokalen Stand zeigt.

Voraussetzungen: ``gh`` ist installiert und angemeldet (``gh auth login``),
das Repository ist ``origin``.
"""

from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
import zipfile
from pathlib import Path

from . import config

RELEASE_TAG = "data"
RELEASE_TITLE = "Aktuelle Auswertung (burgenland.ORF.at)"
SITE_FILES = {
    "index.html": "index.html",
    "app.js": "app.js",
    "d3.v7.min.js": "d3.v7.min.js",
    "graph.json": "graph.json",
    "personen.csv": "personen.csv",
    "beziehungen.csv": "beziehungen.csv",
    "netzwerk.png": "netzwerk.png",
}


def _run(command: list[str], *, cwd: Path | None = None, check: bool = True) -> int:
    """Führt ein Kommando aus, ohne dessen Ausgabe abzufangen (stdio geerbt)."""
    print("  $", " ".join(command))
    result = subprocess.run(command, cwd=str(cwd) if cwd else None)
    if check and result.returncode != 0:
        raise SystemExit(f"Fehlgeschlagen ({result.returncode}): {' '.join(command)}")
    return result.returncode


def build_site(out_dir: Path, site_dir: Path) -> Path:
    """Kopiert die Ausgabedateien in eine Web-Struktur und zippt sie."""
    if not (out_dir / "index.html").exists():
        raise SystemExit(
            f"{out_dir / 'index.html'} fehlt – bitte zuerst 'python run.py' ausführen."
        )
    if site_dir.exists():
        shutil.rmtree(site_dir)
    site_dir.mkdir(parents=True)
    copied = []
    for source, target in SITE_FILES.items():
        path = out_dir / source
        if path.exists():
            shutil.copy2(path, site_dir / target)
            copied.append(f"{target} ({path.stat().st_size / 1024:.0f} KB)")
    print("  Seite zusammengestellt:", ", ".join(copied))

    archive = out_dir / "site.zip"
    with zipfile.ZipFile(archive, "w", compression=zipfile.ZIP_DEFLATED) as bundle:
        for path in sorted(site_dir.iterdir()):
            bundle.write(path, arcname=path.name)
    print(f"  Archiv: {archive} ({archive.stat().st_size / 1024:.0f} KB)")
    return archive


def publish(archive: Path, *, deploy: bool = True, repo: str | None = None,
            log=print) -> None:
    """Lädt das Archiv als Release-Asset hoch und startet den Deploy."""
    base = ["gh", "release"]
    if repo:
        base += ["--repo", repo]

    existing = subprocess.run(
        [*base, "view", RELEASE_TAG], stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    if existing.returncode != 0:
        _run([*base, "create", RELEASE_TAG, "--title", RELEASE_TITLE,
              "--notes", "Rollierendes Release mit der zuletzt lokal erzeugten "
                         "Auswertung. Wird von publish.py ersetzt."])
    _run([*base, "upload", RELEASE_TAG, str(archive), "--clobber"])

    if deploy:
        workflow = ["gh", "workflow", "run", "pages.yml"]
        if repo:
            workflow += ["--repo", repo]
        _run(workflow)
        log("  Deploy angestoßen – Status: gh run list")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="python publish.py",
        description="Lokale Auswertung als GitHub-Pages-Seite veröffentlichen.",
    )
    parser.add_argument("--out", type=Path, default=config.OUT_DIR,
                        help="Ausgabeverzeichnis der Auswertung")
    parser.add_argument("--repo", default=None,
                        help="Repository (Standard: origin des Arbeitsverzeichnisses)")
    parser.add_argument("--no-deploy", action="store_true",
                        help="nur hochladen, Workflow nicht starten")
    args = parser.parse_args(argv)

    print("Veröffentlichung der lokalen Auswertung")
    archive = build_site(args.out, config.DATA_DIR / "site")
    publish(archive, deploy=not args.no_deploy, repo=args.repo)
    print("Fertig.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
