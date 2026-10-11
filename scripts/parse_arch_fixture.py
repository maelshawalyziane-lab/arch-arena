#!/usr/bin/env python3
"""
Standalone inspector for an ARCH fixture - no Django, no database.

Examples
--------
    # what is inside the fixture?
    python scripts/parse_arch_fixture.py fixtures/all.json --summary

    # show the first few parsed problems as plain text
    python scripts/parse_arch_fixture.py fixtures/all.json --preview 3

    # dump the fully normalised corpus (ready for any importer) to JSON
    python scripts/parse_arch_fixture.py fixtures/all.json --dump data/arch_parsed.json \
        --default-category auto --default-track auto

Then load it for real with:

    python manage.py ingest_arch_fixture fixtures/all.json --default-category auto
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from problems.ingestion import load_fixture, load_puid_map, parse_fixture  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description="Parse an otis-web ARCH fixture.")
    parser.add_argument("fixture", help="path to fixtures/all.json")
    parser.add_argument("--puid-map", default="", help="JSON map of ARCH code -> readable PUID")
    parser.add_argument("--default-category", default="auto")
    parser.add_argument("--default-track", default="auto")
    parser.add_argument("--limit", type=int, default=0)
    parser.add_argument("--preview", type=int, default=0, help="print N parsed problems")
    parser.add_argument("--dump", default="", help="write normalised JSON here")
    parser.add_argument("--summary", action="store_true", help="print the summary report only")
    args = parser.parse_args()

    result = parse_fixture(
        load_fixture(args.fixture),
        puid_map=load_puid_map(args.puid_map or None),
        default_category=args.default_category,
        default_track=args.default_track,
        limit=args.limit or None,
    )
    report = result.report()
    print(json.dumps(report, indent=2))

    if args.preview:
        for problem in result.problems[: args.preview]:
            print("\n" + "=" * 78)
            print(f"{problem.puid}  [{problem.category} / {problem.difficulty_track}]")
            print("-" * 78)
            print(problem.statement_tex.strip()[:600] or "(no statement in fixture)")
            for hint in problem.hints:
                print(f"  hint {hint.order_index}: {hint.content_md.strip()[:120]}")
            print(f"  official solution: {'yes' if problem.official_tex else 'NO (AI gate needs it)'}")

    if args.dump:
        out = Path(args.dump)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(
            json.dumps(
                {
                    "report": report,
                    "problems": [
                        {**asdict(p), "puid_quality": p.puid_quality} for p in result.problems
                    ],
                },
                indent=2,
            ),
            encoding="utf-8",
        )
        print(f"\nwrote {out}")

    return 0 if result.n_solutions or args.summary else 0


if __name__ == "__main__":
    raise SystemExit(main())
