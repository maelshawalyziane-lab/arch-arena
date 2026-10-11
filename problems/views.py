"""
Views: the study pages and the verification API.

Security model
--------------
* A problem's official solution text is only ever added to a template context
  when ``UserProgress.is_solved`` is True for the requesting user (see
  ``_solution_context``); locked pages contain no trace of the answer key.
* Hint content is only exposed for hints that already have a HintReveal row.
* ``/api/problems/<id>/verify`` is POST-only, CSRF-protected, throttled, size
  limited, and never echoes the ground truth back to the client.
* Raw grader payloads (``UserSubmission.raw_response``) are staff-only.
"""

from __future__ import annotations

import json
import logging

from django.conf import settings
from django.contrib import messages
from django.contrib.auth import login
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.models import User
from django.db import transaction
from django.db.models import Count, Q
from django.http import Http404, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_GET, require_POST
from django.views.generic import DetailView, ListView, TemplateView

from .models import (
    Category,
    DifficultyTrack,
    Hint,
    HintReveal,
    Problem,
    Solution,
    SubmissionStatus,
    UserProgress,
    UserSubmission,
)
from .services import ai_grader, throttle
from .services.tex import render_rich
from .services.verification import reveal_hint, revealed_hint_ids, verify_submission

logger = logging.getLogger(__name__)


# --------------------------------------------------------------------------- #
# helpers
# --------------------------------------------------------------------------- #
def _client_identity(request) -> str:
    if request.user.is_authenticated:
        return f"user:{request.user.pk}"
    forwarded = request.META.get("HTTP_X_FORWARDED_FOR", "")
    ip = forwarded.split(",")[0].strip() or request.META.get("REMOTE_ADDR", "unknown")
    return f"ip:{ip}"


def _solved_problem_ids(user) -> set[int]:
    if not user or not user.is_authenticated:
        return set()
    return set(
        UserProgress.objects.filter(user=user, is_solved=True).values_list("problem_id", flat=True)
    )


def _solution_context(problem: Problem, solved: bool) -> dict:
    """Return the official-solution context, but ONLY when the gate is open."""
    if not solved:
        return {"solution_html": None, "official_tex": None, "attribution": ""}
    try:
        solution = problem.solution
    except Solution.DoesNotExist:
        return {
            "solution_html": None,
            "official_tex": None,
            "attribution": "",
            "solution_missing": True,
        }
    return {
        "solution_html": render_rich(solution.official_tex),
        "official_tex": solution.official_tex,
        "attribution": solution.attribution,
    }


def _parse_body(request) -> dict:
    if request.content_type and "application/json" in request.content_type:
        try:
            payload = json.loads(request.body.decode("utf-8") or "{}")
            return payload if isinstance(payload, dict) else {}
        except (json.JSONDecodeError, UnicodeDecodeError):
            return {}
    return request.POST.dict()


def _wants_html(request, body: dict) -> bool:
    """True for browser form posts (progressive-enhancement path), False for fetch/API clients."""
    if str(body.get("redirect", "")).lower() in {"1", "true", "yes", "on"}:
        return True
    if "application/json" in (request.content_type or ""):
        return False
    accept = request.headers.get("Accept", "")
    return "text/html" in accept and "application/json" not in accept


# --------------------------------------------------------------------------- #
# study pages
# --------------------------------------------------------------------------- #
#: Préfixe des PUID du corpus importé (voir `ingest_omni_math`).
OMNI_PUID_PREFIX = "OMNI "


def queryset_for_next(*, exclude_ids):
    """Curriculum-ordered queryset used for the "keep going" shortcut on the list page."""
    return Problem.objects.exclude(id__in=exclude_ids).order_by("category", "difficulty_track", "puid")


@login_required
def problem_random_view(request):
    """Redirige vers une fiche tirée au hasard — pratique quand le corpus est vaste.

    Par défaut, on évite ce qui est déjà débloqué : « au hasard » sert à découvrir,
    pas à revoir. ``?scope=all`` tire dans tout le corpus.
    """
    queryset = Problem.objects.all()
    if request.GET.get("scope") != "all":
        queryset = queryset.exclude(id__in=_solved_problem_ids(request.user))
    total = queryset.count()
    if not total:
        messages.info(request, "Toutes les fiches sont déjà débloquées : bravo !")
        return redirect("problem-list")
    pick = queryset.order_by("?").values_list("id", flat=True)[:1][0]
    return redirect("problem-detail", pk=pick)


class ProblemListView(LoginRequiredMixin, ListView):
    """Browse the PUID-indexed ARCH repository with filters."""

    template_name = "problems/problem_list.html"
    context_object_name = "problems"
    paginate_by = 24

    def get_queryset(self):
        # NB: the annotation is called hints_total, not hint_count, because
        # Problem.hint_count is a read-only property.
        queryset = Problem.objects.annotate(hints_total=Count("hints", distinct=True)).prefetch_related(
            "solution"
        )
        params = self.request.GET
        query = params.get("q", "").strip()
        category = params.get("category", "").strip()
        track = params.get("track", "").strip()
        status = params.get("status", "").strip()
        corpus = params.get("corpus", "").strip()

        if query:
            queryset = queryset.filter(
                Q(puid__icontains=query)
                | Q(statement_tex__icontains=query)
                | Q(legacy_puid__icontains=query)
                | Q(hints__content_md__icontains=query)
            ).distinct()
        if category in Category.values:
            queryset = queryset.filter(category=category)
        if track in DifficultyTrack.values:
            queryset = queryset.filter(difficulty_track=track)
        if status == "solved":
            queryset = queryset.filter(id__in=_solved_problem_ids(self.request.user))
        elif status == "unsolved":
            queryset = queryset.exclude(id__in=_solved_problem_ids(self.request.user))
        # Deux corpus cohabitent : les fiches curatées à la main (indices rédigés) et
        # l'import Omni-MATH, reconnaissable à son préfixe de PUID.
        if corpus == "curated":
            queryset = queryset.exclude(puid__startswith=OMNI_PUID_PREFIX)
        elif corpus == "omni":
            queryset = queryset.filter(puid__startswith=OMNI_PUID_PREFIX)

        ordering = params.get("order", "curriculum")
        allowed = {
            "curriculum": ("category", "difficulty_track", "puid"),
            "puid": ("puid",),
            "-puid": ("-puid",),
        }
        return queryset.order_by(*allowed.get(ordering, allowed["curriculum"]))

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        solved_ids = _solved_problem_ids(self.request.user)
        params = self.request.GET
        active_filters = {
            key: params.get(key, "").strip()
            for key in ("q", "category", "track", "status", "corpus")
        }
        status_allows_next = not any(active_filters.values())
        curated_total = Problem.objects.exclude(puid__startswith=OMNI_PUID_PREFIX).count()
        context.update(
            {
                "solved_ids": solved_ids,
                "curated_total": curated_total,
                "omni_total": Problem.objects.count() - curated_total,
                "filters_active": bool(active_filters["q"] or active_filters["category"]
                                       or active_filters["track"] or active_filters["status"]
                                       or active_filters["corpus"]),
                "categories": Category.choices,
                "tracks": DifficultyTrack.choices,
                "current": {
                    "q": self.request.GET.get("q", ""),
                    "category": self.request.GET.get("category", ""),
                    "track": self.request.GET.get("track", ""),
                    "status": active_filters["status"],
                    "corpus": active_filters["corpus"],
                    "order": self.request.GET.get("order", "curriculum"),
                },
                "total_problems": Problem.objects.count(),
                "total_solved": len(solved_ids),
                "grader_label": ai_grader.grader_label(),
                # "Continuer l'entraînement" → the first unsolved problem in curriculum order
                "next_problem": (
                    queryset_for_next(exclude_ids=solved_ids).first() if status_allows_next else None
                ),
            }
        )
        return context


class ProblemDetailView(LoginRequiredMixin, DetailView):
    """Statement + tiered hints + submission box + conditionally-gated solution."""

    model = Problem
    template_name = "problems/problem_detail.html"
    context_object_name = "problem"

    def get_object(self, queryset=None) -> Problem:
        return get_object_or_404(
            Problem.objects.select_related("solution").prefetch_related("hints"), pk=self.kwargs["pk"]
        )

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        problem: Problem = context["problem"]
        user = self.request.user
        solved = problem.solved_by(user)

        hints = list(problem.hints.all())
        revealed = revealed_hint_ids(user, problem)
        hint_rows = [
            {
                "hint": hint,
                "revealed": hint.pk in revealed,
                # Content is None for locked hints -> the lock is enforced by the server,
                # not merely by a CSS class.
                "content_html": None if hint.pk not in revealed else _render_hint(hint),
                "is_next": (hint.pk not in revealed)
                and all(h.pk in revealed for h in hints if h.order_index < hint.order_index),
            }
            for hint in hints
        ]

        history = (
            UserSubmission.objects.filter(user=user, problem=problem).order_by("-created_at")
            if user.is_authenticated
            else UserSubmission.objects.none()
        )
        context.update(
            {
                "solved": solved,
                "hint_rows": hint_rows,
                "revealed_count": len(revealed & {h.pk for h in hints}),
                "submissions": history[:25],
                "attempt_count": history.count(),
                "passed_count": history.filter(status=SubmissionStatus.PASSED).count(),
                "grader_label": ai_grader.grader_label(),
                "rate_limit": settings.VERIFY_RATE_LIMIT,
                "rate_remaining": throttle.peek(
                    identity=_client_identity(self.request), limit=settings.VERIFY_RATE_LIMIT
                ),
                "max_submission_chars": settings.MAX_SUBMISSION_CHARS,
                "allow_reset": settings.ALLOW_PROGRESS_RESET,
                "statement_html": render_rich(problem.statement_tex),
                "nav_prev": Problem.objects.filter(pk__lt=problem.pk).order_by("-pk").first(),
                "nav_next": Problem.objects.filter(pk__gt=problem.pk).order_by("pk").first(),
                **_solution_context(problem, solved),
            }
        )
        return context


def _render_hint(hint: Hint) -> str:
    return render_rich(hint.content_md)


class DashboardView(LoginRequiredMixin, TemplateView):
    template_name = "problems/dashboard.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        user = self.request.user
        solved_ids = _solved_problem_ids(user)
        per_category = []
        for value, label in Category.choices:
            total = Problem.objects.filter(category=value).count()
            solved = Problem.objects.filter(category=value, id__in=solved_ids).count()
            per_category.append(
                {
                    "label": label,
                    "value": value,
                    "total": total,
                    "solved": solved,
                    "pct": round(100 * solved / total) if total else 0,
                }
            )
        status_mix = {}
        if user.is_authenticated:
            status_mix = dict(
                UserSubmission.objects.filter(user=user)
                .values_list("status")
                .annotate(n=Count("id"))
            )
        ok, grader_message = ai_grader.ping_grader()
        context.update(
            {
                "total_problems": Problem.objects.count(),
                "total_solved": len(solved_ids),
                "per_category": per_category,
                "status_mix": status_mix,
                "recent_submissions": (
                    UserSubmission.objects.filter(user=user).select_related("problem")[:8]
                    if user.is_authenticated
                    else []
                ),
                "recent_unlocks": (
                    UserProgress.objects.filter(user=user, is_solved=True)
                    .select_related("problem")
                    .order_by("-unlocked_at")[:8]
                    if user.is_authenticated
                    else []
                ),
                "hints_opened": (
                    HintReveal.objects.filter(user=user).count() if user.is_authenticated else 0
                ),
                "grader_ok": ok,
                "grader_label": ai_grader.grader_label(),
                "grader_message": grader_message,
                "today": timezone.now(),
            }
        )
        return context


# --------------------------------------------------------------------------- #
# verification API
# --------------------------------------------------------------------------- #
@require_POST
def verify_submission_view(request, pk: int):
    """
    ``POST /api/problems/<id>/verify``  body: ``{"text": "<solution outline>"}``

    Response (JSON):
        {"success": true, "unlocked": true|false, "status": "PASSED"|"REJECTED",
         "feedback": "...", "engine": "...", "latency_ms": 1234}

    Status codes: 200 graded · 400 bad request · 404 unknown problem ·
    422 missing ground truth / too long · 429 throttled · 503 grader unreachable.
    """
    if not request.user.is_authenticated:
        # DEMO_MODE=0: progress belongs to a real account. (With DEMO_MODE=1 the
        # middleware has already attached the guest account.)
        return JsonResponse(
            {
                "success": False,
                "unlocked": False,
                "error": "authentication_required",
                "feedback": "Connectez-vous pour soumettre une solution : la progression est liée au compte.",
            },
            status=403,
        )
    problem = get_object_or_404(Problem, pk=pk)
    body = _parse_body(request)
    text = (body.get("text") or body.get("submission") or "").strip()

    if not text:
        return JsonResponse(
            {
                "success": False,
                "unlocked": False,
                "error": "empty_submission",
                "feedback": "Écrivez un plan de solution avant de soumettre.",
            },
            status=400,
        )

    gate = throttle.hit(
        identity=_client_identity(request),
        limit=settings.VERIFY_RATE_LIMIT,
        window_seconds=settings.VERIFY_RATE_WINDOW_SECONDS,
    )
    if not gate.allowed:
        payload = {
            "success": False,
            "unlocked": False,
            "error": "rate_limited",
            "feedback": (
                f"Quota atteint ({settings.VERIFY_RATE_LIMIT} soumissions par "
                f"{settings.VERIFY_RATE_WINDOW_SECONDS // 60} minutes). Réessayez dans environ "
                f"{max(1, gate.retry_after // 60)} minute(s)."
            ),
            "retry_after": gate.retry_after,
        }
        response = JsonResponse(payload, status=429)
        response["Retry-After"] = str(gate.retry_after)
        return response

    result = verify_submission(user=request.user, problem=problem, text=text)
    status_code = {
        "PASSED": 200,
        "REJECTED": 200,
        "PENDING": 503,
        "ERROR": 422,
    }.get(result.status, 200)

    if _wants_html(request, body):  # progressive-enhancement fallback (no JS)
        if result.status == SubmissionStatus.PASSED:
            messages.success(request, f"Solution débloquée ! {result.feedback}")
        elif result.status == SubmissionStatus.REJECTED:
            messages.warning(request, f"Pas encore accepté : {result.feedback}")
        else:
            messages.error(request, result.feedback)
        return redirect("problem-detail", pk=problem.pk)

    payload = result.as_dict()
    payload["rate_remaining"] = gate.remaining
    return JsonResponse(payload, status=status_code)


@require_POST
def reveal_hint_view(request, pk: int, hint_id: int):
    """``POST /api/problems/<id>/hints/<hint_id>/reveal`` - open exactly the next hint."""
    if not request.user.is_authenticated:
        return JsonResponse(
            {"success": False, "error": "authentication_required", "feedback": "Connectez-vous pour ouvrir les indices."},
            status=403,
        )
    problem = get_object_or_404(Problem, pk=pk)
    hint = get_object_or_404(Hint, pk=hint_id, problem=problem)
    ok, message = reveal_hint(user=request.user, problem=problem, hint=hint)
    if not ok:
        revealed = revealed_hint_ids(request.user, problem)
        hint_ids = list(problem.hints.order_by("order_index").values_list("pk", flat=True))
        payload = {
            "success": False,
            "error": "hint_locked",
            "feedback": message,
            "revealed_count": len(revealed),
            "next_hint_id": next((hint_id for hint_id in hint_ids if hint_id not in revealed), None),
        }
        return JsonResponse(payload, status=409)
    from .services.tex import render_rich

    revealed = revealed_hint_ids(request.user, problem)
    return JsonResponse(
        {
            "success": True,
            "hint_id": hint.pk,
            "order_index": hint.order_index,
            "content_html": render_rich(hint.content_md),
            "revealed_count": len(revealed),
            "hint_count": problem.hints.count(),
        }
    )


@require_GET
def problem_status_view(request, pk: int):
    """Lightweight polling endpoint used by the client after an async grade."""
    problem = get_object_or_404(Problem, pk=pk)
    solved = problem.solved_by(request.user)
    latest = None
    if request.user.is_authenticated:
        latest_submission = (
            UserSubmission.objects.filter(user=request.user, problem=problem).order_by("-created_at").first()
        )
        if latest_submission:
            latest = {
                "id": latest_submission.pk,
                "status": latest_submission.status,
                "feedback": latest_submission.ai_feedback,
                "engine": latest_submission.engine,
                "created_at": latest_submission.created_at.isoformat(),
            }
    revealed = revealed_hint_ids(request.user, problem)
    hint_ids = list(problem.hints.order_by("order_index").values_list("pk", flat=True))
    next_hint_id = next((hint_id for hint_id in hint_ids if hint_id not in revealed), None)
    progress = (
        UserProgress.objects.filter(user=request.user, problem=problem).first()
        if request.user.is_authenticated
        else None
    )
    return JsonResponse(
        {
            # stable, documented contract (see docs/API.md)
            "success": True,
            "problem_id": problem.pk,
            "puid": problem.puid,
            "is_solved": solved,
            "unlocked_at": progress.unlocked_at.isoformat() if progress and progress.unlocked_at else None,
            "hints_total": len(hint_ids),
            "hints_revealed": len(revealed),
            "next_hint_id": next_hint_id,
            "submissions": (
                UserSubmission.objects.filter(user=request.user, problem=problem).count()
                if request.user.is_authenticated
                else 0
            ),
            "can_verify": hasattr(problem, "solution"),
            # kept for the existing client helper
            "problem_puid": problem.puid,
            "unlocked": solved,
            "revealed_hints": len(revealed),
            "hint_count": len(hint_ids),
            "latest_submission": latest,
            "rate_remaining": throttle.peek(
                identity=_client_identity(request), limit=settings.VERIFY_RATE_LIMIT
            ),
        }
    )


@require_POST
def reset_progress_view(request, pk: int):
    """Demo/dev utility: re-lock a problem for the current user (never touches other users)."""
    if not settings.ALLOW_PROGRESS_RESET:
        return JsonResponse({"success": False, "error": "disabled"}, status=403)
    problem = get_object_or_404(Problem, pk=pk)
    if not request.user.is_authenticated:
        return JsonResponse({"success": False, "error": "authentication_required"}, status=403)
    with transaction.atomic():
        UserSubmission.objects.filter(user=request.user, problem=problem).delete()
        HintReveal.objects.filter(user=request.user, hint__problem=problem).delete()
        UserProgress.objects.filter(user=request.user, problem=problem).delete()
    return JsonResponse({"success": True, "unlocked": False, "feedback": "Progression réinitialisée pour cette fiche."})


# --------------------------------------------------------------------------- #
# accounts
# --------------------------------------------------------------------------- #
def signup_view(request):
    """Inscription fermée : la plateforme n'ouvre qu'un seul compte.

    L'URL est conservée (des liens existent) mais elle explique la règle au lieu de
    créer un compte. Pour en ouvrir d'autres, passez ``ALLOW_SIGNUP=1`` : le
    formulaire historique réapparaît, utile pour un déploiement multi-utilisateurs.
    """
    if settings.ALLOW_SIGNUP:
        if request.method == "POST":
            form = UserCreationForm(request.POST)
            if form.is_valid():
                user: User = form.save()
                login(request, user)
                messages.success(request, "Bienvenue ! Votre progression sera enregistrée sur ce compte.")
                return redirect("dashboard")
        else:
            form = UserCreationForm()
        return render(request, "registration/signup.html", {"form": form})

    return render(request, "registration/signup_closed.html", status=403)


@login_required
def dashboard_redirect(request):  # pragma: no cover - convenience alias
    return redirect("dashboard")
