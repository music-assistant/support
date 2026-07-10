"""Parse and validate a Music Assistant diagnostics JSON payload.

The file is produced (and sanitized) server-side, but we still treat it as
untrusted: a reporter could attach a hand-crafted file. Parsing is therefore
defensive — depth guarded, structurally validated, and tolerant of missing keys.
"""

from __future__ import annotations

import json
from typing import Any

from . import config
from .gh import log
from .models import Diagnostics, ExceptionEntry, ProviderEntry, SystemInfo


class InvalidDiagnostics(ValueError):
    """Raised when the payload is not a usable diagnostics report."""


def _max_depth(obj: Any, limit: int, depth: int = 0) -> int:
    """Return the nesting depth of ``obj``, short-circuiting past ``limit``."""
    if depth > limit:
        raise InvalidDiagnostics("JSON nesting too deep")
    if isinstance(obj, dict):
        return max((_max_depth(v, limit, depth + 1) for v in obj.values()), default=depth)
    if isinstance(obj, list):
        return max((_max_depth(v, limit, depth + 1) for v in obj), default=depth)
    return depth


def parse_diagnostics(raw: bytes | str) -> Diagnostics:
    """Parse raw bytes/str into a :class:`Diagnostics`, or raise InvalidDiagnostics."""
    if isinstance(raw, bytes):
        try:
            raw = raw.decode("utf-8")
        except UnicodeDecodeError as exc:
            raise InvalidDiagnostics(f"not valid UTF-8: {exc}") from exc

    try:
        data = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise InvalidDiagnostics(f"not valid JSON: {exc}") from exc

    if not isinstance(data, dict):
        raise InvalidDiagnostics("top-level JSON is not an object")

    _max_depth(data, config.MAX_JSON_DEPTH)

    schema_version = data.get("schema_version")
    if not isinstance(schema_version, int):
        raise InvalidDiagnostics("missing or invalid schema_version")

    # A valid report must at least carry a system block.
    system_raw = data.get("system")
    if not isinstance(system_raw, dict):
        raise InvalidDiagnostics("missing system section")

    system = _parse_system(system_raw)
    install = data.get("install") if isinstance(data.get("install"), dict) else {}
    providers = _parse_providers(install.get("providers"))
    players = install.get("players") if isinstance(install.get("players"), dict) else {}
    library = install.get("library") if isinstance(install.get("library"), dict) else {}
    core_cfg = (
        install.get("core_config_non_default")
        if isinstance(install.get("core_config_non_default"), dict)
        else {}
    )
    exceptions = _parse_exceptions(data.get("exceptions"))

    return Diagnostics(
        schema_version=schema_version,
        generated_at=_str_or_none(data.get("generated_at")),
        system=system,
        providers=providers,
        players=players,
        library=library,
        core_config_non_default=core_cfg,
        exceptions=exceptions,
        has_log_tail=bool(data.get("log_tail")),
    )


def try_parse(raw: bytes | str) -> Diagnostics | None:
    """Convenience wrapper: parse or return ``None`` (logging the reason)."""
    try:
        return parse_diagnostics(raw)
    except InvalidDiagnostics as exc:
        log(f"Diagnostics invalid: {exc}")
        return None


# --------------------------------------------------------------------------- #
# Section parsers
# --------------------------------------------------------------------------- #
def _parse_system(raw: dict[str, Any]) -> SystemInfo:
    return SystemInfo(
        version=_str_or_none(raw.get("version")),
        python_version=_str_or_none(raw.get("python_version")),
        platform=_str_or_none(raw.get("platform")),
        machine=_str_or_none(raw.get("machine")),
        hass_addon=_bool_or_none(raw.get("hass_addon")),
        safe_mode=_bool_or_none(raw.get("safe_mode")),
        uptime_seconds=raw.get("uptime_seconds") if isinstance(raw.get("uptime_seconds"), int) else None,
        memory=raw.get("memory") if isinstance(raw.get("memory"), dict) else {},
        disk=raw.get("data_dir_disk") if isinstance(raw.get("data_dir_disk"), dict) else {},
    )


def _parse_providers(raw: Any) -> list[ProviderEntry]:
    if not isinstance(raw, list):
        return []
    providers: list[ProviderEntry] = []
    for item in raw:
        if not isinstance(item, dict):
            continue
        domain = _str_or_none(item.get("domain"))
        if not domain:
            continue
        providers.append(
            ProviderEntry(
                domain=domain,
                instance_id=_str_or_none(item.get("instance_id")) or "",
                type=_str_or_none(item.get("type")) or "",
                enabled=bool(item.get("enabled", False)),
                loaded=bool(item.get("loaded", False)),
                available=bool(item.get("available", False)),
                last_error=_str_or_none(item.get("last_error")),
            )
        )
    return providers


def _parse_exceptions(raw: Any) -> list[ExceptionEntry]:
    if not isinstance(raw, list):
        return []
    exceptions: list[ExceptionEntry] = []
    for item in raw:
        if not isinstance(item, dict):
            continue
        exceptions.append(
            ExceptionEntry(
                exc_type=_str_or_none(item.get("type")) or "Exception",
                fingerprint=_str_or_none(item.get("fingerprint")) or "",
                count=item.get("count") if isinstance(item.get("count"), int) else 1,
                first_seen=_str_or_none(item.get("first_seen")),
                last_seen=_str_or_none(item.get("last_seen")),
                logger=_str_or_none(item.get("logger")),
                level=_str_or_none(item.get("level")),
                origin=_str_or_none(item.get("origin")),
                message=_str_or_none(item.get("message")),
                traceback=_str_or_none(item.get("traceback")),
            )
        )
    # Most frequent first.
    exceptions.sort(key=lambda e: e.count, reverse=True)
    return exceptions


# --------------------------------------------------------------------------- #
# Small coercion helpers
# --------------------------------------------------------------------------- #
def _str_or_none(value: Any) -> str | None:
    return value if isinstance(value, str) and value != "" else None


def _bool_or_none(value: Any) -> bool | None:
    return value if isinstance(value, bool) else None
