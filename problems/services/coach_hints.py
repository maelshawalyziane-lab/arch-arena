"""Indices d'orientation produits localement pour le corpus importé.

Les dix fiches du corpus curaté ont des indices écrits à la main. Les milliers de
problèmes importés (Omni-MATH) ne peuvent pas l'être : on génère donc trois paliers
*méthodologiques*, jamais tirés du texte de la solution.

Règle absolue : un indice généré ne doit contenir **aucune phrase** de
``official_tex`` (le test ``test_ingestion_and_rendering`` le vérifie). On ne
détecte dans la solution que la *technique* employée, puis on affiche une piste
écrite ici, en français, qui décrit la méthode et non le cas particulier.
"""

from __future__ import annotations

import re

# --------------------------------------------------------------------------- #
# palier 1 : stratégie générale par catégorie
# --------------------------------------------------------------------------- #
STRATEGY_BY_CATEGORY: dict[str, str] = {
    "algebra": (
        "Piste générale — Réécrivez la relation sous une forme factorisée ou symétrique, "
        "puis isolez la quantité à borner. Les problèmes d'algèbre se débloquent presque "
        "toujours en comparant deux expressions équivalentes, en étudiant le cas d'égalité, "
        "et en vérifiant la réciproque."
    ),
    "combinatorics": (
        "Piste générale — Cherchez une façon de compter la même quantité de deux manières "
        "différentes, ou une bijection qui ramène la configuration générale à une plus simple. "
        "Traitez séparément le cas minimal (petites valeurs) pour conjecturer la réponse avant "
        "de la prouver."
    ),
    "geometry": (
        "Piste générale — Faites un schéma soigné et cherchez une transformation qui met les "
        "objets en position favorable : rotation, homothétie, symétrie ou inversion. Écrire des "
        "angles et des rapports de longueurs suffit souvent ; si c'est lourd, passez par la "
        "puissance d'un point ou par la colinéarité."
    ),
    "number_theory": (
        "Piste générale — Regardez d'abord le problème modulo un petit entier : l'obstruction "
        "et la construction sont souvent visibles là. Ensuite, comparez les valuations "
        "p-adiques des deux membres pour épuiser les divisibilités possibles."
    ),
    "misc": (
        "Piste générale — Testez les petites valeurs pour deviner la réponse et la forme de "
        "l'extremum, puis cherchez ce qui reste invariant quand on modifie la configuration."
    ),
}

STRATEGY_FALLBACK = STRATEGY_BY_CATEGORY["misc"]

# --------------------------------------------------------------------------- #
# palier 2 : technique repérée dans la solution officielle
# --------------------------------------------------------------------------- #
# (motif, piste). L'ordre compte : la première détection gagne.
TECHNIQUES: tuple[tuple[str, str], ...] = (
    (
        r"vieta|other root|quadratic in|roots of the quadratic|second root",
        "Technique probable — Transformer le problème en équation du second degré en une "
        "variable, puis utiliser la relation entre les deux racines : la racine « conjuguée » "
        "donne souvent une configuration plus petite, donc une descente.",
    ),
    (
        r"infinite descent|minimal counterexample|smallest counter|minimality|descente",
        "Technique probable — Raisonner par l'absurde en choisissant un contre-exemple minimal : "
        "la contradiction vient d'une construction qui produit un contre-exemple strictement plus petit.",
    ),
    (
        r"\bpigeonhole|pigeon-hole|box principle|principe des tiroirs",
        "Technique probable — Compter les objets et les « tiroirs » disponibles : si le nombre "
        "d'objets dépasse celui des tiroirs, deux objets partagent un tiroir. C'est souvent la "
        "seule étape non évidente.",
    ),
    (
        r"double count|count(ing)? (the same|in two|two different ways)|two ways|double-count",
        "Technique probable — Compter une même quantité de deux façons différentes et égaler les "
        "deux expressions : l'identité obtenue est exactement le résultat cherché.",
    ),
    (
        r"\binvariant|monovariant|does not change|remains constant|unaffected",
        "Technique probable — Chercher ce qui ne change pas (ou évolue toujours dans le même sens) "
        "au cours des opérations autorisées ; la réponse est souvent imposée par ce quantificateur.",
    ),
    (
        r"induction|inductive|recurrence on|\brecurrence\b|par récurrence",
        "Technique probable — Raisonner par récurrence sur l'entier naturel du problème en "
        "choisissant bien l'hypothèse : l'énoncé plus fort est souvent plus facile à propager.",
    ),
    (
        r"modulo|mod \d|residue|congruent|divisib",
        "Technique probable — Travailler modulo un entier choisi avec soin : chercher le module "
        "qui transforme la contrainte en obstruction immédiate.",
    ),
    (
        r"valuation|v_?p|p-adic|highest power of|exact power of",
        "Technique probable — Comparer les plus grandes puissances d'un premier fixé divisant "
        "chaque membre, ou utiliser la plus petite valeur prise par une expression entière.",
    ),
    (
        r"am[-– ]gm|arithmetic mean|geometric mean|cauchy|jensen|holder|minkowski|"
        r"in[ée]galit[ée]|homogeneity|weierstrass|schwarz",
        "Technique probable — Mettre les deux membres sous une forme comparable, puis appliquer "
        "une inégalité classique (moyennes, Cauchy–Schwarz, Jensen) ; l'étude du cas d'égalité "
        "fait partie de la preuve.",
    ),
    (
        r"smoothing|tangent line|supporting line|convex|concave|uvw|jensen",
        "Technique probable — Étudier la fonction ou la suite auxiliaire et regarder sa monotonie "
        "ou sa convexité ; le cas d'égalité indique le point optimal.",
    ),
    (
        r"generating function|power series|formal series",
        "Technique probable — Encoder la famille de quantités dans une série formelle et lire le "
        "résultat comme un coefficient : les manipulations deviennent de l'algèbre de polynômes.",
    ),
    (
        r"bijection|bijective|one-to-one correspondence|correspondence",
        "Technique probable — Construire une bijection explicite avec un ensemble dont le "
        "cardinal est connu, plutôt que de compter directement.",
    ),
    (
        r"power of a point|radical axis|cyclique|cyclic quadrilater|circumcircle|"
        r"inscribed angle|angle chasing|chasse aux angles",
        "Technique probable — Exploiter la cyclicité et les angles inscrits, ou la puissance d'un "
        "point : cela remplace de longs calculs par une égalité de produits de longueurs.",
    ),
    (
        r"inversion|homothety|homoth[ée]tie|rotation|reflection|spiral similarity|"
        r"similar triangles|triangles semblables",
        "Technique probable — Appliquer une transformation (homothétie, rotation, inversion, "
        "similitude) qui superpose les objets à comparer, puis conclure par similitude.",
    ),
    (
        r"barycentric|coordinate|analytic geometry|trigonometric|law of sines|law of cosines|"
        r"complex plane|unit circle|roots of unity",
        "Technique probable — Passer en coordonnées (barycentriques, complexes ou trigonométriques) : "
        "le problème géométrique devient un calcul finissable.",
    ),
    (
        r"graph|vertex|vertices|edge|edges|colouring|coloring|bipartite|tree",
        "Technique probable — Modéliser la situation par un graphe : sommets, arêtes, degrés. "
        "Les conclusions sont souvent des conséquences du lemme des poignées de main ou de la parité des degrés.",
    ),
    (
        r"expectation|expected value|probabilit|random|linearity",
        "Technique probable — Introduire une expérience aléatoire auxiliaire et utiliser la "
        "linéarité de l'espérance : le résultat déterministe apparaît en moyenne.",
    ),
    (
        r"telescop|partial fraction|summing by parts|abel",
        "Technique probable — Écrire chaque terme comme une différence de deux termes voisins, "
        "pour que les sommes se simplifient en cascade.",
    ),
    (
        r"dirichlet|pigeonhole principle|polynomial method|combinatorial nullstellensatz",
        "Technique probable — Utiliser un théorème d'existence (Dirichlet, principe des tiroirs) "
        "pour garantir l'objet cherché avant de le construire.",
    ),
    (
        r"construct|construction|example show|take the following|x_{1} = 1|we claim that",
        "Technique probable — Une partie de la preuve est une construction explicite : décrire la "
        "configuration candidate puis vérifier les propriétés imposées une par une.",
    ),
    (
        r"cas d'égalité|equality (case|holds|occurs)|if and only if.*equal|symmetric",
        "Technique probable — Isoler le cas d'égalité (souvent la configuration symétrique) et "
        "montrer que toute autre configuration s'en éloigne strictement.",
    ),
    (
        r"parity|pair|impair|odd|even",
        "Technique probable — Regarder la parité : un argument de parité suffit souvent à "
        "interdire la configuration ou à forcer la réponse.",
    ),
)

TECHNIQUE_FALLBACK = (
    "Technique probable — Traiter d'abord un cas particulier ou une version affaiblie de "
    "l'énoncé, puis généraliser : c'est presque toujours l'ordre dans lequel la solution "
    "officielle procède."
)

# --------------------------------------------------------------------------- #
# palier 3 : contrôle avant rédaction
# --------------------------------------------------------------------------- #
CHECKLIST = (
    "Avant de rédiger — Nommez précisément ce que vous devez établir, listez les hypothèses que "
    "vous n'avez pas encore utilisées (il y en a presque toujours une), testez votre résultat sur "
    "un cas limite, et assurez-vous que le cas d'égalité est bien atteint. Une rédaction sans "
    "vérification finale est presque toujours considérée comme incomplète."
)

_COMPILED = tuple((re.compile(pattern, re.IGNORECASE), nudge) for pattern, nudge in TECHNIQUES)


def detect_technique_hint(solution_tex: str) -> str:
    """Renvoie la piste du premier procédé reconnu dans la solution officielle."""
    haystack = solution_tex or ""
    for pattern, nudge in _COMPILED:
        if pattern.search(haystack):
            return nudge
    return TECHNIQUE_FALLBACK


def generate_hints(*, statement_tex: str, solution_tex: str, category: str) -> list[str]:
    """Trois paliers, du plus général au plus concret :

    1. stratégie générale de la catégorie ;
    2. technique reconnue dans la solution officielle ;
    3. liste de contrôle avant rédaction (étapes non utilisées, cas limite, cas d'égalité).
    """
    return [
        STRATEGY_BY_CATEGORY.get(category, STRATEGY_FALLBACK),
        detect_technique_hint(solution_tex),
        CHECKLIST,
    ]
