"""Central configuration for the Music Assistant triage bot.

Everything that a maintainer might want to tune lives here: label names,
thresholds, feature flags, size caps and the user-facing copy. Keeping it in one
module makes the behaviour easy to audit and adjust without touching logic.
"""

from __future__ import annotations

import os

# --------------------------------------------------------------------------- #
# Repositories
# --------------------------------------------------------------------------- #
SUPPORT_REPO = "music-assistant/support"
SERVER_REPO = "music-assistant/server"
# Provider manifests live here in the server repo.
MANIFEST_PATH = "music_assistant/providers/{domain}/manifest.json"

# --------------------------------------------------------------------------- #
# Sticky comment marker
# --------------------------------------------------------------------------- #
# Hidden HTML comment used to find (and update in place) the single bot comment.
STICKY_MARKER = "<!-- ma-triage-bot -->"
# Hidden machine-readable state is stored between these fences inside the comment.
STATE_BEGIN = "<!-- ma-triage-state:"
STATE_END = "-->"

# --------------------------------------------------------------------------- #
# Labels
# --------------------------------------------------------------------------- #
# Response-state labels (already exist in the repo).
LABEL_NEEDS_ATTENTION = "needs-attention"
LABEL_WAITING_FOR_USER = "waiting-for-user"
LABEL_STALE = "stale"
LABEL_AUTO_CLOSED = "auto-closed"

# Triage-control labels (bot managed / maintainer operated).
LABEL_HOLD = "triage/hold"  # pause all automation on this issue
LABEL_SKIP = "triage/skip"  # never triage this issue
LABEL_DISPATCH_COPILOT = "triage/dispatch-copilot"  # hand off to coding agent
LABEL_REMINDED_1 = "triage/reminded-1"  # 3-day reminder sent
LABEL_REMINDED_2 = "triage/reminded-2"  # 7-day warning sent
LABEL_NEEDS_DIAGNOSTICS = "triage/needs-diagnostics"  # info/diagnostics missing
LABEL_OUTDATED = "triage/outdated-version"  # running an old version

# Install-method labels (created only if they already exist in the repo).
LABEL_HAOS_ADDON = "HA Player"  # closest existing label; see PROVIDER_LABELS note

# Labels that mean "a human is engaged / confirmed" -> exempt from stale/close.
EXEMPT_LABELS = frozenset(
    {
        "bug",
        "enhancement",
        "pinned",
        "Fix to be Confirmed",
        LABEL_HOLD,
    }
)

# Control labels that must never be treated as provider/setup labels.
CONTROL_LABELS = frozenset(
    {
        LABEL_NEEDS_ATTENTION,
        LABEL_WAITING_FOR_USER,
        LABEL_STALE,
        LABEL_AUTO_CLOSED,
        LABEL_HOLD,
        LABEL_SKIP,
        LABEL_DISPATCH_COPILOT,
        LABEL_REMINDED_1,
        LABEL_REMINDED_2,
        LABEL_NEEDS_DIAGNOSTICS,
        LABEL_OUTDATED,
    }
)

# --------------------------------------------------------------------------- #
# Provider domain -> repo label mapping
# --------------------------------------------------------------------------- #
# Maps the diagnostics/manifest provider `domain` to the label used in this repo.
# Only labels that ALREADY exist in the repo are applied (see providers.py); this
# map just handles the odd casings and name differences. Domains not listed fall
# back to the domain string itself (which is applied only if such a label exists).
PROVIDER_LABELS: dict[str, str] = {
    "spotify": "spotify",
    "tidal": "tidal",
    "qobuz": "qobuz",
    "youtube_music": "youtube_music",
    "apple_music": "apple_music",
    "deezer": "deezer",
    "soundcloud": "soundcloud",
    "tunein": "tunein",
    "radiobrowser": "radiobrowser",
    "plex": "plex",
    "jellyfin": "jellyfin",
    "subsonic": "subsonic",
    "filesystem_local": "filesystem_local",
    "audiobookshelf": "audiobookshelf",
    "builtin": "builtin",
    "hass": "hass",
    # player providers
    "slimproto": "Squeezelite",
    "sonos": "sonos",
    "airplay": "airplay",
    "chromecast": "Chromecast",
    "dlna": "dlna",
    "snapcast": "snapcast",
    "hass_players": "hass_players",
    "fully_kiosk": "fully_kiosk",
    "musiccast": "MusicCast",
    "wiim": "WiiM",
}

# codeowners entry for the core team; never pinged/assigned as a "maintainer".
CORE_TEAM_HANDLE = "music-assistant"

# --------------------------------------------------------------------------- #
# Lifecycle thresholds (days)
# --------------------------------------------------------------------------- #
REMINDER_1_DAYS = 3  # gentle reminder
REMINDER_2_DAYS = 7  # warning that it will be closed
AUTO_CLOSE_DAYS = 14  # close after this many days of inactivity while waiting
LOCK_AFTER_CLOSED_DAYS = 14  # lock closed threads after this many inactive days

# --------------------------------------------------------------------------- #
# Safety caps for untrusted downloads / parsing
# --------------------------------------------------------------------------- #
MAX_DOWNLOAD_BYTES = 5 * 1024 * 1024  # 5 MB hard cap for any attachment
MAX_JSON_DEPTH = 40  # reject absurdly nested JSON (billion-laughs style)
MAX_STRING_ECHO = 500  # max chars of any diagnostics-derived string echoed back
MAX_EXCEPTIONS_SHOWN = 5  # top-N exception fingerprints surfaced in the comment
MAX_PROVIDERS_SHOWN = 20  # cap provider lists in the comment
MAX_LOG_WALL_LINES = 30  # a pasted block longer than this counts as a "log wall"
MAX_AI_INPUT_CHARS = 8000  # bound the text handed to the model

# --------------------------------------------------------------------------- #
# Feature flags (repo variables / env)
# --------------------------------------------------------------------------- #

def _flag(name: str, default: bool) -> bool:
    val = os.environ.get(name)
    if val is None or val == "":
        return default
    return val.strip().lower() in ("1", "true", "yes", "on")


# Dry-run defaults to TRUE: the prototype logs intended actions and mutates
# nothing until a maintainer explicitly opts in by setting TRIAGE_DRY_RUN=false.
DRY_RUN = _flag("TRIAGE_DRY_RUN", True)
AI_ENABLED = _flag("TRIAGE_AI_ENABLED", False)
COPILOT_AUTO = _flag("TRIAGE_COPILOT_AUTO", False)
AI_MODEL = os.environ.get("TRIAGE_AI_MODEL", "openai/gpt-4o-mini")
AI_ENDPOINT = os.environ.get(
    "TRIAGE_AI_ENDPOINT", "https://models.github.ai/inference/chat/completions"
)
# Daily hard cap on automatic Copilot dispatches (guards cost / PR noise).
COPILOT_AUTO_DAILY_CAP = int(os.environ.get("TRIAGE_COPILOT_AUTO_DAILY_CAP", "3"))
# Minimum AI confidence (0-1) required before auto-dispatching to Copilot.
COPILOT_AUTO_MIN_CONFIDENCE = float(
    os.environ.get("TRIAGE_COPILOT_AUTO_MIN_CONFIDENCE", "0.75")
)

# --------------------------------------------------------------------------- #
# User-facing copy
# --------------------------------------------------------------------------- #
DISCLOSURE_FOOTER = (
    "\n\n---\n"
    "🤖 _I'm an AI-powered triage assistant. I can make mistakes, and a human "
    "maintainer will still review this issue. This automation helps the small "
    "Music Assistant team keep up with the high volume of reports on this "
    "open-source project — thanks for your patience and for helping us help "
    "you!_"
)

GREETING = "Hi, and thanks for taking the time to report this! 🙏"

# Lifecycle reminder / close copy. `{days}` is filled in at send time.
REMINDER_1_MESSAGE = (
    "👋 Just a gentle nudge on this one — we're still waiting for a bit more "
    "information to be able to help. Whenever you get a chance, could you follow "
    "up on the request above? No rush, but it helps us keep things moving."
)
REMINDER_2_MESSAGE = (
    "👋 Following up again — we still need some more info to look into this. If "
    "we don't hear back, this issue will be **automatically closed after "
    "{days} days** of inactivity to keep the tracker tidy. You can always reply "
    "to reopen the conversation."
)
AUTO_CLOSE_MESSAGE = (
    "This issue is being **automatically closed** because we didn't hear back "
    "after a couple of reminders, so we can't investigate further right now. "
    "This isn't a judgement on the report — please just add a comment with the "
    "requested details (and a diagnostics file) and we'll be happy to reopen and "
    "take another look. Thanks for your understanding! 🙏"
)

# Hidden marker placed on reminder comments so the sweep can tell them apart from
# genuine user activity.
REMINDER_MARKER = "<!-- ma-triage-reminder -->"
