"""Compare a reported Music Assistant version against the latest release.

MA versions look like ``2.9.5`` (stable), ``2.10.0b4`` (beta) or
``2.10.0.dev2026070805`` (dev). We parse them into comparable tuples so we can
tell whether a reporter is running something older than the latest stable
release, or a pre-release build.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from . import config
from .gh import GitHubClient

_RE_VERSION = re.compile(
    r"^\s*v?"
    r"(?P<major>\d+)\.(?P<minor>\d+)\.(?P<patch>\d+)"
    r"(?:(?P<pre_kind>b|rc|a)(?P<pre_num>\d+))?"
    r"(?:\.dev(?P<dev>\d+))?"
    r"\s*$",
    re.IGNORECASE,
)

# Sort order for release channels; stable outranks any pre-release.
_PRE_RANK = {"a": 0, "b": 1, "rc": 2, None: 3}


@dataclass(frozen=True)
class Version:
    major: int
    minor: int
    patch: int
    pre_kind: str | None = None
    pre_num: int = 0
    dev: int | None = None

    @property
    def is_prerelease(self) -> bool:
        return self.pre_kind is not None or self.dev is not None

    @property
    def _key(self) -> tuple:
        # dev builds sort below their base pre/stable; use dev number as tiebreak.
        return (
            self.major,
            self.minor,
            self.patch,
            _PRE_RANK.get(self.pre_kind, 3),
            self.pre_num,
            self.dev if self.dev is not None else float("inf"),
        )

    def __lt__(self, other: "Version") -> bool:
        return self._key < other._key


def parse_version(text: str | None) -> Version | None:
    """Parse a version string into a :class:`Version`, or ``None`` if unrecognised."""
    if not text:
        return None
    match = _RE_VERSION.match(text)
    if not match:
        return None
    return Version(
        major=int(match["major"]),
        minor=int(match["minor"]),
        patch=int(match["patch"]),
        pre_kind=match["pre_kind"].lower() if match["pre_kind"] else None,
        pre_num=int(match["pre_num"]) if match["pre_num"] else 0,
        dev=int(match["dev"]) if match["dev"] else None,
    )


@dataclass
class VersionVerdict:
    reported: Version | None
    latest_stable: str | None
    outdated: bool
    prerelease: bool


def evaluate(reported_text: str | None, gh: GitHubClient) -> VersionVerdict:
    """Compare the reported version against the latest stable server release."""
    reported = parse_version(reported_text)
    latest_release = gh.get_latest_release(config.SERVER_REPO)
    latest_tag = latest_release.get("tag_name") if latest_release else None
    latest = parse_version(latest_tag)

    outdated = False
    if reported is not None and latest is not None:
        # Only flag "outdated" against the stable channel; running a newer
        # pre-release than the latest stable is not outdated.
        outdated = reported < latest and not (
            reported.major == latest.major
            and reported.minor == latest.minor
            and reported.patch == latest.patch
        )

    return VersionVerdict(
        reported=reported,
        latest_stable=latest_tag,
        outdated=outdated,
        prerelease=reported.is_prerelease if reported else False,
    )
