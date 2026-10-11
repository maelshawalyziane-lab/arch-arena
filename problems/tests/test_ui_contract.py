"""
Frontend contract tests (deliverable 4).

These assert the *visible* promises the brief makes about the Problem Detail view —
the exact lock banner, the MathJax/KaTeX include, the hint accordion, the
Markdown/LaTeX textarea, the "Submit for AI Evaluation" button with its loading
spinner, and the unlocked layout (official solution + success badge + feedback
history).  They are deliberately string-level checks against the rendered HTML so
that a template refactor cannot quietly drop a requirement.
"""

from __future__ import annotations

from pathlib import Path

from django.conf import settings
from django.test import TestCase, override_settings
from django.urls import reverse

from problems.models import SubmissionStatus, UserSubmission
from problems.tests.factories import make_problem, make_user
from problems.services.tex import render_rich
from problems.services.verification import verify_submission

from .factories import STRONG_SUBMISSION, make_problem, make_user

# The brief specifies this banner verbatim (French, emoji included).
LOCK_BANNER = "🔒 Solution officielle verrouillée. Soumettez une preuve validée par l'IA pour la débloquer."
SUBMIT_CTA = "Soumettre à l'évaluation IA"
LOCK_SENTINEL = "Let $k = \\\\dfrac{a^2+b^2}{ab+1}$"  # phrase unique to the official solution


def visible_text(html: str) -> str:
    """Page text with tags collapsed, so multi-element sentences can be asserted exactly."""
    import re

    return " ".join(re.sub(r"<[^>]+>", " ", html).split())


class ProblemDetailMarkupTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = make_user("ui-student")
        cls.problem = make_problem(puid="TEST 2026/7", statement=r"Let $a,b$ be positive integers.")

    def setUp(self):
        self.client.force_login(self.user)

    def url(self) -> str:
        return self.problem.get_absolute_url()

    # ---------------------------------------------------------------- locked #
    def test_locked_view_shows_the_exact_banner_and_hides_the_solution(self):
        response = self.client.get(self.url())
        body = response.content.decode()
        self.assertEqual(response.status_code, 200)

        # The banner is the spec's exact sentence.  It is split over two <p> tags in
        # the template, so check it against the *visible text* of the page: the
        # rendering must read exactly as specified, tags or not.
        self.assertIn(LOCK_BANNER, visible_text(body))
        self.assertIn("🔒", body)
        # the answer key itself must not be anywhere in the payload
        self.assertNotIn(LOCK_SENTINEL, body)
        self.assertNotIn(self.problem.answer_tex, body)
        self.assertNotIn(self.problem.solution.official_tex, body)

    def test_no_fragment_of_the_official_solution_leaks_into_the_locked_page(self):
        """
        Stronger than a whole-string check: every sentence of the answer key must be
        absent, so a partial leak (e.g. the first half of the proof) is caught too.
        """
        import re

        body = self.client.get(self.url()).content.decode()
        official = self.problem.solution.official_tex
        sentences = [part.strip() for part in re.split(r"(?<=\.)\s+", official) if len(part.strip()) > 25]
        self.assertGreater(len(sentences), 1)  # sanity: the fixture is prose, not a one-liner
        for sentence in sentences:
            self.assertNotIn(sentence[:40], body, f"fuite partielle détectée : {sentence[:40]!r}")
        self.assertNotIn("solution-body", body)   # no rendered answer block exists at all
        self.assertIn("locked-title", body)       # the locked overlay is what is shown

    def test_locked_view_has_the_submission_form_with_spinner(self):
        body = self.client.get(self.url()).content.decode()
        self.assertIn('name="text"', body)                      # textarea (name=text)
        self.assertIn(SUBMIT_CTA, body)                          # required button label
        self.assertIn('id="submit-spinner"', body)               # loading spinner
        self.assertIn('class="spinner"', body)
        self.assertIn('id="submission-form"', body)
        # the JS contract the client half relies on
        self.assertIn(f'data-verify-url="{reverse("api-verify", args=[self.problem.pk])}"', body)
        self.assertIn(f'data-status-url="{reverse("api-status", args=[self.problem.pk])}"', body)

    def test_hint_accordion_is_tiered_and_locked_hints_carry_no_content(self):
        body = self.client.get(self.url()).content.decode()
        self.assertIn("Indices", body)
        for hint in self.problem.hints.all():
            self.assertIn(f"Indice {hint.order_index}", body)
        # tier 1 is offerable, tier 2 is not openable yet
        self.assertIn("Révéler l'indice 1", body)
        self.assertIn("ouvrez d'abord l'indice 1", body)
        self.assertNotIn("ouvrez d'abord l'indice 0", body)  # tier 1 has nothing before it

    def test_math_is_rendered_through_the_math_pipeline(self):
        body = self.client.get(self.url()).content.decode()
        self.assertIn('class="math-inline"', body)  # server-side TeX span wrapper
        # KaTeX is served locally (works offline / inside sandboxed previews)
        self.assertIn("vendor/katex/katex.min.css", body)
        self.assertIn("vendor/katex/katex.min.js", body)
        self.assertIn("vendor/katex/auto-render.min.js", body)
        self.assertIn("problems/js/app.js", body)
        self.assertIn("problems/js/problem.js", body)

    def test_statement_is_rendered_as_safe_html(self):
        raw = render_rich(r"Show that $\sqrt{2}$ is irrational.")
        self.assertIn("math-inline", raw)
        self.assertNotIn("<script", raw)
        body = self.client.get(self.url()).content.decode()
        self.assertIn("positive integers", body)
        self.assertNotIn("\\dfrac{a^2+b^2}{ab+1}", body)  # nothing from the answer key

    # -------------------------------------------------------------- unlocked #
    def test_unlocked_view_swaps_in_solution_badge_answer_and_history(self):
        result = verify_submission(user=self.user, problem=self.problem, text=STRONG_SUBMISSION, mode="offline")
        self.assertTrue(result.unlocked, result.feedback)

        body = self.client.get(self.url()).content.decode()
        self.assertNotIn(LOCK_BANNER, visible_text(body))    # banner is gone
        self.assertIn("✓ Solution débloquée", body)          # success badge
        self.assertIn("Solution officielle", body)
        self.assertIn("contradicting minimality", body)      # the ground truth is now served
        self.assertIn(self.problem.answer_tex, body)         # answer line, only now
        self.assertIn("Vos corrections", body)               # feedback history panel
        self.assertIn("Correcteur :", body)                  # AI feedback rendered

    def test_rejected_submission_is_visible_in_the_history_but_keeps_the_gate_shut(self):
        weak = "It is well known by Vieta jumping, so the quotient is a square."
        result = verify_submission(user=self.user, problem=self.problem, text=weak, mode="offline")
        self.assertFalse(result.unlocked)

        body = self.client.get(self.url()).content.decode()
        self.assertIn("Vos corrections", body)
        self.assertIn("Refusée", body)           # status badge (French label)
        self.assertIn("Votre copie soumise", body)
        self.assertIn(weak[:40], body)
        self.assertNotIn(LOCK_SENTINEL, body)


class ListAndDashboardMarkupTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = make_user("ui-browser")
        cls.problems = [
            make_problem(puid="ALPHA 2026/1", category="algebra", track="foundation"),
            make_problem(puid="BETA 2026/2", category="geometry", track="hard"),
        ]

    def test_list_shows_cards_with_puid_and_category_badges(self):
        self.client.force_login(self.user)
        body = self.client.get(reverse("problem-list")).content.decode()
        for problem in self.problems:
            self.assertIn(problem.puid, body)
        self.assertIn("Algèbre", body)
        self.assertIn("Géométrie", body)
        self.assertIn(reverse("problem-detail", args=[self.problems[0].pk]), body)
        # search / filter affordances
        self.assertIn('name="q"', body)

    def test_list_marks_solved_problems(self):
        self.client.force_login(self.user)
        verify_submission(user=self.user, problem=self.problems[0], text=STRONG_SUBMISSION, mode="offline")
        body = self.client.get(reverse("problem-list")).content.decode()
        self.assertIn("BETA 2026/2", body)
        self.assertIn("débloquée", body)

    def test_dashboard_summarises_progress_per_category(self):
        self.client.force_login(self.user)
        UserSubmission.objects.create(
            user=self.user,
            problem=self.problems[0],
            submitted_text="x" * 20,
            status=SubmissionStatus.REJECTED,
            ai_feedback="too short",
            engine="offline-heuristic",
        )
        response = self.client.get(reverse("dashboard"))
        body = response.content.decode()
        self.assertEqual(response.status_code, 200)
        self.assertIn("Tableau de bord", body)
        self.assertIn("Algèbre", body)
        self.assertIn("0 / 1", body)   # nothing solved yet in this category
        self.assertIn("offline-heuristic", body)

    def test_login_page_renders_and_signup_is_closed(self):
        """La plateforme n'ouvre qu'un seul compte : l'inscription explique la règle."""
        response = self.client.get(reverse("login"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Connexion")

        closed = self.client.get(reverse("signup"))
        self.assertEqual(closed.status_code, 403)
        self.assertContains(closed, "Les comptes sont fermés", status_code=403)

    @override_settings(ALLOW_SIGNUP=True)
    def test_signup_form_reappears_when_explicitly_enabled(self):
        response = self.client.get(reverse("signup"))
        self.assertEqual(response.status_code, 200)


class ApiContractTests(TestCase):
    """Le contrat JSON de l'API, vu depuis un compte connecté."""

    @classmethod
    def setUpTestData(cls):
        cls.problem = make_problem(puid="API 2026/1", hints=4)
        cls.user = make_user("api-contract")

    def setUp(self):
        self.client.force_login(self.user)

    def test_status_endpoint_exposes_the_documented_fields(self):
        response = self.client.get(reverse("api-status", args=[self.problem.pk]))
        payload = response.json()
        self.assertEqual(response.status_code, 200)
        for key in (
            "success", "problem_id", "puid", "is_solved", "unlocked_at",
            "hints_total", "hints_revealed", "next_hint_id", "submissions",
            "can_verify", "rate_remaining",
        ):
            self.assertIn(key, payload, key)
        self.assertEqual(payload["hints_total"], 4)
        self.assertEqual(payload["hints_revealed"], 0)
        self.assertTrue(payload["can_verify"])
        self.assertEqual(payload["next_hint_id"], self.problem.hints.first().pk)

    def test_status_endpoint_reports_a_problem_without_ground_truth_as_unverifiable(self):
        blind = make_problem(puid="TEST 2026/12", with_solution=False)
        payload = self.client.get(reverse("api-status", args=[blind.pk])).json()
        self.assertFalse(payload["can_verify"])

    def test_hint_reveal_reports_progress_and_the_next_hint_on_refusal(self):
        hints = list(self.problem.hints.order_by("order_index"))
        refused = self.client.post(reverse("api-hint-reveal", args=[self.problem.pk, hints[2].pk]))
        self.assertEqual(refused.status_code, 409)
        body = refused.json()
        self.assertEqual(body["error"], "hint_locked")
        self.assertEqual(body["next_hint_id"], hints[0].pk)
        self.assertEqual(body["revealed_count"], 0)

        granted = self.client.post(reverse("api-hint-reveal", args=[self.problem.pk, hints[0].pk]))
        self.assertEqual(granted.status_code, 200)
        granted_body = granted.json()
        self.assertEqual(granted_body["revealed_count"], 1)
        self.assertEqual(granted_body["order_index"], 1)
        self.assertIn("math-inline", granted_body["content_html"])

        # idempotent: the same reveal can be repeated without a 409
        again = self.client.post(reverse("api-hint-reveal", args=[self.problem.pk, hints[0].pk]))
        self.assertEqual(again.status_code, 200)

    def test_verify_returns_success_true_in_both_verdicts(self):
        rejected = self.client.post(
            reverse("api-verify", args=[self.problem.pk]), {"text": "By Vieta jumping. Routine."}
        ).json()
        self.assertTrue(rejected["success"])
        self.assertFalse(rejected["unlocked"])
        self.assertEqual(rejected["status"], "REJECTED")

        passed = self.client.post(
            reverse("api-verify", args=[self.problem.pk]), {"text": STRONG_SUBMISSION}
        ).json()
        self.assertTrue(passed["success"])
        self.assertTrue(passed["unlocked"])
        self.assertEqual(passed["status"], "PASSED")
        self.assertIn("rate_remaining", passed)

    def test_reset_relocks_only_the_current_problem_for_one_user(self):
        verify_submission(user=self.user, problem=self.problem, text=STRONG_SUBMISSION, mode="offline")
        other = make_user("api-contract-2")
        verify_submission(user=other, problem=self.problem, text=STRONG_SUBMISSION, mode="offline")

        reset = self.client.post(reverse("api-reset", args=[self.problem.pk]))
        self.assertEqual(reset.status_code, 200)
        self.assertTrue(reset.json()["success"])
        self.assertFalse(self.problem.solved_by(self.user))
        self.assertTrue(self.problem.solved_by(other))  # untouched
        self.assertFalse(UserSubmission.objects.filter(user=self.user).exists())


class FramingAndSecurityHeaderTests(TestCase):
    """The custom clickjacking middleware is what lets the preview embed the app."""

    @classmethod
    def setUpTestData(cls):
        cls.problem = make_problem(puid="TEST 2026/21")

    def test_framing_is_allowed_in_demo_mode_and_denied_in_production_mode(self):
        response = self.client.get(self.problem.get_absolute_url())
        self.assertNotIn("X-Frame-Options", response.headers)
        self.assertIn("frame-ancestors", response.headers.get("Content-Security-Policy", ""))

        with override_settings(ALLOW_IFRAMING=False, FRAME_OPTIONS_POLICY="DENY"):
            hardened = self.client.get(self.problem.get_absolute_url())
            self.assertEqual(hardened.headers.get("X-Frame-Options"), "DENY")
            self.assertNotIn("frame-ancestors", hardened.headers.get("Content-Security-Policy", ""))

    def test_security_headers_are_always_present(self):
        response = self.client.get(self.problem.get_absolute_url())
        self.assertEqual(response.headers.get("X-Content-Type-Options"), "nosniff")
        self.assertEqual(response.headers.get("Referrer-Policy"), "same-origin")


class GraderPromptContractTests(TestCase):
    """The grader system prompt must be the specification text, verbatim."""

    def test_system_prompt_is_the_verbatim_french_specification(self):
        from problems.services import ai_grader

        expected = """Rôle : Tu es un correcteur expert des Olympiades Internationales de Mathématiques (IMO).
Tâche : Évaluer si le plan de solution ou la preuve soumis contient une logique mathématique valide et arrive au bon résultat par rapport à la solution officielle.
Données : Énoncé={statement}, Solution officielle={official_tex}, Soumission étudiant={user_submission}.
Réponds UNIQUEMENT en JSON strict sans balises markdown :
{
  "passed": true ou false,
  "feedback": "2-3 phrases explicatives."
}"""
        self.assertEqual(ai_grader.SYSTEM_PROMPT, expected)

    def test_prompt_substitution_injects_the_three_data_slots(self):
        from problems.services import ai_grader

        system, user = ai_grader.build_prompt(
            puid="TEST 2026/1",
            statement="ÉNONCÉ-UNIQUE",
            official_tex="SOLUTION-OFFICIELLE-UNIQUE",
            user_submission="COPIE-ÉTUDIANTE-UNIQUE",
        )
        self.assertIn("Énoncé=ÉNONCÉ-UNIQUE", system)
        self.assertIn("Solution officielle=SOLUTION-OFFICIELLE-UNIQUE", system)
        self.assertIn("Soumission étudiant=COPIE-ÉTUDIANTE-UNIQUE", system)
        # the JSON example survives untouched (no str.format mangling)
        self.assertIn('"passed": true ou false', system)
        for placeholder in ("{statement}", "{official_tex}", "{user_submission}"):
            self.assertNotIn(placeholder, system)
        self.assertIn("JSON", user)

    def test_verdict_parser_accepts_french_booleans(self):
        from problems.services import ai_grader

        for raw in ('{"passed": true, "feedback": "ok"}', '{"passed": "vrai", "feedback": "ok"}',
                    '{"passed": "Valide", "feedback": "ok"}'):
            self.assertEqual(ai_grader.parse_verdict(raw)[0], True)
        for raw in ('{"passed": false, "feedback": "non"}', '{"passed": "faux", "feedback": "non"}'):
            self.assertEqual(ai_grader.parse_verdict(raw)[0], False)


class ThemeAndLayoutContractTests(TestCase):
    """Design system contract: le thème est choisi côté client, sans flash, sans dépendance externe.

    Le rendu doit rester autonome : aucune police, feuille de style ou script chargé depuis un
    CDN. On vérifie aussi que la feuille de style expose bien les deux thèmes et que le HTML
    sémantique attendu (rail latéral, cartes de statistiques) est présent.
    """

    def setUp(self):
        self.problem = make_problem(puid="TH 2026/1", hints=2)
        self.client.force_login(make_user("theme-tester"))

    def test_theme_toggle_and_no_flash_bootstrap(self):
        html = self.client.get(reverse("problem-list")).content.decode()

        self.assertIn('id="theme-toggle"', html)
        self.assertIn("arch-theme", html)              # clé localStorage
        self.assertIn("document.documentElement.dataset.theme", html)
        self.assertIn("prefers-color-scheme", html)     # respect du système sans JS
        self.assertIn('class="icon-sun"', html)         # icônes SVG en ligne, pas d'image externe
        self.assertIn('class="icon-moon"', html)

    def test_rendered_pages_load_no_third_party_assets(self):
        for name in ("problem-list", "dashboard"):
            html = self.client.get(reverse(name)).content.decode()
            self.assertNotIn("cdn.jsdelivr.net", html)
            self.assertNotIn("fonts.googleapis", html)
            self.assertNotIn("unpkg.com", html)
            self.assertIn("/static/problems/css/app.css", html)

    def test_stylesheet_ships_both_themes_and_the_layout_hooks(self):
        css = (Path(settings.BASE_DIR) / "problems/static/problems/css/app.css").read_text(encoding="utf-8")

        self.assertIn('data-theme="light"', css)
        for hook in (".topbar", ".problem-card", ".detail-layout", ".detail-aside", ".rail-card",
                     ".stat-card", ".locked-solution", ".hint", ".verdict", ".progress-bar",
                     "@media print", "prefers-reduced-motion"):
            self.assertIn(hook, css, f"la feuille de style doit définir {hook}")
        # la feuille entière est construite sur des jetons : aucune couleur en dur hors du bloc :root
        self.assertIn("--bg:", css)
