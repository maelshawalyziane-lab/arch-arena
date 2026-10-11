"""Exporte le corpus composé, pour le contrôle KaTeX hors ligne.

Le rendu est fait par :func:`problems.services.tex.render_rich`, exactement comme dans
la page ; le fichier produit est ensuite composé par le vrai KaTeX (Node), ce qui
rattrape ce qu'un simple coup d'œil laisserait passer.

    python manage.py dump_math_corpus --out /tmp/katexcheck/rendered.json
    node /tmp/katexcheck/verify_rendered.js
"""

from __future__ import annotations

import json

from django.core.management.base import BaseCommand

from problems.models import Problem
from problems.services.tex import render_rich


class Command(BaseCommand):
    help = "Écrit le HTML composé de chaque énoncé, indice et solution (JSON)."

    def add_arguments(self, parser) -> None:
        parser.add_argument("--out", default="/tmp/katexcheck/rendered.json")
        parser.add_argument("--corpus", default="", help="limiter à un corpus (omni, curated)")
        parser.add_argument("--puid", default="", help="limiter à un PUID (préfixe accepté)")

    def handle(self, *args, **options) -> None:
        problems = Problem.objects.prefetch_related("hints", "solution").order_by("id")
        if options["corpus"]:
            problems = problems.filter(corpus=options["corpus"])
        if options["puid"]:
            problems = problems.filter(puid__icontains=options["puid"])

        items: list[dict[str, str]] = []
        for problem in problems:
            items.append({"puid": problem.puid, "field": "statement",
                          "html": render_rich(problem.statement_tex)})
            for hint in problem.hints.all():
                items.append({"puid": problem.puid, "field": f"hint {hint.order_index}",
                              "html": render_rich(hint.content_md)})
            solution = getattr(problem, "solution", None)
            if solution:
                items.append({"puid": problem.puid, "field": "solution",
                              "html": render_rich(solution.official_tex)})

        with open(options["out"], "w", encoding="utf-8") as handle:
            json.dump(items, handle, ensure_ascii=False)
        self.stdout.write(f"  textes écrits : {len(items)} → {options['out']}")
