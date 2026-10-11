#!/usr/bin/env python3
"""Avancement de la traduction française du corpus.

Le cache :file:`var/translations.jsonl` est la source de vérité : une ligne par
tentative, on ne retient que la **dernière** par PUID. Le script affiche la
couverture réelle (statut ``ok``) et, pour ce qui reste, sa répartition par
source — utile pour savoir si un quota d'API a coupé la passe en cours.

    python3 scripts/translation_progress.py
    python3 scripts/translation_progress.py --cache var/translations.jsonl --detail 8
"""

from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path

STATUS_LABELS = {
    "ok": "traduits (français écrit en base)",
    "latex_mismatch": "refusés : la signature LaTeX a changé",
    "error": "échecs réseau / quota (à reprendre)",
}


def load_latest(cache: Path) -> dict[str, dict]:
    latest: dict[str, dict] = {}
    if not cache.exists():
        return latest
    for line in cache.read_text(encoding="utf-8").splitlines():
        if line.strip():
            entry = json.loads(line)
            latest[entry["puid"]] = entry
    return latest


def source_of(puid: str) -> str:
    return puid.split("/")[0].replace("OMNI ", "") or "(curaté)"


def main() -> int:
    parser = argparse.ArgumentParser(description="Avancement de la traduction du corpus")
    parser.add_argument("--cache", default="var/translations.jsonl", help="cache de traduction")
    parser.add_argument("--french-if", dest="test_substr", default="", help="compter comme traduits les énoncés contenant ce texte")
    parser.add_argument("--detail", type=int, default=6, help="sources à détailler pour ce qui reste")
    args = parser.parse_args()

    latest = load_latest(Path(args.cache))
    if not latest:
        print(f"cache introuvable ou vide : {args.cache}")
        return 1

    counts = Counter(entry["status"] for entry in latest.values())
    total = len(latest)
    ok = counts["ok"]
    print(f"corpus ................ {total} énoncés")
    print(f"couverture française .. {ok}/{total} ({ok / total * 100:.1f} %)")
    for status, label in STATUS_LABELS.items():
        if counts[status]:
            print(f"  {label:42} {counts[status]:>5}")

    remaining = [puid for puid, entry in latest.items() if entry["status"] != "ok"]
    if remaining:
        by_source = Counter(source_of(puid) for puid in remaining)
        print("\nrestant, par source :")
        for source, count in by_source.most_common(args.detail):
            print(f"  {source:38} {count:>5}")
        if len(by_source) > args.detail:
            print(f"  {'(autres)':38} {sum(by_source.values()) - sum(c for _, c in by_source.most_common(args.detail)):>5}")
        print("\nreprise : make translate   (le cache évite de retraduire ce qui est acquis)")
    else:
        print("\nle corpus est intégralement traduit — python manage.py translate_corpus --apply")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
