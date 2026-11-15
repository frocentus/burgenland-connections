#!/usr/bin/env python3
"""Veröffentlicht die lokal erzeugte Auswertung: ``python publish.py``.

Das Crawling läuft nur lokal (``python run.py --pages 45 --wayback 1200``).
Dieses Skript lädt das Ergebnis als Release-Asset hoch und startet den
GitHub-Actions-Deploy nach GitHub Pages.
"""

import sys

from bglbot.publish import main

if __name__ == "__main__":
    sys.exit(main())
