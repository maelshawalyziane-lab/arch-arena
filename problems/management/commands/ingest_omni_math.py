"""Livre 2 bis — import du corpus Omni-MATH (4 400+ problèmes olympiques).

``ingest_arch_fixture`` couvre le format d'ARCH (livrable 2). Ce second importeur
remplit la plateforme avec un corpus réel : chaque ligne du fichier JSONL fournit
l'énoncé, la solution officielle, une réponse compacte, un domaine et une
difficulté. Aucun accès réseau n'est nécessaire : le fichier est versionné dans
``fixtures/omni_math.jsonl``.

    python manage.py ingest_omni_math                       # tout le corpus
    python manage.py ingest_omni_math --sources imo,imo_shortlist,usamo
    python manage.py ingest_omni_math --limit 200 --dry-run
    python manage.py ingest_omni_math --purge               # retire l'import précédent

Chaque ligne produit un PUID stable ``OMNI <CONCOURS>/<n°>`` (ex. ``OMNI IMO/07``),
ce qui rend l'import idempotent : relancer la commande met à jour au lieu de
dupliquer. Les indices (deux paliers méthodologiques) sont générés localement par
``problems.services.coach_hints`` : aucun appel externe, aucune citation de la
solution officielle.
"""

from __future__ import annotations

import json
from collections import Counter
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from problems.models import Category, DifficultyTrack, Hint, Problem, Solution
from problems.services.coach_hints import generate_hints

DEFAULT_FILE = "fixtures/omni_math.jsonl"

#: Préfixe des PUID importés, partagé avec la vue de liste (filtre « corpus »).
PUID_PREFIX = "OMNI "

#: Libellés courts utilisés dans le PUID (le reste est dérivé du nom de source).
SOURCE_LABELS = {
    "imo": "IMO",
    "imor": "IMO Rémo",
    "imo_shortlist": "IMO SL",
    "imo_longlists": "IMO LL",
    "usamo": "USAMO",
    "usajmo": "USAJMO",
    "usomo": "USOMO",
    "usojmo": "USOJMO",
    "usa_team_selection_test": "USA TST",
    "usa_team_selection_test_for_imo": "USA TST IMO",
    "putnam": "Putnam",
    "apmo": "APMO",
    "apmoapmo_sol": "APMO",
    "china_team_selection_test": "China TST",
    "china_national_olympiad": "China MO",
    "jbmo": "JBMO",
    "jbmo_shortlist": "JBMO SL",
    "jbmo_shortlists": "JBMO SL",
    "balkan_mo": "Balkan MO",
    "balkan_mo_shortlist": "Balkan SL",
    "baltic_way": "Baltic Way",
    "middle_european_mathematical_olympiad": "MEMO",
    "european_girls_mo": "EGMO",
    "european_mathematical_cup": "EMC",
    "tuymaada_olympiad": "Tuymaada",
    "izho": "IZhO",
    "yau_contest": "Yau",
    "imc": "IMC",
    "hmmt_2": "HMMT-2",
    "hmmt_11": "HMMT-11",
    "fermat": "Fermat",
    "cayley": "Cayley",
    "pascal": "Pascal",
    "th_igo": "IGO",
    "pan_african mo": "Pan-African MO",
    "benelux mo": "Benelux MO",
}

#: Le domaine Omni-MATH est une arborescence « Mathematics -> ... -> Feuille ».
CATEGORY_MARKERS = (
    ("number theory", Category.NUMBER_THEORY),
    ("geometry", Category.GEOMETRY),
    ("combinatorics", Category.COMBINATORICS),
    ("discrete mathematics", Category.COMBINATORICS),
    ("graph theory", Category.COMBINATORICS),
    ("algebra", Category.ALGEBRA),
)

#: Seuils de la difficulté Omni-MATH (0–10) vers les trois parcours de la plateforme.
TRACK_THRESHOLDS = ((4.0, DifficultyTrack.FOUNDATION), (6.5, DifficultyTrack.OLYMPIAD))

MIN_SOLUTION_CHARS = 80


def source_label(source: str) -> str:
    """Libellé lisible et stable pour le champ ``source`` d'Omni-MATH."""
    key = (source or "").strip().lower()
    if key in SOURCE_LABELS:
        return SOURCE_LABELS[key]
    pretty = key.replace("_", " ").replace("-", " ").strip()
    return pretty.title() if pretty else "Concours"


def _as_text(value) -> str:
    """Le champ ``domain`` est tantôt une chaîne, tantôt une liste de chaînes."""
    if isinstance(value, (list, tuple, set)):
        return " ".join(str(item) for item in value)
    return str(value or "")


def category_for(domain) -> str:
    """Projette l'arborescence de domaines sur les quatre catégories du schéma."""
    haystack = _as_text(domain).lower()
    for marker, category in CATEGORY_MARKERS:
        if marker in haystack:
            return category
    return Category.MISC


def track_for(raw_difficulty: object) -> str:
    """0–4 → initiation, 4–6,5 → olympiade, au-delà → difficile."""
    try:
        value = float(raw_difficulty)
    except (TypeError, ValueError):
        return DifficultyTrack.OLYMPIAD
    for threshold, track in TRACK_THRESHOLDS:
        if value < threshold:
            return track
    return DifficultyTrack.HARD


def load_records(path: Path):
    with path.open(encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if line:
                yield json.loads(line)


def select_records(
    path: Path,
    *,
    sources: set[str] | None = None,
    min_difficulty: float | None = None,
    max_difficulty: float | None = None,
    limit: int = 0,
):
    """Filtre le JSONL et attribue les PUID — **source unique de vérité**.

    L'import, la traduction et toute autre passe sur le corpus doivent numéroter les
    fiches de la même façon, sinon elles ne parlent plus des mêmes problèmes.
    Renvoie ``(pending, counters, per_source)`` où ``pending`` contient
    ``(record, puid, answer, markup)``.
    """
    from collections import Counter as _Counter

    counters: _Counter[str] = _Counter()
    per_source: _Counter[str] = _Counter()
    source_positions: _Counter[str] = _Counter()
    pending: list[tuple[dict, str, str, list[str]]] = []

    for record in load_records(path):
        counters["lignes_lues"] += 1
        source = (record.get("source") or "").strip().lower()
        if sources and source not in sources:
            counters["source_filtrée"] += 1
            continue

        statement = (record.get("problem") or "").strip()
        solution = (record.get("solution") or "").strip()
        if len(statement) < 20:
            counters["énoncé_manquant"] += 1
            continue
        if len(solution) < MIN_SOLUTION_CHARS:
            counters["solution_manquante"] += 1
            continue

        try:
            numeric = float(record.get("difficulty"))
        except (TypeError, ValueError):
            numeric = 5.0
        if min_difficulty is not None and numeric < min_difficulty:
            counters["difficulté_filtrée"] += 1
            continue
        if max_difficulty is not None and numeric > max_difficulty:
            counters["difficulté_filtrée"] += 1
            continue

        label = source_label(source)
        source_positions[label] += 1
        puid = f"{PUID_PREFIX}{label}/{source_positions[label]:03d}"
        pending.append((record, puid, record.get("answer") or "", []))
        counters["retenus"] += 1
        per_source[label] += 1
        if limit and counters["retenus"] >= limit:
            break

    return pending, counters, per_source


class Command(BaseCommand):
    help = "Importe le corpus Omni-MATH (énoncés, solutions officielles, réponses)."

    def add_arguments(self, parser):
        parser.add_argument("--file", default=DEFAULT_FILE, help=f"JSONL source (défaut : {DEFAULT_FILE})")
        parser.add_argument("--limit", type=int, default=0, help="n'importer que les N premiers problèmes retenus")
        parser.add_argument("--sources", default="", help="liste de sources séparées par des virgules (ex. imo,usamo)")
        parser.add_argument("--min-difficulty", type=float, default=None, help="ignorer en dessous de ce niveau")
        parser.add_argument("--max-difficulty", type=float, default=None, help="ignorer au-dessus de ce niveau")
        parser.add_argument("--purge", action="store_true", help="supprimer d'abord tout le corpus OMNI déjà importé")
        parser.add_argument("--dry-run", action="store_true", help="analyser sans écrire en base")
        parser.add_argument("--report", default="", help="chemin d'un rapport JSON (statistiques détaillées)")

    def handle(self, *args, **options):
        path = Path(options["file"])
        if not path.exists():
            raise CommandError(f"fichier introuvable : {path}")

        wanted = {s.strip().lower() for s in options["sources"].split(",") if s.strip()}
        pending, counters, per_source = select_records(
            path,
            sources=wanted or None,
            min_difficulty=options["min_difficulty"],
            max_difficulty=options["max_difficulty"],
            limit=options["limit"],
        )

        per_category: Counter[str] = Counter()
        per_track: Counter[str] = Counter()

        if options["dry_run"]:
            self.stdout.write(self.style.WARNING("analyse à blanc (--dry-run) : rien n'a été écrit"))
            self._summary(counters, per_source, per_category, per_track)
            return

        with transaction.atomic():
            if options["purge"]:
                deleted, _ = Problem.objects.filter(puid__startswith=PUID_PREFIX).delete()
                counters["purges"] = deleted

            created = updated = hints = solutions = 0
            for record, puid, answer, _first_line in pending:
                category = category_for(record.get("domain"))
                track = track_for(record.get("difficulty"))
                statement = (record.get("problem") or "").strip()
                solution_tex = (record.get("solution") or "").strip()

                problem, is_new = Problem.objects.update_or_create(
                    puid=puid,
                    defaults={
                        "statement_tex": statement,
                        "category": category,
                        "difficulty_track": track,
                        "answer_tex": str(answer).strip()[:255],
                    },
                )
                created += int(is_new)
                updated += int(not is_new)

                Solution.objects.update_or_create(
                    problem=problem,
                    defaults={
                        "official_tex": solution_tex,
                        "attribution": f"Omni-MATH · source {record.get('source')}",
                    },
                )
                solutions += 1

                # Indices générés : on remplace d'éventuels indices générés précédents
                # pour que la commande reste idempotente.
                problem.hints.all().delete()
                for index, content in enumerate(
                    generate_hints(statement_tex=statement, solution_tex=solution_tex, category=category),
                    start=1,
                ):
                    Hint.objects.create(
                        problem=problem,
                        order_index=index,
                        content_md=content,
                        keywords="indice d'orientation généré",
                    )
                    hints += 1

                per_category[problem.get_category_display()] += 1
                per_track[problem.get_difficulty_track_display()] += 1

        counters.update({"créés": created, "mis_à_jour": updated, "solutions": solutions, "indices": hints})
        self._summary(counters, per_source, per_category, per_track)

        if options["report"]:
            report_path = Path(options["report"])
            report_path.parent.mkdir(parents=True, exist_ok=True)
            report_path.write_text(
                json.dumps(
                    {
                        "compteurs": counters,
                        "par_source": per_source.most_common(),
                        "par_categorie": per_category.most_common(),
                        "par_parcours": per_track.most_common(),
                    },
                    ensure_ascii=False,
                    indent=2,
                ),
                encoding="utf-8",
            )
            self.stdout.write(f"rapport écrit : {report_path}")

    # ------------------------------------------------------------------ #
    def _summary(self, counters, per_source, per_category, per_track):
        write = self.stdout.write
        write(self.style.MIGRATE_HEADING("Import Omni-MATH"))
        write(f"  lignes lues ............ {counters['lignes_lues']}")
        write(f"  problèmes retenus ...... {counters['retenus']}")
        for key in ("énoncé_manquant", "solution_manquante", "source_filtrée", "difficulté_filtrée"):
            if counters[key]:
                write(f"  ignorés ({key}) ... {counters[key]}")
        if counters["purges"]:
            write(f"  lignes supprimées ...... {counters['purges']}")
        if counters["créés"] or counters["mis_à_jour"]:
            write(f"  créés .................. {counters['créés']}")
            write(f"  mis à jour ............. {counters['mis_à_jour']}")
            write(f"  solutions officielles .. {counters['solutions']}")
            write(f"  indices générés ........ {counters['indices']}")

        if per_source:
            write("\n  Concours (top 12) :")
            for label, count in per_source.most_common(12):
                write(f"    {label:<26} {count}")
        if per_category:
            write("\n  Catégories :")
            for label, count in per_category.most_common():
                write(f"    {label:<26} {count}")
        if per_track:
            write("\n  Parcours :")
            for label, count in per_track.most_common():
                write(f"    {label:<26} {count}")
