"""Contrat du corpus importé (Omni-MATH) : import, statistiques, filtres, tirage au hasard.

Ces tests verrouillent ce qui fait la « complétude » du site : chaque énoncé du
corpus devient une fiche avec sa solution officielle, ses indices générés, et le
catalogue sait distinguer le corpus curaté du corpus importé.
"""

from __future__ import annotations

import io
import json
import shutil
import tempfile
from pathlib import Path

from django.core.management import call_command
from django.test import TestCase
from django.urls import reverse

from problems.management.commands.ingest_omni_math import (
    DEFAULT_FILE,
    category_for,
    select_records,
    source_label,
    track_for,
)
from problems.models import Hint, Problem, Solution
from problems.management.commands.verify_lock_sample import BANNER as LOCK_BANNER, SUBMIT_LABEL as LOCK_CTA
from problems.tests.factories import make_problem, make_user

SAMPLE_RECORDS = [
    {
        "domain": "Mathematics -> Algebra -> Other",
        "difficulty": 4.5,
        "problem": r"Let $a,b>0$ with $a+b=1$. Prove that $\left(1+\frac1a\right)\left(1+\frac1b\right)\ge 9$.",
        "solution": (
            r"Expand each factor over a common denominator and use $a+b=1$: the product equals "
            r"$1 + \frac{1}{ab}$, and AM-GM gives $ab \le \left(\frac{a+b}{2}\right)^2 = \frac14$, "
            r"so the product is at least $1 + 4 = 9$, with equality exactly when $a = b = \tfrac12$."
        ),
        "answer": r"$9$",
        "source": "imo_shortlist",
    },
    {
        "domain": "Mathematics -> Geometry -> Triangles",
        "difficulty": 7.5,
        "problem": r"Let $ABC$ be a triangle with incenter $I$. Show that $\angle BIC = 90^\circ + \frac{A}{2}$.",
        "solution": (
            r"Add the two angles at $B$ and $C$: $\frac{B+C}{2} = 90^\circ - \frac{A}{2}$, so "
            r"$\angle BIC = 180^\circ - \frac{B+C}{2} = 90^\circ + \frac{A}{2}$. Equality is never "
            r"attained for a genuine triangle because $A > 0$."
        ),
        "answer": "",
        "source": "hmmt_11",
    },
    {
        "domain": "Mathematics -> Number Theory -> Divisibility",
        "difficulty": 2.5,
        "problem": r"Find all $n$ such that $n \mid 2^n$.",
        "solution": (
            r"Write $n = 2^k m$ with $m$ odd and compare the 2-adic valuations of both sides: "
            r"$n \mid 2^n$ forces $k \le n$, which holds for every $k$ once $k \le 2^k$, so the "
            r"constraint really comes from the odd part, and a short check leaves $n = 1$ and $n = 2$."
        ),
        "answer": r"$n=1,2$",
        "source": "putnam",
    },
]


class CorpusStatisticsTests(TestCase):
    """Le fichier source doit rester exploitable : 4 000+ fiches, toutes corrigées."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.path = Path(DEFAULT_FILE)
        if not cls.path.exists():  # corpus optionnel hors de l'environnement de démo
            cls.records = []
            return
        cls.records, _counters, _per_source = select_records(cls.path)

    def test_corpus_is_large_and_every_record_has_a_solution(self):
        if not self.records:
            self.skipTest(f"{DEFAULT_FILE} absent")
        self.assertGreater(len(self.records), 4000, "le corpus doit couvrir tous les problèmes")
        for record, puid, _answer, _markup in self.records:
            self.assertTrue(str(record.get("solution", "")).strip(), f"{puid} sans solution")
            self.assertTrue(str(record.get("problem", "")).strip(), f"{puid} sans énoncé")

    def test_puids_are_unique_and_human_readable(self):
        if not self.records:
            self.skipTest(f"{DEFAULT_FILE} absent")
        puids = [puid for _record, puid, _answer, _markup in self.records]
        self.assertEqual(len(puids), len(set(puids)), "PUID dupliqué dans le corpus")
        for puid in puids[:50]:
            self.assertTrue(puid.startswith("OMNI "), puid)
            self.assertIn("/", puid, puid)

    def test_every_category_and_every_track_is_populated(self):
        if not self.records:
            self.skipTest(f"{DEFAULT_FILE} absent")
        categories = {category_for(record.get("domain")) for record, _p, _a, _m in self.records}
        tracks = {track_for(record.get("difficulty")) for record, _p, _a, _m in self.records}
        self.assertEqual(categories, {"algebra", "combinatorics", "geometry", "number_theory", "misc"})
        self.assertEqual(tracks, {"foundation", "olympiad", "hard"})


class MappingTests(TestCase):
    def test_source_labels_are_short_and_readable(self):
        self.assertEqual(source_label("imo"), "IMO")
        self.assertEqual(source_label("imo_shortlist"), "IMO SL")
        self.assertEqual(source_label("hmmt_11"), "HMMT-11")
        self.assertEqual(source_label("china_team_selection_test"), "China TST")
        self.assertTrue(source_label("some_unknown_contest").startswith("Some"))

    def test_categories_cover_the_json_shapes(self):
        self.assertEqual(category_for(["Mathematics -> Algebra -> Other"]), "algebra")
        self.assertEqual(category_for("Mathematics -> Geometry -> Triangles"), "geometry")
        self.assertEqual(category_for(["Mathematics -> Discrete Mathematics -> Graphs"]), "combinatorics")
        self.assertEqual(category_for(["Mathematics -> Number Theory"]), "number_theory")
        self.assertEqual(category_for(["Mathematics -> Calculus"]), "misc")
        self.assertEqual(category_for(None), "misc")

    def test_difficulty_tracks_are_monotone(self):
        self.assertEqual(track_for(1.0), "foundation")
        self.assertEqual(track_for(5.0), "olympiad")
        self.assertEqual(track_for(9.5), "hard")
        self.assertEqual(track_for("4"), "olympiad")


class GeneratedHintTests(TestCase):
    """Un indice généré ne doit jamais citer une phrase de la solution officielle."""

    def test_hints_never_quote_the_official_solution(self):
        from problems.services.coach_hints import generate_hints

        solution = SAMPLE_RECORDS[0]["solution"]
        statement = SAMPLE_RECORDS[0]["problem"]
        hints = generate_hints(statement_tex=statement, solution_tex=solution, category="algebra")
        self.assertGreaterEqual(len(hints), 2, "au moins une piste générale et une piste technique")
        sentences = [s.strip() for s in solution.replace("\n", " ").split(".") if len(s.strip()) > 25]
        for hint in hints:
            for sentence in sentences:
                self.assertNotIn(sentence, hint, "l'indice recopie la solution")

    def test_hints_are_french_orientation_text(self):
        from problems.services.coach_hints import generate_hints

        hints = generate_hints(
            statement_tex=SAMPLE_RECORDS[2]["problem"],
            solution_tex=SAMPLE_RECORDS[2]["solution"],
            category="number_theory",
        )
        self.assertTrue(any("valuation" in h.lower() or "modulo" in h.lower() for h in hints))


class IngestionCommandTests(TestCase):
    """L'import est idempotent et remplit les trois tables du contrat."""

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.source = self.tmp / "sample.jsonl"
        self.source.write_text(
            "\n".join(json.dumps(record, ensure_ascii=False) for record in SAMPLE_RECORDS),
            encoding="utf-8",
        )

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def _run(self, *args):
        out = io.StringIO()
        call_command("ingest_omni_math", "--file", str(self.source), *args, stdout=out)
        return out.getvalue()

    def test_import_creates_problem_solution_and_hints(self):
        self._run()
        self.assertEqual(Problem.objects.count(), 3)
        self.assertEqual(Solution.objects.count(), 3)
        problem = Problem.objects.get(puid="OMNI IMO SL/001")
        self.assertIn("a+b=1", problem.statement_tex)
        self.assertEqual(problem.category, "algebra")
        self.assertEqual(problem.difficulty_track, "olympiad")
        self.assertEqual(problem.answer_tex, "$9$")
        self.assertTrue(problem.solution.official_tex.startswith("Expand each factor"))
        self.assertGreaterEqual(problem.hints.count(), 2)
        self.assertIn("Omni-MATH", problem.solution.attribution)

    def test_reimport_is_idempotent_and_does_not_duplicate(self):
        self._run()
        problems_after_first = Problem.objects.count()
        hints_after_first = Hint.objects.count()
        self._run()
        self.assertEqual(Problem.objects.count(), problems_after_first)
        self.assertEqual(Hint.objects.count(), hints_after_first)

    def test_source_and_difficulty_filters(self):
        self._run("--sources", "putnam")
        self.assertEqual(Problem.objects.count(), 1)
        self.assertEqual(Problem.objects.get().puid, "OMNI Putnam/001")

    def test_limit_and_dry_run(self):
        self._run("--limit", "2", "--dry-run")
        self.assertEqual(Problem.objects.count(), 0, "le mode dry-run n'écrit rien")
        self._run("--limit", "2")
        self.assertEqual(Problem.objects.count(), 2)


class CatalogueFilterTests(TestCase):
    """Le catalogue distingue le corpus curaté du corpus importé, et sait tirer au sort."""

    @classmethod
    def setUpTestData(cls):
        cls.user = make_user("catalogue-user")
        cls.curated = Problem.objects.create(
            puid="IMO 2019/1",
            statement_tex=r"Determine all $f : \mathbb{Z} \to \mathbb{Z}$ with $f(2a)+2f(b)=f(f(a+b))$.",
            category="algebra",
            difficulty_track="olympiad",
        )
        cls.imported = Problem.objects.create(
            puid="OMNI HMMT-11/007",
            statement_tex=r"Let $ABC$ be a triangle with incenter $I$; show $\angle BIC = 90^\circ + A/2$.",
            category="geometry",
            difficulty_track="hard",
        )

    def setUp(self):
        self.client.force_login(self.user)

    def test_corpus_filter_splits_curated_and_imported(self):
        curated = self.client.get(reverse("problem-list"), {"corpus": "curated"})
        self.assertEqual(list(curated.context["problems"]), [self.curated])
        imported = self.client.get(reverse("problem-list"), {"corpus": "omni"})
        self.assertEqual(list(imported.context["problems"]), [self.imported])

    def test_search_matches_a_puid_or_a_statement(self):
        by_puid = self.client.get(reverse("problem-list"), {"q": "OMNI HMMT-11"})
        self.assertEqual(list(by_puid.context["problems"]), [self.imported])
        by_text = self.client.get(reverse("problem-list"), {"q": "incenter"})
        self.assertEqual(list(by_text.context["problems"]), [self.imported])

    def test_random_view_redirects_to_a_fiche(self):
        for _ in range(5):
            response = self.client.get(reverse("problem-random"))
            self.assertEqual(response.status_code, 302)
            self.assertIn("/problems/", response.url)

    def test_next_problem_cta_points_at_a_fiche_of_the_catalogue(self):
        page = self.client.get(reverse("problem-list"))
        next_problem = page.context["next_problem"]
        self.assertIsInstance(next_problem, Problem)
        self.assertIn(next_problem.puid, {self.curated.puid, self.imported.puid})

class LockAuditCommandTests(TestCase):
    """L'auditeur de verrou tourne sur tout le corpus et sort en erreur dès qu'une page fuit."""

    @classmethod
    def setUpTestData(cls):
        cls.user = make_user("audit-user")
        cls.user.is_superuser = True
        cls.user.save(update_fields=["is_superuser"])
        cls.locked = make_problem("AUDIT 2026/1", hints=2)

    def test_audit_samples_the_catalogue_and_reports_no_leak(self):
        out = io.StringIO()
        call_command("verify_lock_sample", "--sample", "1", "--seed", "3", stdout=out)
        report = out.getvalue()
        self.assertIn("Aucune fuite détectée", report)

    def test_a_leaking_page_is_reported(self):
        """La détection est testée sur un HTML fabriqué : c'est le cœur de l'auditeur."""
        from problems.management.commands.verify_lock_sample import page_leaks

        problem = make_problem("AUDIT 2026/2", hints=1)
        secret = "Assume for contradiction that k is not a perfect square and choose a counterexample"
        problem.solution.official_tex = f"Let k = (a^2+b^2)/(ab+1). {secret} with a+b minimal."
        problem.solution.save(update_fields=["official_tex"])

        clean = f'<div><p class="locked-title">{LOCK_BANNER}</p><button>{LOCK_CTA}</button></div>'
        self.assertEqual(page_leaks(problem, clean), [])

        leaking = clean.replace("</div>", f"<pre class=\"rendered\">{secret}</pre></div>")
        found = page_leaks(problem, leaking)
        self.assertTrue(found, "une page qui recopie la solution doit être signalée")
        self.assertIn("fuite", found[0])

    def test_a_locked_page_without_the_banner_is_reported(self):
        from problems.management.commands.verify_lock_sample import page_leaks

        problem = make_problem("AUDIT 2026/3", hints=1)
        found = page_leaks(problem, "<div>rien</div>")
        self.assertTrue(any("bandeau" in line for line in found))
        self.assertTrue(any("bouton" in line for line in found))

class TranslationPolishTests(TestCase):
    """Le mode texte (``\text{...}``) doit finir en français sans toucher aux maths."""

    def test_english_words_inside_text_mode_are_translated(self):
        from problems.management.commands.translate_corpus import polish_text_mode

        source = r"On conclut $\text{if and only if } x \ge 0$ et $\text{otherwise} \ne 1$."
        polished, changes = polish_text_mode(source)
        self.assertEqual(changes, 2)
        self.assertIn(r"\text{si et seulement si }", polished)
        self.assertIn(r"\text{sinon}", polished)

    def test_polish_never_touches_mathematics_outside_text_mode(self):
        from problems.management.commands.translate_corpus import polish_text_mode

        source = r"$\max(a, b) \text{ for all } a,b$ with $\frac{\text{sum}}{2}$ and plain words if any."
        polished, _changes = polish_text_mode(source)
        self.assertIn(r"\max(a, b)", polished)
        self.assertIn(r"\text{ pour tout }", polished)
        self.assertIn(r"\frac{\text{somme}}{2}", polished)
        self.assertIn("plain words if any.", polished)  # hors maths : intact
