"""Deterministic analysis of a parsed diagnostics report (Tier 0 — no AI).

Turns a :class:`Diagnostics` into an ordered list of human-readable findings and
a set of suggested labels. This is the reliable backbone of the bot; the AI tier
only ever augments what is produced here.
"""

from __future__ import annotations

from . import config
from .gh import GitHubClient
from .models import Diagnostics, Finding, Severity
from .providers import domain_to_label
from .sanitize import inline
from .versioncheck import VersionVerdict, evaluate


def analyze(diag: Diagnostics, gh: GitHubClient) -> tuple[list[Finding], set[str]]:
    """Return ``(findings, suggested_labels)`` for a diagnostics report."""
    findings: list[Finding] = []
    labels: set[str] = set()

    _check_version(diag, gh, findings, labels)
    _check_safe_mode(diag, findings)
    _check_providers(diag, findings, labels)
    _check_players(diag, labels)
    _check_exceptions(diag, findings)
    _check_resources(diag, findings)

    findings.sort(key=lambda f: f.sort_key)
    return findings, labels


def _check_version(
    diag: Diagnostics, gh: GitHubClient, findings: list[Finding], labels: set[str]
) -> None:
    v_findings, v_labels = version_findings(diag.system.version, gh)
    findings.extend(v_findings)
    labels.update(v_labels)


def version_findings(
    reported_version: str | None, gh: GitHubClient
) -> tuple[list[Finding], set[str]]:
    """Version findings from a plain version string (diagnostics or form field)."""
    findings: list[Finding] = []
    labels: set[str] = set()
    verdict: VersionVerdict = evaluate(reported_version, gh)
    reported = reported_version or "unknown"
    if verdict.outdated and verdict.latest_stable:
        findings.append(
            Finding(
                Severity.WARNING,
                "Outdated version",
                f"This report is from **{inline(reported)}**, but the latest "
                f"stable release is **{verdict.latest_stable}**. A number of "
                f"issues are fixed in newer releases — please update and check "
                f"whether the problem persists.",
                labels=[config.LABEL_OUTDATED],
            )
        )
        labels.add(config.LABEL_OUTDATED)
    elif verdict.prerelease:
        findings.append(
            Finding(
                Severity.INFO,
                "Pre-release build",
                f"This report is from a pre-release build (**{inline(reported)}**). "
                f"That's fine and appreciated — just noting it for context.",
            )
        )
    return findings, labels


def install_method_finding(install_method: str | None) -> Finding | None:
    """Flag the unsupported install method selected on the main bug form."""
    if not install_method:
        return None
    lowered = install_method.lower()
    if "unsupported" in lowered or lowered.startswith("other"):
        return Finding(
            Severity.WARNING,
            "Unsupported install method",
            config.UNSUPPORTED_INSTALL_NOTE,
        )
    return None


def _check_safe_mode(diag: Diagnostics, findings: list[Finding]) -> None:
    if diag.system.safe_mode:
        findings.append(
            Finding(
                Severity.CRITICAL,
                "Safe mode is enabled",
                "The server is running in **safe mode**, so most providers and "
                "players are disabled. Many features will not work until safe "
                "mode is turned off. If you didn't enable it deliberately, the "
                "server likely fell back to safe mode after a crash on startup.",
            )
        )


def _check_providers(
    diag: Diagnostics, findings: list[Finding], labels: set[str]
) -> None:
    # Label every configured provider domain (existing-label filtering happens
    # later against the repo's real labels).
    for provider in diag.providers:
        labels.add(domain_to_label(provider.domain))

    errored = diag.providers_in_error
    if not errored:
        return
    lines = []
    for provider in errored[: config.MAX_PROVIDERS_SHOWN]:
        err = inline(provider.last_error) or "unavailable"
        lines.append(f"- **{inline(provider.domain)}** (`{inline(provider.instance_id)}`): {err}")
    findings.append(
        Finding(
            Severity.CRITICAL,
            f"{len(errored)} provider(s) in an error state",
            "The following configured providers are enabled but not working:\n"
            + "\n".join(lines),
        )
    )


def _check_players(diag: Diagnostics, labels: set[str]) -> None:
    by_provider = diag.players.get("by_provider")
    if isinstance(by_provider, dict):
        for domain in by_provider:
            if isinstance(domain, str):
                labels.add(domain_to_label(domain))

    if diag.system.hass_addon is True:
        # Install method is useful context; only applied if such a label exists.
        labels.add("hass")


def _check_exceptions(diag: Diagnostics, findings: list[Finding]) -> None:
    if not diag.exceptions:
        return
    top = diag.exceptions[: config.MAX_EXCEPTIONS_SHOWN]
    lines = []
    for exc in top:
        origin = f" — `{inline(exc.origin)}`" if exc.origin else ""
        msg = f": {inline(exc.message)}" if exc.message else ""
        lines.append(f"- **{inline(exc.exc_type)}** ×{exc.count}{origin}{msg}")
    total = len(diag.exceptions)
    suffix = f" (showing top {len(top)} of {total})" if total > len(top) else ""
    findings.append(
        Finding(
            Severity.WARNING,
            f"Captured exceptions{suffix}",
            "The diagnostics captured these recurring errors, most frequent "
            "first:\n" + "\n".join(lines),
        )
    )


def _check_resources(diag: Diagnostics, findings: list[Finding]) -> None:
    free_mb = diag.system.disk.get("free_mb") if diag.system.disk else None
    if isinstance(free_mb, int) and free_mb < 256:
        findings.append(
            Finding(
                Severity.WARNING,
                "Very low free disk space",
                f"Only ~{free_mb} MB of free disk space is available on the data "
                f"directory volume. Low disk space can cause database and "
                f"caching errors.",
            )
        )
