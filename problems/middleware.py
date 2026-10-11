"""
Middleware.

``DemoUserMiddleware`` implements the zero-friction evaluation mode: when
``DEMO_MODE`` is on and the visitor is anonymous, requests are attributed to a
single lazily-created ``guest`` account so that unlocking, hint reveals and the
submission history are all persisted and demonstrable without a signup step.

In production set ``DEMO_MODE=0``; every page is then owned by a real login.
"""

from __future__ import annotations

from django.conf import settings
from django.contrib.auth.models import User
from django.db import IntegrityError, transaction

GUEST_USERNAME = "guest"


def primary_account() -> User | None:
    """Le compte unique de l'installation (mono-utilisateur par défaut).

    C'est le premier superutilisateur ; les scripts d'administration et le corpus de
    démonstration s'y rattachent, puisque ``DEMO_MODE=0`` ne crée plus de compte invité.
    """
    return User.objects.filter(is_superuser=True).order_by("id").first()


def get_guest_user() -> User:
    """Return the shared demo account, creating it on first use."""
    try:
        return User.objects.get(username=GUEST_USERNAME)
    except User.DoesNotExist:
        try:
            with transaction.atomic():
                user = User.objects.create_user(
                    username=GUEST_USERNAME,
                    password=None,  # unusable password: cannot be logged into directly
                    first_name="Demo",
                    last_name="Guest",
                )
            user.set_unusable_password()
            user.save(update_fields=["password"])
            return user
        except IntegrityError:  # concurrent creation
            return User.objects.get(username=GUEST_USERNAME)


class DemoUserMiddleware:
    """Mode démonstration historique : les visiteurs anonymes partagent un compte invité.

    Il est désactivé par défaut (``DEMO_MODE=0``) : l'installation vise un seul compte
    nominatif. Le code reste là pour rejouer la démonstration d'origine.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if settings.DEMO_MODE and not request.user.is_authenticated:
            request.user = get_guest_user()
            request.is_demo_guest = True
        return self.get_response(request)


class FrameOptionsMiddleware:
    """
    Clickjacking protection with an explicit, environment-driven policy.

    Django's stock middleware cannot be switched off by setting
    ``X_FRAME_OPTIONS = None`` (it calls ``.upper()`` on the value), and the
    in-app preview embeds the app in a cross-origin iframe.  So:

    * dev/demo (``ALLOW_IFRAMING``): the header is omitted so the preview works,
      and a CSP ``frame-ancestors`` line documents the intent;
    * production: ``X-Frame-Options: DENY`` (see docs/SECURITY.md).
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        if getattr(settings, "ALLOW_IFRAMING", False):
            response.headers["Content-Security-Policy"] = "frame-ancestors 'self' https://*.e2b.app"
        else:
            response.headers["X-Frame-Options"] = getattr(settings, "FRAME_OPTIONS_POLICY", "DENY")
        return response
