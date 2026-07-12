# Music Assistant triage bot

Autonomous, AI-assisted triage for issues and Discussions in
`music-assistant/support`.

The bot reads the **diagnostics file** that reporters attach (produced by
_Settings → Download diagnostics_ in Music Assistant), or falls back to scanning
an attached **raw log file** (for older versions without the diagnostics
feature), posts a single sticky summary comment, applies setup/provider labels,
involves community provider maintainers, surfaces docs-grounded answers and
similar past reports, and manages the issue's response state. New/edited
Discussions receive the same docs-grounded help without issue-specific
diagnostics or label handling.

> **Live configuration in this repository:** deterministic triage, AI assessment,
> RAG and Discussion triage are all enabled; dry-run is off. The code retains
> safe defaults (`TRIAGE_DRY_RUN=true`, AI/Discussions off) for a fresh install.
> User-visible mutations are made by the `musicassistant-bot` GitHub App.

## How it works

Thin workflows call a small, testable Python package (`ma_triage`). All issue
content is treated as **untrusted** and is passed to the script via `env:` —
never interpolated into a shell command.

```
.github/
├── workflows/
│   ├── triage.yml            # issues opened/edited/reopened + new comments
│   ├── discussions.yml       # new/edited Discussions
│   ├── triage_scheduled.yml  # daily reminder / auto-close sweep
│   ├── docs_embeddings.yml   # nightly RAG index build (docs + posts)
│   └── lock_threads.yml      # lock old closed threads
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
- **translation**: translation contributions use a GitHub **Discussion** contact
  link rather than an issue form. The legacy label-based skip remains as a safety
  net.

### Deterministic analysis
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

### Evidence-grounded AI assessment
The live bot first gathers a bounded evidence pack:
diagnostics, the exact provider documentation page + retrieved doc sections,
provider-matched pinned/related reports, and lexically relevant excerpts from
the official server source at the reported release tag (falling back to `dev`).
Only then does GitHub Models produce a strictly-typed assessment: category,
confidence, likely cause, concrete evidence and a maintainer verification step.
The prompt explicitly distinguishes official Docker/HA add-on packaging from
manual installations, so managed dependencies are never pushed back onto those
users. Any retrieval/model failure degrades gracefully to the available
evidence/deterministic result. Models calls use `GH_MODELS_TOKEN`; the assessment
renders as a collapsed `<details>` block for maintainers.

### Docs-grounded answers & similar reports
The live bot adds a **retrieval-augmented** layer on top of the analysis:

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
- **Provider-aware docs.** The provider manifest's authoritative documentation
  page is promoted into the retrieved doc set instead of relying on semantic
  ranking alone.
- **Confidence tiers.** `HIGH` (≥ `TRIAGE_ANSWER_HI`) posts a doc-grounded answer
  with cited links; `MEDIUM` (≥ `TRIAGE_ANSWER_LO`) posts doc links only;
  `LOW` stays silent (deterministic triage and duplicate links may still post).
  An answer matching a previously down-voted (`suppress.json`) fingerprint is
  demoted a tier.
- **Cost.** Per actionable issue: **1 embedding + up to 2 chat calls** (docs
  judge + evidence-grounded assessment). Discussions use 1 embedding + up to
  1 docs judge. Indexing runs nightly, cached by content SHA (unchanged chunks
  are never re-embedded) and skips on rate-limit. All output is rendered in the
  same sticky comment, and everything echoed is sanitized.

The two indexes (`docs.json`, `posts.json`) and suppression fingerprints (when
present, `suppress.json`) are stored as JSON on an orphan **`triage-index`** branch
(keeping `main` clean) and read at runtime. The posts index retains bounded body
excerpts and provider identity for evidence-grounded assessment. Automatic
👍/👎 reaction harvesting is **not implemented yet**; suppression data is
currently read-only/manual. Missing indexes degrade gracefully without breaking
deterministic triage.

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
| Variable | Safe default | Live value | Purpose |
|---|---|---|---|
| `TRIAGE_DRY_RUN` | `true` | `false` | Kill switch; `true` logs without mutating. |
| `TRIAGE_AI_ENABLED` | `false` | `true` | Evidence-grounded GitHub Models assessment. |
| `TRIAGE_RAG_ENABLED` | `true` | `true` (default) | Docs answers, pinned notices and related reports. |
| `TRIAGE_DISCUSSIONS_ENABLED` | `false` | `true` | Docs-grounded triage on new/edited Discussions. |
| `TRIAGE_SCAN_LOGS` | `true` | `true` (default) | Redact and scan a raw log when diagnostics are absent. |
| `TRIAGE_AI_MODEL` | `openai/gpt-4o-mini` | default | Evidence assessment model. |
| `TRIAGE_ANSWER_MODEL` | `openai/gpt-4o` | default | Docs judge/answer model. |
| `TRIAGE_EMBED_MODEL` | `openai/text-embedding-3-small` | default | Docs/posts embedding model. |
| `TRIAGE_EMBED_DIM` | `512` | default | Reduced embedding dimensionality. |
| `TRIAGE_ANSWER_HI` / `LO` | `0.75` / `0.45` | default | Full-answer / links-only thresholds. |
| `TRIAGE_INDEX_BRANCH` | `triage-index` | default | Orphan branch holding JSON indexes. |
| `TRIAGE_INDEX_MAX_POSTS` | `500` | default | Similar-report index cap. |
| `TRIAGE_RELATED_EXPAND_SCORE` | `0.80` | default | Expand only strong related-report matches. |
| `TRIAGE_SERVER_REF` | `dev` | default | Current server fallback for manifests/code evidence. |
| `TRIAGE_PINNED_EXCLUDE_CATEGORIES` | `feature polls` | default | Pinned categories not treated as support notices. |

Additional retrieval/model tuning variables are documented inline in
`ma_triage/config.py`; unset/empty Actions variables use those safe defaults.

### RAG indexes (`triage-index` branch)
The `docs_embeddings.yml` workflow builds `docs.json` / `posts.json` and commits
them to the orphan `triage-index` branch. It runs nightly, on manual
`workflow_dispatch`, and on a `repository_dispatch` (`docs-changed`) the docs repo
can send. Build them on demand with:

```bash
python -m ma_triage index all     # or: docs | posts
```

The index-build workflow and the separate issue/Discussion `index-append` jobs
have `contents: write` + `models: read` but no issue/Discussion write permission:
jobs that write index content can never comment, and vice versa. They honour
`TRIAGE_DRY_RUN` (dry-run previews the commit).

### Repo secrets
| Secret | Needed for | Notes |
|---|---|---|
| `GH_MODELS_TOKEN` | Models calls | Personal PAT with the **Models** permission. Required by the live App-based setup because the installation token has no Models entitlement. |
| `TRIAGE_APP_ID` | Bot identity | Numeric ID of the GitHub App installed on this repository. |
| `TRIAGE_APP_PRIVATE_KEY` | Bot identity | Complete PEM private key for the GitHub App. `actions/create-github-app-token` exchanges it for a repository-scoped, one-hour installation token in mutation jobs. |

Issue/discussion comments, labels and lifecycle mutations use the GitHub App
identity. Index commits remain on the built-in `GITHUB_TOKEN`, while Models calls
remain on `GH_MODELS_TOKEN`. Existing `github-actions` sticky comments are left
intact; new stickies are owned and updated by the App.

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
- Tier-1 code evidence comes only from fixed candidate paths in the public
  `music-assistant/server` repository at a validated release/dev ref. Relevant
  line windows, file count and total characters are capped; issue-controlled
  paths or refs are never fetched.
- Everything echoed back from a diagnostics file (or a doc / model answer) is
  escaped: `@mentions` and `#refs` are neutralised, HTML/markers are escaped,
  code spans/fences can't be broken out of, and strings are length-capped.
- Least-privilege permissions **per job**: short-lived App tokens perform
  issue/Discussion mutations but never index writes; index jobs get
  `contents: write` but no issue/Discussion mutation access. Runs are serialized
  per issue/Discussion, and index writes share one global concurrency group.

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

## Live operation

- Issue triage runs on opened/edited/reopened issues; a manual
  `workflow_dispatch` accepts an issue number for controlled re-triage.
- Discussion triage runs on newly created/edited Discussions, excluding
  configured translation categories.
- The posts index is appended on new issues/Discussions and rebuilt nightly with
  the docs index; maintainers can manually dispatch `docs_embeddings.yml`.
- Set `TRIAGE_DRY_RUN=true` for an immediate non-mutating kill switch. Set
  `TRIAGE_AI_ENABLED=false` to retain deterministic triage without Models.
- `triage/hold` pauses automation on an issue; `triage/skip` excludes it.
- The bot does **not** dispatch coding agents or create fix PRs automatically.

> Note: the per-form required-section lists in `ma_triage/template.py` and the
> provider→label maps in `ma_triage/config.py` (`PROVIDER_LABELS` and the free-
> text `PROVIDER_TEXT_ALIASES`) should be kept in sync with the issue forms and
> the repo's labels as they evolve.
