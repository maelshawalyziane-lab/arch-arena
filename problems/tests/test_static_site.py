"""Contrat de la vitrine statique publiée sur Netlify.

Le dossier `site/` est le seul artefact que voit le public : il doit rester cohérent,
navigable, et **sans fuite**. Ces tests reconstruisent la vitrine dans un dossier temporaire
(ils n'écrivent pas dans le dépôt) et vérifient les promesses tenues à l'extérieur :

* la page de présentation annonce le projet et ses chiffres ;
* tous les liens internes visent un fichier réellement présent (pas de 404 en ligne) ;
* les formulaires sont neutralisés : sur un hébergement statique, un POST ne peut pas aboutir,
  donc il est intercepté et annoncé plutôt que laissé en erreur ;
* les aperçus conservent le contrat d'interface du verrou (« verrouillée » = pas de solution) ;
* le dossier publié ne contient **aucune** clé d'API ni chemin de développement.
"""

from __future__ import annotations

import os
import re
import shutil
import tempfile
from pathlib import Path

from django.test import SimpleTestCase

from scripts.build_site import GALLERY, PAGES, landing_page, validate  # type: ignore[import-not-found]

ROOT = Path(__file__).resolve().parent.parent.parent
DESIGN = ROOT / "design"


class StaticSiteBuildTests(SimpleTestCase):
    """La vitrine doit se construire sans dépendance et rester navigable."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        if not any((DESIGN / name).exists() for name in PAGES):
            cls.output = None
            return
        cls.tmp = Path(tempfile.mkdtemp(prefix="arch-site-"))
        cls.output = cls.tmp / "site"

    @classmethod
    def tearDownClass(cls):
        if getattr(cls, "output", None):
            shutil.rmtree(cls.tmp, ignore_errors=True)
        super().tearDownClass()

    def _build(self) -> Path:
        if self.output is None:
            self.skipTest("aucun aperçu dans design/ (lancez make preview)")
        if not self.output.exists():
            import subprocess
            import sys

            subprocess.run(
                [sys.executable, str(ROOT / "scripts" / "build_site.py"), "--out", str(self.output)],
                check=True,
                capture_output=True,
            )
        return self.output

    def test_every_local_link_has_a_target(self):
        site = self._build()
        self.assertEqual(validate(site), [], "un lien de la vitrine ne mène nulle part")

    def test_the_landing_page_presents_the_platform(self):
        site = self._build()
        html = (site / "index.html").read_text(encoding="utf-8")
        self.assertIn("Pas de solution sans preuve.", html)
        self.assertIn("4 334", html)
        self.assertIn("correcteur expert des Olympiades Internationales de Mathématiques (IMO)", html)
        self.assertIn("docs/PUBLIER.md", html)

    def test_landing_page_is_self_contained(self):
        html = landing_page()
        self.assertNotIn("<link rel=\"stylesheet\"", html)
        self.assertNotIn("src=\"http", html)
        self.assertIn("<style>", html)

    def test_gallery_targets_exist(self):
        site = self._build()
        for name, _title, _text in GALLERY:
            self.assertTrue((site / name).exists(), f"aperçu manquant : {name}")

    def test_forms_are_neutralised(self):
        site = self._build()
        for name in ("connexion.html", "fiche-verrouillee.html"):
            html = (site / name).read_text(encoding="utf-8")
            self.assertIn("addEventListener(\"submit\"", html, f"{name} : formulaires non interceptés")
            self.assertIn("Aperçu statique : la soumission est désactivée", html)

    def test_no_development_path_survives_in_the_snapshot(self):
        site = self._build()
        for page in site.glob("*.html"):
            html = page.read_text(encoding="utf-8")
            self.assertNotIn("127.0.0.1:8000", html, f"{page.name} cite encore le serveur local")

    def test_published_folder_never_contains_a_secret(self):
        """Une valeur secrète ne doit jamais atterrir sur un hébergement public.

        Le *nom* des variables d'environnement (`GEMINI_API_KEY`) est cité volontairement
        dans la page d'hébergement : c'est la valeur qui doit rester absente.
        """
        site = self._build()
        # La sentinelle est construite à l'exécution : on cherche la clé API (par sa forme),
        # les clés des fournisseurs, la clé Django de développement… et le mot de passe réel
        # s'il est fourni par l'environnement. Rien de tout cela n'est écrit dans le dépôt.
        secrets = [r"AQ\.[A-Za-z0-9_.-]{20,}", r"sk-[A-Za-z0-9]{20}", "dev-only-insecure-key"]
        for name in ("ARCH_ADMIN_PASSWORD", "ARCH_PASSWORD"):
            value = os.environ.get(name, "")
            if value:
                secrets.append(re.escape(value))
        suspicious = re.compile("|".join(secrets), re.I)
        for page in site.glob("*"):
            if page.suffix in {".html", ".txt", ".toml"}:
                text = page.read_text(encoding="utf-8")
                self.assertIsNone(
                    suspicious.search(text), f"{page.name} contient un secret ou un mot de passe"
                )

    def test_locked_snapshot_still_hides_the_official_solution(self):
        site = self._build()
        html = (site / "fiche-verrouillee.html").read_text(encoding="utf-8")
        self.assertIn("Solution officielle verrouillée", html)
        self.assertIn("Soumettre à l'évaluation IA", html)
        # aucune section « solution » rendue : le verrou tient aussi dans la vitrine
        self.assertNotIn('class="rendered solution-body"', html)

    def test_closed_signup_and_admin_notice_are_explained(self):
        site = self._build()
        closed = (site / "comptes-fermes.html").read_text(encoding="utf-8")
        self.assertIn("Les comptes sont fermés", closed)
        admin = (site / "administration.html").read_text(encoding="utf-8")
        self.assertIn("/admin/", admin)
