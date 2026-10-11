"""
Tests for the ARCH ingestion pipeline and the safe TeX/Markdown renderer.

The ingestion tests run against a synthetic fixture that mirrors the real
``fixtures/all.json`` dialect (``{"model", "pk", "fields"}`` rows), plus a
solution row shape, because the upstream public fixture deliberately ships
dummy data with no solutions.
"""

from __future__ import annotations

import json
import tempfile
from pathlib import Path

from django.core.management import call_command
from django.test import TestCase

from problems.ingestion import (
    ingest_into_database,
    infer_category,
    infer_track,
    load_fixture,
    parse_fixture,
    resolve_puid,
)
from problems.models import Hint, Problem, Solution
from problems.services.tex import render_rich, to_plain_text

FIXTURE_ROWS = [
    {"model": "arch.problem", "pk": 11, "fields": {"puid": "AB12CD", "hyperlink": ""}},
    {"model": "arch.problem", "pk": 12, "fields": {"puid": "IMO 2016/4", "hyperlink": ""}},
    {"model": "arch.hint", "pk": 101, "fields": {"problem": 11, "keywords": "Number Theory",
                                                 "number": 25, "content": "Look at $p \\pmod 4$."}},
    {"model": "arch.hint", "pk": 102, "fields": {"problem": 11, "keywords": "Number Theory",
                                                 "number": 35, "content": "Use Fermat's little theorem."}},
    {"model": "arch.hint", "pk": 103, "fields": {"problem": 12, "keywords": "Algebra",
                                                 "number": 40, "content": "Try Cauchy-Schwarz."}},
    {"model": "arch.solution", "pk": 201, "fields": {"problem": 11, "official_tex": "Every prime $p \\equiv 1$ works."}},
    {"model": "core.unit", "pk": 1, "fields": {"code": "XYZ", "group": 1, "position": 3}},
]


class ParserTests(TestCase):
    def test_parses_problems_hints_and_solutions_and_ignores_other_models(self):
        result = parse_fixture(FIXTURE_ROWS)
        self.assertEqual(result.stats["rows_scanned"], 7)
        self.assertEqual(result.stats["problem_rows"], 2)
        self.assertEqual(result.stats["hint_rows"], 3)
        self.assertEqual(result.stats["solution_rows"], 1)
        self.assertEqual(result.stats["unknown_models_ignored"], 1)

        by_puid = {p.puid: p for p in result.problems}
        self.assertEqual(by_puid["AB12CD"].legacy_puid, "AB12CD")
        self.assertEqual(len(by_puid["AB12CD"].hints), 2)
        self.assertEqual(by_puid["AB12CD"].official_tex, "Every prime $p \\equiv 1$ works.")
        self.assertEqual(by_puid["IMO 2016/4"].puid_quality, "human")

    def test_hints_are_renumbered_one_based_in_order(self):
        result = parse_fixture(FIXTURE_ROWS)
        problem = next(p for p in result.problems if p.puid == "AB12CD")
        self.assertEqual([h.order_index for h in problem.hints], [1, 2])
        self.assertIn("pmod", problem.hints[0].content_md)

    def test_puid_map_attaches_readable_identifiers(self):
        result = parse_fixture(FIXTURE_ROWS, puid_map={"AB12CD": "IMO 2016/4-twin"})
        self.assertIn("IMO 2016/4-twin", [p.puid for p in result.problems])

    def test_puid_resolution_rules(self):
        self.assertEqual(resolve_puid("IMO 2016/4", "", {})[0], "IMO 2016/4")
        self.assertEqual(resolve_puid("XKPFMI", "", {})[0:2], ("XKPFMI", "XKPFMI"))
        self.assertEqual(resolve_puid("XKPFMI", "", {"XKPFMI": "USAMO 2018/3"})[0], "USAMO 2018/3")
        # AoPS links still give something readable
        self.assertTrue(
            resolve_puid("", "https://artofproblemsolving.com/community/c6h1234567", {})[0].startswith("AoPS")
        )

    def test_category_and_track_inference(self):
        self.assertEqual(infer_category("IMO 2016/4", "", "combinatorics, pigeonhole"), "combinatorics")
        self.assertEqual(infer_category("IMO 2016/4", "", "Number Theory: primes"), "number_theory")
        self.assertEqual(infer_category("XYZ", "some statement about triangles", ""), "geometry")
        self.assertEqual(infer_category("XYZ", "unclassifiable text", ""), "misc")
        self.assertEqual(infer_track("IMO 2016/6", ""), "hard")
        self.assertEqual(infer_track("IMO 2016/1", ""), "olympiad")
        self.assertEqual(infer_track("USA TST 2019/3", ""), "hard")

    def test_missing_statement_can_be_skipped_or_flagged(self):
        rows = [{"model": "arch.problem", "pk": 1, "fields": {"puid": "NOSTMT", "hyperlink": ""}}]
        kept = parse_fixture(rows)
        self.assertEqual(len(kept.problems), 1)
        self.assertTrue(any("no statement text" in w for w in kept.warnings))

        skipped = parse_fixture(rows, skip_missing_statement=True)
        self.assertEqual(len(skipped.problems), 0)


class DatabaseWriterTests(TestCase):
    def test_ingestion_is_idempotent(self):
        result = parse_fixture(FIXTURE_ROWS)
        first = ingest_into_database(result)
        self.assertEqual(first["created"], 2)
        self.assertEqual(first["hints"], 3)
        self.assertEqual(first["solutions"], 1)

        second = ingest_into_database(parse_fixture(FIXTURE_ROWS))
        self.assertEqual(second["created"], 0)
        self.assertEqual(second["unchanged"], 2)
        self.assertEqual(Hint.objects.count(), 3)
        self.assertEqual(Solution.objects.count(), 1)
        self.assertEqual(Problem.objects.count(), 2)

    def test_dry_run_writes_nothing(self):
        summary = ingest_into_database(parse_fixture(FIXTURE_ROWS), dry_run=True)
        self.assertEqual(summary["created"], 2)
        self.assertEqual(Problem.objects.count(), 0)

    def test_management_command_imports_a_fixture_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "all.json"
            path.write_text(json.dumps(FIXTURE_ROWS), encoding="utf-8")
            call_command("ingest_arch_fixture", str(path), "--default-category", "auto", verbosity=0)
            self.assertEqual(Problem.objects.count(), 2)
            self.assertEqual(load_fixture(path)[0]["model"], "arch.problem")

    def test_real_upstream_fixture_parses_if_present(self):
        """If fixtures/all.json has been downloaded, it must parse without error."""
        upstream = Path("fixtures/all.json")
        if not upstream.exists():
            self.skipTest("fixtures/all.json not downloaded (see manage.py fetch_arch_fixture)")
        result = parse_fixture(load_fixture(upstream))
        self.assertGreaterEqual(result.stats["problem_rows"], 3)
        self.assertEqual(result.n_problems, result.stats["problems_built"])
        # every parsed hint must be reachable through its problem
        for problem in result.problems:
            for hint in problem.hints:
                self.assertTrue(hint.content_md.strip())


class TeXRendererTests(TestCase):
    def test_escapes_html_but_keeps_math(self):
        html = render_rich("<script>alert(1)</script> and $a<b$")
        self.assertNotIn("<script>", html)
        self.assertIn("&lt;script&gt;", html)
        self.assertIn('class="math-inline"', html)
        self.assertIn("$a&lt;b$", html)  # escaped for HTML, intact as textContent for KaTeX

    def test_display_math_and_environments(self):
        html = render_rich(r"Text $$x^2$$ and \\[y^2\\]")
        self.assertIn('class="math-block"', html)
        self.assertIn("$$x^2$$", html)
        env = render_rich(r"\begin{align} a &= b \\ c &= d \end{align}")
        self.assertIn("$$", env)

    def test_attribute_injection_is_neutralised(self):
        html = render_rich('<img src=x onerror=alert(1)> $x$')
        self.assertNotIn("<img", html)
        self.assertIn("&lt;img", html)

    def test_markdown_lists_and_bold(self):
        html = render_rich("- **first** item\n- second item")
        self.assertIn("<ul>", html)
        self.assertIn("<strong>first</strong>", html)
        self.assertIn("<li>", html)

    def test_to_plain_text_strips_tex_commands(self):
        plain = to_plain_text(r"Let $k = \frac{a^2+b^2}{ab+1}$ be given.")
        self.assertNotIn("\\frac", plain)
        self.assertNotIn("$", plain)
        self.assertIn("Let", plain)

    def test_empty_inputs_are_safe(self):
        self.assertEqual(render_rich(""), "")
        self.assertEqual(render_rich(None), "")
        self.assertEqual(to_plain_text(None), "")

    def test_renderer_output_is_stable_for_the_seed_corpus(self):
        from problems.seed_data.showcase import PROBLEMS

        for problem in PROBLEMS:
            html = render_rich(problem["statement_tex"])
            self.assertNotIn("<script", html)
            self.assertTrue(html.strip())
            for hint in problem["hints"]:
                self.assertTrue(render_rich(hint).strip())
            self.assertTrue(render_rich(problem["official_tex"]).strip())
