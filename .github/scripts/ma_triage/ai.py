"""Tier 1 — optional GitHub Models assessment.

Sends a **bounded, sanitized** summary of the diagnostics and the issue text to
the GitHub Models inference API and asks for a small, strictly-typed JSON verdict.

This tier is entirely optional and defensive:
* gated behind ``config.AI_ENABLED`` (repo variable ``TRIAGE_AI_ENABLED``),
* every failure (network, rate limit, malformed output) returns ``None`` so the
  deterministic Tier-0 result is always posted regardless,
* only sanitized, length-capped text ever leaves the runner.
"""

from __future__ import annotations

import json
from typing import Any

import requests

from . import config
from .models import AIResult, Diagnostics
from .sanitize import fenced, inline

# Allowed values for the model's `category` field; anything else → "unknown".
_CATEGORIES = frozenset({"bug", "config", "user-error", "upstream", "unknown"})

# JSON schema for the model's structured output (OpenAI-compatible).
_OUTPUT_SCHEMA: dict[str, Any] = {
    "name": "triage_assessment",
    "strict": True,
    "schema": {
        "type": "object",
        "additionalProperties": False,
        "properties": {
            "summary": {"type": "string"},
            "likely_root_cause": {"type": "string"},
            "category": {
                "type": "string",
                "enum": ["bug", "config", "user-error", "upstream", "unknown"],
            },
            "confidence": {"type": "number"},
            "possibly_fixed_in_version": {"type": ["string", "null"]},
            "suggested_labels": {"type": "array", "items": {"type": "string"}},
            "user_message": {"type": "string"},
        },
        "required": [
            "summary",
            "likely_root_cause",
            "category",
            "confidence",
            "suggested_labels",
            "user_message",
        ],
    },
}

_SYSTEM_PROMPT = (
    "You are a triage assistant for the open-source project Music Assistant. "
    "You are given a sanitized diagnostics summary and an issue report. Judge "
    "whether the report looks like a genuine bug, a configuration/user error, or "
    "an upstream problem, and give a short, friendly, non-committal assessment. "
    "Be honest about uncertainty (reflect it in `confidence`). Never invent "
    "version numbers or facts not present in the input. Keep `user_message` warm "
    "and concise. Only suggest labels from the provided candidate list."
)


def _diag_summary(diag: Diagnostics) -> str:
    lines: list[str] = []
    sys = diag.system
    lines.append(
        "SYSTEM: "
        + inline(
            f"version={sys.version} python={sys.python_version} "
            f"platform={sys.platform} hass_addon={sys.hass_addon} "
            f"safe_mode={sys.safe_mode}"
        )
    )
    errored = diag.providers_in_error
    if errored:
        lines.append("PROVIDERS_IN_ERROR:")
        for provider in errored[: config.MAX_PROVIDERS_SHOWN]:
            lines.append(
                f"- {inline(provider.domain)}: {inline(provider.last_error) or 'unavailable'}"
            )
    if diag.exceptions:
        lines.append("TOP_EXCEPTIONS:")
        for exc in diag.exceptions[: config.MAX_EXCEPTIONS_SHOWN]:
            lines.append(
                f"- {inline(exc.exc_type)} x{exc.count}: {inline(exc.message)}"
            )
            if exc.traceback:
                lines.append(fenced(exc.traceback, max_len=600))
    return "\n".join(lines)


def build_messages(
    diag: Diagnostics, title: str, body: str, candidate_labels: list[str]
) -> list[dict[str, str]]:
    """Assemble the (bounded, sanitized) chat messages for the model."""
    user_content = (
        f"ISSUE TITLE: {inline(title, max_len=300)}\n\n"
        f"ISSUE BODY (excerpt):\n{fenced(body, max_len=2500)}\n\n"
        f"DIAGNOSTICS SUMMARY:\n{_diag_summary(diag)}\n\n"
        f"CANDIDATE LABELS: {', '.join(candidate_labels) or '(none)'}"
    )
    if len(user_content) > config.MAX_AI_INPUT_CHARS:
        user_content = user_content[: config.MAX_AI_INPUT_CHARS] + "\n…[truncated]"
    return [
        {"role": "system", "content": _SYSTEM_PROMPT},
        {"role": "user", "content": user_content},
    ]


def _coerce(data: dict[str, Any]) -> AIResult:
    try:
        confidence = float(data.get("confidence", 0.0))
    except (TypeError, ValueError):
        confidence = 0.0
    labels = data.get("suggested_labels") or []
    if not isinstance(labels, list):
        labels = []
    category = str(data.get("category", "unknown")).strip().lower()
    if category not in _CATEGORIES:
        category = "unknown"
    return AIResult(
        summary=str(data.get("summary", "")).strip(),
        likely_root_cause=str(data.get("likely_root_cause", "")).strip(),
        category=category,
        confidence=max(0.0, min(1.0, confidence)),
        possibly_fixed_in_version=(data.get("possibly_fixed_in_version") or None),
        suggested_labels=[str(x) for x in labels][:10],
        user_message=(str(data.get("user_message")).strip() or None),
    )


def assess(
    diag: Diagnostics,
    title: str,
    body: str,
    *,
    token: str,
    candidate_labels: list[str] | None = None,
) -> AIResult | None:
    """Run the Tier-1 assessment; return ``None`` on any failure or if disabled."""
    if not config.AI_ENABLED:
        return None
    messages = build_messages(diag, title or "", body or "", candidate_labels or [])
    payload = {
        "model": config.AI_MODEL,
        "messages": messages,
        "temperature": 0.2,
        "response_format": {"type": "json_schema", "json_schema": _OUTPUT_SCHEMA},
    }
    try:
        resp = requests.post(
            config.AI_ENDPOINT,
            headers={
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json",
                "Accept": "application/json",
            },
            json=payload,
            timeout=60,
        )
        if resp.status_code >= 400:
            print(f"AI assessment skipped: HTTP {resp.status_code}: {resp.text[:200]}")
            return None
        content = resp.json()["choices"][0]["message"]["content"]
        data = json.loads(content)
        return _coerce(data)
    except Exception as exc:  # noqa: BLE001 — never let AI break triage
        print(f"AI assessment skipped: {exc}")
        return None
