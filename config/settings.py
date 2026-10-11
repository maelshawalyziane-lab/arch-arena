"""
Django settings for the arch-olympiad platform.

Design goals
------------
* Runs with zero configuration on SQLite for local development / demo.
* Switches to PostgreSQL in production purely through environment variables.
* Never hard-codes secrets; everything sensitive is read from the environment.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path
from urllib.parse import unquote, urlparse

BASE_DIR = Path(__file__).resolve().parent.parent


def _load_dotenv(path: Path) -> None:
    """Charge `.env` s'il existe — sans dépendance externe.

    Les variables déjà présentes dans l'environnement gagnent : `.env` n'est qu'un
    confort de développement (il contient la clé du correcteur, il ne doit jamais
    être versionné — `.gitignore` s'en charge).
    """
    if not path.exists():
        return
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


_load_dotenv(BASE_DIR / ".env")


# --------------------------------------------------------------------------- #
# small helpers
# --------------------------------------------------------------------------- #
def env(key: str, default: str = "") -> str:
    return os.environ.get(key, default).strip()


def env_bool(key: str, default: bool = False) -> bool:
    raw = env(key, "1" if default else "0").lower()
    return raw in {"1", "true", "yes", "on"}


def env_list(key: str, default: str = "") -> list[str]:
    return [item.strip() for item in env(key, default).split(",") if item.strip()]


# --------------------------------------------------------------------------- #
# core
# --------------------------------------------------------------------------- #
SECRET_KEY = env("DJANGO_SECRET_KEY", "dev-only-insecure-key-change-me")
DEBUG = env_bool("DJANGO_DEBUG", True)

# In DEBUG we accept any host so that port-forwarded preview URLs work out of the box.
ALLOWED_HOSTS = env_list("DJANGO_ALLOWED_HOSTS", "*" if DEBUG else "localhost,127.0.0.1")

# The in-app preview proxies the app through a *.e2b.app origin.  CSRF only accepts
# POSTs whose Origin matches CSRF_TRUSTED_ORIGINS, so list that wildcard while in
# demo/debug mode.  Production should set DJANGO_CSRF_TRUSTED_ORIGINS explicitly.
CSRF_TRUSTED_ORIGINS = env_list(
    "DJANGO_CSRF_TRUSTED_ORIGINS",
    "https://*.e2b.app" if DEBUG else "",
)

# Clickjacking: Django's own XFrameOptionsMiddleware rejects a null value, so the
# policy lives in problems.middleware.FrameOptionsMiddleware instead.  In demo/debug
# the header is omitted (the app must be embeddable in the preview iframe); in
# production it is DENY.
ALLOW_IFRAMING = DEBUG
FRAME_OPTIONS_POLICY = "SAMEORIGIN" if DEBUG else "DENY"

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "problems",
]

# WhiteNoise sert les fichiers statiques (CSS, JS, KaTeX) directement depuis Gunicorn :
# c'est ce qui permet un déploiement sans serveur web séparé. Absent en développement,
# il est simplement ignoré (l'application fonctionne sans lui).
USE_WHITENOISE = env_bool("USE_WHITENOISE", True)
try:
    import whitenoise  # noqa: F401
except ImportError:  # pragma: no cover - dépendance de production facultative
    USE_WHITENOISE = False

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "problems.middleware.DemoUserMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "problems.middleware.FrameOptionsMiddleware",  # replaces django.middleware.clickjacking
    "django.middleware.gzip.GZipMiddleware",
]
if USE_WHITENOISE:  # juste après SecurityMiddleware, comme le recommande la documentation
    MIDDLEWARE.insert(1, "whitenoise.middleware.WhiteNoiseMiddleware")

ROOT_URLCONF = "config.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
                "problems.context_processors.platform_settings",
            ],
        },
    },
]

WSGI_APPLICATION = "config.wsgi.application"
ASGI_APPLICATION = "config.asgi.application"


# --------------------------------------------------------------------------- #
# database  (DATABASE_URL wins; otherwise POSTGRES_* vars; otherwise SQLite)
# --------------------------------------------------------------------------- #
def database_from_url(url: str) -> dict:
    parsed = urlparse(url)
    engine = {
        "postgres": "django.db.backends.postgresql",
        "postgresql": "django.db.backends.postgresql",
        "sqlite": "django.db.backends.sqlite3",
    }.get(parsed.scheme, "django.db.backends.postgresql")
    if engine.endswith("sqlite3"):
        return {"ENGINE": engine, "NAME": unquote(parsed.path.lstrip("/")) or "db.sqlite3"}
    return {
        "ENGINE": engine,
        "NAME": unquote(parsed.path.lstrip("/")),
        "USER": unquote(parsed.username or ""),
        "PASSWORD": unquote(parsed.password or ""),
        "HOST": parsed.hostname or "",
        "PORT": str(parsed.port or ""),
        "CONN_MAX_AGE": 60,
    }


DATABASE_URL = env("DATABASE_URL")
if DATABASE_URL:
    DATABASES = {"default": database_from_url(DATABASE_URL)}
elif env("POSTGRES_DB"):
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.postgresql",
            "NAME": env("POSTGRES_DB"),
            "USER": env("POSTGRES_USER", "postgres"),
            "PASSWORD": env("POSTGRES_PASSWORD"),
            "HOST": env("POSTGRES_HOST", "localhost"),
            "PORT": env("POSTGRES_PORT", "5432"),
            "CONN_MAX_AGE": 60,
        }
    }
else:
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.sqlite3",
            "NAME": BASE_DIR / "db.sqlite3",
            "OPTIONS": {"timeout": 20},
        }
    }

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"


# --------------------------------------------------------------------------- #
# auth / i18n / static
# --------------------------------------------------------------------------- #
AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

LOGIN_URL = "login"
LOGIN_REDIRECT_URL = "dashboard"
LOGOUT_REDIRECT_URL = "problem-list"

LANGUAGE_CODE = "en-us"
TIME_ZONE = env("DJANGO_TIME_ZONE", "UTC")
USE_I18N = True
USE_TZ = True

STATIC_URL = "static/"
STATICFILES_DIRS = [BASE_DIR / "static"] if (BASE_DIR / "static").exists() else []
STATIC_ROOT = BASE_DIR / "staticfiles"

STORAGES = {
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    "staticfiles": {
        # En production, WhiteNoise compresse et sert les fichiers avec un en-tête de cache
        # long. En développement (ou sans WhiteNoise) on garde le stockage Django standard,
        # qui n'exige pas de `collectstatic`.
        "BACKEND": (
            "whitenoise.storage.CompressedStaticFilesStorage"
            if USE_WHITENOISE and not DEBUG
            else "django.contrib.staticfiles.storage.StaticFilesStorage"
        )
    },
}

MESSAGE_STORAGE = "django.contrib.messages.storage.session.SessionStorage"


# --------------------------------------------------------------------------- #
# product / platform settings (consumed by problems.services.*)
# --------------------------------------------------------------------------- #
#: La plateforme est **mono-compte** : le mode démonstration (un compte invité partagé
#: entre visiteurs anonymes) doit être demandé explicitement. Le laisser dépendre de
#: DEBUG faisait diverger un dépôt fraîchement cloné de l'installation réelle — les
#: visiteurs anonymes y entraient sans mot de passe.
DEMO_MODE = env_bool("DEMO_MODE", False)
ALLOW_PROGRESS_RESET = env_bool("ALLOW_PROGRESS_RESET", DEBUG)
#: Par défaut la plateforme est mono-compte : l'inscription est fermée.
ALLOW_SIGNUP = env_bool("ALLOW_SIGNUP", False)

AI_MODE = env("AI_MODE", "auto").lower()            # auto | live | offline
AI_PROVIDER = env("AI_PROVIDER", "openai").lower()  # openai | anthropic | gemini
AI_MODEL = env("AI_MODEL")                          # blank -> provider default
AI_TIMEOUT_SECONDS = int(env("AI_TIMEOUT_SECONDS", "60") or 60)
AI_MAX_RETRIES = int(env("AI_MAX_RETRIES", "2") or 0)
#: Si le correcteur en ligne tombe (quota, réseau, panne du fournisseur), une évaluation
#: de repli est produite plutôt qu'une erreur 503 : l'élève garde un verdict et l'interface
#: indique explicitement le moteur utilisé. Mettre AI_FALLBACK=0 pour exiger l'API.
AI_FALLBACK = env("AI_FALLBACK", "1").lower() not in {"0", "false", "no", "off"}
#: Disjoncteur : après AI_BREAKER_THRESHOLD échecs consécutifs, on cesse d'appeler l'API
#: pendant AI_BREAKER_SECONDS (sinon chaque soumission attend un quota déjà épuisé).
AI_BREAKER_THRESHOLD = int(env("AI_BREAKER_THRESHOLD", "2") or 2)
AI_BREAKER_SECONDS = int(env("AI_BREAKER_SECONDS", "300") or 300)
AI_MAX_OUTPUT_TOKENS = int(env("AI_MAX_OUTPUT_TOKENS", "700") or 700)
OPENAI_API_KEY = env("OPENAI_API_KEY")
ANTHROPIC_API_KEY = env("ANTHROPIC_API_KEY")
GEMINI_API_KEY = env("GEMINI_API_KEY")

# Les tests ne doivent jamais dépendre du réseau : même si une clé est configurée
# dans .env, la suite s'exécute avec le correcteur hors ligne déterministe.
if "test" in sys.argv or env_bool("DJANGO_TESTING", False):
    AI_MODE = "offline"

VERIFY_RATE_LIMIT = int(env("VERIFY_RATE_LIMIT", "20") or 0)
VERIFY_RATE_WINDOW_SECONDS = int(env("VERIFY_RATE_WINDOW_SECONDS", "3600") or 3600)
MAX_SUBMISSION_CHARS = int(env("MAX_SUBMISSION_CHARS", "20000") or 20000)

# LocMemCache is fine for a single-process demo; point CACHES at Redis/Memcached
# in production so the verification throttle is shared across workers.
CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
        "LOCATION": "arch-olympiad",
    }
}

# Security headers that are safe even in development.  (Everything cookie-related
# is enabled via config.settings_production, see docs/SETUP.md.)
SECURE_CONTENT_TYPE_NOSNIFF = True
SECURE_REFERRER_POLICY = "same-origin"
SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SAMESITE = "Lax"
CSRF_COOKIE_SAMESITE = "Lax"

# The AI endpoints can be slow (long generations) — keep generous timeouts on the
# WSGI side; the per-request timeout is enforced inside services/ai_grader.py.
DATA_UPLOAD_MAX_MEMORY_SIZE = 2 * 1024 * 1024  # 2 MB is plenty for a LaTeX proof

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "verbose": {"format": "[{asctime}] {levelname} {name}: {message}", "style": "{"},
    },
    "handlers": {
        "console": {"class": "logging.StreamHandler", "formatter": "verbose"},
    },
    "loggers": {
        "problems": {"handlers": ["console"], "level": "INFO", "propagate": False},
    },
}
