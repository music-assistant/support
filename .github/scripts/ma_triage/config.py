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
# Existing sticky comments were created before the GitHub App rollout. Keep
# those comments intact instead of replacing them and losing their history.
LEGACY_BOT_LOGINS = frozenset({"github-actions", "github-actions[bot]"})
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
LABEL_REMINDED_1 = "triage/reminded-1"  # 3-day reminder sent
LABEL_REMINDED_2 = "triage/reminded-2"  # 7-day warning sent
LABEL_NEEDS_DIAGNOSTICS = "triage/needs-diagnostics"  # info/diagnostics missing
LABEL_OUTDATED = "triage/outdated-version"  # running an old version

# Form-kind labels applied by the issue templates themselves. Used to branch
# validation/parsing by form (see template.form_kind). The main bug form carries
# only "triage"; the frontend and translation forms add their own label.
LABEL_TRIAGE = "triage"
LABEL_FRONTEND = "frontend"
LABEL_TRANSLATION = "translation"

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
    "spotify_connect": "Spotify Connect",
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
    "opensubsonic": "subsonic",
    "filesystem_local": "filesystem_local",
    "audiobookshelf": "audiobookshelf",
    "builtin": "builtin",
    "hass": "hass",
    # player providers
    "slimproto": "Squeezelite",
    "squeezelite": "Squeezelite",
    "sonos": "sonos",
    "airplay": "airplay",
    "chromecast": "Chromecast",
    "dlna": "dlna",
    "snapcast": "snapcast",
    "hass_players": "hass_players",
    "fully_kiosk": "fully_kiosk",
    "musiccast": "MusicCast",
    "wiim": "WiiM",
    "heos": "HEOS",
    "sendspin": "sendspin",
}

# Provider labels occasionally differ from the current provider directory/domain
# in the server repository. These overrides are authoritative for manifest
# metadata (documentation + codeowners).
PROVIDER_MANIFEST_DOMAINS: dict[str, str] = {
    "spotify connect": "spotify_connect",
    "subsonic": "opensubsonic",
    "squeezelite": "squeezelite",
}

# codeowners entry for the core team; never pinged/assigned as a "maintainer".
CORE_TEAM_HANDLE = "music-assistant"

# --------------------------------------------------------------------------- #
# Provider detection from free text
# --------------------------------------------------------------------------- #
# The reworked bug form no longer has dedicated "Music Providers"/"Player
# Providers" sections, so we also detect providers mentioned in free text
# ("What happened?", "How to reproduce", the title, …). Maps a lower-cased alias
# to the provider label. Matching is word-boundary based (see providers.py), and
# only labels that already exist in the repo are ever applied. Keep aliases
# specific to avoid false positives.
PROVIDER_TEXT_ALIASES: dict[str, str] = {
    "spotify connect": "Spotify Connect",
    "spotify": "spotify",
    "tidal": "tidal",
    "qobuz": "qobuz",
    "youtube music": "youtube_music",
    "youtube_music": "youtube_music",
    "ytmusic": "youtube_music",
    "apple music": "apple_music",
    "apple_music": "apple_music",
    "deezer": "deezer",
    "soundcloud": "soundcloud",
    "tunein": "tunein",
    "radio browser": "radiobrowser",
    "radiobrowser": "radiobrowser",
    "plex": "plex",
    "jellyfin": "jellyfin",
    "subsonic": "subsonic",
    "opensubsonic": "subsonic",
    "funkwhale": "subsonic",
    "navidrome": "subsonic",
    "audiobookshelf": "audiobookshelf",
    "filesystem": "filesystem_local",
    "snapcast": "snapcast",
    "sonos": "sonos",
    "airplay": "airplay",
    "chromecast": "Chromecast",
    "google cast": "Chromecast",
    "squeezelite": "Squeezelite",
    "squeezebox": "Squeezelite",
    "slimproto": "Squeezelite",
    "musiccast": "MusicCast",
    "wiim": "WiiM",
    "heos": "HEOS",
    "sendspin": "sendspin",
    "dlna": "dlna",
    "upnp": "dlna",
    "fully kiosk": "fully_kiosk",
    "fully_kiosk": "fully_kiosk",
}

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
MAX_LOG_TAIL_BYTES = 512 * 1024  # for oversized logs, also grab the last ~512 KB
MAX_JSON_DEPTH = 40  # reject absurdly nested JSON (billion-laughs style)
MAX_STRING_ECHO = 500  # max chars of any diagnostics-derived string echoed back
MAX_EXCEPTIONS_SHOWN = 5  # top-N exception fingerprints surfaced in the comment
MAX_PROVIDERS_SHOWN = 20  # cap provider lists in the comment
MAX_REPORTED_PROVIDERS = 5  # cap provider metadata lookups from untrusted text
MAX_LOG_WALL_LINES = 30  # a pasted block longer than this counts as a "log wall"
MAX_AI_INPUT_CHARS = 16000  # bound the evidence-rich text handed to the model
MAX_CODE_CONTEXT_CHARS = 5000  # official server-code excerpts per assessment
MAX_CODE_CONTEXT_FILES = 5
RELATED_EXCERPT_CHARS = 1200  # post body retained for assessment evidence

# GitHub issue forms render an empty optional field as this literal string.
NO_RESPONSE_SENTINEL = "_No response_"

# --------------------------------------------------------------------------- #
# Feature flags (repo variables / env)
# --------------------------------------------------------------------------- #

def _flag(name: str, default: bool) -> bool:
    val = os.environ.get(name)
    if val is None or val == "":
        return default
    return val.strip().lower() in ("1", "true", "yes", "on")


def _env_str(name: str, default: str) -> str:
    """Env value, treating unset OR empty as "use the default".

    GitHub Actions passes an unset ``${{ vars.X }}`` as an *empty string*, so a
    plain ``os.environ.get(name, default)`` would wrongly yield ``""`` and, for
    numeric config, crash on ``int("")``. All TRIAGE_* config reads go through
    these helpers so an unset repo variable falls back to the default.
    """
    val = os.environ.get(name)
    return val if val not in (None, "") else default


def _env_int(name: str, default: int) -> int:
    val = os.environ.get(name)
    if not val or not val.strip():
        return default
    try:
        return int(val)
    except ValueError:
        return default


def _env_float(name: str, default: float) -> float:
    val = os.environ.get(name)
    if not val or not val.strip():
        return default
    try:
        return float(val)
    except ValueError:
        return default


# Dry-run defaults to TRUE: the prototype logs intended actions and mutates
# nothing until a maintainer explicitly opts in by setting TRIAGE_DRY_RUN=false.
SERVER_REF = _env_str("TRIAGE_SERVER_REF", "dev")
# Login of the current GitHub App bot (set from create-github-app-token's
# ``app-slug`` output). Empty preserves the legacy single-token behaviour.
BOT_LOGIN = _env_str("TRIAGE_BOT_LOGIN", "")
DRY_RUN = _flag("TRIAGE_DRY_RUN", True)
AI_ENABLED = _flag("TRIAGE_AI_ENABLED", False)
# Scan an attached raw log file when no diagnostics JSON is present (common on
# MA versions older than the diagnostics feature). The log is redacted before any
# of it is echoed (see logscan.py / sanitize.py).
SCAN_LOGS = _flag("TRIAGE_SCAN_LOGS", True)
AI_MODEL = _env_str("TRIAGE_AI_MODEL", "openai/gpt-4o-mini")
AI_ENDPOINT = _env_str("TRIAGE_AI_ENDPOINT", "https://models.github.ai/inference/chat/completions")
# Set by the workflow when GitHub Copilot is available. Its presence selects the
# CLI backend in `ai._chat` instead of an HTTP endpoint — Copilot is a command,
# not a URL, so there is nothing for AI_ENDPOINT to point at. Not a TRIAGE_*
# variable because it is a credential, and the credential is the capability: no
# token means no CLI to call, which is exactly the condition to branch on.
AI_CLI_TOKEN = os.environ.get("COPILOT_GITHUB_TOKEN", "")
# Longer than the HTTP timeout: the CLI starts a process and does its own
# retries, so it is slower to answer than an endpoint that either responds or
# does not.
AI_CLI_TIMEOUT = _env_int("TRIAGE_AI_CLI_TIMEOUT", 180)

# --------------------------------------------------------------------------- #
# RAG layer (Phase 2) — docs-grounded answers + similar-post detection
# --------------------------------------------------------------------------- #
# The RAG layer is *additionally* gated behind AI_ENABLED (see rag.py). This
# sub-flag lets a maintainer turn off just the RAG features while keeping the
# Tier-1 assessment. Effective enablement is ``AI_ENABLED and RAG_ENABLED``.
RAG_ENABLED = _flag("TRIAGE_RAG_ENABLED", True)

# Live discussion triage (docs-grounded answers + related posts on GitHub
# Discussions). Gated *additionally* behind AI_ENABLED and RAG_ENABLED, and
# defaults OFF so merging the feature is dormant until a maintainer opts in by
# setting TRIAGE_DISCUSSIONS_ENABLED=true. Effective enablement is
# ``AI_ENABLED and RAG_ENABLED and DISCUSSIONS_ENABLED``.
DISCUSSIONS_ENABLED = _flag("TRIAGE_DISCUSSIONS_ENABLED", False)

# Code tracing lets the chat model search a checkout of the server repository
# for the code behind a report. Its paths join those from the provider label and
# the traceback rather than replacing them. Defaults OFF so merging it is
# dormant, and needs a checkout the workflow has placed on disk — both must be
# set for tracing to run.
CODE_TRACE_ENABLED = _flag("TRIAGE_CODE_TRACE_ENABLED", False)
CODE_TRACE_CHECKOUT = _env_str("TRIAGE_SERVER_CHECKOUT", "")
# Where the trace job left its result for the triage job to pick up. Producing
# the paths and using them run in different jobs on purpose: the process that
# searches a tree under the direction of public issue text holds no token that
# can write to the repository.
CODE_TRACE_PATHS_FILE = _env_str("TRIAGE_TRACED_PATHS", "")
# How long the model may search. A runner searches a great deal more slowly than
# a laptop does — measured on seven runs against the same tree, a search that
# takes 139s locally takes 250-280s here, and the ones that need longest are the
# reports where a trace is worth most. Cutting them off returns nothing, while
# letting them run costs only the reports that were slow anyway: most finish in
# a few minutes and are unaffected by where this sits.
#
# Raising it past fourteen minutes has no effect: the job is cancelled at
# fifteen, and a cancelled job uploads nothing at all.
CODE_TRACE_TIMEOUT = _env_int("TRIAGE_CODE_TRACE_TIMEOUT", 840)
# The reported problem, fetched to a file for the trace job. A manual dispatch
# carries no issue payload, so the file is the only source of the issue text
# there, and reading one keeps that job free of an API client and its token.
CODE_TRACE_ISSUE_FILE = _env_str("TRIAGE_ISSUE_FILE", "")
# The report as handed to the tracer. Smaller than MAX_AI_INPUT_CHARS because
# the tracer gets only the report, never the diagnostics or retrieved evidence.
MAX_TRACE_INPUT_CHARS = 6000

# Public docs repository (Astro/Starlight). Readable with the default
# GITHUB_TOKEN — it is public, so no secret is required.
DOCS_REPO = _env_str("TRIAGE_DOCS_REPO", "music-assistant/music-assistant.io")
DOCS_CONTENT_ROOT = _env_str("TRIAGE_DOCS_CONTENT_ROOT", "src/content/docs")
DOCS_SITE = _env_str("TRIAGE_DOCS_SITE", "https://www.music-assistant.io")
DOCS_REF = _env_str("TRIAGE_DOCS_REF", "main")
# Doc paths (relative to the content root) whose prefix excludes them from the
# index — the dated blog posts are announcements, not troubleshooting material.
DOCS_EXCLUDE_PREFIXES = tuple(
    p.strip()
    for p in _env_str("TRIAGE_DOCS_EXCLUDE", "blog/").split(",")
    if p.strip()
)
# Discussion categories excluded (case-insensitive) from BOTH the similar-posts
# index and live discussion triage. Translation contributions live in a
# Discussion category and are neither useful as "similar reports" for bug issues
# nor something the bot should auto-answer, so they are skipped by default.
DISCUSSION_EXCLUDE_CATEGORIES = tuple(
    c.strip().lower()
    for c in _env_str("TRIAGE_DISCUSSION_EXCLUDE_CATEGORIES", "translations,translation").split(",")
    if c.strip()
)
# Discussion categories handled in "duplicates only" mode. They are still
# indexed (they make good "similar report" hits) and still checked for likely
# duplicates, but the docs judge is skipped: a docs-grounded answer has nothing
# to offer a feature request, so posting one is noise however good the retrieval
# is. Duplicate detection stays on because duplicate feature requests are
# exactly what clutters the backlog.
DISCUSSION_NO_ANSWER_CATEGORIES = tuple(
    c.strip().lower()
    for c in _env_str(
        "TRIAGE_DISCUSSION_NO_ANSWER_CATEGORIES",
        "feature requests and ideas,feature polls",
    ).split(",")
    if c.strip()
)

# Orphan branch in THIS repo that stores the JSON indexes (keeps ``main`` clean).
INDEX_BRANCH = _env_str("TRIAGE_INDEX_BRANCH", "triage-index")
DOCS_INDEX_PATH = "docs.json"
POSTS_INDEX_PATH = "posts.json"
SUPPRESS_INDEX_PATH = "suppress.json"

# GitHub Models — embeddings + judge/answer chat (both OpenAI-compatible, served
# from models.github.ai with the default token + ``models: read`` permission).
EMBED_MODEL = _env_str("TRIAGE_EMBED_MODEL", "openai/text-embedding-3-small")
# Reduced embedding dimensionality (OpenAI ``dimensions`` param) keeps the JSON
# indexes small and the pure-Python cosine fast. Set to 0 to use the model default.
EMBED_DIM = _env_int("TRIAGE_EMBED_DIM", 512)
EMBED_ENDPOINT = _env_str("TRIAGE_EMBED_ENDPOINT", "https://models.github.ai/inference/embeddings")
EMBED_BATCH = _env_int("TRIAGE_EMBED_BATCH", 64)
ANSWER_MODEL = _env_str("TRIAGE_ANSWER_MODEL", "openai/gpt-4o")

# Confidence-tier thresholds for the doc-answer judge (0-1). See rag.tier().
ANSWER_HI = _env_float("TRIAGE_ANSWER_HI", 0.75)
ANSWER_LO = _env_float("TRIAGE_ANSWER_LO", 0.45)

# Retrieval knobs.
DOCS_TOP_K = _env_int("TRIAGE_DOCS_TOP_K", 6)
# Max chunks from any one documentation page in a single retrieval. Sections of
# the same page rank together, so without a cap the top-K is spent on one page.
# The authoritative provider-doc promotion in rag.py deliberately overrides this.
DOCS_MAX_PER_PAGE = _env_int("TRIAGE_DOCS_MAX_PER_PAGE", 1)
RELATED_POSTS = _env_int("TRIAGE_RELATED_POSTS", 3)
# Two posts from the same project share a lot of vocabulary (players, providers,
# playback, Home Assistant), so cosine between any two of them rarely drops below
# ~0.35 — a floor set there filters nothing. Measured over live discussion
# triage, the useful matches sit at ~0.65+ and the noise below ~0.55.
RELATED_MIN_SCORE = _env_float("TRIAGE_RELATED_MIN_SCORE", 0.60)
# Keep weak semantic matches available without presenting them as likely
# duplicates. Only scores at/above this threshold render expanded.
RELATED_EXPAND_SCORE = _env_float("TRIAGE_RELATED_EXPAND_SCORE", 0.70)
# Pinned Feature Polls mention providers but are not operational status notices.
PINNED_EXCLUDE_CATEGORIES = tuple(
    c.strip().lower()
    for c in _env_str("TRIAGE_PINNED_EXCLUDE_CATEGORIES", "feature polls").split(",")
    if c.strip()
)
# A pinned notice naming this many providers or more is a general status/index
# post, not a notice about a specific provider — matching on a bare provider
# mention would attach it to almost every report.
PINNED_MAX_PROVIDERS = _env_int("TRIAGE_PINNED_MAX_PROVIDERS", 4)
# Minimum dense cosine for the top doc hit to show links when the judge call
# itself failed (retrieval-only MEDIUM fallback).
DOCS_MIN_DENSE = _env_float("TRIAGE_DOCS_MIN_DENSE", 0.30)
# Max doc links rendered in a MEDIUM (links-only) comment section.
DOCS_LINKS_SHOWN = _env_int("TRIAGE_DOCS_LINKS_SHOWN", 3)
# A cited-answer fingerprint with at least this many downvotes is suppressed.
SUPPRESS_MIN_DOWNVOTES = _env_int("TRIAGE_SUPPRESS_MIN_DOWNVOTES", 1)
RRF_K = 60  # reciprocal-rank-fusion constant
BM25_K1 = 1.5
BM25_B = 0.75

# Indexing caps / cost guards.
#
# Issues and discussions are capped separately. Under one shared cap the two
# compete for slots by recency, so a busy stretch of discussions evicts the older
# issues duplicate detection depends on.
#
# The ceiling that matters is on-disk size rather than post count: the index is
# committed to git and rewritten whole on every new post. Measured on the live
# file: 1.4 KB per quantised 1024-wide vector (see `retrieval.encode_vec`) plus
# up to `RELATED_EXCERPT_CHARS` of text, so ~2.3 KB a post. Under the previous
# JSON-float encoding the vector alone would have been ~10x that.
#
# The issue cap covers the repository's whole history with headroom, because a
# duplicate can point at any earlier report and one that is not indexed can
# never be found. Discussions stay capped by recency: they are mostly feature
# requests, which score near zero against a bug report, so the older ones buy
# far less than they cost.
INDEX_MAX_ISSUES = _env_int("TRIAGE_INDEX_MAX_ISSUES", 3500)
INDEX_MAX_DISCUSSIONS = _env_int("TRIAGE_INDEX_MAX_DISCUSSIONS", 500)
# Bounds how much is *fetched* before trimming; the per-kind caps above decide
# what is kept.
INDEX_MAX_POSTS = _env_int(
    "TRIAGE_INDEX_MAX_POSTS", INDEX_MAX_ISSUES + INDEX_MAX_DISCUSSIONS
)
DOCS_CHUNK_MAX_CHARS = _env_int("TRIAGE_DOCS_CHUNK_MAX_CHARS", 2000)
MAX_POST_EMBED_CHARS = 6000  # bound the text embedded per post / query
MAX_DOC_ANSWER_CHARS = 1200  # cap the judge's answer echoed into the comment

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

# Greeting for the sticky comment posted on a Discussion (a question, not a bug
# report). Kept short and clearly automated; the disclosure footer still applies.
DISCUSSION_GREETING = (
    "👋 Thanks for starting a discussion! Here are a few automated pointers that "
    "might help while the community and maintainers take a look."
)

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

DIAGNOSTICS_SETTINGS_PATH = (
    "Settings → System → Diagnostics → Download diagnostics"
)

# Note added when the analysis came from a raw log file rather than a diagnostics
# report (older MA versions). We only ever show redacted, derived facts from logs.
LOG_FALLBACK_NOTE = (
    "ℹ️ I analysed the **attached log file** (no diagnostics report was found). "
    "Logs give me less to go on than a diagnostics report, and I only surface "
    "redacted, derived facts from them. If you're on Music Assistant 2.9.6 or "
    "newer, a diagnostics report would help us a lot more — see "
    f"**{DIAGNOSTICS_SETTINGS_PATH}**."
)

# Note added when the reporter selected the unsupported install method.
UNSUPPORTED_INSTALL_NOTE = (
    "⚠️ You indicated you're running Music Assistant via an **unsupported install "
    "method**. Only the Home Assistant add-on and the official Docker container "
    "are supported. We're happy to take a look, but issues specific to "
    "unsupported setups may be closed if they can't be reproduced on a supported "
    "one."
)

# Frontend form: what we say when required info / a screenshot is missing.
FRONTEND_MISSING_MESSAGE = (
    "To help us look into this UI issue, could you make sure the report includes "
    "a **screenshot or short screen recording** that shows the problem, plus the "
    "steps to reproduce it? That's by far the most useful thing for frontend bugs."
)

# Main form: reporter pasted a screenshot/image into the diagnostics field
# instead of attaching the actual diagnostics report or log file.
SCREENSHOT_ATTACHMENT_NOTE = (
    "👀 It looks like you pasted a **screenshot** in the *Diagnostics report or "
    "log file* section. I can't read logs from an image — and a partial "
    "screenshot usually doesn't include enough to go on. Could you attach the "
    "actual **diagnostics report** (a `.json` file) or your **full log file** "
    "instead?"
)

# --------------------------------------------------------------------------- #
# RAG layer copy (docs-grounded answers + similar past reports)
# --------------------------------------------------------------------------- #
# Shown for a HIGH-confidence, docs-grounded answer (generated prose + links).
DOCS_ANSWER_HEADING = "### 📚 This might be answered in the docs"
# Shown for a MEDIUM-confidence result (relevant links only, no generated prose).
DOCS_LINKS_HEADING = "### 📚 Docs that might help"
DOCS_ANSWER_DISCLAIMER = (
    "_This is an automated suggestion based on the documentation — it may not "
    "perfectly match your setup, and a maintainer will still take a look. If it "
    "helped, a 👍 on this comment helps me learn; a 👎 tells me I got it wrong._"
)
RELATED_POSTS_HEADING = "### 🔁 Similar past reports"
RELATED_POSTS_INTRO = (
    "These earlier issues or discussions look related and might already have an "
    "answer (or indicate a duplicate):"
)
RELATED_POSTS_WEAK_SUMMARY = "🔁 Possibly related past reports"
RELATED_POSTS_WEAK_INTRO = (
    "These reports have some overlap, but the automated match was not strong "
    "enough to call them likely duplicates:"
)

# --------------------------------------------------------------------------- #
# Duplicates-only copy (feature-request categories)
# --------------------------------------------------------------------------- #
# The generic related-posts copy above is written for bug reports ("might
# already have an answer") and asks the reader to do nothing. On a feature
# request the useful outcome is consolidation, so the ask has to be explicit.
# Kept short: the section heading below already states the finding, so repeating
# it here just reads as the bot saying the same thing twice.
DISCUSSION_DUPE_GREETING = "👋 Thanks for the suggestion!"
# Matched request is still OPEN — consolidating votes onto it is worthwhile.
DUPE_OPEN_HEADING = "### 🔁 This may already have been requested"
DUPE_OPEN_INTRO = "If that's the same idea, the most useful thing you can do is:"
DUPE_OPEN_ACTIONS = (
    "1. **👍 the existing request** — upvotes are how we gauge demand, and they "
    "only count when they're all on one request.\n"
    "2. **Close this one** (use _Close discussion_ on this page) so the interest "
    "stays in one place.\n\n"
    "If it's actually different, reply here explaining what this adds and we'll "
    "leave it open."
)
# Every match is CLOSED — never send someone to upvote a closed request. Ask
# them to decide instead, and to spell out the gap if they keep this open.
DUPE_CLOSED_HEADING = "### 🔁 This may have been requested before"
DUPE_CLOSED_INTRO = "That earlier request has since been closed."
DUPE_CLOSED_ACTIONS = (
    "You can close this one if that already addressed what you needed. "
    "Otherwise please keep it open and help us by being as clear as you can "
    "about what the linked request **didn't** cover — that detail is what tells "
    "us this is genuinely something new."
)
# Mixed case: shown after the open-request ask above.
DUPE_ALSO_CLOSED_INTRO = "Also previously requested, now closed:"
PINNED_POSTS_HEADING = "### 📌 Current support notice"
PINNED_POSTS_INTRO = (
    "A pinned Music Assistant support post mentions the affected provider:"
)
PROVIDER_DOCS_HEADING = "### 📖 Provider documentation"
