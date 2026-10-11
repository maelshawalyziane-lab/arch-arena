# Publier ARCH Arena

Ce document répond à une question précise : **« je veux publier le site »**. Il y a deux
réponses, parce qu'il y a deux objets dans ce dépôt.

| Ce que vous voulez publier | Où | Statut |
|---|---|---|
| La **vitrine** (présentation + aperçus de l'interface) | **Netlify** | prêt : `make site`, puis publication |
| La **vraie plateforme** (verrou IA, correction, progression) | Render, Railway, Fly.io, PythonAnywhere, VPS | fichiers fournis : `Dockerfile`, `deploy/start.sh`, `deploy/render.yaml` |

---

## 0. Le plus court chemin

**Vous voulez juste une adresse en ligne, maintenant** → la vitrine, sur Netlify :

```bash
make publish        # régénère les aperçus et site/, puis rappelle les étapes
```
puis glissez le dossier `site/` sur <https://app.netlify.com/drop>. C'est en ligne en
quelques secondes, gratuitement. Les formulaires y sont neutralisés (c'est annoncé au
clic) puisque la vitrine n'a pas de serveur.

**Vous voulez la plateforme qui corrige vraiment** → Render, avec `deploy/render.yaml` :

1. poussez le dépôt sur GitHub ;
2. Render → *New* → **Blueprint** → choisissez le dépôt ;
3. renseignez trois variables demandées : `DJANGO_ALLOWED_HOSTS`,
   `DJANGO_CSRF_TRUSTED_ORIGINS`, `GEMINI_API_KEY` (plus `ARCH_ADMIN_PASSWORD`) ;
4. c'est tout : au premier démarrage, le conteneur crée le compte unique, importe les
   4 334 problèmes **et** applique les 4 040 énoncés français (~20 secondes, sans réseau).

---

## 1. Pourquoi la plateforme ne peut pas tourner sur Netlify

Netlify sert des **fichiers statiques** et exécute des **fonctions serverless**. Ce projet
est une application Django : il lui faut un serveur et une base de données. Trois choses,
en particulier, ne peuvent pas descendre dans le navigateur :

* **la clé du correcteur IA.** Si elle était envoyée au navigateur, n'importe qui la lirait
  dans les outils de développement et dépenserait votre quota — ou la révoquerait.
* **la solution officielle.** Le cahier des charges est explicite : elle ne doit **jamais** être
  présente dans la page tant que `is_solved == false`. Un export statique ne peut pas décider
  quoi servir selon l'état de la progression.
* **la progression et l'historique.** Ils vivent en base (4 334 fiches, 13 010 indices,
  soumissions, déblocages) et sont liés à un compte.

Publier l'application sur un hébergeur statique reviendrait donc soit à retirer le verrou,
soit à exposer la clé. Ni l'un ni l'autre n'est acceptable : on sépare les deux objets.

---

## 2. Publier la vitrine sur Netlify (5 minutes, gratuit)

La vitrine est construite dans `site/` : une page de présentation, onze pages réelles
(catalogue, fiche verrouillée, fiche débloquée, fiche importée, tableau de bord, connexion,
thème clair…) et `netlify.toml`.

### Étape 1 — (re)construire le dossier

```bash
make site          # = python3 scripts/build_site.py
```

Le script réécrit les liens internes pour qu'ils pointent vers les bons aperçus, neutralise
les formulaires (sur un hébergeur statique un POST ne peut pas aboutir : c'est annoncé au
clic) et vérifie que **chaque lien local vise un fichier existant**.

### Étape 2 — publier

**Option A — glisser-déposer (le plus rapide).** Ouvrez <https://app.netlify.com/drop> et
glissez le dossier `site/`. Netlify vous donne une URL du type
`https://random-name-123456.netlify.app` en quelques secondes.

**Option B — en ligne de commande.**

```bash
npm install -g netlify-cli
netlify deploy --dir=site --prod          # première fois : `netlify login` puis `netlify init`
```

**Option C — depuis GitHub.** Poussez le dépôt, puis *New site from Git* : `netlify.toml` est
déjà lu, `publish = "site"`. À chaque `git push`, Netlify republie.

### Étape 3 — vérifier

Ouvrez l'URL, puis testez : `/` (présentation), la galerie d'aperçus, et la fiche verrouillée
(le bandeau « 🔒 Solution officielle verrouillée… » et le bouton « Soumettre à l'évaluation IA »
doivent être là, et **aucune** solution officielle dans la page).

### Si vous changez l'interface plus tard

```bash
make publish ARCH_PASSWORD='…'      # aperçus + site/, puis le rappel des étapes
git add design site && git commit -m "vitrine à jour" && git push
```

Netlify republie à chaque `git push` (ou re-glissez `site/` si vous publiez à la main).

---

## 3. Publier la vraie plateforme (l'application qui corrige)

### 3.1 Choisir l'hébergeur

| Hébergeur | Idéal pour | Remarques |
|---|---|---|
| **Render** (`deploy/render.yaml`) | le plus simple | plan gratuit : l'instance s'endort après 15 min d'inactivité ; PostgreSQL géré |
| **PythonAnywhere** | SQLite, sans Docker | offre gratuite utilisable pour un projet personnel ; WSGI, pas de conteneur |
| **Railway / Fly.io** | conteneur, plus de contrôle | `Dockerfile` prêt ; volume persistant pour SQLite |
| **VPS (Hetzner, OVH…)** | contrôle total | `deploy/start.sh` + systemd ou Docker Compose |

### 3.2 Variables d'environnement (les seules à renseigner)

```bash
DJANGO_SETTINGS_MODULE=config.settings_production
DJANGO_SECRET_KEY=<64 caractères aléatoires>      # python3 -c 'import secrets;print(secrets.token_urlsafe(64))'
DJANGO_ALLOWED_HOSTS=votre-domaine.example        # jamais « * »
DJANGO_CSRF_TRUSTED_ORIGINS=https://votre-domaine.example
GEMINI_API_KEY=<votre clé>
AI_PROVIDER=gemini
AI_MODEL=gemini-3.5-flash-lite                    # 500 requêtes/jour sur ce modèle
DATABASE_URL=postgres://…                          # ou ALLOW_SQLITE_IN_PRODUCTION=1 (voir plus bas)
ARCH_ADMIN_PASSWORD=<mot de passe du compte admin>  # créé au premier démarrage
```

`config.settings_production` **refuse de démarrer** si la clé secrète est celle du
développement ou si les hôtes sont vides : c'est volontaire, mieux vaut un échec bruyant
qu'un site en ligne à moitié sécurisé.

### 3.3 Premier déploiement

```bash
# migrations, fichiers statiques, vérifications, puis Gunicorn : tout est dans le script
bash deploy/start.sh
```

Sur une base neuve, `deploy/start.sh` exécute **automatiquement** `manage.py bootstrap`,
qui enchaîne — et ne fait rien si la base est déjà remplie :

```bash
python manage.py bootstrap         # = compte unique + catalogue complet + français
python manage.py bootstrap --force # réimporte tout (rarement utile)
python manage.py bootstrap --skip-corpus   # le compte seulement
```

Ce que fait l'amorçage, dans l'ordre : création du superutilisateur `admin` (mot de passe
`ARCH_ADMIN_PASSWORD`), les 10 fiches curatées, les 4 324 problèmes Omni-MATH avec leurs
13 010 indices et leurs solutions, puis l'application des énoncés français depuis le cache
`var/translations.jsonl` **sans aucune requête réseau**. Comptez une vingtaine de secondes.

> Le corpus et le cache de traduction sont livrés dans l'image Docker (`.dockerignore`
> les autorise explicitement). Rien à télécharger au démarrage, rien à recopier à la main.

### 3.4 Vérifier en ligne, comme en local

```bash
python manage.py check --deploy
python manage.py verify_lock_sample --sample 50        # aucune fuite de solution
python scripts/demo_gate.py --base https://votre-domaine.example --puid "IMO 1988/6" --username admin --password '…'
curl -I https://votre-domaine.example/accounts/login/  # X-Frame-Options, nosniff…
```

### 3.5 Ce que coûte chaque option (chiffres de 2026)

| Option | Prix | Ce qu'il faut savoir |
|---|---|---|
| **Netlify** (vitrine) | **0 €** | Toujours allumé, CDN, HTTPS. Aucun formulaire ne fonctionne : c'est annoncé au clic. |
| **Render** (plateforme), plan *Starter* | ≈ 7 $/mois le service + 6 $/mois la base | Ne s'endort pas, base conservée. C'est l'option « ça marche et je n'y pense plus ». |
| **Render**, plan gratuit | 0 $ | **Deux pièges** : le service s'endort après 15 min (≈ 1 min de réveil à la première visite) et la base PostgreSQL gratuite **expire 30 jours après sa création** (puis 14 jours de grâce avant suppression). Les instances gratuites n'acceptent pas de disque persistant : un SQLite local ne survivrait donc pas à un redéploiement. |
| **VPS** (Hetzner, Scaleway…) + Docker | ≈ 4 €/mois | Le plus durable : `bash deploy/start.sh` et un volume pour `db.sqlite3`. Demande de savoir administrer une machine. |
| **Votre ordinateur** | 0 € | La plateforme est **mono-utilisateur** : la faire tourner chez vous et publier seulement la vitrine est un choix parfaitement défendable. |

Quand la clé Gemini atteint son quota gratuit, le site **ne casse pas** : avec
`AI_MODE=auto` et `AI_FALLBACK=1`, la soumission est évaluée par le correcteur déterministe
intégré, et la réponse le signale (`degraded: true`). Pour exiger l'API coûte que coûte,
mettez `AI_FALLBACK=0` : la soumission sera refusée proprement (429) au lieu d'être notée
hors ligne.

---

## 4. Ce qui change quand c'est public

1. **Le mot de passe devient la seule barrière.** Le mono-compte est un choix, pas une
   sécurité. Choisissez un mot de passe long et unique au moment de l'amorçage
   (`ARCH_ADMIN_PASSWORD`) ou changez-le ensuite (`python manage.py changepassword admin`) ;
   **ne le mettez jamais dans le dépôt** — il vit dans `.env` localement et dans les
   variables d'environnement de l'hébergeur.
2. **La clé Gemini doit rester côté serveur.** Si vous la voyez dans le code source HTML ou
   dans un appel depuis le navigateur, il y a un problème.
3. **Le quota IA est public lui aussi.** 500 requêtes/jour sur `gemini-3.5-flash-lite` : une
   page ouverte à tous peut l'épuiser. Le **disjoncteur** (2 échecs consécutifs → pause de
   5 min) et le régulateur de débit limitent la casse, mais pour un usage public, prévoyez un
   quota payant ou fermez l'accès (`DEMO_MODE=0`, inscription fermée — c'est déjà le cas).
4. **HTTPS et sauvegardes.** Les plateformes citées fournissent le certificat ; pensez à
   sauvegarder la base (PostgreSQL managé, ou `db.sqlite3` si vous avez choisi SQLite).
5. **SQLite en production**, si vous y tenez : `ALLOW_SQLITE_IN_PRODUCTION=1` (un
   avertissement est émis au démarrage). Valable pour un seul serveur avec un disque
   persistant ; sinon, prenez PostgreSQL.

---

## 5. Et si vous voulez vraiment du serverless ?

C'est possible, mais c'est un **portage**, pas un déploiement : réécrire la validation des
soumissions et la lecture des fiches en fonctions Netlify, remplacer les sessions Django par
un jeton, déplacer la base vers Netlify DB (PostgreSQL). Le résultat perdrait l'administration
Django, les commandes de gestion (`ingest_omni_math`, `translate_corpus`, `verify_lock_sample`)
et les 101 tests resteraient attachés au projet Django, pas aux fonctions. Coût réel : plusieurs
jours, pour un gain nul sur le plan fonctionnel.

La combinaison recommandée — **vitrine Netlify + application Django chez un hébergeur
Python** — donne exactement ce que vous voulez : une adresse publique propre à montrer, et
la vraie plateforme qui corrige, sans compromis sur le verrou.
