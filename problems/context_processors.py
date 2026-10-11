"""Template context processor exposing read-only platform flags to templates."""

from django.conf import settings


def platform_settings(request):
    """Expose a tiny, secret-free slice of the configuration to templates."""
    return {
        "PLATFORM": {
            "demo_mode": settings.DEMO_MODE,
            "ai_mode": settings.AI_MODE,
            "ai_provider": settings.AI_PROVIDER,
            "allow_progress_reset": settings.ALLOW_PROGRESS_RESET,
        }
    }
