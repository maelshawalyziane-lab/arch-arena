"""
`manage.py seed_showcase` - load the curated, machine-verified problem corpus.

Unlike `ingest_arch_fixture` (which imports whatever an ARCH fixture contains),
this command installs problems whose official solutions have been verified by
`scripts/verify_seed.py`, so the AI gate has a trustworthy answer key:

    python manage.py seed_showcase                 # upsert problems + demo history
    python manage.py seed_showcase --reset         # wipe demo progress and redo it
    python manage.py seed_showcase --no-history    # problems only, nothing unlocked
    python manage.py seed_showcase --only "IMO 1988/6,IMO 2014/5"

It is idempotent: re-running updates statements/hints/solutions in place.
"""

from __future__ import annotations

from django.conf import settings
from django.core.management.base import BaseCommand
from django.db import transaction

from problems.middleware import get_guest_user, primary_account
from problems.models import (
    Hint,
    HintReveal,
    Problem,
    Solution,
    SubmissionStatus,
    UserProgress,
    UserSubmission,
)
from problems.seed_data.showcase import DEMO_PASSED_ATTEMPTS, PROBLEMS, UNLOCKED_IN_DEMO


class Command(BaseCommand):
    help = "Seed the curated showcase problems (with verified official solutions)."

    def add_arguments(self, parser):
        parser.add_argument("--reset", action="store_true",
                            help="Delete progress/submissions/hint reveals of the demo guest first.")
        parser.add_argument("--no-history", action="store_true",
                            help="Skip the demo submission history and unlock records.")
        parser.add_argument("--only", default="", help="Comma-separated PUID allow-list.")

    def handle(self, *args, **options):
        only = {p.strip() for p in options["only"].split(",") if p.strip()} or None
        selected = [p for p in PROBLEMS if not only or p["puid"] in only]
        if not selected:
            self.stderr.write(self.style.ERROR("no matching PUIDs in the showcase corpus"))
            return

        created = updated = 0
        hint_count = solution_count = 0
        with transaction.atomic():
            for data in selected:
                problem, is_new = Problem.objects.update_or_create(
                    puid=data["puid"],
                    defaults={
                        "legacy_puid": data.get("legacy_puid", ""),
                        "statement_tex": data["statement_tex"],
                        "category": data["category"],
                        "difficulty_track": data["difficulty_track"],
                        "source_url": data.get("source_url", ""),
                        "answer_tex": data.get("answer_tex", ""),
                    },
                )
                created += is_new
                updated += (not is_new)

                for index, hint_text in enumerate(data["hints"], start=1):
                    Hint.objects.update_or_create(
                        problem=problem,
                        order_index=index,
                        defaults={"content_md": hint_text.strip(), "keywords": data.get("keywords", "")},
                    )
                    hint_count += 1

                Solution.objects.update_or_create(
                    problem=problem,
                    defaults={
                        "official_tex": data["official_tex"].strip(),
                        "attribution": data.get("attribution", ""),
                    },
                )
                solution_count += 1

            history_created = 0
            if not options["no_history"]:
                history_created = self._seed_demo_history(selected, reset=options["reset"])

        self.stdout.write(
            self.style.SUCCESS(
                f"showcase corpus ready: {created} created, {updated} updated, "
                f"{hint_count} hints, {solution_count} official solutions, "
                f"{history_created} demo history rows"
            )
        )
        if solution_count < len(selected):
            self.stderr.write(self.style.WARNING("some problems are missing an official solution!"))

    # ------------------------------------------------------------------ #
    def _seed_demo_history(self, selected: list[dict], *, reset: bool) -> int:
        """Attache l'historique de démonstration au compte unique de l'installation.

        En mono-compte (``DEMO_MODE=0``) c'est le superutilisateur `admin` ; en mode
        démonstration historique, c'est le compte invité partagé.
        """
        guest = get_guest_user() if settings.DEMO_MODE else (primary_account() or get_guest_user())
        made = 0
        for data in selected:
            problem = Problem.objects.filter(puid=data["puid"]).first()
            if problem is None:
                continue
            if reset:
                UserSubmission.objects.filter(user=guest, problem=problem).delete()
                HintReveal.objects.filter(user=guest, hint__problem=problem).delete()
                UserProgress.objects.filter(user=guest, problem=problem).delete()

            existing = UserSubmission.objects.filter(user=guest, problem=problem, is_demo=True).exists()
            if existing:
                continue

            attempts = list(data.get("demo_submissions", []))
            attempts.extend(DEMO_PASSED_ATTEMPTS.get(data["puid"], []))

            for attempt in attempts:
                status = attempt.get("status", SubmissionStatus.REJECTED)
                if status == SubmissionStatus.PASSED and data["puid"] not in UNLOCKED_IN_DEMO:
                    continue  # keep most problems locked so the gate stays visible in the demo
                UserSubmission.objects.create(
                    user=guest,
                    problem=problem,
                    submitted_text=attempt["text"],
                    status=status,
                    ai_feedback=attempt.get("feedback", ""),
                    engine="seed (demo history)",
                    is_demo=True,
                )
                made += 1
                if status == SubmissionStatus.PASSED:
                    progress, _ = UserProgress.objects.get_or_create(user=guest, problem=problem)
                    progress.mark_solved()
        return made
