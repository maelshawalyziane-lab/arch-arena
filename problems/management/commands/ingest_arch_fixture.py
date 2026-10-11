"""
`manage.py ingest_arch_fixture` - seed the platform from `fixtures/all.json`.

Usage
-----
    python manage.py ingest_arch_fixture fixtures/all.json --dry-run
    python manage.py ingest_arch_fixture fixtures/all.json --default-category auto \
        --default-track auto --puid-map data/puid_map.json --report var/ingest.json

Every run prints a machine-readable summary (and optionally writes it to disk), so
the import is auditable: you always know how many problems, hints and *official
solutions* were found.  That last number matters -- a fixture without solutions
cannot power the AI gate for those problems.
"""

from __future__ import annotations

import json
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError

from problems.ingestion import (
    ingest_into_database,
    load_fixture,
    load_puid_map,
    parse_fixture,
)


class Command(BaseCommand):
    help = "Parse an otis-web ARCH JSON fixture and seed Problem/Hint/Solution rows."

    def add_arguments(self, parser):
        parser.add_argument("fixture", help="Path to fixtures/all.json")
        parser.add_argument("--dry-run", action="store_true", help="Parse and report, write nothing.")
        parser.add_argument(
            "--puid-map",
            default="",
            help='JSON file mapping ARCH codes to readable PUIDs, e.g. {"XKPFMI": "IMO 2016/4"}.',
        )
        parser.add_argument(
            "--default-category",
            default="auto",
            help="'auto' infers Algebra/Combinatorics/Geometry/Number Theory, otherwise a fixed value "
                 "(algebra|combinatorics|geometry|number_theory|misc).",
        )
        parser.add_argument(
            "--default-track",
            default="auto",
            help="'auto' infers the difficulty track from the PUID, otherwise a fixed value "
                 "(foundation|olympiad|hard).",
        )
        parser.add_argument("--only-puids", default="", help="Comma-separated allow-list of PUIDs.")
        parser.add_argument("--limit", type=int, default=0, help="Import at most N problems.")
        parser.add_argument(
            "--skip-missing-statement",
            action="store_true",
            help="Skip rows whose statement is not in the fixture (statements usually live in arch/data/).",
        )
        parser.add_argument(
            "--no-update",
            action="store_true",
            help="Never modify existing rows (insert-only mode).",
        )
        parser.add_argument("--report", default="", help="Write the JSON report to this path.")

    def handle(self, *args, **options):
        fixture_path = Path(options["fixture"])
        if not fixture_path.exists():
            raise CommandError(f"fixture not found: {fixture_path}")

        rows = load_fixture(fixture_path)
        only = {p.strip() for p in options["only_puids"].split(",") if p.strip()} or None
        result = parse_fixture(
            rows,
            puid_map=load_puid_map(options["puid_map"] or None),
            default_category=options["default_category"],
            default_track=options["default_track"],
            skip_missing_statement=options["skip_missing_statement"],
            only_puids=only,
            limit=options["limit"] or None,
        )

        summary = ingest_into_database(
            result,
            dry_run=options["dry_run"],
            update_existing=not options["no_update"],
        )
        report = result.report() | {"db": summary, "fixture": str(fixture_path), "dry_run": options["dry_run"]}

        self.stdout.write(self.style.MIGRATE_HEADING(f"ARCH fixture ingestion - {fixture_path}"))
        self.stdout.write(
            f"  rows scanned        : {result.stats['rows_scanned']}\n"
            f"  problem rows        : {result.stats['problem_rows']}\n"
            f"  hint rows           : {result.stats['hint_rows']}\n"
            f"  solution rows       : {result.stats['solution_rows']}\n"
            f"  problems parsed     : {result.n_problems}\n"
            f"  hints parsed        : {result.n_hints}\n"
            f"  OFFICIAL SOLUTIONS  : {result.n_solutions}\n"
            f"  PUID quality        : {report['puid_quality']}\n"
            f"  categories          : {report['categories']}\n"
            f"  tracks              : {report['tracks']}\n"
            f"  database            : {summary}"
        )
        if not result.n_solutions:
            self.stdout.write(
                self.style.WARNING(
                    "  ! no official solutions in this fixture - the AI gate will report "
                    "'missing ground truth' for those problems.  Note that the public "
                    "fixtures/all.json ships dummy data; run `manage.py seed_showcase` for "
                    "curated problems with verified official solutions."
                )
            )
        for warning in result.warnings[:10]:
            self.stdout.write(self.style.WARNING(f"  ! {warning}"))
        if len(result.warnings) > 10:
            self.stdout.write(self.style.WARNING(f"  ! ... {len(result.warnings) - 10} more warnings"))

        if options["report"]:
            report_path = Path(options["report"])
            report_path.parent.mkdir(parents=True, exist_ok=True)
            report_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
            self.stdout.write(self.style.SUCCESS(f"report written to {report_path}"))

        if options["dry_run"]:
            self.stdout.write(self.style.WARNING("dry run: nothing written to the database"))
