"""Qualité du rendu LaTeX : réparations du corpus et intégrité de la mise en page.

Ces tests verrouillent le travail sur le rendu : le corpus importé contient du LaTeX
abîmé (macros de concours, commandes de mise en page, contrôle caractères perdus,
BBCode de forums, tableaux sans séparateur de ligne). Chacun de ces dégâts doit être
réparé **au moment du rendu**, sans jamais toucher aux données stockées.
"""

from __future__ import annotations

from django.test import SimpleTestCase

from problems.services.tex import (
    MATH_ALIASES,
    convert_bbcode,
    convert_text_environments,
    render_rich,
    repair_control_chars,
    sanitize_math,
    to_plain_text,
    tokenize_math,
)

SLASH = chr(92)   # un antislash, écrit ainsi pour rester lisible


class AliasAndControlCharTests(SimpleTestCase):
    """Les macros des concours et les caractères de contrôle perdus."""

    def test_benchmark_aliases_are_expanded(self):
        self.assertEqual(sanitize_math(SLASH + "plus{} 1"), "+ 1")
        self.assertEqual(sanitize_math("a " + SLASH + "equal{} b"), "a = b")
        self.assertEqual(sanitize_math("a " + SLASH + "minus{} b"), "a - b")
        self.assertEqual(sanitize_math(SLASH + "ZZ"), SLASH + "mathbb{Z}")
        self.assertEqual(sanitize_math(SLASH + "RR^2"), SLASH + "mathbb{R}^2")
        self.assertEqual(sanitize_math(SLASH + "sgn(x)"), SLASH + "operatorname{sgn}(x)")

    def test_documented_alias_table_is_complete(self):
        for name in ("plus", "minus", "equal", "ZZ", "RR", "QQ", "NN", "CC"):
            self.assertIn(name, MATH_ALIASES)

    def test_every_alias_renders_without_leaving_its_name(self):
        for name, replacement in MATH_ALIASES.items():
            rendered = sanitize_math(SLASH + name + " x")
            self.assertNotIn(SLASH + name, rendered)
            self.assertTrue(rendered.startswith(replacement[:2]), rendered)

    def test_control_characters_are_restored_to_commands(self):
        # le caractère de contrôle 0x0c est un `\\f` dont l'antislash a été mangé :
        # « \x0c » suivi de « rac » est le `\\frac` d'origine
        self.assertEqual(repair_control_chars("\x0c" + "rac{1}{2}"), SLASH + "frac{1}{2}")
        self.assertNotIn("\x0c", repair_control_chars("a \x0c" + " b"))
        self.assertEqual(repair_control_chars("x\x15 y"), "x y")
        self.assertEqual(repair_control_chars("x\x01 y"), "x y")

    def test_layout_commands_are_removed_not_shown(self):
        rendered = sanitize_math(SLASH + "vspace{2pt} x " + SLASH + "indent y " + SLASH + "ref{eq:1}")
        for leftover in ("vspace", "indent", SLASH + "ref"):
            self.assertNotIn(leftover, rendered)
        self.assertIn("x", rendered)

    def test_mbox_becomes_text(self):
        self.assertEqual(sanitize_math(SLASH + "mbox{if } x > 0"), SLASH + "text{if } x > 0")

    def test_text_mode_underscores_are_escaped(self):
        rendered = sanitize_math(SLASH + "text{since a_0 is }")
        self.assertIn(SLASH + "_0", rendered)


class CorpusDamageRepairTests(SimpleTestCase):
    """BBCode, environnements, tableaux, délimiteurs : les dégâts de l'import."""

    def test_bbcode_paired_tags_become_markdown(self):
        self.assertEqual(convert_bbcode("[b]Trouver[/b] [i]tout[/i]"), "**Trouver** *tout*")

    def test_bbcode_list_becomes_markdown_list(self):
        self.assertIn("- un", convert_bbcode("[list][*] un [*] deux[/list]"))

    def test_lone_brackets_are_not_touched(self):
        # `$[x]$` est une notation mathématique, pas une balise BBCode
        self.assertEqual(convert_bbcode("$[x]$ et $[b]$"), "$[x]$ et $[b]$")

    def test_layout_environments_become_real_lists(self):
        html = render_rich(r"\begin{enumerate} \item un \item deux \end{enumerate}")
        self.assertEqual(html, "<ol><li>un</li><li>deux</li></ol>")
        self.assertNotIn("enumerate", html)

    def test_tabular_is_rendered_as_array(self):
        html = render_rich(r"\[\begin{tabular}{cc} a & b \\ c & d \end{tabular}\]")
        self.assertIn(r"\begin{array}{cc}", html)
        self.assertNotIn("tabular", html)

    def test_hline_used_as_row_separator_gets_its_line_break(self):
        body = SLASH + "begin{array}{c} a " + SLASH + "hline b " + SLASH + "end{array}"
        repaired = sanitize_math(body, display=True)
        self.assertIn(SLASH * 2 + " " + SLASH + "hline", repaired)

    def test_hline_outside_an_array_is_dropped(self):
        body = SLASH + "begin{array}{c} a " + SLASH + "end{array} " + SLASH + "hline"
        self.assertNotIn(SLASH + "hline", sanitize_math(body, display=True))

    def test_bare_left_brace_becomes_a_delimiter(self):
        body = SLASH + "left{x " + SLASH + "right}"
        repaired = sanitize_math(body, display=True)
        self.assertIn(SLASH + "left" + SLASH + "{", repaired)
        self.assertIn(SLASH + "right" + SLASH + "}", repaired)

    def test_orphan_left_right_are_removed(self):
        self.assertEqual(sanitize_math("(1+5^{2}" + SLASH + "right)"), "(1+5^{2})")
        self.assertEqual(sanitize_math(SLASH + "left( x"), "( x")

    def test_complete_left_right_pairs_survive(self):
        body = SLASH + "left( x " + SLASH + "right)"
        self.assertEqual(sanitize_math(body), body)

    def test_lost_display_closer_is_restored(self):
        tokens = tokenize_math("Posons " + SLASH + "[ f(x) = 1 ] puis fin.")
        maths = [content for kind, content, _ in tokens if kind == "math"]
        self.assertEqual(len(maths), 1)
        self.assertIn("f(x) = 1", maths[0])
        self.assertNotIn("puis fin", maths[0])

    def test_aboxed_loses_its_box_but_keeps_the_alignment(self):
        body = SLASH + "begin{align*} " + SLASH + "Aboxed{f(n) &= 1} " + SLASH + "end{align*}"
        rendered = sanitize_math(body, display=True)
        self.assertIn("f(n) &= 1", rendered)
        self.assertNotIn("boxed", rendered)

    def test_double_dollar_inside_a_formula_is_dropped(self):
        html = render_rich(r"$(x+y)=$\begin{cases} 1 & \text{si } x>0 \\ 0 & \text{sinon} \end{cases}$")
        self.assertIn("math-inline", html)
        self.assertNotIn("$$", html.split("math-block")[0].split(">")[-1])


class ProseIsNeverSwallowedTests(SimpleTestCase):
    """Un `$` orphelin ne doit pas avaler la phrase qui suit."""

    prose = "Il dit $terme. Since the first factor contains '+2 x^{3}' puis fin."

    def test_trailing_prose_is_not_rendered_as_math(self):
        blocks = [content for kind, content, _ in tokenize_math(self.prose) if kind == "math"]
        self.assertEqual(blocks, [])

    def test_the_orphan_delimiter_is_not_displayed(self):
        self.assertNotIn("$", render_rich(self.prose))

    def test_a_real_formula_next_to_broken_math_still_renders(self):
        text = self.prose + " Et " + SLASH + "[ x^2 = 1 " + SLASH + "]."
        html = render_rich(text)
        self.assertIn("math-block", html)
        self.assertIn("x^2 = 1", html)

    def test_an_unclosed_formula_of_plain_words_is_not_math(self):
        def _tokens(text):
            return [(kind, content) for kind, content, _ in tokenize_math(text)]

        # l'ouvreur orphelin est retiré : il ne doit pas s'afficher
        self.assertEqual(_tokens("Une valeur $x et la suite"), [("text", "Une valeur x et la suite")])
        # une formule non refermée mais clairement mathématique reste composée
        kinds = [kind for kind, _ in _tokens("Reste $x^2")]
        self.assertIn("math", kinds)


class LayoutIntegrityTests(SimpleTestCase):
    """La phrase ne doit jamais être découpée par une formule en ligne."""

    def test_inline_math_stays_inside_its_paragraph(self):
        html = render_rich(r"Trouver toutes les fonctions $f: \mathbb{R} \to \mathbb{R}$ telles que.")
        self.assertEqual(html.count("<p>"), 1)
        self.assertEqual(html.count("</p>"), 1)
        self.assertIn("math-inline", html)
        self.assertLess(html.index("<p>"), html.index("math-inline"))
        self.assertGreater(html.index("</p>"), html.index("math-inline"))

    def test_display_math_becomes_a_block(self):
        html = render_rich(r"Soit a tel que \[ a^2 = 1 \] alors.")
        self.assertIn('<div class="math-block">', html)
        self.assertEqual(html.count("<p>"), 2)
        self.assertLess(html.index("</p>"), html.index("math-block"))
        self.assertGreater(html.index("</p>", html.index("math-block")), html.index("math-block"))

    def test_several_inline_formulas_share_one_paragraph(self):
        html = render_rich(r"Avec $a>0$ et $b>0$, montrer $a+b>0$.")
        self.assertEqual(html.count("<p>"), 1)
        self.assertEqual(html.count("math-inline"), 3)

    def test_bullet_and_numbered_lists(self):
        self.assertEqual(render_rich("- un\n- deux"), "<ul><li>un</li><li>deux</li></ul>")
        self.assertEqual(render_rich("1. un\n2. deux"), "<ol><li>un</li><li>deux</li></ol>")

    def test_rendered_html_never_shows_tex_plumbing(self):
        text = (
            "\x0crac{1}{2} " + SLASH + "vspace{2pt} " + SLASH + "mbox{a} [b]gras[/b] "
            + SLASH + "plus{} " + SLASH + "ZZ"
        )
        html = render_rich(text)
        for forbidden in ("\x0c", SLASH + "vspace", SLASH + "mbox", "[b]", SLASH + "plus", SLASH + "ZZ"):
            self.assertNotIn(forbidden, html)

    def test_plain_text_view_has_no_control_characters(self):
        self.assertNotIn("\x0c", to_plain_text("\x0frac{1}{2} et " + SLASH + "vspace{1pt}"))


class CorpusInvariantTests(SimpleTestCase):
    """Invariant sur un échantillon : le rendu ne doit contenir aucune scorie connue."""

    FORBIDDEN = (
        "\x0c", "\x15", "\x01",
        SLASH + "plus", SLASH + "minus", SLASH + "equal",
        SLASH + "ZZ", SLASH + "RR", SLASH + "QQ", SLASH + "NN", SLASH + "CC",
        SLASH + "vspace", SLASH + "mbox", SLASH + "indent", SLASH + "ref{",
        "[b]", "[/b]", "[i]", "[tex]", "[/list]",
        "\r\n", "  ", 
    )

    SAMPLE = (
        # énoncé réel du corpus : maths en ligne + bloc d'affichage
        r"Soient $a, b > 0$ des réels tels que $a + b = 1$. Prouver que"
        r"\[ \left(1 + \frac{1}{a}\right)\left(1 + \frac{1}{b}\right) \ge 9, \]"
        r"avec égalité si et seulement si $a = b = \tfrac12$.",
        # solution réelle : environnement tabulé et `\hline`
        SLASH + "begin{array}{|c|c|} " + SLASH + "hline n & 3 " + SLASH * 2
        + " " + SLASH + "hline 4 & 5 " + SLASH * 2 + " " + SLASH + "end{array}",
        # macros de concours mélangées à des commandes de mise en page
        "x^n " + SLASH + "plus{} ax^{n " + SLASH + "minus{} 1} " + SLASH + "plus{} pq"
        + " " + SLASH + "vspace{4pt} " + SLASH + "ZZ",
        # BBCode et contrôle caractère
        "\x0crac{1}{2} [b]but[/b] [list][*] un [*] deux[/list]",
        # formule cassée du corpus : `\left` sans antislash
        SLASH + "left{p_{1} p_{2} " + SLASH + "mid p_{1} p_{2}" + SLASH + "right.",
    )

    def test_no_known_scorie_survives_rendering(self):
        for text in self.SAMPLE:
            html = render_rich(text)
            for forbidden in self.FORBIDDEN:
                self.assertNotIn(forbidden, html, f"{forbidden!r} dans le rendu de {text[:60]!r}")

    def test_brackets_of_floor_notation_survive(self):
        html = render_rich(r"Alors $[x] + [y] \le [x+y]$ pour tout réel.")
        self.assertIn("[x] + [y]", html)
        self.assertNotIn("math-block", html)


class SentenceIntegrityTests(SimpleTestCase):
    """La phrase reste entière : les formules ne la découpent pas."""

    def test_bold_markdown_survives_a_formula_inside_it(self):
        html = render_rich(r"* **$a' \ne 0$.** Sinon $k = b^2$.")
        self.assertIn("<li>", html)
        self.assertIn("<strong>", html)
        self.assertIn(r"$a' \ne 0$", html)
        self.assertNotIn("**", html)

    def test_existing_formula_is_never_rewrapped(self):
        from problems.services.tex import wrap_prose_math

        line = r"**$a' \ne 0$.** Sinon $k = b^2$."
        self.assertEqual(wrap_prose_math(line), line)

    def test_literal_dollar_is_not_a_delimiter(self):
        html = render_rich(r"Le coût est \$320, la remise \$80, soit 75\% du prix.")
        self.assertIn("&#36;320", html)
        self.assertIn("&#36;80", html)
        self.assertNotIn("math-inline", html)

    def test_escaped_commands_of_prose_are_readable(self):
        html = render_rich(r"Il paie \$5, soit 100\% en 2\,ans.")
        self.assertNotIn(SLASH + "%", html)
        self.assertNotIn(SLASH + ",", html)

    def test_math_commands_are_not_mistaken_for_escapes(self):
        # `\times`, `\text`, `\theta`… commencent comme `\t` mais sont des formules
        for tex in (r"$a \times b$", r"$\theta \neq 0$", r"$x \text{ et } y$"):
            tokens = tokenize_math(tex)
            self.assertEqual([kind for kind, _body, _display in tokens], ["math"], tex)

    def test_currency_dollars_do_not_shift_the_following_formulas(self):
        html = render_rich(r"il paie $\$40$ puis $\$10$, soit $\frac{1}{5}$ du total.")
        self.assertIn(r"$\frac{1}{5}$", html)
        self.assertEqual(html.count('class="math-inline"'), 3)   # 40, 10 et 1/5

    def test_braces_of_escaped_sets_survive(self):
        html = render_rich(r"pour les ensembles \(\left\{i_{2}, \ldots, i_{k}\right\}\) de \([n]\).")
        self.assertIn(r"\left\{i_{2}, \ldots, i_{k}\right\}", html)
        self.assertIn(r"$[n]$", html)

    def test_layout_commands_and_lost_tables_are_neutralised(self):
        self.assertEqual(sanitize_math(r"x \vspace{1em} y", display=False), "x y")
        self.assertEqual(sanitize_math(r"0\.78", display=False), "0.78")
        self.assertNotIn(r"\hline", sanitize_math(r"N & & 0 \\ \hline x", display=False))
        self.assertIn(r"\quad", sanitize_math(r"N & & 0 x", display=False))
