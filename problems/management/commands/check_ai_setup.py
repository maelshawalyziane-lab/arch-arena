"""
`manage.py check_ai_setup` — verify the grading configuration *and* the JSON contract.

    python manage.py check_ai_setup              # configuration + prompt/parse dry run
    python manage.py check_ai_setup --live       # also spend one real API call
    python manage.py check_ai_setup --json       # machine-readable output (CI)

Exit code is 0 when the grader is usable (offline counts: the demo still works),
1 when a live grader was requested and is broken.
"""

from __future__ import annotations

import json as jsonlib

from django.core.management.base import BaseCommand

from problems.services import ai_grader

# One short problem whose official solution is unambiguous, used to exercise the
# real provider end-to-end (statement -> prompt -> model -> strict JSON -> verdict).
PROBE = {
    "puid": "PROBE /1",
    "statement": (
        "Prove that for every positive integer $n$ the number "
        "$n(n+1)(n+2)$ is divisible by $6$."
    ),
    "official_tex": (
        "Among three consecutive integers one is divisible by $3$ and at least one is even, "
        "so $6 = 2\\cdot 3$ divides the product."
    ),
    "passing": (
        "Let $n$ be a positive integer and consider $n, n+1, n+2$. Among three consecutive "
        "integers exactly one is divisible by $3$, so $3$ divides the product. Moreover at "
        "least one of the three integers is even, so $2$ divides the product as well. Since "
        "$2$ and $3$ are coprime, their product $6$ divides $n(n+1)(n+2)$. Therefore the claim "
        "holds for every positive integer $n$."
    ),
    "failing": "It is obvious by symmetry and well known.",
}


class Command(BaseCommand):
    help = "Check the AI grader configuration, prompt and strict-JSON contract."

    def add_arguments(self, parser):
        parser.add_argument(
            "--live",
            action="store_true",
            help="Also make one real API call (spends tokens) to prove the key works.",
        )
        parser.add_argument("--json", action="store_true", help="Emit machine-readable JSON.")

    # ------------------------------------------------------------------ #
    def handle(self, *args, **options):
        from django.conf import settings

        as_json: bool = options["json"]
        checks: list[tuple[str, bool, str]] = []

        def check(name: str, ok: bool, detail: str = "") -> None:
            checks.append((name, ok, detail))
            if not as_json:
                mark = self.style.SUCCESS("PASS") if ok else self.style.WARNING("WARN")
                self.stdout.write(f"  [{mark}] {name}" + (f" — {detail}" if detail else ""))

        if not as_json:
            self.stdout.write(self.style.MIGRATE_HEADING("Configuration du correcteur IA"))

        # 1. engine resolution -------------------------------------------------
        try:
            engine = ai_grader.resolve_engine()
            check(
                "résolution du moteur",
                True,
                f"AI_MODE={settings.AI_MODE} -> {engine}"
                + ("" if engine == "live" else " (aucune clé : correcteur structurel hors ligne)"),
            )
        except ai_grader.GraderUnavailable as exc:
            engine = None
            check("résolution du moteur", False, str(exc))

        # 2. key presence ------------------------------------------------------
        provider = settings.AI_PROVIDER
        key = getattr(settings, ai_grader._API_KEY_SETTING.get(provider, "OPENAI_API_KEY"), "")
        if provider not in ai_grader._API_KEY_SETTING:
            check(
                "fournisseur",
                False,
                f"AI_PROVIDER={provider!r} non pris en charge (openai | anthropic | gemini)",
            )
        else:
            endpoint = {
                "openai": "api.openai.com",
                "anthropic": "api.anthropic.com",
                "gemini": "generativelanguage.googleapis.com (endpoint compatible OpenAI)",
            }[provider]
            check("fournisseur", True, f"{provider} → {endpoint}")
        check(
            "clé API",
            bool(key) or engine != "live",
            ("présente (" + key[:7] + "…" if key else "absente — correcteur hors ligne utilisé")
            if engine != "live"
            else ("présente" if key else "manquante alors que AI_MODE=live l'exige"),
        )

        # 3. model / timeout sanity ------------------------------------------
        model = settings.AI_MODEL or ai_grader.DEFAULT_MODELS.get(provider, "")
        check("modèle", bool(model), model or "aucun résolu")
        check(
            "délai & tentatives",
            settings.AI_TIMEOUT_SECONDS >= 5 and settings.AI_MAX_RETRIES >= 0,
            f"délai={settings.AI_TIMEOUT_SECONDS}s tentatives={settings.AI_MAX_RETRIES}",
        )

        # 4. prompt contract ---------------------------------------------------
        system, user = ai_grader.build_prompt(
            puid=PROBE["puid"],
            statement=PROBE["statement"],
            official_tex=PROBE["official_tex"],
            user_submission=PROBE["passing"],
        )
        # The prompt is the French specification text, kept verbatim: these checks are
        # contract checks on its structure (persona, the three injected data slots and
        # the strict-JSON demand), not style opinions.  See ai_grader.SYSTEM_PROMPT.
        requirements = {
            "persona : correcteur IMO (FR)": "correcteur expert" in system
            and "Olympiades Internationales de Mathématiques" in system,
            "solution officielle injectée comme référence": PROBE["official_tex"] in system,
            "copie de l'étudiant injectée telle quelle": PROBE["passing"] in system,
            "énoncé injecté": PROBE["statement"] in system,
            "JSON strict exigé": '"passed"' in system and '"feedback"' in system,
            "balises markdown interdites": "balises markdown" in system.lower(),
        }
        for name, ok in requirements.items():
            check(f"prompt: {name}", ok)

        # 5. strict-JSON parser ------------------------------------------------
        parser_cases = [
            ('{"passed": true, "feedback": "ok"}', (True, "ok"), "bare JSON"),
            ('```json\n{"passed": false, "feedback": "gap"}\n```', (False, "gap"), "fenced JSON"),
            ('Sure! {"passed": true, "feedback": "fine"}', (True, "fine"), "prose wrapper"),
            ('{"passed": "yes", "feedback": "x"}', (True, "x"), "stringified boolean"),
        ]
        for raw, expected, label in parser_cases:
            try:
                got = ai_grader.parse_verdict(raw)
            except Exception as exc:  # noqa: BLE001
                check(f"analyseur : {label}", False, f"{exc.__class__.__name__} levée : {exc}")
                continue
            check(f"analyseur : {label}", got == expected, f"{got!r}")
        try:
            ai_grader.parse_verdict("I cannot help with that.")
            check("analyseur : rejette le non-JSON", False, "aucune exception levée")
        except ai_grader.GraderUnavailable as exc:
            check(
                "analyseur : rejette le non-JSON",
                isinstance(exc, ValueError),
                "GraderResponseError (GraderUnavailable + ValueError) comme attendu",
            )

        # 6. offline dry run ---------------------------------------------------
        offline = ai_grader.grade_submission(
            puid=PROBE["puid"],
            statement=PROBE["statement"],
            official_tex=PROBE["official_tex"],
            user_submission=PROBE["passing"],
            mode="offline",
        )
        check(
            "correcteur hors ligne : accepte une vraie preuve",
            offline.passed,
            f"{offline.engine} · {offline.feedback[:90]}",
        )
        offline_bad = ai_grader.grade_submission(
            puid=PROBE["puid"],
            statement=PROBE["statement"],
            official_tex=PROBE["official_tex"],
            user_submission=PROBE["failing"],
            mode="offline",
        )
        check("correcteur hors ligne : refuse les arguments vagues", not offline_bad.passed)

        # 7. optional live call ------------------------------------------------
        live_ok = True
        if options["live"]:
            if engine != "live":
                check("appel réel", False, "AI_MODE=live injoignable — configurez d'abord une clé")
                live_ok = False
            else:
                if not as_json:
                    self.stdout.write("  … appel du fournisseur (une requête) …")
                try:
                    verdict = ai_grader.grade_submission(
                        puid=PROBE["puid"],
                        statement=PROBE["statement"],
                        official_tex=PROBE["official_tex"],
                        user_submission=PROBE["passing"],
                    )
                    check(
                        "appel réel : preuve acceptée",
                        verdict.passed,
                        f"{verdict.engine} · {verdict.latency_ms} ms · {verdict.feedback[:120]}",
                    )
                    live_ok = live_ok and verdict.passed
                except ai_grader.GraderUnavailable as exc:
                    live_ok = False
                    check("appel réel", False, str(exc)[:300])

        usable, message = ai_grader.ping_grader()
        if not as_json:
            self.stdout.write("")
            self.stdout.write(message)
        failures = [name for name, ok, _ in checks if not ok]
        if failures:
            if not as_json:
                self.stdout.write(self.style.ERROR(f"{len(failures)} contrôle(s) en échec : {failures}"))
            if as_json:
                self.stdout.write(
                    jsonlib.dumps({"usable": usable, "checks": checks, "failures": failures}, indent=2)
                )
            raise SystemExit(1)
        if as_json:
            self.stdout.write(jsonlib.dumps({"usable": usable, "checks": checks}, indent=2))
        else:
            self.stdout.write(self.style.SUCCESS(f"Les {len(checks)} contrôles passent."))
            if engine != "live":
                self.stdout.write(
                    "Remarque : la démonstration utilise le correcteur structurel hors ligne. "
                    "Exportez une clé API puis relancez `check_ai_setup --live` pour de vraies corrections."
                )
