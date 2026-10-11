"""
Tests for the AI verification gate: the lock must be real, the unlock must be
earned, and infrastructure failures must never be reported as mathematical ones.
"""

from __future__ import annotations

import json
from unittest import mock

from django.test import TestCase, override_settings
from django.urls import reverse

from problems.models import (
    HintReveal,
    SubmissionStatus,
    UserProgress,
    UserSubmission,
)
from problems.services import ai_grader
from problems.services.verification import verify_submission

from .factories import STRONG_SUBMISSION, WEAK_SUBMISSION, make_problem, make_user

# Distinctive fragments that appear ONLY in the official solution (OFFICIAL_TEX).
# A bare word like "Vieta" is not used as the sentinel because the student's own
# submitted outline legitimately appears in their grading history.
SOLUTION_SENTINELS = ("contradicting minimality", "always a perfect square", "\blacksquare")


class LockedStateTests(TestCase):
    """The answer key must not reach a client that has not unlocked the problem."""

    @classmethod
    def setUpTestData(cls):
        cls.problem = make_problem()
        cls.user = make_user()

    def test_locked_page_never_contains_the_official_solution(self):
        self.client.force_login(self.user)
        response = self.client.get(self.problem.get_absolute_url())
        body = response.content.decode()
        self.assertEqual(response.status_code, 200)
        self.assertIn("Solution officielle verrouillée", body)
        # distinctive fragments of the answer key must be absent
        for fragment in SOLUTION_SENTINELS:
            self.assertNotIn(fragment, body)
        self.assertNotIn(self.problem.answer_tex, body)
        # and the model's solution must not be serialised anywhere in the payload
        self.assertNotIn(self.problem.solution.official_tex[:60], body)

    def test_anonymous_visitor_is_sent_to_the_login_page(self):
        """Installation mono-compte : rien n'est visible sans connexion."""
        self.client.logout()
        response = self.client.get(self.problem.get_absolute_url())
        self.assertEqual(response.status_code, 302)
        self.assertIn("/accounts/login/", response.url)
        # la page de connexion elle-même ne divulgue aucune solution
        login_page = self.client.get(response.url).content.decode()
        for fragment in SOLUTION_SENTINELS:
            self.assertNotIn(fragment, login_page)

    @override_settings(DEMO_MODE=True)
    def test_demo_mode_guest_sees_the_same_locked_state(self):
        """Le mode démonstration historique (compte invité partagé) reste verrouillé pareil."""
        self.client.logout()
        response = self.client.get(self.problem.get_absolute_url())
        body = response.content.decode()
        self.assertEqual(response.status_code, 200)
        for fragment in SOLUTION_SENTINELS:
            self.assertNotIn(fragment, body)


@override_settings(DEMO_MODE=False, VERIFY_RATE_LIMIT=0)
class VerificationApiTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.problem = make_problem()
        cls.user = make_user()

    def setUp(self):
        self.client.force_login(self.user)
        self.url = reverse("api-verify", args=[self.problem.pk])

    def _post(self, text: str):
        return self.client.post(
            self.url, data=json.dumps({"text": text}), content_type="application/json"
        )

    # ------------------------------------------------------------ contract #
    def test_rejected_submission_keeps_the_gate_closed(self):
        response = self._post(WEAK_SUBMISSION)
        payload = response.json()
        self.assertEqual(response.status_code, 200)
        self.assertTrue(payload["success"])
        self.assertFalse(payload["unlocked"])
        self.assertEqual(payload["status"], SubmissionStatus.REJECTED)

        submission = UserSubmission.objects.get(user=self.user, problem=self.problem)
        self.assertEqual(submission.status, SubmissionStatus.REJECTED)
        self.assertTrue(submission.ai_feedback)
        self.assertFalse(UserProgress.objects.filter(user=self.user, problem=self.problem, is_solved=True).exists())

        # page still locked
        body = self.client.get(self.problem.get_absolute_url()).content.decode()
        for fragment in SOLUTION_SENTINELS:
            self.assertNotIn(fragment, body)
        self.assertIn("Solution officielle verrouillée", body)

    def test_passing_submission_unlocks_and_reveals_the_solution(self):
        response = self._post(STRONG_SUBMISSION)
        payload = response.json()
        self.assertEqual(response.status_code, 200)
        self.assertTrue(payload["unlocked"])
        self.assertEqual(payload["status"], SubmissionStatus.PASSED)

        progress = UserProgress.objects.get(user=self.user, problem=self.problem)
        self.assertTrue(progress.is_solved)
        self.assertIsNotNone(progress.unlocked_at)

        body = self.client.get(self.problem.get_absolute_url()).content.decode()
        self.assertIn("✓ Solution débloquée", body)
        self.assertIn("contradicting minimality", body)  # the official solution is now served

    def test_already_unlocked_submissions_are_archived_not_regraded(self):
        UserProgress.objects.create(user=self.user, problem=self.problem, is_solved=True)
        with mock.patch("problems.services.ai_grader.grade_submission") as grader:
            payload = self._post(WEAK_SUBMISSION).json()
        grader.assert_not_called()
        self.assertTrue(payload["unlocked"])
        self.assertEqual(payload["engine"], "archived")

    def test_empty_submission_is_a_client_error(self):
        response = self._post("   ")
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["error"], "empty_submission")
        self.assertEqual(UserSubmission.objects.count(), 0)

    @override_settings(MAX_SUBMISSION_CHARS=120)
    def test_oversized_submission_is_rejected_without_grading(self):
        response = self._post("x" * 500)
        self.assertEqual(response.status_code, 422)
        self.assertEqual(response.json()["error"], "submission_too_long")
        self.assertEqual(UserSubmission.objects.count(), 0)

    def test_missing_ground_truth_is_reported_as_configuration_problem(self):
        bare = make_problem(puid="TEST 2026/2", with_solution=False)
        response = self.client.post(
            reverse("api-verify", args=[bare.pk]),
            data=json.dumps({"text": STRONG_SUBMISSION}),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 422)
        self.assertEqual(response.json()["error"], "missing_ground_truth")
        self.assertFalse(UserProgress.objects.filter(problem=bare, is_solved=True).exists())

    def test_get_is_not_allowed(self):
        self.assertEqual(self.client.get(self.url).status_code, 405)

    def test_authentication_is_required_outside_demo_mode(self):
        self.client.logout()
        response = self._post(STRONG_SUBMISSION)
        self.assertEqual(response.status_code, 403)
        self.assertEqual(response.json()["error"], "authentication_required")

    # ------------------------------------------------- infrastructure faults #
    @override_settings(VERIFY_RATE_LIMIT=2, VERIFY_RATE_WINDOW_SECONDS=60)
    def test_rate_limit_returns_429_and_retry_after(self):
        self.assertEqual(self._post(WEAK_SUBMISSION).status_code, 200)
        self.assertEqual(self._post(WEAK_SUBMISSION).status_code, 200)
        response = self._post(WEAK_SUBMISSION)
        self.assertEqual(response.status_code, 429)
        self.assertEqual(response.json()["error"], "rate_limited")
        self.assertIn("Retry-After", response.headers)

    @override_settings(VERIFY_RATE_LIMIT=0)
    def test_grader_outage_yields_pending_not_rejected(self):
        with mock.patch(
            "problems.services.ai_grader.grade_submission",
            side_effect=ai_grader.GraderUnavailable("simulated outage"),
        ):
            response = self._post(STRONG_SUBMISSION)
        payload = response.json()
        self.assertEqual(response.status_code, 503)
        self.assertEqual(payload["error"], "grader_unavailable")
        self.assertFalse(payload["unlocked"])
        self.assertEqual(payload["status"], SubmissionStatus.PENDING)
        self.assertFalse(payload["success"])  # nothing was graded
        submission = UserSubmission.objects.get(user=self.user, problem=self.problem)
        self.assertEqual(submission.status, SubmissionStatus.PENDING)
        self.assertFalse(UserProgress.objects.filter(user=self.user, problem=self.problem).exists())

    def test_parse_verdict_tolerates_real_world_model_output(self):
        cases = [
            ('{"passed": true, "feedback": "ok"}', True),
            ('```json\n{"passed": false, "feedback": "gap"}\n```', False),
            ('Sure!\n{"passed": "true", "feedback": "looks right"}', True),
            ('{"verdict": "fail", "explanation": "the case a = b is missing"}', False),
        ]
        for raw, expected in cases:
            passed, feedback = ai_grader.parse_verdict(raw)
            self.assertIs(passed, expected, raw)
            self.assertTrue(feedback)

    def test_parse_verdict_rejects_garbage(self):
        for raw in ("", "no json here", '{"foo": 1}'):
            # Must be BOTH: a ValueError for parsing callers, and a
            # GraderUnavailable so the API stores the attempt as PENDING (a
            # malformed model reply must never be graded as a student failure).
            with self.assertRaises(ai_grader.GraderUnavailable):
                ai_grader.parse_verdict(raw)
            with self.assertRaises(ValueError):
                ai_grader.parse_verdict(raw)

    # --------------------------------------------------------------- service #
    def test_service_marks_progress_atomically_and_logs_the_engine(self):
        result = verify_submission(
            user=self.user, problem=self.problem, text=STRONG_SUBMISSION
        )
        self.assertTrue(result.unlocked)
        submission = UserSubmission.objects.get(pk=result.submission_id)
        self.assertEqual(submission.engine, "offline-heuristic")
        self.assertIsNotNone(submission.latency_ms)
        self.assertTrue(submission.raw_response)  # audit trail for staff

    def test_progress_is_per_user(self):
        other = make_user("other")
        verify_submission(user=self.user, problem=self.problem, text=STRONG_SUBMISSION)
        self.assertTrue(self.problem.solved_by(self.user))
        self.assertFalse(self.problem.solved_by(other))


@override_settings(DEMO_MODE=False)
class HintGatingTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.problem = make_problem(hints=4)
        cls.user = make_user()

    def setUp(self):
        self.client.force_login(self.user)

    def hint_at(self, order: int):
        return self.problem.hints.get(order_index=order)

    def reveal(self, order: int):
        hint = self.hint_at(order)
        return self.client.post(reverse("api-hint-reveal", args=[self.problem.pk, hint.pk]))

    def test_hints_open_in_order(self):
        self.assertEqual(self.reveal(2).status_code, 409)
        self.assertEqual(self.reveal(3).status_code, 409)
        self.assertEqual(self.reveal(1).status_code, 200)
        self.assertEqual(self.reveal(2).status_code, 200)
        self.assertEqual(self.reveal(4).status_code, 409)
        self.assertEqual(self.reveal(3).status_code, 200)

    def test_hint_text_is_withheld_until_revealed(self):
        body = self.client.get(self.problem.get_absolute_url()).content.decode()
        self.assertNotIn("Tier 1 hint", body)
        self.reveal(1)
        body = self.client.get(self.problem.get_absolute_url()).content.decode()
        self.assertIn("Tier 1 hint", body)
        self.assertNotIn("Tier 2 hint", body)
        self.assertEqual(HintReveal.objects.filter(user=self.user).count(), 1)

    def test_reveal_is_idempotent(self):
        self.reveal(1)
        self.reveal(1)
        self.assertEqual(HintReveal.objects.filter(user=self.user).count(), 1)

    def test_cannot_reveal_another_problems_hint(self):
        other = make_problem(puid="TEST 2026/9", hints=2)
        foreign = other.hints.get(order_index=1)
        response = self.client.post(reverse("api-hint-reveal", args=[self.problem.pk, foreign.pk]))
        self.assertEqual(response.status_code, 404)

    def test_reset_relocks_the_problem_for_the_current_user_only(self):
        self.reveal(1)
        verify_submission(user=self.user, problem=self.problem, text=STRONG_SUBMISSION)
        other = make_user("persistent")
        UserProgress.objects.create(user=other, problem=self.problem, is_solved=True)

        response = self.client.post(reverse("api-reset", args=[self.problem.pk]))
        self.assertEqual(response.status_code, 200)
        self.assertFalse(UserProgress.objects.filter(user=self.user, problem=self.problem).exists())
        self.assertFalse(HintReveal.objects.filter(user=self.user).exists())
        self.assertTrue(UserProgress.objects.filter(user=other, problem=self.problem).exists())

    @override_settings(ALLOW_PROGRESS_RESET=False)
    def test_reset_can_be_disabled(self):
        response = self.client.post(reverse("api-reset", args=[self.problem.pk]))
        self.assertEqual(response.status_code, 403)
