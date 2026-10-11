"""
Submission -> grading -> unlock orchestration (the transactional heart of the app).

Spec mapping
------------
Step A  fetch ``Solution.official_tex`` for the target problem          -> _fetch_ground_truth
Step B  receive the student's text from the request                      -> verify_submission(text=...)
Step C  build the strict evaluation payload and call the LLM             -> ai_grader.grade_submission
Step D  parse the verdict, persist UserSubmission and update UserProgress -> _persist

Design notes
------------
* The whole write phase runs in a single ``transaction.atomic()`` block, so a
  crash mid-way can never leave a PASSED submission without an unlocked problem.
* If the grader is unreachable the submission is stored as ``PENDING`` (not
  REJECTED): infrastructure failure must never be reported to the student as a
  mathematical failure, and a retry/teacher override can resolve it later.
* A problem that is already solved is not re-graded - that keeps the gate honest
  (the solution is already visible) and avoids burning LLM budget.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

from django.conf import settings
from django.db import transaction
from django.utils import timezone

from ..models import Hint, HintReveal, Problem, Solution, SubmissionStatus, UserProgress, UserSubmission
from . import ai_grader

logger = logging.getLogger(__name__)


@dataclass
class VerificationResult:
    success: bool
    unlocked: bool
    status: str
    feedback: str
    engine: str
    latency_ms: int | None = None
    error: str | None = None
    submission_id: int | None = None

    def as_dict(self) -> dict:
        payload = {
            "success": self.success,
            "unlocked": self.unlocked,
            "status": self.status,
            "feedback": self.feedback,
            "engine": self.engine,
        }
        if self.latency_ms is not None:
            payload["latency_ms"] = self.latency_ms
        if self.submission_id is not None:
            payload["submission_id"] = self.submission_id
        if self.error:
            payload["error"] = self.error
        return payload


def _fetch_ground_truth(problem: Problem) -> str:
    """Step A - the answer key. Raises ``Solution.DoesNotExist`` when missing."""
    solution: Solution = problem.solution  # OneToOne reverse accessor
    return solution.official_tex


def verify_submission(*, user, problem: Problem, text: str, mode: str | None = None) -> VerificationResult:
    """Run the full gate for one submission. Never raises for grader/network issues."""
    engine_label = ai_grader.grader_label()
    submission_text = (text or "").strip()

    if not submission_text:
        return VerificationResult(
            success=False, unlocked=False, status="ERROR", engine=engine_label,
            feedback="Écrivez un plan de solution avant de soumettre.", error="empty_submission",
        )
    if len(submission_text) > settings.MAX_SUBMISSION_CHARS:
        return VerificationResult(
            success=False, unlocked=False, status="ERROR", engine=engine_label,
            feedback=(f"Soumission trop longue ({len(submission_text)} > "
                      f"{settings.MAX_SUBMISSION_CHARS} caractères)."),
            error="submission_too_long",
        )

    try:
        official_tex = _fetch_ground_truth(problem)
    except Solution.DoesNotExist:
        return VerificationResult(
            success=False, unlocked=False, status="ERROR", engine=engine_label,
            feedback=(
                "Cette fiche n'a pas encore de solution officielle : le verrou IA ne peut pas "
                "être évalué. Ajoutez une solution (admin) ou relancez l'ingestion avec une "
                "source qui contient les solutions."
            ),
            error="missing_ground_truth",
        )

    progress = UserProgress.objects.filter(user=user, problem=problem).first()
    if progress and progress.is_solved:
        # Already unlocked: record the attempt for the history log, do not spend tokens.
        submission = UserSubmission.objects.create(
            user=user,
            problem=problem,
            submitted_text=submission_text,
            status=SubmissionStatus.PASSED,
            ai_feedback="Solution déjà débloquée : soumission archivée sans nouvelle évaluation.",
            engine="archived",
        )
        return VerificationResult(
            success=True,
            unlocked=True,
            status=SubmissionStatus.PASSED,
            feedback="La solution officielle est déjà débloquée ; cette soumission a été archivée sans nouvelle évaluation.",
            engine="archived",
            submission_id=submission.pk,
        )

    # Step B + C
    try:
        verdict = ai_grader.grade_submission(
            puid=problem.puid,
            statement=problem.statement_tex,
            official_tex=official_tex,
            user_submission=submission_text,
            mode=mode,
        )
    except ai_grader.GraderUnavailable as exc:
        submission = UserSubmission.objects.create(
            user=user,
            problem=problem,
            submitted_text=submission_text,
            status=SubmissionStatus.PENDING,
            ai_feedback=(
                "Le correcteur IA est injoignable : cette tentative est en attente (PENDING). "
                f"Raison : {exc}. Réessayez dans un instant."
            ),
            engine=engine_label,
        )
        logger.error("grader unavailable puid=%s error=%s", problem.puid, exc)
        return VerificationResult(
            success=False,
            unlocked=False,
            status=SubmissionStatus.PENDING,
            feedback=(
                "Le correcteur IA est momentanément indisponible — votre soumission a été "
                "enregistrée en PENDING et peut être renvoyée. Rien n'a été considéré comme faux."
            ),
            engine=engine_label,
            submission_id=submission.pk,
            error="grader_unavailable",
        )

    # Step D
    return _persist(
        user=user,
        problem=problem,
        submission_text=submission_text,
        verdict=verdict,
    )


def _persist(*, user, problem: Problem, submission_text: str, verdict: ai_grader.GraderVerdict) -> VerificationResult:
    """Step D - persist the verdict and flip the unlock flag atomically."""
    status = SubmissionStatus.PASSED if verdict.passed else SubmissionStatus.REJECTED
    with transaction.atomic():
        submission = UserSubmission.objects.create(
            user=user,
            problem=problem,
            submitted_text=submission_text,
            status=status,
            ai_feedback=verdict.feedback,
            engine=verdict.engine,
            latency_ms=verdict.latency_ms,
            raw_response=verdict.raw or None,
        )
        unlocked = False
        if verdict.passed:
            progress, _ = UserProgress.objects.get_or_create(user=user, problem=problem)
            if progress.is_solved:
                unlocked = True
            else:
                progress.is_solved = True
                progress.unlocked_at = timezone.now()
                progress.save(update_fields=["is_solved", "unlocked_at", "updated_at"])
                unlocked = True
                logger.info("unlocked puid=%s user=%s engine=%s", problem.puid, user, verdict.engine)

    return VerificationResult(
        success=True,
        unlocked=unlocked,
        status=status,
        feedback=verdict.feedback,
        engine=verdict.engine,
        latency_ms=verdict.latency_ms,
        submission_id=submission.pk,
    )


# --------------------------------------------------------------------------- #
# hint gating
# --------------------------------------------------------------------------- #
def revealed_hint_ids(user, problem: Problem) -> set[int]:
    if not user or not user.is_authenticated:
        return set()
    return set(
        HintReveal.objects.filter(user=user, hint__problem=problem).values_list("hint_id", flat=True)
    )


def reveal_hint(*, user, problem: Problem, hint: Hint) -> tuple[bool, str]:
    """
    Reveal one hint, enforcing the "one at a time" rule *server side*.

    Returns ``(ok, message)``.  Hint text is only ever returned to the client once
    the corresponding HintReveal row exists.
    """
    if hint.problem_id != problem.pk:
        return False, "Cet indice n'appartient pas à cette fiche."
    previous = set(
        Hint.objects.filter(problem=problem, order_index__lt=hint.order_index).values_list(
            "order_index", flat=True
        )
    )
    if previous:
        unlocked_orders = set(
            HintReveal.objects.filter(user=user, hint__problem=problem).values_list(
                "hint__order_index", flat=True
            )
        )
        missing = sorted(previous - unlocked_orders)
        if missing:
            return False, f"Ouvrez d'abord l'indice {missing[0]} — les indices s'ouvrent dans l'ordre."
    HintReveal.objects.get_or_create(user=user, hint=hint)
    return True, ""
