"""Audit du rendu LaTeX de tout le corpus.

Vérifie que rien de « sale » n'arrive jusqu'à l'écran : ni macro de concours non
développée, ni commande de mise en page, ni caractère de contrôle, ni balise BBCode,
ni LaTeX resté dans la prose (hors des formules).

    python3 manage.py check_rendering                  # tout le corpus
    python3 manage.py check_rendering --sample 400     # échantillon rapide
    python3 manage.py check_rendering --corpus omni    # seulement les fiches importées

Sortie : code 1 si une seule anomalie est trouvée (utilisable en intégration continue).
"""

from __future__ import annotations

import random
import re
from typing import Iterable, Iterator

from django.core.management.base import BaseCommand

from problems.models import Hint, Problem, Solution
from problems.services.tex import render_rich

#: Scories qui ne doivent jamais apparaître dans une page.
#: (libellé, motif, dans la prose seule ?)
#: Une « balise BBCode » ne compte que **hors** des formules : `\sqrt[b]{x}`, `[b]=98.6`
#: ou `\mathbb{Z}[i]` sont des notations, pas du forum.
FORBIDDEN: tuple[tuple[str, re.Pattern, bool], ...] = (
    ("caractère de contrôle", re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f]"), False),
    (
        "macro de concours non développée",
        re.compile(r"\\(?:plus|minus|equal|ZZ|RR|QQ|NN|CC|ee|sgn|hdots)(?![A-Za-z])"),
        False,
    ),
    (
        "commande de mise en page",
        re.compile(
            r"\\(?:vspace|hspace|vskip|hskip|mbox|makebox|indent|noindent|hfill"
            r"|smallskip|medskip|bigskip|ref|label|section|subsection|newline|par)"
            r"(?![A-Za-z])"
        ),
        # dans une formule, `\newline` et `\mbox` font partie du texte source et KaTeX
        # les compose ; dans la prose, ce serait du LaTeX resté à l'écran.
        True,
    ),
    (
        "environnement transformé non appliqué",
        re.compile(r"\\begin\s*\{(?:tabular|eqnarray)"),
        False,
    ),
    (
        "balise BBCode",
        re.compile(r"\[(?:/?)(?:b|i|u|s|tex|math|list|quote|url|img|color)(?:=[^\]]*)?\]"),
        True,
    ),
    ("marqueur de liste BBCode", re.compile(r"\[\*\]"), True),
)

#: LaTeX resté **hors** d'une formule : le signal que le découpage s'est trompé.
MATH_SPAN_RE = re.compile(
    r'<span class="math-inline">\$.*?\$</span>|<div class="math-block">\$\$.*?\$\$</div>',
    re.DOTALL,
)
TEX_IN_PROSE_RE = re.compile(
    r"\\(?:frac|dfrac|tfrac|sqrt|sum|prod|int|lim|alpha|beta|gamma|mathbb|mathcal"
    r"|left|right|cdot|times|leq|geq|neq|to|mapsto|text|operatorname|begin|end)"
    r"(?![A-Za-z])"
)


class Command(BaseCommand):
    help = "Vérifie que le rendu LaTeX du corpus ne contient aucune scorie."

    def add_arguments(self, parser) -> None:
        parser.add_argument("--sample", type=int, default=0, help="nombre de fiches à tirer au hasard")
        parser.add_argument("--seed", type=int, default=7, help="graine du tirage aléatoire")
        parser.add_argument(
            "--corpus", choices=("all", "omni", "curated"), default="all", help="sous-ensemble à contrôler"
        )
        parser.add_argument("--show", type=int, default=20, help="nombre d'anomalies détaillées")
        parser.add_argument(
            "--strict",
            action="store_true",
            help="échouer aussi sur le LaTeX resté dans la prose (résidu des fragments abîmés)",
        )

    # ------------------------------------------------------------------ outils

    def _problems(self, corpus: str, sample: int, seed: int) -> list[Problem]:
        queryset = Problem.objects.all()
        if corpus == "omni":
            queryset = queryset.filter(puid__startswith="OMNI")
        elif corpus == "curated":
            queryset = queryset.exclude(puid__startswith="OMNI")
        rows = list(queryset.order_by("pk"))
        if sample and sample < len(rows):
            rows = random.Random(seed).sample(rows, sample)
        return rows

    def _texts(self, problem: Problem) -> Iterator[tuple[str, str]]:
        statement = problem.statement_tex or ""
        if statement:
            yield "énoncé", statement
        for solution in Solution.objects.filter(problem=problem).only("official_tex"):
            if solution.official_tex:
                yield "solution", solution.official_tex
        for hint in Hint.objects.filter(problem=problem).only("content_md"):
            if hint.content_md:
                yield "indice", hint.content_md

    def _anomalies(self, html: str) -> tuple[list[str], bool]:
        """Scories interdites, et — à part — LaTeX resté dans la prose.

        Les scories sont des défauts : elles font échouer la commande. Le LaTeX resté
        dans la prose est un **résidu** : le fragment est trop abîmé pour être composé
        sans risque (délimiteur perdu, accolade en trop). Il est compté, puis signalé
        seulement en mode strict.
        """
        prose = MATH_SPAN_RE.sub(" ", html)
        found = [
            label
            for label, pattern, prose_only in FORBIDDEN
            if pattern.search(prose if prose_only else html)
        ]
        return found, bool(TEX_IN_PROSE_RE.search(prose))

    # ------------------------------------------------------------------ action

    def handle(self, *args, **options) -> None:
        corpus = options["corpus"]
        problems = self._problems(corpus, options["sample"], options["seed"])
        shown = 0
        anomalies = 0
        residues = 0
        texts = 0
        formulas = 0

        for problem in problems:
            for field, raw in self._texts(problem):
                texts += 1
                html = render_rich(raw)
                formulas += len(MATH_SPAN_RE.findall(html))
                issues, residue = self._anomalies(html)
                if residue:
                    residues += 1
                    if options["strict"] and not issues:
                        issues = ["LaTeX resté dans la prose"]
                if not issues:
                    continue
                anomalies += 1
                if shown < options["show"]:
                    shown += 1
                    self.stdout.write(
                        self.style.ERROR(f"  ✗ {problem.puid} [{field}] → {', '.join(issues)}")
                    )

        self.stdout.write("")
        self.stdout.write(f"  fiches contrôlées   : {len(problems)}")
        self.stdout.write(f"  textes analysés     : {texts}")
        self.stdout.write(f"  formules composées  : {formulas}")
        self.stdout.write(f"  résidu (fragments abîmés) : {residues}")
        if anomalies:
            self.stdout.write(self.style.ERROR(f"  ANOMALIES           : {anomalies}"))
            raise SystemExit(1)
        self.stdout.write(self.style.SUCCESS("  ANOMALIES           : 0"))
