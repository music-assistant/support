# Issue Automation

Automated issue management for the Music Assistant support repository.

## Features

### Phase 1: Core Automation ✅

#### 1. Automatic Provider Label Assignment
- Scans issue body for mentions of music and player providers
- Automatically applies corresponding provider labels
- Creates labels dynamically if they don't exist
- Supports 20+ providers with smart alias matching

#### 2. Maintainer Assignment
- Fetches provider manifest files from `music-assistant/server` repository
- Extracts maintainer information from each provider's `manifest.json`
- Automatically assigns maintainers to relevant issues/PRs
- Skips generic "music_assistant" maintainer
- Falls back to @mentions if assignment fails

#### 3. Template Validation
- Checks that required issue template sections are filled out
- Validates that log files are attached (not pasted)
- Posts a helpful comment when validation fails with specific issues
- Only comments once to avoid spam

### Phase 2: Intelligent Log Analysis ✅

#### 4. Pattern-Based Log Analysis
- **20+ comprehensive error patterns** detected automatically:
  - Authentication & token issues (Spotify, Tidal, generic)
  - Network connectivity (timeouts, mDNS/multicast, connection resets)
  - Rate limiting (provider-specific and generic)
  - Provider-specific errors (Librespot, YouTube Music PO token)
  - Playback quality (dropouts, buffering, sync issues)
  - Metadata/tag errors
  - SSL/certificate problems
  - Missing dependencies
  - Region restrictions

- **Provider-specific analysis:**
  - Detects which providers are mentioned in logs
  - Applies provider-specific troubleshooting
  - Links to relevant documentation

- **Severity classification:**
  - 🚨 Critical (requires immediate attention)
  - ❌ Error (blocks functionality)
  - ⚠️ Warning (degraded experience)
  - ℹ️ Info (minor issues)

#### 5. AI-Powered Analysis (Optional)
- Uses **Claude AI** for intelligent log interpretation
- Provides contextual analysis beyond pattern matching
- Identifies root causes and suggests step-by-step solutions
- Determines if issue is a bug or configuration problem
- **Requires:** `ANTHROPIC_API_KEY` secret in repository settings
- **Graceful fallback:** Works without AI using pattern matching

#### 6. Automated Troubleshooting Suggestions
- Specific, actionable guidance for each detected issue
- Links to official documentation where relevant
- Network troubleshooting for common blockers (Pi-hole, AdGuard, VPN/VLAN)
- Provider-specific auth refresh instructions
- Device-specific recommendations

## How It Works

The bot runs as a GitHub Actions workflow triggered on:
- `issues.opened` and `issues.edited`
- `pull_request_target.opened` and `pull_request_target.edited`

### Workflow Process

1. **Provider Detection**
   - Extracts text from issue sections (Music Providers, Player Providers, Problem description)
   - Matches against known providers using aliases from `provider_mappings.json`
   - Fetches manifest from: `music-assistant/server/main/music_assistant/providers/{provider}/manifest.json`

2. **Label & Maintainer Assignment**
   - Applies provider labels automatically
   - Assigns maintainers based on manifest data
   - Creates labels dynamically if needed

3. **Template Validation**
   - Checks required sections are completed
   - Verifies log attachment (not pasted)
   - Posts validation feedback if issues found

4. **Log Analysis (Phase 2)**
   - Downloads attached log files from GitHub
   - Runs pattern-based analysis (20+ error patterns)
   - Optionally runs AI analysis if API key available
   - Posts comprehensive troubleshooting comment

## Configuration

### Provider Mappings

Edit `.github/scripts/provider_mappings.json`:

```json
{
  "music_providers": {
    "provider_directory_name": ["alias1", "alias2", "common name"]
  },
  "player_providers": {
    "provider_directory_name": ["alias1", "alias2"]
  }
}
```

**Example:**
```json
{
  "music_providers": {
    "spotify": ["spotify"],
    "youtube_music": ["youtube music", "ytmusic", "yt music"]
  }
}
```

### AI Analysis Setup (Optional)

To enable AI-powered log analysis:

1. Get an Anthropic API key from https://console.anthropic.com/
2. Add it as a repository secret:
   - Go to repository Settings → Secrets and variables → Actions
   - Create new secret: `ANTHROPIC_API_KEY`
   - Paste your API key

**Note:** The bot works fine without AI analysis - pattern matching alone provides excellent coverage of common issues.

### Supported Providers

#### Music Providers
- Spotify, Tidal, Qobuz, YouTube Music, Apple Music
- Deezer, SoundCloud, TuneIn, RadioBrowser
- Plex, Jellyfin, Subsonic
- Filesystem (Local), URL, Builtin, Audiobookshelf

#### Player Providers
- Slimproto (Squeezebox), Sonos, AirPlay
- Cast (Chromecast/Google Cast), DLNA, Snapcast
- Home Assistant, Fully Kiosk

## Error Detection Examples

### Network Issues
```
🚨 Detected: "Player Discovery Issues (mDNS/Multicast)"
Suggestion:
- mDNS/multicast traffic must NOT be blocked
- Check Pi-hole, AdGuard, pfSense settings
- Ensure devices on same Layer 2 network
- VPN/VLAN separation prevents discovery
→ Links to troubleshooting guide
```

### Authentication Errors
```
❌ Detected: "Spotify Authentication Issue"
Provider: Spotify
Suggestion:
- Re-authenticate in Settings → Providers → Spotify
- Consider custom Spotify Client ID for better reliability
- Check popup blockers
- Verify Spotify Premium account
```

### Rate Limiting
```
⚠️ Detected: "Spotify API Rate Limit"
Suggestion:
- Using default Client ID has heavy rate limiting
- Configure custom Spotify Client ID
- Go to Settings → Providers → Spotify
- Add your own Client ID/Secret
```

## Files Structure

```
.github/
├── workflows/
│   ├── issue_triage_bot.yml          # Triage bot workflow (provider labels, log analysis)
│   ├── response_tracker.yml          # Response state tracking (needs-attention / waiting-for-user)
│   ├── stale_issues.yml              # Stale issue auto-close
│   └── lock_threads.yml              # Lock closed threads after 30 days
└── scripts/
    ├── triage_bot.py                 # Main bot logic
    ├── log_analyzer.py               # Phase 2: Intelligent log analysis
    ├── provider_mappings.json        # Provider aliases configuration
    ├── backfill_labels.py            # One-time backfill for response-state labels
    └── README.md                     # This documentation
```

## Phase 2 Enhancements

### Comprehensive Error Patterns

Based on extensive research of the Music Assistant codebase and issue history, the log analyzer now detects:

**Authentication Issues:**
- Token expiration (all providers)
- Spotify-specific auth problems
- Tidal session failures
- Refresh token issues

**Network Problems:**
- Connection timeouts
- mDNS/multicast blocking
- VPN/VLAN separation
- Connection resets during playback
- Pi-hole/AdGuard/pfSense blocking

**Provider-Specific:**
- Spotify Librespot timeouts
- Spotify rate limiting (with Client ID solution)
- Tidal rate limiting
- YouTube Music PO token requirements

**Playback Issues:**
- Audio dropouts
- Buffer underruns
- Player sync/grouping conflicts

**Configuration Problems:**
- SSL/certificate errors
- Missing Python dependencies
- Region restrictions
- Metadata/tag corruption

### AI Analysis Capabilities

When enabled, Claude AI provides:
- **Root cause identification** from complex log patterns
- **Contextual understanding** of issue descriptions + logs
- **Step-by-step troubleshooting** tailored to the specific problem
- **Bug vs configuration** determination
- **Actionable insights** beyond simple pattern matching

### Smart Features

- **Deduplication:** Won't post multiple analysis comments
- **Severity sorting:** Shows most critical issues first
- **Provider detection:** Only shows relevant provider-specific errors
- **Graceful degradation:** AI optional, pattern matching always works
- **Combined analysis:** Shows both pattern-based and AI insights

## Testing

### Local Testing

```bash
cd .github/scripts

# Set environment variables
export GITHUB_TOKEN="your_token"
export ISSUE_NUMBER="123"
export ISSUE_BODY="$(gh issue view 123 --json body -q .body)"
export ISSUE_TITLE="$(gh issue view 123 --json title -q .title)"
export REPOSITORY="music-assistant/support"
export IS_PULL_REQUEST="false"

# Optional: Enable AI analysis
export ANTHROPIC_API_KEY="your_api_key"

# Run the bot
python triage_bot.py
```

### Testing Log Analyzer

```python
from log_analyzer import LogAnalyzer

# Test pattern detection
log_content = """
ERROR: Spotify authentication failed
WARNING: Connection timeout while connecting to player
INFO: Rate limit exceeded, retrying in 30s
"""

analyzer = LogAnalyzer(log_content)
issues = analyzer.analyze()
comment = analyzer.generate_comment()
print(comment)
```

## Debugging

The bot outputs detailed logs in GitHub Actions:
- Detected providers
- Labels added
- Maintainers assigned
- Validation issues found
- Log files downloaded
- Pattern matches detected
- AI analysis status

Check the **Actions** tab for each workflow run's output.

## Maintenance

### Adding New Providers
1. Edit `provider_mappings.json`
2. Add provider directory name and aliases
3. Commit and push

### Adding New Error Patterns
1. Edit `log_analyzer.py`
2. Add pattern to `ERROR_PATTERNS` dictionary
3. Specify severity, title, description, suggestion
4. Optionally set provider-specific

### Updating Documentation
When providers or patterns change, update:
- This README
- Provider lists in "Supported Providers"
- Example outputs in "Error Detection Examples"

## Dependencies

- **Python 3.11+**
- **PyGithub** - GitHub API interactions
- **requests** - HTTP client for manifest fetching and log downloads
- **anthropic** (optional) - AI-powered log analysis

## Permissions

The workflow requires:
- ✅ `issues: write` - Add labels, assign users, post comments
- ✅ `pull-requests: write` - Triage PRs
- ✅ `contents: read` - Checkout repository

## Performance

- **Pattern analysis:** ~100-500ms for typical log files
- **AI analysis:** ~2-5 seconds (when enabled)
- **Total workflow:** ~10-30 seconds including downloads

## Response State Tracking

Automated tracking of which issues need maintainer attention vs. waiting for user response.

### Labels

| Label | Purpose |
|-------|---------|
| `needs-attention` | Issue needs maintainer/collaborator response |
| `waiting-for-user` | Waiting for the issue author to respond |
| `stale` | No activity for an extended period |
| `auto-closed` | Closed automatically due to inactivity |

### How It Works

The `response_tracker.yml` workflow automatically manages labels based on who comments:

- **New/reopened issue** → `needs-attention` added
- **Maintainer comments** (not the issue author) → `needs-attention` removed, `waiting-for-user` added
- **Issue author comments** → `waiting-for-user` removed, `needs-attention` added
- **Bot/community comments** → no label changes

The triage bot also sets `waiting-for-user` when it posts template validation comments.

### Filtering Issues

View all issues needing your attention:
```
is:issue is:open label:needs-attention
```

### Stale Issue Management

The `stale_issues.yml` workflow runs daily and handles two cases:

1. **Unresponsive users** (issues with `waiting-for-user`): 14 days → stale warning, 3 more days → auto-close
2. **Dormant issues** (general inactivity): 60 days → stale warning, 14 more days → auto-close

Exempt labels: `bug-confirmed`, `enhancement`, `pinned`

### Thread Locking

The `lock_threads.yml` workflow locks closed issues after 30 days of inactivity, directing users to open new issues.

### Backfilling Existing Issues

Run the one-time backfill script to label all existing open issues:

```bash
cd .github/scripts
GITHUB_TOKEN=ghp_xxx python backfill_labels.py
```

## Future Enhancements

Potential additions:
- Cross-reference with known GitHub issues
- Link to similar resolved issues
- Track error frequency across issues
- Provider status checking (API outages)
- Integration with Discord notifications
- Weekly summary reports of common issues

## Support

For issues with the triage bot itself:
- Check GitHub Actions logs for errors
- Verify environment variables are set
- Test locally with sample data
- Open an issue in the support repo

## Credits

Built using comprehensive research of:
- Music Assistant server codebase error patterns
- Historical issue analysis
- Documentation troubleshooting guides
- Community discussions

Pattern detection based on real-world issues from the Music Assistant community.
