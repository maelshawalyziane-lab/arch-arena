#!/usr/bin/env bash
#
# Démarrage de la plateforme sur un hébergeur Python (Render, Railway, Fly.io, VPS…).
#
# Le script est volontairement explicite : il prépare la base, rassemble les fichiers
# statiques (WhiteNoise les sert ensuite depuis Gunicorn, sans nginx), puis démarre
# l'application. Toutes les valeurs sensibles viennent de l'environnement, jamais du dépôt.
#
# Variables lues :
#   DJANGO_SETTINGS_MODULE          config.settings_production
#   DJANGO_SECRET_KEY               clé longue et aléatoire (obligatoire)
#   DJANGO_ALLOWED_HOSTS            hôtes autorisés, séparés par des virgules (obligatoire)
#   DJANGO_CSRF_TRUSTED_ORIGINS     https://votre-domaine (obligatoire pour les POST)
#   DATABASE_URL                    postgres://… (sinon SQLite dans le conteneur)
#   GEMINI_API_KEY / AI_PROVIDER / AI_MODEL   correcteur IA
#   PORT                            port d'écoute fourni par l'hébergeur
#
set -euo pipefail

cd "$(dirname "$0")/.."

: "${DJANGO_SETTINGS_MODULE:=config.settings_production}"
export DJANGO_SETTINGS_MODULE

PYTHON="${PYTHON:-python3}"
WORKERS="${WEB_CONCURRENCY:-3}"
TIMEOUT="${GUNICORN_TIMEOUT:-120}"
PORT="${PORT:-8000}"

echo "→ migrations"
"$PYTHON" manage.py migrate --noinput

echo "→ fichiers statiques"
"$PYTHON" manage.py collectstatic --noinput --clear

echo "→ vérifications système"
"$PYTHON" manage.py check --deploy

# Installation neuve : compte unique, catalogue complet (4 324 problèmes + 10 fiches
# curatées) et énoncés français, le tout hors ligne depuis les fichiers du dépôt.
# Sur une base déjà remplie, la commande le constate et ne touche à rien (~1 seconde).
echo "→ amorçage (compte, catalogue, français)"
"$PYTHON" manage.py bootstrap

echo "→ gunicorn (${WORKERS} workers, port ${PORT})"
exec "$PYTHON" -m gunicorn config.wsgi:application \
    --bind "0.0.0.0:${PORT}" \
    --workers "${WORKERS}" \
    --timeout "${TIMEOUT}" \
    --access-logfile - \
    --error-logfile -
