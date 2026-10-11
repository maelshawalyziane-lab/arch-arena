#!/usr/bin/env bash
#
# Finition de la traduction française du corpus, sans surveillance.
#
# Le quota gratuit de l'API Gemini est limité (500 requêtes par modèle et par
# jour) : quand il est épuisé, chaque tentative échoue proprement et le cache
# (var/translations.jsonl) conserve ce qui est déjà accepté. Cette boucle
# réessaie donc toutes les 15 minutes et écrit en base dès qu'il reste quelque
# chose à traduire — le jour suivant, le corpus se termine tout seul.
#
# Utilisation :
#     scripts/finish_translation.sh            # en arrière-plan
#     make translate                           # équivalent manuel, une passe
#
set -u

cd "$(dirname "$0")/.."
LOG=var/translation_loop.log
mkdir -p var

remaining() {
    python3 - <<'PY'
import json
from pathlib import Path

rows = [json.loads(line) for line in Path("var/translations.jsonl").read_text(encoding="utf-8").splitlines() if line.strip()]
latest = {}
for row in rows:
    latest[row["puid"]] = row
print(sum(1 for row in latest.values() if row["status"] != "ok"))
PY
}

while true; do
    echo "=== $(date -Is) · reprise ($(remaining) énoncé(s) en attente) ===" >>"$LOG"
    # lot de 10 : une requête couvre dix énoncés, ce qui économise le quota
    python3 manage.py translate_corpus --workers 4 --batch 10 --rounds 1 --singles \
        --rpm 10 --cache var/translations.jsonl >>"$LOG" 2>&1
    python3 manage.py translate_corpus --apply --cache var/translations.jsonl >>"$LOG" 2>&1

    left=$(remaining)
    echo "--- $(date -Is) · restant : $left" >>"$LOG"
    if [ "$left" = "0" ]; then
        echo "=== $(date -Is) · corpus intégralement traduit ===" >>"$LOG"
        break
    fi
    sleep 900
done
