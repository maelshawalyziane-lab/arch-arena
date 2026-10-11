"""Small helpers shared by the test modules (no external factory dependency)."""

from __future__ import annotations

from django.contrib.auth.models import User

from problems.models import Category, DifficultyTrack, Hint, Problem, Solution

OFFICIAL_TEX = r"""Let $k = \frac{a^2+b^2}{ab+1}$.

Assume for contradiction that $k$ is not a perfect square and choose a counterexample with
$a \ge b$ and $a+b$ minimal. The relation $a^2 + b^2 = k(ab+1)$ is a quadratic equation in $a$,
so by Vieta the other root $a' = kb - a$ is an integer and $(a', b)$ is a solution with the same
quotient $k$. One shows in order that $a > b$, that $a' \ne 0$, that $a' > 0$ and that $a' < b$,
contradicting minimality. Hence $k$ is always a perfect square. $\blacksquare$"""

# A write-up that the offline plausibility grader accepts (it mirrors the ground truth).
STRONG_SUBMISSION = r"""Assume for contradiction that $k = \frac{a^2+b^2}{ab+1}$ is not a perfect square and choose a
counterexample with $a \ge b$ minimal in $a + b$.

Step 1: view $a^2 - kba + (b^2-k) = 0$ as a quadratic in $a$. By Vieta the other root is
$a' = kb - a$, an integer, and $(a',b)$ is another solution with the same quotient $k$; also
$a a' = b^2 - k$.

Step 2: assume $k$ is not a square. Then $a > b$, because $a = b$ gives $k = \frac{2a^2}{a^2+1} < 2$.
Also $a' \ne 0$, since $aa' = 0$ would give $k = b^2$, a square.

Step 3: suppose $a' < 0$. Then $aa' \le -a$, so $k \ge a + b^2$, while the bound
$k < \frac{a}{b} + \frac{b}{a} \le a + b$ contradicts it. Hence $a' > 0$.

Step 4: if $a' \ge b$ then $ab \le aa' = b^2 - k < b^2$, forcing $a < b$, contradiction. So
$0 < a' < b$ and $(b, a')$ is a smaller counterexample, contradicting the minimal choice.

Therefore the quotient is always a square. QED"""

WEAK_SUBMISSION = "It is well known that the quotient is a square by Vieta jumping. Routine."


def make_user(username: str = "student", password: str = "pw-12345-strong") -> User:
    return User.objects.create_user(username=username, password=password)


def make_problem(
    puid: str = "TEST 2026/1",
    *,
    category: str = Category.NUMBER_THEORY,
    track: str = DifficultyTrack.OLYMPIAD,
    hints: int = 3,
    with_solution: bool = True,
    statement: str = r"Let $a,b$ be positive integers with $(ab+1) \mid (a^2+b^2)$. Prove that the quotient is a square.",
) -> Problem:
    problem = Problem.objects.create(
        puid=puid,
        statement_tex=statement,
        category=category,
        difficulty_track=track,
        answer_tex=r"a perfect square",
    )
    for index in range(1, hints + 1):
        Hint.objects.create(
            problem=problem,
            order_index=index,
            content_md=rf"Tier {index} hint with math $x_{index} \le {index}$ and a nudge toward Vieta.",
            keywords="vieta jumping",
        )
    if with_solution:
        Solution.objects.create(problem=problem, official_tex=OFFICIAL_TEX, attribution="unit test")
    return problem
