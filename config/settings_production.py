"""
Production settings.

    DJANGO_SETTINGS_MODULE=config.settings_production python manage.py migrate

Everything here is a *hardening overlay* on config.settings; the database,
AI grader and gate settings are still read from the same environment variables
(see .env.example).  Use this module whenever the app is reachable by anyone
other than you.
"""

from __future__ import annotations

from .settings import *  # noqa: F401,F403  (re-export the development defaults)
from .settings import env, env_bool, env_list  # noqa: F401

# --------------------------------------------------------------------------- #
# never run these in production
# --------------------------------------------------------------------------- #
DEBUG = False
DEMO_MODE = env_bool("DEMO_MODE", False)          # guest auto-login must be OFF
ALLOW_PROGRESS_RESET = env_bool("ALLOW_PROGRESS_RESET", False)
ALLOW_IFRAMING = env_bool("ALLOW_IFRAMING", False)  # no clickjacking, keep DENY
FRAME_OPTIONS_POLICY = "DENY"

ALLOWED_HOSTS = env_list("DJANGO_ALLOWED_HOSTS", "") if not DEBUG else []
if not ALLOWED_HOSTS:  # fail loudly rather than silently serving any Host header
    raise RuntimeError(
        "Set DJANGO_ALLOWED_HOSTS (comma separated) when running with "
        "DJANGO_SETTINGS_MODULE=config.settings_production"
    )
CSRF_TRUSTED_ORIGINS = env_list("DJANGO_CSRF_TRUSTED_ORIGINS", "")

# A production SECRET_KEY must be long and random (50+ chars).
if SECRET_KEY == "dev-only-insecure-key-change-me" or len(SECRET_KEY) < 50:  # noqa: F405
    raise RuntimeError(
        "Set a strong DJANGO_SECRET_KEY (>= 50 random chars) in production; e.g. "
        "python -c 'import secrets; print(secrets.token_urlsafe(64))'"
    )
if not env("DATABASE_URL") and not env("POSTGRES_DB"):
    # SQLite reste possible pour une installation personnelle sur un seul serveur
    # (PythonAnywhere, petit VPS, conteneur avec volume) : les données vivent alors dans
    # un fichier, qu'il faut sauvegarder. Par défaut on refuse, pour qu'un déploiement
    # « multi-instances » ne découvre pas le problème après avoir perdu la progression.
    if not env_bool("ALLOW_SQLITE_IN_PRODUCTION", False):
        raise RuntimeError(
            "Production expects PostgreSQL: set DATABASE_URL or the POSTGRES_* variables "
            "(and `pip install 'psycopg[binary]'`), or accept SQLite explicitly with "
            "ALLOW_SQLITE_IN_PRODUCTION=1 (single-server installs; back up db.sqlite3)."
        )
    import warnings

    warnings.warn(
        "ALLOW_SQLITE_IN_PRODUCTION=1 : base SQLite. Sur une plateforme qui redéploie le "
        "conteneur, la progression serait perdue — montez un volume persistant et sauvegardez "
        "db.sqlite3.",
        RuntimeWarning,
        stacklevel=1,
    )

# --------------------------------------------------------------------------- #
# transport + cookie security
# --------------------------------------------------------------------------- #
SECURE_SSL_REDIRECT = env_bool("DJANGO_SECURE_SSL_REDIRECT", True)
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
SECURE_HSTS_SECONDS = int(env("DJANGO_HSTS_SECONDS", "31536000") or 0)  # 1 year
SECURE_HSTS_INCLUDE_SUBDOMAINS = True
SECURE_HSTS_PRELOAD = True

SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
SESSION_COOKIE_AGE = 60 * 60 * 24 * 14
SESSION_EXPIRE_AT_BROWSER_CLOSE = False
SESSION_COOKIE_NAME = "__Host-sessionid"      # __Host- prefix requires a secure cookie
CSRF_COOKIE_NAME = "__Host-csrftoken"
LANGUAGE_COOKIE_SECURE = True

SECURE_CONTENT_TYPE_NOSNIFF = True
SECURE_REFERRER_POLICY = "same-origin"
X_FRAME_OPTIONS = "DENY"

# Django's `security.W002` warns that django.middleware.clickjacking is missing.
# It is missing on purpose: problems.middleware.FrameOptionsMiddleware emits the
# same header with an environment-driven policy (DENY here, omitted in dev so the
# sandboxed preview can embed the app).  The behaviour is covered by
# problems.tests.test_ui_contract.FramingAndSecurityHeaderTests.
SILENCED_SYSTEM_CHECKS = ["security.W002"]

# Don't ship stack traces, and don't leak the Django version in headers.
MIDDLEWARE = [m for m in MIDDLEWARE if m != "django.middleware.gzip.GZipMiddleware"] + [  # noqa: F405
    "django.middleware.gzip.GZipMiddleware"
]

# --------------------------------------------------------------------------- #
# shared cache (the verification throttle must work across workers)
# --------------------------------------------------------------------------- #
# Set REDIS_URL to switch off LocMemCache, e.g. redis://127.0.0.1:6379/1
if env("REDIS_URL"):
    CACHES = {  # noqa: F405
        "default": {
            "BACKEND": "django.core.cache.backends.redis.RedisCache",
            "LOCATION": env("REDIS_URL"),
        }
    }

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {"verbose": {"format": "[{asctime}] {levelname} {name}: {message}", "style": "{"}},
    "handlers": {"console": {"class": "logging.StreamHandler", "formatter": "verbose"}},
    "loggers": {
        "problems": {"handlers": ["console"], "level": env("DJANGO_LOG_LEVEL", "INFO"), "propagate": False},
        "django.request": {"handlers": ["console"], "level": "WARNING", "propagate": False},
    },
}
