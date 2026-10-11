r"""Traduction française du corpus importé (4 300+ énoncés) via l'API Gemini.

Le catalogue importé arrive en anglais. Cette commande le traduit en français
**sans jamais toucher aux mathématiques** : chaque traduction est comparée à
l'original (mêmes formules, mêmes commandes LaTeX, dans l'ordre) et, en cas
d'écart, l'énoncé d'origine est conservé plutôt que d'écrire une version abîmée.

Deux optimisations dimensionnantes :

* **traduction par lots** (``--batch``, 5 énoncés par requête) : le quota d'appels
  est le facteur limitant, pas la durée de calcul ;
* **cache reprenable** (:file:`var/translations.jsonl`) : chaque résultat est écrit
  au fil de l'eau, donc une coupure ne fait perdre que la requête en cours.

    export GEMINI_API_KEY=...                              # ou clé lue depuis .env
    python manage.py translate_corpus                       # traduit (reprise automatique)
    python manage.py translate_corpus --batch 5 --workers 8 # réglages par défaut
    python manage.py translate_corpus --apply                # écrit en base
    python manage.py translate_corpus --apply --revert       # remet l'anglais

Statuts du cache :
    ok              traduction acceptée (signature LaTeX identique)
    latex_mismatch  refusée après reprise : l'original est conservé
    error           l'API n'a pas répondu : à retenter à la prochaine exécution
"""

from __future__ import annotations

import json
import os
import random
import re
import threading
import time
import urllib.error
import urllib.request
from collections import Counter
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from problems.management.commands.ingest_omni_math import DEFAULT_FILE, select_records
from problems.models import Problem

GEMINI_OPENAI_URL = "https://generativelanguage.googleapis.com/v1beta/openai/chat/completions"

#: Modèles essayés dans l'ordre ; le premier qui répond passe en tête pour la suite.
DEFAULT_MODELS = (
    # Les quotas gratuits dépendent du modèle : les « lite » autorisent 500 requêtes
    # par jour, les autres 20. On commence donc par les gros volumes.
    "gemini-3.5-flash-lite",
    "gemini-3.1-flash-lite",
    "gemini-3.8-flash",
    "gemini-flash-latest",
    "gemini-3-flash-preview",
    "gemini-3.7-flash",
    "gemini-flash-lite-latest",
    "gemini-3.1-flash-lite",
    "gemini-3.6-flash",
    "gemini-3.5-flash",
)

SYSTEM_BATCH = """Tu es traducteur spécialisé dans les mathématiques olympiques.
On te donne plusieurs énoncés d'olympiades, chacun précédé d'une ligne de repère « @@ITEM n@@ ».
Traduis chacun en français et rends UNIQUEMENT le texte, dans ce format exact :

@@ITEM 1@@
<traduction du premier énoncé>
@@ITEM 2@@
<traduction du deuxième énoncé>

Règles absolues :
- Le code mathématique est recopié À L'IDENTIQUE, caractère par caractère : tout ce qui est entre
  $...$, $$...$$, \\(...\\), \\[...\\], ainsi que toute commande LaTeX (\\frac, \\sum, \\le…) reste
  tel quel. Aucune traduction à l'intérieur des mathématiques.
- Ne rien omettre, ne rien ajouter : aucun commentaire, aucun titre, aucune réponse.
- Vocabulaire des olympiades françaises : « entier naturel », « démontrer », « tel que »,
  « pour tout », « si et seulement si », « cercle circonscrit », « point milieu »…
- Conserve les repères « @@ITEM n@@ » exactement tels quels, dans le même ordre."""

SYSTEM_ONE = """Tu es traducteur spécialisé dans les mathématiques olympiques.
Traduis l'énoncé d'olympiade suivant en français.

Règles absolues :
- Le code mathématique est recopié À L'IDENTIQUE, caractère par caractère ($...$, $$...$$, \\(...\\),
  \\[...\\] et toute commande LaTeX comme \\frac, \\sum, \\le). Aucune traduction à l'intérieur.
- Ne rien omettre, ne rien ajouter : pas de commentaire, pas de titre, pas de réponse.
- Vocabulaire des olympiades françaises (« entier naturel », « démontrer », « tel que », « pour tout »).
- Réponds uniquement par la traduction, sans guillemets ni préambule."""

MATH_RE = re.compile(r"\$\$.*?\$\$|\$[^$]*\$|\\\(.*?\\\)|\\\[.*?\\\]", re.DOTALL)
CMD_RE = re.compile(r"\\[a-zA-Z]+")
ITEM_RE = re.compile(r"^@@ITEM\s*(\d+)@@\s*$", re.MULTILINE)


def _normalise_formula(span: str) -> str:
    """Formule débarrassée de sa seule mise en forme : délimiteurs et espaces.

    Le traducteur a le droit d'écrire ``$ x $`` là où l'anglais écrivait ``$x$``, ou de
    replier un ``\\[ ... \\]`` sur une seule ligne : ce n'est pas une altération des
    mathématiques. En revanche, changer un signe, une borne ou supprimer une commande
    LaTeX reste détecté.
    """
    inner = span
    for opening, closing in (("$$", "$$"), ("\\[", "\\]"), ("\\(", "\\)"), ("$", "$")):
        if inner.startswith(opening) and inner.endswith(closing) and len(inner) >= len(opening) + len(closing):
            inner = inner[len(opening): len(inner) - len(closing)]
            break
    return " ".join(inner.split())


def fingerprint(text: str) -> tuple[tuple[str, ...], tuple[tuple[str, int], ...]]:
    r"""Signature mathématique d'un énoncé : formules normalisées + commandes internes.

    Deux volets, et deux seulement :

    * **les formules**, normalisées (délimiteurs et espaces retirés) et comparées dans
      l'ordre : ajouter, retirer ou réordonner une formule est refusé ;
    * **les commandes LaTeX situées DANS les mathématiques**, comptées : une commande
      perdue ou ajoutée à l'intérieur d'une formule est refusée.

    En revanche, la structure typographique du *texte* (``\begin{enumerate}``,
    ``\item``, ``\textbf``…) peut légitimement disparaître : le traducteur a le droit
    de rendre une liste à puces en prose française. Ce qui doit rester intact, c'est
    la mathématique, pas la mise en page.
    """
    spans = MATH_RE.findall(text)
    formulas = tuple(_normalise_formula(span) for span in spans)
    inside_math = " ".join(spans)
    commands = tuple(sorted(Counter(CMD_RE.findall(inside_math)).items()))
    return formulas, commands


# --------------------------------------------------------------------------- #
# polissage : mots anglais restés dans un \text{...} (le modèle les oublie souvent)
# --------------------------------------------------------------------------- #
TEXT_MODE_RE = re.compile(r"\\text\s*\{([^{}]*)\}")

#: (anglais, français) — appliqué mot entier, uniquement dans le mode texte.
TEXT_MODE_WORDS: tuple[tuple[str, str], ...] = (
    ("if and only if", "si et seulement si"),
    ("is not divisible by", "n'est pas divisible par"),
    ("is divisible by", "est divisible par"),
    ("is a multiple of", "est un multiple de"),
    ("such that", "tel que"),
    ("for all", "pour tout"),
    ("otherwise", "sinon"),
    ("where", "où"),
    ("integers", "entiers"),
    ("if", "si"),
    ("and", "et"),
    ("or", "ou"),
    ("for", "pour"),
    ("the", "le"),
    ("with", "avec"),
    ("sum", "somme"),
    ("mod", "mod"),
)


def polish_text_mode(text: str) -> tuple[str, int]:
    """Traduit les mots anglais enfermés dans ``\\text{...}`` (jamais le reste)."""
    changes = 0

    def fix(match: re.Match) -> str:
        nonlocal changes
        content = match.group(1)
        fixed = content
        for english, french in TEXT_MODE_WORDS:
            fixed = re.sub(rf"\b{re.escape(english)}\b", french, fixed, flags=re.IGNORECASE)
        if fixed != content:
            changes += 1
        return match.group(0).replace(content, fixed)

    return TEXT_MODE_RE.sub(fix, text), changes


def parse_batch(raw: str, expected: list[int]) -> dict[int, str]:
    """Découpe la réponse du modèle sur les repères @@ITEM n@@."""
    parts = ITEM_RE.split(raw or "")
    found: dict[int, str] = {}
    for index in range(1, len(parts) - 1, 2):
        try:
            key = int(parts[index])
        except ValueError:
            continue
        found[key] = parts[index + 1].strip()
    # tolérance : réponse sans repères et un seul item attendu
    if not found and len(expected) == 1 and raw.strip():
        found[expected[0]] = raw.strip()
    return found


@dataclass
class Entry:
    puid: str
    status: str          # ok | latex_mismatch | error
    french: str | None
    english: str
    model: str = ""
    seconds: float = 0.0
    attempts: int = 1
    note: str = ""

    def as_json(self) -> dict:
        payload = {
            "puid": self.puid,
            "status": self.status,
            "fr": self.french,
            "en": self.english,
            "model": self.model,
            "seconds": round(self.seconds, 2),
            "attempts": self.attempts,
            "at": time.strftime("%Y-%m-%dT%H:%M:%S"),
        }
        if self.note:
            payload["note"] = self.note
        return payload


class ModelQueue:
    """Régulateur de débit : le palier gratuit de Gemini plafonne à 15 requêtes/minute.

    Plutôt que de lancer des requêtes en rafale et de récolter des 429, on répartit les
    appels entre plusieurs modèles, chacun avec son créneau (60/rpm secondes d'écart).
    Un 429 met le modèle au repos ; un 503 le met brièvement en attente. Le quota étant
    compté par modèle, la rotation multiplie simplement le débit disponible.
    """

    def __init__(self, models: tuple[str, ...], rpm: int = 15) -> None:
        self.models = tuple(models)
        self.base_interval = 60.0 / max(1, rpm)
        self.interval = self.base_interval
        self._state = {m: {"next": 0.0, "blocked": 0.0} for m in self.models}
        self._cold = 0.0          # cooldown global (service en surcharge)
        self._lock = threading.Lock()

    def acquire(self, preferred: str | None = None, timeout: float = 240.0) -> str | None:
        """Renvoie un modèle dont le créneau est arrivé (en attendant si nécessaire)."""
        deadline = time.monotonic() + timeout
        while True:
            with self._lock:
                now = time.monotonic()
                order = ([preferred] if preferred else []) + [m for m in self.models if m != preferred]
                best = min(
                    order,
                    key=lambda m: max(now, self._state[m]["next"], self._state[m]["blocked"], self._cold),
                )
                ready_at = max(now, self._state[best]["next"], self._state[best]["blocked"], self._cold)
                if ready_at <= now:
                    self._state[best]["next"] = now + self.interval
                    return best
                wait = min(ready_at - now, 2.0)
            if time.monotonic() >= deadline:
                return None
            time.sleep(wait)

    def widen(self, factor: float = 1.25, ceiling: float = 6.0) -> float:
        """Quota atteint : on espace davantage toutes les requêtes (AIMD, phase de recul)."""
        with self._lock:
            self.interval = min(ceiling, self.interval * factor)
            return self.interval

    def narrow(self, factor: float = 0.85) -> float:
        """Ça repasse : on revient progressivement vers la cadence visée."""
        with self._lock:
            self.interval = max(self.base_interval, self.interval * factor)
            return self.interval

    @property
    def spacing(self) -> float:
        with self._lock:
            return self.interval

    def penalise(self, model: str, seconds: float) -> None:
        with self._lock:
            self._state[model]["blocked"] = max(
                self._state[model]["blocked"], time.monotonic() + seconds
            )

    def cool_down(self, seconds: float) -> None:
        """Ralentit tout le monde (le service renvoie des 503 en série)."""
        with self._lock:
            self._cold = max(self._cold, time.monotonic() + seconds)


class Translator:
    """Appels Gemini (endpoint compatible OpenAI), repli de modèle et reprise sur quota."""

    def __init__(self, api_key: str, models: tuple[str, ...], timeout: int = 180, rpm: int = 15) -> None:
        if not api_key:
            raise CommandError(
                "aucune clé API : exportez GEMINI_API_KEY (ou renseignez-la dans .env)"
            )
        self.api_key = api_key
        self.models = tuple(models)
        self.timeout = timeout
        self.queue = ModelQueue(self.models, rpm=rpm)
        self._lock = threading.Lock()
        self.model = models[0]
        self.attempts = 0

    # ------------------------------------------------------------------ #
    def _post(self, payload: dict) -> dict:
        request = urllib.request.Request(
            GEMINI_OPENAI_URL,
            data=json.dumps(payload).encode("utf-8"),
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            },
        )
        with urllib.request.urlopen(request, timeout=self.timeout) as response:
            return json.loads(response.read().decode("utf-8"))

    def _call(self, system: str, user: str, model: str) -> str:
        data = self._post(
            {
                "model": model,
                "temperature": 0,
                "messages": [
                    {"role": "system", "content": system},
                    {"role": "user", "content": user},
                ],
            }
        )
        return (data["choices"][0]["message"]["content"] or "").strip()

    def _model_order(self) -> tuple[str, ...]:
        with self._lock:
            favourite = self.model
        return (favourite,) + tuple(m for m in self.models if m != favourite)

    def _remember(self, model: str) -> None:
        with self._lock:
            self.model = model

    # ------------------------------------------------------------------ #
    def translate_many(self, items: list[tuple[str, str]]) -> dict[str, Entry]:
        """Traduit un lot. Renvoie une entrée par PUID (ok, latex_mismatch ou error)."""
        started = time.time()
        user = "\n".join(f"@@ITEM {i}@@\n{text}\n" for i, (_puid, text) in enumerate(items, start=1))
        expected = list(range(1, len(items) + 1))
        last_error = "aucune réponse"

        for attempt in range(6):
            with self._lock:
                preferred = self.model
            model = self.queue.acquire(preferred)
            if model is None:
                break
            try:
                raw = self._call(SYSTEM_BATCH, user, model)
            except urllib.error.HTTPError as exc:
                last_error = f"HTTP {exc.code}"
                if exc.code == 429:
                    # quota atteint : on ralentit tout le monde de 60 % plutôt que
                    # d'exclure un modèle pendant une minute (le débit reste utile)
                    spacing = self.queue.widen()
                    self.queue.penalise(model, 1.5)
                    logger_debug = f"quota → espacement {spacing:.1f} s"
                    self.last_pacing = logger_debug
                elif exc.code in (500, 502, 503, 504):
                    self.queue.cool_down(3)
                    self.queue.penalise(model, 8)
                else:
                    self.queue.penalise(model, 120)
                continue
            except Exception as exc:
                last_error = str(exc)[:100]
                self.queue.penalise(model, 5)
                continue

            parsed = parse_batch(raw, expected)
            if not parsed:
                last_error = "aucun repère @@ITEM@@ dans la réponse"
                continue

            self.queue.narrow()
            with self._lock:
                self.model = model
            entries: dict[str, Entry] = {}
            for position, (puid, original) in enumerate(items, start=1):
                candidate = parsed.get(position, "")
                if candidate and fingerprint(candidate) == fingerprint(original):
                    entries[puid] = Entry(puid, "ok", candidate, original, model,
                                          time.time() - started, attempt + 1)
                else:
                    entries[puid] = Entry(puid, "latex_mismatch", None, original, model,
                                          time.time() - started, attempt + 1,
                                          note="lot incomplet : énoncé manquant ou LaTeX modifié")
            return entries

        return {
            puid: Entry(puid, "error", None, original, "", time.time() - started, 6, note=last_error)
            for puid, original in items
        }

    def translate_one(self, puid: str, text: str) -> Entry:
        """Reprise individuelle : dernier recours pour un énoncé récalcitrant."""
        started = time.time()
        last_error = "aucune réponse"
        for attempt in range(4):
            with self._lock:
                preferred = self.model
            model = self.queue.acquire(preferred)
            if model is None:
                break
            try:
                raw = self._call(SYSTEM_ONE, text, model)
            except urllib.error.HTTPError as exc:
                last_error = f"HTTP {exc.code}"
                if exc.code == 429:
                    self.queue.widen()
                    self.queue.penalise(model, 1.5)
                else:
                    self.queue.penalise(model, 10)
                continue
            except Exception as exc:
                last_error = str(exc)[:100]
                self.queue.penalise(model, 5)
                continue

            if raw and fingerprint(raw) == fingerprint(text):
                self.queue.narrow()
                with self._lock:
                    self.model = model
                return Entry(puid, "ok", raw, text, model, time.time() - started, attempt + 1)
            last_error = "LaTeX modifié"
        return Entry(puid, "latex_mismatch", None, text, "", time.time() - started, 4, note=last_error)


class Command(BaseCommand):
    help = "Traduit les énoncés du corpus importé en français (API Gemini), avec cache reprenable."

    def add_arguments(self, parser):
        parser.add_argument("--file", default=DEFAULT_FILE, help="JSONL source (anglais)")
        parser.add_argument("--cache", default="var/translations.jsonl", help="cache reprenable")
        parser.add_argument("--workers", type=int, default=6, help="requêtes simultanées (la cadence est fixée par --rpm)")
        parser.add_argument("--rpm", type=int, default=15, help="requêtes/minute et par modèle (palier gratuit : 15)")
        parser.add_argument("--rounds", type=int, default=2, help="passes par lots avant les reprises individuelles")
        parser.add_argument("--batch", type=int, default=5, help="énoncés par requête (défaut : 5)")
        parser.add_argument("--limit", type=int, default=0, help="ne traiter que N énoncés")
        parser.add_argument("--model", default="", help="modèle de départ")
        parser.add_argument("--sources", default="", help="restreindre à certaines sources (ex. imo,usamo)")
        parser.add_argument("--apply", action="store_true", help="écrit les traductions en base")
        parser.add_argument("--revert", action="store_true", help="avec --apply : remet l'anglais d'origine")
        parser.add_argument("--rewrite", action="store_true", help="retraduire même ce qui est en cache")
        parser.add_argument(
            "--polish",
            action="store_true",
            help="avant --apply : traduire les mots anglais restés dans les \\text{...}",
        )
        parser.add_argument("--timeout", type=int, default=180, help="délai par requête, en secondes")
        parser.add_argument("--singles", action="store_true", help="dernier recours : reprises une par une")

    # ------------------------------------------------------------------ #
    def handle(self, *args, **options):
        cache_path = Path(options["cache"])
        cache_path.parent.mkdir(parents=True, exist_ok=True)

        if options["polish"]:
            self._polish(cache_path)

        if options["apply"]:
            self._apply(cache_path, revert=options["revert"])
            return

        path = Path(options["file"])
        if not path.exists():
            raise CommandError(f"fichier introuvable : {path}")

        wanted = {s.strip().lower() for s in options["sources"].split(",") if s.strip()}
        pending, _counters, _per_source = select_records(path, sources=wanted or None, limit=options["limit"])
        english = {puid: (record.get("problem") or "").strip() for record, puid, _, _ in pending}

        cached = {} if options["rewrite"] else self._read_cache(cache_path)
        todo = [(puid, text) for puid, text in english.items() if cached.get(puid, {}).get("status") != "ok"]

        self.stdout.write(self.style.MIGRATE_HEADING("Traduction du corpus"))
        self.stdout.write(f"  énoncés sélectionnés ...... {len(english)}")
        self.stdout.write(f"  déjà traduits (cache) ..... {len(english) - len(todo)}")
        self.stdout.write(f"  à traduire ................ {len(todo)}")
        if not todo:
            self.stdout.write(self.style.SUCCESS("rien à faire : le cache est à jour."))
            self.stdout.write("écriture en base : python manage.py translate_corpus --apply")
            return

        api_key = getattr(settings, "GEMINI_API_KEY", "") or os.environ.get("GEMINI_API_KEY", "")
        models = (options["model"],) if options["model"] else DEFAULT_MODELS
        translator = Translator(api_key, models, timeout=options["timeout"], rpm=options["rpm"])

        batch_size = max(1, options["batch"])
        started = time.time()
        counters = {"ok": 0, "latex_mismatch": 0, "error": 0}

        chunks = self._chunks(todo, batch_size)
        for round_index in range(1, max(1, options["rounds"]) + 1):
            self.stdout.write("")
            self.stdout.write(self.style.MIGRATE_HEADING(
                f"Passe {round_index}/{options['rounds']} — {len(chunks)} lot(s) de {batch_size}"
            ))
            entries = self._run_pass(
                translator, chunks, cache_path, counters,
                workers=max(1, options["workers"]), started=started, total=len(todo),
            )
            stuck = [(puid, english[puid]) for puid, entry in entries.items() if entry.status != "ok"]
            if not stuck:
                break
            chunks = self._chunks(stuck, batch_size)

        if stuck and options["singles"]:
            self.stdout.write("")
            self.stdout.write(self.style.WARNING(
                f"reprises individuelles sur {len(stuck)} énoncé(s)…"
            ))
            self._run_pass(
                translator, stuck, cache_path, counters,
                workers=min(4, max(1, options["workers"])), started=started,
                total=len(stuck), mode="single",
            )

        self.stdout.write("")
        self.stdout.write(self.style.SUCCESS(
            f"terminé : {counters['ok']} traduction(s) acceptée(s), "
            f"{counters['latex_mismatch']} conservée(s) en anglais, {counters['error']} échec(s) réseau."
        ))
        self.stdout.write(f"cache : {cache_path}")
        self.stdout.write("écriture en base : python manage.py translate_corpus --apply")

    # ------------------------------------------------------------------ #
    @staticmethod
    def _chunks(items, size):
        return [list(items[i:i + size]) for i in range(0, len(items), size)]

    def _run_pass(self, translator, chunks, cache_path, counters, *, workers, started, total, mode="batch"):
        """Exécute une passe et renvoie les entrées produites, indexées par PUID."""
        produced: dict[str, Entry] = {}
        processed = 0

        with cache_path.open("a", encoding="utf-8") as sink:
            with ThreadPoolExecutor(max_workers=workers) as pool:
                if mode == "single":
                    # `chunks` est une liste de couples (puid, texte) : un appel par énoncé
                    futures = {
                        pool.submit(translator.translate_one, puid, text): (puid, text)
                        for puid, text in chunks
                    }
                else:
                    futures = {pool.submit(translator.translate_many, chunk): chunk for chunk in chunks}

                for future in as_completed(futures):
                    try:
                        batch_entries = future.result()
                    except Exception as exc:  # noqa: BLE001 — une passe ne doit jamais mourir
                        self.stderr.write(f"  ! lot abandonné : {exc}")
                        continue

                    if mode == "single":
                        items = {batch_entries.puid: batch_entries}
                    else:
                        items = batch_entries

                    for puid, entry in items.items():
                        if entry.status == "ok" or puid not in produced:
                            produced[puid] = entry
                        sink.write(json.dumps(entry.as_json(), ensure_ascii=False) + "\n")
                        counters[entry.status] += 1
                        processed += 1
                    sink.flush()

                    elapsed = time.time() - started
                    rate = processed / elapsed if elapsed else 0
                    done = counters["ok"] + counters["latex_mismatch"] + counters["error"]
                    remaining = max(0, total - processed)
                    eta = remaining / rate if rate else 0
                    self.stdout.write(
                        f"  {processed}/{total} · {counters['ok']} ok · "
                        f"{counters['latex_mismatch']} à reprendre · {counters['error']} échec(s) · "
                        f"{rate:.2f} énoncé/s · espacement {translator.queue.spacing:.1f} s · reste ~{eta/60:.0f} min"
                    )
        return produced

    # ------------------------------------------------------------------ #
    def _read_cache(self, cache_path: Path) -> dict[str, dict]:
        entries: dict[str, dict] = {}
        if not cache_path.exists():
            return entries
        with cache_path.open(encoding="utf-8") as handle:
            for line in handle:
                line = line.strip()
                if not line:
                    continue
                try:
                    item = json.loads(line)
                except json.JSONDecodeError:
                    continue
                entries[item["puid"]] = item
        return entries

    def _polish(self, cache_path: Path) -> None:
        """Réécrit le cache : ``\\text{if}`` → ``\\text{si}``, sans toucher aux maths."""
        entries = self._read_cache(cache_path)
        if not entries:
            raise CommandError(f"cache vide : {cache_path}")
        touched = 0
        fixed_entries = 0
        for entry in entries.values():
            if entry.get("status") != "ok" or not entry.get("fr"):
                continue
            polished, changes = polish_text_mode(entry["fr"])
            if changes:
                entry["fr"] = polished
                fixed_entries += 1
                touched += changes
        if not fixed_entries:
            self.stdout.write("polissage : rien à corriger.")
            return
        with cache_path.open("w", encoding="utf-8") as handle:
            for entry in entries.values():
                handle.write(json.dumps(entry, ensure_ascii=False) + "\n")
        self.stdout.write(self.style.SUCCESS(
            f"polissage : {touched} bloc(s) \\text{{...}} traduits dans {fixed_entries} énoncé(s)."
        ))

    def _apply(self, cache_path: Path, *, revert: bool) -> None:
        entries = self._read_cache(cache_path)
        if not entries:
            raise CommandError(f"cache vide : {cache_path} (lancez d'abord la traduction)")
        usable = {p: e for p, e in entries.items() if e.get("status") == "ok" and e.get("fr")}
        if not usable:
            raise CommandError("aucune traduction acceptée dans le cache")

        problems = {p.puid: p for p in Problem.objects.filter(puid__in=list(usable))}
        missing = sorted(set(usable) - set(problems))
        touched = 0

        with transaction.atomic():
            for puid, entry in usable.items():
                problem = problems.get(puid)
                if problem is None:
                    continue
                target = entry["en"] if revert else entry["fr"]
                if problem.statement_tex.strip() == target.strip():
                    continue
                problem.statement_tex = target
                problem.save(update_fields=["statement_tex", "updated_at"])
                touched += 1

        action = "remis en anglais" if revert else "traduits en français"
        self.stdout.write(self.style.SUCCESS(f"{touched} énoncé(s) {action} ({len(usable)} dans le cache)."))
        if missing:
            self.stdout.write(self.style.WARNING(
                f"{len(missing)} fiche(s) absentes de la base (import incomplet ?) — ex. {missing[:3]}"
            ))
