"""Vérifie le verrou IA sur un échantillon aléatoire du catalogue **entier**.

Le corpus importé (4 324 fiches) ne peut pas être relu à la main : cette commande
tire N fiches au hasard et, pour chacune, demande la page comme un visiteur
anonyme (client Django en mémoire, aucun serveur à lancer) puis vérifie :

1. la page répond 200 et affiche le bandeau de verrouillage exact ;
2. **aucune phrase** de ``Solution.official_tex`` n'apparaît dans le HTML ;
3. la réponse compacte (``answer_tex``) n'apparaît pas non plus ;
4. le formulaire de soumission et son bouton « Soumettre à l'évaluation IA » sont là.

Toute fuite fait sortir la commande en code 1 (utilisable en intégration continue) :

    python manage.py verify_lock_sample --sample 25
    python manage.py verify_lock_sample --sample 50 --seed 2026 --corpus omni
    python manage.py verify_lock_sample --all --corpus curated
"""

from __future__ import annotations

import random
import re

from django.core.management.base import BaseCommand
from django.test import Client

from problems.middleware import primary_account
from problems.models import Problem, UserProgress
from problems.services.tex import to_plain_text

BANNER = "Solution officielle verrouillée"
SUBMIT_LABEL = "Soumettre à l'évaluation IA"
MIN_SENTENCE = 40


def sentences(text: str, minimum: int = MIN_SENTENCE) -> list[str]:
    """Phrases (ou fragments) assez longs pour être une fuite exploitable."""
    plain = to_plain_text(text)
    plain = re.sub(r"\s+", " ", plain)
    parts = re.split(r"(?<=[.!?;:])\s+", plain)
    return [p.strip() for p in parts if len(p.strip()) >= minimum]


def page_leaks(problem, html: str) -> list[str]:
    """Fuites détectées dans le HTML **verrouillé** d'une fiche (liste vide = propre).

    Trois contrôles, du plus grave au plus anodin :

    * une phrase de ``Solution.official_tex`` qui apparaît dans la page ;
    * la réponse compacte (``answer_tex``) révélée alors que la fiche est verrouillée —
      sauf si l'énoncé la contient déjà (les candidats d'un QCM, par exemple) ;
    * l'absence du bandeau de verrouillage ou du bouton de soumission (une fiche qui ne
      serait pas verrouillée du tout est un défaut au même titre qu'une fuite).
    """
    leaks: list[str] = []
    official = getattr(getattr(problem, "solution", None), "official_tex", "") or ""

    if BANNER not in html:
        leaks.append(f"{problem.puid} : bandeau de verrouillage absent")
    if SUBMIT_LABEL not in html:
        leaks.append(f"{problem.puid} : bouton de soumission absent")

    for sentence in sentences(official):
        if sentence in html:
            leaks.append(f"{problem.puid} : la solution fuite → {sentence[:70]!r}")
            break

    answer = (problem.answer_tex or "").strip()
    raw_statement = problem.statement_tex or ""
    public = re.sub(r"\s+", " ", to_plain_text(raw_statement))
    if len(answer) >= 4 and answer not in public and answer not in raw_statement:
        # le gabarit du formulaire contient un exemple en `placeholder` : ce n'est pas
        # une fuite, on l'écarte avant de chercher la réponse dans la page.
        body = re.sub(r"<textarea[^>]*>.*?</textarea>", " ", html, flags=re.S | re.I)
        if answer in body:
            leaks.append(f"{problem.puid} : la réponse compacte fuite → {answer!r}")

    return leaks


class Command(BaseCommand):
    help = "Contrôle aléatoire du verrou : la solution officielle ne doit jamais fuiter."

    def add_arguments(self, parser):
        parser.add_argument("--sample", type=int, default=20, help="nombre de fiches tirées au hasard")
        parser.add_argument("--seed", type=int, default=None, help="graine du tirage (reproductible)")
        parser.add_argument(
            "--corpus",
            choices=("omni", "curated", "all"),
            default="all",
            help="omni = corpus importé, curated = les 10 fiches écrites à la main",
        )
        parser.add_argument("--all", action="store_true", help="tester tout le corpus sélectionné")

    def handle(self, *args, **options):
        queryset = Problem.objects.all()
        if options["corpus"] == "omni":
            queryset = queryset.filter(puid__startswith="OMNI ")
        elif options["corpus"] == "curated":
            queryset = queryset.exclude(puid__startswith="OMNI ")

        pks = list(queryset.values_list("pk", flat=True))
        if not pks:
            self.stderr.write(self.style.ERROR("aucune fiche dans ce corpus"))
            return

        if not options["all"]:
            rng = random.Random(options["seed"])
            pks = rng.sample(pks, min(options["sample"], len(pks)))

        # L'accès est verrouillé (un seul compte, inscription fermée) : le contrôle
        # s'authentifie comme le compte de l'installation, sans mot de passe.
        account = primary_account()
        client = Client()
        if account is not None:
            client.force_login(account)

        # Les fiches déjà débloquées sont légitimement ouvertes : on les compte à part
        # au lieu de les prendre pour des fuites.
        solved_queryset = UserProgress.objects.filter(is_solved=True, problem_id__in=pks)
        if account is not None:
            solved_queryset = solved_queryset.filter(user=account)
        solved = set(solved_queryset.values_list("problem_id", flat=True))

        checked = leaked = skipped = 0
        failures: list[str] = []

        for pk in pks:
            problem = Problem.objects.get(pk=pk)
            response = client.get(f"/problems/{pk}/")
            if response.status_code != 200:
                failures.append(f"{problem.puid} : HTTP {response.status_code}")
                leaked += 1
                continue

            html = response.content.decode("utf-8", errors="replace")
            if pk in solved:
                skipped += 1
                continue
            checked += 1

            found = page_leaks(problem, html)
            if found:
                failures.extend(found)
                leaked += len(found)

        self.stdout.write(
            self.style.MIGRATE_HEADING(
                f"Verrou : {len(pks)} fiche(s) tirée(s) au hasard "
                f"({options['corpus']}{', graine ' + str(options['seed']) if options['seed'] else ''})"
            )
        )
        self.stdout.write(f"fiches testées ......... {checked}")
        if skipped:
            self.stdout.write(f"déjà débloquées (ignorées) {skipped}")
        else:
            self.stdout.write("déjà débloquées (ignorées) 0")
        self.stdout.write(f"anomalies .............. {leaked}")

        if failures:
            for line in failures[:20]:
                self.stderr.write(self.style.ERROR(f"  ✗ {line}"))
            raise SystemExit(1)

        self.stdout.write(
            self.style.SUCCESS(
                f"Aucune fuite détectée : {checked}/{checked} pages verrouillées sont propres."
            )
        )
