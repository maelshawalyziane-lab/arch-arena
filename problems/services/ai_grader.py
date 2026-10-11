"""
The AI verification gate.

Pipeline (mirrors the spec's Steps A-D):

    A. the caller has already fetched ``Solution.official_tex`` from the database
    B. the student's submission text arrives here
    C. ``build_prompt`` assembles the strict grader payload and it is sent to an
       LLM (OpenAI / Anthropic) -- or to the deterministic offline grader when no
       API key is configured
    D. the JSON verdict is parsed into a :class:`GraderVerdict`, which the caller
       (``problems.services.verification``) turns into UserSubmission +
       UserProgress rows.

Two engines
-----------
* ``live``    - a real LLM grades the proof against the official solution.
* ``offline`` - a deterministic lexical plausibility grader.  It exists so the
  platform (and its test-suite / demo) works with no API key and no network.  It
  is **not** a mathematical verifier and the UI labels it as such; it can be
  disabled by setting ``AI_MODE=live``.
"""

from __future__ import annotations

import json
import logging
import random
import re
import threading
import time
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from typing import Any

from django.conf import settings

from .tex import to_plain_text

logger = logging.getLogger(__name__)

OPENAI_URL = "https://api.openai.com/v1/chat/completions"
ANTHROPIC_URL = "https://api.anthropic.com/v1/messages"
#: Gemini expose un endpoint compatible OpenAI : même charge utile, même analyse.
GEMINI_URL = "https://generativelanguage.googleapis.com/v1beta/openai/chat/completions"

DEFAULT_MODELS = {
    "openai": "gpt-4o",
    "anthropic": "claude-sonnet-4-5",
    "gemini": "gemini-3.5-flash-lite",
}


class GraderUnavailable(RuntimeError):
    """Raised when a live grader was required but could not be reached."""


# --------------------------------------------------------------------------- #
# the grader prompt (Step C) -- kept byte-stable so verdicts are reproducible.
#
# WARNING: this text is the verbatim French prompt from the specification.
# ``build_prompt`` substitutes the three placeholders with plain string
# replacement (NOT str.format) because the literal JSON example below contains
# braces that str.format would try to read as replacement fields.  If you edit
# the prompt, keep the three ``{...}`` placeholders spelled exactly like this:
# ``{statement}``, ``{official_tex}``, ``{user_submission}``.
# --------------------------------------------------------------------------- #
SYSTEM_PROMPT = """Rôle : Tu es un correcteur expert des Olympiades Internationales de Mathématiques (IMO).
Tâche : Évaluer si le plan de solution ou la preuve soumis contient une logique mathématique valide et arrive au bon résultat par rapport à la solution officielle.
Données : Énoncé={statement}, Solution officielle={official_tex}, Soumission étudiant={user_submission}.
Réponds UNIQUEMENT en JSON strict sans balises markdown :
{
  "passed": true ou false,
  "feedback": "2-3 phrases explicatives."
}"""


class GraderResponseError(GraderUnavailable, ValueError):
    """
    The provider answered, but the reply was not a usable JSON verdict.

    It deliberately inherits from *both* ``GraderUnavailable`` (so callers record
    the attempt as PENDING - a malformed model reply is never the student's fault)
    and ``ValueError`` (so it still reads as a parse error to callers/tests that
    expect one).
    """


@dataclass
class GraderVerdict:
    passed: bool
    feedback: str
    engine: str
    latency_ms: int
    raw: dict[str, Any] = field(default_factory=dict)
    degraded: bool = False  # True when the offline plausibility grader was used


# --------------------------------------------------------------------------- #
# prompt construction
# --------------------------------------------------------------------------- #
def build_prompt(*, statement: str, official_tex: str, user_submission: str, puid: str = "") -> tuple[str, str]:
    """Return ``(system_prompt, user_prompt)`` for the grader."""
    # NOTE: str.format() cannot be used here - the prompt contains a literal JSON
    # example ({"passed": ..., "feedback": ...}) whose braces would be read as
    # replacement fields.  Placeholders are substituted literally instead, so the
    # prompt text stays exactly as specified (no brace escaping).
    system = (
        SYSTEM_PROMPT.replace("{statement}", statement.strip())
        .replace("{official_tex}", official_tex.strip())
        .replace("{user_submission}", user_submission.strip())
    )
    user = (
        f"<problem id={puid!r}>\n"
        "Corrige la soumission ci-dessus selon les règles et réponds uniquement avec le JSON demandé."
    )
    return system, user


# --------------------------------------------------------------------------- #
# JSON verdict parsing (Step D)
# --------------------------------------------------------------------------- #
_FENCE_RE = re.compile(r"^\s*```(?:json)?|```\s*$", re.MULTILINE)

_TRUTHY = {
    "true", "yes", "pass", "passed", "1", "correct", "accept", "accepted",
    # French wording, since the grader answers in French
    "vrai", "oui", "valide", "validé", "validee", "accepte", "accepté", "réussi", "reussi",
}
_FALSY = {
    "false", "no", "fail", "failed", "0", "incorrect", "reject", "rejected",
    # French wording
    "faux", "non", "invalide", "refuse", "refusé", "rejete", "rejeté", "échoué", "echoue",
}


def parse_verdict(text: str) -> tuple[bool, str]:
    """
    Extract ``{"passed": bool, "feedback": str}`` from a model response.

    Tolerates markdown fences, leading prose, and "passed": "true" string forms.
    Raises :class:`GraderResponseError` (a ``GraderUnavailable`` *and* a
    ``ValueError``) when nothing usable can be found, so the caller stores the
    attempt as PENDING instead of failing the student.
    """
    if not text:
        raise GraderResponseError("empty grader response")
    cleaned = _FENCE_RE.sub("", text).strip()

    payload: dict[str, Any] | None = None
    try:
        payload = json.loads(cleaned)
    except json.JSONDecodeError:
        start, end = cleaned.find("{"), cleaned.rfind("}")
        if start != -1 and end > start:
            try:
                payload = json.loads(cleaned[start : end + 1])
            except json.JSONDecodeError:
                payload = None
    if not isinstance(payload, dict):
        raise GraderResponseError(
            f"could not parse JSON verdict from grader response: {text[:200]!r}"
        )

    # The spec's schema, plus a couple of tolerated aliases.
    raw_flag = payload.get("passed", payload.get("pass", payload.get("verdict")))
    if isinstance(raw_flag, bool):
        passed = raw_flag
    elif isinstance(raw_flag, (int, float)):
        passed = bool(raw_flag)
    elif isinstance(raw_flag, str):
        lowered = raw_flag.strip().lower()
        passed = lowered in _TRUTHY
        if lowered not in _TRUTHY | _FALSY:
            raise GraderResponseError(f"unrecognised verdict flag: {raw_flag!r}")
    else:
        raise GraderResponseError("grader response has no 'passed' field")

    feedback = str(payload.get("feedback") or payload.get("explanation") or "").strip()
    feedback = feedback or ("Accepté : la soumission correspond à la solution officielle." if passed
                            else "Refusé : la soumission n'établit pas encore la conclusion demandée.")
    return passed, feedback[:4000]


# --------------------------------------------------------------------------- #
# transport
# --------------------------------------------------------------------------- #
def _post_json(url: str, payload: dict[str, Any], headers: dict[str, str], timeout: int) -> dict[str, Any]:
    request = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json", **headers},
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=timeout) as response:  # noqa: S310 (fixed https URLs)
        return json.loads(response.read().decode("utf-8"))


def _sleep_backoff(attempt: int) -> None:
    time.sleep(min(8.0, (2**attempt) * 0.5) + random.random() * 0.25)


def _call_openai(system: str, user: str, model: str) -> tuple[str, dict[str, Any]]:
    payload = {
        "model": model,
        "temperature": 0,
        "max_tokens": settings.AI_MAX_OUTPUT_TOKENS,
        "response_format": {"type": "json_object"},
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
    }
    headers = {"Authorization": f"Bearer {settings.OPENAI_API_KEY}"}
    data = _post_json(OPENAI_URL, payload, headers, settings.AI_TIMEOUT_SECONDS)
    choices = data.get("choices") or []
    if not choices:
        raise GraderUnavailable(f"OpenAI returned no choices: {str(data)[:200]}")
    content = (choices[0].get("message") or {}).get("content") or ""
    return content, {"provider": "openai", "model": model, "usage": data.get("usage")}


def _call_gemini(system: str, user: str, model: str) -> tuple[str, dict[str, Any]]:
    """Même contrat que ``_call_openai``, sur l'endpoint compatible OpenAI de Gemini."""
    payload = {
        "model": model,
        "temperature": 0,
        "max_tokens": settings.AI_MAX_OUTPUT_TOKENS,
        "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}],
    }
    headers = {"Authorization": f"Bearer {settings.GEMINI_API_KEY}"}
    data = _post_json(GEMINI_URL, payload, headers, settings.AI_TIMEOUT_SECONDS)
    text = (data["choices"][0]["message"]["content"] or "").strip()
    return text, {"provider": "gemini", "model": model, "usage": data.get("usage")}


def _call_anthropic(system: str, user: str, model: str) -> tuple[str, dict[str, Any]]:
    payload = {
        "model": model,
        "max_tokens": settings.AI_MAX_OUTPUT_TOKENS,
        "temperature": 0,
        "system": system,
        # Prefilling the assistant turn with "{" forces a bare JSON object back.
        "messages": [
            {"role": "user", "content": user},
            {"role": "assistant", "content": "{"},
        ],
    }
    headers = {
        "x-api-key": settings.ANTHROPIC_API_KEY,
        "anthropic-version": "2023-06-01",
    }
    data = _post_json(ANTHROPIC_URL, payload, headers, settings.AI_TIMEOUT_SECONDS)
    blocks = data.get("content") or []
    text = "".join(block.get("text", "") for block in blocks if isinstance(block, dict)).strip()
    # The continuation of a prefilled assistant turn omits the "{" we seeded, so
    # restore it to make the fragment parseable JSON again.
    if text and not text.startswith("{"):
        text = "{" + text
    return text, {"provider": "anthropic", "model": model, "usage": data.get("usage")}


# --------------------------------------------------------------------------- #
# offline deterministic grader
# --------------------------------------------------------------------------- #
_STOPWORDS = {
    "the", "and", "for", "that", "with", "this", "then", "there", "which", "have", "from",
    "such", "when", "also", "into", "will", "each", "they", "them", "than", "over", "note",
    "let", "prove", "proof", "solution", "problem", "case", "cases", "since", "because",
    "hence", "therefore", "thus", "so", "we", "is", "are", "be", "by", "of", "in", "on",
    "to", "as", "it", "at", "or", "if", "not", "all", "any", "some", "can", "need", "must",
    "get", "gets", "give", "gives", "show", "shown", "used", "using", "use", "one", "two",
    "every", "exists", "exist", "obtain", "yields", "hold", "holds", "true", "equal",
    # French
    "le", "la", "les", "un", "une", "des", "du", "de", "au", "aux", "et", "ou", "est",
    "sont", "soit", "soient", "que", "qui", "quoi", "dont", "pour", "par", "dans", "sur",
    "avec", "sans", "donc", "alors", "ainsi", "tout", "toute", "tous", "toutes", "cette",
    "ce", "cet", "ces", "son", "sa", "ses", "leur", "leurs", "nous", "vous", "ils",
    "elles", "on", "il", "elle", "plus", "moins", "aussi", "comme", "mais", "si", "ne",
    "pas", "être", "etre", "avoir", "fait", "faire", "peut", "peuvent", "même", "meme",
    "puis", "lorsque", "quand", "car", "or", "d'un", "d'une",
}

# Latin letters with accents are part of the word class, otherwise French prose
# would be tokenised into nothing ("démontrer" -> "montrer").
_TOKEN_RE = re.compile(r"[A-Za-zÀ-ÖØ-öø-ÿ][A-Za-zÀ-ÖØ-öø-ÿ'\-]{2,}|\d{1,4}|\\[a-zA-Z]{2,}")

# Proof-structure vocabulary, English *and* French (the UI and the grader speak
# French, but students may write in either language).
_STRUCTURE_MARKERS = (
    # English — connecteurs logiques courants (une rédaction correcte en contient
    # toujours plusieurs, même sans employer « therefore » ou « hence »)
    "since", "because", "follows", "it follows", "note that", "we get", "we obtain",
    "we have", "yields", "gives ", "obtain ", "there exists", "for all", "for every",
    "let us", "define", "denote", "consider", "must be", "if and only if", "at most",
    "at least", "instead", "otherwise", "so that", "such that", "ge ", "le ", "neq",
    # English — vocabulaire de preuve
    "wlog", "without loss", "assume", "contradiction", "induction", "lemma", "claim",
    "suppose", "pigeonhole", "modulo", "mod ", "congruent", "=>", "implies", "qed",
    "therefore", "hence", "thus", "step", "case", "finally", "suffices",
    # Français — connecteurs logiques
    "puisque", "car ", "on obtient", "on en déduit", "on a ", "il existe", "pour tout",
    "quel que soit", "définissons", "definissons", "notons", "considérons", "considerons",
    "au plus", "au moins", "si et seulement si", "ce qui", "entraîne", "entraine",
    "de sorte que", "tel que", "sinon", "à savoir", "a savoir",
    # Français — vocabulaire de preuve
    "sans perte de généralité", "sans perte de generalite", "supposons", "suppose",
    "hypothèse", "hypothese", "contradiction", "absurde", "récurrence", "recurrence",
    "lemme", "affirmation", "montrons", "démontrer", "demontrer", "donc", "d'où", "dou",
    "par conséquent", "par consequent", "ainsi", "étape", "etape", "cas", "enfin",
    "il suffit", "vérifie", "verifie", "c.q.f.d", "cqfd",
)


def _tokens(text: str) -> list[str]:
    return [t.lower() for t in _TOKEN_RE.findall(text)]


def _salient(tokens: list[str]) -> set[str]:
    return {t for t in tokens if t not in _STOPWORDS and len(t) >= 3}


def _offline_grade(*, statement: str, official_tex: str, user_submission: str) -> GraderVerdict:
    """
    Deterministic plausibility grader used when no LLM is configured.

    Signals (all reported in the feedback so the student can see the reasoning):
      * structural markers of a proof attempt
      * amount of real mathematics (LaTeX tokens / multi-character expressions)
      * coverage of the salient vocabulary of the official solution
    """
    started = time.perf_counter()
    submission = user_submission.strip()
    lowered = submission.lower()
    sub_tokens = _tokens(submission)
    gt_salient = _salient(_tokens(official_tex))
    sub_salient = _salient(sub_tokens)

    notes: list[str] = []

    # 1. length gate
    if len(submission) < 120:
        notes.append(f"trop court ({len(submission)} caractères) pour être un plan de solution")

    # 2. structural markers
    markers = sorted({m for m in _STRUCTURE_MARKERS if m in lowered})
    math_density = submission.count("$") + submission.count("\\")

    # 3. vocabulary coverage of the reference solution
    coverage = (len(gt_salient & sub_salient) / len(gt_salient)) if gt_salient else 0.0
    missing = sorted(gt_salient - sub_salient)[:8]

    # Thresholds are deliberately calibrated so that a *short but genuine* proof of
    # a short problem still passes (a 250-character complete argument is a real
    # solution), while a long restatement of the problem cannot: coverage of the
    # reference solution's distinctive vocabulary does the heavy lifting.
    word_count = len(re.findall(r"[A-Za-z][A-Za-z'\-]*", submission))
    # The length bar scales with the reference solution: a complete two-line proof
    # of a short warm-up problem is not "too short" just because the problem is easy.
    reference_chars = max(len(official_tex.strip()), 1)
    required_chars = min(240, max(120, int(0.6 * reference_chars)))
    long_enough = len(submission) >= required_chars or word_count >= 45
    enough_markers = len(markers) >= 2
    coverage_ok = coverage >= 0.30
    math_ok = math_density >= 3 or coverage >= 0.5
    passed = long_enough and enough_markers and coverage_ok and math_ok

    if passed:
        feedback = (
            "Vérification heuristique hors ligne (aucun LLM configuré) : plan accepté. "
            f"Texte substantiel ({len(submission)} caractères), marqueurs de preuve présents "
            f"({', '.join(markers[:5])}) et {coverage:.0%} du vocabulaire distinctif de la "
            "solution officielle retrouvé. Configurez AI_MODE=live avec une clé API pour une "
            "correction mathématique réelle."
        )
    else:
        reasons = []
        if not long_enough:
            reasons.append(
                f"trop court ({len(submission)} caractères, {word_count} mots ; "
                f"{required_chars} caractères attendus pour un énoncé de cette taille)"
            )
        if not enough_markers:
            reasons.append(f"peu de marqueurs de preuve ({', '.join(markers) or 'aucun'})")
        if not coverage_ok:
            hint = f" ; la solution de référence s'appuie sur : {', '.join(missing)}" if missing else ""
            reasons.append(
                f"idées clés de la solution officielle absentes (recouvrement {coverage:.0%}{hint})"
            )
        if not math_ok:
            reasons.append("aucune mathématique substantielle rédigée")
        feedback = (
            "Vérification heuristique hors ligne (aucun LLM configuré) : soumission refusée — "
            + " ; ".join(reasons)
            + ". Ce correcteur ne mesure que la structure et le recouvrement de vocabulaire ; "
            "configurez un vrai correcteur LLM pour une vérification mathématique."
        )

    latency = int((time.perf_counter() - started) * 1000)
    return GraderVerdict(
        passed=passed,
        feedback=feedback,
        engine="offline-heuristic",
        latency_ms=latency,
        raw={
            "engine": "offline-heuristic",
            "markers": markers,
            "coverage": round(coverage, 4),
            "chars": len(submission),
            "math_density": math_density,
            "missing_terms": missing,
        },
        degraded=True,
    )


# --------------------------------------------------------------------------- #
# public entry point
# --------------------------------------------------------------------------- #
#: Quelle variable d'environnement porte la clé de chaque fournisseur.
_API_KEY_SETTING = {
    "openai": "OPENAI_API_KEY",
    "anthropic": "ANTHROPIC_API_KEY",
    "gemini": "GEMINI_API_KEY",
}


# --------------------------------------------------------------------------- #
# disjoncteur : ne pas attendre un quota épuisé à chaque soumission
# --------------------------------------------------------------------------- #
_BREAKER_LOCK = threading.Lock()
_BREAKER = {"failures": 0, "blocked_until": 0.0}


def _breaker_blocked() -> bool:
    with _BREAKER_LOCK:
        return time.monotonic() < _BREAKER["blocked_until"]


def _breaker_record(success: bool) -> None:
    with _BREAKER_LOCK:
        if success:
            _BREAKER["failures"] = 0
            _BREAKER["blocked_until"] = 0.0
            return
        _BREAKER["failures"] += 1
        if _BREAKER["failures"] >= max(1, int(getattr(settings, "AI_BREAKER_THRESHOLD", 2))):
            _BREAKER["blocked_until"] = time.monotonic() + max(
                5, int(getattr(settings, "AI_BREAKER_SECONDS", 300))
            )


def breaker_state() -> str:
    """Pour l'affichage/diagnostic : état lisible du disjoncteur."""
    with _BREAKER_LOCK:
        remaining = _BREAKER["blocked_until"] - time.monotonic()
    return f"ouvert encore {int(remaining)} s" if remaining > 0 else "fermé"


def resolve_engine(mode: str | None = None) -> str:
    """Decide between ``live`` and ``offline`` from settings/env overrides."""
    mode = (mode or settings.AI_MODE or "auto").lower()
    if mode == "offline":
        return "offline"
    has_key = bool(getattr(settings, _API_KEY_SETTING[settings.AI_PROVIDER], ""))
    if mode == "live":
        if not has_key:
            raise GraderUnavailable(
                f"AI_MODE=live mais aucune clé API n'est configurée pour le fournisseur "
                f"{settings.AI_PROVIDER!r}."
            )
        return "live"
    return "live" if has_key else "offline"


def grader_label() -> str:
    """Human-readable engine label for the UI badge."""
    try:
        engine = resolve_engine()
    except GraderUnavailable:
        return "indisponible"
    if engine == "offline":
        return "correcteur heuristique hors ligne (aucune clé API configurée)"
    return f"{settings.AI_PROVIDER}:{settings.AI_MODEL or DEFAULT_MODELS.get(settings.AI_PROVIDER, 'default')}"


def _fallback_verdict(
    *,
    statement: str,
    official_tex: str,
    user_submission: str,
    reason: str,
) -> GraderVerdict:
    """Évaluation de repli : heuristique structurelle, annoncée comme telle.

    Un élève qui soumet une preuve doit toujours obtenir une réponse. Quand le
    correcteur en ligne est injoignable (clé absente, quota, panne), on rend le
    verdict hors ligne **en le signalant** au lieu de renvoyer une erreur 503 ;
    l'interface affiche le moteur réellement utilisé.
    """
    verdict = _offline_grade(
        statement=statement, official_tex=official_tex, user_submission=user_submission
    )
    note = (
        "⚠️ Correcteur IA en ligne indisponible — évaluation de repli (analyse "
        "structurelle) : le verdict est provisoire"
    )
    if reason:
        note += f" [motif : {reason[:160]}]"
    return GraderVerdict(
        passed=verdict.passed,
        feedback=f"{note}\n\n{verdict.feedback}",
        engine=f"repli:{verdict.engine}",
        latency_ms=verdict.latency_ms,
        raw={**verdict.raw, "fallback_reason": reason[:400]},
    )


def grade_submission(
    *,
    puid: str,
    statement: str,
    official_tex: str,
    user_submission: str,
    mode: str | None = None,
) -> GraderVerdict:
    """
    Grade one submission.  Raises :class:`GraderUnavailable` if a live grader was
    requested but every attempt failed (the caller records the submission as
    PENDING instead of silently failing the student).
    """
    engine = resolve_engine(mode)
    if engine == "offline":
        return _offline_grade(
            statement=statement, official_tex=official_tex, user_submission=user_submission
        )

    # le disjoncteur évite d'attendre une API déjà en échec (quota épuisé, panne) :
    # on répond immédiatement par l'évaluation de repli, en l'annonçant clairement.
    if _breaker_blocked():
        return _fallback_verdict(
            statement=statement,
            official_tex=official_tex,
            user_submission=user_submission,
            reason=f"correcteur en ligne suspendu temporairement ({breaker_state()})",
        )

    provider = settings.AI_PROVIDER
    model = settings.AI_MODEL or DEFAULT_MODELS.get(provider, "")
    system, user = build_prompt(
        statement=statement, official_tex=official_tex, user_submission=user_submission, puid=puid
    )
    caller = {
        "openai": _call_openai,
        "anthropic": _call_anthropic,
        "gemini": _call_gemini,
    }.get(provider, _call_openai)

    started = time.perf_counter()
    last_error: Exception | None = None
    for attempt in range(settings.AI_MAX_RETRIES + 1):
        try:
            text, meta = caller(system, user, model)
            passed, feedback = parse_verdict(text)
            latency = int((time.perf_counter() - started) * 1000)
            logger.info(
                "graded puid=%s provider=%s model=%s passed=%s attempt=%d latency_ms=%d",
                puid, provider, model, passed, attempt + 1, latency,
            )
            _breaker_record(True)
            return GraderVerdict(
                passed=passed,
                feedback=feedback,
                engine=f"{provider}:{model}",
                latency_ms=latency,
                raw={**meta, "verdict_text": text[:2000], "attempts": attempt + 1},
            )
        except urllib.error.HTTPError as exc:  # 4xx/5xx: retry 5xx & 429
            body = ""
            try:
                body = exc.read().decode("utf-8", "replace")[:400]
            except Exception:  # pragma: no cover
                pass
            last_error = GraderUnavailable(f"HTTP {exc.code} from {provider}: {body}")
            logger.warning("grader HTTP error provider=%s code=%s body=%s", provider, exc.code, body)
            if exc.code in {400, 401, 403, 404, 422}:
                break  # configuration problem - retrying will not help
        except Exception as exc:  # noqa: BLE001 - network, timeout, JSON, parse errors
            last_error = exc
            logger.warning("grader attempt %d failed: %s", attempt + 1, exc)
        if attempt < settings.AI_MAX_RETRIES:
            _sleep_backoff(attempt)

    _breaker_record(False)
    if getattr(settings, "AI_FALLBACK", True):
        logger.warning("grader en ligne indisponible, évaluation de repli : %s", last_error)
        return _fallback_verdict(
            statement=statement,
            official_tex=official_tex,
            user_submission=user_submission,
            reason=str(last_error) if last_error else "échec du fournisseur",
        )
    raise GraderUnavailable(str(last_error) if last_error else "unknown grader failure")


def ping_grader() -> tuple[bool, str]:
    """Cheap configuration check used by `manage.py check_ai_setup` and the dashboard."""
    try:
        engine = resolve_engine()
    except GraderUnavailable as exc:
        return False, str(exc)
    if engine == "offline":
        return True, "correcteur heuristique hors ligne (passez AI_MODE=live + une clé API pour une vraie vérification)"
    label = f"{settings.AI_PROVIDER}:{settings.AI_MODEL or DEFAULT_MODELS.get(settings.AI_PROVIDER, 'default')}"
    return True, f"correcteur en ligne prêt : {label}"


def plain_terms_for_demo(text: str, limit: int = 12) -> list[str]:
    """Utility used by the demo scripts to show what the offline grader keys on."""
    return sorted(_salient(_tokens(to_plain_text(text))))[:limit]
