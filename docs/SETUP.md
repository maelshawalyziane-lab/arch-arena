# Installation, configuration et déploiement

## 1. Développement local (SQLite, correcteur hors ligne)

```bash
git clone <ce dépôt> && cd arch-olympiad
python3 -m venv .venv && . .venv/bin/activate
pip install -r requirements.txt          # Django ; psycopg seulement pour PostgreSQL

python manage.py migrate                 # applique problems/migrations/0001 · 0002 · 0003
python manage.py seed_showcase           # 10 fiches curatées + 38 indices par paliers + 10 solutions officielles
python manage.py ingest_omni_math        # 4 324 problèmes olympiques (Omni-MATH, ~15 s, sans réseau)
python manage.py createsuperuser         # facultatif : admin sur /admin/
python manage.py runserver 0.0.0.0:8000
```

L'installation est **mono-compte** : `DEMO_MODE=0`, pas d'inscription (`/signup/` répond 403),
toutes les pages d'étude exigent une connexion. Créez le compte administrateur une fois :

```bash
export ARCH_ADMIN_PASSWORD='…'            # mot de passe du compte unique, hors dépôt
python manage.py bootstrap --password "$ARCH_ADMIN_PASSWORD"   # compte + catalogue + français
```

Le correcteur IA se configure dans `.env` (lu automatiquement) :

```bash
AI_PROVIDER=gemini            # gemini | openai | anthropic
AI_MODEL=gemini-3.5-flash
GEMINI_API_KEY=...
python manage.py check_ai_setup --live
```

Sans clé, `AI_MODE=auto` bascule sur le **correcteur structurel déterministe hors ligne**, donc
tout le parcours verrouillé → refusé → accepté → débloqué fonctionne immédiatement. L'interface étiquette partout le
moteur (`offline-heuristic`) pour qu'un verdict ne soit jamais pris pour une vraie
correction mathématique.

Vérifier l'installation :

```bash
python manage.py check                        # vérifications système
python manage.py check_ai_setup               # config du correcteur + contrat du prompt/JSON (18 contrôles)
python manage.py test problems                # 101 tests
python scripts/verify_seed.py                 # 34 contrôles machine sur les solutions officielles
python scripts/demo_gate.py --puid "IMO 1988/6"   # 25 contrôles de bout en bout en HTTP
```

### Voir l'interface sans navigateur

```bash
python manage.py runserver 8000 &      # ou `make run`
python scripts/make_preview.py         # → design/apercu-*.html (autonomes, hors ligne)
```

Le script incorpore `problems/static/problems/css/app.css` et `js/app.js` dans la page : le
fichier produit s'ouvre sans serveur et s'affiche correctement même dans un aperçu sans accès
réseau. Le thème clair/sombre se bascule avec le bouton de la barre supérieure
(`localStorage.arch-theme`).

## 2. Configuration

Chaque réglage est une variable d'environnement ; voir
[`.env.example`](../.env.example) pour la liste commentée. Les principaux :

| Variable | Défaut | Remarques |
|---|---|---|
| `DJANGO_SECRET_KEY` | valeur de démo | **à définir** en production (≥ 50 caractères) |
| `DJANGO_DEBUG` | `1` | mettre `0` en production |
| `DJANGO_ALLOWED_HOSTS` | `*` si DEBUG | séparé par des virgules ; obligatoire en production |
| `DJANGO_CSRF_TRUSTED_ORIGINS` | `https://*.e2b.app` si DEBUG | ajouter votre origine réelle en production |
| `DATABASE_URL` | — | prioritaire sur `POSTGRES_*` et sur SQLite |
| `DEMO_MODE` | `= DEBUG` | `1` partage un compte `guest` avec les visiteurs anonymes |
| `ALLOW_PROGRESS_RESET` | `= DEBUG` | active `POST /api/problems/<id>/reset` |
| `AI_MODE` | `auto` | `auto` \| `live` \| `offline` |
| `AI_PROVIDER` | `openai` | `openai` \| `anthropic` |
| `AI_MODEL` | défaut du fournisseur | ex. `gpt-4o`, `claude-sonnet-4-5` |
| `AI_TIMEOUT_SECONDS` / `AI_MAX_RETRIES` | `60` / `2` | délai par tentative, tentatives sur 5xx/réseau |
| `OPENAI_API_KEY` / `ANTHROPIC_API_KEY` | — | seule la clé du fournisseur choisi est lue |
| `VERIFY_RATE_LIMIT` / `VERIFY_RATE_WINDOW_SECONDS` | `20` / `3600` | quota de corrections par utilisateur |
| `MAX_SUBMISSION_CHARS` | `20000` | plafond dur sur la longueur d'une soumission |

Copier et charger le modèle :

```bash
cp .env.example .env
set -a && . ./.env && set +a
```

## 3. PostgreSQL

```bash
createdb arch_olympiad
export DATABASE_URL=postgres://arch_app:secret@127.0.0.1:5432/arch_olympiad
pip install 'psycopg[binary]'
python manage.py migrate
```

`sql/schema_postgres.sql` est l'équivalent écrit à la main de la migration (avec en plus des
contraintes `CHECK`, un index de recherche `pg_trgm` et la recette d'un rôle à moindre
privilège). Appliquez-le avec `psql -f sql/schema_postgres.sql` puis
`python manage.py migrate --fake-initial` si un outil de migration externe possède le
schéma. `python manage.py sqlmigrate problems 0001` imprime le DDL produit par l'ORM pour
vérifier la parité.

## 4. Brancher un vrai correcteur LLM

```bash
export AI_MODE=live
export AI_PROVIDER=openai           # ou anthropic
export OPENAI_API_KEY=sk-...
export AI_MODEL=gpt-4o              # facultatif ; sinon le défaut du fournisseur
python manage.py check_ai_setup --live     # effectue un appel réel et affiche le verdict
```

Le prompt du correcteur (persona, règles de tolérance, exigence de JSON strict) vit à un
seul endroit : `problems/services/ai_grader.py::SYSTEM_PROMPT`. Il est repris **verbatim**
du cahier des charges ; la substitution des trois champs se fait par remplacement de chaîne
littéral, car l'exemple JSON contient des accolades que `str.format()` interpréterait comme
des champs. Un test de conformité (`GraderPromptContractTests`) le verrouille.

Détails gérés pour vous :

* OpenAI : `POST /v1/chat/completions`, `temperature=0`, `response_format={"type": "json_object"}`.
* Anthropic : `POST /v1/messages`, `temperature=0`, tour assistant pré-rempli par `{`.
* Les deux via la bibliothèque standard (`urllib.request`) — **aucun client HTTP tiers**.
* L'analyseur de verdict accepte un booléen JSON **ou** une chaîne (`true`/`vrai`/`validé`…),
  retire les balises markdown et tolère une phrase avant le JSON.

Sémantique des pannes : les erreurs réseau et les 5xx/429 sont retentées `AI_MAX_RETRIES`
fois avec un délai croissant ; les 400/401/403/404/422 sont des erreurs de configuration et
ne sont pas retentées. Par défaut (`AI_FALLBACK=1`) un échec définitif produit une
**évaluation de repli** — analyse structurelle hors ligne, précédée de la mention
« ⚠️ Correcteur IA en ligne indisponible » et suivie du moteur réel (`repli:offline-heuristic`)
— pour qu'un quota épuisé ne bloque pas l'élève. Avec `AI_FALLBACK=0`, la soumission est
enregistrée en **`PENDING`** (HTTP 503) — jamais `REJECTED` — donc une panne du fournisseur
ne peut pas être confondue avec une preuve fausse.

Un **disjoncteur** (`AI_BREAKER_THRESHOLD`, défaut 2 ; `AI_BREAKER_SECONDS`, défaut 300)
coupe les appels après plusieurs échecs consécutifs : les copies suivantes reçoivent
immédiatement l'évaluation de repli au lieu d'attendre un quota déjà mort.

Si le modèle renvoie autre chose qu'un verdict JSON exploitable, la réponse est retentée puis
classée par `GraderResponseError`, qui est **à la fois** un `GraderUnavailable` (la tentative
devient `PENDING`) et un `ValueError` (les appelants voient une erreur d'analyse).

## 5. Production

```bash
export DJANGO_SETTINGS_MODULE=config.settings_production
export DJANGO_ALLOWED_HOSTS=olympiad.example.com
export DJANGO_SECRET_KEY=$(python -c 'import secrets; print(secrets.token_urlsafe(64))')
export DJANGO_CSRF_TRUSTED_ORIGINS=https://olympiad.example.com
export DATABASE_URL=postgres://user:pass@db:5432/arch_olympiad
export REDIS_URL=redis://127.0.0.1:6379/1        # quota partagé entre les workers
export DEMO_MODE=0
export ALLOW_PROGRESS_RESET=0

python manage.py check --deploy
python manage.py migrate
python manage.py collectstatic --noinput
gunicorn config.wsgi:application --bind 0.0.0.0:8000 --workers 3 --timeout 120
```

`config/settings_production.py` refuse de démarrer si la clé secrète de démo est encore en
place, si `ALLOWED_HOSTS` est vide, ou si aucune configuration PostgreSQL n'est présente. Il
active aussi HSTS (1 an, preload), les cookies `Secure`/`__Host-`, le cadre `DENY`,
`SECURE_SSL_REDIRECT`, et un cache Redis quand `REDIS_URL` est défini.

Fichiers statiques : KaTeX est embarqué dans `problems/static/vendor/katex` (≈ 600 Ko, woff2
uniquement), donc les maths s'affichent hors ligne ; lancez `collectstatic` et laissez
nginx/WhiteNoise servir `/static/`.

## 6. Ingérer et traduire des données (Omni-MATH, ARCH)

```bash
python manage.py ingest_omni_math                 # 4 324 problèmes (énoncé + solution)
python manage.py translate_corpus                 # traduction française (reprise automatique)
python manage.py translate_corpus --apply         # écriture en base
python manage.py translate_corpus --apply --revert  # retour à l'anglais
```

La traduction n'écrit que les énoncés dont la signature LaTeX est identique à l'original :
aucune formule n'est abîmée, et le cache `var/translations.jsonl` permet de reprendre après
une coupure. Le quota gratuit de Gemini (500 requêtes par modèle et par jour) impose de
découper le travail :

```bash
python3 scripts/translation_progress.py    # couverture française + répartition du restant
make translate                             # reprise d'une passe, puis écriture en base
bash scripts/finish_translation.sh         # boucle toutes les 15 min, sans surveillance
```

```bash
python manage.py fetch_arch_fixture                       # → fixtures/all.json (amont, données factices)
python manage.py ingest_arch_fixture fixtures/all.json \
    --puid-map data/puid_map.example.json \
    --default-category auto --default-track auto \
    --report var/ingest_report.json
```

Pièges et comportements :

* La fixture publique amont est **factice** (3 fiches, 0 solution, PUID opaques) : c'est
  l'état du dépôt amont, pas un bug de l'importateur. Le rapport liste ce qui a été importé,
  écarté, et tous les avertissements.
* Les énoncés vivent en amont dans `arch/data/<PUID>.tex`. Les lignes sans énoncé sont
  importées quand même (les indices restent utiles) et signalées ; `--skip-missing-statement`
  les écarte.
* L'import est idempotent : fiches indexées sur `legacy_puid`, indices sur
  `(problem, order_index)`, solutions sur le lien `OneToOne`.

## 7. Checklist d'exploitation

- [ ] `python manage.py check --deploy` est propre.
- [ ] `DEMO_MODE=0` et `ALLOW_PROGRESS_RESET=0`.
- [ ] Les sauvegardes PostgreSQL couvrent `problems_solution` (les clés de correction) : la
      perdre rend toutes les fiches verrouillées invérifiables (`422 no_official_solution`).
- [ ] `VERIFY_RATE_LIMIT` > 0 et un cache partagé (Redis) pour que le quota ne soit pas
      par processus.
- [ ] Journaux : le logger `problems` en INFO écrit une ligne par correction
      (`graded puid=… passed=… latency_ms=…`).
- [ ] Si vous activez les index `pg_trgm` de `sql/schema_postgres.sql`, la recherche
      d'énoncés reste rapide à plusieurs dizaines de milliers de fiches.

## 8. Dépannage

| Symptôme | Cause / solution |
|---|---|
| `422 no_official_solution` | La fiche n'a pas de ligne `Solution` ; ajoutez-la dans l'admin. |
| `503 grader_unavailable` | Pas de clé / fournisseur en panne ; la tentative est `PENDING`. Lancez `check_ai_setup`. |
| Les maths s'affichent en `\frac{…}` brut | KaTeX n'a pas chargé *et* le repli n'a pas tourné — vérifiez que `/static/vendor/katex/katex.min.js` est bien servi. |
| `409 hint_locked` | Les indices s'ouvrent dans l'ordre : ouvrez d'abord `next_hint_id`. |
| `403 authentication_required` | `DEMO_MODE=0` et vous êtes déconnecté. |
| `403 csrf` | Renvoyez le cookie `csrftoken` dans `X-CSRFToken`. |
| Solution collée mais toujours verrouillée | C'est voulu : seul un verdict positif fait passer `is_solved` à `true`. |
| L'aperçu renvoie une erreur 400 | L'origine de l'aperçu doit figurer dans `DJANGO_CSRF_TRUSTED_ORIGINS` (`https://*.e2b.app` est pré-rempli en DEBUG). |
| Le bandeau ne correspond pas au texte attendu | Il est défini dans `problems/templates/problems/problem_detail.html` (`.locked-title`) et vérifié mot pour mot par `test_ui_contract.py`. |
