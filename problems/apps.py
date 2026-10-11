"""App configuration for the `problems` app."""

from django.apps import AppConfig


class ProblemsConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "problems"
    verbose_name = "ARCH problems"
