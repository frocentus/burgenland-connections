"""burgenland-connections – Scraping- und Auswertungs-Bot für burgenland.ORF.at.

Das Paket ist in vier Stufen gegliedert:

1. ``discover``  – findet Artikel-URLs (Startseiten-Paginierung, RSS, Themen-Links)
2. ``parse``     – zerlegt eine Artikelseite in Titel, Lead, Body, Tags, Datum
3. ``extract``   – erkennt Personen, Funktionen und Ko-Erwähnungen (Regel-basiertes NER)
4. ``graph``     – aggregiert Personen und Beziehungen, exportiert JSON/CSV/HTML
"""

__version__ = "0.1.0"
