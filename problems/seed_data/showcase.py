"""
Curated showcase corpus: problems whose official solutions are *verified*.

Every ``official_tex`` below is machine-checked by ``scripts/verify_seed.py``
(exact identities, exhaustive search over a finite range, or Monte-Carlo over the
configuration), and the two 2001 problems use the official IMO solutions.

Why a curated corpus at all?
----------------------------
The public ``fixtures/all.json`` from otis-web ships *dummy* data (faker PUIDs and
no solutions), so it can demonstrate the importer but not the AI gate.  This
module provides the ground truth that makes the gate meaningful out of the box.

To extend: append a dict with the same keys and re-run
``python manage.py seed_showcase`` — the command is idempotent.
"""

from __future__ import annotations

PROBLEMS: list[dict] = [
    # ------------------------------------------------------------------ #
    # ALGEBRA
    # ------------------------------------------------------------------ #
    {
        "puid": "IMO 2019/1",
        "legacy_puid": "",
        "category": "algebra",
        "difficulty_track": "olympiad",
        "source_url": "https://artofproblemsolving.com/wiki/index.php/2019_IMO_Problems/Problem_1",
        "statement_tex": r"""Soit $\mathbb{Z}$ l'ensemble des entiers. Déterminer toutes les fonctions $f : \mathbb{Z} \to \mathbb{Z}$ telles que, pour tous entiers $a$ et $b$,
\[ f(2a) + 2f(b) = f\big(f(a+b)\big). \]""",
        "answer_tex": r"$f \equiv 0$, or $f(x) = 2x + c$ for some integer $c$",
        "hints": [
            r"Commencez par les valeurs particulières : posez $(a,b) = (0,0)$, puis $(0,b)$, puis $(a,0)$. L'une de ces substitutions relie $f(f(x))$ à $f(x)$.",
            r"Avec $c = f(0)$ vous devez obtenir $f(f(b)) = 2f(b) + c$ puis $f(2a) = 2f(a) - c$. Réinjectez ensuite cette relation « presque linéaire » dans l'équation d'origine.",
            r"Après substitution, tout se ramène à $f(a+b) = f(a) + f(b) - c$ : la fonction $g(x) := f(x) - c$ est donc additive sur $\mathbb{Z}$.",
            r"Une application additive sur $\mathbb{Z}$ est linéaire : $g(x) = kx$ avec $k = g(1)$, donc $f(x) = kx + c$. Reportez-la dans $f(f(b)) = 2f(b) + c$ et identifiez les coefficients de $b$ : vous obtenez $k^2 = 2k$. Vérifiez *les deux* valeurs de $k$ qui subsistent dans l'équation d'origine.",
        ],
        "attribution": "Own write-up; cross-checked against the IMO 2019 official solution",
        "official_tex": r"""Let $c = f(0)$.

**Step 1: exploit the special values.** Putting $(a,b) = (0,b)$ into the equation gives $f(0) + 2f(b) = f(f(b))$, that is
\[ f(f(b)) = 2f(b) + c \qquad \text{for all } b \in \mathbb{Z}. \tag{1} \]
Putting $(a,b) = (a,0)$ gives $f(2a) + 2c = f(f(a))$, and using (1) on the right-hand side,
\[ f(2a) = 2f(a) - c. \tag{2} \]

**Step 2: the equation is almost additive.** Substitute (2) into the original relation for arbitrary $a,b$, keeping (1) for the right-hand side:
\[ 2f(a) - c + 2f(b) = f\big(f(a+b)\big) = 2f(a+b) + c, \]
hence
\[ f(a+b) = f(a) + f(b) - c \qquad \text{for all } a,b \in \mathbb{Z}. \tag{3} \]

**Step 3: additivity.** Let $g(x) = f(x) - c$. Then (3) says $g(a+b) = g(a)+g(b)$: the map $g : \mathbb{Z} \to \mathbb{Z}$ is additive. An additive map on $\mathbb{Z}$ is linear: if $k = g(1)$ then $g(n) = kn$ for $n \ge 0$ by induction, while $g(0) = 0$ and $g(-n) = -g(n)$ follow from additivity. Hence
\[ f(x) = kx + c, \qquad k = f(1) - c \in \mathbb{Z}. \]

**Step 4: determine $k$ and $c$.** Substitute $f(x) = kx+c$ into (1):
\[ k(kb+c) + c = 2(kb + c) + c \quad\Longleftrightarrow\quad k^2\, b + kc = 2k\, b + 2c \qquad \text{for all } b \in \mathbb{Z}. \]
Comparing coefficients of $b$ gives $k^2 = 2k$, hence $k \in \{\,0,2\,\}$; comparing constants gives $kc = 2c$.

* If $k = 0$, then $kc = 2c$ forces $c = 0$, so $f \equiv 0$.
* If $k = 2$, the constant condition is automatic, so every $c \in \mathbb{Z}$ is allowed and $f(x) = 2x + c$.

**Step 5: verify both families.** For $f \equiv 0$ both sides vanish, since $f(f(a+b)) = f(0) = 0$. For $f(x) = 2x+c$,
\[ f(2a) + 2f(b) = (4a + c) + (4b + 2c) = 4(a+b) + 3c \]
and, since $f(a+b) = 2(a+b)+c$,
\[ f\big(f(a+b)\big) = 2\big(2(a+b)+c\big) + c = 4(a+b) + 3c, \]
so the equation holds.

Hence the solutions are exactly $f \equiv 0$ and $f(x) = 2x+c$ with $c \in \mathbb{Z}$. $\blacksquare$""",
    },
    {
        "puid": "IMO 2014/1",
        "legacy_puid": "",
        "category": "algebra",
        "difficulty_track": "olympiad",
        "source_url": "https://artofproblemsolving.com/wiki/index.php/2014_IMO_Problems/Problem_1",
        "statement_tex": r"""Soit $a_0 < a_1 < a_2 < \cdots$ une suite infinie d'entiers strictement positifs. Prouver qu'il existe un unique entier $n \ge 1$ tel que
\[ a_n < \frac{a_0 + a_1 + \cdots + a_n}{n} \le a_{n+1}. \]""",
        "answer_tex": r"existence and uniqueness of such an $n$",
        "hints": [
            r"Les deux inégalités portent sur les mêmes objets : la somme partielle $S_n = a_0 + \cdots + a_n$ et le terme $a_n$ (ou $a_{n+1}$). Réécrivez-les comme des conditions sur la seule quantité $S_n - n a_n$.",
            r"$a_n < S_n/n$ s'écrit exactement $S_n - n a_n > 0$. Et comme $S_{n+1} = S_n + a_{n+1}$, la quantité $S_{n+1} - (n+1)a_{n+1}$ vaut $S_n - n a_{n+1}$ : servez-vous en pour transformer l'inégalité de droite.",
            r"Avec $t_n = S_n - n a_n$, la condition devient donc $t_n > 0 \ge t_{n+1}$. Calculez alors $t_{n+1} - t_n$ et souvenez-vous que la suite $(a_n)$ est strictement croissante.",
            r"$(t_n)$ est strictement décroissante, part de $t_1 = a_0 > 0$ et tend vers $-\infty$ (ses pas valent au moins $k$ en valeur absolue). Une suite strictement décroissante qui part d'une valeur positive et file vers $-\infty$ traverse zéro une seule fois : ce passage est l'indice $n$ cherché.",
        ],
        "attribution": "Own write-up",
        "official_tex": r"""Let $S_n = a_0 + a_1 + \cdots + a_n$ and define
\[ t_n = S_n - n\,a_n \qquad (n \ge 1). \]

**Reformulating the requirement.** Since $n \ge 1$,
\[ a_n < \frac{S_n}{n} \iff S_n - n\,a_n > 0 \iff t_n > 0. \]
Also $t_{n+1} = S_{n+1} - (n+1)a_{n+1} = S_n + a_{n+1} - (n+1)a_{n+1} = S_n - n\,a_{n+1}$, so
\[ \frac{S_n}{n} \le a_{n+1} \iff S_n - n\,a_{n+1} \le 0 \iff t_{n+1} \le 0. \]
Thus the required property of $n$ is precisely
\[ t_n > 0 \quad \text{and} \quad t_{n+1} \le 0. \tag{$\ast$} \]

**The sequence $(t_n)$ is strictly decreasing.** For every $n \ge 1$,
\[ t_{n+1} - t_n = \big(S_n - n\,a_{n+1}\big) - \big(S_n - n\,a_n\big) = n\,(a_n - a_{n+1}) < 0, \]
because $a_n < a_{n+1}$.

**It starts positive.** $t_1 = (a_0 + a_1) - a_1 = a_0 \ge 1 > 0$, as $a_0$ is a positive integer.

**It tends to $-\infty$.** As $(a_n)$ is strictly increasing, $a_{k+1} - a_k \ge 1$, hence $t_{k+1} - t_k = -k(a_{k+1}-a_k) \le -k$ for every $k \ge 1$. Summing from $k = 2$ to $n-1$,
\[ t_n \le t_2 - \sum_{k=2}^{n-1} k = t_2 - \frac{n(n-1)}{2} + 1 \longrightarrow -\infty \qquad (n \to \infty). \]

**Conclusion.** Since $(t_n)$ is strictly decreasing, the set $\{\,n \ge 1 : t_n > 0\,\}$ is an initial segment $\{1, 2, \dots, n_0\}$: if $t_n > 0$ and $m < n$, then $t_m > t_n > 0$. This set is finite because $t_n \to -\infty$, and it is non-empty because $t_1 > 0$. Therefore there is exactly one index $n_0 \ge 1$ with $t_{n_0} > 0$ and $t_{n_0+1} \le 0$, which by $(\ast)$ is the unique $n$ satisfying the required double inequality. $\blacksquare$""",
    },
    {
        "puid": "Drill 2018/A1",
        "legacy_puid": "",
        "category": "algebra",
        "difficulty_track": "foundation",
        "source_url": "",
        "statement_tex": r"""Soient $a, b > 0$ des réels tels que $a + b = 1$. Prouver que
\[ \left(1 + \frac{1}{a}\right)\left(1 + \frac{1}{b}\right) \ge 9, \]
avec égalité si et seulement si $a = b = \tfrac12$.""",
        "answer_tex": r"the minimum is $9$, attained exactly at $a = b = \tfrac12$",
        "hints": [
            r"Mettez chaque facteur au même dénominateur : $1 + \frac1a = \frac{a+1}{a}$.",
            r"Développez le numérateur en utilisant $a + b = 1$ : le produit devient $1 + \frac{2}{ab}$.",
            r"Il ne reste qu'une estimation d'une ligne sur $ab$ : par AM–GM, $ab \le \left(\frac{a+b}{2}\right)^2 = \frac14$.",
        ],
        "attribution": "Classical warm-up",
        "official_tex": r"""Write both factors with a common denominator and expand:
\[ \left(1+\frac1a\right)\left(1+\frac1b\right) = \frac{(a+1)(b+1)}{ab} = \frac{ab + (a+b) + 1}{ab} = \frac{ab + 2}{ab} = 1 + \frac{2}{ab}, \]
where $a + b = 1$ was used in the third equality.

By AM–GM applied to $a$ and $b$,
\[ \sqrt{ab} \le \frac{a+b}{2} = \frac12 \quad\Longrightarrow\quad ab \le \frac14 \quad\Longrightarrow\quad \frac{1}{ab} \ge 4. \]
Therefore
\[ \left(1+\frac1a\right)\left(1+\frac1b\right) = 1 + \frac{2}{ab} \ge 1 + 8 = 9. \]
Equality in AM–GM holds exactly when $a = b$; combined with $a + b = 1$ this means $a = b = \frac12$, and indeed $(1+2)(1+2) = 9$ there. $\blacksquare$

*Alternative finish:* the same estimate can be read as $\frac1a + \frac1b \ge \frac{4}{a+b} = 4$ (AM–HM), giving $1 + \frac1a + \frac1b + \frac1{ab} = 1 + \frac2{ab} \ge 9$ again.""",
    },
    # ------------------------------------------------------------------ #
    # NUMBER THEORY
    # ------------------------------------------------------------------ #
    {
        "puid": "IMO 2005/4",
        "legacy_puid": "",
        "category": "number_theory",
        "difficulty_track": "olympiad",
        "source_url": "https://artofproblemsolving.com/wiki/index.php/2005_IMO_Problems/Problem_4",
        "statement_tex": r"""Déterminer tous les entiers strictement positifs qui sont premiers avec tous les termes de la suite
\[ a_n = 2^n + 3^n + 6^n - 1, \qquad n = 1, 2, 3, \ldots \]""",
        "answer_tex": r"only $1$",
        "hints": [
            r"Calculez les premiers termes : $a_1 = 10$, $a_2 = 48$, $a_3 = 250$. Quels nombres premiers apparaissent ? Conjecturez, puis prouvez que *tout* nombre premier divise au moins un terme.",
            r"Pourquoi cela suffit-il ? Tout entier $m \ge 2$ admet un diviseur premier $p$ ; si $p \mid a_{n_0}$, alors $\gcd(m, a_{n_0}) > 1$ et $m$ n'est pas premier avec tous les termes. La réponse ne peut donc être que $1$.",
            r"Le petit théorème de Fermat donne $x^{p-1} \equiv 1 \pmod p$ pour $p \nmid x$. Choisissez l'exposant pour que $2^n, 3^n, 6^n$ deviennent les inverses $2^{-1}, 3^{-1}, 6^{-1}$ modulo $p$.",
            r"L'identité à viser est $\tfrac12 + \tfrac13 + \tfrac16 - 1 = 0$, ce qui rend $n = p - 2$ naturel pour $p \ge 5$. Traitez directement $p = 2$ et $p = 3$ avant de l'utiliser.",
        ],
        "attribution": "Own write-up; standard solution",
        "official_tex": r"""We claim that **every prime divides at least one term** of the sequence; then the answer is $1$.

* $p = 2$: for every $n \ge 1$, the terms $2^n$ and $6^n$ are even and $3^n$ is odd, so $a_n = \text{even} + \text{odd} + \text{even} - 1$ is even. Hence $2 \mid a_n$ for all $n \ge 1$.
* $p = 3$: $a_2 = 4 + 9 + 36 - 1 = 48 = 3 \cdot 16$, so $3 \mid a_2$.
* $p \ge 5$: put $n = p - 2 \ge 3$. Since $p$ does not divide $2$, $3$ or $6$, Fermat's little theorem gives
\[ 2^{p-1} \equiv 3^{p-1} \equiv 6^{p-1} \equiv 1 \pmod p, \]
i.e. $2^{p-2} \equiv 2^{-1}$, $3^{p-2} \equiv 3^{-1}$ and $6^{p-2} \equiv 6^{-1} \pmod p$. Therefore
\[ a_{p-2} \equiv 2^{-1} + 3^{-1} + 6^{-1} - 1 \equiv \frac{3 + 2 + 1 - 6}{6} = 0 \pmod p, \]
where multiplying by the invertible $6$ is legitimate because $p \ge 5$. Hence $p \mid a_{p-2}$.

**Conclusion.** Let $m$ be a positive integer that is relatively prime to every term $a_n$. If $m \ge 2$, let $p$ be any prime divisor of $m$; by the above, $p \mid a_{n_0}$ for some $n_0 \ge 1$, so $\gcd(m, a_{n_0}) \ge p > 1$ — a contradiction. Hence $m = 1$. Conversely, $1$ is relatively prime to every integer. The answer is $\boxed{1}$. $\blacksquare$""",
        "demo_submissions": [
            {
                "status": "REJECTED",
                "text": (
                    "Par le petit théorème de Fermat, pour tout premier p on a 2^(p-1) = 3^(p-1) = 1 mod p. "
                    "Donc en prenant n = p - 1 on obtient a_n = 1 + 1 + 1 - 1 = 2 mod p. Cela ne s'annule pas. "
                    "Je pense que la réponse est 1 car les termes croissent vite et ne partagent jamais de facteur."
                ),
                "feedback": (
                    "Refusé : l'exposant n = p - 1 donne a_n ≡ 2 (mod p), ce qui ne prouve aucune divisibilité ; "
                    "l'affirmation « ne partagent jamais de facteur » est fausse — les motifs de divisibilité "
                    "doivent être démontrés, pas supposés. L'étape clé est de rendre les exposants ÉGAUX à -1 "
                    "modulo p (inverses), et non à +1."
                ),
            }
        ],
    },
    {
        "puid": "IMO 1988/6",
        "legacy_puid": "",
        "category": "number_theory",
        "difficulty_track": "hard",
        "source_url": "https://artofproblemsolving.com/wiki/index.php/1988_IMO_Problems/Problem_6",
        "statement_tex": r"""Soient $a$ et $b$ des entiers strictement positifs tels que $ab + 1$ divise $a^2 + b^2$. Montrer que
\[ \frac{a^2 + b^2}{ab + 1} \]
est le carré d'un entier.""",
        "answer_tex": r"the quotient is always a perfect square",
        "hints": [
            r"Appelez $k$ le quotient et lisez $a^2 + b^2 = k(ab+1)$ comme une *équation du second degré en $a$* : $x^2 - kbx + (b^2 - k) = 0$.",
            r"Une racine est $a$, donc par Vieta l'autre racine vaut $a' = kb - a \in \mathbb{Z}$, avec $aa' = b^2 - k$. En reportant, $(a', b)$ est une autre solution de la même équation avec le *même* quotient $k$.",
            r"Supposons que $k$ ne soit pas un carré parfait et prenons un contre-exemple avec $a \ge b$ et $a + b$ minimal. Montrez dans l'ordre : $a > b$ (si $a = b$ alors $k = \frac{2a^2}{a^2+1} < 2$, donc $k = 1$) ; $a' \ne 0$ (sinon $k = b^2$) ; $a' > 0$ ; puis $a' < b$.",
            r"Alors $(a', b)$ fournit un contre-exemple plus petit, ce qui contredit la minimalité : c'est la classique **descente de Vieta** (échange de racines). Bornes utiles : $k < \frac{a}{b} + \frac{b}{a} \le a + b$ exclut $a' < 0$, et $a' \ge b$ forcerait $ab \le aa' = b^2 - k < b^2$, c'est-à-dire $a < b$.",
        ],
        "attribution": "Standard Vieta-jumping solution",
        "official_tex": r"""Let
\[ k = \frac{a^2+b^2}{ab+1} \in \mathbb{Z}_{>0}. \]

**The Vieta jump.** The defining relation is equivalent to
\[ a^2 - k\,b\,a + (b^2 - k) = 0, \]
a quadratic equation in the variable $a$ with one root $a$; let $a'$ be its other root. By Vieta,
\[ a + a' = kb, \qquad a\,a' = b^2 - k, \]
so $a' = kb - a \in \mathbb{Z}$. Substituting $x = a'$ into the quadratic shows that $(a', b)$ satisfies
\[ a'^2 + b^2 = k\,(a'b + 1), \qquad\text{that is}\qquad k = \frac{a'^2+b^2}{a'b+1}. \]

**Assume for contradiction that $k$ is not a perfect square.** Choose a pair $(a,b)$ of positive integers with $a \ge b$, $k = (a^2+b^2)/(ab+1)$ not a perfect square, such that $a + b$ is minimal.

* **$a > b$.** If $a = b$, then $k = \frac{2a^2}{a^2+1} < 2$, so $k = 1 = 1^2$, a perfect square. Hence $a > b \ge 1$.

* **$a' \ne 0$.** Otherwise $aa' = b^2 - k = 0$, i.e. $k = b^2$, again a perfect square.

* **$a' > 0$.** Suppose $a' \le -1$. Then $aa' \le -a$, so $b^2 - k \le -a$, i.e. $k \ge a + b^2$. On the other hand,
\[ k = \frac{a^2+b^2}{ab+1} < \frac{a^2+b^2}{ab} = \frac{a}{b} + \frac{b}{a} \le a + b \le a + b^2, \]
where $\frac ab \le a$ and $\frac ba \le 1 \le b$ both use $a \ge b \ge 1$. Contradiction.

* **$a' < b$.** If $a' \ge b$, then $ab \le aa' = b^2 - k < b^2$, which forces $a < b$ — contradicting $a > b$.

Therefore $0 < a' < b$, and $(a', b)$ is a pair of positive integers with the same non-square quotient $k$ and
\[ a' + b < a + b, \]
contradicting the minimality of $a + b$ (reorder the pair as $(b, a')$ so that the first coordinate is the larger one).

Hence no counterexample exists: $k = \frac{a^2+b^2}{ab+1}$ is always a perfect square. $\blacksquare$

*Remark.* This argument — replacing one root of an associated quadratic by the other — is the prototype of **Vieta jumping**, the standard technique for this family of problems.""",
    },
    {
        "puid": "Drill 2020/N1",
        "legacy_puid": "",
        "category": "number_theory",
        "difficulty_track": "foundation",
        "source_url": "",
        "statement_tex": r"""Prouver que pour tout entier strictement positif $n$ il existe un entier strictement positif $m$ tel que $n \mid m$ et dont l'écriture décimale n'utilise que les chiffres $0$ et $1$.

Par exemple, pour $n = 7$ on peut prendre $m = 1001 = 7 \cdot 143$.""",
        "answer_tex": r"take a difference of two repunits",
        "hints": [
            r"Considérez les repunits $R_k = \underbrace{11\ldots1}_{k \text{ uns}}$ pour $k = 1, 2, \ldots, n+1$ et regardez-les modulo $n$.",
            r"Il y a $n+1$ nombres mais seulement $n$ restes possibles : deux d'entre eux sont donc congrus modulo $n$, et leur différence est un multiple de $n$.",
            r"Calculez cette différence : soustraire deux repunits de longueurs différentes ne demande jamais de retenue, donc $R_i - R_j = \underbrace{11\cdots1}_{i-j}\underbrace{00\cdots0}_{j}$ n'utilise que les chiffres $1$ et $0$.",
        ],
        "attribution": "Classical drill",
        "official_tex": r"""Let
\[ R_k = \underbrace{11\cdots 1}_{k \text{ ones}} \qquad (k \ge 1). \]
Consider the $n+1$ integers $R_1, R_2, \ldots, R_{n+1}$ modulo $n$. As there are only $n$ possible residues, the pigeonhole principle provides indices $i > j \ge 1$ with
\[ R_i \equiv R_j \pmod n, \qquad\text{hence}\qquad n \mid R_i - R_j. \]
Now
\[ R_i - R_j = \underbrace{11\cdots 1}_{i-j}\underbrace{00\cdots 0}_{j}, \]
a positive integer (because $i > j$) whose decimal digits are only $1$ and $0$: subtracting $R_j$ from $R_i$ needs no borrowing since $R_i$ ends with $j$ ones. Setting $m = R_i - R_j$ gives the required multiple of $n$. $\blacksquare$

*Variant.* The same pigeonhole argument applied to $1, 11, 111, \ldots$ modulo $n$ is the standard proof that every prime $p \ne 2,5$ divides some repunit.""",
    },
    # ------------------------------------------------------------------ #
    # COMBINATORICS
    # ------------------------------------------------------------------ #
    {
        "puid": "IMO 2014/5",
        "legacy_puid": "",
        "category": "combinatorics",
        "difficulty_track": "hard",
        "source_url": "https://artofproblemsolving.com/wiki/index.php/2014_IMO_Problems/Problem_5",
        "statement_tex": r"""Pour tout entier strictement positif $n$, la Banque du Cap émet des pièces de valeur $\frac1n$. Étant donné une collection finie de telles pièces (les valeurs n'étant pas nécessairement distinctes) dont la valeur totale ne dépasse pas $99 + \frac12$, prouver qu'il est possible de partager cette collection en $100$ groupes au plus, chacun de valeur totale au plus $1$.""",
        "answer_tex": r"at most $100$ groups suffice",
        "hints": [
            r"Prouvez l'énoncé plus précis : $k$ groupes suffisent lorsque la valeur totale ne dépasse pas $k - \frac12$ ; le problème est le cas $k = 100$ puisque $99 + \frac12 = 100 - \frac12$.",
            r"Deux normalisations anodines : deux pièces de valeur $\frac1{2m}$ se fusionnent en une seule pièce $\frac1m$ (la valeur totale ne change pas), et $2m+1$ pièces de valeur $\frac1{2m+1}$ forment déjà un groupe parfait de valeur exactement $1$, qu'on peut mettre de côté.",
            r"Après normalisation, construisez $k$ boîtes $B_0, \ldots, B_{k-1}$ : placez dans $B_0$ l'unique pièce éventuellement restante de valeur $\frac12$, et dans $B_m$ toutes les pièces de valeur $\frac1{2m+1}$ (au plus $2m$ d'entre elles) ainsi que l'éventuelle pièce de valeur $\frac1{2m+2}$. Vérifiez que $\frac{2m}{2m+1} + \frac1{2m+2} < 1$.",
            r"Chaque pièce restante vaut au plus $\frac1{2k+1}$. Déposez-les gloutonnement dans les boîtes sans jamais dépasser $1$. Si une pièce de valeur $\frac1n$ ($n \ge 2k+1$) ne rentrait pas, chaque boîte dépasserait $1 - \frac1{2k+1}$, donc les boîtes contiendraient déjà plus de $k - \frac{k}{2k+1} > k - \frac12$ — alors que la valeur totale des pièces est au plus $k - \frac12$. Contradiction.",
        ],
        "attribution": "Own write-up of the standard construction",
        "official_tex": r"""We prove the stronger statement:

> For every integer $k \ge 1$, a finite collection of coins of values $\frac1n$ ($n \ge 1$) and total value at most $k - \frac12$ can be split into at most $k$ groups, each of total value at most $1$.

Applying it with $k = 100$ gives the problem, since $99 + \frac12 = 100 - \frac12$.

**Step 1: normalisation.** Repeat the following two operations as long as they apply.

*(a)* If two coins of value $\frac1{2m}$ are present, replace them by a single coin of value $\frac1m$ ($\frac1{2m} + \frac1{2m} = \frac1m$, so the total value is unchanged). This is harmless: given any splitting of the new collection, replacing the merged coin by the original two inside its group restores a legal splitting of the old collection with the same number of groups.

*(b)* If $2m + 1$ coins of value $\frac1{2m+1}$ are present, put them into a single group (their total value is exactly $1$) and remove them. The remaining coins have total value at most $(k - \frac12) - 1 = (k-1) - \frac12$, so by induction on $k$ they fit into at most $k - 1$ further groups. (The case $m = 0$ says that a coin of value $1$ is a group by itself.)

When we stop, no two coins of value $\frac1{2m}$ coexist, and fewer than $2m+1$ coins of value $\frac1{2m+1}$ coexist.

**Step 2: the boxes.** Form boxes $B_0, B_1, \ldots, B_{k-1}$.
* $B_0$ receives all coins of value $\frac12$; by (a) there is at most one, so its value is $\le \frac12 < 1$.
* For $1 \le m \le k-1$, put into $B_m$ all coins of value $\frac1{2m+1}$ — at most $2m$ of them, since (b) no longer applies — and at most one coin of value $\frac1{2m+2}$, since two such coins would have been merged by (a). Hence
\[ \operatorname{val}(B_m) \le \frac{2m}{2m+1} + \frac{1}{2m+2} < 1, \]
because $(2m)(2m+2) + (2m+1) < (2m+1)(2m+2)$ simplifies to $6m + 1 < 6m + 2$.

Every coin of value $\ge \frac1{2k+1}$ is now inside a box: the coins of value $\frac1{2m+1}$ with $m \le k-1$ and those of value $\frac1{2m+2}$ with $m + 1 \le k$ are exactly the coins whose denominator is at most $2k$.

**Step 3: the leftover pile.** Let the remaining coins (each of value $\le \frac1{2k+1}$) form a pile of total value $P > 0$. Toss them into the boxes one at a time, each time choosing any box whose value would remain $\le 1$; stop when the pile is empty. We prove this never gets stuck.

Suppose a pile coin of value $\frac1n$, where $n \ge 2k+1$, cannot be placed. Then every box has value $> 1 - \frac1n \ge 1 - \frac1{2k+1}$, so the boxes' total value $W$ satisfies
\[ W > k\left(1 - \frac{1}{2k+1}\right) = k - \frac{k}{2k+1}. \tag{1} \]
On the other hand $T \le k - \frac12$ is the total value of the whole collection and $T = W + P$ with $P > 0$, so
\[ W = T - P < k - \frac12. \tag{2} \]
Since $2k < 2k+1$ implies $\frac{k}{2k+1} < \frac12$, we have $k - \frac{k}{2k+1} > k - \frac12$. Combining with (1) and (2),
\[ W > k - \frac{k}{2k+1} > k - \frac12 > W, \]
a contradiction. Hence every leftover coin is placed and no box ever exceeds $1$.

**Conclusion.** After undoing the mergers from step 1(a), the collection is split into the $k$ boxes plus the groups formed in step 1(b): at most $k$ groups, each of total value at most $1$. With $k = 100$ this is the claim. $\blacksquare$""",
    },
    {
        "puid": "IMO 2001/3",
        "legacy_puid": "",
        "category": "combinatorics",
        "difficulty_track": "hard",
        "source_url": "https://artofproblemsolving.com/wiki/index.php/2001_IMO_Problems/Problem_3",
        "statement_tex": r"""Vingt-et-une filles et vingt-et-un garçons ont participé à une compétition mathématique. Il s'est avéré que

1. chaque candidat a résolu au plus six problèmes, et
2. pour chaque couple formé d'une fille et d'un garçon, il existe au moins un problème que tous les deux ont résolu.

Prouver qu'il existe un problème résolu par au moins trois filles et au moins trois garçons.""",
        "answer_tex": r"some problem was solved by $\ge 3$ girls and $\ge 3$ boys",
        "hints": [
            r"Comptez les incidences de couples : si $g_p$ et $b_p$ sont les nombres de filles et de garçons ayant résolu le problème $p$, la condition 2 donne $\sum_p g_p b_p \ge 21 \cdot 21 = 441$ (chacun des 441 couples fille–garçon partage au moins un problème).",
            r"Raisonnez par l'absurde en supposant que tout problème vérifie $g_p \le 2$ ou $b_p \le 2$. Séparez les problèmes en $P_+ = \{p : g_p \ge 3\}$ (où donc $b_p \le 2$) et $P_- = \{p : g_p \le 2\}$.",
            r"Fixez une fille. Les 21 garçons sont tous couverts par les six problèmes au plus qu'elle a résolus, donc l'un de ses problèmes est résolu par au moins $\lceil 21/6 \rceil = 4$ garçons — et par hypothèse ce problème appartient à $P_-$. Chaque fille résout donc un problème de $P_-$, c'est-à-dire $\sum_{p \in P_-} g_p \ge 21$, et par conséquent $\sum_{p \in P_+} g_p \le 6 \cdot 21 - 21 = 5 \cdot 21$. Symétriquement, chaque garçon résout un problème de $P_+$, d'où $\sum_{p \in P_-} b_p \le 5 \cdot 21$.",
            r"Découpez maintenant le double comptage $\sum_p g_p b_p$ : sur $P_+$ utilisez $b_p \le 2$, sur $P_-$ utilisez $g_p \le 2$. Les deux bornes ci-dessus donnent au plus $2 \cdot 105 + 2 \cdot 105 = 420 < 441$, en contradiction avec le premier indice.",
        ],
        "attribution": "IMO 2001 official solutions 1 and 2",
        "official_tex": r"""Let $G$, $B$ be the sets of girls and boys (both of size $21$), let $P$ be the set of problems, let $P(x)$ be the set of problems solved by contestant $x$, and let $G(p)$, $B(p)$ be the sets of girls and boys who solved problem $p$. In this notation the hypotheses are
\[ |P(g)| \le 6, \quad |P(b)| \le 6, \qquad P(g) \cap P(b) \ne \emptyset \qquad (g \in G,\ b \in B). \]

**Solution 1 (double counting).** Assume for contradiction that
\[ \text{for every } p \in P: \quad |G(p)| \le 2 \ \text{ or }\ |B(p)| \le 2. \tag{$\star$} \]
Count the set of triples
\[ T = \{\,(p,g,b) : p \in P(g) \cap P(b)\,\}. \]
Since every one of the $21^2 = 441$ girl–boy pairs shares at least one problem,
\[ |T| = \sum_{g \in G}\sum_{b \in B} |P(g) \cap P(b)| \ge 441. \tag{1} \]
On the other hand, counting by problems,
\[ |T| = \sum_{p \in P} |G(p)| \cdot |B(p)|. \tag{2} \]
Moreover, exchanging the order of summation,
\[ \sum_{p \in P} |G(p)| = \sum_{g \in G} |P(g)| \le 6 \cdot 21 = 126, \qquad \sum_{p \in P} |B(p)| \le 126. \tag{3} \]

Set $P_+ = \{\,p : |G(p)| \ge 3\,\}$ and $P_- = \{\,p : |G(p)| \le 2\,\}$, so that $P$ is the disjoint union of $P_+$ and $P_-$.

*Claim.* $\sum_{p \in P_-} |G(p)| \ge 21$ and $\sum_{p \in P_+} |B(p)| \ge 21$.

*Proof of the claim.* Fix a girl $g$. Every boy shares a problem with $g$, and those common problems all belong to $P(g)$, which has at most six elements. The problems of $P(g)$ that are solved by at most two boys cover at most $2|P(g)| \le 12$ boys in total, which does not account for all $21$ boys; hence some $p \in P(g)$ is solved by at least $3$ boys, and by $(\star)$ it satisfies $|G(p)| \le 2$, i.e. $p \in P_-$. So every girl solves a problem of $P_-$, giving $\sum_{p \in P_-} |G(p)| \ge |G| = 21$. Exchanging the roles of girls and boys gives $\sum_{p \in P_+} |B(p)| \ge 21$. $\square$

By (3) and the claim,
\[ \sum_{p \in P_+} |G(p)| \le 126 - 21 = 105, \qquad \sum_{p \in P_-} |B(p)| \le 126 - 21 = 105. \tag{4} \]
Finally, by $(\star)$ each $p \in P_+$ has $|B(p)| \le 2$, and each $p \in P_-$ has $|G(p)| \le 2$, so
\[ |T| = \sum_{p \in P_+} |G(p)||B(p)| + \sum_{p \in P_-} |G(p)||B(p)| \le 2\sum_{p \in P_+} |G(p)| + 2\sum_{p \in P_-} |B(p)| \le 2\cdot105 + 2\cdot105 = 420, \]
using (4). But $420 < 441$ contradicts (1). Hence $(\star)$ is false: some problem was solved by at least three girls and at least three boys.

**Solution 2 (colouring a $21 \times 21$ board).** Assume $(\star)$ again and colour a problem *red* if $|G(p)| \le 2$ and *black* otherwise (then $|B(p)| \le 2$ for black problems). Take the $21 \times 21$ board whose rows are the girls and whose columns are the boys. For each cell $(g,b)$ choose one problem $p \in P(g) \cap P(b)$, which exists by hypothesis 2, and give the cell the colour of $p$.

One colour occurs on at least $\lceil 441/2 \rceil = 221$ cells, so some row or some column contains at least $\lceil 221/21 \rceil = 11$ cells of the same colour.

Suppose row $g$ contains $11$ black cells, indexed by $11$ distinct boys. A black problem $p$ can be chosen in at most $|B(p)| \le 2$ cells of this row (the cells in which $p$ is chosen correspond to distinct boys who solved $p$), so the $11$ cells involve at least $\lceil 11/2 \rceil = 6$ distinct problems, all of them solved by $g$. By hypothesis 1, girl $g$ solved exactly those problems — at most six in total — and each of them is solved by at most two boys, so at most $6 \cdot 2 = 12$ boys share a problem with $g$. This contradicts hypothesis 2, which requires all $21$ boys to share a problem with her. The case of a column with $11$ red cells is symmetric. Hence $(\star)$ fails. $\blacksquare$""",
    },
    # ------------------------------------------------------------------ #
    # GEOMETRY
    # ------------------------------------------------------------------ #
    {
        "puid": "IMO 2006/1",
        "legacy_puid": "",
        "category": "geometry",
        "difficulty_track": "olympiad",
        "source_url": "https://artofproblemsolving.com/wiki/index.php/2006_IMO_Problems/Problem_1",
        "statement_tex": r"""Soit $ABC$ un triangle et $I$ le centre de son cercle inscrit. Un point $P$ intérieur au triangle vérifie
\[ \angle PBA + \angle PCA = \angle PBC + \angle PCB. \]
Montrer que $AP \ge AI$, avec égalité si et seulement si $P = I$.""",
        "answer_tex": r"$AP \ge AI$, with equality iff $P = I$",
        "hints": [
            r"Additionnez les deux membres de l'hypothèse et utilisez $\angle PBA + \angle PBC = \angle ABC$, $\angle PCA + \angle PCB = \angle ACB$. Cela détermine $\angle PBC + \angle PCB$, donc $\angle BPC$.",
            r"Vous obtenez $\angle BPC = 90^\circ + \frac{A}{2}$. Rappelez-vous l'identité classique du centre du cercle inscrit $\angle BIC = 90^\circ + \frac{A}{2}$ : puisque $P$ et $I$ sont du même côté de $BC$, les quatre points $B, C, I, P$ sont cocycliques.",
            r"Soit $M$ le centre de ce cercle. Montrez que $A$, $I$, $M$ sont alignés : dans le triangle isocèle $BMC$ on a $\angle MBC = \frac A2$, donc $\angle MBI = \frac A2 + \frac B2$ ; combiné à $MI = MB$ et $\angle BIA = 90^\circ + \frac C2$, cela donne $\angle MIA = 180^\circ$.",
            r"Comme $I$ se trouve entre $A$ et $M$, la distance de $A$ au cercle $(BIC)$ vaut $AM - MI = AI$ et son point le plus proche est $I$. Tout point $P$ du cercle — en particulier le $P$ du problème — vérifie donc $AP \ge AI$, avec égalité seulement pour $P = I$.",
        ],
        "attribution": "Own write-up; standard solution",
        "official_tex": r"""Write $A = \angle BAC$, $B = \angle ABC$, $C = \angle BCA$.

**Step 1: the condition characterises a circle.** Adding the two sides of the hypothesis and using $\angle PBA + \angle PBC = B$ and $\angle PCA + \angle PCB = C$,
\[ 2\big(\angle PBC + \angle PCB\big) = B + C = 180^\circ - A, \qquad\text{so}\qquad \angle PBC + \angle PCB = \frac{180^\circ - A}{2}. \]
Hence
\[ \angle BPC = 180^\circ - \frac{180^\circ - A}{2} = 90^\circ + \frac{A}{2}. \]
The incentre satisfies the standard identity $\angle BIC = 90^\circ + \frac{A}{2}$, and $P$, $I$ are on the same side of the line $BC$. Therefore $B$, $C$, $I$, $P$ are concyclic: $P$ lies on the circle $\Gamma$ through $B$, $C$, $I$.

**Step 2: $A$, $I$, $M$ are collinear, where $M$ is the centre of $\Gamma$.** Since $\angle BIC = 90^\circ + \frac A2 > 90^\circ$, the point $I$ lies on the minor arc $BC$ of $\Gamma$, so $M$ is on the opposite side of the line $BC$ from $I$. In the isosceles triangle $BMC$ (with $MB = MC$) the central angle satisfies $\angle BMC = 2\big(180^\circ - \angle BIC\big) = 180^\circ - A$; hence
\[ \angle MBC = \angle MCB = \frac{180^\circ - (180^\circ - A)}{2} = \frac{A}{2}. \]
Because $M$ and $I$ lie on opposite sides of $BC$, while $BI$ bisects $\angle B$, we get
\[ \angle MBI = \angle MBC + \angle CBI = \frac{A}{2} + \frac{B}{2}. \]
The triangle $MBI$ is isosceles ($MI = MB = $ radius), so $\angle MIB = \angle MBI = \frac{A+B}{2} = 90^\circ - \frac{C}{2}$. Using the standard incenter identity $\angle BIA = 90^\circ + \frac{C}{2}$,
\[ \angle MIA = \angle MIB + \angle BIA = \left(90^\circ - \frac{C}{2}\right) + \left(90^\circ + \frac{C}{2}\right) = 180^\circ, \]
so $M$, $I$, $A$ are collinear; since $M$ and $A$ are on opposite sides of $BC$, the point $I$ lies strictly between $M$ and $A$.

**Step 3: $AP \ge AI$.** Let $R_\Gamma = MI$ be the radius of $\Gamma$. As $I$ lies on the segment $AM$,
\[ AM = AI + IM = AI + R_\Gamma > R_\Gamma, \]
so $A$ lies strictly outside $\Gamma$. For a point outside a circle, the distance to the circle is (distance to the centre) minus (radius), and it is attained at the point of the circle lying on the segment joining the point to the centre — here that point is $I$. Hence
\[ \min_{X \in \Gamma} AX = AM - R_\Gamma = AI. \]
Since $P \in \Gamma$ by Step 1,
\[ AP \ge AI, \]
with equality if and only if $P$ is that closest point, i.e. $P = I$.

Finally, $P = I$ does satisfy the hypothesis, because $\angle IBA + \angle ICA = \frac B2 + \frac C2 = \angle IBC + \angle ICB$, so the equality case $P = I$ is genuine. $\blacksquare$""",
    },
    {
        "puid": "IMO 2001/1",
        "legacy_puid": "",
        "category": "geometry",
        "difficulty_track": "hard",
        "source_url": "https://artofproblemsolving.com/wiki/index.php/2001_IMO_Problems/Problem_1",
        "statement_tex": r"""Soit $ABC$ un triangle acutangle de centre du cercle circonscrit $O$. Soit $P$ le pied de la hauteur issue de $A$ sur $BC$. Supposons que
\[ \angle BCA \ge \angle ABC + 30^\circ. \]
Prouver que $\angle CAB + \angle COP < 90^\circ$.""",
        "answer_tex": r"$\angle CAB + \angle COP < 90^\circ$",
        "hints": [
            r"Posez $\alpha = \angle CAB$, $\beta = \angle ABC$, $\gamma = \angle BCA$ et soit $R$ le rayon du cercle circonscrit. Il suffit de prouver $OP > PC$ : calculez l'angle $\angle PCO$ pour comprendre pourquoi.",
            r"$OB = OC = R$ et $\angle BOC = 2\alpha$ est l'angle au centre, donc $\angle PCO = \angle BCO = 90^\circ - \alpha$. Si $OP > PC$, alors dans le triangle $COP$ le côté $OP$ est opposé à $\angle PCO$ et $PC$ est opposé à $\angle COP$, donc $\angle PCO > \angle COP$, c'est-à-dire $\alpha + \angle COP < 90^\circ$.",
            r"Calculez maintenant une différence de longueurs : par la loi des sinus étendue $AB = 2R\sin\gamma$ et $AC = 2R\sin\beta$ ; comme $AP \perp BC$, $BP = AB\cos\beta$ et $PC = AC\cos\gamma$. Par conséquent $BP - PC = 2R\sin(\gamma - \beta)$, et $\gamma - \beta \ge 30^\circ$ avec $\gamma < 90^\circ$ donne $BP - PC \ge R$.",
            r"Terminez par l'inégalité triangulaire dans $OBP$ : $R + OP = OB + OP > BP \ge R + PC$, d'où $OP > PC$.",
        ],
        "attribution": "IMO 2001 official solution 2",
        "official_tex": r"""Write $\alpha = \angle CAB$, $\beta = \angle ABC$, $\gamma = \angle BCA$, let $R$ be the circumradius and put $\delta = \angle COP$.

**It suffices to prove $OP > PC$.** Since $OB = OC = R$, the triangle $BOC$ is isosceles and the central angle is $\angle BOC = 2\alpha$ (it subtends the chord $BC$), whence
\[ \angle PCO = \angle BCO = \frac{180^\circ - 2\alpha}{2} = 90^\circ - \alpha. \]
If $OP > PC$, then in triangle $COP$ the larger side $OP$ is opposite the larger angle, so
\[ \angle PCO > \angle COP = \delta, \qquad\text{i.e.}\qquad 90^\circ - \alpha > \delta, \]
which is exactly $\alpha + \delta < 90^\circ$.

**Proving $OP > PC$.** The extended law of sines gives $AB = 2R\sin\gamma$ and $AC = 2R\sin\beta$. Since $AP \perp BC$, the triangles $ABP$ and $ACP$ are right-angled at $P$, so
\[ BP = AB\cos\angle ABP = AB\cos\beta, \qquad PC = AC\cos\angle ACP = AC\cos\gamma . \]
(Here $\angle ABP = \beta$ and $\angle ACP = \gamma$ because $P$ lies on the segment $BC$, which holds as $ABC$ is acute.) Hence
\[ BP - PC = 2R\big(\sin\gamma\cos\beta - \sin\beta\cos\gamma\big) = 2R\sin(\gamma - \beta). \]
By hypothesis $\gamma - \beta \ge 30^\circ$, and since the triangle is acute, $\gamma < 90^\circ$, so $30^\circ \le \gamma - \beta < 90^\circ$. On this interval the sine is increasing, so
\[ BP - PC = 2R\sin(\gamma-\beta) \ge 2R\sin 30^\circ = R. \]
Finally, apply the triangle inequality in triangle $OBP$, whose side $OB$ has length $R$:
\[ R + OP = OB + OP > BP \ge R + PC, \qquad\text{hence}\qquad OP > PC . \]
Together with the first part this gives $\angle CAB + \angle COP = \alpha + \delta < 90^\circ$, as required. $\blacksquare$""",
    },
]

# --------------------------------------------------------------------------- #
# demo history
# --------------------------------------------------------------------------- #
# The `demo_submissions` keys above are replayed by `manage.py seed_showcase`
# for the DEMO_MODE guest account so that both the rejected-attempt and the
# unlocked states are visible immediately.  Two problems additionally receive a
# full unlock record so the unlocked UI can be inspected without grading
# anything by hand.
UNLOCKED_IN_DEMO = {"Drill 2018/A1"}

DEMO_PASSED_ATTEMPTS: dict[str, list[dict]] = {
    "Drill 2018/A1": [
        {
            "status": "REJECTED",
            "text": (
                "Par AM-GM sur les deux facteurs, (1 + 1/a)(1 + 1/b) >= 2*sqrt((1 + 1/a)(1 + 1/b)) — "
                "circulaire. Comme a + b = 1, on sait que ab <= 1/4, donc 1/(ab) >= 4 et le produit vaut "
                "au moins 9. Je n'ai pas vérifié le cas d'égalité mais la borne semble correcte."
            ),
            "feedback": (
                "Refusé : l'estimation ab <= 1/4 est correcte, mais la copie ne démontre jamais l'identité "
                "(1+1/a)(1+1/b) = 1 + 2/(ab) qui relie les deux, donc le dernier pas « le produit vaut au "
                "moins 9 » n'est pas justifié ; le cas d'égalité manque aussi. "
                "Commencez par réduire le produit en une seule fraction, puis appliquez AM-GM."
            ),
        },
        {
            "status": "PASSED",
            "text": (
                "Avec a + b = 1, on réduit chaque facteur au même dénominateur : "
            "(1 + 1/a)(1 + 1/b) = (a+1)(b+1)/(ab) = (ab + a + b + 1)/(ab) = (ab + 2)/(ab) = 1 + 2/(ab). "
            "By AM-GM, ab <= ((a+b)/2)^2 = 1/4, hence 1/(ab) >= 4 and therefore "
            "1 + 2/(ab) >= 1 + 8 = 9. Equality in AM-GM requires a = b, which with a + b = 1 means a = b = 1/2, "
            "and there indeed (1+2)(1+2) = 9."
            ),
            "feedback": (
                "Accepté : la réduction à 1 + 2/(ab) est correcte et l'étape AM-GM ab <= 1/4 est appliquée avec "
                "le cas d'égalité correctement identifié."
            ),
        },
    ],
}
