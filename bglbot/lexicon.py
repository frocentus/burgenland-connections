"""Sprachressourcen für die Personen- und Funktionserkennung.

Die Listen sind bewusst als editierbare Python-Daten gehalten: Wer den Bot auf
eine andere Region oder Redaktion umstellt, ergänzt hier Vokabular, ohne die
Erkennungslogik anzufassen.
"""

from __future__ import annotations

import re

from dataclasses import dataclass


@dataclass(frozen=True)
class Role:
    canonical: str      # stabile ID, z. B. "landeshauptmann"
    label: str          # Anzeigeform, z. B. "Landeshauptfrau"
    category: str       # politik | verwaltung | sicherheit | wirtschaft | ...
    rank: int = 50      # kleiner = prominenter (für die Auswahl der Hauptfunktion)


#: Oberfläche (klein geschrieben) -> Rolle. Mehrwortformen sind erlaubt.
ROLE_SURFACES: dict[str, Role] = {}


def _role(*surfaces: str, canonical: str, label: str, category: str, rank: int = 50) -> None:
    for surface in surfaces:
        ROLE_SURFACES[surface] = Role(canonical, label, category, rank)


# --- Landespolitik -------------------------------------------------------
_role("landeshauptmann", "landeshauptfrau", "landeshauptmanns",
      canonical="landeshauptmann", label="Landeshauptmann/-frau", category="politik", rank=1)
_role("landeshauptmann-stellvertreter", "landeshauptmann-stellvertreterin",
      "landeshauptfrau-stellvertreterin", "lh-stellvertreter", "lh-stellvertreterin",
      # Schreibweisen ohne Bindestrich (in Fließtexten üblich)
      "landeshauptmannstellvertreter", "landeshauptmannstellvertreterin",
      "landeshauptfraustellvertreterin", "landeshauptmannstellvertreters",
      canonical="lh-stellvertreter", label="Landeshauptmann-Stellvertreter/in", category="politik", rank=3)
_role("landesrat", "landesrätin", "landesräte",
      canonical="landesrat", label="Landesrat/Landesrätin", category="politik", rank=4)
_role("landesregierungsmitglied", "regierungsmitglied",
      canonical="landesregierung", label="Regierungsmitglied", category="politik", rank=8)
_role("landtagspräsident", "landtagspräsidentin",
      canonical="landtagspräsident", label="Landtagspräsident/in", category="politik", rank=5)
_role("landtagsabgeordneter", "landtagsabgeordnete", "landtagsabgeordneten",
      canonical="landtagsabgeordneter", label="Landtagsabgeordnete/r", category="politik", rank=12)
_role("landtagsklubobmann", "landtagsklubobfrau", "klubobmann", "klubobfrau", "klubchef", "klubchefin",
      "klubobmannstellvertreter", "klubobfraustellvertreterin",
      canonical="klubobmann", label="Klubobmann/Klubobfrau", category="politik", rank=10)
_role("parteichef", "parteichefin", "parteiobmann", "parteiobfrau",
      canonical="parteivorsitzender", label="Parteivorsitzende/r", category="politik", rank=9)
_role("parteivorsitzender", "parteivorsitzende", "landesparteivorsitzender",
      "landesparteivorsitzende", "landesparteiobmann", "landesparteiobfrau",
      "landesparteichef", "landesparteichefin",
      canonical="parteivorsitzender", label="Parteivorsitzende/r", category="politik", rank=6)
_role("spitzenkandidat", "spitzenkandidatin",
      canonical="spitzenkandidat", label="Spitzenkandidat/in", category="politik", rank=20)

# --- Bundesebene ---------------------------------------------------------
_role("bundeskanzler", "bundeskanzlerin", "kanzler", "kanzlerin",
      canonical="bundeskanzler", label="Bundeskanzler/in", category="politik", rank=2)
_role("vizekanzler", "vizekanzlerin",
      canonical="vizekanzler", label="Vizekanzler/in", category="politik", rank=4)
_role("bundesminister", "bundesministerin", "minister", "ministerin",
      canonical="minister", label="Minister/in", category="politik", rank=5)
_role("staatssekretär", "staatssekretärin",
      canonical="staatssekretär", label="Staatssekretär/in", category="politik", rank=10)
_role("nationalrat", "nationalrätin", "nationalratsabgeordneter", "nationalratsabgeordnete",
      canonical="nationalrat", label="Nationalrat/Nationalrätin", category="politik", rank=15)
_role("bundesrat", "bundesrätin",
      canonical="bundesrat", label="Bundesrat/Bundesrätin", category="politik", rank=25)
_role("abgeordneter", "abgeordnete", "abgeordneten",
      canonical="abgeordneter", label="Abgeordnete/r", category="politik", rank=22)

# --- Gemeinde ------------------------------------------------------------
_role("bürgermeister", "bürgermeisterin", "buergermeister", "buergermeisterin",
      canonical="bürgermeister", label="Bürgermeister/in", category="verwaltung", rank=7)
_role("vizebürgermeister", "vizebürgermeisterin",
      canonical="vizebürgermeister", label="Vizebürgermeister/in", category="verwaltung", rank=11)
_role("ortschef", "ortschefin", "stadtchef", "stadtchefin", "dorfchef", "dorfchefin",
      canonical="bürgermeister", label="Ortschef/in", category="verwaltung", rank=13)
_role("gemeinderat", "gemeinderätin", "gemeinderäte",
      canonical="gemeinderat", label="Gemeinderat/Gemeinderätin", category="verwaltung", rank=30)
_role("stadtrat", "stadträtin", "stadträte",
      canonical="stadtrat", label="Stadtrat/Stadträtin", category="verwaltung", rank=18)
_role("gemeindevorstand", "gemeindevorständin", "ortsvorsteher", "ortsvorsteherin",
      canonical="gemeindevorstand", label="Gemeindevorstand", category="verwaltung", rank=35)

# --- Verwaltung / Behörden ----------------------------------------------
_role("amtsleiter", "amtsleiterin", "gemeindeamtsleiter",
      canonical="amtsleiter", label="Amtsleiter/in", category="verwaltung", rank=40)
_role("bezirkshauptmann", "bezirkshauptfrau", "bezirkshauptleute",
      canonical="bezirkshauptmann", label="Bezirkshauptmann/-frau", category="verwaltung", rank=14)
_role("landesamtsdirektor", "landesamtsdirektorin",
      canonical="landesamtsdirektor", label="Landesamtsdirektor/in", category="verwaltung", rank=16)
_role("sektionschef", "sektionschefin", "sektionsleiter", "sektionsleiterin",
      canonical="sektionschef", label="Sektionschef/in", category="verwaltung", rank=28)
_role("abteilungsleiter", "abteilungsleiterin", "referatsleiter", "referatsleiterin",
      canonical="abteilungsleiter", label="Abteilungsleiter/in", category="verwaltung", rank=45)

# --- Sicherheit / Einsatz -----------------------------------------------
_role("polizeikommandant", "polizeikommandantin", "bezirkspolizeikommandant",
      "bezirkspolizeikommandantin", "stadtpolizeikommandant",
      canonical="polizeikommandant", label="Polizeikommandant/in", category="sicherheit", rank=24)
_role("landespolizeidirektor", "landespolizeidirektorin",
      canonical="landespolizeidirektor", label="Landespolizeidirektor/in", category="sicherheit", rank=17)
_role("feuerwehrkommandant", "feuerwehrkommandantin", "abschnittskommandant",
      "abschnittskommandantin", "ortsfeuerwehrkommandant", "bezirksfeuerwehrkommandant",
      "landesfeuerwehrkommandant", "landesfeuerwehrkommandantin",
      canonical="feuerwehrkommandant", label="Feuerwehrkommandant/in", category="sicherheit", rank=26)
_role("einsatzleiter", "einsatzleiterin", "einsatzoffizier",
      canonical="einsatzleiter", label="Einsatzleiter/in", category="sicherheit", rank=32)
_role("kommandant", "kommandantin",
      canonical="kommandant", label="Kommandant/in", category="sicherheit", rank=34)

# --- Justiz --------------------------------------------------------------
_role("richter", "richterin", "staatsanwalt", "staatsanwältin",
      canonical="richter", label="Richter/in bzw. Staatsanwalt/-anwältin", category="justiz", rank=38)
_role("rechtsanwalt", "rechtsanwältin", "verteidiger", "verteidigerin", "anwalt", "anwältin",
      canonical="rechtsanwalt", label="Rechtsanwalt/-anwältin", category="justiz", rank=42)
_role("notar", "notarin",
      canonical="notar", label="Notar/in", category="justiz", rank=60)

# --- Wirtschaft ----------------------------------------------------------
_role("geschäftsführer", "geschäftsführerin", "geschaeftsfuehrer",
      canonical="geschäftsführer", label="Geschäftsführer/in", category="wirtschaft", rank=27)
_role("vorstandsvorsitzender", "vorstandsvorsitzende", "vorstandschef", "vorstandschefin",
      canonical="vorstandsvorsitzender", label="Vorstandsvorsitzende/r", category="wirtschaft", rank=23)
_role("vorstand", "vorständin", "vorstandsdirektor", "vorstandsdirektorin",
      canonical="vorstand", label="Vorstand", category="wirtschaft", rank=30)
_role("direktor", "direktorin",
      canonical="direktor", label="Direktor/in", category="wirtschaft", rank=31)
_role("prokurist", "prokuristin", "unternehmer", "unternehmerin", "eigentümer", "eigentümerin",
      canonical="unternehmer", label="Unternehmer/in", category="wirtschaft", rank=44)
_role("betriebsrat", "betriebsrätin", "betriebsratsvorsitzender", "betriebsratsvorsitzende",
      canonical="betriebsrat", label="Betriebsrat/Betriebsrätin", category="wirtschaft", rank=48)
_role("filialleiter", "filialleiterin", "geschäftsleiter", "geschäftsleiterin",
      canonical="geschäftsführer", label="Geschäftsleiter/in", category="wirtschaft", rank=44)

# --- Kirche / Bildung / Gesundheit --------------------------------------
_role("pfarrer", "pfarrerin", "pfarrmoderator", "diakon", "diakonin",
      canonical="pfarrer", label="Pfarrer/in", category="kirche", rank=33)
_role("bischof", "bischöfin", "erzbischof", "erzbischöfin", "abt", "äbtissin",
      canonical="bischof", label="Bischof/Bischöfin", category="kirche", rank=21)
_role("rektor", "rektorin", "schulleiter", "schulleiterin", "direktorin", "klassenvorstand",
      canonical="schulleiter", label="Schulleiter/in", category="bildung", rank=36)
_role("professor", "professorin", "hochschulprofessor",
      canonical="professor", label="Professor/in", category="bildung", rank=40)
_role("arzt", "ärztin", "chefarzt", "chefärztin", "oberarzt", "oberärztin", "primar", "primaria",
      canonical="arzt", label="Arzt/Ärztin", category="gesundheit", rank=37)
_role("pflegedirektor", "pflegedirektorin", "krankenhausdirektor", "krankenhausdirektorin",
      canonical="pflegedirektor", label="Pflegedirektion", category="gesundheit", rank=39)

# --- Sport ---------------------------------------------------------------
_role("trainer", "trainerin", "cheftrainer", "cheftrainerin",
      canonical="trainer", label="Trainer/in", category="sport", rank=29)
_role("sportdirektor", "sportdirektorin", "sportlicher leiter", "sportliche leiterin",
      canonical="sportdirektor", label="Sportdirektor/in", category="sport", rank=33)
_role("kapitän", "kapitänin", "mannschaftskapitän", "mannschaftskapitänin",
      canonical="kapitän", label="Kapitän/in", category="sport", rank=44)
_role("spieler", "spielerin", "torwart", "torhüter", "torschütze", "torschützin",
      canonical="spieler", label="Spieler/in", category="sport", rank=52)

# --- Organisationen / Vereine / Kultur ----------------------------------
_role("obmann", "obfrau", "vereinsobmann", "vereinsobfrau", "obmann-stellvertreter",
      "obfrau-stellvertreterin",
      canonical="obmann", label="Obmann/Obfrau", category="organisation", rank=19)
_role("präsident", "präsidentin", "ehrenpräsident", "ehrenpräsidentin",
      canonical="präsident", label="Präsident/in", category="organisation", rank=15)
_role("vizepräsident", "vizepräsidentin",
      canonical="vizepräsident", label="Vizepräsident/in", category="organisation", rank=20)
_role("sprecher", "sprecherin", "pressesprecher", "pressesprecherin",
      "redakteur", "redakteurin", "chefredakteur", "chefredakteurin",
      "journalist", "journalistin", "moderator", "moderatorin",
      canonical="sprecher", label="Sprecher/in bzw. Redaktion", category="organisation", rank=41)
_role("intendant", "intendantin", "festivalleiter", "festivalleiterin",
      "museumsleiter", "museumsleiterin", "kurator", "kuratorin",
      canonical="kultureinrichtung", label="Kulturinstitution (Leitung)", category="kultur", rank=40)
_role("dirigent", "dirigentin", "musiker", "musikerin", "sänger", "sängerin",
      "schauspieler", "schauspielerin", "regisseur", "regisseurin",
      "autor", "autorin", "schriftsteller", "schriftstellerin",
      "kabarettist", "kabarettistin",
      canonical="kultur", label="Kulturschaffende/r", category="kultur", rank=46)
_role("filmemacher", "filmemacherin", "kameramann", "kamerafrau",
      "drehbuchautor", "drehbuchautorin", "produzent", "produzentin",
      "dokumentarfilmer", "dokumentarfilmerin", "fotograf", "fotografin",
      canonical="filmemacher", label="Filmschaffende/r", category="kultur", rank=36)
_role("architekt", "architektin", "botschafter", "botschafterin",
      "moderator", "moderatorin", "hotelier", "gastronom", "gastronomin",
      "gastwirt", "gastwirtin", "designer", "designerin", "bildhauer",
      "bildhauerin", "maler", "malerin",
      canonical="beruf", label="Berufsbezeichnung", category="organisation", rank=50)
_role("kapellmeister", "kapellmeisterin", "bezirkskapellmeister",
      "landeskapellmeister", "stabführer", "chorleiter", "chorleiterin",
      "musikpädagoge", "musikpädagogin", "komponist", "komponistin",
      canonical="kapellmeister", label="Kapellmeister/in bzw. Musikleitung",
      category="kultur", rank=38)
_role("blasmusikobmann", "blasmusikobfrau", "bezirksobmann", "bezirksobfrau",
      "landesobmann", "landesobfrau", "vereinsobmann", "vereinsobfrau",
      "ehrenobmann", "ehrenobfrau", "jugendreferent", "jugendreferentin",
      canonical="obmann", label="Obmann/Obfrau", category="organisation", rank=25)
_role("landwirt", "landwirtin", "bergbauer", "bergbäuerin", "winzer", "winzerin",
      "gärtner", "gärtnerin", "bäcker", "bäckerin", "fleischhauer",
      "tischler", "tischlerin", "installateur", "elektriker", "mechaniker",
      canonical="beruf", label="Berufsbezeichnung", category="wirtschaft", rank=60)
_role("physiotherapeut", "physiotherapeutin", "hebamme", "notfallsanitäter",
      "notfallsanitäterin", "apotheker", "apothekerin", "tierarzt", "tierärztin",
      "ordensschwester", "superior", "diakon", "diakonin",
      canonical="gesundheitsberuf", label="Gesundheits-/Pflegeberuf",
      category="gesundheit", rank=55)
_role("polizist", "polizistin", "offizier", "offizierin", "soldat", "soldatin",
      "justizwachebeamter", "justizwachebeamtin", "zollbeamter",
      canonical="sicherheitsberuf", label="Sicherheitsberuf", category="sicherheit", rank=55)
_role("projektleiter", "projektleiterin", "koordinator", "koordinatorin",
      canonical="projektleiter", label="Projekt-/Prozessleitung", category="organisation", rank=47)

#: Abkürzungen werden exakt (Groß-/Kleinschreibung) gematcht.
ACRONYM_ROLES: dict[str, Role] = {
    "LH": ROLE_SURFACES["landeshauptmann"],
    "LH-Stv.": ROLE_SURFACES["landeshauptmann-stellvertreter"],
    "LR": ROLE_SURFACES["landesrat"],
    "LAbg.": ROLE_SURFACES["landtagsabgeordneter"],
    "LTAbg.": ROLE_SURFACES["landtagsabgeordneter"],
    "Bgm.": ROLE_SURFACES["bürgermeister"],
    "Bgm": ROLE_SURFACES["bürgermeister"],
    "Vbgm.": ROLE_SURFACES["vizebürgermeister"],
    "NR": ROLE_SURFACES["nationalrat"],
    "NRin": ROLE_SURFACES["nationalrat"],
    "BR": ROLE_SURFACES["bundesrat"],
    "StS": ROLE_SURFACES["staatssekretär"],
    "BM": ROLE_SURFACES["minister"],
}


# --- Parteien ------------------------------------------------------------
PARTY_ALIASES: dict[str, str] = {
    "spö": "SPÖ", "spo": "SPÖ", "sozialdemokraten": "SPÖ", "sozialdemokratie": "SPÖ",
    "sozialdemokratisch": "SPÖ", "sozialdemokratische": "SPÖ", "roten": "SPÖ", "rote": "SPÖ",
    "övp": "ÖVP", "oevp": "ÖVP", "türkisen": "ÖVP", "türkise": "ÖVP", "schwarzen": "ÖVP",
    "fpö": "FPÖ", "fpoe": "FPÖ", "blauen": "FPÖ", "blaue": "FPÖ", "freiheitlichen": "FPÖ",
    "grüne": "Grüne", "grünen": "Grüne", "gruene": "Grüne", "gruenen": "Grüne",
    "neos": "NEOS", "pinken": "NEOS", "kpö": "KPÖ", "kpoe": "KPÖ",
    "bierpartei": "Bierpartei", "liste burgenland": "Liste Burgenland",
}

#: Parteien, die als Präfix einer Funktionsangabe auftreten ("SPÖ-Chef").
PARTY_TOKENS = ("SPÖ", "ÖVP", "FPÖ", "Grüne", "GRÜNE", "NEOS", "KPÖ")


# --- Namensvokabular -----------------------------------------------------
FIRST_NAMES = {
    "alexander", "alexandra", "alfred", "andrea", "andreas", "anna", "anneliese",
    "anselm", "anton", "astrid", "barbara", "bernhard", "birgit", "brigitte",
    "christian", "christiane", "christina", "christine", "christoph", "daniel",
    "daniela", "david", "doris", "edith", "elisabeth", "emil", "erich", "erika",
    "ernst", "eva", "florian", "franz", "franziska", "gabi", "gabriele", "georg",
    "gerald", "gerhard", "gertrude", "gottfried", "günter", "günther", "hans",
    "harald", "heidi", "heike", "heinrich", "helga", "helmut", "herbert",
    "hermann", "hildegard", "horst", "hubert", "ines", "ingrid", "irene",
    "isabella", "jakob", "johann", "johanna", "johannes", "josef", "julia",
    "jürgen", "karin", "karl", "katharina", "klaus", "konrad", "kurt", "leonhard",
    "lisa", "ludwig", "manfred", "marcel", "maria", "marianne", "mario", "markus",
    "martin", "matthias", "max", "michael", "michaela", "monika", "nicole",
    "norbert", "oliver", "oswald", "patrick", "paul", "peter", "petra", "philipp",
    "rainer", "ralf", "regina", "reinhard", "renate", "richard", "robert",
    "roland", "roman", "rudolf", "sabine", "sandra", "sebastian", "sigrid",
    "silvia", "simon", "stefan", "stephan", "susanne", "tanja", "theresa",
    "thomas", "tobias", "udo", "ulrich", "ulrike", "ursula", "valentin",
    "verena", "viktor", "walter", "werner", "wilhelm", "wolfgang", "magdalena",
    "carina", "patrik", "klaus", "helene", "johannes", "ursula", "anja", "kurt",
    "gertrude", "heribert", "gottfried", "oswald", "leonhard", "norbert", "didi",
    "kathrin", "kerstin", "mario", "marcel", "rene", "sandra", "tanja", "theresa",
    "bernd", "rory", "jon", "lukas", "maximilian", "simon", "oliver", "patrick",
    "grete", "josko", "greta", "grethe", "joso", "vlado", "ivan", "marija",
    "nikolaus", "marina", "angelika", "bettina", "silvio", "zoltan", "gert",
    "charley", "herbert", "ursula", "ingrid", "helmut", "otto", "lisa",
    "ronald", "josef", "julia", "andreas", "michael", "franz", "karl",
    "werner", "rudi", "hansjörg", "wolfdieter", "kurt", "hubert", "gottfried",
    "benjamin", "elias", "jonas", "leon", "lena", "luca", "noah", "emil",
    "hannah", "marlene", "sophie", "valerie", "victoria", "alexander",
    "raphaela", "marin", "veronika", "kristina", "corina", "rosa", "wolfgang",
    "gudrun", "hildegard", "herta", "irmgard", "klaudia", "konstanze", "lena",
    "lea", "laura", "lorenz", "magdalena", "manuel", "margit", "marion",
    "marlene", "martha", "matthäus", "maximilian", "melitta", "miriam",
    "nina", "oskar", "otto", "pascal", "patrizia", "paula", "philippa",
    "raimund", "reinhard", "roswitha", "rudolf", "rut", "sandra", "sarah",
    "selina", "sigrid", "silke", "sonja", "stefanie", "susanna", "sven",
    "sylvia", "tamara", "thomas", "tina", "tobias", "udo", "ursula", "uta",
    "vera", "verena", "volker", "waltraud", "werner", "wilhelmine", "yvonne",
    "alois", "aloisia", "andrea", "annemarie", "anton", "armin", "arnold",
    "astrid", "barbara", "bernhard", "birgit", "brigitta", "charlotte",
    "christa", "dagmar", "dietmar", "edeltraud", "elfriede", "else", "emma",
    "erich", "erika", "ernst", "evelyn", "fabian", "felix", "ferdinand",
    "florian", "franz", "franziska", "friedrich", "gabriele", "georg",
    "gerda", "gernot", "gertraud", "gisela", "gottfried", "gregor", "günter",
    "hannelore", "hansjörg", "harald", "heidi", "heike", "heinz", "helga",
    "herbert", "hermann", "hilmar", "hubert", "ilse", "ines", "ingrid",
    "irene", "isabella", "josef", "julia", "julian", "jürgen", "karin",
    "karl", "katharina", "klaus", "konrad", "kurt", "leonhard", "liane",
    "ludwig", "manfred", "marcel", "marianne", "mario", "markus", "martin",
    "michael", "michaela", "monika", "norbert", "oswald", "peter", "petra",
    "rainer", "ralf", "regina", "renate", "richard", "robert", "roland",
    "roman", "sabine", "sebastian", "stefan", "stephan", "tanja", "theresa",
    "ulrich", "ulrike", "valentin", "viktor", "walter", "werner", "wolfgang",
}


# --- Generische Wörter (keine Personennamen) -----------------------------
GENERIC_WORDS = {
    # Artikel / Pronomen / Partikeln
    "der", "die", "das", "den", "dem", "des", "ein", "eine", "einer", "eines",
    "einem", "einen", "er", "sie", "es", "wir", "ich", "ihr", "ihm", "ihn",
    "ihre", "ihrer", "seine", "seiner", "dieser", "diese", "dieses", "diesen",
    "beide", "beiden", "beider", "alle", "alles", "viele", "mehrere", "andere",
    "anderer", "weiter", "weitere", "zwei", "drei", "vier", "fünf", "sechs",
    "sieben", "acht", "neun", "zehn", "hundert", "tausend", "millionen",
    "milliarden", "prozent", "euro", "cent",
    # Zeit
    "jahr", "jahre", "jahren", "jahrzehnt", "jahrzehnte", "monat", "monate",
    "woche", "wochen", "tag", "tage", "tagen", "nacht", "morgen", "abend",
    "mittag", "uhr", "minute", "minuten", "stunde", "stunden", "zeit", "zeiten",
    "anfang", "ende", "mitte", "montag", "dienstag", "mittwoch", "donnerstag",
    "freitag", "samstag", "sonntag", "jänner", "februar", "märz", "april",
    "mai", "juni", "juli", "august", "september", "oktober", "november",
    "dezember", "heute", "gestern", "morgen", "derzeit", "damals", "frühjahr",
    "sommer", "winter", "herbst", "frühling", "advent", "weihnachten", "ostern",
    "silvester", "neujahr", "wochenende", "feiertag", "feiertage", "saison",
    # Raum
    "land", "länder", "bundesland", "burgenland", "österreich", "stadt",
    "städte", "gemeinde", "gemeinden", "marktgemeinde", "bezirk", "bezirke",
    "region", "regionen", "ort", "orte", "dörfer", "dorf", "viertel", "platz",
    "straße", "strasse", "weg", "gasse", "haus", "hof", "burg", "schloss",
    "kirche", "pfarre", "pfarrei", "schule", "volksschule", "mittelschule",
    "gymnasium", "universität", "fachhochschule", "krankenhaus", "klinik",
    "ordination", "zentrum", "halle", "stadion", "gelände", "areal", "baustelle",
    "grenze", "grenzübergang", "see", "fluss", "bach", "berg", "hügel", "wald",
    "feld", "acker", "weinberg", "garten", "park", "siedlung", "siedlungsgebiet",
    "süd", "norden", "osten", "westen", "nord", "mitte", "umgebung", "innenstadt",
    # Institutionen / Organisationen
    "landtag", "gemeinderat", "gemeindevorstand", "regierung", "landesregierung",
    "ministerium", "behörde", "amt", "ämter", "magistrat", "rathaus", "gericht",
    "landesgericht", "staatsanwaltschaft", "justizanstalt", "polizei",
    "polizeidirektion", "landespolizeidirektion", "feuerwehr", "rettung",
    "bundesheer", "justiz", "anwaltschaft", "notariat", "kammer",
    "wirtschaftskammer", "arbeiterkammer", "landwirtschaftskammer", "ams",
    "arbeitsmarktservice", "övp", "spö", "fpö", "grüne", "grünen", "neos", "kpö",
    "partei", "parteien", "fraktion", "liste", "bündnis", "verein", "vereine",
    "verband", "verbände", "gmbh", "ag", "kg", "og", "holding", "bank", "banken",
    "versicherung", "raiffeisen", "genossenschaft", "stiftung", "fonds",
    "orchest", "orchester", "theater", "museum", "bibliothek", "archiv", "verein",
    "projekt", "projekte", "konzept", "plan", "pläne", "antrag", "beschluss",
    "gesetz", "verordnung", "förderung", "förderungen", "budget", "geld", "kosten",
    "preis", "preise", "aktion", "aktionen", "veranstaltung", "veranstaltungen",
    "fest", "feste", "konzert", "ausstellung", "lesung", "film", "buch", "bücher",
    "musik", "kultur", "kunst", "literatur", "medien", "presse", "interview",
    "aussendung", "stellungnahme", "presseaussendung", "meldung", "bericht",
    "studie", "umfrage", "statistik", "zahlen", "daten", "ergebnis", "ergebnisse",
    "wahl", "wahlen", "wahlkampf", "stimmen", "mandat", "sitz", "sitzung",
    "konferenz", "tagung", "kongress", "symposium", "podium", "debatte",
    "kritik", "streit", "konflikt", "einigung", "kompromiss", "lösung",
    "problem", "probleme", "thema", "themen", "frage", "fragen", "antwort",
    # Kriminalität / Unfall / Wetter
    "unfall", "unfälle", "brand", "brände", "feuer", "alarm", "einsatz",
    "einsätze", "verletzte", "verletzter", "tote", "toter", "opfer", "täter",
    "prozess", "urteil", "anklage", "haft", "strafe", "einbruch", "diebstahl",
    "betrug", "cyberangriff", "angriff", "attacke", "attentat", "mord",
    "wetter", "gewitter", "schnee", "regen", "sturm", "wind", "hitze", "kälte",
    "temperatur", "unwetter", "hochwasser", "trockenheit", "sonne", "nebel",
    "verkehr", "straße", "sperre", "sperren", "baustelle", "umleitung", "auto",
    "pkw", "lkw", "motorrad", "fahrrad", "zug", "bus", "bahn",
    # Sport
    "sport", "spiel", "spiele", "mannschaft", "team", "teams", "liga",
    "landesliga", "bundesliga", "meisterschaft", "titel", "sieg", "niederlage",
    "remis", "unentschieden", "tor", "tore", "match", "derby", "cup", "finale",
    "halbzeit", "runde", "saison", "transfer", "vertrag", "kader", "tabelle",
    "herbstmeister", "meister", "meistertitel", "aufstieg", "abstieg", "punkte",
    "spieler", "trainer", "schiedsrichter", "fan", "fans", "publikum",
    # Adjektive / Adverbien / Sonstiges
    "auch", "aber", "doch", "denn", "weil", "wenn", "dann", "nun", "jetzt",
    "bereits", "noch", "nur", "schon", "erst", "wieder", "daher", "deshalb",
    "zudem", "außerdem", "allerdings", "jedoch", "insgesamt", "rund", "etwa",
    "knapp", "sehr", "so", "wie", "was", "wer", "wo", "wann", "warum", "dabei",
    "damit", "dafür", "dagegen", "durch", "gegen", "ohne", "über", "unter",
    "zwischen", "während", "wegen", "trotz", "seit", "bis", "nach", "vor",
    "beim", "vom", "zum", "zur", "im", "am", "an", "auf", "aus", "bei", "mit",
    "von", "zu", "für", "ist", "sind", "war", "waren", "wird", "werden", "wurde",
    "wurden", "hat", "haben", "hatte", "hatten", "kann", "können", "muss",
    "müssen", "soll", "sollen", "will", "wollen", "darf", "dürfen", "laut",
    "neue", "neuer", "neues", "neuen", "alte", "alter", "altes", "alten",
    "große", "großer", "großes", "großen", "kleine", "kleiner", "kleinen",
    "gute", "guter", "gutes", "guten", "erste", "erster", "erstes", "ersten",
    "zweite", "dritte", "letzte", "letzter", "letzten", "nächste", "nächsten",
    "rot", "rote", "roter", "blau", "blaue", "grün", "grüne", "schwarz",
    "schwarze", "weiß", "gold", "silber", "bronze", "österreichische",
    "österreichischer", "burgenländische", "burgenländischer", "internationale",
    "europäische", "sozialdemokratische", "sozialdemokratischer", "christliche",
    "freiheitliche", "grüne", "rote", "schwarze", "blaue", "türkise",
    "gesamt", "gemeinsam", "öffentlich", "öffentliche", "privat",
    # typische Motive in Bildzeilen (sonst würden "Weingut Esterházy" o. Ä. zu Personen)
    "weingut", "gutshof", "denkmal", "statue", "fassade", "eingang", "ausgang",
    "ausblick", "blick", "luftbild", "panorama", "detail", "innenansicht",
    "außenansicht", "symbolbild", "plakat", "schild", "tafel", "bühne", "podium",
    "mauer", "turm", "tor", "ufer", "insel", "brücke", "kapelle", "altar",
    "musikschule", "volkshochschule", "hauptplatz", "kirchenplatz",
    "hauptstraße", "bahnhofstraße", "industriestraße", "gewerbestraße",
    "also", "ebenso", "gleichzeitig", "mittlerweile", "inzwischen", "vielmehr",
    "als", "dass", "ob", "um", "wie", "sondern", "oder", "und", "sowie",
    "obwohl", "sobald", "solange", "sofern", "falls", "damit", "indem",
    # englische Begriffe in deutschsprachigen Texten
    "social", "media", "boy", "boys", "girl", "girls", "day", "days", "night",
    "live", "show", "shows", "event", "events", "news", "press", "team", "teams",
    "club", "clubs", "city", "open", "tour", "top", "star", "stars", "award",
    "awards", "pro", "plus", "digital", "online", "web", "app", "apps",
    "podcast", "podcasts", "video", "videos", "talk", "food", "drinks",
    "flag", "football", "basketball", "volleyball", "handball", "baseball",
    "softball", "hockey", "rugby", "cricket", "soccer", "golf", "tennis",
    "skateboard", "snowboard", "workshop", "workshops", "meeting", "start-up",
    "black", "friday", "community", "nurses", "gospel", "singer", "lilies",
    "seal", "maker", "special", "olympic", "olympics", "red", "green", "house",
    "junge", "talente", "welt", "deine", "ost", "regionalliga", "schleife",
    "outlet", "center", "plaza", "resort", "lounge", "bar", "store", "shop",
    "book", "dance", "company", "flamenco", "academia", "irish", "moose",
    "the", "tiger", "maxi", "crossing", "openair", "launch", "award",
}

#: Einzelwort-Ortsnamen (klein). Wird zur Laufzeit um automatisch aus dem
#: Korpus gelernte Toponyme ergänzt (siehe ``bglbot.gazetteer``).
GEO_WORDS = {
    # Bundesländer, Staaten, große Städte
    "burgenland", "kärnten", "niederösterreich", "oberösterreich", "salzburg",
    "steiermark", "tirol", "vorarlberg", "wien", "österreich", "ungarn",
    "slowakei", "slowenien", "kroatien", "deutschland", "tschechien", "polen",
    "rumänien", "serbien", "italien", "schweiz", "europa", "brüssel", "berlin",
    "münchen", "graz", "linz", "st", "sankt", "donau",
    # Bezirksvororte
    "eisenstadt", "rust", "neusiedl", "oberpullendorf", "oberwart",
    "mattersburg", "güssing", "jennersdorf",
    # Orte und Katastralgemeinden im Burgenland
    "frauenkirchen", "parndorf", "kittsee", "gols", "mönchhof", "podersdorf",
    "illmitz", "apetlon", "andau", "tadten", "wallern", "pamhagen",
    "deutschkreutz", "raiding", "neutal", "lutzmannsburg", "jahrndorf",
    "schützen", "leithaprodersdorf", "klingenbach", "eisenberg", "lackenbach",
    "großpetersdorf", "pinkafeld", "stadtschlaining", "rechnitz", "lockenhaus",
    "bernstein", "mariasdorf", "oberschützen", "tatzmannsdorf", "stegersbach",
    "heiligenkreuz", "rudersdorf", "fürstenfeld", "hartberg", "horitschon",
    "großwarasdorf", "weppersdorf", "stoob", "kaisersdorf", "steinberg",
    "unterfrauenhaid", "lackendorf", "ritzing", "neckenmarkt", "draßmarkt",
    "pilgersdorf", "kirchschlag", "hochneukirchen", "hollenthon", "lichtenegg",
    "bromberg", "erlach", "lanzenkirchen", "walpersbach", "pitten", "schwarzau",
    "neudörfl", "zemendorf", "pöttelsdorf", "stöttera", "antau", "hirm",
    "sigless", "sieggraben", "kobersdorf", "weingraben", "rotenturm", "jabing",
    "badersdorf", "schachendorf", "dürnbach", "strem", "güttenbach",
    "olbendorf", "bocksdorf", "rauchwart", "rohr", "kaltenbrunn", "elend",
    "königsdorf", "mühlgraben", "tschanigraben", "luising", "hagensdorf",
    "heugraben", "hochstraß", "kukmirn", "limbach", "tobaj", "wörterberg",
    "stinatz", "wolfau", "aschau", "allhau", "loipersdorf", "kemeten",
    "hannersdorf", "litzelsdorf", "ohlendorf", "rothenthurm", "burgauberg",
    "neudauberg", "raitenberg", "grieselstein", "mogersdorf", "weichselbaum",
    "rosendorf", "henndorf", "auersthal", "zicksee", "margarethen", "oberberg",
    "unterberg", "loipersbach", "dörfl", "kalkgruben", "weiden", "halbturn",
    "zurndorf", "nickelsdorf", "edelstal", "wolfsthal", "haslau",
    "regelsbrunn", "hainburg", "bruckneudorf", "bruck", "krensdorf",
    "zemendorf", "pöttsching", "wulkaprodersdorf",
    "hornstein", "müllendorf", "großhöflein", "kleinhöflein", "sankt georgen",
    "oberberg", "eisenstadt", "neufeld", "zillingtal", "grosshöflein",
    "steinbrunn", "trausdorf", "wulka", "purbach", "breitenbrunn",
    "winden", "jois", "neusiedl", "weiden", "gattendorf", "zurndorf",
    "pama", "kroatisch", "minihof", "geresdorf", "rosental", "podgoria",
    "krobotek", "weichselbaum", "hochstraß", "eisenberg", "pinka", "pinkatal",
}

#: Wörter, die einem Namen direkt folgen und ihn als Institution entlarven
#: ("Konrad Adenauer Stiftung", "Thomas-Morus-Preis").
INSTITUTION_WORDS = {
    "stiftung", "institut", "instituts", "preis", "preises", "platz", "straße",
    "strasse", "gasse", "weg", "schule", "schulzentrum", "gymnasium", "heim",
    "klinik", "haus", "zentrum", "museum", "galerie", "verein", "verband",
    "gmbh", "ag", "kg", "bank", "kasse", "kammer", "staat", "gemeinde",
}

#: Oberflächen, die zwar wie Namen aussehen, aber keine Personen sind.
NOT_PERSONS = {
    "burgenland", "österreich", "europa", "eu", "orf", "orf.at", "land",
    "stadt", "gemeinde", "sankt", "st", "donau", "wulka", "pinka", "raab",
}

ATTRIBUTION_VERBS = (
    "sagte", "sagt", "sagten", "meinte", "meint", "erklärte", "erklärt",
    "betonte", "betont", "forderte", "fordert", "kritisierte", "kritisiert",
    "berichtete", "berichtet", "bestätigte", "bestätigt", "teilte", "informierte",
    "gratulierte", "gratuliert", "dankte", "dankt", "lobte", "lobt", "warnte",
    "warnt", "appellierte", "appelliert", "hofft", "rechnet", "sieht", "sprach",
    "erzählte", "schilderte", "argumentiert", "begründet", "verweist", "kündigte",
    "heißt", "hieß", "so", "laut", "zufolge", "gemäß", "wies", "stellte",
)

#: Signalwörter, die den Charakter einer Beziehung zwischen zwei Personen färben.
RELATION_CUES: dict[str, tuple[str, ...]] = {
    "nachfolge": ("folgt", "nachfolger", "nachfolgerin", "vorgänger", "vorgängerin",
                  "nachgefolgt", "übernimmt", "übergibt", "scheidet", "ablöst", "ablöse"),
    "zuspruch": ("gratuliert", "dankt", "dankte", "lobt", "lobte", "würdigt", "würdigte",
                 "anerkennt", "ehrt", "auszeichnet", "beglückwünscht"),
    "konflikt": ("kritisiert", "kritik", "wirft", "vorwurf", "vorwürfe", "attackiert",
                 "kontert", "streit", "auseinandersetzung", "wehrt sich", "zurückgewiesen",
                 "weist zurück", "widerspricht", "klagt", "beschuldigt", "gegen",
                 "protestiert", "protest", "konflikt", "disput", "streitpunkt"),
    "kooperation": ("gemeinsam", "kooperation", "kooperieren", "einig", "einigung",
                    "vereinbart", "partnerschaft", "bündnis", "zusammenarbeit",
                    "unterstützt", "unterstützung", "solidarisch", "verbündet"),
    "wahl": ("gewählt", "wahl", "kandidatur", "kandidat", "stimmen", "delegierte",
             "konferenz", "nominierte", "nominierung", "liste", "mandat"),
    "vertretung": ("vertritt", "vertreten", "stellvertreter", "stellvertreterin",
                   "vertretung", "in vertretung"),
}

#: Kleine Stoppliste für Satzanfänge, die keine Namen sind.
SENTENCE_STARTERS = {
    "der", "die", "das", "ein", "eine", "er", "sie", "es", "wir", "ich", "auch",
    "aber", "doch", "denn", "weil", "wenn", "dann", "nun", "jetzt", "heute",
    "gestern", "morgen", "damit", "dafür", "dagegen", "deshalb", "daher",
    "zudem", "außerdem", "allerdings", "jedoch", "insgesamt", "rund", "etwa",
    "knapp", "seit", "nach", "vor", "bei", "beim", "vom", "zum", "zur", "im",
    "am", "an", "auf", "aus", "mit", "von", "zu", "für", "über", "unter",
    "zwischen", "während", "wegen", "trotz", "bis", "um", "laut", "so",
}

#: Akademische und journalistische Titel, die nie Teil eines Namens sind.
ACADEMIC_TITLES = {
    "mag", "mag.", "mmag", "mmag.", "dr", "dr.", "di", "di.", "dipl", "ing",
    "ing.", "prof", "prof.", "univ", "ba", "ma", "msc", "bsc", "mba", "phd",
    "stv", "stv.", "sen", "sen.", "em", "em.", "h.c",
}

#: Wörter, die direkt vor einem Namen stehen, aber selbst kein Name sind
#: („Anrainer Klaus Maras“, „Bäckermeister Heinz Bayer“).
DESCRIPTOR_NOUNS = {
    "anrainer", "anrainerin", "anrainerinnen", "bewohner", "bewohnerin",
    "betroffener", "betroffene", "betroffenen", "kunde", "kundin", "kunden",
    "vertreter", "vertreterin", "vertretern", "sprecher", "sprecherin",
    "mitarbeiter", "mitarbeiterin", "arbeiter", "arbeiterin", "bauer",
    "bäuerin", "bäckermeister", "bäckermeisterin", "unternehmer", "unternehmerin",
    "schüler", "schülerin", "schülern", "lehrer", "lehrerin", "eltern",
    "experte", "expertin", "fachmann", "fachfrau", "kenner", "kennerin",
    "kritiker", "kritikerin", "befürworter", "befürworterin", "gegner",
    "gegnerin", "initiator", "initiatorin", "organisator", "organisatorin",
    "veranstalter", "veranstalterin", "besitzer", "besitzerin", "pächter",
    "pächterin", "wirt", "wirtin", "landwirt", "landwirtin", "winzer",
    "winzerin", "obstbauer", "obstbäuerin", "journalist", "journalistin",
    "moderator", "moderatorin", "referent", "referentin", "vortragender",
    "teilnehmer", "teilnehmerin", "gewinner", "gewinnerin", "sieger",
    "siegerin", "täter", "täterin", "opfer", "zeuge", "zeugin", "lenker",
    "lenkerin", "fahrer", "fahrerin", "passant", "passantin", "nachbar",
    "nachbarin", "nachbarn", "kollege", "kollegin", "kollegen", "chef",
    "chefin", "boss", "star", "idol", "vorbild", "talent", "nachwuchstalent",
    "nachwuchsspieler", "nachwuchsspielerin", "jungtalent", "musiker",
    "musikerin", "sänger", "sängerin", "schauspieler", "schauspielerin",
    "kabarettist", "kabarettistin", "autor", "autorin", "schriftsteller",
    "schriftstellerin", "maler", "malerin", "künstler", "künstlerin",
}

#: Suffixe, mit denen deutsche Substantive gebeugt werden.
_GERMAN_SUFFIXES = ("s", "es", "en", "n", "e", "er", "em", "es")

_BLOCK_CACHE: dict[str, bool] = {}


def is_generic(word_lower: str) -> bool:
    """Prüft ein Token (inkl. deutscher Flexionsendungen) gegen die Stopplisten."""
    cached = _BLOCK_CACHE.get(word_lower)
    if cached is not None:
        return cached
    if (word_lower in GENERIC_WORDS or word_lower in GEO_WORDS
            or word_lower in NOT_PERSONS or word_lower in DESCRIPTOR_NOUNS
            or word_lower in ACADEMIC_TITLES or word_lower in ROLE_SURFACES):
        _BLOCK_CACHE[word_lower] = True
        return True
    # Nur lange Stämme strippen, damit Nachnamen wie "Hofer" (-> "hof") heil bleiben.
    for suffix in _GERMAN_SUFFIXES:
        if word_lower.endswith(suffix):
            stem = word_lower[: -len(suffix)]
            if len(stem) >= 5 and (stem in GENERIC_WORDS or stem in GEO_WORDS):
                _BLOCK_CACHE[word_lower] = True
                return True
    _BLOCK_CACHE[word_lower] = False
    return False

#: Kanonische Funktions-ID -> Kategorie (für Farbgebung im Graphen).
ROLE_CATEGORY: dict[str, str] = {r.canonical: r.category for r in ROLE_SURFACES.values()}

#: Substantiv-Köpfe, die am Ende eines Kompositums stehen. Ein Kandidat, dessen
#: letztes Token so endet, ist ein Ding und keine Person
#: ("Norbert Hofers Gesundheitszustand", "Heinrich Knotzers Werk").
COMPOUND_HEADS = (
    "zustand", "werk", "amt", "haus", "bau", "kosten", "preis", "projekt",
    "plan", "idee", "wunsch", "forderung", "kritik", "rede", "auftritt",
    "besuch", "entscheidung", "aussage", "meinung", "vorschlag", "antrag",
    "vertrag", "zusage", "absage", "sieg", "niederlage", "spiel", "zeit",
    "jahr", "tag", "woche", "monat", "stunde", "minute", "weg", "straße",
    "platz", "gasse", "berg", "tal", "feld", "wald", "see", "bach", "dorf",
    "stadt", "land", "gemeinde", "verein", "partei", "firma", "unternehmen",
    "gruppe", "team", "club", "verband", "institut", "schule", "kirche",
    "fest", "feier", "konzert", "ausstellung", "buch", "film", "lied",
    "album", "tour", "reise", "urlaub", "krankheit", "verletzung", "unfall",
    "brand", "einsatz", "termin", "treffen", "gespräch", "runde", "sitzung",
    "wahl", "kampf", "streit", "konflikt", "lösung", "ergebnis", "bilanz",
    "studie", "konzept", "programm", "aktion", "kampagne", "bericht",
    "meldung", "interview", "statement", "zitat", "vertretung", "nachfolge",
    "zuständigkeit", "verantwortung", "aufgabe", "rolle", "position",
    "funktion", "tätigkeit", "arbeit", "engagement", "auftrag", "mandat",
    "sitz", "stimme", "mehrheit", "kritik", "lob", "dank", "gruß", "wort",
    "worte", "trauer", "freude", "sorge", "angst", "hoffnung", "vision",
    "ziel", "idee", "konzept", "strategie", "reform", "gesetz", "verordnung",
    "förderung", "budget", "million", "milliarde", "prozent", "zahl", "zahlen",
)


#: Abstrakt-/Sachsubstantiv-Suffixe: "Feinstaubbelastung", "Verfolgungsmaßnahmen",
#: "Anton Proksch-Instituts" sind keine Personen.
THING_SUFFIXES = (
    "ung", "ungen", "heit", "keit", "keiten", "schaft", "schaften", "tion",
    "tionen", "ion", "ionen", "ität", "ismus", "maßnahme", "maßnahmen",
    "abzeichen", "belastung", "vergiftung", "anlage", "gebäude", "fläche",
    "stelle", "nummer", "zeichen", "mittel", "gerät", "betrag", "quote",
    "frist", "vergiftung", "institut", "instituts", "anstalt", "stiftung",

)


#: Mindestlänge des Kompositum-Stamms vor dem Kopf. Verhindert, dass kurze
#: Vorsilben echte Namen blockieren: "Roland" endet auf "land", ist aber ein
#: Vorname; "Weiland" auf "land", ist ein Nachname.
MIN_COMPOUND_STEM = 4


def ends_with_thing(word_lower: str) -> bool:
    """Prüft, ob ein Token auf einen dinglichen Kopf oder ein Abstraktum endet.

    Genitivformen („Proksch-Instituts“) werden vorher auf den Grundform-Stamm
    zurückgeführt. Der Stamm vor dem Kopf muss mindestens vier Zeichen haben.
    """
    candidates = [word_lower]
    if len(word_lower) > 7 and word_lower.endswith("s"):
        candidates.append(word_lower[:-1])
    for cand in candidates:
        for head in COMPOUND_HEADS + THING_SUFFIXES:
            if cand.endswith(head) and len(cand) - len(head) >= MIN_COMPOUND_STEM:
                return True
    return False

#: Sentiment-/Beziehungsvokabular für Kanten. Gewicht = Intensität (0..1).
#: Pro Satz zählt je Kategorie nur der stärkste Treffer, damit "kritisiert"
#: nicht doppelt wiegt, wenn "Kritik" als Teilstring mitmatcht.
SENTIMENT_CUES: dict[str, tuple[tuple[str, float], ...]] = {
    "feindselig": (
        ("attackiert", 1.0), ("attacke", 0.9), ("angriff", 0.9), ("beschimpft", 1.0),
        ("diffamiert", 1.0), ("hetzt", 1.0), ("hetze", 1.0), ("feindselig", 1.0),
        ("niedergemacht", 1.0), ("scharfe kritik", 0.8), ("schlagabtausch", 0.7),
        ("konfrontation", 0.9), ("zerfleischt", 1.0), ("beschuldigt", 0.9),
        ("wirft vor", 0.8), ("vorwurf", 0.7), ("vorwürfe", 0.8),
    ),
    "negativ": (
        ("kritisiert", 0.7), ("kritik", 0.6), ("kritisch", 0.5), ("kontert", 0.7),
        ("wehrt sich", 0.6), ("weist zurück", 0.7), ("zurückgewiesen", 0.7),
        ("streit", 0.6), ("konflikt", 0.7), ("auseinandersetzung", 0.6),
        ("disput", 0.6), ("protest", 0.5), ("protestieren", 0.5), ("klagt", 0.6),
        ("klage", 0.5), ("anzeige", 0.6), ("ermittelt", 0.5), ("ermittlungen", 0.5),
        ("misstrauen", 0.8), ("streitpunkt", 0.6),
        ("unter druck", 0.5), ("widerspricht", 0.6), ("absage", 0.5),
        ("verzögert", 0.4), ("blockiert", 0.5), ("ablehnt", 0.5), ("lehnt ab", 0.5),
        ("verweigert", 0.5), ("blockade", 0.5), ("eklat", 0.8),
        ("verstimmung", 0.6), ("misstrauensantrag", 0.9), ("debatte", 0.35),
        ("streitfrage", 0.6), ("unmut", 0.5), ("empörung", 0.7), ("vorwurf", 0.7),
    ),
    "positiv": (
        ("lobt", 0.8), ("lob", 0.6), ("gratuliert", 0.7), ("gratulation", 0.7),
        ("dankt", 0.7), ("dankte", 0.7), ("dank", 0.5), ("würdigt", 0.8),
        ("würdigte", 0.8), ("anerkennt", 0.7), ("begrüßt", 0.5), ("freut sich", 0.6),
        ("unterstützt", 0.7), ("unterstützung", 0.6), ("verteidigt", 0.7),
        ("stärkt", 0.6), ("vertrauen", 0.6), ("ehrt", 0.7), ("geehrt", 0.6),
        ("auszeichnet", 0.7), ("beglückwünscht", 0.7), ("zufrieden", 0.5),
        ("anerkennung", 0.6), ("respekt", 0.45), ("gelungen", 0.45),
        ("erfolgreich", 0.3), ("einladung", 0.4),
    ),
    "kooperativ": (
        ("einig", 0.5), ("einigung", 0.6), ("einigen", 0.5), ("kooperation", 0.7),
        ("kooperieren", 0.7), ("zusammenarbeit", 0.6), ("partnerschaft", 0.6),
        ("bündnis", 0.6), ("solidarisch", 0.6), ("dialog", 0.4), ("gespräch", 0.3),
        ("vereinbart", 0.4), ("gemeinsam", 0.3), ("abgestimmt", 0.4),
        ("unterstützen einander", 0.6),
    ),
}

#: Gewicht, mit dem eine Kategorie in den Sentiment-Score eingeht.
SENTIMENT_WEIGHT = {
    "feindselig": -1.2,
    "negativ": -1.0,
    "positiv": +1.0,
    "kooperativ": +0.8,
}

#: Kurzformen und Spitznamen -> bürgerlicher Vorname. Der ORF schreibt "Grete",
#: die Wikipedia und andere Artikel führen "Margarethe"; ohne diese Brücke
#: entstehen zwei Personen und der Wikipedia-Artikel bleibt unauffindbar.
NICKNAMES: dict[str, tuple[str, ...]] = {
    "grete": ("margarethe", "margareta", "greta"),
    "gretl": ("margarethe", "margareta"),
    "didi": ("dietmar", "dieter"),
    "sepp": ("josef",), "seppi": ("josef",), "pepi": ("josef",), "joschi": ("josef",),
    "hans": ("johann", "johannes"),
    "hansi": ("johann",),
    "fritz": ("friedrich",), "franzl": ("franz",), "ferdl": ("ferdinand",),
    "resi": ("therese",), "resl": ("therese",),
    "lisi": ("elisabeth",), "sissi": ("elisabeth",), "lotte": ("charlotte",),
    "gustl": ("august", "gustav"), "gusti": ("auguste", "gustava"),
    "hanni": ("johanna", "hannelore"),
    "toni": ("anton", "antonia"),
    "niki": ("nikolaus",),
    "michi": ("michael",),
    "andi": ("andreas",),
    "babsi": ("barbara",),
    "vroni": ("veronika",),
    "traudi": ("gertraud", "gertrude"), "trude": ("gertrud", "gertrude"),
    "heini": ("heinrich",),
    "wasti": ("sebastian",),
    "loisl": ("alois",),
    "xandi": ("alexander",),
    "ossi": ("oskar", "oswald"),
    "kari": ("karl",),
    "susI": ("susanne",),
    "inge": ("ingrid", "ingeborg"),
    "evi": ("eva",),
    "moni": ("monika",),
    "dani": ("daniel", "daniela"),
    "steffi": ("stefanie", "stephanie"),
    "tom": ("thomas",),
    "alex": ("alexander", "alexandra"),
    "max": ("maximilian",),
    "leo": ("leopold", "leonhard"),
    "rudi": ("rudolf",),
    "leni": ("helene", "magdalena"),
    "bertl": ("albert", "berthold"),
    "ferdi": ("ferdinand",),
    "poldi": ("leopold",),
    "viki": ("viktoria",),
    "mizzi": ("maria",),
    "hermi": ("hermine",),
    "elfi": ("elfriede",),
    "edi": ("eduard",),
    "gerti": ("gertrude",),
    "gabi": ("gabriele",),
}


def canonical_first_name(name: str) -> str:
    """Vergleichsform des Vornamens: „Grete“ und „Margarethe“ werden gleich."""
    first = re.split(r"[-\s]+", name.strip())[0].lower()
    targets = NICKNAMES.get(first)
    return (targets[0] if targets else first)