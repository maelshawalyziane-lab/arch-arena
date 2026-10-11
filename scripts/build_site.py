#!/usr/bin/env python3
"""Construit `site/` — le dossier publiable sur Netlify (ou GitHub Pages, S3, etc.).

Pourquoi une vitrine statique ?

Django ne tourne pas sur Netlify : la plateforme repose sur un serveur (verrou côté
serveur, appels au correcteur IA avec une clé secrète, base de données de progression).
Ce script ne prétend pas déployer l'application : il assemble une **page de présentation
réelle** plus les **aperçus statiques** de l'interface, de sorte que le projet soit
montrable en ligne immédiatement, pendant que la vraie application tourne sur un
hébergeur Python (voir docs/PUBLIER.md).

Ce que fait le script, sans réseau :

* copie les aperçus de `design/` vers `site/` en renommant les fichiers en clair ;
* réécrit les liens internes de l'application (`/`, `/dashboard/`, `/problems/<pk>/`…)
  pour qu'ils pointent vers l'aperçu correspondant — la navigation reste utilisable ;
* neutralise les formulaires (connexion, soumission) : sur un hébergeur statique, un
  POST ne peut pas aboutir, donc on l'annonce au lieu de laisser une erreur 405 ;
* fabrique `site/index.html` (présentation) et `site/comptes-fermes.html` ;
* vérifie que **chaque lien local du site pointe vers un fichier existant**.

    python3 scripts/build_site.py            # écrit site/ et netlify.toml
    python3 scripts/build_site.py --check    # vérifie seulement les liens
"""

from __future__ import annotations

import argparse
import re
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DESIGN = ROOT / "design"
SITE = ROOT / "site"

#: aperçu d'origine → nom public sur le site
PAGES: dict[str, str] = {
    "apercu-exercices.html": "catalogue.html",
    "apercu-exercices-theme-clair.html": "catalogue-clair.html",
    "apercu-fiche-verrouillee.html": "fiche-verrouillee.html",
    "apercu-fiche-verrouillee-theme-clair.html": "fiche-verrouillee-claire.html",
    "apercu-fiche-debloquee.html": "fiche-debloquee.html",
    "apercu-fiche-importee.html": "fiche-importee.html",
    "apercu-tableau-de-bord.html": "tableau-de-bord.html",
    "apercu-connexion.html": "connexion.html",
}

#: libellés utilisés par la galerie de la page d'accueil
GALLERY: list[tuple[str, str, str]] = [
    ("catalogue.html", "Catalogue", "4 334 fiches, filtres par catégorie, parcours, corpus et état du verrou."),
    ("fiche-verrouillee.html", "Fiche verrouillée", "Bandeau de verrouillage, indices dépliés un par un, zone de rédaction."),
    ("fiche-debloquee.html", "Fiche débloquée", "Après un verdict positif : solution officielle, badge et historique de correction."),
    ("fiche-importee.html", "Fiche importée", "Une fiche du corpus Omni-MATH : mêmes règles, même verrou."),
    ("tableau-de-bord.html", "Tableau de bord", "Progression, séries par catégorie, reprise des fiches en cours."),
    ("connexion.html", "Connexion", "Une seule porte d'entrée : l'inscription est fermée."),
    ("catalogue-clair.html", "Thème clair", "Le même catalogue en thème clair — un jeu de variables, pas une seconde feuille."),
    ("fiche-verrouillee-claire.html", "Fiche claire", "La fiche verrouillée en thème clair."),
]

#: liens écrits par l'application → fichier de l'aperçu qui y correspond
LINK_MAP: dict[str, str] = {
    "/": "catalogue.html",
    "/dashboard/": "tableau-de-bord.html",
    "/accounts/login/": "connexion.html",
    "/signup/": "comptes-fermes.html",
    "/problems/au-hasard/": "catalogue.html",
    "/admin/": "administration.html",
}

PROBLEM_LINK = re.compile(r'href="/problems/\d+/?"')
LOGIN_LINK = re.compile(r'href="/accounts/login/\?[^"]*"')

BANNER_OLD = re.compile(
    r'<div class="preview-banner">.*?</div>',
    re.S,
)

BANNER_NEW = """<div class="preview-banner">
  <strong>Aperçu statique</strong> — démonstration de l'interface, CSS et JS incorporés.
  Le verrou IA, la correction et la progression vivent côté serveur : cette page est une
  photographie, pas l'application. <a href="index.html">Présentation du projet</a>.
</div>"""

#: intercepte les formulaires : sur un hébergement statique, le POST ne peut pas aboutir
FORM_GUARD = """<script>
  (function () {
    function toast(message) {
      var bar = document.createElement("div");
      bar.setAttribute("role", "status");
      bar.textContent = message;
      bar.style.cssText = "position:fixed;left:50%;bottom:24px;transform:translateX(-50%);" +
        "max-width:min(560px,92vw);background:#1a2233;color:#e8ecf6;border:1px solid #3a465f;" +
        "border-radius:12px;padding:12px 18px;font:500 14px/1.5 system-ui,sans-serif;" +
        "box-shadow:0 12px 32px rgba(0,0,0,.45);z-index:1200";
      document.body.appendChild(bar);
      setTimeout(function () { bar.remove(); }, 6000);
    }
    document.addEventListener("submit", function (event) {
      event.preventDefault();
      toast("Aperçu statique : la soumission est désactivée ici. " +
            "Le correcteur IA et le verrou fonctionnent sur la version hébergée de la plateforme.");
    }, true);
  })();
</script>"""


def rewrite(html: str) -> str:
    """Réécrit les liens de l'application et neutralise les formulaires."""
    for path, target in LINK_MAP.items():
        html = html.replace(f'href="{path}"', f'href="{target}"')
    html = PROBLEM_LINK.sub('href="fiche-verrouillee.html"', html)
    html = LOGIN_LINK.sub('href="connexion.html"', html)
    html = BANNER_OLD.sub(BANNER_NEW, html, count=1)
    if "<script>" in html:
        html = html.replace("</body>", FORM_GUARD + "\n</body>", 1)
    return html


def build_pages(destination: Path = SITE) -> list[str]:
    written: list[str] = []
    destination.mkdir(parents=True, exist_ok=True)
    for source_name, public_name in PAGES.items():
        source = DESIGN / source_name
        if not source.exists():
            print(f"  ! aperçu manquant : {source_name} (lancez make preview)")
            continue
        (destination / public_name).write_text(rewrite(source.read_text(encoding="utf-8")), encoding="utf-8")
        written.append(public_name)
    return written


def build_closed_signup(destination: Path = SITE) -> None:
    page = """<!DOCTYPE html>
<html lang="fr" data-theme="dark">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Comptes fermés · ARCH Arena</title>
  <style>
    :root { --bg:#090d16; --panel:#131a29; --text:#e8ecf6; --muted:#96a0b8; --accent:#6b8cff; --line:#233049; }
    * { box-sizing:border-box; }
    body { margin:0; min-height:100vh; display:grid; place-items:center; padding:24px;
           background:radial-gradient(1100px 600px at 50% -10%, rgba(107,140,255,.16), transparent), var(--bg);
           color:var(--text); font:400 16px/1.65 system-ui,-apple-system,"Segoe UI",sans-serif; }
    .card { width:min(640px,100%); background:var(--panel); border:1px solid var(--line);
            border-radius:18px; padding:34px 32px; box-shadow:0 24px 60px rgba(0,0,0,.45); }
    h1 { margin:0 0 12px; font:600 26px/1.25 Georgia,serif; }
    p { color:var(--muted); margin:0 0 14px; }
    a.btn { display:inline-block; margin-top:10px; padding:11px 18px; border-radius:10px;
            background:var(--accent); color:#08101f; font-weight:600; text-decoration:none; }
    code { background:#0c1322; border:1px solid var(--line); border-radius:6px; padding:1px 6px; }
  </style>
</head>
<body>
  <div class="card">
    <h1>Les comptes sont fermés</h1>
    <p>La plateforme fonctionne avec <strong>un seul compte</strong>, celui de son propriétaire.
       L'inscription publique est désactivée côté serveur : cette page n'est qu'un aperçu statique,
       aucun formulaire ne pourrait de toute façon aboutir ici.</p>
    <p>Aucune donnée n'est collectée : ni courriel, ni identifiant tiers, ni traceur.</p>
    <a class="btn" href="index.html">Retour à la présentation</a>
  </div>
</body>
</html>
"""
    (destination / "comptes-fermes.html").write_text(page, encoding="utf-8")


def build_admin_notice(destination: Path = SITE) -> None:
    page = """<!DOCTYPE html>
<html lang="fr" data-theme="dark">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Administration · ARCH Arena</title>
  <style>
    :root { --bg:#090d16; --panel:#131a29; --text:#e8ecf6; --muted:#96a0b8; --accent:#6b8cff; --line:#233049; }
    * { box-sizing:border-box; }
    body { margin:0; min-height:100vh; display:grid; place-items:center; padding:24px;
           background:radial-gradient(1100px 600px at 50% -10%, rgba(107,140,255,.16), transparent), var(--bg);
           color:var(--text); font:400 16px/1.65 system-ui,-apple-system,"Segoe UI",sans-serif; }
    .card { width:min(680px,100%); background:var(--panel); border:1px solid var(--line);
            border-radius:18px; padding:34px 32px; box-shadow:0 24px 60px rgba(0,0,0,.45); }
    h1 { margin:0 0 12px; font:600 26px/1.25 Georgia,serif; }
    p, li { color:var(--muted); }
    ul { padding-left:18px; }
    a.btn { display:inline-block; margin-top:14px; padding:11px 18px; border-radius:10px;
            background:var(--accent); color:#08101f; font-weight:600; text-decoration:none; }
    code { background:#0c1322; border:1px solid var(--line); border-radius:6px; padding:1px 6px; }
  </style>
</head>
<body>
  <div class="card">
    <h1>L'administration vit avec le serveur</h1>
    <p>Cette vitrine est statique : l'interface d'administration de Django
       (<code>/admin/</code>) n'existe que sur l'application hébergée, où elle sert à corriger
       une fiche, ajouter un énoncé ou consulter les soumissions.</p>
    <ul>
      <li>les fiches, indices et solutions officielles sont en base de données, pas dans un fichier ;</li>
      <li>l'accès est réservé au compte unique de l'installation ;</li>
      <li>les mêmes données se pilotent aussi par commande : <code>ingest_omni_math</code>,
          <code>translate_corpus --apply</code>, <code>verify_lock_sample</code>.</li>
    </ul>
    <a class="btn" href="index.html">Retour à la présentation</a>
  </div>
</body>
</html>
"""
    (destination / "administration.html").write_text(page, encoding="utf-8")


#: Blocs de code incorporé : le CSS et le JavaScript sont du texte, leurs `href="…"`
#: internes ne sont pas des liens du document (KaTeX en contient, entre autres).
CODE_BLOCK_RE = re.compile(r"<script\b.*?</script>|<style\b.*?</style>", re.DOTALL | re.IGNORECASE)


def validate(destination: Path = SITE) -> list[str]:
    """Chaque lien local doit viser un fichier présent dans le dossier publié."""
    broken: list[str] = []
    for page in sorted(destination.glob("*.html")):
        html = page.read_text(encoding="utf-8")
        markup = CODE_BLOCK_RE.sub(" ", html)
        for target in re.findall(r'(?:href|src)="([^"]+)"', markup):
            if target.startswith(("http://", "https://", "data:", "#", "mailto:", "?")):
                continue
            name = target.split("#")[0].split("?")[0]
            if not name or name.endswith(".css") or name.endswith(".js"):
                continue
            if not (destination / name).exists():
                broken.append(f"{page.name} → {target}")
    return broken


def build_netlify_config() -> None:
    config = """# Configuration Netlify — vitrine statique du projet ARCH Arena.
#
# `site/` est le dossier publié : il est fabriqué par `python3 scripts/build_site.py`
# (les aperçus de design/ y sont recopiés et leurs liens réécrits). Ne l'éditez pas à la
# main : relancez le script.
#
# L'application Django elle-même (verrou côté serveur, correcteur IA, base de données)
# ne peut pas tourner sur Netlify : voir docs/PUBLIER.md pour les hébergeurs adaptés.

[build]
  publish = "site"
  command = "python3 scripts/build_site.py"

[build.environment]
  PYTHON_VERSION = "3.13"

# 404 : on renvoie la présentation plutôt qu'une page d'erreur brute
[[redirects]]
  from = "/*"
  to = "/index.html"
  status = 404

[[headers]]
  for = "/*"
  [headers.values]
    X-Content-Type-Options = "nosniff"
    X-Frame-Options = "DENY"
    Referrer-Policy = "strict-origin-when-cross-origin"
    Permissions-Policy = "geolocation=(), camera=(), microphone=()"

[[headers]]
  for = "/*.html"
  [headers.values]
    Cache-Control = "public, max-age=0, must-revalidate"
"""
    (ROOT / "netlify.toml").write_text(config, encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Construit le site statique publiable (Netlify).")
    parser.add_argument("--check", action="store_true", help="vérifier les liens sans reconstruire")
    parser.add_argument("--out", default=str(SITE), help="dossier de sortie (défaut : site/)")
    args = parser.parse_args()
    destination = Path(args.out)

    if not args.check:
        if destination.exists():
            shutil.rmtree(destination)
        destination.mkdir(parents=True)
        pages = build_pages(destination)
        build_closed_signup(destination)
        build_admin_notice(destination)
        (destination / "index.html").write_text(landing_page(), encoding="utf-8")
        (destination / "robots.txt").write_text("User-agent: *\nAllow: /\n", encoding="utf-8")
        if destination == SITE:
            build_netlify_config()
        print(f"{destination}/ construit : {len(pages) + 3} page(s) HTML")
        for name in pages:
            print(f"  · {name}")

    broken = validate(destination)
    if broken:
        print("\nliens cassés :")
        for line in broken:
            print("  ✗", line)
        return 1
    print("\nTous les liens locaux du site pointent vers un fichier existant.")
    print("Publication : glissez le dossier site/ sur https://app.netlify.com/drop,")
    print("ou laissez Netlify exécuter `python3 scripts/build_site.py` depuis le dépôt.")
    return 0


def landing_page() -> str:
    """La page de présentation publique (autonome : aucune ressource externe)."""
    cards = "\n".join(
        f"""        <a class="card" href="{name}">
          <span class="card-kicker">Aperçu</span>
          <h3>{title}</h3>
          <p>{text}</p>
          <span class="card-cta">Ouvrir →</span>
        </a>"""
        for name, title, text in GALLERY
    )
    return f"""<!DOCTYPE html>
<html lang="fr" data-theme="dark">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>ARCH Arena — entraînement olympique, solutions débloquées par l'IA</title>
<meta name="description" content="Plateforme d'auto-formation en mathématiques olympiques : 4 334 problèmes, indices progressifs, et solution officielle strictement verrouillée jusqu'à validation d'une preuve par un correcteur IA.">
<meta name="color-scheme" content="dark light">
<meta name="theme-color" content="#090d16">
<link rel="icon" href="data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 32 32'%3E%3Crect width='32' height='32' rx='8' fill='%236b8cff'/%3E%3Ctext x='16' y='23' font-size='20' text-anchor='middle' fill='white' font-family='Georgia,serif'%3E%E2%88%91%3C/text%3E%3C/svg%3E">
<style>
  :root {{
    --bg:#090d16; --bg-elev:#111827; --panel:#131a29; --line:#233049;
    --text:#e8ecf6; --muted:#96a0b8; --accent:#6b8cff; --accent-ink:#08101f;
    --ok:#4ade80; --warn:#fbbf24; --radius:16px;
    --sp-2:.5rem; --sp-3:.75rem; --sp-4:1rem; --sp-5:1.5rem; --sp-6:2rem; --sp-7:3rem;
  }}
  * {{ box-sizing:border-box; }}
  html {{ scroll-behavior:smooth; }}
  body {{
    margin:0; background:
      radial-gradient(1200px 620px at 50% -10%, rgba(107,140,255,.18), transparent 60%),
      var(--bg);
    color:var(--text); font:400 16px/1.65 system-ui,-apple-system,"Segoe UI",Roboto,sans-serif;
    -webkit-font-smoothing:antialiased;
  }}
  a {{ color:inherit; }}
  .wrap {{ width:min(1120px,92vw); margin:0 auto; }}
  header.top {{ position:sticky; top:0; z-index:20; backdrop-filter:blur(12px);
    background:rgba(9,13,22,.82); border-bottom:1px solid var(--line); }}
  .top-inner {{ display:flex; align-items:center; gap:var(--sp-4); padding:12px 0; }}
  .brand {{ display:flex; align-items:center; gap:10px; font-weight:650; letter-spacing:.01em; }}
  .brand-mark {{ width:32px; height:32px; border-radius:9px; display:grid; place-items:center;
    background:linear-gradient(140deg,#6b8cff,#8b6bff); color:#08101f; font:700 18px Georgia,serif; }}
  nav.top-nav {{ margin-left:auto; display:flex; gap:var(--sp-5); font-size:14.5px; }}
  nav.top-nav a {{ color:var(--muted); text-decoration:none; }}
  nav.top-nav a:hover {{ color:var(--text); }}
  .hero {{ padding:var(--sp-7) 0 var(--sp-6); }}
  .eyebrow {{ display:inline-flex; align-items:center; gap:8px; font-size:13px; letter-spacing:.06em;
    text-transform:uppercase; color:var(--accent); }}
  h1 {{ font:600 clamp(30px,4.4vw,52px)/1.12 Georgia,"Iowan Old Style",serif; margin:14px 0 16px; max-width:22ch; }}
  .lede {{ color:var(--muted); font-size:clamp(16px,1.6vw,18.5px); max-width:62ch; margin:0 0 var(--sp-5); }}
  .stats {{ display:flex; flex-wrap:wrap; gap:var(--sp-3); margin:0 0 var(--sp-5); }}
  .stat {{ background:var(--panel); border:1px solid var(--line); border-radius:var(--radius);
    padding:12px 16px; min-width:132px; }}
  .stat b {{ display:block; font-size:22px; letter-spacing:-.01em; }}
  .stat span {{ color:var(--muted); font-size:13px; }}
  .cta-row {{ display:flex; flex-wrap:wrap; gap:var(--sp-3); }}
  .btn {{ display:inline-flex; align-items:center; gap:8px; padding:12px 20px; border-radius:11px;
    text-decoration:none; font-weight:600; border:1px solid transparent; }}
  .btn.primary {{ background:var(--accent); color:var(--accent-ink); }}
  .btn.ghost {{ border-color:var(--line); color:var(--text); background:var(--panel); }}
  section {{ padding:var(--sp-7) 0; border-top:1px solid var(--line); }}
  h2 {{ font:600 clamp(22px,2.6vw,30px)/1.25 Georgia,serif; margin:0 0 10px; }}
  .section-lede {{ color:var(--muted); max-width:70ch; margin:0 0 var(--sp-5); }}
  .steps {{ display:grid; gap:var(--sp-4); grid-template-columns:repeat(auto-fit,minmax(260px,1fr)); }}
  .step {{ background:var(--panel); border:1px solid var(--line); border-radius:var(--radius); padding:20px; }}
  .step-n {{ display:inline-grid; place-items:center; width:28px; height:28px; border-radius:50%;
    background:rgba(107,140,255,.16); color:var(--accent); font-weight:700; margin-bottom:10px; }}
  .step h3 {{ margin:0 0 8px; font-size:17px; }}
  .step p {{ margin:0; color:var(--muted); font-size:14.5px; }}
  .gallery {{ display:grid; gap:var(--sp-4); grid-template-columns:repeat(auto-fill,minmax(255px,1fr)); }}
  .card {{ display:block; text-decoration:none; background:var(--panel); border:1px solid var(--line);
    border-radius:var(--radius); padding:18px; transition:transform .15s ease, border-color .15s ease; }}
  .card:hover {{ transform:translateY(-2px); border-color:#33456b; }}
  .card-kicker {{ font-size:12px; letter-spacing:.08em; text-transform:uppercase; color:var(--accent); }}
  .card h3 {{ margin:6px 0 8px; font-size:17px; }}
  .card p {{ margin:0 0 12px; color:var(--muted); font-size:14.5px; }}
  .card-cta {{ font-size:14px; font-weight:600; }}
  .prompt {{ background:#0c1322; border:1px solid var(--line); border-radius:var(--radius);
    padding:20px; overflow:auto; }}
  .prompt pre {{ margin:0; font:13.5px/1.6 ui-monospace,SFMono-Regular,Menlo,monospace; color:#cbd5f5; white-space:pre-wrap; }}
  .notice {{ border-left:3px solid var(--warn); background:rgba(251,191,36,.07); padding:14px 18px;
    border-radius:10px; color:#e6d9b8; margin-top:var(--sp-5); font-size:15px; }}
  .two-col {{ display:grid; gap:var(--sp-5); grid-template-columns:repeat(auto-fit,minmax(300px,1fr)); }}
  .panel {{ background:var(--panel); border:1px solid var(--line); border-radius:var(--radius); padding:22px; }}
  .panel h3 {{ margin:0 0 10px; font-size:17px; }}
  .panel ul {{ margin:0; padding-left:18px; color:var(--muted); font-size:14.8px; }}
  .panel li {{ margin:.35em 0; }}
  code {{ background:#0c1322; border:1px solid var(--line); border-radius:6px; padding:1px 6px;
    font:13.5px ui-monospace,SFMono-Regular,Menlo,monospace; }}
  footer {{ padding:var(--sp-6) 0 var(--sp-7); color:var(--muted); font-size:14px; border-top:1px solid var(--line); }}
  footer p {{ margin:.4em 0; }}
</style>
</head>
<body>
<header class="top">
  <div class="wrap top-inner">
    <span class="brand"><span class="brand-mark">∑</span> ARCH Arena</span>
    <nav class="top-nav">
      <a href="#principe">Le principe</a>
      <a href="#apercus">Aperçus</a>
      <a href="#verrou">Le verrou IA</a>
      <a href="#heberger">Héberger la vraie plateforme</a>
    </nav>
  </div>
</header>

<main>
  <section class="hero wrap">
    <span class="eyebrow">Auto-formation · olympiades de mathématiques</span>
    <h1>Pas de solution sans preuve.</h1>
    <p class="lede">
      Une plateforme d'entraînement inspirée d'ARCH&nbsp;: on cherche vraiment, on rédige,
      et la solution officielle reste <strong>verrouillée côté serveur</strong> jusqu'à ce qu'un
      correcteur IA juge la rédaction mathématiquement valable. Le verrou n'est pas un flou
      visuel&nbsp;: tant que la fiche est verrouillée, la solution n'est <em>jamais</em> envoyée
      au navigateur.
    </p>
    <div class="stats">
      <div class="stat"><b>4 334</b><span>fiches au catalogue</span></div>
      <div class="stat"><b>13 010</b><span>indices par paliers</span></div>
      <div class="stat"><b>4 324</b><span>énoncés (Omni-MATH)</span></div>
      <div class="stat"><b>1</b><span>compte, fermé</span></div>
    </div>
    <div class="cta-row">
      <a class="btn primary" href="fiche-verrouillee.html">Voir une fiche verrouillée</a>
      <a class="btn ghost" href="catalogue.html">Parcourir le catalogue</a>
      <a class="btn ghost" href="fiche-debloquee.html">Voir une fiche débloquée</a>
    </div>
  </section>

  <section id="principe" class="wrap">
    <h2>La règle du jeu</h2>
    <p class="section-lede">Trois étapes, toujours dans cet ordre. Les indices s'ouvrent un par un,
       jamais tous d'un coup, et ils ne citent aucune phrase de la solution officielle.</p>
    <div class="steps">
      <div class="step"><span class="step-n">1</span><h3>Chercher vraiment</h3>
        <p>L'énoncé est rendu en KaTeX (police mathématique embarquée, utilisable hors ligne).
           Trois paliers d'indices : stratégie générale, technique repérée dans la solution,
           puis liste de contrôle avant rédaction.</p></div>
      <div class="step"><span class="step-n">2</span><h3>Rédiger</h3>
        <p>Un espace Markdown/LaTeX, comme une copie : étapes clés, cas limites, cas d'égalité,
           conclusion. La progression est enregistrée par compte.</p></div>
      <div class="step"><span class="step-n">3</span><h3>Faire corriger</h3>
        <p>La rédaction part au correcteur IA, qui la compare à la solution officielle et répond
           en JSON strict. Verdict positif&nbsp;: la solution se débloque et l'historique conserve
           la correction.</p></div>
    </div>
  </section>

  <section id="apercus" class="wrap">
    <h2>Aperçus de l'interface</h2>
    <p class="section-lede">Captures réelles de l'application (pages servies par le serveur Django,
       puis figées). La navigation entre aperçus fonctionne&nbsp;; les formulaires sont neutralisés.</p>
    <div class="gallery">
{cards}
    </div>
    <div class="notice">
      <strong>Ceci est une vitrine statique.</strong> Netlify ne peut pas exécuter Django&nbsp;:
      sans serveur, il n'y a ni verrou, ni appel au correcteur, ni base de progression. Les
      formulaires de ces aperçus sont donc désactivés — c'est annoncé au clic, et non laissé
      en erreur 405.
    </div>
  </section>

  <section id="verrou" class="wrap">
    <h2>Le verrou IA, dans le détail</h2>
    <p class="section-lede">L'endpoint <code>POST /api/problems/&lt;id&gt;/verify</code> suit quatre étapes :
       lecture de la solution officielle en base, réception de la rédaction, appel au modèle avec
       ce prompt système (celui du cahier des charges, verbatim), puis analyse du JSON renvoyé.</p>
    <div class="prompt"><pre>Rôle : Tu es un correcteur expert des Olympiades Internationales de Mathématiques (IMO).
Tâche : Évaluer si le plan de solution ou la preuve soumis contient une logique mathématique valide et arrive au bon résultat par rapport à la solution officielle.
Données : Énoncé={{statement}}, Solution officielle={{official_tex}}, Soumission étudiant={{user_submission}}.
Réponds UNIQUEMENT en JSON strict sans balises markdown :
{{"passed": true ou false, "feedback": "2-3 phrases explicatives."}}</pre></div>
    <div class="two-col" style="margin-top:var(--sp-5)">
      <div class="panel">
        <h3>Verdict positif</h3>
        <ul>
          <li><code>is_solved = true</code>, <code>unlocked_at = maintenant</code></li>
          <li>la soumission passe en <code>PASSED</code></li>
          <li>la réponse renvoie <code>success: true, unlocked: true</code>, puis la page suivante sert
              la solution officielle, sa réponse compacte et l'historique</li>
        </ul>
      </div>
      <div class="panel">
        <h3>Verdict négatif</h3>
        <ul>
          <li>la soumission est archivée en <code>REJECTED</code> avec la correction</li>
          <li><code>success: true, unlocked: false</code> — un refus est une réponse, pas une panne</li>
          <li>la solution reste hors de la page&nbsp;: un test le vérifie sur les 4 332 fiches verrouillées</li>
        </ul>
      </div>
    </div>
  </section>

  <section id="heberger" class="wrap">
    <h2>Héberger la vraie plateforme</h2>
    <p class="section-lede">Le code est un projet Django standard (SQLite en développement,
       PostgreSQL en production) : n'importe quel hébergeur Python convient. Le dépôt contient
       déjà <code>Dockerfile</code>, <code>deploy/render.yaml</code> et
       <code>settings_production.py</code>.</p>
    <div class="two-col">
      <div class="panel">
        <h3>Ce qui doit tourner côté serveur</h3>
        <ul>
          <li>la clé du correcteur IA (jamais dans le navigateur)</li>
          <li>la solution officielle, servie uniquement après déblocage</li>
          <li>la progression et l'historique des soumissions</li>
          <li>la session et l'inscription fermée</li>
        </ul>
      </div>
      <div class="panel">
        <h3>Netlify sait faire quoi, ici</h3>
        <ul>
          <li>servir cette vitrine (statique, rapide, HTTPS, en-têtes de sécurité)</li>
          <li>héberger une <em>fonction</em> serverless — mais l'application devrait alors être
              réécrite pour un autre modèle d'exécution</li>
          <li>pas de Django, pas de base de données, pas de verrou côté serveur</li>
        </ul>
      </div>
    </div>
    <div class="notice">
      Hôte recommandé pour la vraie application&nbsp;: Render, Railway, Fly.io ou PythonAnywhere
      (Docker ou WSGI), avec PostgreSQL et les variables <code>DJANGO_SETTINGS_MODULE=config.settings_production</code>,
      <code>DJANGO_SECRET_KEY</code>, <code>DJANGO_ALLOWED_HOSTS</code>, <code>GEMINI_API_KEY</code>.
      La procédure complète est dans <code>docs/PUBLIER.md</code>.
    </div>
  </section>
</main>

<footer class="wrap">
  <p>ARCH Arena — plateforme d'auto-formation en mathématiques olympiques, inspirée du système
     ARCH (Automated Repository of Canned Hints) d'Evan Chen et du corpus Omni-MATH (Apache-2.0).</p>
  <p>Cette page est un aperçu statique&nbsp;: le verrou IA, la correction et la progression
     fonctionnent sur la version hébergée du serveur, pas ici.</p>
</footer>
</body>
</html>
"""


if __name__ == "__main__":
    sys.exit(main())
