"""Prépare une installation neuve, en une seule commande.

Sur un poste de travail la base est déjà remplie ; sur un hébergeur, le conteneur démarre
avec une base vierge. Cette commande fait alors **tout** ce qu'il faut pour que la
plateforme soit utilisable dès la première requête :

1. le **compte unique** (superutilisateur `admin`, mot de passe pris dans
   ``ARCH_ADMIN_PASSWORD``) — sans lui, personne ne peut se connecter ;
2. le **catalogue complet** : les dix fiches curatées puis les 4 324 problèmes du corpus
   Omni-MATH, avec leurs indices et leurs solutions officielles ;
3. la **version française** des énoncés, appliquée depuis le cache de traduction
   (``var/translations.jsonl``) — aucune requête réseau n'est nécessaire.

Tout est idempotent : sur une base déjà remplie, la commande le constate et ne touche à
rien. C'est ce que la production exécute à chaque démarrage.

    python manage.py bootstrap                     # installation neuve
    python manage.py bootstrap --force             # réimporte le catalogue
    python manage.py bootstrap --skip-corpus       # compte uniquement

Un dépôt fraîchement cloné n'a pas de base : la commande applique donc les migrations
elle-même avant tout le reste, ce qui la rend utilisable telle quelle, sans rien connaître
de Django.
"""

from __future__ import annotations

import os
from pathlib import Path

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.core.management.base import BaseCommand
from django.db import transaction

from problems.models import Hint, Problem, Solution, UserProgress, UserSubmission

DEFAULT_CACHE = "var/translations.jsonl"


class Command(BaseCommand):
    help = "Installation neuve : compte unique, catalogue complet, énoncés en français."

    def add_arguments(self, parser) -> None:
        parser.add_argument("--username", default="admin")
        parser.add_argument(
            "--password",
            default=os.environ.get("ARCH_ADMIN_PASSWORD", ""),
            help="mot de passe du compte unique (défaut : $ARCH_ADMIN_PASSWORD)",
        )
        parser.add_argument(
            "--force", action="store_true", help="réimporter le catalogue même s'il est déjà là"
        )
        parser.add_argument("--skip-corpus", action="store_true", help="ne créer que le compte")
        parser.add_argument("--cache", default=DEFAULT_CACHE, help="cache de traduction à appliquer")
        parser.add_argument(
            "--no-translation", action="store_true", help="ne pas appliquer le français"
        )
        parser.add_argument(
            "--skip-migrate", action="store_true", help="ne pas appliquer les migrations"
        )

    # ------------------------------------------------------------------ étapes

    def _ensure_account(self, username: str, password: str) -> None:
        User = get_user_model()
        user = User.objects.filter(username=username).first()
        if user is None:
            if not password:
                self.stderr.write(
                    self.style.WARNING(
                        "  ! aucun mot de passe fourni (ARCH_ADMIN_PASSWORD) : le compte est créé "
                        "avec un mot de passe inutilisable, à définir avec `manage.py changepassword`."
                    )
                )
            with transaction.atomic():
                user = User.objects.create_superuser(username=username, password=password or None)
            self.stdout.write(f"  compte créé          : {username}")
            return
        self.stdout.write(f"  compte déjà présent  : {username} (mot de passe inchangé)")

    def _corpus_is_ready(self) -> bool:
        return Problem.objects.exists() and Solution.objects.exists()

    # ------------------------------------------------------------------ action

    def handle(self, *args, **options) -> None:
        self.stdout.write("Amorçage de la plateforme")

        if not options["skip_migrate"]:
            self.stdout.write("  → schéma de la base (migrations)")
            call_command("migrate", interactive=False, verbosity=0)

        self._ensure_account(options["username"], options["password"])

        if options["skip_corpus"]:
            return

        if self._corpus_is_ready() and not options["force"]:
            self.stdout.write("  catalogue déjà en base : import sauté")
        else:
            self.stdout.write("  → fiches curatées")
            call_command("seed_showcase", verbosity=0)
            self.stdout.write("  → corpus Omni-MATH (4 324 problèmes : énoncés, indices, solutions)")
            call_command("ingest_omni_math", verbosity=0)

        cache = Path(options["cache"])
        french = Problem.objects.exclude(statement_tex="").filter(
            statement_tex__regex=r"[À-ÿ]"
        ).count()
        if options["no_translation"] or not cache.exists():
            if not cache.exists():
                self.stdout.write(f"  cache de traduction absent : {cache} (corpus en anglais)")
        else:
            self.stdout.write("  → version française des énoncés (depuis le cache, hors ligne)")
            call_command("translate_corpus", apply=True, cache=str(cache), verbosity=0)

        self.stdout.write("")
        self.stdout.write(f"  problèmes   : {Problem.objects.count()}")
        self.stdout.write(f"  indices     : {Hint.objects.count()}")
        self.stdout.write(f"  solutions   : {Solution.objects.count()}")
        self.stdout.write(f"  progression : {UserProgress.objects.count()}")
        self.stdout.write(f"  soumissions : {UserSubmission.objects.count()}")
        self.stdout.write(
            self.style.SUCCESS(
                "Installation prête. Connectez-vous avec le compte unique pour commencer."
            )
        )
