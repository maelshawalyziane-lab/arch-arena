# ARCH Arena — image de production (Django + Gunicorn + WhiteNoise).
#
#     docker build -t arch-arena .
#     docker run --rm -p 8000:8000 \
#       -e DJANGO_SECRET_KEY="$(python3 -c 'import secrets;print(secrets.token_urlsafe(64))')" \
#       -e DJANGO_ALLOWED_HOSTS=localhost,127.0.0.1 \
#       -e DJANGO_CSRF_TRUSTED_ORIGINS=http://localhost:8000 \
#       -e GEMINI_API_KEY=… \
#       arch-arena
#
# Dans un vrai déploiement, la base vit hors du conteneur : passez DATABASE_URL
# (PostgreSQL). Sans elle, l'application utilise SQLite dans le conteneur, donc les
# données disparaissent au redéploiement.

FROM python:3.13-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    DJANGO_SETTINGS_MODULE=config.settings_production

WORKDIR /app

# Les dépendances d'abord : la couche est réutilisée tant que requirements.txt ne bouge pas.
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Utilisateur non privilégié ; les dossiers écrits par l'application lui appartiennent.
RUN useradd --create-home --uid 10001 app \
 && mkdir -p /app/staticfiles /app/var \
 && chown -R app:app /app
USER app

EXPOSE 8000
#: `PORT` est fourni par l'hébergeur (Render : 10000) ; /healthz/ répond toujours 200.
HEALTHCHECK --interval=30s --timeout=5s --start-period=60s --retries=3 \
  CMD python -c "import os,urllib.request,sys; port=os.environ.get('PORT','8000'); sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:'+port+'/healthz/', timeout=4).status == 200 else 1)"

CMD ["bash", "deploy/start.sh"]
