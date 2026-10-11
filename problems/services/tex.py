"""
Safe TeX + light-Markdown rendering.

Threat model
------------
Problem statements, hints, official solutions and AI feedback are all text that
we render into the DOM.  Two things must never happen:

1.  Stored XSS.  Everything is HTML-escaped *before* any markup is generated;
    the renderer therefore only ever emits a fixed, safe whitelist of tags
    (``p``, ``br``, ``ul``, ``li``, ``strong``, ``em``, ``code``, ``span``,
    ``div``) and never copies attacker-controlled attribute values.
2.  Math must reach KaTeX intact.  KaTeX reads ``textContent`` and renders into a
    sibling element, so escaping ``<``, ``>``, ``&`` inside ``$...$`` is not only
    safe, it is required for correct output.

Callables
---------
``render_rich(text)``  -> safe HTML for templates (``|safe``)
``to_plain_text(text)`` -> de-TeXed plain text (prompts, meta descriptions, search)

Three clean-up passes run before a single character reaches the page, because the
imported corpus (4 324 statements, thousands of solutions) is real-world LaTeX:
mangled by re-encodings, written for a full TeX distribution rather than KaTeX, and
occasionally containing layout commands that mean nothing in a web page.

``repair_control_chars``  puts back the escapes lost in transit (``\x0crac`` -> ``\frac``)
``sanitize_math``         rewrites or drops commands KaTeX does not implement
``MATH_ALIASES``          the same renames, also shipped to the browser as KaTeX macros
"""

from __future__ import annotations

import html
import re

__all__ = [
    "render_rich",
    "to_plain_text",
    "MATH_DELIMITERS",
    "MATH_ALIASES",
    "MATH_ENV_RENAMES",
    "TEXT_ENVIRONMENTS",
    "MATH_ENVIRONMENTS",
    "repair_control_chars",
    "convert_text_environments",
    "sanitize_math",
]

# --------------------------------------------------------------------------- #
# clean-up 1/2 : escapes mangled by re-encodings
# --------------------------------------------------------------------------- #
# A `\frac` that travelled through a layer that interpreted `\f` arrives as a form
# feed followed by "rac". Same story for `\b`, `\v`, `\r`, `\a`. When such a control
# character is followed by a letter it *was* a backslash, so we put it back; any
# other stray control character (NUL, NAK, …) is simply dropped.
_ESCAPED_CONTROL = {"\x07": "a", "\x08": "b", "\x0b": "v", "\x0c": "f", "\x0d": "r"}
_CONTROL_RE = re.compile(r"[\x07\x08\x0b\x0c\x0d](?=[A-Za-z])")
#: Les caractères de contrôle restants disparaissent, avec l'espace qui les entoure
#: (mais jamais un retour à la ligne : les paragraphes sont préservés).
_STRAY_CONTROL_RE = re.compile(r"[ \t]*[\x00-\x08\x0b\x0c\x0e-\x1f]+[ \t]*")


def repair_control_chars(text: str | None) -> str:
    r"""Restore escapes lost to re-encoding (``\\x0crac`` → ``\\frac``), drop the rest.

    >>> repair_control_chars("$\\x0crac{1}{2}$")
    '$\\\\frac{1}{2}$'
    """
    if not text:
        return text or ""
    text = _CONTROL_RE.sub(lambda m: "\\" + _ESCAPED_CONTROL[m.group(0)], text)
    return _STRAY_CONTROL_RE.sub(" ", text)


# --------------------------------------------------------------------------- #
# clean-up 2/2 : commands KaTeX does not implement
# --------------------------------------------------------------------------- #
#: Renames applied identically in the browser (``app.js`` passes them as KaTeX
#: macros, which also covers math typed by the student in a submission).
MATH_ALIASES: dict[str, str] = {
    "plus": "+",          # HMMT / China TST write $x^n \plus{} 1$
    "minus": "-",
    "equal": "=",
    "ZZ": r"\mathbb{Z}",
    "RR": r"\mathbb{R}",
    "QQ": r"\mathbb{Q}",
    "NN": r"\mathbb{N}",
    "CC": r"\mathbb{C}",
    "ee": r"\mathrm{e}",
    "sgn": r"\operatorname{sgn}",
    "hdots": r"\ldots",
    "o": "ø",
}

#: LaTeX-only commands: dropped inside ``$...$`` (they carry no mathematics).
_MATH_DROP = (
    r"\\vspace\s*\{(?:[^{}]|\{[^{}]*\})*\}",     # \vspace{1em}
    r"\\hspace\s*\{(?:[^{}]|\{[^{}]*\})*\}",     # \hspace{2pt}
    r"\\vskip\s+[0-9.]+[a-z]{0,2}",
    r"\\\[[0-9.]+(?:pt|em|ex|cm|mm|in)\]",       # \\[4pt]
    r"\\(?:sub)*section\*?\s*\{[^{}]*\}",
    r"\\(?:eq)?ref\s*\{[^{}]*\}",
    r"\\label\s*\{[^{}]*\}",
    r"\\makebox(?![A-Za-z])",
    r"\\mbox(?![A-Za-z])",                        # \mbox{x} -> \text{x}
    r"\\textnormal(?![A-Za-z])",
    r"\\textsl(?![A-Za-z])",
    r"\\indent(?![A-Za-z])",
    r"\\noindent(?![A-Za-z])",
    r"\\hfill(?![A-Za-z])",
    r"\\break(?![A-Za-z])",
    r"\\newpage(?![A-Za-z])",
    r"\\clearpage(?![A-Za-z])",
    r"\\eqno(?![A-Za-z])",
    r"\\atop(?![A-Za-z])",
    r"\\displaylines(?![A-Za-z])",
    r"\\allowbreak(?![A-Za-z])",
    r"\\smallskip|\\medskip|\\bigskip",
    r"\\displaystyle(?![A-Za-z])",                # inutile ici : KaTeX est déjà en display
    r"\\limits(?![A-Za-z])",
)
_MATH_DROP_RE = re.compile("|".join(_MATH_DROP))
_MATH_RENAME = {
    "mbox": r"\text",
    "textnormal": r"\text",
    "textsl": r"\textit",
    "makebox": r"\text",
    "Aboxed": r"\boxed",
    "fboxed": r"\boxed",
    "mod": r"\bmod",
}
_TAG_RE = re.compile(r"\\tag\s*\{[^{}]*\}")
_PCT_RE = re.compile(r"(?<!\\)%")
_HASH_RE = re.compile(r"(?<!\\)#")
#: ``\ \hline`` : le séparateur de ligne a perdu un antislash à l'import
_ROW_BREAK_RE = re.compile(r"\\s+(?=\\hline)")
#: antislash solitaire (ni commande, ni séparateur) : invalide en mode math
_LONE_SLASH_RE = re.compile(r"(?<!\\)\\(?=\s|$)")
_HLINE_RE = re.compile(r"\\hline(?![A-Za-z])")
_TRAILING_HLINE_RE = re.compile(r"\\hline(?![A-Za-z])\s*(?=\\end)")
_EM_RE = re.compile(r"\\em(?![A-Za-z])")
#: Un titre de section dont l'accolade fermante est partie avec le découpage :
#: `\section*{Impossibilité via ` doit disparaître jusqu'à la fin du fragment.
_CUT_HEADER_RE = re.compile(r"\\(?:sub)*section\*?\s*\{[^}]*\Z|\\[A-Za-z]*(?:ref|label|tag|index)\s*\{[^}]*\Z")
_OPENDELIM_RE = re.compile(r"\\[()]")
_ALIAS_RE = {
    name: re.compile(r"\\" + name + r"(?![A-Za-z])")
    for name in MATH_ALIASES
    if name not in _MATH_RENAME
}


def _escape_brace_delimiters(text: str) -> str:
    r"""``\left{`` → ``\left\{`` et ``\right}`` → ``\right\}``.

    KaTeX refuse une accolade non échappée après ``\left`` / ``\right`` ; le corpus
    en contient (le ``\`` a disparu à l'import). On travaille par remplacement de
    chaînes, sans expression régulière ni échappement interprété.

    >>> _escape_brace_delimiters(chr(92) + "left{ x " + chr(92) + "right}")
    '\\left\\{ x \\right\\}'
    """
    slash = chr(92)
    out = text
    for command in ("left", "right"):
        for brace, escaped in (("{", slash + "{"), ("}", slash + "}")):
            out = out.replace(slash + command + brace, slash + command + escaped)
            out = out.replace(slash + command + " " + brace, slash + command + escaped)
    return out

#: ``\bigg {\{}`` → ``\bigg\{`` : KaTeX refuse un groupe là où il attend un délimiteur.
_DELIMITER_GROUP_RE = re.compile(
    r"\\(?P<cmd>big|Big|bigg|Bigg)(?P<tail>[lrm]?)\s*\{\s*(?P<delim>\\[{}|.]|[()[\]|.])\s*\}"
)
#: ``\begin{array}{c@{ }c}`` → ``\begin{array}{cc}`` (KaTeX ignore les colonnes `@{}`).
_ARRAY_SPEC_RE = re.compile(
    r"(\\begin\s*\{(?:array|subarray|tabular)\})\s*\{((?:[^{}]|\{[^{}]*\})*)\}",
    re.IGNORECASE,
)


def _clean_array_spec(match: re.Match) -> str:
    spec = match.group(2)
    spec = re.sub(r"@\s*\{[^{}]*\}", "", spec)      # espacement inter-colonnes
    spec = re.sub(r"[pmb]\s*\{[^{}]*\}", "c", spec)  # colonnes de largeur fixe
    return match.group(1) + "{" + spec + "}"


def _at_depth_zero(body: str) -> list[bool]:
    """Pour chaque caractère, ``True`` s'il est **hors de toute accolade**.

    Sert à ne toucher qu'à la structure d'une formule : un ``&`` au premier niveau est
    un séparateur de colonnes, tandis que celui de ``\\text{a & b}`` est du texte.
    """
    depth = 0
    escaped = False
    flags: list[bool] = []
    for char in body:
        flags.append(depth == 0 and not escaped)
        if escaped:
            escaped = False
            continue
        if char == chr(92):
            escaped = True
        elif char == "{":
            depth += 1
        elif char == "}":
            depth = max(0, depth - 1)
    return flags


def _replace_at_depth_zero(body: str, needle: str, replacement: str) -> str:
    """Remplace ``needle`` là où il est au premier niveau d'accolades."""
    flags = _at_depth_zero(body)
    out: list[str] = []
    index = 0
    while index < len(body):
        if flags[index] and body.startswith(needle, index):
            out.append(replacement)
            index += len(needle)
            continue
        out.append(body[index])
        index += 1
    return "".join(out)


#: Commandes de mise en page que KaTeX ne connaît pas : elles ne portent aucun contenu
#: mathématique, on les retire avec leur argument éventuel.
_LAYOUT_COMMAND_RE = re.compile(
    r"\\(?:vspace\*?|hspace\*?|vskip|hskip|vfill|hfill|smallskip|medskip|bigskip"
    r"|noindent|newpage|clearpage|pagebreak|linebreak|allowbreak|par)"
    r"(?:\s*\{[^{}]*\})?",
    re.MULTILINE,
)
#: Un corps qui contient un environnement mathématique sait se servir de ``&`` et
#: ``\\hline`` ; sans environnement, ces deux-là sont des commandes inconnues.
_MATH_ENV_RE = re.compile(
    r"\\begin\{(?:array|matrix|pmatrix|bmatrix|vmatrix|Vmatrix|smallmatrix|cases"
    r"|aligned|align\*?|gathered|gather\*?|split|subarray|equation\*?)\}",
)


def _drop_stray_dollars(body: str) -> str:
    r"""Retire les ``$`` qui n'ont aucun sens en mode mathématique.

    ``$`` n'est légitime qu'à l'intérieur d'un ``\text{…}`` (KaTeX y repasse en mode
    mathématique). Ailleurs — dans un tableau, un environnement — c'est un résidu de
    conversion : KaTeX refuse la formule entière à cause de lui.

    >>> _drop_stray_dollars(r"\begin{array}{r} $P 7 R$ \end{array}")
    '\\begin{array}{r} P 7 R \\end{array}'
    >>> _drop_stray_dollars(r"\text{si $x > e$}")
    '\\text{si $x > e$}'
    """
    out: list[str] = []
    depth = 0
    index = 0
    while index < len(body):
        char = body[index]
        if char == "\\":
            out.append(body[index : index + 2])
            index += 2
            continue
        if char == "{":
            depth += 1
        elif char == "}":
            depth = max(0, depth - 1)
        elif char == "$" and depth == 0:
            # un `$` isolé suivait souvent une commande (`\hline$R Q 0$`) : sans
            # espace, le nom de la commande se prolongerait (`\hlineR`)
            if out and out[-1][-1:].isalpha():
                out.append(" ")
            index += 1
            continue
        out.append(char)
        index += 1
    return "".join(out)


_ENV_TOKEN_RE = re.compile(r"\\(?P<kind>begin|end)\s*\{(?P<name>[a-zA-Z*]+)\}")
_TEXT_MODE_RE = re.compile(r"\\(?:text|textrm|textit|textbf|mbox|textnormal)\s*\{")


_ENV_HEAD_RE = re.compile(r"\\begin\s*\{[a-zA-Z*]+\}\s*(?:\{[^{}]*\})?\s*$")


def _repair_hline_rows(body: str) -> str:
    r"""Ajoute le séparateur de ligne manquant devant un ``\hline``.

    Dans le corpus, ``\hline`` tient parfois lieu de ``\\`` : les lignes du tableau ne
    sont alors jamais terminées et KaTeX refuse le filet. Un ``\\`` est inséré quand le
    filet n'est ni en début de tableau, ni précédé d'un séparateur.

    >>> _repair_hline_rows(chr(92) + "begin{array}{c} a " + chr(92) + "hline b " + chr(92) + "end{array}")
    '\\begin{array}{c} a \\\\ \\hline b \\end{array}'
    """
    out: list[str] = []
    cursor = 0
    while True:
        match = _HLINE_RE.search(body, cursor)
        if not match:
            out.append(body[cursor:])
            break
        out.append(body[cursor : match.start()])
        head = "".join(out).rstrip()
        starts_row = head.endswith("\\\\") or bool(_ENV_HEAD_RE.search(head))
        if not starts_row:
            out.append("\\\\ ")
        out.append(r"\hline")
        cursor = match.end()
    return "".join(out)


def _drop_orphan_hlines(body: str) -> str:
    r"""Retire les ``\hline`` qui ne sont dans aucun tableau.

    KaTeX n'accepte un filet que dans un environnement ``array`` ; le corpus en laisse
    après le ``\end{array}`` (résidu de conversion), ce qui fait échouer la formule
    entière. Ceux qui sont à l'intérieur sont conservés — ils dessinent le tableau.

    >>> _drop_orphan_hlines(chr(92) + "begin{array}{c} a " + chr(92) + "end{array} " + chr(92) + "hline")
    '\\begin{array}{c} a \\end{array}  '
    """
    out: list[str] = []
    depth = 0
    cursor = 0
    for match in _ENV_TOKEN_RE.finditer(body):
        segment = body[cursor : match.start()]
        out.append(segment if depth else _HLINE_RE.sub(" ", segment))
        out.append(match.group(0))
        depth = max(0, depth + (1 if match.group("kind") == "begin" else -1))
        cursor = match.end()
    tail = body[cursor:]
    out.append(tail if depth else _HLINE_RE.sub(" ", tail))
    return "".join(out)


def _escape_text_mode_underscores(body: str) -> str:
    r"""Échappe les ``_`` à l'intérieur d'un ``\text{…}``.

    En mode texte, KaTeX n'accepte pas ``_`` non échappé : ``\text{a_0}`` échoue.
    Le rendu visuel avec l'échappement est identique.

    >>> _escape_text_mode_underscores(chr(92) + "text{a_0 est entier}")
    '\\text{a\\_0 est entier}'
    """
    out: list[str] = []
    cursor = 0
    while True:
        match = _TEXT_MODE_RE.search(body, cursor)
        if not match:
            out.append(body[cursor:])
            break
        out.append(body[cursor : match.end()])
        depth = 0
        for position in range(match.end() - 1, len(body)):
            if body[position] == "{":
                depth += 1
            elif body[position] == "}":
                depth -= 1
                if depth == 0:
                    inner = re.sub(r"(?<!\\)_", lambda _m: chr(92) + "_", body[match.end() : position])
                    out.append(inner)
                    cursor = position
                    break
        else:
            break
    return "".join(out)


#: Commandes collées à la lettre suivante : ``\toR`` se lit ``\toR`` (inconnu) et non
#: ``\to R``. Le corpus oublie souvent l'espace ; on la remet.
#: Les commandes mathématiques courantes. Elles servent à deux choses : ne jamais
#: découper une commande valide (``\int``, ``\inf``, ``\intercal``) et retrouver, dans
#: un nom collé, la commande qu'il cache (``\geqx`` → ``\geq x``).
_KNOWN_COMMANDS = frozenset("""
alpha beta gamma delta epsilon varepsilon zeta eta theta vartheta iota kappa lambda mu nu
xi pi varpi rho varrho sigma varsigma tau upsilon phi varphi chi psi omega
Gamma Delta Theta Lambda Xi Pi Sigma Upsilon Phi Psi Omega
frac dfrac tfrac cfrac sqrt binom dbinom tbinom choose overset underset stackrel
sum prod coprod int iint iiint oint lim limsup liminf sup inf min max det gcd lcm
sin cos tan cot sec csc arcsin arccos arctan sinh cosh tanh coth exp log ln lg deg dim
ker hom arg Pr mod bmod pmod
cdot cdots vdots ddots ldots dots dotsb dotsc dotsi dotsm dotso
times div pm mp ast star circ bullet oplus ominus otimes oslash odot dagger ddagger
cup cap uplus sqcup sqcap vee wedge setminus smallsetminus wr diamond bigtriangleup
leq geq le ge neq ne equiv sim simeq approx cong asymp propto ll gg prec succ
subset supset subseteq supseteq sqsubset sqsupset sqsubseteq sqsupseteq in ni notin
owns perp parallel mid nmid models vdash dashv top bot angle triangle square
forall exists nexists neg lnot emptyset varnothing infin infty aleph hbar ell wp
Re Im prime partial nabla imath jmath
to gets rightarrow leftarrow leftrightarrow Rightarrow Leftarrow Leftrightarrow
mapsto longrightarrow longleftarrow longleftrightarrow implies iff
uparrow downarrow updownarrow nearrow searrow swarrow nwarrow
left lfloor rfloor lceil rceil langle rangle lvert rvert lVert rVert
backslash vert Vert lbrace rbrace lbrack rbrack
left right big Big bigg Bigg Bigl Bigr bigl bigr biggl biggr biggl biggr
quad qquad hspace vspace mspace
overline underline overbrace underbrace overline widehat widetilde
hat check breve acute grave tilde bar vec dot ddot mathring
text textbf textit textrm textsf texttt mathrm mathbf mathit mathsf mathtt
mathbb mathcal mathfrak mathscr boldsymbol bm
operatorname operatorname* DeclareMathOperator
begin end item hline cline vline
substack textstyle displaystyle scriptstyle scriptscriptstyle limits nolimits
colon mid dblcolon
stackrel stackbin underset overset
raisebox mbox hbox fbox boxed Aboxed phantom vphantom hphantom
square blacksquare triangle blacktriangle
qed square qedsymbol
binom
aleph beth gimel daleth
pmod
""".split())


def _split_glued_command(name: str) -> tuple[str, str] | None:
    r"""Découpe un nom de commande collé à l'atome suivant.

    L'import a mangé des espaces : ``\geqx_{1}`` s'écrit pour ``\geq x_{1}``. On ne
    découpe que si le reste est **une seule lettre** — sinon ``\geqslant`` et
    ``\intercal`` seraient saccagés.

    >>> _split_glued_command(chr(92) + "geqx")
    ('\\geq', 'x')
    >>> _split_glued_command(chr(92) + "intercal") is None
    True
    """
    body = name[1:]
    if body in _KNOWN_COMMANDS:
        return None
    for cut in range(len(body) - 1, 1, -1):
        prefix, rest = body[:cut], body[cut:]
        if prefix in _KNOWN_COMMANDS and len(rest) == 1 and (rest.isalpha() or rest.isdigit()):
            return "\\" + prefix, rest
    return None


_COMMAND_RUN_RE = re.compile(r"[A-Za-z]+")


def _separate_glued_commands(body: str) -> str:
    r"""``	oR`` → ``	o R`` (l'espace avalée à l'import).

    >>> _separate_glued_commands(chr(92) + "toR")
    '\\to R'
    >>> _separate_glued_commands(chr(92) + "geqx_{1}")
    '\\geq x_{1}'
    >>> _separate_glued_commands(chr(92) + "top") + " et " + chr(92) + "int_0^1"
    '\\top et \\int_0^1'
    """
    out: list[str] = []
    index = 0
    while index < len(body):
        if body[index] == chr(92) and index + 1 < len(body) and body[index + 1].isalpha():
            run = _COMMAND_RUN_RE.match(body, index + 1)
            if run:
                split = _split_glued_command(chr(92) + run.group(0))
                if split:
                    out.append(split[0] + " ")      # le reste est relu normalement
                    index += len(split[0])
                    continue
        out.append(body[index])
        index += 1
    return "".join(out)


def _balance_left_right(body: str) -> str:
    r"""Supprime les ``\left`` / ``\right`` orphelins (le corpus en a beaucoup).

    Une paire complète est conservée telle quelle. Un ``\left`` jamais refermé ou un
    ``\right`` sans ``\left`` est retiré : le crochet ordinaire reste, s'affiche à
    l'identique, et KaTeX cesse de refuser la formule entière.

    >>> _balance_left_right("(1+5+5^{2}" + chr(92) + "right) = 156")
    '(1+5+5^{2}) = 156'
    >>> _balance_left_right(chr(92) + "left( x " + chr(92) + "right)")
    '\\left( x \\right)'
    """
    pieces: list[list] = []            # [texte, à conserver]
    stack: list[int] = []              # positions des `\left` en attente
    index = 0
    while index < len(body):
        if body.startswith(r"\left", index) and not body[index + 5 : index + 6].isalpha():
            stack.append(len(pieces))
            pieces.append([r"\left", False])
            index += 5
            continue
        if body.startswith(r"\right", index) and not body[index + 6 : index + 7].isalpha():
            follower = body[index + 6 :].lstrip()
            if not follower or follower[0] == "}":
                # `\right` sans délimiteur (fin de fragment) : il ne peut pas se composer
                pieces.append([r"\right", False])
                index += 6
                continue
            if stack:
                pieces[stack.pop()][1] = True      # paire complète : les deux restent
                pieces.append([r"\right", True])
            else:
                pieces.append([r"\right", False])  # orphelin : retiré
            index += 6
            continue
        pieces.append([body[index], True])
        index += 1
    return "".join(piece for piece, keep in pieces if keep)


def _balance_braces(body: str) -> str:
    r"""Équilibre les accolades simples d'un fragment.

    Le corpus a perdu des accolades fermantes (``f: \mathbb{Z} \rightarrow{``).
    Les accolades manquantes sont ajoutées en fin de formule, les fermantes
    surnuméraires retirées. Les accolades échappées ``\{`` ``\}`` ne sont pas touchées.

    >>> _balance_braces(r"S={(x, y) \mid x>0")
    'S={(x, y) \\mid x>0}'
    """
    out: list[str] = []
    depth = 0
    index = 0
    while index < len(body):
        char = body[index]
        if char == "\\":
            out.append(body[index : index + 2])
            index += 2
            continue
        if char == "{":
            depth += 1
        elif char == "}":
            if depth == 0:
                index += 1              # fermante sans ouvrante : retirée
                continue
            depth -= 1
        out.append(char)
        index += 1
    return "".join(out) + "}" * depth


def _unwrap_command(body: str, name: str) -> str:
    r"""Retire ``\Aboxed{…}`` en gardant le contenu (les ``&`` doivent rester au niveau de l'alignement)."""
    pattern = re.compile(r"\\" + name + r"\s*\{")
    while True:
        match = pattern.search(body)
        if not match:
            return body
        depth = 0
        end = match.end() - 1
        for position in range(match.end() - 1, len(body)):
            if body[position] == "{":
                depth += 1
            elif body[position] == "}":
                depth -= 1
                if depth == 0:
                    end = position
                    break
        else:
            end = len(body)
        body = body[: match.start()] + body[match.end() : end] + body[end + 1 :]


#: Commandes après lesquelles une accolade échappée est un *délimiteur*, pas un
#: groupe : ``\left\{`` ne réclame aucun ``\right\}``.
_DELIMITER_COMMANDS = ("\\left", "\\right", "\\middle", "\\big", "\\Big", "\\bigg", "\\Bigg")


def _at_delimiter_position(body: str, position: int) -> bool:
    head = body[max(0, position - 8) : position]
    return any(head.endswith(cmd + tail) for cmd in _DELIMITER_COMMANDS for tail in ("", "l", "r", "m"))


def _balance_escaped_braces(body: str) -> str:
    r"""Répare les ``\{`` dont le ``\}`` a été perdu à l'import.

    ``\{B\}`` désigne un ensemble ; dans le corpus il devient parfois ``\{B}``, que
    KaTeX refuse. Une accolade échappée sans partenaire devient une accolade ordinaire,
    qui ouvre ou ferme un groupe : les accolades de groupement sont invisibles, le rendu
    est identique et la formule redevient composable. Les accolades en position de
    délimiteur (``\left\{``, ``\big\}``…) ne sont jamais touchées.

    >>> _balance_escaped_braces("D " + chr(92) + "backslash " + chr(92) + "{R}")
    'D \\backslash {R}'
    >>> _balance_escaped_braces(chr(92) + "left" + chr(92) + "{ x " + chr(92) + "right" + chr(92) + "}")
    '\\left\\{ x \\right\\}'
    """
    opens = [m.start() for m in re.finditer(r"\\\{", body) if not _at_delimiter_position(body, m.start())]
    closes = [m.start() for m in re.finditer(r"\\\}", body) if not _at_delimiter_position(body, m.start())]
    if len(opens) == len(closes):
        return body
    chars = list(body)
    if len(opens) > len(closes):
        for position in reversed(opens[: len(opens) - len(closes)]):
            chars[position] = "{"
            chars[position + 1] = ""
    else:
        for position in reversed(closes[: len(closes) - len(opens)]):
            chars[position] = "}"
            chars[position + 1] = ""
    return "".join(chars)


def sanitize_math(body: str, *, display: bool = False) -> str:
    r"""Make a math fragment digestible for KaTeX without changing the mathematics.

    * benchmark alias macros are expanded (``\\plus{}`` → ``+``, ``\\ZZ`` → ``\\mathbb{Z}``);
    * commands that only make sense in a full TeX page (``\\vspace``, ``\\ref``,
      ``\\section``…) are removed rather than shown as errors;
    * ``\\mbox``/``\\textsl``/``\\textnormal`` become ``\\text``/``\\textit``;
    * ``\\tag{…}`` is kept for display equations (KaTeX numbers them) and dropped
      for inline ones (KaTeX refuses it there).

    >>> sanitize_math(r"a \equal{} 1 \plus{} \left( \minus{} 1\right)^n")
    'a = 1 + \\\\left( - 1\\\\right)^n'
    """
    out = body

    # alias macros, including the `{}` padding the benchmark files add
    for name, replacement in MATH_ALIASES.items():
        if name in _MATH_RENAME:
            continue
        pattern = re.compile(r"\\" + name + r"\s*\{\}")
        out = pattern.sub(lambda _m, r=replacement: r, out)
        out = _ALIAS_RE[name].sub(lambda _m, r=replacement: r, out)

    # renames first (they take a braced argument), then the bare drops
    out = re.sub(r"\\mbox\s*\{", r"\\text{", out)
    out = re.sub(r"\\textnormal\s*\{", r"\\text{", out)
    out = re.sub(r"\\textsl\s*\{", r"\\textit{", out)
    out = re.sub(r"\\makebox\s*\{", r"\\text{", out)
    out = _unwrap_command(out, "Aboxed")          # garde le contenu, retire la boîte
    out = _unwrap_command(out, "fboxed")
    out = _unwrap_command(out, "em")              # `{\em texte}` (TeX 2.09)
    out = re.sub(r"\\mod(?![A-Za-z])", lambda _m: "\\bmod", out)
    out = _EM_RE.sub(" ", out)                    # `{\em texte}`
    out = _OPENDELIM_RE.sub(" ", out)             # `\(` / `\)` : invalides en mode math
    out = _MATH_DROP_RE.sub(" ", out)

    if not display:
        out = _TAG_RE.sub(" ", out)

    out = _DELIMITER_GROUP_RE.sub(lambda m: "\\" + m.group("cmd") + m.group("delim"), out)
    out = _escape_brace_delimiters(out)
    out = _ARRAY_SPEC_RE.sub(_clean_array_spec, out)
    out = _drop_stray_dollars(out)
    out = _LAYOUT_COMMAND_RE.sub(" ", out)            # \vspace{1em}, \hfill, \noindent…
    out = re.sub(r"(?<=\d)\\.(?=\d)", ".", out)     # `0\.78` : c'est un point décimal
    if not _MATH_ENV_RE.search(out):
        # tableau dont le `\\begin{array}` s'est perdu : sans environnement, KaTeX
        # refuse `\\hline` et `&`. On garde les valeurs, on perd les filets.
        out = _HLINE_RE.sub("", out)
        out = _replace_at_depth_zero(out, "&", r"\quad ")
    out = _balance_escaped_braces(out)
    out = _separate_glued_commands(out)
    out = _balance_left_right(out)
    out = _balance_braces(out)
    out = re.sub(r"\\\.(?![A-Za-z])", ".", out)          # `\.` : point échappé à la TeX
    out = re.sub(r"\\\\", " ", out) if not _ENV_BEGIN_RE.search(out) else out
    if _ENV_BEGIN_RE.search(out):
        out = _repair_hline_rows(out)
    out = _TRAILING_HLINE_RE.sub(" ", out)      # `\hline` juste avant `\end`
    out = re.sub(r"\\hline\s*$", "", out)       # `\hline` en fin de formule
    out = _EM_RE.sub(" ", out)                  # `\em` seul (TeX 2.09)
    out = _CUT_HEADER_RE.sub(" ", out)
    out = _drop_orphan_hlines(out)
    out = _escape_text_mode_underscores(out)
    if not _ENV_BEGIN_RE.search(out):
        # filets et `&` de tableau perdu : sans environnement, ils sont invalides
        out = re.sub(r"(?<![A-Za-z])&(?![A-Za-z])", " ", out)

    # Le `%` de LaTeX commente la fin de la ligne ; ici les retours à la ligne ont
    # été perdus à l'import, donc il est traité comme une espace — sinon il effacerait
    # la formule entière.
    out = _PCT_RE.sub(" ", out)
    out = _HASH_RE.sub(" ", out)                    # `#` : invalide en mode math
    out = _ROW_BREAK_RE.sub(lambda _m: chr(92) * 2 + " ", out)
    out = _LONE_SLASH_RE.sub(" ", out)

    # tidy the whitespace left by the removals, without touching math spacing
    out = re.sub(r"[ \t]{2,}", " ", out)
    out = re.sub(r"\s+([,.;:)])", r"\1", out)
    return out.strip()

#: Environments KaTeX does not implement, and their closest supported equivalent.
#: ``tabular`` (53 uses in the corpus) is an array; ``eqnarray`` is an aligned block.
MATH_ENV_RENAMES: dict[str, str] = {
    "tabular": "array",
    "tabular*": "array",
    "eqnarray": "aligned",
    "eqnarray*": "aligned",
    "displaylines": "gathered",
    "math": "aligned",
    "darray": "array",
}

#: Environments that are *page layout*, not mathematics: they must become real HTML.
TEXT_ENVIRONMENTS = frozenset(
    {
        "enumerate", "itemize", "description",
        "proof", "lemma", "lemma*", "theorem", "theorem*", "corollary", "proposition",
        "definition", "remark", "note", "abstract", "verbatim", "exercise", "example",
    }
)

#: Environments holding mathematical content (KaTeX renders every one of these).
MATH_ENVIRONMENTS = frozenset(
    {
        "align", "align*", "aligned", "alignat", "alignat*", "alignedat",
        "array", "cases", "dcases", "rcases", "split", "gathered", "gather", "gather*",
        "matrix", "pmatrix", "bmatrix", "Bmatrix", "vmatrix", "Vmatrix", "smallmatrix",
        "subarray", "equation", "equation*", "CD", "tikzcd",
    }
)

_ENV_BEGIN_RE = re.compile(r"\\begin\s*\{(?P<name>[a-zA-Z*]+)\}")
_ITEM_RE = re.compile(r"\\item\b\s*(?:\[(?P<label>[^\]]*)\])?")


def _rename_math_environments(text: str) -> str:
    """``\\begin{tabular}`` → ``\\begin{array}``, ``\\begin{eqnarray*}`` → ``\\begin{aligned}``."""
    def rename(match: re.Match) -> str:
        name = match.group("name")
        return "\\end{%s}" % MATH_ENV_RENAMES[name] if match.group(0).startswith("\\end") else \
               "\\begin{%s}" % MATH_ENV_RENAMES[name]

    pattern = re.compile(
        r"\\(?:begin|end)\s*\{(?P<name>" + "|".join(re.escape(n) for n in MATH_ENV_RENAMES) + r")\}"
    )
    return pattern.sub(rename, text)


def _balanced_environment(text: str, begin_index: int) -> tuple[str, int, int] | None:
    """Match a ``\\begin{name}`` with its own ``\\end{name}``, counting nesting."""
    opener = _ENV_BEGIN_RE.match(text, begin_index)
    if not opener:
        return None
    name = opener.group("name")
    depth = 0
    cursor = begin_index
    token_re = re.compile(
        r"\\begin\s*\{" + re.escape(name) + r"\}|\\end\s*\{" + re.escape(name) + r"\}"
    )
    for token in token_re.finditer(text, cursor):
        if token.group(0).startswith("\\begin"):
            depth += 1
        else:
            depth -= 1
            if depth == 0:
                return name, opener.end(), token.start()
    return None


def _environment_body_to_markdown(name: str, body: str) -> str:
    """Turn a layout environment into markdown-ish lines the renderer understands."""
    if name not in {"enumerate", "itemize", "description"}:
        # proof / lemma / abstract / verbatim: keep the content, drop the wrapper
        return "\n\n" + re.sub(r"[ \t]+", " ", body.strip()) + "\n\n"

    parts = _ITEM_RE.split(body)
    # re.split with one capture group yields [lead, label1, text1, label2, text2, …]
    lead = parts[0].strip()
    entries: list[tuple[str, str]] = []
    for index in range(1, len(parts), 2):
        label = (parts[index] or "").strip()
        content = parts[index + 1] if index + 1 < len(parts) else ""
        entries.append((label, re.sub(r"\s+", " ", content).strip()))

    lines: list[str] = []
    if lead:
        lines.append(re.sub(r"\s+", " ", lead))
    for position, (label, content) in enumerate(entries, start=1):
        if name == "enumerate":
            lines.append(f"{position}. {content}")
        elif label:
            lines.append(f"- **{label}** {content}")
        else:
            lines.append(f"- {content}")
    return "\n\n" + "\n".join(lines) + "\n\n"


def convert_text_environments(text: str) -> str:
    r"""Replace ``\begin{enumerate}…\end{enumerate}`` with a Markdown list.

    Innermost environments are converted first, so nesting survives. Anything that is
    not a known layout environment is left untouched (it is probably inside ``$…$``).

    >>> convert_text_environments(r"\begin{itemize}\item un\item deux\end{itemize}")
    '\n\n- un\n- deux\n\n'
    """
    guard = 0
    while guard < 200:
        guard += 1
        converted = False
        for match in _ENV_BEGIN_RE.finditer(text):
            name = match.group("name")
            if name not in TEXT_ENVIRONMENTS:
                continue
            spans = _balanced_environment(text, match.start())
            if not spans:
                continue
            _name, open_end, close_start = spans
            body = text[open_end:close_start]
            if _ENV_BEGIN_RE.search(body) and any(
                inner.group("name") in TEXT_ENVIRONMENTS for inner in _ENV_BEGIN_RE.finditer(body)
            ):
                continue  # a nested layout environment: convert the inner one first
            text = text[: match.start()] + _environment_body_to_markdown(name, body) + text[spans[2] + len(f"\\end{{{name}}}"):]
            converted = True
            break
        if not converted:
            break
    return text


# --------------------------------------------------------------------------- #
# math tokenising
# --------------------------------------------------------------------------- #
# Order matters: display math must be matched before inline math.
_MATH_RE = re.compile(
    r"""
    \$\$(?P<d1>.+?)\$\$                    # $$ ... $$
  | \\\[(?P<d2>.+?)\\\]                    # \[ ... \]
  | \\\((?P<i1>.+?)\\\)                    # \( ... \)
  | (?<!\\)\$(?P<i2>.+?)(?<!\\)\$          # $ ... $
    """,
    re.DOTALL | re.VERBOSE,
)

# \begin{env} ... \end{env}  used directly in the source (no $...$ wrapper)
_ENV_RE = re.compile(r"\\begin\{(?P<env>[a-zA-Z*]+)\}.*?\\end\{(?P=env)\}", re.DOTALL)

# Delimiters the KaTeX auto-render extension must be configured with (see base.html)
MATH_DELIMITERS = [
    {"left": "$$", "right": "$$", "display": True},
    {"left": "\\[", "right": "\\]", "display": True},
    {"left": "\\(", "right": "\\)", "display": False},
    {"left": "$", "right": "$", "display": False},
]

_INLINE_MD = (
    (re.compile(r"\*\*(?P<x>[^*]+)\*\*"), r"<strong>\g<x></strong>"),
    (re.compile(r"(?<![A-Za-z0-9_])\*(?P<x>[^*\n]+)\*(?![A-Za-z0-9_])"), r"<em>\g<x></em>"),
    (re.compile(r"`(?P<x>[^`]+)`"), r"<code>\g<x></code>"),
)


def _escape(text: str) -> str:
    """Escape HTML but keep it compact (quotes are not escaped: we never set attributes)."""
    return html.escape(text, quote=False)


def _render_math(inner: str, display: bool) -> str:
    """Clean a math fragment, then wrap it in the delimiters KaTeX understands."""
    body = _escape(sanitize_math(inner.strip(), display=display))
    if display:
        return f'<div class="math-block">$${body}$$</div>'
    # the class lets the client-side fallback renderer find math even when the
    # KaTeX CDN is unreachable (offline / sandboxed previews)
    return f'<span class="math-inline">${body}$</span>'


#: A line that opens a bullet or a numbered list item.
_LIST_ITEM_RE = re.compile(r"^\s*(?P<marker>[-*•]|\d+[.)])\s+(?P<body>.+)$")


def _inline(escaped_text: str) -> str:
    """Apply inline markdown to already-escaped text."""
    for pattern, replacement in _INLINE_MD:
        escaped_text = pattern.sub(replacement, escaped_text)
    return escaped_text


# --------------------------------------------------------------------------- #
# restes de BBCode (forums AoPS : [b], [i], [list], [*], [tex]…)
# --------------------------------------------------------------------------- #
# 510 balises traînent encore dans le corpus importé. Elles ne sont pas du LaTeX :
# on les traduit en markdown, que le rendu sait déjà composer.

#: Balises appariées → markdown. Volontairement limité aux balises **fermées** :
#: un `[b]` isolé peut être une notation mathématique (`$[b]$`), il doit rester.
_BBCODE_PAIRED = {
    "b": ("**", "**"),
    "i": ("*", "*"),
    "u": ("", ""),
    "s": ("", ""),
    "em": ("*", "*"),
    "strong": ("**", "**"),
    "code": ("`", "`"),
    "tex": ("$", "$"),
    "math": ("$", "$"),
    "quote": ("", ""),
    "center": ("", ""),
    "spoiler": ("", ""),
    "url": ("", ""),
    "color": ("", ""),
    "size": ("", ""),
    "font": ("", ""),
    "background": ("", ""),
    "img": ("", ""),          # images de forums, mortes depuis longtemps
}
_BBCODE_LIST_RE = re.compile(
    r"\[list(?P<kind>=[^\]]*)?\](?P<body>.*?)\[/list\]", re.IGNORECASE | re.DOTALL
)
_BBCODE_STANDALONE_RE = re.compile(r"\[(?:hr|br)\s*/?\]", re.IGNORECASE)


#: ``\n`` / ``\t`` écrits en toutes lettres : un reste d'échappement de conversion,
#: à ne pas confondre avec ``\times``, ``\text``, ``\theta``, ``\neq``…
_LITERAL_ESCAPE_RE = re.compile(r"\\[nt](?![A-Za-z])")

#: Une formule délimitée : ``$…$``, ``$$…$$``, ``\\[…]`` ou ``\\(…)``.
#: Un ``\$`` est un dollar **littéral** (« 40 dollars ») : il ne délimite rien, sinon
#: ``$\$40$`` se coupait en deux et les formules suivantes se décalaient.
_MATH_SPAN_RE = re.compile(
    r"(?<!\\)\$\$(?:\\.|[^$\\])*(?<!\\)\$\$"
    r"|(?<!\\)\$(?:\\.|[^$\\])*(?<!\\)\$"
    r"|\\\[.*?\\\]"
    r"|\\\(.*?\\\)",
    re.DOTALL,
)


def convert_bbcode(text: str) -> str:
    r"""Traduit les restes de BBCode d'AoPS en markdown.

    Seules les balises **appariées** sont converties ; une balise isolée est laissée
    telle quelle, car ``$[b]$`` est une notation mathématique et non du BBCode.

    >>> convert_bbcode("[b]Trouver[/b] [i]toutes[/i] les valeurs de $x$")
    '**Trouver** *toutes* les valeurs de $x$'
    >>> convert_bbcode("[list][*] un [*] deux[/list]")
    '\n\n- un\n- deux\n\n'
    """
    # Les balises sont retirées **hors des maths** : `$\\langle a\\rangle+[b]=98.6$`
    # contient un `[b]` qui est une notation, pas du gras. Les formules sont donc mises
    # de côté le temps du nettoyage, puis remises telles quelles.
    protected: list[str] = []

    def hide(match: re.Match) -> str:
        protected.append(match.group(0))
        return f"\x00{len(protected) - 1}\x00"

    text = _MATH_SPAN_RE.sub(hide, text)

    def list_replacer(match: re.Match) -> str:
        marker = "1." if match.group("kind") else "-"
        items = [item.strip() for item in re.split(r"\[\*\]", match.group("body")) if item.strip()]
        return "\n\n" + "\n".join(f"{marker} {item}" for item in items) + "\n\n"

    previous = None
    while previous != text:                       # les listes peuvent être imbriquées
        previous = text
        text = _BBCODE_LIST_RE.sub(list_replacer, text)

    for name, (open_md, close_md) in _BBCODE_PAIRED.items():
        pattern = re.compile(
            r"\[" + name + r"(?:=[^\]]*)?\](?P<body>.*?)\[/" + name + r"\]",
            re.IGNORECASE | re.DOTALL,
        )
        text = pattern.sub(lambda m, o=open_md, c=close_md, n=name: "" if n == "img"
                           else f"{o}{m.group('body')}{c}", text)

    text = _BBCODE_STANDALONE_RE.sub("\n", text)
    # `[*]` sans `[list]` autour (le forum l'ouvrait ailleurs) : c'est une puce
    text = re.sub(r"[ \t]*\[\*\][ \t]*", lambda m: "\n- " if m.start() else "- ", text)
    text = re.sub(r"\[/?(?:list|color|size|font|background|quote|center|spoiler)(?:=[^\]]*)?\]",
                  "", text, flags=re.IGNORECASE)
    # balises orphelines — un `[i]` sans `[/i]` vient d'un message de forum tronqué.
    # Les balises multi-lettres se retirent sans risque ; les balises d'une lettre sont
    # épargnées quand elles touchent un `$`, car `$[b]$` est une notation mathématique.
    text = re.sub(r"\[/?(?:tex|math|url|img|hr|br)(?:=[^\]]*)?\]", "", text, flags=re.IGNORECASE)
    text = re.sub(r"(?<!\$)\[/?(?:b|i|u|s)\](?!\$)", "", text, flags=re.IGNORECASE)
    for number, span in enumerate(protected):
        text = text.replace(f"\x00{number}\x00", span)
    return text


# --------------------------------------------------------------------------- #
# découpage des mathématiques : un analyseur, pas une expression régulière
# --------------------------------------------------------------------------- #
# Le corpus est du vrai LaTeX, abîmé par les conversions : on y trouve des `$$`
# à l'intérieur de `$…$`, des `$` isolés au milieu d'une formule, des `\left(`
# dont le `\right)` n'arrive que trois `$` plus loin, et des `$…$` imbriqués dans
# un `\text{…}`. Une expression régulière ne peut pas décider où s'arrête une
# formule dans ces cas ; un analyseur qui suit les accolades et l'équilibre des
# délimiteurs, si.

_LEFT_RE = re.compile(r"\\left(?![a-zA-Z])")
_RIGHT_RE = re.compile(r"\\right(?![a-zA-Z])")
_ENV_END_RE = re.compile(r"\\end\s*\{[a-zA-Z*]+\}")


def _delimiters_balanced(body: str) -> bool:
    r"""Vrai si les ``\left``/``\right`` et ``\begin``/``\end`` s'équilibrent."""
    if len(_LEFT_RE.findall(body)) != len(_RIGHT_RE.findall(body)):
        return False
    return len(_ENV_BEGIN_RE.findall(body)) == len(_ENV_END_RE.findall(body))


def _repair_lost_closers(text: str) -> str:
    r"""Rend son antislash à un ``]`` qui fermait un ``\[``.

    Le corpus écrit parfois ``\[ f(x) = 1 ]`` — le ``\`` du ``\]`` a disparu. Sans
    réparation, le ``\[`` cherche son ``\]`` beaucoup plus loin et avale la prose qui
    suit. Le ``]`` nu est reconnu fermeture quand le contenu qui le précède est
    équilibré (``\left``/``\right``, ``\begin``/``\end``, crochets et accolades).

    >>> _repair_lost_closers(chr(92) + "[ f(x) = 1 ] suite")
    '\\[ f(x) = 1 \\] suite'
    >>> _repair_lost_closers(chr(92) + "[ [0,1] " + chr(92) + "]")
    '\\[ [0,1] \\]'
    """
    slash = chr(92)
    opens = [m.start() for m in re.finditer(re.escape(slash + "["), text)]
    if not opens:
        return text
    closes = [m.start() for m in re.finditer(re.escape(slash + "]"), text)]
    events: list[tuple[int, int]] = [(position, 0) for position in opens]
    events += [(position, 1) for position in closes]
    events.sort()
    stack: list[int] = []
    for position, kind in events:
        if kind == 0:
            stack.append(position)
        elif stack:
            stack.pop()
    if not stack:
        return text

    repaired = text
    # du dernier au premier : une insertion décale ce qui suit
    for open_position in reversed(stack):
        found = False
        search_from = open_position + 2
        while True:
            candidate_position = repaired.find("]", search_from)
            if candidate_position == -1:
                break
            if candidate_position and repaired[candidate_position - 1] == slash:
                search_from = candidate_position + 1
                continue
            candidate = repaired[open_position + 2 : candidate_position]
            if (
                _delimiters_balanced(candidate)
                and candidate.count("[") == candidate.count("]")
                and candidate.count("{") == candidate.count("}")
                and candidate.strip()
            ):
                repaired = (
                    repaired[:candidate_position] + slash + "]" + repaired[candidate_position + 1 :]
                )
                found = True
                break
            search_from = candidate_position + 1
        if not found:
            # aucune fermeture crédible : l'ouvreur n'en était pas un, il disparaît
            # pour que la prose reste de la prose
            repaired = repaired[:open_position] + repaired[open_position + 2 :]

    parens = len(re.findall(re.escape(slash + "("), repaired))
    closing = len(re.findall(re.escape(slash + ")"), repaired))
    if parens > closing:
        repaired = repaired.replace(slash + "(", "", parens - closing)
    elif closing > parens:
        repaired = repaired.replace(slash + ")", "", closing - parens)
    return repaired


_PROSE_WORDS_RE = re.compile(r"[A-Za-z]{3,}(?:\s+[A-Za-z]{3,}){2,}")
#: Environnement multi-ligne : à composer en mode affichage.
_ALIGNMENT_RE = re.compile(
    r"\\begin\s*\{(?:align|align\*|aligned|alignat|gather|gather\*|eqnarray|eqnarray\*|split|multline)\}"
)


def _looks_like_prose(body: str) -> bool:
    r"""Vrai si le corps contient une phrase, signe qu'un ``$`` orphelin a avalé du texte.

    Seul le niveau d'accolade 0 est examiné : ``\text{for all}`` est du texte voulu,
    une phrase nue au milieu d'une formule ne l'est pas.

    >>> _looks_like_prose("term. Since the first factor contains")
    True
    >>> _looks_like_prose(r"x = \text{for all } n")
    False
    """
    depth = 0
    plain: list[str] = []
    index = 0
    while index < len(body):
        char = body[index]
        if char == chr(92):
            index += 2
            plain.append(" ")
            continue
        if char == "{":
            depth += 1
        elif char == "}":
            depth = max(0, depth - 1)
        if depth == 0:
            plain.append(char)
        index += 1
    return bool(_PROSE_WORDS_RE.search("".join(plain)))


def tokenize_math(text: str) -> list[tuple[str, str, bool]]:
    r"""Découpe un texte en ``("text", contenu, False)`` et ``("math", corps, display)``.

    Règles de l'analyseur, dans l'ordre où elles se présentent :

    * hors mathématiques : ``$$``, ``\[``, ``\(``, ``$`` ouvrent une formule, et un
      ``\begin{align}…`` autonome (sans délimiteur) ouvre un bloc d'affichage ;
    * à l'intérieur d'une formule, un ``$`` situé **entre accolades** appartient au
      contenu (c'est le cas de ``\text{si $x>0$}``, que KaTeX sait composer) ;
    * un ``$$`` rencontré dans une formule en ligne est un parasite de conversion :
      il est retiré, la formule continue ;
    * un ``$`` isolé qui laisserait un ``\left`` sans ``\right`` est un parasite lui
      aussi : la formule est prolongée jusqu'à ce que tout s'équilibre ;
    * une formule jamais refermée se termine à la fin du texte (et le nettoyage
      s'occupe des délimiteurs orphelins).

    >>> tokenize_math(r"a $x$ b")
    [('text', 'a ', False), ('math', 'x', False), ('text', ' b', False)]
    """
    text = _repair_lost_closers(text)
    tokens: list[tuple[str, str, bool]] = []
    plain_start = 0
    index = 0
    length = len(text)
    dropped: list[tuple[int, int]] = []      # délimiteurs orphelins, à ne pas afficher

    def slice_without(start: int, end: int) -> str:
        """Texte de ``[start, end[`` privé des délimiteurs abandonnés."""
        cursor = start
        pieces: list[str] = []
        for drop_start, drop_end in dropped:
            if drop_end <= start or drop_start >= end:
                continue
            if drop_start > cursor:
                pieces.append(text[cursor:drop_start])
            cursor = max(cursor, drop_end)
        pieces.append(text[cursor:end])
        return "".join(pieces)

    def emit_plain(upto: int) -> None:
        if upto > plain_start:
            tokens.append(("text", slice_without(plain_start, upto), False))

    while index < length:
        if text.startswith("\\$", index):     # un dollar échappé n'ouvre rien
            index += 2
            continue

        display: bool | None = None
        closer = ""
        opener_length = 0
        if text.startswith("$$", index):
            display, closer, opener_length = True, "$$", 2
        elif text.startswith("\\[", index):
            display, closer, opener_length = True, "\\]", 2
        elif text.startswith("\\(", index):
            display, closer, opener_length = False, "\\)", 2
        elif text[index] == "$":
            display, closer, opener_length = False, "$", 1
        elif text.startswith("\\begin{", index):
            span = _balanced_environment(text, index)
            if span and span[0] in MATH_ENVIRONMENTS:
                name, _open_end, close_start = span
                end = close_start + len("\\end{%s}" % name)
                emit_plain(index)
                tokens.append(("math", text[index:end], True))
                index = plain_start = end
                continue

        if display is None:
            index += 1
            continue

        # ---- rechercher le délimiteur de fermeture -------------------------
        cursor = index + opener_length
        depth = 0
        last_kept = cursor
        kept: list[str] = []
        closed = False

        while cursor < length:
            char = text[cursor]
            # le délimiteur est testé avant l'échappement : `\]` commence par `\`
            if depth == 0 and closer != "$" and text.startswith(closer, cursor):
                closed = True
                break
            if char == "\\":
                cursor += 2
                continue
            if char == "{":
                depth += 1
                cursor += 1
                continue
            if char == "}":
                depth = max(0, depth - 1)
                cursor += 1
                continue
            if depth == 0:
                if closer == "$" and char == "$":
                    if text.startswith("$$", cursor):
                        # `$$` parasite dans une formule en ligne : retiré
                        kept.append(text[last_kept:cursor])
                        cursor += 2
                        last_kept = cursor
                        continue
                    candidate = "".join(kept) + text[last_kept:cursor]
                    if _delimiters_balanced(candidate):
                        closed = True
                        break
                    # `$` parasite : la formule continue après l'avoir retiré
                    kept.append(text[last_kept:cursor])
                    cursor += 1
                    last_kept = cursor
                    continue
            cursor += 1

        body = "".join(kept) + text[last_kept : cursor if closed else length]

        # Un ouvreur dont le contenu ressemble à de la prose (paragraphes, formules
        # imbriquées, titre markdown, texte très long) n'était pas un délimiteur :
        # c'est un `$` orphelin du corpus. On l'abandonne et on repart juste après
        # lui, pour que les vraies formules qu'il contient soient rendues.
        if display and (r"\[" in body or r"\(" in body):
            dropped.append((index, index + opener_length))
            index += opener_length
            continue
        if not display and (
            r"\[" in body or r"\]" in body or r"\(" in body or r"\)" in body
            or "\n\n" in body or len(body) > 400 or _looks_like_prose(body)
            or _LITERAL_ESCAPE_RE.search(body)
            or (body.strip() and set(body.strip()) == {chr(92)})
            or (not closed and not re.search(r"[\\^_=<>]", body))
        ):
            dropped.append((index, index + opener_length))
            index += opener_length
            continue

        # un environnement d'alignement ne se compose pas en ligne (KaTeX le refuse) :
        # la formule devient un bloc d'affichage
        if not display and _ALIGNMENT_RE.search(body):
            display = True
        emit_plain(index)
        tokens.append(("math", body, bool(display)))
        index = cursor + (len(closer) if closed else 0)
        plain_start = index

    if length > plain_start:
        tokens.append(("text", slice_without(plain_start, length), False))
    return tokens


#: Commandes TeX rencontrées dans la *prose* des solutions importées (elles y sont
#: restées parce que l'énoncé était du LaTeX brut). Elles ne doivent jamais apparaître
#: telles quelles dans la page.
_PROSE_COMMANDS = {
    "textbf": ("**", "**"), "bf": ("**", "**"),
    "textit": ("*", "*"), "emph": ("*", "*"), "em": ("*", "*"),
    "texttt": ("`", "`"),
    "newline": ("\n", ""), "par": ("\n\n", ""), "\\": ("\n", ""),
    "smallskip": ("", ""), "medskip": ("", ""), "bigskip": ("", ""),
    "noindent": ("", ""), "indent": ("", ""),
}
_PROSE_COMMAND_RE = re.compile(
    r"\\(" + "|".join(re.escape(name) for name in _PROSE_COMMANDS if name != "\\") + r")(?![A-Za-z])"
)


#: Commandes de mise en page : dans la prose, elles n'ont aucun sens, elles disparaissent.
_PROSE_DROP_RE = re.compile(
    r"\\(?:vspace|hspace|vskip|hskip|vfil|hfil)\s*\{[^{}]*\}"
    r"|\\(?:sub)*section\*?\s*\{[^{}]*\}"
    r"|\\(?:eq)?ref\s*\{[^{}]*\}"
    r"|\\(?:label|tag|index)\s*\{[^{}]*\}"
    r"|\\(?:indent|noindent|hfill|vfill|smallskip|medskip|bigskip|displaystyle|limits"
    r"|allowbreak|newpage|clearpage|linebreak|pagebreak|break)\b"
    r"|\\(?:quad|qquad|thinspace|enspace|,|;|!|:)\s*"
)
#: Commandes de préambule (document LaTeX entier importé par erreur).
_DOCUMENT_COMMAND_RE = re.compile(
    r"\\(?:title|author|date|thanks|documentclass|usepackage|maketitle|tableofcontents"
    r"|newtheorem|pagestyle|thispagestyle|setlength)\*?"
    r"(?:\s*\{[^{}]*\})*(?:\s*\{[^{}]*\})?\s*"
)
#: Environnement de mise en page dont le ``\end`` est resté dans un autre fragment.
_UNPAIRED_ENV_RE = re.compile(
    r"\\(?:begin|end)\s*\{(?:itemize|enumerate|description|proof|verbatim|center|quote|abstract)\}"
)

#: Commandes de mise en forme à contenu : on garde le contenu, on jette l'enveloppe.
_PROSE_UNWRAP_RE = re.compile(
    r"\\(?:mbox|text|textrm|mathrm|mathbb|mathcal|mathbf|operatorname|emph)\s*\{([^{}]*)\}"
)


def restore_literal_escapes(text: str) -> str:
    r"""Rend leur sens aux séquences ``\n`` / ``\t`` restées littérales.

    L'import a laissé des « antislash + n » écrits en clair là où l'auteur avait mis un
    retour à la ligne. Traités comme des commandes, ils produisaient des formules
    absurdes (``. \n\n*``).

    >>> restore_literal_escapes("fin. " + chr(92) + "n" + chr(92) + "n * suite")
    'fin. \n\n * suite'
    """
    return re.sub(
        r"\\(?P<letter>[nrt])(?![a-z])",          # `\ne` reste `\ne`, `\nNext` devient une ligne
        lambda m: {"n": "\n", "r": "\n", "t": " "}[m.group("letter")],
        text,
    )


def strip_tex_plumbing(text: str) -> str:
    r"""Retire de la prose les commandes TeX qui n'ont pas été composées.

    Une phrase doit rester une phrase : ni ``\vspace{2pt}``, ni ``\mbox{a}``, ni
    ``\mathbb{Z}`` au milieu d'un texte français.

    >>> strip_tex_plumbing("Soit " + chr(92) + "vspace{2pt} " + chr(92) + "mbox{x} " + chr(92) + "ZZ")
    'Soit x Z'
    """
    out = text
    for name, replacement in MATH_ALIASES.items():
        out = re.sub(r"\\" + name + r"\s*\{\}", lambda _m, r=replacement: r, out)
        out = re.sub(r"\\" + name + r"(?![A-Za-z])", lambda _m, r=replacement: r, out)
    out = restore_literal_escapes(out)
    out = _PROSE_DROP_RE.sub(" ", out)
    out = _CUT_HEADER_RE.sub(" ", out)
    out = _DOCUMENT_COMMAND_RE.sub(" ", out)
    out = _UNPAIRED_ENV_RE.sub(" ", out)
    previous = None
    while previous != out:                        # imbrications simples
        previous = out
        out = _PROSE_UNWRAP_RE.sub(lambda m: m.group(1), out)
    return re.sub(r"[ \t]{2,}", " ", out)


#: Atomes d'une expression mathématique « nue » dans la prose : une commande avec ses
#: arguments, un groupe entre accolades, un nombre, une lettre isolée, un symbole.
_MATH_ATOM = (
    r"\\[A-Za-z]+\*?(?:[ \t]*\{[^{}]*\})*"       # \frac{1}{2}, \sqrt{2}, \geq
    r"|\\[{}|.,;:!%]"                              # \{ \} \| (délimiteurs échappés)
    r"|\\(?![A-Za-z])"                              # un antislash resté seul
    r"|\{[^{}]*\}"
    r"|[0-9]+(?:\.[0-9]+)?|\.\d+"
    r"|[A-Za-z]"
    r"|[+\-=<>^_/|(){}\[\],.!]"
)
_MATH_ATOM_RE = re.compile(_MATH_ATOM)


#: Commandes qui ne font pas une formule : les enrober serait pire que les laisser.
_NON_MATH_COMMANDS = frozenset(
    {"item", "hline", "label", "tag", "ref", "quad", "qquad", "hfill", "vspace", "hspace",
     "par", "newline", "linebreak", "pagebreak", "noindent", "indent", "begin", "end"}
)


def _is_wrappable(body: str) -> bool:
    r"""Une expression nue mérite-t-elle d'être recomposée en formule ?

    Non si elle est trop courte, sans commande, tronquée (accolades ou délimiteurs
    déséquilibrés), si elle contient un retour à la ligne de tableau, un environnement
    ou seulement des commandes de mise en page : dans ces cas, le mieux est de laisser
    la phrase telle quelle.

    >>> _is_wrappable(chr(92) + "frac{1}{2} = " + chr(92) + "frac{2}{4}")
    True
    >>> _is_wrappable("72{\\" + chr(92) + "}")
    False
    >>> _is_wrappable(chr(92) + "item")
    False
    """
    if len(body) < 4 or "$" in body or "{}" in body:       # argument vide : formule tronquée
        return False
    commands = re.findall(r"\\([A-Za-z]+)", body)
    if not commands:
        return False
    if all(name in _NON_MATH_COMMANDS for name in commands):
        return False
    if any(name in {"begin", "end"} for name in commands):
        return False
    if chr(92) * 2 in body:                     # séparateur de ligne de tableau
        return False
    if body.count("{") != body.count("}"):
        return False
    if body.count("(") != body.count(")"):
        return False
    if _LEFT_RE.search(body) is not None and len(_LEFT_RE.findall(body)) != len(_RIGHT_RE.findall(body)):
        return False
    return True


def wrap_prose_math(text: str) -> str:
    r"""Entoure de ``$…$`` les formules écrites nues dans la prose.

    Le corpus contient des phrases du type « on obtient \frac{1}{2} = \frac{2}{4} » :
    les délimiteurs ont été perdus à l'import et la formule s'affichait en clair. Elle
    est recomposée dès qu'elle contient une commande TeX. La détection s'arrête sur un
    mot (deux lettres consécutives), un passage à la ligne ou tout texte inattendu,
    de sorte que la phrase autour n'est jamais absorbée.

    >>> wrap_prose_math("on obtient " + chr(92) + "frac{1}{2} = " + chr(92) + "frac{2}{4} ici")
    'on obtient $\\frac{1}{2} = \\frac{2}{4}$ ici'
    >>> wrap_prose_math("Let " + chr(92) + "{a_{n}" + chr(92) + "}_{n " + chr(92) + "geq 1} be a sequence")
    'Let $\\{a_{n}\\}_{n \\geq 1}$ be a sequence'
    >>> wrap_prose_math("la suite est monotone")
    'la suite est monotone'
    """
    # Les formules déjà délimitées sont mises de côté : sans cela, `**$a' \ne 0$**`
    # voyait son `\ne` recomposé et la phrase se déchirait (`$a' $\ne 0$$.**`).
    spans: list[str] = []

    def hide(match: re.Match) -> str:
        spans.append(match.group(0))
        return f"{_MATH_HOLE}{len(spans) - 1}{_MATH_HOLE}"

    text = _MATH_SPAN_RE.sub(hide, text)

    atoms = []
    for match in _MATH_ATOM_RE.finditer(text):
        atom = match.group(0)
        if len(atom) == 1 and atom.isalpha():
            # une lettre collée à un mot (« t » de « obtient ») n'appartient pas à une
            # formule : seules les lettres isolées sont retenues
            before = text[match.start() - 1] if match.start() else " "
            after = text[match.end()] if match.end() < len(text) else " "
            if before.isalpha() or after.isalpha():
                continue
        atoms.append((match.start(), match.end(), atom))
    runs: list[tuple[int, int]] = []
    current: list[int] | None = None
    previous_end: int | None = None
    previous_letter = False

    for start, end, atom in atoms:
        letter = len(atom) == 1 and atom.isalpha()
        if current is not None:
            gap = text[previous_end:start] if previous_end is not None else ""
            contiguous = gap == "" and not gap.strip()
            broken = (
                "\n" in gap and previous_end is not None
                or (gap and gap.strip())
                or (contiguous and previous_letter and letter)   # deux lettres collées
            )
            if broken:
                runs.append((current[0], current[1]))
                current = None
        if current is None:
            current = [start, end]
        else:
            current[1] = end
        previous_end = end
        previous_letter = letter
    if current is not None:
        runs.append((current[0], current[1]))

    for start, end in reversed(runs):          # de la fin vers le début : les offsets tiennent
        body = text[start:end].strip()
        if _MATH_HOLE in body:          # déjà une formule mise de côté : ne pas l'enrober
            continue
        trailing = ""
        while body and body[-1] in ",.;:!?_^":  # opérateur orphelin : il reste dans la phrase
            trailing = body[-1] + trailing
            body = body[:-1].rstrip()
        if not _is_wrappable(body):
            continue
        text = text[:start] + f"${body}$" + trailing + text[end:]
        end = start + len(body) + 2 + len(trailing)
        # les runs précédents restent valides : on ne touche qu'à leur fin éventuelle
        del end
    for number, span in enumerate(spans):
        text = text.replace(f"{_MATH_HOLE}{number}{_MATH_HOLE}", span)
    return text


def _prose_to_markdown(text: str) -> str:
    r"""Traduit les commandes TeX de mise en forme d'un passage de prose.

    ``\textbf{Solution.}`` devient ``**Solution.**``, ``\newline`` une fin de ligne.
    Ces commandes viennent des solutions importées, écrites en LaTeX brut ; elles ne
    doivent jamais apparaître telles quelles dans la page.

    >>> _prose_to_markdown(chr(92) + "textbf{Solution.} Then " + chr(92) + "newline x")
    '**Solution.** Then \n x'
    """
    text = text.replace("\\\\", "\n")
    out: list[str] = []
    index = 0
    while index < len(text):
        match = _PROSE_COMMAND_RE.match(text, index)
        if not match:
            out.append(text[index])
            index += 1
            continue
        name = match.group(1)
        open_md, close_md = _PROSE_COMMANDS[name]
        cursor = match.end()
        if cursor < len(text) and text[cursor] == "{":
            depth = 0
            for scanner in range(cursor, len(text)):
                if text[scanner] == "{":
                    depth += 1
                elif text[scanner] == "}":
                    depth -= 1
                    if depth == 0:
                        out.append(open_md + text[cursor + 1 : scanner] + close_md)
                        index = scanner + 1
                        break
            else:
                out.append(open_md)
                index = cursor
        else:
            out.append(open_md)
            index = cursor
    return "".join(out)


#: Formule reconstituée dans la prose (voir :func:`wrap_prose_math`).
_PROSE_MATH_RE = re.compile(r"\$([^$]+)\$")

#: Une formule écrite à la TeX : ``\(x\)`` (en ligne) ou ``\\[x\\]`` (affichage).
_PAREN_MATH_RE = re.compile(r"\\\((.*?)\\\)", re.DOTALL)

#: Marqueur temporaire d'une formule mise de côté pendant la mise en forme d'une ligne.
_MATH_HOLE = "\x01"

#: Marqueur temporaire d'un dollar littéral (``\$320``), remis en entité à la fin.
_DOLLAR_SIGN = "\x02"

#: Échappements TeX qui traînent dans la prose : chacun vaut son caractère. Ils sont
#: remplacés **après** l'échappement HTML de la ligne, sinon l'entité du dollar serait
#: elle-même échappée (``&amp;#36;``).
_PROSE_ESCAPES: tuple[tuple[str, str], ...] = (
    (_DOLLAR_SIGN, "&#36;"), (r"\%", "%"), (r"\&", "&"), (r"\#", "#"),
    (r"\_", "_"), (r"\{", "{"), (r"\}", "}"),
    (r"\,", " "), (r"\;", " "), (r"\:", " "), (r"\!", ""),
    (r"\quad", " "), (r"\qquad", " "),
)


def _plain_escapes(html: str) -> str:
    """Remplace les derniers échappements TeX d'une ligne par leur caractère."""
    for needle, replacement in _PROSE_ESCAPES:
        html = html.replace(needle, replacement)
    return html


def _close_stray_parentheses(text: str) -> str:
    r"""Ramène les ``\(…\)`` à des ``$…$``, en refermant ceux restés ouverts.

    Le corpus mêle les deux notations. Quand la fermeture s'est perdue, la formule est
    refermée en fin de ligne : elle est courte, et elle **reste dans sa phrase** au
    lieu d'y laisser traîner du LaTeX brut.

    >>> _close_stray_parentheses(chr(92) + "(x+1) puis " + chr(92) + "(x-1)")
    '$x+1$ puis $x-1$'
    >>> _close_stray_parentheses("le coût est " + chr(92) + "(156 fois 0,78, soit 121,68.")
    'le coût est $156 fois 0,78, soit 121,68.$'
    """
    while text.count(r"\(") > text.count(r"\)"):
        text = text.rstrip() + " " + r"\)"
    return _PAREN_MATH_RE.sub(lambda match: f"${match.group(1)}$", text)


def _inline_math(span: str) -> str:
    """Une formule d'une ligne de prose → son élément HTML, nettoyé et échappé.

    >>> _inline_math("$" + chr(36) + "\\left\\{a\\right\\}" + chr(36))
    '<span class="math-inline">$\\\\left\\\\{a\\\\right\\\\}$</span>'
    """
    inner = span.strip()
    for opener, closer in (("$$", "$$"), (r"\[", r"\]"), (r"\(", r"\)"), ("$", "$")):
        if inner.startswith(opener) and inner.endswith(closer) and len(inner) > len(opener):
            inner = inner[len(opener) : len(inner) - len(closer)]
            break
    body = _escape(sanitize_math(inner.strip(), display=False))
    if not body.strip():
        return ""
    return f'<span class="math-inline">${body}$</span>'


def _render_prose_line(line: str) -> str:
    r"""Une ligne de prose → HTML, formules nues recomposées comprises.

    C'est ici que la phrase reste **une** phrase : le texte est mis en forme, mais
    chaque formule retrouvée devient un vrai élément mathématique composé par KaTeX.

    >>> _render_prose_line("Soit " + chr(92) + "frac{1}{2} le total")
    'Soit <span class="math-inline">$\\frac{1}{2}$</span> le total'
    """
    parts: list[str] = []          # HTML des formules, remis en place à la fin

    def slot(fragment: str) -> str:
        parts.append(fragment)
        return f"{_MATH_HOLE}{len(parts) - 1}{_MATH_HOLE}"

    # 1. les formules déjà délimitées sortent du nettoyage : `\left\{` y perdrait son
    #    antislash, et un `\ne` serait repris pour une formule nue.
    line = _MATH_SPAN_RE.sub(lambda match: slot(_inline_math(match.group(0))), line)
    # 2. la prose : commandes de mise en forme, formules nues, échappements
    prose = _close_stray_parentheses(wrap_prose_math(strip_tex_plumbing(line)))
    prose = prose.replace(r"\$", _DOLLAR_SIGN)   # `\$320` : un dollar littéral

    # 3. les formules reconnues dans la prose deviennent, elles aussi, des éléments
    def stash(match: re.Match) -> str:
        return slot(_inline_math("$" + match.group(1) + "$"))

    html = _inline(_escape(_prose_to_markdown(_PROSE_MATH_RE.sub(stash, prose))))
    html = _plain_escapes(html)
    for _pass in range(len(parts) + 1):     # une formule peut en contenir une autre
        remaining = False
        for index, fragment in enumerate(parts):
            marker = f"{_MATH_HOLE}{index}{_MATH_HOLE}"
            if marker in html:
                html = html.replace(marker, fragment)
                remaining = True
        if not remaining:
            break
    return html


def render_rich(text: str | None) -> str:
    r"""Render Markdown-flavoured TeX to safe HTML.

    Inline math **stays inside its sentence**: a formula is part of the prose, not a
    block of its own. Display math (``$$…$$``, ``\[…\]``, a bare ``\begin{align}…``)
    does break the paragraph, as it should. Lines starting with ``-``/``*``/``1.``
    become a list.

    >>> render_rich(r"Find all $f$ such that $$f(x)=x$$ holds.")
    '<p>Find all <span class="math-inline">$f$</span> such that</p><div class="math-block">$$f(x)=x$$</div><p>holds.</p>'
    >>> render_rich("- one\n- two")
    '<ul><li>one</li><li>two</li></ul>'
    """
    if not text:
        return ""
    text = repair_control_chars(text)
    # `\n` / `\t` écrits en toutes lettres redeviennent de vrais caractères **avant** le
    # découpage : sinon les paragraphes du corpus ne sont jamais reconnus.
    text = restore_literal_escapes(text)
    text = convert_bbcode(text)
    text = convert_text_environments(text)
    text = _rename_math_environments(text)
    tokens = tokenize_math(text)

    blocks: list[str] = []
    para: list[str] = []            # lignes déjà rendues du paragraphe courant
    raw: list[str] = []             # contenu brut en attente (texte et `$formules$`)
    items: list[str] = []
    ordered = False                 # is the list being built an <ol>?

    def flush_paragraph() -> None:
        """Ferme le paragraphe en cours (nettoyage des espaces)."""
        nonlocal para
        if para:
            body = "".join(para)
            body = re.sub(r"(?:\s*<br>\s*)+$", "", body)   # no dangling line break
            body = re.sub(r"^(?:\s*<br>\s*)+", "", body)
            body = re.sub(r"[ \t]{2,}", " ", body).strip()
            if body:
                blocks.append(f"<p>{body}</p>")
        para = []

    def flush_list() -> None:
        nonlocal items, ordered
        if items:
            tag = "ol" if ordered else "ul"
            blocks.append(f"<{tag}>" + "".join(f"<li>{item}</li>" for item in items) + f"</{tag}>")
        items = []
        ordered = False

    def append_line(piece: str) -> None:
        if not para:
            para.append("")
        para[-1] += piece

    def flush_text() -> None:
        """Rend le texte accumulé : c'est **ici** que la phrase reste entière.

        Les fragments arrivent séparés (l'analyseur a isolé les formules) : les recoller
        avant la mise en forme évite qu'un `**…$x$…**` se casse en deux paragraphes.
        """
        nonlocal raw, ordered
        if not raw:
            return
        content = "".join(raw)
        raw = []
        for index, line in enumerate(content.split("\n")):
            if not line.strip():            # blank line ends the paragraph
                flush_list()
                flush_paragraph()
                continue

            item = _LIST_ITEM_RE.match(line)
            if item:
                flush_paragraph()
                if not items:
                    ordered = item.group("marker")[0].isdigit()
                items.append(_render_prose_line(item.group("body").strip()))
                continue

            if items:
                flush_list()
            if index > 0 and para and not para[-1].endswith("</span>"):
                # keep the author's line break, but never right next to inline math,
                # where the formula belongs to the sentence and <br> would cut it
                append_line("<br>")
            append_line(_render_prose_line(line))

    for kind, content, display in tokens:
        if kind == "math":
            body = sanitize_math(content.strip(), display=display)
            if not body.strip():
                continue                # un `$` orphelin du corpus ne produit rien
            if display:                     # display math: its own block
                flush_text()                # le texte d'abord : il peut ouvrir une liste
                flush_list()
                flush_paragraph()
                blocks.append(f'<div class="math-block">$${_escape(body)}$$</div>')
            else:                           # inline math: part of the sentence
                raw.append(f"${body}$")
            continue
        raw.append(content)

    flush_text()
    flush_list()
    flush_paragraph()
    rendered = "".join(blocks)
    # Statements that are only math still deserve a paragraph wrapper for spacing.
    return rendered or f"<p>{_escape(text)}</p>"


_TEX_COMMANDS_RE = re.compile(r"\\[a-zA-Z]+\*?")
_PLAIN_STRIP_RE = re.compile(r"[${}\\]")


def to_plain_text(text: str | None, *, max_length: int | None = None) -> str:
    """Best-effort plain-text version of a TeX fragment (for search / previews / prompts)."""
    if not text:
        return ""
    plain = _TEX_COMMANDS_RE.sub(" ", repair_control_chars(text))
    plain = _PLAIN_STRIP_RE.sub(" ", plain)
    plain = re.sub(r"[ \t]{2,}", " ", plain)
    plain = re.sub(r"\s*\n\s*", " ", plain).strip()
    if max_length and len(plain) > max_length:
        plain = plain[: max_length - 1].rstrip() + "…"
    return plain
