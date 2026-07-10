"""Typed data structures for parsed diagnostics and triage results."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class Severity(str, Enum):
    """Relative importance of a finding, controls ordering in the comment."""

    CRITICAL = "critical"
    WARNING = "warning"
    INFO = "info"


@dataclass
class ProviderEntry:
    """A single configured provider from the install census."""

    domain: str
    instance_id: str
    type: str
    enabled: bool
    loaded: bool
    available: bool
    last_error: str | None = None

    @property
    def in_error(self) -> bool:
        """Whether this provider looks broken (enabled but unavailable/errored)."""
        return self.enabled and (not self.available or bool(self.last_error))


@dataclass
class ExceptionEntry:
    """An aggregated, sanitized exception fingerprint."""

    exc_type: str
    fingerprint: str
    count: int
    first_seen: str | None = None
    last_seen: str | None = None
    logger: str | None = None
    level: str | None = None
    origin: str | None = None
    message: str | None = None
    traceback: str | None = None


@dataclass
class SystemInfo:
    """Point-in-time system/runtime snapshot."""

    version: str | None = None
    python_version: str | None = None
    platform: str | None = None
    machine: str | None = None
    hass_addon: bool | None = None
    safe_mode: bool | None = None
    uptime_seconds: int | None = None
    memory: dict[str, Any] = field(default_factory=dict)
    disk: dict[str, Any] = field(default_factory=dict)


@dataclass
class Diagnostics:
    """A parsed and validated Music Assistant diagnostics report."""

    schema_version: int
    generated_at: str | None
    system: SystemInfo
    providers: list[ProviderEntry] = field(default_factory=list)
    players: dict[str, Any] = field(default_factory=dict)
    library: dict[str, Any] = field(default_factory=dict)
    core_config_non_default: dict[str, Any] = field(default_factory=dict)
    exceptions: list[ExceptionEntry] = field(default_factory=list)
    has_log_tail: bool = False
    # "json" for a real diagnostics report, "log" when reconstructed from a raw
    # log file (only a subset of fields is then populated; see logscan.py).
    source: str = "json"

    @property
    def providers_in_error(self) -> list[ProviderEntry]:
        return [p for p in self.providers if p.in_error]

    @property
    def from_log(self) -> bool:
        return self.source == "log"


@dataclass
class Finding:
    """A single deterministic (or AI) observation to surface to the user."""

    severity: Severity
    title: str
    detail: str
    # Optional labels this finding suggests applying.
    labels: list[str] = field(default_factory=list)

    _ORDER = {Severity.CRITICAL: 0, Severity.WARNING: 1, Severity.INFO: 2}

    @property
    def sort_key(self) -> int:
        return self._ORDER[self.severity]


@dataclass
class AIResult:
    """Structured output from the Tier-1 GitHub Models analysis."""

    summary: str
    likely_root_cause: str
    category: str  # bug | config | user-error | upstream | unknown
    confidence: float  # 0-1
    possibly_fixed_in_version: str | None = None
    suggested_labels: list[str] = field(default_factory=list)
    user_message: str | None = None


@dataclass
class TriageResult:
    """Everything the bot decided about an issue in one pass."""

    # Which issue form this came from: "main" (server bug), "frontend" (UI bug)
    # or "translation". Drives validation, messaging and whether we comment.
    form_kind: str = "main"
    # True when the whole issue should be left alone (e.g. translation form).
    skip: bool = False

    has_diagnostics: bool = False
    diagnostics_invalid: bool = False
    # The attachment the form asked for is missing (diagnostics/log for the main
    # form, a screenshot/recording for the frontend form).
    missing_attachment: bool = False
    missing_sections: list[str] = field(default_factory=list)
    log_wall_detected: bool = False

    # Facts read straight from the form fields (available even without a file).
    reported_version: str | None = None
    install_method: str | None = None

    findings: list[Finding] = field(default_factory=list)
    labels_to_add: set[str] = field(default_factory=set)
    maintainers_to_ping: set[str] = field(default_factory=set)
    ai: AIResult | None = None
    diagnostics: Diagnostics | None = None

    @property
    def is_actionable(self) -> bool:
        """True when we have enough to diagnose (valid diagnostics present)."""
        return self.has_diagnostics and not self.diagnostics_invalid

    @property
    def needs_user_action(self) -> bool:
        """True when the reporter still has to provide something."""
        if self.skip:
            return False
        if self.form_kind == "frontend":
            return bool(self.missing_sections or self.missing_attachment)
        # main bug form
        return bool(
            self.missing_sections
            or self.diagnostics_invalid
            or (self.missing_attachment and not self.has_diagnostics)
        )

    @property
    def should_comment(self) -> bool:
        """Whether the bot has anything worth posting (keeps the tracker quiet).

        - translation: never.
        - frontend: only when the reporter needs to add something.
        - main: whenever we have a diagnostics summary OR a request to make
          (i.e. essentially always — a main report always yields useful output).
        """
        if self.skip or self.form_kind == "translation":
            return False
        if self.form_kind == "frontend":
            return self.needs_user_action
        return self.is_actionable or self.needs_user_action or bool(self.findings)
