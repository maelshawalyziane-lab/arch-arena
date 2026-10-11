"""
`manage.py fetch_arch_fixture` - download `fixtures/all.json` from otis-web.

Keeps a local copy so ingestion is reproducible and offline-friendly:

    python manage.py fetch_arch_fixture --output fixtures/all.json
    python manage.py ingest_arch_fixture fixtures/all.json --default-category auto
"""

from __future__ import annotations

import json
import urllib.request
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError

DEFAULT_URL = "https://raw.githubusercontent.com/vEnhance/otis-web/main/fixtures/all.json"


class Command(BaseCommand):
    help = "Download the upstream otis-web ARCH fixture (fixtures/all.json)."

    def add_arguments(self, parser):
        parser.add_argument("--url", default=DEFAULT_URL)
        parser.add_argument("--output", default="fixtures/all.json")
        parser.add_argument("--force", action="store_true", help="Overwrite an existing file.")
        parser.add_argument("--timeout", type=int, default=30)

    def handle(self, *args, **options):
        output = Path(options["output"])
        if output.exists() and not options["force"]:
            raise CommandError(f"{output} exists - pass --force to overwrite")
        try:
            with urllib.request.urlopen(options["url"], timeout=options["timeout"]) as response:  # noqa: S310
                payload = response.read()
        except Exception as exc:  # noqa: BLE001
            raise CommandError(f"download failed: {exc}") from exc

        data = json.loads(payload.decode("utf-8"))
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_bytes(payload)

        counts: dict[str, int] = {}
        for row in data if isinstance(data, list) else data.get("objects", []):
            key = str(row.get("model", "?"))
            counts[key] = counts.get(key, 0) + 1
        arch = {k: v for k, v in counts.items() if k.startswith("arch.")}
        self.stdout.write(
            self.style.SUCCESS(
                f"saved {len(payload)} bytes to {output}\n"
                f"  total rows      : {sum(counts.values())}\n"
                f"  arch.* rows     : {arch or 'none'}\n"
                f"  distinct models : {len(counts)}"
            )
        )
        if arch.get("arch.problem", 0) <= 5:
            self.stdout.write(
                self.style.WARNING(
                    "  ! this looks like the upstream dummy fixture (only a handful of problems). "
                    "For a real corpus point --url at your own export of the ARCH data."
                )
            )
