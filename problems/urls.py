"""URL routes for the study pages and the verification API."""

from django.urls import path

from . import views

urlpatterns = [
    # study pages
    path("", views.ProblemListView.as_view(), name="problem-list"),
    path("problems/au-hasard/", views.problem_random_view, name="problem-random"),
    path("problems/<int:pk>/", views.ProblemDetailView.as_view(), name="problem-detail"),
    path("dashboard/", views.DashboardView.as_view(), name="dashboard"),
    path("signup/", views.signup_view, name="signup"),
    # verification API (spec: POST /api/problems/:id/verify, no trailing slash)
    path("api/problems/<int:pk>/verify", views.verify_submission_view, name="api-verify"),
    path("api/problems/<int:pk>/verify/", views.verify_submission_view),
    path("api/problems/<int:pk>/status", views.problem_status_view, name="api-status"),
    path("api/problems/<int:pk>/status/", views.problem_status_view),
    path("api/problems/<int:pk>/reset", views.reset_progress_view, name="api-reset"),
    path("api/problems/<int:pk>/reset/", views.reset_progress_view),
    path(
        "api/problems/<int:pk>/hints/<int:hint_id>/reveal",
        views.reveal_hint_view,
        name="api-hint-reveal",
    ),
    path("api/problems/<int:pk>/hints/<int:hint_id>/reveal/", views.reveal_hint_view),
]
