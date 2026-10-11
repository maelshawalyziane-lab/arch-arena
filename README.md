# arch-olympiad — une plateforme d'entraînement olympique façon ARCH, avec verrou IA

Application Django autonome pour **auto-étudier les mathématiques olympiques**.
Elle s'inspire d'[ARCH (Automated Repository of Canned Hints)](https://github.com/vEnhance/otis-web)
d'Evan Chen (`otis-web`) et ajoute ce qu'ARCH laisse volontairement de côté : une
**solution officielle qui reste verrouillée tant que vous n'avez pas vraiment résolu le
problème**, sous le contrôle d'un correcteur LLM qui compare votre rédaction à la
solution de référence.

```
  parcourir par PUID            indices par paliers          verrou IA (le gate)         récompense
  ─────────────────             ──────────────────           ───────────────────         ──────────
  IMO 1988/6          ──▶       indice 1 → 2 → 3      ──▶     POST /api/problems/5/verify ──▶  solution
  IMO 2014/5                    (un seul à la fois,          ├─ passed:  unlocked = true       officielle
  Drill 2020/N1                  imposé côté serveur)       └─ failed:  unlocked = false      + historique
                                                                 (le feedback nomme le trou)
```

* Parcourir le corpus par **PUID** (`IMO 2016/4`), catégorie et palier de difficulté.
* Ouvrir les **indices un par un** — le serveur refuse tout palier sauté et n'envoie
  jamais le texte d'un indice non ouvert au navigateur.
* Rédiger sa preuve en **Markdown + LaTeX** et la soumettre au correcteur.
* Le correcteur reçoit la **solution officielle comme référence**, a consigne d'accepter
  les preuves alternatives valides et de refuser les arguments vagues, et répond en JSON strict.
* En cas de succès, le backend écrit `UserProgress.is_solved = true`, horodate
  `unlocked_at = NOW()`, et la page se met à servir `Solution.official_tex`.
  **Avant cet instant, la clé de correction n'est jamais envoyée au client.**

---

## 1. Démarrage rapide (SQLite, sans clé API, ~60 secondes)

```bash
python3 -m venv .venv && . .venv/bin/activate      # facultatif mais recommandé
pip install -r requirements.txt

python manage.py migrate                           # (1) base de données + migrations
python manage.py seed_showcase                     # corpus curaté : 10 fiches, 38 indices, 10 solutions
python manage.py ingest_omni_math                  # + 4 324 problèmes olympiques (énoncé + solution)
python manage.py runserver 0.0.0.0:8000            # ouvrir http://127.0.0.1:8000/

make site && make serve-site                       # vitrine statique publiable (port 8010)
```

### Publier

| Objet | Où | Procédure |
|---|---|---|
| La vitrine (présentation + aperçus) | **Netlify** | `make site`, puis glisser `site/` sur <https://app.netlify.com/drop> |
| La vraie plateforme (verrou, IA, progression) | Render / Railway / Fly / PythonAnywhere | `bash deploy/start.sh` (`Dockerfile` et `deploy/render.yaml` fournis) |

Tout est détaillé dans **[docs/PUBLIER.md](docs/PUBLIER.md)**. En résumé : Netlify ne peut pas
exécuter Django, donc la clé du correcteur, la solution officielle et la progression restent
côté serveur — la vitrine est publiée à part, et elle ne contient aucun secret (un test le
vérifie sur chaque fichier de `site/`).

### Un seul compte

L'installation est **mono-utilisateur** : un compte administrateur, aucune inscription,
aucun compte invité. Les pages d'étude redirigent vers la connexion, `/signup/` explique la
règle (403) ; c'est le réglage par défaut, et `DEMO_MODE=1` ouvre au contraire un compte
invité partagé pour montrer l'interface.

```bash
export ARCH_ADMIN_PASSWORD='…'            # jamais dans le dépôt : .env ou l'environnement
python manage.py bootstrap --password "$ARCH_ADMIN_PASSWORD"
# ou, compte par compte :
python manage.py createsuperuser
```

`bootstrap` fait d'un coup ce qu'il faut à une installation neuve : le compte, le catalogue
et les énoncés français (détail dans `docs/PUBLIER.md`).

`ALLOW_SIGNUP=1` rouvre le formulaire d'inscription, `DEMO_MODE=1` rétablit le compte invité
partagé : ces deux interrupteurs servent aux essais, pas au fonctionnement normal.

### Le correcteur IA (Gemini)

`AI_MODE=auto` suffit : dès qu'une clé est présente, les copies partent au modèle ; sans clé,
la plateforme utilise le **correcteur structurel déterministe hors ligne** pour que le
parcours (verrouillé → refusé → accepté → débloqué) reste démontrable.

```bash
# .env (lu automatiquement au démarrage, jamais versionné)
AI_PROVIDER=gemini
AI_MODEL=gemini-3.5-flash
GEMINI_API_KEY=...

python manage.py check_ai_setup          # 18 contrôles : fournisseur, clé, prompt, JSON
python manage.py check_ai_setup --live   # + un vrai appel au modèle (quota : 500/modèle/jour)
```

`AI_PROVIDER` accepte `gemini` (endpoint compatible OpenAI de Google), `openai` et
`anthropic` ; le prompt système, lui, ne change pas — c'est toujours celui du cahier des
charges, en français.

**Quand l'API tombe, le site continue.** Une clé dont le quota gratuit est épuisé (500
requêtes par modèle et par jour) ne doit pas transformer le parcours en erreur 503 : le
correcteur rend alors une **évaluation de repli** (analyse structurelle) précédée de la
mention « ⚠️ Correcteur IA en ligne indisponible » et accompagnée du moteur réellement
utilisé (`engine`, affiché sous le verdict). Un **disjoncteur** coupe en outre les appels
pendant 5 minutes après 2 échecs consécutifs, pour ne pas faire patienter chaque copie
devant une API déjà morte. Régler `AI_FALLBACK=0` pour exiger l'API (mode strict) et
`AI_BREAKER_THRESHOLD` / `AI_BREAKER_SECONDS` pour ajuster le disjoncteur.

### Prouver que le verrou est réel

```bash
python scripts/verify_seed.py                       # 34 contrôles machine sur les solutions officielles
python scripts/demo_gate.py --puid "IMO 1988/6"     # 25 contrôles de bout en bout, en HTTP
python manage.py verify_lock_sample --sample 100    # verrou sur 100 fiches tirées au hasard
python manage.py verify_lock_sample --all           # les 4 332 fiches verrouillées, une par une
```

Le même script sait rejouer la porte sur **n'importe quelle fiche**, y compris importée :

```bash
python manage.py shell -c "from problems.models import Problem; \
  open('/tmp/copie.txt','w').write(Problem.objects.get(puid='OMNI IMO/001').solution.official_tex)"
python scripts/demo_gate.py --puid "OMNI IMO/001" --submission-file /tmp/copie.txt
```

`scripts/demo_gate.py` pilote un serveur réel comme le ferait un navigateur (CSRF,
cookies, POST JSON) et affiche un transcript : il remet d'abord la progression à zéro
pour être rejouable, puis vérifie que la page verrouillée ne contient pas la clé de
correction, que « indice 2 avant indice 1 » est refusé en `409`, qu'une rédaction vague
est refusée, qu'une vraie preuve est acceptée et débloque la page, et qu'une nouvelle
soumission sur une fiche déjà débloquée est archivée sans être réévaluée.

---

## 2. Ce qui a été construit (carte des livrables)

| Livrable | Où |
|---|---|
| **1. Schéma + migrations** | `problems/models.py`, `problems/migrations/0001_initial.py` (schéma) et `0002_…` (libellés FR), DDL PostgreSQL écrit à la main dans [`sql/schema_postgres.sql`](sql/schema_postgres.sql) |
| **2. Script d'ingestion des fixtures** | `problems/ingestion.py` + `manage.py ingest_arch_fixture fixtures/all.json` (`manage.py fetch_arch_fixture` télécharge la fixture amont) |
| **3. Endpoint de vérification** | `problems/services/verification.py` (étapes A–D), `problems/services/ai_grader.py` (prompt, fournisseurs, analyse JSON stricte), `problems/views.py::verify_submission_view` → `POST /api/problems/<id>/verify` |
| **4. Interface & verrouillage** | `problems/templates/problems/problem_detail.html`, `static/problems/js/problem.js`, `static/problems/css/app.css` (KaTeX servi localement + repli Unicode) |
| bonus : démo du verrou | `scripts/demo_gate.py` |
| bonus : vérificateur des clés | `scripts/verify_seed.py` |
| bonus : inspecteur de fixture | `scripts/parse_arch_fixture.py` |

### Schéma

```
Problem        id, puid (unique, « IMO 2018/3 »), legacy_puid, statement_tex,
               category (algebra|combinatorics|geometry|number_theory|misc),
               difficulty_track (foundation|olympiad|hard), source_url, answer_tex
Hint           id, problem FK, order_index (1..n, unique par fiche), content_md, keywords
Solution       id, problem OneToOne, official_tex, attribution          ← la clé de correction
UserProgress   id, user FK, problem FK (unique ensemble), is_solved=false, unlocked_at
UserSubmission id, user FK, problem FK, submitted_text, status (PENDING|PASSED|REJECTED),
               ai_feedback, engine, latency_ms, raw_response (staff only), created_at
HintReveal     id, user FK, hint FK (unique ensemble), revealed_at      ← impose l'ordre des indices
```

Deux invariants sont garantis par la **base**, pas seulement par Python :

* `unique_progress_per_user (user_id, problem_id)` — une seule ligne de progression par fiche.
* `unique_reveal_per_user_hint (user_id, hint_id)` + `unique_hint_order_per_problem` —
  impossible de sauter un palier d'indice, impossible de le révéler deux fois.

---

## 3. Le verrou IA (étapes A–D)

`POST /api/problems/<id>/verify` avec `{"text": "<votre rédaction>"}` (ou en
`application/x-www-form-urlencoded`) et l'en-tête `X-CSRFToken`.

| Étape | Ce qui se passe |
|---|---|
| **A. Récupérer** | Charger la fiche, la progression de l'utilisateur et `Solution.official_tex`. Une fiche sans solution officielle répond `422 no_official_solution` — elle ne peut jamais être débloquée au hasard. Une fiche déjà débloquée est **archivée** (`engine: "archived"`, pas de réévaluation) et ne peut pas être reverrouillée. |
| **B. Recevoir** | Valider la soumission : non vide, ≤ `MAX_SUBMISSION_CHARS`, quota par utilisateur (`VERIFY_RATE_LIMIT` / `VERIFY_RATE_WINDOW_SECONDS`). Chaque tentative est enregistrée en base avant l'évaluation. |
| **C. Corriger** | Construire la requête avec la **solution officielle verbatim comme référence** et le prompt système fixe du correcteur IMO ; appeler le fournisseur (OpenAI `temperature=0` + `response_format=json_object` ; Anthropic avec un tour assistant pré-rempli par `{`). Seul `{"passed": bool, "feedback": str}` est accepté : les balises markdown sont retirées, une réponse illisible est retentée puis traitée comme une panne du correcteur. |
| **D. Débloquer** | `passed: true` → `status=PASSED`, `UserProgress.is_solved=true`, `unlocked_at=NOW()`, réponse `{"success": true, "unlocked": true, …}`. `passed: false` → `status=REJECTED`, le verrou reste fermé, et la réponse est **toujours `success: true` avec `unlocked: false`** pour que le client reçoive systématiquement un verdict. |

Une panne du correcteur n'est **jamais** convertie en échec : la ligne est enregistrée en
`PENDING` (HTTP `503`, réessayable), afin qu'un verdict négatif signifie toujours
« la mathématique est fausse » et non « le réseau est tombé ».

Endpoints annexes : `GET /api/problems/<id>/status` (état du verrou sans charger la page),
`POST /api/problems/<id>/reset` (reverrouillage démo/dev si `ALLOW_PROGRESS_RESET=1`),
`POST /api/problems/<id>/hints/<hint_id>/reveal` (`200` servi, `409` si le palier précédent
n'est pas ouvert, `404` pour un indice d'une autre fiche, `403` hors connexion quand `DEMO_MODE=0`).

### Le prompt système du correcteur (verbatim, en un seul exemplaire)

Le prompt exact demandé par le cahier des charges — correcteur IMO, tolérant sur les
étapes de calcul omises, intraitable sur les arguments vagues, **JSON uniquement et sans
balises markdown** — vit à un seul endroit : la constante
`problems/services/ai_grader.py::SYSTEM_PROMPT`. Modifiez-la là et nulle part ailleurs :
tous les chemins fournisseurs, les tentatives et les tests lisent cette constante.

```
Rôle : Tu es un correcteur expert des Olympiades Internationales de Mathématiques (IMO).
Tâche : Évaluer si le plan de solution ou la preuve soumis contient une logique mathématique valide et arrive au bon résultat par rapport à la solution officielle.
Données : Énoncé={statement}, Solution officielle={official_tex}, Soumission étudiant={user_submission}.
Réponds UNIQUEMENT en JSON strict sans balises markdown :
{
  "passed": true ou false,
  "feedback": "2-3 phrases explicatives."
}
```

> **Note d'implémentation.** La substitution des trois champs `{statement}`,
> `{official_tex}` et `{user_submission}` se fait par remplacement de chaîne littéral, et
> **non** par `str.format()` : l'exemple JSON du prompt contient des accolades que
> `str.format` interpréterait comme des champs à substituer. Un test le verrouille
> (`GraderPromptContractTests`) et vérifie que le prompt reste identique au texte du cahier
> des charges.

---

## 4. Bases de données : SQLite en développement, PostgreSQL pour de vrai

Ordre de priorité : `DATABASE_URL` → `POSTGRES_*` → SQLite embarqué (défaut).

```bash
# PostgreSQL (le livrable 1 fournit aussi le DDL écrit à la main)
createdb arch_olympiad
export DATABASE_URL=postgres://arch_app:secret@127.0.0.1:5432/arch_olympiad
pip install 'psycopg[binary]'

python manage.py migrate                      # l'ORM possède le schéma
# … ou, si un outil de migration externe le possède :
psql "$DATABASE_URL" -f sql/schema_postgres.sql
python manage.py migrate --fake-initial
```

`sql/schema_postgres.sql` contient en plus un durcissement que Django ne crée pas :
contraintes `CHECK` sur les colonnes d'énumération, cohérence
(`is_solved = true ⇔ unlocked_at IS NOT NULL`), index `pg_trgm` pour la recherche, et la
recette d'un rôle applicatif à moindre privilège.

Pour la production (HSTS, cookies `Secure`/`__Host-`, cadre `DENY`, `DEMO_MODE=0`,
cache Redis partagé pour le quota) :

```bash
export DJANGO_SETTINGS_MODULE=config.settings_production
export DJANGO_ALLOWED_HOSTS=olympiad.example.com
export DJANGO_SECRET_KEY=$(python -c 'import secrets; print(secrets.token_urlsafe(64))')
python manage.py check --deploy
```

`config/settings_production.py` refuse de démarrer avec une clé secrète de démo, un
`ALLOWED_HOSTS` vide ou une configuration PostgreSQL absente.

---

## 5. Le catalogue : deux corpus, 4 300+ énoncés

La plateforme démarre avec un catalogue réel, pas trois exemples.

| Corpus | Contenu | Origine |
|---|---|---|
| **Curaté** (10 fiches) | énoncés et indices rédigés à la main (en français), solutions vérifiées machine à machine | `problems/seed_data/showcase.py` |
| **Importé** (4 324 fiches) | énoncé + solution officielle + réponse compacte + domaine + difficulté | [Omni-MATH](https://huggingface.co/datasets/KbsdJames/Omni-MATH) (Apache-2.0), versionné dans `fixtures/omni_math.jsonl` |

```bash
make corpus                                    # tout le corpus (~15 s)
python manage.py ingest_omni_math --sources imo,imo_shortlist,usamo
python manage.py ingest_omni_math --limit 200 --dry-run
python manage.py ingest_omni_math --purge      # retire l'import précédent
```

Ce que fait l'importeur :

* PUID stable `OMNI <CONCOURS>/<n°>` (`OMNI IMO SL/042`, `OMNI Putnam/007`) → l'import est
  idempotent : relancer met à jour, ne duplique pas ; deux sources partageant un libellé
  (`apmo`, `apmoapmo_sol` → **APMO**) reçoivent des numéros distincts ;
* domaine Omni-MATH → `Category`, difficulté 0–10 → `DifficultyTrack`
  (< 4 : initiation, < 6,5 : olympiade, au-delà : difficile) ;
* réponse compacte → `answer_tex`, révélée **avec** la solution officielle ;
* **trois indices méthodologiques** par fiche, générés localement par
  `problems/services/coach_hints.py` : piste générale (catégorie), technique reconnue dans la
  solution officielle (22 procédés : Vieta, descente infinie, tiroirs, double comptage,
  invariant, récurrence, valuations, bijection, puissance d'un point, graphes, espérance…), puis
  liste de contrôle avant rédaction. Aucun appel réseau, et **aucune phrase de la solution
  officielle n'est recopiée** : un test vérifie que les indices ne citent jamais `official_tex`
  (sinon la génération deviendrait une fuite du verrou).

### Traduire le corpus (4 324 énoncés, français)

```bash
python manage.py translate_corpus                # traduit (cache reprenable, reprise auto)
python manage.py translate_corpus --apply         # écrit les traductions en base
python manage.py translate_corpus --apply --revert   # remet l'anglais d'origine
```

* **Aucune mathématique n'est touchée** : chaque traduction est comparée à l'original
  (mêmes formules, mêmes commandes LaTeX, dans l'ordre) ; si la signature diffère, la
  version anglaise est conservée et l'énoncé repart en reprise. Jamais de formule abîmée.
* **Cache reprenable** `var/translations.jsonl` : chaque résultat est écrit au fil de l'eau,
  une coupure ne fait perdre que la requête en cours ; l'anglais d'origine est conservé dans
  le cache et reste dans `fixtures/omni_math.jsonl` (donc `--revert` est exact).
* **Débit** : le palier gratuit de Gemini plafonne à 15 requêtes/minute ; la commande régule
  sa cadence (AIMD) et regroupe 10 énoncés par requête (`--batch`), avec rotation entre
  plusieurs modèles (`--model`, `--rpm`). Les quotas **journaliers** dépendent du modèle :
  500 requêtes/jour pour les « lite » (`gemini-3.5-flash-lite`, `gemini-3.1-flash-lite`,
  utilisés en priorité), 20/jour pour les autres (`gemini-3.8-flash`, …).
* **Polissage** : `--polish` traduit les mots anglais oubliés **dans** le mode texte
  (`\text{if }` → `\text{si }`) sans jamais toucher aux formules ; `--revert` reste exact
  (l'anglais d'origine est conservé dans le cache et dans `fixtures/omni_math.jsonl`).
* Les **indices générés** et l'interface sont en français ; les solutions officielles restent
  dans leur langue d'origine (c'est la référence mathématique, on ne la paraphrase pas — le
  correcteur IA traduit le raisonnement de l'élève vers elle).

**Où en est la traduction ?** Le quota gratuit de l'API (500 requêtes par modèle et par jour)
est le seul facteur limitant : une passe complète consomme tout le quota du jour. Le cache est
la source de vérité, et la commande ne retente que ce qui n'est pas encore accepté :

```bash
python3 scripts/translation_progress.py   # couverture française + répartition du restant
make translate                            # une passe de reprise, puis écriture en base
make translate-status                     # l'avancement, sans rien lancer
bash scripts/finish_translation.sh        # boucle sans surveillance (reprise toutes les 15 min)
```

`finish_translation.sh` est le filet de sécurité : lancé le soir, il réessaie toutes les quinze
minutes et écrit en base dès que le quota se réinitialise — le corpus se termine seul. Les
énoncés encore en anglais restent parfaitement lisibles en attendant, et `--revert` sait
toujours revenir à la version d'origine.

Le catalogue distingue les deux corpus dans l'interface : filtre **Corpus**, raccourcis par
concours, recherche plein texte sur PUID/énoncé/indices, et un bouton **Problème au hasard**
(`/problems/au-hasard/`, qui évite ce que vous avez déjà débloqué).

## 6. Ingérer le corpus ARCH (livrable 2)

```bash
python manage.py fetch_arch_fixture                                # → fixtures/all.json depuis otis-web
python scripts/parse_arch_fixture.py fixtures/all.json --summary   # reconnaissance sans Django
python manage.py ingest_arch_fixture fixtures/all.json --dry-run   # analyse + rapport, aucune écriture
python manage.py ingest_arch_fixture fixtures/all.json \
    --puid-map data/puid_map.example.json \
    --default-category auto --default-track auto \
    --report var/ingest_report.json
```

Ce que le pipeline traite explicitement (la fixture amont est au format Django mais sa
copie publique ne contient que des **données factices**) :

* Les lignes sont des `{"model": "arch.problem"|"arch.hint"|"arch.solution", "pk", "fields"}` ;
  les modèles inconnus sont comptés et ignorés, jamais fatals.
* Le champ amont `arch.hint.number` est un **identifiant d'indice, pas un palier** :
  l'importateur renumérote les indices `1..n` dans l'ordre amont pour que la révélation
  par paliers ait un sens.
* Les PUID publics sont des codes ARCH opaques de 6 lettres. `--puid-map` les convertit en
  identifiants lisibles ; sans cela, l'ingestion réussit mais signale la qualité des PUID
  dans son rapport (`var/ingest_report.json`) — exactement ce qu'un vrai déploiement doit voir.
* Les énoncés vivent en amont dans `arch/data/<PUID>.tex`, pas dans la fixture. Les lignes
  sans énoncé sont importées et signalées (`--skip-missing-statement` pour les écarter) ;
  elles se complètent dans l'admin Django.
* Réimporter est idempotent : les fiches sont indexées sur `legacy_puid`, les indices sur
  `(problem, order_index)`, les solutions sur le lien `OneToOne`.

Les 10 fiches du corpus curaté (`manage.py seed_showcase`) sont celles dont les solutions
officielles sont **vérifiées machine** par `scripts/verify_seed.py` : IMO 2019/1, 2014/1,
2005/4, 1988/6, 2014/5, 2006/1, 2001/3, 2001/1, 1993/5 et l'exercice d'initiation 2018/A1.

---

## 7. Tests & vérification

```bash
python manage.py check_ai_setup           # 18 contrôles : fournisseur, contrat du prompt, analyseur JSON, correcteur hors ligne
python manage.py test problems -v 2       # 110 tests : verrou, indices, auth, ingestion, traduction, vitrine, interface
python scripts/verify_seed.py             # 34 contrôles machine sur les clés de correction (symbolique / exhaustif / Monte-Carlo)
python scripts/demo_gate.py --puid "IMO 1988/6"   # 25 contrôles HTTP contre un serveur lancé
```

Dernier passage mesuré : `verify_lock_sample --all` → **4 332 / 4 332 pages verrouillées
propres** (aucune phrase de la solution officielle, aucune réponse compacte non publique dans
le HTML), et `demo_gate` → 25/25.

La suite de tests verrouille ce qui, sinon, pourrirait en silence : la page verrouillée ne
contient jamais la clé de correction, les révélations d'indices hors ordre sont refusées,
une fiche déjà débloquée ne peut pas être réévaluée, une panne du correcteur produit
`PENDING` et jamais `REJECTED`, l'analyseur d'ingestion est idempotent, le rendu
Markdown/TeX échappe le HTML tout en préservant les maths, le prompt système est identique
au texte du cahier des charges, et `test_ui_contract.py` fixe les promesses visibles de
l'interface (le bandeau de verrouillage mot pour mot, l'accordéon d'indices, le bouton
« Soumettre à l'évaluation IA » avec son indicateur de chargement, KaTeX servi localement,
la mise en page débloquée avec solution + historique).

---

## 8. Design system et aperçus hors ligne

L'interface est écrite **à la main** : aucun framework CSS, aucun CDN, aucun nom de classe
utilitaire. Un seul fichier fait autorité, `problems/static/problems/css/app.css`
(~20 sections numérotées : jetons, thèmes, topbar, composants, pages, responsive, impression).

* **Jetons** — couleurs (`--bg`, `--bg-elev`, `--accent`, `--ok`, `--warn`, `--danger`), typographie
  (`--font-ui`, `--font-display`, `--font-mono`), espacement (`--sp-1`…`--sp-8`), rayons, ombres,
  anneaux de focus. Rien n'est codé en dur ailleurs dans la feuille.
* **Deux thèmes** — sombre par défaut, clair via `:root[data-theme="light"]`. Le choix est
  mémorisé dans `localStorage` (`arch-theme`) et appliqué par un script en ligne **avant le premier
  rendu** : pas de clignotement. Sans JavaScript, le thème suit `prefers-color-scheme`.
* **Codage couleur par catégorie** — la barre latérale des cartes, les badges et les barres de
  progression reprennent la teinte Algèbre / Combinatoire / Géométrie / Théorie des nombres.
* **HTML sémantique** — `header`/`main`/`section`/`article`/`aside`/`nav`, hiérarchie de titres
  respectée, `aria-label` sur les zones, `role="progressbar"` sur la progression, lien d'évitement
  « Aller au contenu principal », focus visible partout. Les seuls styles en ligne du projet sont
  la propriété `--pct` des barres de progression (une donnée, pas une décoration).
* **Sans réseau** — police du système (aucune requête de police) et KaTeX **embarqué** dans
  `static/vendor/katex`. Rien à installer : les maths s'affichent en local, et le repli
  `js/app.js` reste lisible même sans KaTeX.

### Voir le rendu sans navigateur

`scripts/make_preview.py` récupère les pages d'un serveur en cours d'exécution et **incorpore**
le CSS et le JS : il produit des fichiers autonomes, ouvrables hors ligne, utiles aussi pour les
aperçus qui n'ont pas d'accès réseau.

```bash
make run &                                   # serveur sur :8000
make preview                                 # → design/apercu-*.html
```

Les aperçus couvrent la liste des exercices, une fiche verrouillée, une fiche débloquée, le
tableau de bord et la connexion.

## 9. Notes de sécurité

* **Les clés de correction restent côté serveur.** La page verrouillée n'affiche qu'un
  texte factice et un bandeau ; `official_tex` et `answer_tex` ne sont mis dans le contexte
  du template qu'après `UserProgress.is_solved = true`. Les tests utilisent des sentinelles
  (`SOLUTION_SENTINELS`) pour que toute régression ici casse immédiatement.
* **Le mode démo est bruyant.** `DEMO_MODE=1` partage un compte invité et est refusé par
  `config/settings_production.py`.
* **CSRF actif sur l'API** (en-tête `X-CSRFToken`) ; les origines `https://*.e2b.app` sont
  autorisées en démo pour l'aperçu.
* **Quota** par utilisateur, stocké en cache — utilisez Redis en production pour qu'il soit
  partagé entre les workers.
* **Les soumissions sont des textes non fiables** : stockées brutes, échappées au rendu,
  jamais évaluées ; la requête au correcteur est encodée en JSON. `raw_response` (sortie du
  modèle) n'est visible qu'avec le statut staff dans l'admin.
* **Prompt système.** Le prompt étant repris *verbatim* du cahier des charges, il ne
  contient pas de garde anti-injection : la sortie n'est utilisée que comme
  `{passed, feedback}` typé, et un verdict n'est appliqué qu'après analyse JSON stricte —
  mais si votre menace inclut des étudiants qui cherchent à manipuler le modèle, ajoutez
  une ligne de garde au prompt (le test de conformité devra alors être mis à jour).

---

## 10. Arborescence du dépôt

```
arch-olympiad/
├── config/                 settings.py · settings_production.py · urls.py · wsgi.py · asgi.py
├── problems/
│   ├── models.py           Problem, Hint, Solution, UserProgress, UserSubmission, HintReveal
│   ├── migrations/         0001_initial.py · 0002_… (libellés FR)
│   ├── services/           tex.py · ai_grader.py (SYSTEM_PROMPT) · verification.py · throttle.py · coach_hints.py
│   ├── views.py urls.py    pages d'étude + API de vérification
│   ├── ingestion.py        analyseur/importateur de fixture ARCH (livrable 2)
│   ├── management/commands/  fetch_arch_fixture · ingest_arch_fixture · ingest_omni_math · seed_showcase · translate_corpus · verify_lock_sample · check_ai_setup
│   ├── seed_data/showcase.py corpus curaté, solutions vérifiées machine
│   ├── templates/problems/   base · problem_list · problem_detail · dashboard · registration/*
│   ├── static/problems/      css/app.css (design system, 20 sections) · js/app.js · js/problem.js
│   ├── static/vendor/katex/  KaTeX local (woff2) — les maths marchent hors ligne
│   └── tests/                factories.py · test_gate.py · test_ingestion_and_rendering.py · test_ui_contract.py · test_omni_corpus.py
├── fixtures/all.json       fixture ARCH amont (données factices ; supprimable)
├── fixtures/omni_math.jsonl corpus Omni-MATH versionné (4 428 lignes, 7,5 Mo)
├── sql/schema_postgres.sql DDL PostgreSQL + durcissement
├── scripts/                verify_seed.py · demo_gate.py · parse_arch_fixture.py · make_preview.py
│                             build_site.py (vitrine Netlify) · translation_progress.py
│                             finish_translation.sh (finition de la traduction)
├── site/                   vitrine statique publiée telle quelle par Netlify (make site)
├── netlify.toml            configuration Netlify : dossier publié, en-têtes, 404
├── Dockerfile              image de production (Gunicorn + WhiteNoise, sans nginx)
├── deploy/                 start.sh (migrations, statique, Gunicorn) · render.yaml (Blueprint)
├── design/                 aperçus HTML autonomes (CSS/JS incorporés, hors ligne)
├── data/puid_map.example.json
├── docs/                   SETUP.md (config/déploiement/dépannage) · API.md (contrat des endpoints)
├── .env.example · requirements.txt · manage.py · Makefile
```

## 11. Provenance et limites connues

* Le format des indices et les conventions de PUID suivent
  [vEnhance/otis-web](https://github.com/vEnhance/otis-web) (ARCH). Ce projet est une
  réimplémentation indépendante : aucun code amont n'est recopié. Le seul composant tiers
  embarqué est KaTeX (`problems/static/vendor/katex`, licence MIT, polices woff2 seules).
* La fixture publique `fixtures/all.json` contient des **données factices** (3 fiches,
  0 solution) avec des PUID opaques : c'est l'état amont, pas un bug de l'importateur.
* Les sources PreTeXt `.ptx` ne sont pas analysées ; les énoncés viennent de la fixture,
  d'un fichier `arch/data/<PUID>.tex`, ou de la saisie dans l'admin.
* Le correcteur hors ligne est un **contrôle de plausibilité**, étiqueté comme tel dans son
  feedback et dans l'interface (`offline-heuristic`) : il mesure la longueur, les marqueurs
  de preuve et le recouvrement du vocabulaire de la solution de référence, avec un seuil de
  longueur proportionnel à la solution, pour qu'une preuve courte mais complète passe aussi.
  Configurez un vrai fournisseur pour une correction mathématique.
* L'interface et le correcteur parlent français ; les énoncés, indices et solutions du
  corpus embarqué sont encore en anglais (textes mathématiques sourcés et vérifiés).
  Dites-le si vous voulez le corpus traduit — la structure est prête.
