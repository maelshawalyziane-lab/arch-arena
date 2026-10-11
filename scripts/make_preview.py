#!/usr/bin/env python3
"""
Génère des aperçus HTML *autonomes* des pages de la plateforme.

Pourquoi : l'aperçu intégré s'exécute dans une iframe sans réseau, donc les
feuilles de style et scripts servis par `/static/...` ne s'y chargent pas. Ce
script récupère les pages depuis un serveur de développement en cours
d'exécution et **incorpore** le CSS et le JS dans le fichier produit, ce qui
donne un rendu fidèle et hors ligne, ouvrable n'importe où.

    python manage.py runserver 8000 &
    python scripts/make_preview.py --base http://127.0.0.1:8000

Sortie : design/apercu-*.html
"""

from __future__ import annotations

import argparse
import base64
import html
import os
import re
import sys
import http.cookiejar
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
STATIC = ROOT / "problems" / "static"

PAGES = [
    ("/", "apercu-exercices.html", "Accueil — le catalogue complet"),
    ("/problems/{locked_pk}/", "apercu-fiche-verrouillee.html", "Fiche curatée — solution verrouillée"),
    ("/problems/{unlocked_pk}/", "apercu-fiche-debloquee.html", "Fiche curatée — solution débloquée"),
    ("/problems/{imported_locked_pk}/", "apercu-fiche-importee.html", "Fiche importée (Omni-MATH) — verrouillée"),
    ("/dashboard/", "apercu-tableau-de-bord.html", "Tableau de bord"),
    ("/accounts/login/", "apercu-connexion.html", "Connexion"),
]

BANNER = """<div class="preview-banner">
  <strong>Aperçu statique</strong> — {label} · CSS et JS incorporés, aucune ressource externe.
  La version vivante (verrou IA fonctionnel, indices interactifs) tourne sur
  <span class="mono">{base}</span>.
</div>"""


COOKIES = http.cookiejar.CookieJar()
OPENER = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(COOKIES))


def fetch(base: str, path: str) -> str:
    url = base.rstrip("/") + path
    with OPENER.open(url, timeout=30) as response:  # noqa: S310 (URL de confiance)
        return response.read().decode("utf-8")


def login(base: str, username: str, password: str) -> bool:
    """La plateforme n'a qu'un compte : les aperçus doivent s'y connecter."""
    page = fetch(base, "/accounts/login/")
    match = re.search(r'name="csrfmiddlewaretoken" value="([^"]+)"', page)
    token = match.group(1) if match else ""
    data = urllib.parse.urlencode(
        {"username": username, "password": password, "csrfmiddlewaretoken": token, "next": "/"}
    ).encode()
    request = urllib.request.Request(
        base.rstrip("/") + "/accounts/login/",
        data=data,
        headers={
            "Content-Type": "application/x-www-form-urlencoded",
            "Referer": base.rstrip("/") + "/accounts/login/",
        },
        method="POST",
    )
    with OPENER.open(request, timeout=30) as response:
        response.read()
    return any(cookie.name == "sessionid" for cookie in COOKIES)


def katex_stylesheet() -> str:
    """Feuille de style KaTeX avec ses polices mathématiques en data URI.

    L'aperçu s'affiche dans une iframe **sans réseau** : une feuille qui pointerait vers
    ``/static/vendor/katex/fonts/…`` chargerait sans police et KaTeX composerait avec la
    police de secours — symboles décalés, sommes tordues. Les vingt polices sont donc
    incorporées en base64, et chaque ``@font-face`` est réduit à sa seule source woff2.
    """
    css = (STATIC / "vendor" / "katex" / "katex.min.css").read_text(encoding="utf-8")
    fonts = STATIC / "vendor" / "katex" / "fonts"

    def rewrite_src(source: re.Match) -> str:
        for target, _format in re.findall(r"url\(([^)]+)\)\s*format\(\s*[\"']?([\w-]+)[\"']?\s*\)", source.group(0)):
            if not target.endswith(".woff2"):
                continue
            font = fonts / Path(target).name
            if not font.exists():
                continue
            payload = base64.b64encode(font.read_bytes()).decode("ascii")
            return f'src:url(data:font/woff2;base64,{payload}) format("woff2")'
        return source.group(0)

    return re.sub(
        r"@font-face\{[^}]*\}",
        # le `;` final est absent dans le fichier minifié : il est donc optionnel
        lambda block: re.sub(r"src:[^;}]+;?", rewrite_src, block.group(0), count=1),
        css,
    )


def inline_assets(page: str) -> str:
    """Remplace les <link>/<script> locaux par du contenu incorporé.

    Tout ce dont les mathématiques ont besoin — la feuille KaTeX avec ses polices, le
    moteur KaTeX, le script de la page — devient autonome : l'aperçu compose de vraies
    formules hors ligne, exactement comme la plateforme en ligne.
    """
    styles = [
        katex_stylesheet(),
        *[
            (STATIC / rel).read_text(encoding="utf-8")
            for rel in ("problems/css/app.css",)
            if (STATIC / rel).exists()
        ],
    ]
    scripts = [
        *[
            (STATIC / rel).read_text(encoding="utf-8")
            for rel in (
                "vendor/katex/katex.min.js",
                "vendor/katex/auto-render.min.js",
                "problems/js/app.js",
            )
            if (STATIC / rel).exists()
        ],
    ]

    # 1. les polices sont dans le CSS : plus besoin de les précharger séparément
    page = re.sub(r'\s*<link rel="preload"[^>]*href="/static/vendor/katex/fonts/[^"]*">', "", page)

    # 2. feuilles de style
    page = re.sub(
        r'\s*<link rel="stylesheet" href="/static/vendor/katex/katex\.min\.css">',
        lambda _match: f"\n<style>\n{styles[0]}\n</style>",
        page,
    )
    page = re.sub(
        r'\s*<link rel="stylesheet" href="/static/problems/css/app\.css">',
        lambda _match: f"\n<style>\n{styles[1]}\n</style>",
        page,
    )

    # 3. scripts : problem.js a besoin du serveur (soumission, indices) — il reste
    #    dehors ; KaTeX et app.js, eux, composent les mathématiques hors ligne.
    page = re.sub(r'\s*<script[^>]*src="/static/problems/js/problem\.js"[^>]*></script>', "", page)
    for relative, script in zip(
        ("vendor/katex/katex.min.js", "vendor/katex/auto-render.min.js", "problems/js/app.js"), scripts
    ):
        page = re.sub(
            r'\s*<script[^>]*src="/static/' + re.escape(relative) + r'"[^>]*></script>',
            lambda _match, source=script: f"\n<script>\n{source}\n</script>",
            page,
        )
    return page


#: Deux pages sont aussi livrées en thème clair (la vitrine les expose côte à côte).
LIGHT_VARIANTS = {
    "apercu-exercices.html": "apercu-exercices-theme-clair.html",
    "apercu-fiche-verrouillee.html": "apercu-fiche-verrouillee-theme-clair.html",
}


def to_light(page: str) -> str:
    """Bascule une page en thème clair, sans deuxième feuille de style.

    Le thème est porté par l'attribut ``data-theme`` ; le script d'amorçage qui lit le
    choix de l'utilisateur est neutralisé pour que la variante reste claire même
    lorsqu'elle est ouverte par quelqu'un dont le navigateur préfère le sombre.
    """
    page = page.replace('data-theme="dark"', 'data-theme="light"', 1)
    page = page.replace('content="#090d16"', 'content="#f6f7fb"', 1)
    page = page.replace(
        'saved || (prefersLight ? "light" : "dark")',
        '"light"',
    )
    return page


def annotate(page: str, label: str, base: str) -> str:
    """Ajoute un bandeau d'aperçu discret, sans toucher au reste du document."""
    banner_css = """
<style>
  .preview-banner {
    position: relative; z-index: 40; display: flex; flex-wrap: wrap; gap: .5rem;
    align-items: center; justify-content: center; padding: .55rem 1rem;
    background: #6b8cff; color: #fff; font-family: system-ui, sans-serif; font-size: .8rem;
  }
  .preview-banner .mono { font-family: ui-monospace, monospace; background: rgba(0,0,0,.18);
    padding: 0 .35em; border-radius: 4px; }
</style>
"""
    return page.replace("</head>", banner_css + "</head>", 1).replace(
        re.search(r"<body[^>]*>", page).group(0),
        re.search(r"<body[^>]*>", page).group(0)
        + "\n"
        + BANNER.format(label=html.escape(label), base=html.escape(base)),
        1,
    )


MATH_SPANS = re.compile(r'class="math-(?:inline|block)"')


def richest(base: str, candidates: list[int], inspect: int = 12) -> int:
    """Choisit, parmi les premières fiches, celle qui montre le mieux la composition.

    Les aperçus sont la vitrine du rendu : autant y mettre une fiche chargée en formules
    plutôt qu'un énoncé qui n'en contient aucune.
    """
    best, score = candidates[0], -1
    for pk in candidates[:inspect]:
        try:
            page = fetch(base, f"/problems/{pk}/")
        except urllib.error.URLError:
            continue
        found = len(MATH_SPANS.findall(page))
        if found > score:
            best, score = pk, found
        if score >= 24:
            break
    return best


def resolve_pks(base: str) -> dict[str, int]:
    """Trouve les fiches à photographier : curatée verrouillée, curatée débloquée, importée."""
    listing = fetch(base, "/?corpus=curated")
    pks = [int(pk) for pk in re.findall(r'href="/problems/(\d+)/"', listing)]
    if not pks:
        raise SystemExit("aucune fiche trouvée : lancez `python manage.py seed_showcase`")

    curated = fetch(base, "/?corpus=curated&status=solved")
    unlocked = [int(pk) for pk in re.findall(r'href="/problems/(\d+)/"', curated)] or pks

    locked = fetch(base, "/?corpus=curated&status=unsolved")
    locked_pks = [int(pk) for pk in re.findall(r'href="/problems/(\d+)/"', locked)] or pks

    imported = fetch(base, "/?corpus=omni")
    imported_pks = [int(pk) for pk in re.findall(r'href="/problems/(\d+)/"', imported)]

    return {
        "locked_pk": richest(base, locked_pks[:10]),
        "unlocked_pk": unlocked[0],
        "imported_locked_pk": richest(base, imported_pks[:10]) if imported_pks else pks[0],
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base", default="http://127.0.0.1:8000")
    parser.add_argument("--out", default="design")
    parser.add_argument("--username", default="admin")
    parser.add_argument("--password", default=os.environ.get("ARCH_PASSWORD", ""))
    args = parser.parse_args()

    if args.password and not login(args.base, args.username, args.password):
        raise SystemExit("connexion impossible : vérifiez --username/--password")

    out_dir = ROOT / args.out
    out_dir.mkdir(parents=True, exist_ok=True)
    pks = resolve_pks(args.base)

    made = []
    for path, filename, label in PAGES:
        try:
            page = fetch(args.base, path.format(**pks))
        except urllib.error.URLError as exc:
            print(f"  ! {path} → {exc}", file=sys.stderr)
            continue
        page = inline_assets(page)
        page = annotate(page, label, args.base)
        target = out_dir / filename
        target.write_text(page, encoding="utf-8")
        made.append((filename, len(page)))

        light_name = LIGHT_VARIANTS.get(filename)
        if light_name:
            light = to_light(page)
            (out_dir / light_name).write_text(light, encoding="utf-8")
            made.append((light_name, len(light)))

    if not made:
        print("aucun aperçu généré", file=sys.stderr)
        return 1
    print(f"{len(made)} aperçus écrits dans {out_dir}/ :")
    for filename, size in made:
        print(f"  · {filename}  ({size / 1024:.0f} Ko)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
