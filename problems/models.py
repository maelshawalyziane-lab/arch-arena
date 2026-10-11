"""
Database models for the Math Olympiad self-study platform.

The schema follows the ARCH (Automated Repository of Canned Hints) idea from
Evan Chen's otis-web, extended with the AI-verification gate:

    Problem 1 ──< Hint            (tiered, reveal-one-at-a-time)
            1 ──1 Solution        (OFFICIAL ground truth, never sent to a locked client)
    User ──< UserProgress         (is_solved + unlocked_at  -> the unlock flag)
         ──< UserSubmission       (the audit trail of every grading attempt)
         ──< HintReveal           (server-side record of which hints were opened)

Everything here is standard Django ORM and therefore maps 1:1 onto PostgreSQL
via `manage.py migrate`; sql/schema_postgres.sql is the equivalent hand-written
DDL for teams that manage schema outside Django.
"""

from __future__ import annotations

from django.conf import settings
from django.core.validators import MinValueValidator, RegexValidator
from django.db import models
from django.urls import reverse
from django.utils import timezone


class Category(models.TextChoices):
    """The four canonical olympiad subjects."""

    ALGEBRA = "algebra", "Algèbre"
    COMBINATORICS = "combinatorics", "Combinatoire"
    GEOMETRY = "geometry", "Géométrie"
    NUMBER_THEORY = "number_theory", "Théorie des nombres"
    # Used by the ingestion pipeline for rows whose subject cannot be inferred.
    MISC = "misc", "Non classé"

    @property
    def abbr(self) -> str:
        return {
            Category.ALGEBRA: "A",
            Category.COMBINATORICS: "C",
            Category.GEOMETRY: "G",
            Category.NUMBER_THEORY: "N",
            Category.MISC: "?",
        }[self.value]


class DifficultyTrack(models.TextChoices):
    """Coarse difficulty ladder used for progressive study."""

    FOUNDATION = "foundation", "Initiation"
    OLYMPIAD = "olympiad", "Olympiade"
    HARD = "hard", "Difficile (P3/P6)"


class Problem(models.Model):
    """A single olympiad problem, identified by its human-readable PUID."""

    puid = models.CharField(
        "PUID",
        max_length=120,
        unique=True,
        help_text='Human readable Problem Unique ID, e.g. "IMO 2016/4", "USAMO 2018/3".',
        validators=[
            RegexValidator(
                regex=r"^\S(.*\S)?$",
                message="A PUID may not start or end with whitespace or be empty.",
            )
        ],
    )
    legacy_puid = models.CharField(
        "ARCH short code",
        max_length=20,
        blank=True,
        db_index=True,
        help_text=(
            "Original 6-character otis-web code (e.g. XKPFMI) for rows whose PUID is not "
            "human readable. Kept so re-imports stay idempotent."
        ),
    )
    statement_tex = models.TextField(help_text="Markdown-flavoured TeX statement (source of truth).")
    category = models.CharField(max_length=20, choices=Category.choices, db_index=True)
    difficulty_track = models.CharField(
        max_length=20, choices=DifficultyTrack.choices, db_index=True
    )
    source_url = models.URLField(blank=True, help_text="AoPS page, shortlist PDF, ...")
    answer_tex = models.CharField(
        max_length=255,
        blank=True,
        help_text="Compact canonical answer, revealed together with the official solution.",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("category", "difficulty_track", "puid")
        indexes = [
            models.Index(fields=["puid"], name="problem_puid_idx"),
            # Le corpus complet dépasse 4 000 fiches : l'ordre d'affichage par défaut
            # (« progression conseillée ») et les filtres catégorie/parcours sont
            # servis par un index composite unique.
            models.Index(
                fields=["category", "difficulty_track", "puid"],
                name="problem_curriculum_idx",
            ),
        ]

    def __str__(self) -> str:
        return self.puid

    def get_absolute_url(self) -> str:
        return reverse("problem-detail", args=[self.pk])

    @property
    def category_label(self) -> str:
        return Category(self.category).label

    @property
    def hint_count(self) -> int:
        return self.hints.count()

    @property
    def excerpt(self) -> str:
        """Plain-text preview of the statement (TeX stripped) for list cards."""
        from .services.tex import to_plain_text

        return to_plain_text(self.statement_tex, max_length=190)

    def solved_by(self, user) -> bool:
        if not user or not user.is_authenticated:
            return False
        return UserProgress.objects.filter(user=user, problem=self, is_solved=True).exists()


class Hint(models.Model):
    """A tiered hint. `order_index` defines the reveal order (1, 2, 3, ...)."""

    problem = models.ForeignKey(Problem, related_name="hints", on_delete=models.CASCADE)
    order_index = models.PositiveIntegerField(
        validators=[MinValueValidator(1)], help_text="1-based reveal order."
    )
    content_md = models.TextField(help_text="Markdown/TeX hint text.")
    keywords = models.CharField(
        max_length=255,
        blank=True,
        help_text="Optional topic tags inherited from ARCH (used for search).",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("problem", "order_index")
        constraints = [
            models.UniqueConstraint(
                fields=["problem", "order_index"], name="unique_hint_order_per_problem"
            )
        ]

    def __str__(self) -> str:
        return f"{self.problem.puid} · hint {self.order_index}"


class Solution(models.Model):
    """
    The OFFICIAL ground-truth solution.

    This row is the answer key: it is (a) the reference text handed to the LLM
    grader and (b) the payload rendered once a user unlocks the problem.  It must
    never be serialised to a client that has not unlocked the problem.
    """

    problem = models.OneToOneField(Problem, related_name="solution", on_delete=models.CASCADE)
    official_tex = models.TextField()
    attribution = models.CharField(
        max_length=255,
        blank=True,
        default="",
        help_text='Where the write-up comes from, e.g. "IMO 2001 official solutions".',
    )
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self) -> str:
        return f"Official solution for {self.problem.puid}"


class UserProgress(models.Model):
    """Per-user unlock state for a problem."""

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, related_name="progress", on_delete=models.CASCADE
    )
    problem = models.ForeignKey(Problem, related_name="progress", on_delete=models.CASCADE)
    is_solved = models.BooleanField(default=False, db_index=True)
    unlocked_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name_plural = "user progress"
        constraints = [
            models.UniqueConstraint(fields=["user", "problem"], name="unique_progress_per_user")
        ]
        indexes = [models.Index(fields=["user", "is_solved"], name="progress_user_solved_idx")]

    def __str__(self) -> str:
        state = "solved" if self.is_solved else "in progress"
        return f"{self.user} · {self.problem.puid} ({state})"

    def mark_solved(self) -> "UserProgress":
        if not self.is_solved:
            self.is_solved = True
            self.unlocked_at = self.unlocked_at or timezone.now()
            self.save(update_fields=["is_solved", "unlocked_at", "updated_at"])
        return self


class SubmissionStatus(models.TextChoices):
    PENDING = "PENDING", "En attente (correcteur injoignable)"
    PASSED = "PASSED", "Acceptée — solution débloquée"
    REJECTED = "REJECTED", "Refusée"


class UserSubmission(models.Model):
    """One grading attempt.  Immutable audit trail (admin-only raw payload)."""

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, related_name="submissions", on_delete=models.CASCADE
    )
    problem = models.ForeignKey(Problem, related_name="submissions", on_delete=models.CASCADE)
    submitted_text = models.TextField()
    status = models.CharField(
        max_length=10, choices=SubmissionStatus.choices, default=SubmissionStatus.PENDING
    )
    ai_feedback = models.TextField(blank=True)
    engine = models.CharField(
        max_length=32, blank=True, help_text='Which grader ran, e.g. "openai:gpt-4o" or "offline-heuristic".'
    )
    latency_ms = models.PositiveIntegerField(null=True, blank=True)
    raw_response = models.JSONField(
        null=True, blank=True, help_text="Raw grader payload - staff only, never exposed by the API."
    )
    is_demo = models.BooleanField(
        default=False, help_text="Seeded submission created only to showcase the UI."
    )
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        ordering = ("-created_at",)
        indexes = [models.Index(fields=["user", "problem", "-created_at"], name="submission_lookup_idx")]

    def __str__(self) -> str:
        return f"{self.problem.puid} · {self.user} · {self.status}"

    @property
    def unlocked(self) -> bool:
        return self.status == SubmissionStatus.PASSED


class HintReveal(models.Model):
    """
    Server-side record of revealed hints.

    Why store this?  The UI unhides hints one at a time, and persistence must be
    authoritative: the *content* of a hint is only ever sent to the client after
    this row exists, so "reveal one at a time" cannot be bypassed by forging a
    front-end state (unlike a pure client-side accordion).
    """

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, related_name="hint_reveals", on_delete=models.CASCADE
    )
    hint = models.ForeignKey(Hint, related_name="reveals", on_delete=models.CASCADE)
    revealed_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["user", "hint"], name="unique_reveal_per_user_hint")
        ]

    def __str__(self) -> str:
        return f"{self.user} revealed {self.hint}"
