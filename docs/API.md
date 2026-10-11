# Référence de l'API

Tous les endpoints renvoient du JSON sauf mention contraire. Le CSRF est exigé sur
chaque `POST` (middleware `CsrfViewMiddleware` de Django) : renvoyez le cookie
`csrftoken` dans l'en-tête `X-CSRFToken` — c'est ce que fait le front dans
`problems/static/problems/js/problem.js`, et `scripts/demo_gate.py` montre comment le
faire depuis Python sans aucune dépendance.

| Méthode | Chemin | Rôle |
|---|---|---|
| `POST` | `/api/problems/<id>/verify` | Soumettre une rédaction au correcteur IA (le verrou) |
| `GET` | `/api/problems/<id>/status` | État du verrou sans charger la page |
| `POST` | `/api/problems/<id>/reset` | Reverrouiller une fiche pour l'utilisateur courant (démo/dev) |
| `POST` | `/api/problems/<id>/hints/<hint_id>/reveal` | Révéler un palier d'indice |

Des alias avec slash final existent pour chaque route (`/verify/`, `/status/`, …).

---

## `POST /api/problems/<id>/verify`

Vérifie une rédaction par rapport à la solution officielle. Implémenté en étapes A–D dans
`problems/services/verification.py`.

### Requête

```json
{ "text": "Let $k = (a^2+b^2)/(ab+1)$ ... (Markdown + LaTeX)" }
```

* `text` (ou l'alias historique `submission`) — seul champ obligatoire.
* Un corps `application/x-www-form-urlencoded` (`text=...&redirect=1`) est aussi accepté :
  c'est ce qu'utilise le repli sans JavaScript ; avec `redirect=1`, la réponse est une
  redirection `303` vers la fiche au lieu de JSON.

### Succès (HTTP 200)

La forme est **identique pour un succès et un échec** — `success` vaut `true` dans les
deux cas, seul `unlocked` change. C'est volontaire : le client affiche toujours un verdict.

```json
{
  "success": true,
  "unlocked": true,
  "status": "PASSED",
  "feedback": "Correct Vieta jumping argument: the descent a' = kb - a is justified and the minimality contradiction closes it. The step a' > 0 is proven rather than assumed.",
  "engine": "openai:gpt-4o",
  "latency_ms": 3421,
  "submission_id": 118,
  "rate_remaining": 19
}
```

```json
{
  "success": true,
  "unlocked": false,
  "status": "REJECTED",
  "feedback": "The Vieta jump is stated but a' > 0 is assumed. Without 0 < a' < b the minimality argument does not close, so the descent is not yet a proof.",
  "engine": "openai:gpt-4o",
  "latency_ms": 2988,
  "submission_id": 119,
  "rate_remaining": 18
}
```

### Erreurs

| Statut | `error` | Signification |
|---|---|---|
| `400` | `empty_submission`, `too_long`, `invalid_json` | Rien (ou trop) à corriger |
| `403` | `authentication_required` | Hors connexion alors que `DEMO_MODE=0` |
| `403` | `csrf` | Jeton CSRF absent ou invalide |
| `404` | `not_found` | Fiche inexistante |
| `422` | `no_official_solution` | La fiche n'a pas encore de ligne `Solution` — impossible à débloquer par construction |
| `429` | `rate_limited` | Quota `VERIFY_RATE_LIMIT` par `VERIFY_RATE_WINDOW_SECONDS` (voir `Retry-After`) |
| `503` | `grader_unavailable` | Toutes les tentatives ont échoué ; la soumission est enregistrée `PENDING` et réessayable |

Les corps d'erreur sont `{"success": false, "error": "<code>", "feedback": "<texte lisible>"}`.

### Effets en base

* Accepté → `UserSubmission.status = PASSED`, `UserProgress.is_solved = true`,
  `unlocked_at = NOW()`. Toute soumission ultérieure sur la fiche est stockée avec
  `engine = "archived"` et n'est **pas** réévaluée (le verrou ne se referme pas tout seul).
* Refusé → `status = REJECTED` ; la solution reste verrouillée.
* Panne du correcteur → `status = PENDING` ; la solution reste verrouillée.

---

## `GET /api/problems/<id>/status`

```json
{
  "success": true,
  "problem_id": 5,
  "puid": "IMO 1988/6",
  "is_solved": false,
  "unlocked_at": null,
  "hints_total": 4,
  "hints_revealed": 1,
  "next_hint_id": 18,
  "submissions": 3,
  "can_verify": true,
  "latest_submission": {"id": 119, "status": "REJECTED", "feedback": "…", "engine": "openai:gpt-4o", "created_at": "2026-10-11T09:12:44+00:00"},
  "rate_remaining": 18
}
```

(The legacy keys `problem_puid` / `unlocked` / `revealed_hints` / `hint_count` are
also present, so older clients keep working.)

`can_verify` est `false` quand la fiche n'a pas de solution officielle (l'API répondra
`422`) — utile pour désactiver le bouton de soumission.

---

## `POST /api/problems/<id>/hints/<hint_id>/reveal`

Les indices s'ouvrent strictement dans l'ordre `order_index`. La réponse ne contient le
texte de l'indice que si la révélation est légale :

```json
{ "success": true, "hint_id": 18, "order_index": 1, "content_html": "<p>…</p>", "revealed_count": 1, "hint_count": 4 }
```

| Statut | `error` | Signification |
|---|---|---|
| `200` | — | Révélé (idempotent : révéler un indice déjà ouvert le renvoie) |
| `403` | `authentication_required` | Hors connexion alors que `DEMO_MODE=0` |
| `404` | `hint_not_found` | L'indice appartient à une autre fiche |
| `409` | `hint_locked` | Un palier inférieur est encore fermé (`next_hint_id` indique lequel ouvrir) |

---

## `POST /api/problems/<id>/reset`

Disponible quand `ALLOW_PROGRESS_RESET=1` (défaut en développement). Supprime **uniquement**
la progression, les indices révélés et les soumissions de l'utilisateur courant pour cette
fiche, afin qu'une démonstration soit rejouable. Répond `403 {"error": "disabled"}` en
production, où `config/settings_production.py` la désactive par défaut.

```json
{ "success": true, "unlocked": false, "feedback": "Progress reset for this problem." }
```

---

## Quota de correction

| Réglage | Défaut | Effet |
|---|---|---|
| `VERIFY_RATE_LIMIT` | `20` | Tentatives par utilisateur et par fenêtre (`0` désactive) |
| `VERIFY_RATE_WINDOW_SECONDS` | `3600` | Longueur de la fenêtre |
| `MAX_SUBMISSION_CHARS` | `20000` | Plafond dur sur `text` |

Le budget restant est renvoyé en `rate_remaining` à chaque réponse de vérification et
affiché dans l'interface (« N soumission(s) restante(s) sur 20 »).

## Exemple complet

```bash
# 1. récupérer un jeton CSRF (toute page rendant un formulaire pose le cookie)
curl -s -c /tmp/jar http://127.0.0.1:8000/accounts/login/ > /dev/null
TOKEN=$(awk '/csrftoken/ {print $7}' /tmp/jar)

# 2. soumettre une rédaction
curl -s -b /tmp/jar -H "X-CSRFToken: $TOKEN" -H 'Content-Type: application/json' \
     -d '{"text":"Let $k=\\frac{a^2+b^2}{ab+1}$ and use Vieta jumping with $a'\''=kb-a$ ..."}' \
     http://127.0.0.1:8000/api/problems/5/verify | python3 -m json.tool

# 3. ou rejouer tout le parcours, comme un navigateur :
python scripts/demo_gate.py --puid "IMO 1988/6"
```
