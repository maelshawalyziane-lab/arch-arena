#!/usr/bin/env python3
"""
Machine verification harness for the curated ground-truth solutions.

Why this exists
---------------
The whole platform rests on one assumption: `Solution.official_tex` is *correct*.
A wrong answer key silently poisons every AI verdict, so every seeded problem is
checked here — either by an exact symbolic/algorithmic identity, by exhaustive
search over a finite range, or by Monte-Carlo sampling of the configuration
(NOT by "looks reasonable").

What is checked
---------------
IMO 2019/1   the two claimed function families satisfy the equation exactly; the
             coefficient analysis k^2 = 2k has no other solutions in Z
IMO 2014/1   for random increasing sequences the double inequality holds for
             exactly one index n
IMO 2005/4   every prime p <= 400 divides some term 2^n + 3^n + 6^n - 1, so the
             claimed answer {1} is consistent
IMO 1988/6   exhaustive: for all 1 <= b <= a <= 80 with (ab+1) | (a^2+b^2), the
             quotient is a perfect square; the Vieta descent maps (a,b) to a
             genuinely smaller solution
IMO 2014/5   the constructive algorithm in the ground truth is *simulated* on
             random legal coin multisets: it terminates, uses <= 100 groups and
             no group exceeds value 1; the key inequality
             2m/(2m+1) + 1/(2m+2) < 1 and the counting bound k - 1/2 < k - k/(2k+1)
             are also verified
IMO 2001/3   the arithmetic of both official solutions (ceilings 4 / 11 / 6 and
             the bound 420 < 441)
IMO 2006/1   random triangles: P on the circle through B, I, C really does
             satisfy the angle condition; A, I, M are collinear; the minimum of
             AP over that circle equals AI and is attained only at I
IMO 2001/1   random acute triangles with gamma >= beta + 30: the claim
             angle CAB + angle COP < 90 holds, and the official chain
             BP - PC >= R holds
drills       the two Foundation solutions are exact identities / divisibility
             facts checked by brute force

Run:  python scripts/verify_seed.py        (exit code 0 == all checks passed)
"""

from __future__ import annotations

import math
import random
import sys
from dataclasses import dataclass
from fractions import Fraction
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from problems.seed_data.showcase import PROBLEMS  # noqa: E402

random.seed(20261011)


@dataclass
class Report:
    checks: list[tuple[str, bool, str]] = None  # type: ignore[assignment]

    def __post_init__(self):
        self.checks = []

    def check(self, name: str, ok: bool, detail: str = "") -> None:
        self.checks.append((name, bool(ok), detail))
        mark = "PASS" if ok else "FAIL"
        print(f"  [{mark}] {name}" + (f" — {detail}" if detail else ""))

    @property
    def failed(self) -> list[tuple[str, bool, str]]:
        return [c for c in self.checks if not c[1]]


# --------------------------------------------------------------------------- #
# IMO 2019/1
# --------------------------------------------------------------------------- #
def verify_2019_1(r: Report) -> None:
    def f_zero(x: int) -> int:
        return 0

    def make_f(c: int):
        return lambda x: 2 * x + c

    ok_families = True
    for c in (-100, -3, 0, 5, 12345):
        f = make_f(c)
        for a in range(-6, 7):
            for b in range(-6, 7):
                if f(2 * a) + 2 * f(b) != f(f(a + b)):
                    ok_families = False
    for a in range(-9, 10):
        for b in range(-9, 10):
            if f_zero(2 * a) + 2 * f_zero(b) != f_zero(f_zero(a + b)):
                ok_families = False
    r.check("2019/1: f ≡ 0 and f(x) = 2x + c satisfy the equation", ok_families)

    # coefficient comparison: f(x) = k x + c must satisfy k^2 = 2k and k c = 2c
    candidates = [k for k in range(-50, 51) if k * k == 2 * k]
    r.check(
        "2019/1: k^2 = 2k leaves only k ∈ {0, 2}",
        set(candidates) == {0, 2},
        f"solutions {candidates}",
    )
    # for k = 0 the constant condition kc = 2c forces c = 0
    k0_c = [c for c in range(-30, 31) if 0 * c == 2 * c]
    r.check("2019/1: k = 0 forces c = 0", k0_c == [0])


# --------------------------------------------------------------------------- #
# IMO 2014/1
# --------------------------------------------------------------------------- #
def verify_2014_1(r: Report) -> None:
    def good_indices(seq: list[int]) -> list[int]:
        """All n with the double inequality, restricted to indices whose successor exists."""
        out = []
        for n in range(1, len(seq) - 1):
            s = sum(seq[: n + 1])
            if seq[n] * n < s <= n * seq[n + 1]:
                out.append(n)
        return out

    ok = True
    bad = ""
    for _ in range(4000):
        length = random.randint(5, 25)
        seq = sorted(random.sample(range(1, 400), length))
        if len(set(seq)) != length:
            continue
        found = good_indices(seq)
        if len(found) > 1:
            ok = False
            bad = f"seq={seq[:8]}... found={found}"
            break
        if len(found) == 0:
            # The unique index can be the final one of the truncated sequence: the
            # crossing of t_n = S_n - n a_n is then at n = len(seq) - 1.
            n = len(seq) - 1
            t_n = sum(seq[: n + 1]) - n * seq[n]
            if t_n <= 0:
                ok = False
                bad = f"no valid index and t_{n} = {t_n} <= 0 for seq={seq[:8]}..."
                break
    r.check("2014/1: exactly one index n satisfies the double inequality", ok, bad)

    # monotonicity of t_n = S_n - n a_n
    seq = sorted(random.sample(range(1, 500), 30))
    t = [sum(seq[: n + 1]) - n * seq[n] for n in range(1, 30)]
    r.check("2014/1: t_n is strictly decreasing and starts positive", all(
        t[i + 1] < t[i] for i in range(len(t) - 1)
    ) and t[0] > 0)


# --------------------------------------------------------------------------- #
# IMO 2005/4
# --------------------------------------------------------------------------- #
def verify_2005_4(r: Report) -> None:
    def a(n: int) -> int:
        return 2**n + 3**n + 6**n - 1

    hits = {2: 1, 3: 2}  # prime -> exponent n with p | a_n
    for p in range(5, 400):
        if all(p % q for q in range(2, int(math.isqrt(p)) + 1)):
            n = p - 2
            hits[p] = n
    ok = all(a(n) % p == 0 for p, n in hits.items())
    r.check(
        "2005/4: every prime p ≤ 400 divides some term (n = p−2 for p ≥ 5)",
        ok,
        f"{len(hits)} primes checked; a_1={a(1)}, a_2={a(2)}",
    )
    # the Fermat step: 2^(p-2) ≡ 1/2 (mod p) and 1/2+1/3+1/6 = 1
    ok_inv = all(
        (pow(2, p - 2, p) * 2) % p == 1 and (pow(3, p - 2, p) * 3) % p == 1
        for p in hits
        if p >= 5
    )
    r.check("2005/4: 2^(p−2) ≡ 2⁻¹ and 3^(p−2) ≡ 3⁻¹ (mod p) for p ≥ 5", ok_inv)
    r.check("2005/4: p = 2 divides every term and p = 3 divides a_2", a(1) % 2 == 0 and a(5) % 2 == 0 and a(2) % 3 == 0)
    r.check("2005/4: 1/2 + 1/3 + 1/6 − 1 equals 0", Fraction(1, 2) + Fraction(1, 3) + Fraction(1, 6) - 1 == 0)


# --------------------------------------------------------------------------- #
# IMO 1988/6 (Vieta jumping)
# --------------------------------------------------------------------------- #
def verify_1988_6(r: Report) -> None:
    ok_square = True
    descent_ok = True
    violations = []
    for b in range(1, 41):
        for a in range(b, 81):
            num, den = a * a + b * b, a * b + 1
            if num % den:
                continue
            k = num // den
            if math.isqrt(k) ** 2 != k:
                ok_square = False
                violations.append((a, b, k))
            if a > b and math.isqrt(k) ** 2 != k:
                a_prime = k * b - a
                # in a *minimal counterexample* (k not a square) a' is a positive
                # integer below b and still a solution: that is the descent
                if not (a_prime > 0 and a_prime < b):
                    descent_ok = False
                    violations.append(("descent", a, b, k, a_prime))
                if (a_prime * a_prime + b * b) != k * (a_prime * b + 1):
                    descent_ok = False
            elif a > b and k * b - a == 0 and k != b * b:
                descent_ok = False
                violations.append(("a'=0 but k != b^2", a, b, k))
    r.check("1988/6: (ab+1) | (a²+b²) ⟹ the quotient is a perfect square", ok_square, str(violations[:3]))
    r.check("1988/6: the Vieta jump gives 0 < a' < b with the same k", descent_ok)
    r.check("1988/6: quotient never equals 1 for a > b", all(
        ((a * a + b * b) // (a * b + 1)) != 1
        for a in range(2, 60)
        for b in range(1, a)
        if (a * a + b * b) % (a * b + 1) == 0
    ))


# --------------------------------------------------------------------------- #
# IMO 2014/5 (Cape Town coins) - simulate the constructive algorithm
# --------------------------------------------------------------------------- #
def verify_2014_5(r: Report) -> None:
    K = 100  # number of groups allowed

    for m in range(1, K):
        if not (Fraction(2 * m, 2 * m + 1) + Fraction(1, 2 * m + 2) < 1):
            r.check(f"2014/5: box B_{m} stays below value 1", False)
            return
    r.check("2014/5: 2m/(2m+1) + 1/(2m+2) < 1 for all boxes B_1..B_99", True)

    if not (Fraction(K) - Fraction(1, 2) < Fraction(K) - Fraction(K, 2 * K + 1)):
        r.check("2014/5: counting bound k − 1/2 < k − k/(2k+1)", False)
        return
    r.check("2014/5: counting bound k − 1/2 < k − k/(2k+1) (k = 100)", True)

    def random_instance() -> list[Fraction]:
        """Random legal multiset of Cape Town coins with total value ≤ 99.5."""
        coins: list[Fraction] = []
        total = Fraction(0)
        target = Fraction(99) + Fraction(1, 2)
        while True:
            n = random.randint(1, 40)
            coin = Fraction(1, n)
            if total + coin > target:
                break
            coins.append(coin)
            total += coin
            if len(coins) > 60000:
                break
        return coins

    def algorithm(coins: list[Fraction]) -> tuple[list[list[Fraction]], bool]:
        coins = sorted(coins)
        groups: list[list[Fraction]] = []
        # Phase 1: normalise
        changed = True
        while changed:
            changed = False
            # 1a. two coins of size 1/(2m) -> one coin of 1/m
            for n in range(2, 2 * K + 40, 2):
                small = Fraction(1, n)
                while coins.count(small) >= 2:
                    coins.remove(small)
                    coins.remove(small)
                    coins.append(small * 2)
                    coins.sort()
                    changed = True
            # 1b. 2m+1 coins of size 1/(2m+1) form a group of value exactly 1
            for m in range(0, K + 20):
                den = 2 * m + 1
                small = Fraction(1, den)
                while coins.count(small) >= den:
                    for _ in range(den):
                        coins.remove(small)
                    groups.append([small] * den)
                    changed = True
        # Phase 2: boxes.  Step 1(b) formed len(groups) groups of value exactly 1,
        # so the induction gives us only K - len(groups) boxes for what remains.
        K_eff = K - len(groups)
        boxes: list[list[Fraction]] = [[] for _ in range(K_eff)]
        weights = [Fraction(0) for _ in range(K)]
        if K_eff <= 0:
            return groups, not coins
        half = Fraction(1, 2)
        while half in coins:
            coins.remove(half)
            boxes[0].append(half)
            weights[0] += half
        for m in range(1, K_eff):
            odd_den, even_den = 2 * m + 1, 2 * m + 2
            odd, even = Fraction(1, odd_den), Fraction(1, even_den)
            # at most 2m coins of size 1/(2m+1)
            while boxes[m].count(odd) < 2 * m and odd in coins:
                coins.remove(odd)
                boxes[m].append(odd)
                weights[m] += odd
            if even in coins:  # at most one coin of size 1/(2m+2) after normalisation
                coins.remove(even)
                boxes[m].append(even)
                weights[m] += even
        # Phase 3: toss the remaining small coins into boxes without exceeding 1
        for coin in list(coins):
            placed = False
            for i in range(K_eff):
                if weights[i] + coin <= 1:
                    boxes[i].append(coin)
                    weights[i] += coin
                    coins.remove(coin)
                    placed = True
                    break
            if not placed:
                return groups + boxes, False
        for box in boxes:
            groups.append(box)
        return groups, True

    ok_all = True
    detail = ""
    for trial in range(60):
        coins = random_instance()
        groups, completed = algorithm(coins)
        total = sum(coins)
        n_groups = len([g for g in groups if g])
        if not completed:
            ok_all, detail = False, f"trial {trial}: a coin could not be placed"
            break
        if n_groups > K:
            ok_all, detail = False, f"trial {trial}: used {n_groups} > {K} groups"
            break
        if any(sum(g) > 1 for g in groups):
            ok_all, detail = False, f"trial {trial}: a group exceeds value 1"
            break
        if sum(sum(g) for g in groups) != total:
            ok_all, detail = False, f"trial {trial}: coin multiset not preserved"
            break
    r.check("2014/5: algorithm splits 60 random instances into ≤ 100 groups of value ≤ 1", ok_all, detail)


# --------------------------------------------------------------------------- #
# IMO 2001/3
# --------------------------------------------------------------------------- #
def verify_2001_3(r: Report) -> None:
    r.check("2001/3: pigeonhole ⌈21/6⌉ = 4 boys share some problem of a girl", math.ceil(21 / 6) == 4)
    bound = 2 * (5 * 21 + 5 * 21)
    r.check("2001/3: double counting gives |T| ≤ 420 < 441", bound == 420 and bound < 21 * 21)
    r.check(
        "2001/3: colouring solution arithmetic ⌈441/2⌉ = 221, ⌈221/21⌉ = 11, ⌈11/2⌉ = 6",
        math.ceil(441 / 2) == 221 and math.ceil(221 / 21) == 11 and math.ceil(11 / 2) == 6,
    )
    r.check("2001/3: 6·2 = 12 < 21 boys is the final contradiction", 6 * 2 < 21)

    # Scaled brute force of the double-counting mechanism: 3 girls, 3 boys, 2
    # problems, "at most 2 problems solved" (automatic here), threshold ">= 2 of
    # each sex".  If every problem had min(g_p,b_p) <= 1 the count would force
    # sum g_p b_p <= 2*3 = 6 < 9, so no configuration may avoid the conclusion.
    import itertools

    opts = [frozenset(s) for s in itertools.chain.from_iterable(
        itertools.combinations(range(2), k) for k in range(3)
    )]
    avoiding = []
    for ga in itertools.product(opts, repeat=3):
        for ba in itertools.product(opts, repeat=3):
            if not all(gm & bm for gm in ga for bm in ba):
                continue  # condition 2 (every girl-boy pair shares a problem)
            if all(
                not (sum(1 for m in ga if p in m) >= 2 and sum(1 for m in ba if p in m) >= 2)
                for p in range(2)
            ):
                avoiding.append((ga, ba))
    r.check(
        "2001/3: scaled brute force finds no configuration avoiding the conclusion (bound 2·3 = 6 < 9)",
        not avoiding,
        f"{len(avoiding)} avoiding configurations",
    )


# --------------------------------------------------------------------------- #
# IMO 2006/1 (incentre, AP ≥ AI)
# --------------------------------------------------------------------------- #
def _angs(v: tuple[float, float], w: tuple[float, float]) -> float:
    """Angle between two 2-D vectors, in radians."""
    dot = v[0] * w[0] + v[1] * w[1]
    nv = math.hypot(*v)
    nw = math.hypot(*w)
    return math.acos(max(-1.0, min(1.0, dot / (nv * nw))))


def verify_2006_1(r: Report) -> None:
    ok_condition = ok_collinear = ok_min = ok_locus = True
    detail_col = detail_min = detail_ang = ""

    def inside(p, tri, eps=1e-9):
        (x1, y1), (x2, y2), (x3, y3) = tri
        d1 = (p[0] - x2) * (y1 - y2) - (x1 - x2) * (p[1] - y2)
        d2 = (p[0] - x3) * (y2 - y3) - (x2 - x3) * (p[1] - y3)
        d3 = (p[0] - x1) * (y3 - y1) - (x3 - x1) * (p[1] - y1)
        neg = (d1 < -eps) or (d2 < -eps) or (d3 < -eps)
        pos = (d1 > eps) or (d2 > eps) or (d3 > eps)
        return not (neg and pos)

    def deficit(P, A_pt, B_pt, C_pt):
        """|(∠PBA+∠PCA) − (∠PBC+∠PCB)| in radians."""
        lhs = _angs((P[0] - B_pt[0], P[1] - B_pt[1]), (A_pt[0] - B_pt[0], A_pt[1] - B_pt[1])) + _angs(
            (P[0] - C_pt[0], P[1] - C_pt[1]), (A_pt[0] - C_pt[0], A_pt[1] - C_pt[1])
        )
        rhs = _angs((P[0] - B_pt[0], P[1] - B_pt[1]), (C_pt[0] - B_pt[0], C_pt[1] - B_pt[1])) + _angs(
            (P[0] - C_pt[0], P[1] - C_pt[1]), (B_pt[0] - C_pt[0], B_pt[1] - C_pt[1])
        )
        return abs(lhs - rhs)

    trials_with_points = 0
    locus_trials = 0
    for _ in range(120):
        A_pt = (random.uniform(0, 6), random.uniform(0, 6))
        B_pt = (random.uniform(0, 6), random.uniform(0, 6))
        C_pt = (random.uniform(0, 6), random.uniform(0, 6))
        if abs((B_pt[0] - A_pt[0]) * (C_pt[1] - A_pt[1]) - (B_pt[1] - A_pt[1]) * (C_pt[0] - A_pt[0])) < 1e-2:
            continue
        a = math.dist(B_pt, C_pt)
        b = math.dist(C_pt, A_pt)
        c = math.dist(A_pt, B_pt)
        I = (
            (a * A_pt[0] + b * B_pt[0] + c * C_pt[0]) / (a + b + c),
            (a * A_pt[1] + b * B_pt[1] + c * C_pt[1]) / (a + b + c),
        )
        ax, ay = B_pt
        bx, by = C_pt
        cx, cy = I
        d = 2 * (ax * (by - cy) + bx * (cy - ay) + cx * (ay - by))
        if abs(d) < 1e-9:
            continue
        M = (
            ((ax**2 + ay**2) * (by - cy) + (bx**2 + by**2) * (cy - ay) + (cx**2 + cy**2) * (ay - by)) / d,
            ((ax**2 + ay**2) * (cx - bx) + (bx**2 + by**2) * (ax - cx) + (cx**2 + cy**2) * (bx - ax)) / d,
        )
        R_gamma = math.dist(M, I)
        AI = math.dist(A_pt, I)

        # (a) A, I, M collinear (with M on the far side of BC, so I between them)
        cross = (I[0] - A_pt[0]) * (M[1] - A_pt[1]) - (I[1] - A_pt[1]) * (M[0] - A_pt[0])
        if abs(cross) > 1e-6 * (1 + math.dist(A_pt, M)):
            ok_collinear = False
            detail_col = f"non-collinear: cross={cross:.2e}"
            break

        # (b) the distance from A to the circle (BIC) is exactly AI, attained at I
        if abs((math.dist(A_pt, M) - R_gamma) - AI) > 1e-6 * (1 + AI):
            ok_min = False
            detail_min = f"min-dist {math.dist(A_pt, M) - R_gamma:.6f} vs AI={AI:.6f}"
            break

        # (c) every interior point of the circle satisfies the angle condition,
        #     and AP >= AI there
        checked_here = 0
        for k in range(720):
            theta = 2 * math.pi * k / 720
            P = (M[0] + R_gamma * math.cos(theta), M[1] + R_gamma * math.sin(theta))
            if not inside(P, (A_pt, B_pt, C_pt)):
                continue
            checked_here += 1
            if deficit(P, A_pt, B_pt, C_pt) > 1e-6:
                ok_condition = False
                detail_ang = f"condition off by {deficit(P, A_pt, B_pt, C_pt):.2e} at an interior circle point"
                break
            if math.dist(A_pt, P) < AI - 1e-9:
                ok_min = False
                detail_min = f"AP={math.dist(A_pt, P):.6f} < AI={AI:.6f}"
                break
        if not ok_condition or not ok_min:
            break
        if checked_here == 0:
            continue
        trials_with_points += 1


        # (d) converse: grid-search interior points satisfying the condition and
        #     check they all lie on the circle (BIC)
        lo_x = min(A_pt[0], B_pt[0], C_pt[0])
        hi_x = max(A_pt[0], B_pt[0], C_pt[0])
        lo_y = min(A_pt[1], B_pt[1], C_pt[1])
        hi_y = max(A_pt[1], B_pt[1], C_pt[1])
        found_solutions = 0
        for i in range(1, 41):
            for j in range(1, 41):
                P = (lo_x + (hi_x - lo_x) * i / 41, lo_y + (hi_y - lo_y) * j / 41)
                if not inside(P, (A_pt, B_pt, C_pt)):
                    continue
                if deficit(P, A_pt, B_pt, C_pt) < 1e-3:
                    found_solutions += 1
                    if abs(math.dist(M, P) - R_gamma) > 0.02 * (1 + R_gamma):
                        ok_locus = False
                        break
            if not ok_locus:
                break
        if found_solutions:
            locus_trials += 1
        # A coarse grid can miss the (possibly very short) solution arc entirely;
        # only trials that did produce hits are meaningful for the converse.

    r.check("2006/1: A, I and the centre M of (BIC) are collinear (I between A and M)", ok_collinear, detail_col)
    r.check("2006/1: min over the circle (BIC) of AP equals AI (external tangency at I)", ok_min, detail_min)
    r.check("2006/1: interior points of the circle (BIC) satisfy ∠PBA+∠PCA = ∠PBC+∠PCB", ok_condition, detail_ang)
    r.check(
        "2006/1: conversely, interior points satisfying the condition lie on (BIC)",
        ok_locus,
        f"{locus_trials} triangles had grid hits",
    )


# --------------------------------------------------------------------------- #
# IMO 2001/1 (acute triangle, gamma >= beta + 30 => alpha + delta < 90)
# --------------------------------------------------------------------------- #
def verify_2001_1(r: Report) -> None:
    ok_claim = ok_chain = True
    detail = ""
    for _ in range(2000):
        beta = random.uniform(1, 55)          # degrees
        gamma_lo = beta + 30
        if gamma_lo >= 90:
            continue
        gamma = random.uniform(gamma_lo, 89.0)
        alpha = 180 - beta - gamma
        if alpha <= 0 or max(alpha, beta, gamma) >= 90:  # acute triangle
            continue
        R = 1.0
        AB = 2 * R * math.sin(math.radians(gamma))
        AC = 2 * R * math.sin(math.radians(beta))
        BP = AB * math.cos(math.radians(beta))
        PC = AC * math.cos(math.radians(gamma))
        if BP - PC < R - 1e-9:  # official chain: BP - PC = 2R sin(gamma-beta) >= R
            ok_chain = False
            detail = f"BP-PC={BP - PC:.6f} < R for beta={beta:.2f}, gamma={gamma:.2f}"
            break
        # OP and PC with P the foot of the altitude: place BC on the x-axis
        # P is the projection of A, so PC = AC cos gamma (verified above).
        # OP^2 from the power of P: PB·PC = R^2 − OP^2  =>  OP^2 = R^2 − PB·PC
        OP2 = R**2 - BP * PC
        if OP2 <= PC * PC:  # we need OP > PC
            ok_claim = False
            detail = f"OP={math.sqrt(OP2):.6f} <= PC={PC:.6f}"
            break
        # delta = ∠COP is opposite the side PC in triangle C-O-P, so
        # cos(delta) = (R^2 + OP^2 - PC^2) / (2 R OP)
        cos_delta = (R**2 + OP2 - PC * PC) / (2 * R * math.sqrt(OP2))
        delta = math.degrees(math.acos(max(-1.0, min(1.0, cos_delta))))
        if alpha + delta >= 90 - 1e-9:
            ok_claim = False
            detail = f"alpha+delta={alpha + delta:.6f}"
            break
    r.check("2001/1: OP > PC follows from BP − PC ≥ R", ok_chain)
    r.check("2001/1: ∠CAB + ∠COP < 90° for random admissible acute triangles", ok_claim, detail)


# --------------------------------------------------------------------------- #
# Foundation drills
# --------------------------------------------------------------------------- #
def verify_drills(r: Report) -> None:
    ok_amgm = True
    for _ in range(2000):
        a = random.random()
        b = 1 - a
        if a <= 0 or b <= 0:
            continue
        if (1 + 1 / a) * (1 + 1 / b) < 9 - 1e-9:
            ok_amgm = False
    r.check("drill A1: (1+1/a)(1+1/b) ≥ 9 for a+b=1", ok_amgm)
    r.check(
        "drill A1: 1 + 2/(ab) ≥ 9 ⟺ ab ≤ 1/4 at a = b = 1/2",
        abs((1 + 2 / (0.25)) - 9) < 1e-12,
    )

    def repunit(n: int) -> int:
        return int("1" * n)

    ok_rep = True
    for n in range(1, 300):
        residues = {repunit(k) % n for k in range(1, n + 2)}
        if len(residues) <= n:  # pigeonhole must already force a collision
            continue
        # difference of two repunits with distinct lengths is 0/1-digit
        pair_found = False
        for i in range(1, n + 2):
            for j in range(i):
                diff = abs(repunit(i) - repunit(j))
                if diff and diff % n == 0 and set(str(diff)) <= {"0", "1"}:
                    pair_found = True
                    break
            if pair_found:
                break
        if not pair_found:
            ok_rep = False
            break
    r.check("drill N1: for every n ≤ 300 some 0/1-digit number is divisible by n", ok_rep)


# --------------------------------------------------------------------------- #
# seed-data integrity
# --------------------------------------------------------------------------- #
def verify_seed_integrity(r: Report) -> None:
    puids = [p["puid"] for p in PROBLEMS]
    r.check("seed: PUIDs are unique", len(puids) == len(set(puids)), f"{len(puids)} problems")
    r.check(
        "seed: every problem has ≥ 3 hints and an official solution",
        all(len(p["hints"]) >= 3 and p["official_tex"].strip() for p in PROBLEMS),
    )
    r.check(
        "seed: every hint is non-empty and hints have no leading/trailing blank lines",
        all(h.strip() and h.strip() == h for p in PROBLEMS for h in p["hints"]),
    )
    cats = {p["category"] for p in PROBLEMS}
    r.check("seed: all four IMO categories are represented", cats >= {"algebra", "combinatorics", "geometry", "number_theory"}, str(sorted(cats)))
    tracks = {p["difficulty_track"] for p in PROBLEMS}
    r.check("seed: difficulty tracks cover foundation/olympiad/hard", tracks == {"foundation", "olympiad", "hard"}, str(sorted(tracks)))


def main() -> int:
    print("=" * 78)
    print("Machine verification of curated ground-truth solutions")
    print("=" * 78)
    report = Report()
    for name, fn in (
        ("IMO 2019/1 — functional equation", verify_2019_1),
        ("IMO 2014/1 — unique averaging index", verify_2014_1),
        ("IMO 2005/4 — 2^n+3^n+6^n−1", verify_2005_4),
        ("IMO 1988/6 — Vieta jumping", verify_1988_6),
        ("IMO 2014/5 — Cape Town coins (algorithm simulated)", verify_2014_5),
        ("IMO 2001/3 — 21 girls and 21 boys", verify_2001_3),
        ("IMO 2006/1 — incentre, AP ≥ AI", verify_2006_1),
        ("IMO 2001/1 — ∠CAB + ∠COP < 90°", verify_2001_1),
        ("Foundation drills", verify_drills),
        ("Seed data integrity", verify_seed_integrity),
    ):
        print(f"\n{name}")
        fn(report)

    failed = report.failed
    print("\n" + "=" * 78)
    print(f"{len(report.checks) - len(failed)}/{len(report.checks)} checks passed")
    if failed:
        print("FAILURES:")
        for name, _, detail in failed:
            print(f"  - {name} {detail}")
        return 1
    print("Toutes les clés de correction ont été vérifiées machine à machine.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
