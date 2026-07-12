# Music Assistant issue triage bot (experimental)

Autonomous, AI-assisted triage for issues in `music-assistant/support`.

The bot reads the **diagnostics file** that reporters attach (produced by
_Settings → Download diagnostics_ in Music Assistant), or falls back to scanning
an attached **raw log file** (for older versions without the diagnostics
feature), posts a single sticky summary comment, applies setup/provider labels,
involves community provider maintainers, surfaces docs-grounded answers and
similar past issues, and manages the issue's response state.

> ⚠️ **Experimental & dry-run by default.** With `TRIAGE_DRY_RUN` unset or
> `true`, the bot makes **no changes** — it only writes what it _would_ do to
> the Actions job summary. Set the repo variable `TRIAGE_DRY_RUN=false` to go
> live.

## How it works

Thin workflows call a small, testable Python package (`ma_triage`). All issue
content is treated as **untrusted** and is passed to the script via `env:` —
never interpolated into a shell command.

```
.github/
├── workflows/
│   ├── triage.yml            # issues opened/edited/reopened + new comments
│   ├── triage_scheduled.yml  # daily reminder / auto-close sweep
│   └── docs_embeddings.yml   # nightly RAG index build (docs + posts)
└── scripts/
    ├── ma_triage/            # the bot (see module docstrings)
    ├── requirements.txt      # just `requests`
    └── tests/                # offline pytest suite + fixtures
```

### Issue forms
The bot branches on the issue form (detected from labels):
- **main bug report** (`triage`): full diagnostics/log analysis + summary;
- **frontend bug** (`triage`, `frontend`): checks a screenshot/recording is
  attached and required fields are filled — stays silent when the report is
  complete;
- **translation**: translation contributions are moving to a GitHub **Discussion**
  (via a contact link in the issue chooser) rather than an issue form, so no
  issue carries a `translation` label anymore. The label-based skip guard is kept
  as a harmless safety net.

### Tier 0 — deterministic (always on)
From the diagnostics file the bot derives, with no AI:
- **version check** vs the latest server release (outdated / pre-release);
- **safe mode** banner;
- **providers in error** (with sanitized error text);
- **top exception fingerprints** by count;
- **provider/setup labels** — provider labels come only from the provider reported
  in the title/form text (never the full diagnostics census); title matches win
  over incidental comparisons in the body;
- the reported provider's authoritative **documentation link** and, for one
  actionable provider, its community **codeowner** (from the current server
  manifest on `dev`, skipping the core `@music-assistant` team);
- low-disk and other resource hints.

If only a **raw log file** is attached (older Music Assistant versions), the bot
redacts it first — stripping tokens, home directories, emails, MAC addresses and
non-local IPs — then extracts the version banner, safe-mode, provider setup
errors and exception fingerprints from the redacted text. Only derived facts and
redacted snippets are ever echoed. Controlled by `TRIAGE_SCAN_LOGS` (default on).

If no usable attachment is present, or required template sections are empty, the
bot posts a friendly request explaining how to download the diagnostics report.

### Tier 1 — GitHub Models (optional)
When `TRIAGE_AI_ENABLED=true`, a bounded, sanitized summary is sent to the
GitHub Models API for a short, strictly-typed assessment (category, confidence,
likely cause, possibly-fixed-in version). Any failure degrades gracefully to the
Tier-0 result. Uses the default `GITHUB_TOKEN` with `models: read`, or a
`GH_MODELS_TOKEN` PAT when set. The assessment renders as a collapsed
`<details>` block for maintainers.

### Docs-grounded answers & similar reports (Phase 2, optional)
When `TRIAGE_AI_ENABLED=true` (and `TRIAGE_RAG_ENABLED` is not `false`), the bot
adds a **retrieval-augmented** layer on top of the tiers above, modelled on
`zwave-js-bot`:

- **Docs Q&A.** The incoming issue is embedded once and matched against an index
  of the public docs (`music-assistant/music-assistant.io`, chunked by heading).
  Retrieval is hybrid and entirely local — dense cosine **plus** BM25 over the
  breadcrumbs+body, fused with Reciprocal Rank Fusion — so exact tokens (provider
  domains, error codes) are not lost. The top chunks and the issue go to a single
  judge call that returns `{answers_question, confidence, answer, cited_sections}`.
- **Similar past reports.** The issue embedding is compared (dense cosine) to an
  index of past issues + discussions to surface likely duplicates / prior answers.
  When a provider is known, candidates must match that provider exactly; weak
  matches stay collapsed, while only strong matches render expanded. Pinned
  support notices that mention the provider are surfaced separately and Feature
  Polls are ignored. Translation-category discussions are excluded from the
  index. New/edited Discussions use the same RAG path when
  `TRIAGE_DISCUSSIONS_ENABLED=true`.
- **Confidence tiers.** `HIGH` (≥ `TRIAGE_ANSWER_HI`) posts a doc-grounded answer
  with cited links; `MEDIUM` (≥ `TRIAGE_ANSWER_LO`) posts doc links only;
  `LOW` stays silent (deterministic triage and duplicate links may still post).
  An answer matching a previously down-voted (`suppress.json`) fingerprint is
  demoted a tier.
- **Cost.** Per issue: **1 embedding + ≤1 judge chat**, only when AI is enabled.
  Indexing runs nightly, cached by content SHA (unchanged chunks are never
  re-embedded) and skips on rate-limit. All output is rendered as extra sections
  in the same sticky comment, and everything echoed is sanitized.

The two indexes (`docs.json`, `posts.json`) and the down-vote fingerprints
(`suppress.json`) are stored as JSON on an orphan **`triage-index`** branch
(keeping `main` clean) and read at runtime. When they are absent the whole layer
degrades gracefully and Tier-0/Tier-1 behaviour is unchanged.

## Response-state lifecycle

| Trigger | Effect |
|---|---|
| issue opened, info/diagnostics missing | request info; `waiting-for-user` |
| issue opened, valid diagnostics | analyse + label; `needs-attention` |
| reporter comments | `needs-attention`; clears `waiting-for-user` + reminders |
| maintainer comments | `waiting-for-user`; clears `needs-attention` |
| `waiting-for-user` ≥ 3 days | gentle reminder (`triage/reminded-1`) |
| `waiting-for-user` ≥ 7 days | close warning (`triage/reminded-2`) |
| ≥ 14 days inactivity | auto-close politely (reopen invite) |

Exempt from reminders/close: `bug`, `enhancement`, `pinned`,
`Fix to be Confirmed`, `triage/hold`. Closed threads are locked by the separate
`lock_threads.yml` workflow.

Maintainer override labels: `triage/hold` (pause automation), `triage/skip`
(never triage).

## Configuration

### Repo variables (Settings → Secrets and variables → Actions → Variables)
| Variable | Default | Purpose |
|---|---|---|
| `TRIAGE_DRY_RUN` | `true` | Kill switch. `false` to make real changes. |
| `TRIAGE_AI_ENABLED` | `false` | Enable Tier-1 GitHub Models assessment. |
| `TRIAGE_SCAN_LOGS` | `true` | Scan an attached raw log (redacted) when no diagnostics report is present. |
| `TRIAGE_AI_MODEL` | `openai/gpt-4o-mini` | Model id for Tier 1. |
| `TRIAGE_RAG_ENABLED` | `true` | Sub-flag for the Phase-2 RAG layer (still requires `TRIAGE_AI_ENABLED`). |
| `TRIAGE_DISCUSSIONS_ENABLED` | `false` | Enable docs-grounded triage on new/edited Discussions. |
| `TRIAGE_EMBED_MODEL` | `openai/text-embedding-3-small` | Embeddings model (GitHub Models). |
| `TRIAGE_EMBED_DIM` | `512` | Embedding dimensionality (keeps indexes small). |
| `TRIAGE_ANSWER_MODEL` | `openai/gpt-4o` | Judge/answer chat model. |
| `TRIAGE_ANSWER_HI` | `0.75` | Min confidence for a full doc-grounded answer. |
| `TRIAGE_ANSWER_LO` | `0.45` | Min confidence for doc links only. |
| `TRIAGE_DOCS_REPO` | `music-assistant/music-assistant.io` | Public docs source. |
| `TRIAGE_INDEX_BRANCH` | `triage-index` | Orphan branch holding the JSON indexes. |
| `TRIAGE_INDEX_MAX_POSTS` | `500` | Cap on posts embedded into the similar-posts index. |
| `TRIAGE_RELATED_EXPAND_SCORE` | `0.80` | Similarity score required to expand related posts; weaker provider-matched results are collapsed. |
| `TRIAGE_SERVER_REF` | `dev` | Server ref used for provider documentation/codeowner manifests. |
| `TRIAGE_PINNED_EXCLUDE_CATEGORIES` | `feature polls` | Pinned Discussion categories excluded from support notices. |

### RAG indexes (`triage-index` branch)
The `docs_embeddings.yml` workflow builds `docs.json` / `posts.json` and commits
them to the orphan `triage-index` branch. It runs nightly, on manual
`workflow_dispatch`, and on a `repository_dispatch` (`docs-changed`) the docs repo
can send. Build them on demand with:

```bash
python -m ma_triage index all     # or: docs | posts
```

The index-build workflow (and the small `index-append` job in `triage.yml` that
appends each new issue) has `contents: write` + `models: read` but **no**
`issues:` permission — the job that can write repo contents can never comment,
and vice-versa. Both honour `TRIAGE_DRY_RUN` (dry-run previews the commit).

### Repo secrets
| Secret | Needed for | Notes |
|---|---|---|
| `GH_MODELS_TOKEN` | Tier 1 / RAG (optional) | PAT with the **Models** permission. Used for GitHub Models calls (embeddings + judge/assessment) when the org hasn't enabled Models for the default Actions token. Falls back to `GITHUB_TOKEN` when unset. |
| `TRIAGE_APP_ID` | Bot identity | Numeric ID of the GitHub App installed on this repository. |
| `TRIAGE_APP_PRIVATE_KEY` | Bot identity | Complete PEM private key for the GitHub App. `actions/create-github-app-token` exchanges it for a repository-scoped, one-hour installation token in mutation jobs. |

Issue/discussion comments, labels and lifecycle mutations use the GitHub App
identity. Index commits remain on the built-in `GITHUB_TOKEN`, while Models calls
remain on `GH_MODELS_TOKEN`. Existing `github-actions` sticky comments are left
unchanged during the rollout; new stickies are owned and updated by the App.

## Security model

- Triggers are `issues`, `issue_comment`, `discussion`, `schedule`,
  `workflow_dispatch` and `repository_dispatch` — **no
  `pull_request_target`**.
- Mutation jobs mint short-lived tokens from a narrowly scoped GitHub App; jobs
  that only manage issue lifecycle further restrict their token to Issues write.
  The built-in workflow token no longer has issue/discussion write access.
- Issue content flows through `env:` → `os.environ`; it is never placed in a
  shell command line.
- Attachment downloads are **host-allowlisted** (`user-attachments` / repo
  `files`) and **byte-capped** while streaming; JSON is parsed with size/depth
  guards; nothing from a file is ever executed.
- The docs corpus comes from the **public** docs repo (read with the default
  token, no secret); doc text is comparatively trusted but is still sanitized
  before it is echoed into a comment.
- Everything echoed back from a diagnostics file (or a doc / model answer) is
  escaped: `@mentions` and `#refs` are neutralised, HTML/markers are escaped,
  code spans/fences can't be broken out of, and strings are length-capped.
- Least-privilege permissions **per job**: the commenting jobs get `issues:
  write` but never `contents: write`; the index-writing jobs get `contents:
  write` + `models: read` but never `issues:` access. One concurrent run per issue.

## Local development / testing

```bash
cd .github/scripts
python -m venv .venv && . .venv/bin/activate
pip install -r requirements.txt pytest
pytest -q            # fully offline; uses fixtures under tests/fixtures/
```

Run a subcommand locally in dry-run against a real issue (read-only):

```bash
export GITHUB_TOKEN=... REPOSITORY=music-assistant/support TRIAGE_DRY_RUN=true
export ISSUE_NUMBER=123
ISSUE_TITLE="$(gh issue view 123 --json title -q .title)" \
ISSUE_BODY="$(gh issue view 123 --json body -q .body)" \
python -m ma_triage triage
```

## Rollout

1. Land with `TRIAGE_DRY_RUN=true`; review job summaries on real issues.
2. Set `TRIAGE_DRY_RUN=false` to enable Tier-0/1 actions.
3. Enable `TRIAGE_AI_ENABLED=true` (optionally provide `GH_MODELS_TOKEN`) and run
   the RAG index build once for docs-grounded answers + similar issues.

> Note: the per-form required-section lists in `ma_triage/template.py` and the
> provider→label maps in `ma_triage/config.py` (`PROVIDER_LABELS` and the free-
> text `PROVIDER_TEXT_ALIASES`) should be kept in sync with the issue forms and
> the repo's labels as they evolve.
