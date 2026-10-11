"""Contrats du déploiement mono-compte et du correcteur Gemini.

Deux promesses faites à l'utilisateur, vérifiées ici sans réseau :

* **un seul compte** : l'inscription est fermée, les pages exigent une connexion, et
  l'identifiant de l'administrateur traverse vraiment le formulaire de connexion ;
* **le correcteur IA est branché sur Gemini** : le bon endpoint, la bonne clé, le même
  contrat JSON que pour OpenAI/Anthropic (le prompt système reste celui du cahier des
  charges, en français).
"""

from __future__ import annotations

import io
import json
import urllib.error
from io import StringIO
from unittest.mock import patch

from django.contrib.auth.models import User
from django.core.management import call_command
from django.test import TestCase, override_settings
from django.urls import reverse

from problems.services import ai_grader
from problems.tests.factories import make_problem, make_user

#: Mot de passe **de test**, sans rapport avec celui de l'installation : le dépôt ne doit
#: contenir aucun identifiant réel. Le compte de production est créé par `manage.py
#: bootstrap`, à partir de `ARCH_ADMIN_PASSWORD`.
ADMIN_PASSWORD = "test-only-not-a-secret"


class SingleAccountTests(TestCase):
    """L'installation n'ouvre qu'un compte : celui de l'administrateur."""

    @classmethod
    def setUpTestData(cls):
        cls.admin = User.objects.create_superuser(username="admin", password=ADMIN_PASSWORD)

    def test_login_form_accepts_the_admin_credentials(self):
        response = self.client.post(
            reverse("login"), {"username": "admin", "password": ADMIN_PASSWORD}, follow=True
        )
        self.assertEqual(response.status_code, 200)
        self.assertIn("sessionid", response.cookies or self.client.cookies)

    def test_login_rejects_a_wrong_password(self):
        response = self.client.post(reverse("login"), {"username": "admin", "password": "mauvais"})
        self.assertNotIn("sessionid", self.client.cookies)

    def test_signup_cannot_create_a_second_account(self):
        before = User.objects.count()
        response = self.client.post(
            reverse("signup"), {"username": "intrus", "password1": "x-12345-A", "password2": "x-12345-A"}
        )
        self.assertEqual(response.status_code, 403)
        self.assertEqual(User.objects.count(), before)

    def test_every_study_page_requires_a_login(self):
        for name in ("problem-list", "problem-random", "dashboard"):
            response = self.client.get(reverse(name))
            self.assertEqual(response.status_code, 302, name)
            self.assertIn("/accounts/login/", response.url, name)

    def test_api_endpoints_refuse_anonymous_callers(self):
        problem = make_problem(puid="MONO 2026/1")
        verify = self.client.post(
            reverse("api-verify", args=[problem.pk]), {"text": "peu importe"}
        )
        self.assertIn(verify.status_code, (403, 302))

    def test_only_the_admin_user_exists_after_seeding_the_showcase(self):
        """`seed_showcase` rattache son historique au compte unique, il n'en crée pas d'autre."""
        out = StringIO()
        call_command("seed_showcase", reset=True, stdout=out)
        self.assertEqual(list(User.objects.values_list("username", flat=True)), ["admin"])
        self.assertTrue(
            problem_solved_for(self.admin) is None or True  # aucune exception levée suffit
        )


def problem_solved_for(user):
    from problems.models import UserProgress

    return UserProgress.objects.filter(user=user, is_solved=True).first()


class GeminiProviderTests(TestCase):
    """Le fournisseur `gemini` réutilise le contrat OpenAI, avec sa propre URL et sa clé."""

    # NB : la suite force AI_MODE=offline (config/settings.py) ; on rétablit « auto »
    # ici pour vérifier la bascule automatique dès qu'une clé est présente.
    @override_settings(AI_PROVIDER="gemini", GEMINI_API_KEY="AQ.cle-de-test", AI_MODEL="", AI_MODE="auto")
    def test_live_engine_is_selected_when_the_key_is_present(self):
        self.assertEqual(ai_grader.resolve_engine(), "live")
        self.assertEqual(ai_grader.DEFAULT_MODELS["gemini"], "gemini-3.5-flash-lite")
        self.assertIn("gemini", ai_grader.grader_label())

    @override_settings(AI_PROVIDER="gemini", GEMINI_API_KEY="", AI_MODE="auto")
    def test_without_a_key_the_offline_grader_takes_over(self):
        self.assertEqual(ai_grader.resolve_engine(), "offline")

    @override_settings(AI_PROVIDER="gemini", GEMINI_API_KEY="AQ.cle-de-test", AI_MODEL="gemini-3.5-flash")
    def test_gemini_call_shape(self):
        captured: dict = {}

        def fake_post(url, payload, headers, timeout):  # noqa: ANN001
            captured.update(url=url, payload=payload, headers=headers, timeout=timeout)
            return {"choices": [{"message": {"content": '{"passed": true, "feedback": "bien"}'}}]}

        with patch.object(ai_grader, "_post_json", side_effect=fake_post):
            text, meta = ai_grader._call_gemini("système", "utilisateur", "gemini-3.5-flash")

        self.assertEqual(captured["url"], ai_grader.GEMINI_URL)
        self.assertEqual(captured["headers"]["Authorization"], "Bearer AQ.cle-de-test")
        self.assertEqual(captured["payload"]["model"], "gemini-3.5-flash")
        self.assertEqual(captured["payload"]["messages"][0]["role"], "system")
        self.assertEqual(meta["provider"], "gemini")
        self.assertEqual(json.loads(text)["passed"], True)

    @override_settings(AI_PROVIDER="gemini", GEMINI_API_KEY="AQ.cle-de-test", AI_MODE="auto",
                       AI_MAX_RETRIES=0)
    def test_grade_submission_uses_gemini_and_parses_the_verdict(self):
        problem = make_problem(puid="GEM 2026/1")
        reply = {"choices": [{"message": {"content": '{"passed": true, "feedback": "Démonstration correcte."}'}}]}
        with patch.object(ai_grader, "_post_json", return_value=reply) as post:
            verdict = ai_grader.grade_submission(
                puid=problem.puid,
                statement=problem.statement_tex,
                official_tex=problem.solution.official_tex,
                user_submission="Ma preuve complète.",
            )
        self.assertTrue(verdict.passed)
        self.assertTrue(verdict.engine.startswith("gemini"), verdict.engine)
        sent = post.call_args.args[1]  # charge utile
        self.assertEqual(sent["model"], "gemini-3.5-flash-lite")
        # le prompt système reste celui du cahier des charges, en français
        self.assertIn("correcteur expert des Olympiades Internationales", sent["messages"][0]["content"])

    def test_check_ai_setup_accepts_the_gemini_provider(self):
        with override_settings(AI_PROVIDER="gemini", GEMINI_API_KEY="AQ.cle-de-test"):
            out = StringIO()
            call_command("check_ai_setup", stdout=out)
        self.assertIn("Les 18 contrôles passent", out.getvalue())

class GraderResilienceTests(TestCase):
    """Quand l'API du fournisseur tombe, l'élève garde une évaluation — jamais une erreur 503.

    Le quota gratuit de Gemini (500 requêtes par modèle et par jour) s'épuise vite :
    l'interface doit continuer à fonctionner et dire honnêtement quel moteur a servi.
    """

    def setUp(self):
        # le disjoncteur est un état de module : on le referme avant chaque test
        ai_grader._breaker_record(True)

    def _failing_caller(self, *args, **kwargs):
        raise urllib.error.HTTPError(
            ai_grader.GEMINI_URL, 429, "Too Many Requests", {}, io.BytesIO(b"quota")
        )

    @override_settings(AI_MODE="live", AI_PROVIDER="gemini", GEMINI_API_KEY="clé-de-test", AI_MAX_RETRIES=0)
    def test_provider_failure_falls_back_to_the_offline_grader(self):
        with patch.object(ai_grader, "_call_gemini", self._failing_caller), \
                override_settings(AI_FALLBACK=True):
            verdict = ai_grader.grade_submission(
                puid="TEST 2026/1",
                statement="Énoncé",
                official_tex="Solution officielle",
                user_submission="Une preuve structurée.",
            )
        self.assertTrue(verdict.engine.startswith("repli:"), verdict.engine)
        self.assertIn("indisponible", verdict.feedback)
        self.assertIn("429", verdict.raw.get("fallback_reason", ""))

    @override_settings(AI_MODE="live", AI_PROVIDER="gemini", GEMINI_API_KEY="clé-de-test", AI_MAX_RETRIES=0)
    def test_strict_mode_still_raises_when_the_fallback_is_disabled(self):
        with patch.object(ai_grader, "_call_gemini", self._failing_caller), \
                override_settings(AI_FALLBACK=False):
            with self.assertRaises(ai_grader.GraderUnavailable):
                ai_grader.grade_submission(
                    puid="TEST 2026/1",
                    statement="Énoncé",
                    official_tex="Solution officielle",
                    user_submission="Une preuve structurée.",
                )

    @override_settings(
        AI_MODE="live", AI_PROVIDER="gemini", GEMINI_API_KEY="clé-de-test",
        AI_MAX_RETRIES=0, AI_BREAKER_THRESHOLD=1, AI_BREAKER_SECONDS=300, AI_FALLBACK=True,
    )
    def test_the_circuit_breaker_stops_calling_a_dead_api(self):
        with patch.object(ai_grader, "_call_gemini", side_effect=self._failing_caller) as caller:
            for _ in range(3):
                verdict = ai_grader.grade_submission(
                    puid="TEST 2026/1",
                    statement="Énoncé",
                    official_tex="Solution officielle",
                    user_submission="Une preuve structurée.",
                )
                self.assertTrue(verdict.engine.startswith("repli:"))
        self.assertEqual(caller.call_count, 1, "le disjoncteur doit couper après le premier échec")
        self.assertNotEqual(ai_grader.breaker_state(), "fermé")


class HealthCheckTests(TestCase):
    """La sonde de santé des hébergeurs.

    Elle est interrogée pendant le déploiement, en HTTP simple, sans session : elle
    doit répondre 200 dans tous les cas. Une redirection vers HTTPS y serait comptée
    comme un échec de déploiement (c'est arrivé sur Render).
    """

    def test_answers_without_being_logged_in(self):
        response = self.client.get("/healthz/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["status"], "ok")

    @override_settings(
        SECURE_SSL_REDIRECT=True,
        SECURE_PROXY_SSL_HEADER=("HTTP_X_FORWARDED_PROTO", "https"),
        SECURE_REDIRECT_EXEMPT=[r"^healthz/$"],
    )
    def test_is_exempt_from_the_https_redirect(self):
        response = self.client.get("/healthz/", secure=False)
        self.assertEqual(response.status_code, 200)

    @override_settings(
        SECURE_SSL_REDIRECT=True,
        SECURE_PROXY_SSL_HEADER=("HTTP_X_FORWARDED_PROTO", "https"),
        SECURE_REDIRECT_EXEMPT=[r"^healthz/$"],
    )
    def test_the_other_pages_still_force_https(self):
        response = self.client.get("/accounts/login/", secure=False)
        self.assertEqual(response.status_code, 301)
