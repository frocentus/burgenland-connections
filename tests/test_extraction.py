"""Tests für die regelbasierte Erkennung (ohne Netzzugriff)."""

from __future__ import annotations

import unittest

from bglbot import extract as EX
from bglbot import gazetteer, graph as G, lexicon, resolve
from bglbot import text as T
from bglbot.parse import Article


def make_article(text: str, title: str = "Testartikel", captions: list[str] | None = None) -> Article:
    return Article(
        id="1",
        url="https://burgenland.orf.at/stories/1/",
        title=title,
        category="Test",
        lead="",
        paragraphs=[text],
        captions=captions or [],
        published="2026-11-14T10:00:00",
    )


def extract(article: Article) -> EX.ArticleExtraction:
    learned = gazetteer.learn([article.text])
    ctx = EX.ExtractionContext(geo=gazetteer.combine(learned))
    return EX.extract_article(article, ctx)


class TextToolsTest(unittest.TestCase):
    def test_abbreviations_do_not_split(self):
        sents = T.split_sentences("Das sagte er z.B. am Montag. Danach ging er.")
        self.assertEqual(len(sents), 2)

    def test_ordinal_does_not_split(self):
        sents = T.split_sentences("Zum 18. Mal fand das Fest statt. Es war gut.")
        self.assertEqual(len(sents), 2)

    def test_name_token(self):
        self.assertTrue(T.is_name_token("Haider-Wallner"))
        self.assertTrue(T.is_name_token("McIlroy"))
        self.assertFalse(T.is_name_token("SPÖ-Chef"))
        self.assertFalse(T.is_name_token("NS-Opfer"))
        self.assertFalse(T.is_name_token("SPÖ"))


class RoleAndPartyTest(unittest.TestCase):
    def test_role_before_name_and_party(self):
        article = make_article(
            "Landesrat Heinrich Dorner (SPÖ) und Landeshauptmann-Stellvertreterin "
            "Anja Haider-Wallner (Grüne) nahmen an der Feier teil."
        )
        result = extract(article)
        people = {p.name: p for p in result.persons}
        self.assertIn("Heinrich Dorner", people)
        self.assertEqual(people["Heinrich Dorner"].party, "SPÖ")
        self.assertEqual(people["Heinrich Dorner"].role_id, "landesrat")
        self.assertEqual(people["Anja Haider-Wallner"].party, "Grüne")
        self.assertEqual(people["Anja Haider-Wallner"].role_id, "lh-stellvertreter")

    def test_party_prefix_on_role(self):
        article = make_article(
            "SPÖ-Landesparteivorsitzender Landeshauptmann Hans Peter Doskozil "
            "gratulierte dem neuen Duo."
        )
        result = extract(article)
        person = result.persons[0]
        self.assertEqual(person.name, "Hans Peter Doskozil")
        self.assertEqual(person.party, "SPÖ")
        self.assertEqual(person.role_id, "landeshauptmann")

    def test_role_after_name(self):
        article = make_article(
            "Gerhard Bachmann ist Bürgermeister in Deutsch Jahrndorf (Bezirk Neusiedl am See)."
        )
        result = extract(article)
        person = result.persons[0]
        self.assertEqual(person.name, "Gerhard Bachmann")
        self.assertEqual(person.role_id, "bürgermeister")
        self.assertIn("Deutsch Jahrndorf", person.role_context or "")


class CaptionListTest(unittest.TestCase):
    def test_comma_list_is_split_into_persons(self):
        caption = ("Thomas Prunner, Raphaela Pint, Martin Ganster, Chefredakteur "
                   "Walter Schneeberger, Elisabeth Pauer-Gerbavsits, Marin Berlakovich")
        article = make_article(
            "Die Moderatoren präsentieren die Sendung.", captions=[caption]
        )
        names = {p.name for p in extract(article).persons}
        self.assertIn("Elisabeth Pauer-Gerbavsits", names)
        self.assertIn("Marin Berlakovich", names)
        self.assertIn("Raphaela Pint", names)
        self.assertFalse(any("Pauer-Gerbavsits Marin" in n for n in names))

    def test_no_name_spans_across_punctuation(self):
        article = make_article("Zsifkovics: Papst Franziskus lobte das Engagement.")
        names = {p.name for p in extract(article).persons}
        self.assertFalse(any(n.startswith("Zsifkovics ") for n in names))


class ExclusionTest(unittest.TestCase):
    def test_org_is_not_a_person(self):
        article = make_article(
            "Einer der Geschäftsführer der Biowärme GmbH ist der ehemalige "
            "Bürgermeister Manfred Kölly (LBL)."
        )
        names = {p.name for p in extract(article).persons}
        self.assertIn("Manfred Kölly", names)
        self.assertNotIn("Biowärme", names)

    def test_genitive_surname_is_normalised(self):
        article = make_article(
            "Heinrich Knotzer baute das Denkmal. Beeindruckend ist Heinrich Knotzers Werk."
        )
        names = {p.name for p in extract(article).persons}
        self.assertIn("Heinrich Knotzer", names)
        self.assertFalse(any(n.endswith("s") and n.startswith("Heinrich Knotz") for n in names))

    def test_place_names_are_not_persons(self):
        article = make_article(
            "In Lackenbach (Bezirk Oberpullendorf) und in Deutschkreutz wurde gefeiert."
        )
        self.assertEqual(extract(article).persons, [])


class OccupationTest(unittest.TestCase):
    """Berufsbezeichnung vor dem Namen darf den Vollnamen nicht verhindern."""

    def test_media_occupation_yields_full_name(self):
        article = make_article(
            "Der junge Marzer Filmemacher Benjamin Knöbl lebt seit neun Jahren in "
            "Los Angeles. Knöbl erzählt die Geschichte einer Sechsjährigen."
        )
        names = {p.name for p in extract(article).persons}
        self.assertIn("Benjamin Knöbl", names)
        self.assertNotIn("Knöbl", names)


class FalsePositiveTest(unittest.TestCase):
    """Berufslisten und Sportarten dürfen nicht als Personen erscheinen."""

    def test_occupation_list_is_not_a_person(self):
        article = make_article(
            "Trotzdem blieb er zeit seines Lebens Landwirt und nebenbei Komponist, "
            "Musiker, Kapellmeister und Musikpädagoge."
        )
        self.assertEqual({p.name for p in extract(article).persons}, set())

    def test_sport_name_is_not_a_person(self):
        article = make_article(
            "Der Fokus liegt nun auf Flag Football – der kontaktlosen Variante. "
            "Flag Football wird 2028 erstmals olympisch, Flag Football boomt."
        )
        self.assertEqual({p.name for p in extract(article).persons}, set())

    def test_surname_only_does_not_create_person(self):
        article = make_article("Bürgermeister Knöbl eröffnete das Fest.")
        self.assertEqual(extract(article).persons, [])


    def test_noun_after_role_is_not_a_person(self):
        article = make_article(
            "Ende Oktober hatte der Gemeinderat die Entlassung der bisherigen "
            "Amtsleiterin beschlossen. Die Amtsleitung wird neu ausgeschrieben."
        )
        names = {p.name for p in extract(article).persons}
        self.assertNotIn("Entlassung", names)


class SentimentTest(unittest.TestCase):
    """Kanten sollen einen Beziehungston tragen."""

    def _edge(self, text: str) -> dict:
        article = make_article(text)
        extraction = extract(article)
        persons = resolve.resolve([extraction])
        graph_data = G.build_graph([extraction], persons)
        return graph_data["edges"][0]

    def test_criticism_is_negative(self):
        edge = self._edge(
            "Landeshauptmann Hans Peter Doskozil kritisierte Bürgermeister "
            "Gerhard Bachmann scharf."
        )
        self.assertEqual(edge["sentiment"]["label"], "negativ")
        self.assertEqual(edge["sentiment"]["direction"], {"hans-peter-doskozil>gerhard-bachmann": 1})

    def test_praise_is_positive(self):
        edge = self._edge(
            "Landeshauptmann Hans Peter Doskozil lobte Bürgermeister Gerhard Bachmann."
        )
        self.assertEqual(edge["sentiment"]["label"], "positiv")

    def test_negation_flips_praise(self):
        edge = self._edge(
            "Landeshauptmann Hans Peter Doskozil war nicht zufrieden mit dem Auftritt "
            "von Bürgermeister Gerhard Bachmann."
        )
        self.assertEqual(edge["sentiment"]["label"], "negativ")

    def test_neutral_pair_stays_neutral(self):
        edge = self._edge(
            "Landeshauptmann Hans Peter Doskozil und Bürgermeister Gerhard Bachmann "
            "nahmen an der Feier teil."
        )
        # Neutrale Kanten tragen kein Sentiment-Objekt (spart ~900 KB Seitengröße);
        # fehlend bedeutet neutral.
        self.assertEqual(edge.get("sentiment", {}).get("label", "neutral"), "neutral")


class RoleNormalisationTest(unittest.TestCase):
    """Schreibvarianten einer Funktion ergeben einen Eintrag."""

    def test_variants_are_merged(self):
        texts = [
            "Landeshauptmann Hans Peter Doskozil eröffnete das Fest.",
            "SPÖ-Landeshauptmann Hans Peter Doskozil sprach beim Fest.",
            "Die Rede des Landeshauptmanns Hans Peter Doskozil wurde gelobt.",
        ]
        extractions = []
        for index, text in enumerate(texts):
            article = make_article(text)
            article.id = str(index + 1)
            extractions.append(extract(article))
        persons = resolve.resolve(extractions)
        self.assertEqual(len(persons), 1)
        roles = persons[0].to_dict()["roles"]
        self.assertEqual(roles[0]["label"], "Landeshauptmann")
        self.assertEqual(roles[0]["count"], 3)


class PersonToneTest(unittest.TestCase):
    """Tonlage einer Person, auch wenn die Kritik keinem Gegenüber gilt."""

    def _tone(self, text: str, fragment: str) -> dict:
        article = make_article(text)
        extraction = extract(article)
        persons = resolve.resolve([extraction])
        data = G.build_graph([extraction], persons)
        node = next(n for n in data["nodes"] if fragment in n["name"])
        return node["tone"]

    def test_criticism_of_institution_counts(self):
        tone = self._tone(
            "SPÖ-Klubobmann Roland Fürst kritisierte die Bundesregierung scharf "
            "und forderte eine Katastrophenversicherung.", "Fürst")
        self.assertIn("kritisch", tone["label"])
        self.assertGreaterEqual(tone["critical"], 1)

    def test_praise_counts(self):
        tone = self._tone(
            "Landeshauptmann Hans Peter Doskozil lobte die Arbeit der Regierung "
            "ausdrücklich und dankte allen Beteiligten.", "Doskozil")
        self.assertIn("zustimmend", tone["label"])


class NicknameTest(unittest.TestCase):
    """Kurzformen müssen auf den bürgerlichen Vornamen führen."""

    def test_variants(self):
        from bglbot.wiki import name_variants
        self.assertIn("Margarethe Krojer", name_variants("Grete Krojer"))
        self.assertIn("Dietmar Kühbauer", name_variants("Didi Kühbauer"))
        self.assertIn("Johann Sipötz", name_variants("Hans Sipötz"))

    def test_unknown_name_stays(self):
        from bglbot.wiki import name_variants
        self.assertEqual(name_variants("Roland Fürst"), ["Roland Fürst"])


class ResolutionTest(unittest.TestCase):
    def test_variants_and_surname_only_are_merged(self):
        art1 = make_article(
            "Hans Peter Doskozil sagte am Freitag, der Landeshauptmann bleibe bei seiner Linie."
        )
        art2 = make_article(
            "Für den Landeshauptmann war es ein Erfolg: Doskozil sprach von einem Signal."
        )
        art1.id, art2.id = "1", "2"
        extractions = [extract(art1), extract(art2)]
        persons = resolve.resolve(extractions)
        self.assertEqual(len(persons), 1)
        self.assertEqual(persons[0].name, "Hans Peter Doskozil")
        self.assertEqual(persons[0].article_count, 2)

    def test_first_name_typo_is_merged(self):
        art1 = make_article("Die Musikerin Luisa Schweig tritt am Samstag auf.")
        art2 = make_article("Lusia Schweig gewann den Wettbewerb.")
        art1.id, art2.id = "1", "2"
        persons = resolve.resolve([extract(art1), extract(art2)])
        self.assertEqual(len(persons), 1)


if __name__ == "__main__":
    unittest.main()
