#!/usr/bin/env python3
"""
End-to-end demonstration of the verification gate over HTTP (no Django imports).

It exercises exactly what a browser does — CSRF, cookies, JSON POST — and prints
a transcript, so it doubles as a smoke test and as documentation:

    python manage.py runserver 8000 &
    python scripts/demo_gate.py --base http://127.0.0.1:8000 --puid "IMO 1988/6"

Sequence:
  0. reset this user's progress     (POST /reset, so the demo is repeatable)
  1. open the problem page          (solution must be LOCKED and absent from the HTML)
  2. try to reveal hint 2 first     (server refuses: hints open in order)
  3. reveal hint 1                  (accepted)
  4. submit a hand-waving outline   (expected REJECTED)
  5. submit a real proof outline    (expected PASSED + unlocked)
  6. reload the page                (official solution now present, verified by phrase)

Note: the aria/user-facing strings checked here are French, because the UI is
French ("Solution officielle verrouillée", "Soumettre à l'évaluation IA").
"""

from __future__ import annotations

import argparse
import http.cookiejar
import os
import json
import re
import sys
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

PASS = "\033[92mPASS\033[0m"
FAIL = "\033[91mFAIL\033[0m"

RESULTS: list[tuple[str, bool, str]] = []


def report(name: str, ok: bool, detail: str = "") -> None:
    RESULTS.append((name, ok, detail))
    print(f"  [{PASS if ok else FAIL}] {name}" + (f" — {detail}" if detail else ""))


class Client:
    def __init__(self, base: str) -> None:
        self.base = base.rstrip("/")
        self.jar = http.cookiejar.CookieJar()
        self.opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(self.jar))

    def get(self, path: str) -> str:
        with self.opener.open(self.base + path, timeout=60) as response:
            return response.read().decode("utf-8")

    def post(self, path: str, payload: dict | None = None, *, form: bool = False) -> tuple[int, str, str]:
        token = self.csrf()
        headers = {"X-CSRFToken": token, "Accept": "application/json", "Referer": self.base + "/"}
        if form:
            data = urllib.parse.urlencode(payload or {}).encode()
            headers["Content-Type"] = "application/x-www-form-urlencoded"
        else:
            data = json.dumps(payload or {}).encode()
            headers["Content-Type"] = "application/json"
        request = urllib.request.Request(self.base + path, data=data, headers=headers, method="POST")
        try:
            with self.opener.open(request, timeout=180) as response:
                return response.status, response.read().decode("utf-8"), response.headers.get("Content-Type", "")
        except urllib.error.HTTPError as exc:
            return exc.code, exc.read().decode("utf-8"), exc.headers.get("Content-Type", "")

    def login(self, username: str, password: str) -> bool:
        """Se connecte comme le ferait un navigateur (la plateforme n'a qu'un compte)."""
        page = self.get("/accounts/login/")
        match = re.search(r'name="csrfmiddlewaretoken" value="([^"]+)"', page)
        token = match.group(1) if match else self._csrf_cookie()
        data = urllib.parse.urlencode(
            {"username": username, "password": password, "csrfmiddlewaretoken": token, "next": "/"}
        ).encode()
        # Le cookie csrftoken est déjà dans le pot : ne PAS poser d'en-tête Cookie manuel,
        # sinon il masque les cookies du pot sur la redirection qui suit la connexion
        # (la sessionid fraîche n'est alors jamais renvoyée et le test échoue à tort).
        request = urllib.request.Request(
            self.base + "/accounts/login/",
            data=data,
            headers={
                "Content-Type": "application/x-www-form-urlencoded",
                "Referer": self.base + "/accounts/login/",
            },
            method="POST",
        )
        try:
            with self.opener.open(request, timeout=60) as response:
                body = response.read().decode("utf-8", errors="replace")
                if "sessionid" not in {c.name for c in self.jar}:
                    return False
                # la session doit vraiment ouvrir une page réservée
                return "<title>Catalogue" in body or "Tableau de bord" in body
        except urllib.error.HTTPError as exc:
            print("  connexion refusée :", exc.code, exc.read()[:160].decode(errors="replace"))
            return False

    def csrf(self) -> str:
        token = self._csrf_cookie()
        if token:
            return token
        # Prime the cookie.  Django only sets it on a page that renders a form with
        # {% csrf_token %}, so fall back to the login page (every page may be a
        # plain list view with no form on it).
        for path in ("/", "/accounts/login/"):
            self.get(path)
            token = self._csrf_cookie()
            if token:
                return token
        return ""

    def _csrf_cookie(self) -> str:
        for cookie in self.jar:
            if cookie.name == "csrftoken":
                return cookie.value
        return ""


def find_problem(client: Client, puid: str) -> tuple[int, str]:
    html = client.get("/?q=" + urllib.parse.quote(puid))
    for match in re.finditer(r'href="/problems/(\d+)/"[^>]*>\s*<div class="card-top">\s*<span class="puid">([^<]+)</span>', html):
        if match.group(2).strip() == puid:
            return int(match.group(1)), html
    raise SystemExit(f"could not find problem {puid!r} on the list page - run seed_showcase first")


WEAK = (
    "This is well known. By the standard Vieta jumping argument the answer follows immediately, "
    "so the quotient must be a square. The details are routine."
)

STRONG = r"""
Let $k = \frac{a^2+b^2}{ab+1}$, an integer, and read the defining relation as a quadratic in $a$:
$$a^2 - kba + (b^2 - k) = 0.$$
One root is $a$, so by Vieta the other root $a' = kb - a$ is an integer and $(a',b)$ is again a
solution of the same equation with the same quotient $k$; also $a a' = b^2 - k$.

Assume for contradiction that $k$ is not a perfect square, and choose a counterexample with
$a \ge b$ and $a+b$ minimal (well-ordering on the positive integers). Then $a \ne b$, because
$a = b$ would give $k = \frac{2a^2}{a^2+1} < 2$, hence $k = 1$, a square. So $a > b \ge 1$.

Next $a' \ne 0$: otherwise $b^2 - k = aa' = 0$ gives $k = b^2$, a square. Suppose $a' < 0$; then
$a a' \le -a$, so $b^2 - k \le -a$, i.e. $k \ge a + b^2$. But
$$k = \frac{a^2+b^2}{ab+1} < \frac{a^2+b^2}{ab} = \frac{a}{b} + \frac{b}{a} \le a + b \le a + b^2,$$
using $a \ge b \ge 1$. Contradiction, so $a' > 0$.

Finally $a' < b$: if $a' \ge b$ then $ab \le a a' = b^2 - k < b^2$, forcing $a < b$, contradiction.

Hence $0 < a' < b$, and $(a', b)$ — reordered as $(b, a')$ — is a strictly smaller counterexample,
contradicting minimality. Therefore no counterexample exists: the quotient
$\frac{a^2+b^2}{ab+1}$ is always the square of an integer. QED
"""


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base", default="http://127.0.0.1:8000")
    parser.add_argument("--puid", default="IMO 1988/6")
    parser.add_argument("--username", default="admin", help="compte unique de la plateforme")
    parser.add_argument("--password", default=os.environ.get("ARCH_PASSWORD", ""), help="mot de passe (ou $ARCH_PASSWORD)")
    parser.add_argument(
        "--submission-file",
        default="",
        help=(
            "fichier texte utilisé comme « bonne » soumission, à la place de la copie de "
            "démonstration calibrée sur IMO 1988/6. Utile pour rejouer la porte sur une fiche "
            "importée : dump de la solution officielle, votre propre rédaction, etc."
        ),
    )
    parser.add_argument(
        "--keep-progress",
        action="store_true",
        help="do not reset this user's progress first (the gate checks then need a fresh account)",
    )
    args = parser.parse_args()

    client = Client(args.base)
    print(f"== gate demonstration against {args.base} for {args.puid} ==\n")

    print("0b. connexion")
    if args.password:
        if client.login(args.username, args.password):
            report("connexion au compte unique", True, args.username)
        else:
            report("connexion au compte unique", False, "vérifiez --username/--password")
            return 1
    else:
        print("  (aucun mot de passe fourni : --password ou ARCH_PASSWORD)")

    pk, list_html = find_problem(client, args.puid)

    print("0. clean starting state (the demo must be repeatable)")
    if args.keep_progress:
        report("progression réinitialisée", True, "ignorée via --keep-progress")
    else:
        status, body, _ = client.post(f"/api/problems/{pk}/reset", {})
        payload = json.loads(body) if body.strip().startswith("{") else {}
        report(
            "progression réinitialisée pour cette fiche",
            status == 200 and payload.get("success") is True,
            f"HTTP {status}" + ("" if status == 200 else " (nécessite ALLOW_PROGRESS_RESET=1)"),
        )

    print("\n1. open the problem page")
    page = client.get(f"/problems/{pk}/")
    report("page chargée", f"{args.puid}" in page, f"fiche n° {pk}")
    report("solution officielle ABSENTE du HTML verrouillé", "Let $k = \\dfrac{a^2+b^2}{ab+1}" not in page)
    report("bandeau de verrouillage présent", "Solution officielle verrouillée" in page
           and "Soumettez une preuve validée par l'IA pour la débloquer." in page)
    report("aucune fuite de la clé de correction", "a$ is opposite" not in page and "Vieta jumping" not in page)

    print("\n2. hint gating")
    # Les attributs peuvent être répartis sur plusieurs lignes : on tolère
    # l'ordre et les espaces, seul le couple (li, data-hint-id) compte.
    hint_ids = [int(m) for m in re.findall(r'<li[^>]*\bdata-hint-id="(\d+)"', page)]
    report("indices rendus en liste par paliers", len(hint_ids) >= 3, f"{len(hint_ids)} indices")
    if len(hint_ids) >= 2:
        status, body, _ = client.post(f"/api/problems/{pk}/hints/{hint_ids[1]}/reveal", {})
        report("révéler l'indice 2 avant le 1 est refusé", status == 409, f"HTTP {status}")
        status, body, _ = client.post(f"/api/problems/{pk}/hints/{hint_ids[0]}/reveal", {})
        payload = json.loads(body) if body.strip().startswith("{") else {}
        report("révéler l'indice 1 réussit", status == 200 and payload.get("success"), f"HTTP {status}")
        page = client.get(f"/problems/{pk}/")
        report("le contenu de l'indice 1 est servi", payload.get("content_html", "\u0000")[:40] in page
               or "revealed" in page)

    print("\n3. soumission faible (refus attendu, la solution reste verrouillée)")
    if args.submission_file:
        strong = Path(args.submission_file).read_text(encoding="utf-8")
    else:
        strong = STRONG
        if args.puid.strip() != "IMO 1988/6":
            print(
                "  note : la copie de démonstration est écrite pour IMO 1988/6 ; sur une autre "
                "fiche, les contrôles de verdict échoueront. Utilisez --submission-file pour "
                "fournir une rédaction adaptée."
            )

    status, body, _ = client.post(f"/api/problems/{pk}/verify", {"text": WEAK})
    payload = json.loads(body)
    report("HTTP 200 avec success=true", status == 200 and payload.get("success") is True, f"HTTP {status}")
    report("non débloquée", payload.get("unlocked") is False)
    report("status REJECTED", payload.get("status") == "REJECTED")
    report("feedback précis", len(payload.get("feedback", "")) > 60, payload.get("feedback", "")[:110] + "…")
    report("solution toujours absente après refus", "Let $k = \\dfrac{a^2+b^2}{ab+1}" not in client.get(f"/problems/{pk}/"))

    print("\n4. vraie rédaction (acceptation et déblocage attendus)")
    status, body, _ = client.post(f"/api/problems/{pk}/verify", {"text": strong})
    payload = json.loads(body)
    report("HTTP 200 with success=true", status == 200 and payload.get("success") is True, f"HTTP {status}")
    report("débloquée = true", payload.get("unlocked") is True)
    report("status PASSED", payload.get("status") == "PASSED")
    report("moteur indiqué", bool(payload.get("engine")), str(payload.get("engine")))
    report("feedback positif renvoyé", len(payload.get("feedback", "")) > 40, payload.get("feedback", "")[:110] + "…")

    print("\n5. la page sert maintenant la solution officielle")
    page = client.get(f"/problems/{pk}/")
    report("badge débloquée affiché", "✓ Solution débloquée" in page)
    report("solution officielle rendue", "Let $k = \\dfrac{a^2+b^2}{ab+1}" in page or "Vieta" in page)
    report("historique de correction rendu", "Vos corrections" in page)
    report("source LaTeX copiable proposée", "Copier la source LaTeX" in page)

    print("\n6. status endpoint")
    status, body, _ = client.post(f"/api/problems/{pk}/verify", {"text": strong})  # already unlocked
    payload = json.loads(body)
    report("une re-soumission sur une fiche débloquée est archivée, pas réévaluée",
           payload.get("engine") == "archived", str(payload.get("engine")))

    failures = [r for r in RESULTS if not r[1]]
    print("\n" + "=" * 70)
    print(f"{len(RESULTS) - len(failures)}/{len(RESULTS)} contrôles réussis")
    for name, _, detail in failures:
        print(f"  - {name} {detail}")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
