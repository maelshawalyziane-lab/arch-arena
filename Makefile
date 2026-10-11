# arch-olympiad - developer shortcuts
# `make help` lists everything.

PY ?= python3
MANAGE := $(PY) manage.py
PORT ?= 8000
PUID ?= IMO 1988/6
DATABASE_URL ?=

.DEFAULT_GOAL := help
.PHONY: help install init migrate seed corpus run shell test check verify gate ai lock-check preview site serve-site publish deploy-check docs clean reset-db postgres-sql translate translate-status

help:  ## affiche cette aide
	@grep -hE '^[a-zA-Z_-]+:.*?## ' $(MAKEFILE_LIST) | sort | awk 'BEGIN{FS=":.*?## "}{printf "  \033[36m%-12s\033[0m %s\n", $$1, $$2}'

install:  ## installe les dépendances Python
	$(PY) -m pip install -r requirements.txt

init: install migrate seed corpus  ## installation initiale : dépendances + schéma + corpus complet

migrate:  ## applique les migrations
	$(MANAGE) migrate

seed:  ## (re)charge le corpus curaté (10 fiches, 38 indices, 10 solutions)
	$(MANAGE) seed_showcase

corpus:  ## importe le corpus Omni-MATH complet (4 300+ problèmes, ~15 s)
	$(MANAGE) ingest_omni_math $(if $(LIMIT),--limit $(LIMIT),) $(if $(SOURCES),--sources "$(SOURCES)",)

run:  ## lance le serveur de développement sur $(PORT)
	$(MANAGE) runserver 0.0.0.0:$(PORT)

shell:  ## shell Django
	$(MANAGE) shell

test:  ## lance la suite de tests
	$(MANAGE) test problems -v 2

check:  ## vérifications système (ARGS="--deploy" pour la prod)
	$(MANAGE) check $(ARGS)

verify:  ## vérifie machine à machine chaque solution officielle (34 contrôles)
	$(PY) scripts/verify_seed.py

lock-check:  ## verrou sur un échantillon aléatoire du corpus importé (SAMPLE=25)
	$(MANAGE) verify_lock_sample --sample $(or $(SAMPLE),25) $(if $(SEED),--seed $(SEED),)

gate:  ## rejoue tout le verrou IA en HTTP (25 contrôles ; serveur lancé)
	$(PY) scripts/demo_gate.py --base http://127.0.0.1:$(PORT) --puid "$(PUID)"

ai:  ## vérifie le correcteur (LIVE=1 pour un vrai appel API)
	$(MANAGE) check_ai_setup $(if $(LIVE),--live,)

preview:  ## génère les aperçus HTML autonomes dans design/ (serveur lancé)
	@test -n "$(or $(PASSWORD),$(ARCH_PASSWORD))" || \
	  { printf "  Mot de passe requis pour photographier les pages connectées :\n    make preview PASSWORD='…'      (ou export ARCH_PASSWORD=…)\n"; exit 1; }
	$(PY) scripts/make_preview.py --base http://127.0.0.1:$(PORT) \
	  --username $(or $(USER_NAME),admin) --password '$(or $(PASSWORD),$(ARCH_PASSWORD))'

translate:  ## traduit les énoncés restants puis écrit le français en base (BATCH=10)
	$(MANAGE) translate_corpus --workers 4 --batch $(or $(BATCH),10) --rounds 2 --singles --rpm 15 --cache var/translations.jsonl
	$(MANAGE) translate_corpus --apply --cache var/translations.jsonl

translate-status:  ## avancement de la traduction (couverture française du corpus)
	$(PY) scripts/translation_progress.py

site:  ## construit site/ : la vitrine statique publiable sur Netlify
	$(PY) scripts/build_site.py

serve-site:  ## sert site/ en local (SITE_PORT=8010) pour vérifier avant publication
	cd site && $(PY) -m http.server $(or $(SITE_PORT),8010) --bind 0.0.0.0

publish:  ## remet la vitrine à jour (aperçus + site/) et affiche les étapes de publication
	@$(MAKE) --no-print-directory preview
	@$(MAKE) --no-print-directory site
	@printf '\n  Vitrine prête dans site/ — trois façons de la mettre en ligne :\n'
	@printf '    1. glisser-déposer  : https://app.netlify.com/drop\n'
	@printf '    2. ligne de commande: netlify deploy --dir=site --prod\n'
	@printf '    3. depuis GitHub    : git push (Netlify lit netlify.toml)\n'
	@printf '  Vérifiez ensuite la fiche verrouillée : bandeau de verrou, aucune solution visible.\n\n'
	@printf '  La vraie plateforme (verrou + correcteur IA) se déploie séparément : voir docs/PUBLIER.md\n\n'

deploy-check:  ## vérifie les settings de production (clé, hôtes, statique, Gunicorn)
	DJANGO_SETTINGS_MODULE=config.settings_production \
	DJANGO_SECRET_KEY="$$( $(PY) -c 'import secrets;print(secrets.token_urlsafe(64))' )" \
	DJANGO_ALLOWED_HOSTS=localhost DJANGO_CSRF_TRUSTED_ORIGINS=http://localhost \
	ALLOW_SQLITE_IN_PRODUCTION=1 $(MANAGE) check --deploy
	@echo "→ la vraie plateforme se déploie avec : bash deploy/start.sh (voir docs/PUBLIER.md)"

ingest:  ## réimporte la fixture ARCH (FIXTURE=chemin)
	$(MANAGE) fetch_arch_fixture
	$(MANAGE) ingest_arch_fixture $(if $(FIXTURE),$(FIXTURE),fixtures/all.json) \
	    --puid-map data/puid_map.example.json --default-category auto --default-track auto \
	    --report var/ingest_report.json

postgres-sql:  ## affiche le DDL de migration (parité avec sql/schema_postgres.sql)
	$(MANAGE) sqlmigrate problems 0001

reset-db:  ## DESTRUCTIF : recrée la base de développement et le corpus
	rm -f db.sqlite3
	$(MAKE) migrate seed

clean:  ## supprime les caches et artefacts de build
	find . -name '__pycache__' -prune -exec rm -rf {} +
	rm -rf .pytest_cache staticfiles
	find design -name 'apercu-*.html' -delete
