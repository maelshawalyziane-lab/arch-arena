"""Django admin registration - the staff-facing control room."""

from django.contrib import admin, messages
from django.utils.html import format_html

from .models import (
    Hint,
    HintReveal,
    Problem,
    Solution,
    SubmissionStatus,
    UserProgress,
    UserSubmission,
)


class UserSubmissionInline(admin.TabularInline):
    """
    Read-only inline listing a problem's grading attempts.

    UserSubmission points at Problem (not at UserProgress), so this inline is
    attached to ProblemAdmin; user-level history is browsed via the submissions
    changelist instead.
    """

    model = UserSubmission
    extra = 0
    can_delete = False
    fields = ("status", "engine", "latency_ms", "ai_feedback", "created_at")
    readonly_fields = fields
    ordering = ("-created_at",)
    fk_name = "problem"

    def has_add_permission(self, request, obj=None):  # pragma: no cover - admin UX
        return False


class HintInline(admin.TabularInline):
    model = Hint
    extra = 1
    fields = ("order_index", "content_md", "keywords")


class SolutionInline(admin.StackedInline):
    model = Solution
    extra = 0
    fields = ("official_tex", "attribution")


@admin.register(Problem)
class ProblemAdmin(admin.ModelAdmin):
    list_display = ("puid", "category", "difficulty_track", "legacy_puid", "solved_count", "created_at")
    list_filter = ("category", "difficulty_track")
    search_fields = ("puid", "legacy_puid", "statement_tex")
    readonly_fields = ("created_at", "updated_at")
    inlines = (HintInline, SolutionInline, UserSubmissionInline)
    fieldsets = (
        (None, {"fields": ("puid", "legacy_puid", "category", "difficulty_track", "source_url")}),
        ("Content", {"fields": ("statement_tex", "answer_tex")}),
        ("Timestamps", {"fields": ("created_at", "updated_at")}),
    )

    @admin.display(description="Unlocked by")
    def solved_count(self, obj: Problem) -> int:
        return obj.progress.filter(is_solved=True).count()


@admin.register(Hint)
class HintAdmin(admin.ModelAdmin):
    list_display = ("problem", "order_index", "keywords")
    list_filter = ("problem__category",)
    search_fields = ("content_md", "keywords", "problem__puid")


@admin.register(Solution)
class SolutionAdmin(admin.ModelAdmin):
    list_display = ("problem", "attribution", "updated_at")
    search_fields = ("problem__puid", "official_tex")
    # The ground truth is sensitive: staff only (this whole admin already is).


@admin.register(UserProgress)
class UserProgressAdmin(admin.ModelAdmin):
    list_display = ("user", "problem", "is_solved", "unlocked_at")
    list_filter = ("is_solved", "problem__category")
    search_fields = ("user__username", "problem__puid")
    autocomplete_fields = ("problem",)


@admin.register(UserSubmission)
class UserSubmissionAdmin(admin.ModelAdmin):
    list_display = ("problem", "user", "status", "engine", "latency_ms", "is_demo", "created_at")
    list_filter = ("status", "engine", "problem__category", "is_demo")
    search_fields = ("user__username", "problem__puid", "submitted_text", "ai_feedback")
    readonly_fields = (
        "user",
        "problem",
        "submitted_text",
        "status",
        "ai_feedback",
        "engine",
        "latency_ms",
        "raw_response",
        "created_at",
    )
    date_hierarchy = "created_at"

    def has_add_permission(self, request):  # pragma: no cover - admin UX
        return False

    @admin.display(description="Preview")
    def short_text(self, obj: UserSubmission) -> str:
        return format_html("<code>{}</code>", obj.submitted_text[:120])

    actions = ("regrade_as_passed",)

    @admin.action(description="Manual override: mark these submissions PASSED (+unlock)")
    def regrade_as_passed(self, request, queryset):
        count = 0
        for submission in queryset:
            submission.status = SubmissionStatus.PASSED
            submission.ai_feedback = (submission.ai_feedback + "\n[staff override: accepted]").strip()
            submission.save(update_fields=["status", "ai_feedback"])
            progress, _ = UserProgress.objects.get_or_create(
                user=submission.user, problem=submission.problem
            )
            progress.mark_solved()
            count += 1
        messages.success(request, f"{count} submission(s) manually accepted; solutions unlocked.")


@admin.register(HintReveal)
class HintRevealAdmin(admin.ModelAdmin):
    list_display = ("user", "hint", "revealed_at")
    list_filter = ("hint__problem__category",)
    search_fields = ("user__username", "hint__problem__puid")
