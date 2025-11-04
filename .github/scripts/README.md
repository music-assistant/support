# Issue Triage Bot

An automated bot for triaging issues and pull requests in the Music Assistant support repository.

## Features

### 1. Automatic Provider Label Assignment
- Scans issue body for mentions of music and player providers
- Automatically applies corresponding provider labels
- Creates labels dynamically if they don't exist

### 2. Maintainer Assignment
- Fetches provider manifest files from `music-assistant/server` repository
- Extracts maintainer information from each provider's `manifest.json`
- Automatically assigns maintainers to relevant issues
- Skips generic "music_assistant" maintainer

### 3. Template Validation
- Checks that required issue template sections are filled out
- Validates that log files are attached (not pasted)
- Posts a helpful comment when validation fails with specific issues
- Only comments once to avoid spam

## How It Works

The bot runs as a GitHub Actions workflow triggered on:
- `issues.opened`
- `issues.edited`
- `pull_request_target.opened`
- `pull_request_target.edited`

### Provider Detection

The bot uses a smart matching system to detect providers:

1. **Extracts text** from issue sections:
   - "Music Providers"
   - "Player Providers"
   - "The problem"
   - Issue title

2. **Matches against known providers** using aliases defined in `provider_mappings.json`:
   - Example: "YouTube Music", "ytmusic", "yt music" all map to `youtube_music`
   - Case-insensitive matching

3. **Fetches provider manifests** from the server repo:
   - URL: `https://raw.githubusercontent.com/music-assistant/server/main/music_assistant/providers/{provider}/manifest.json`

4. **Extracts maintainers** from the manifest's `maintainers` field

### Template Validation Rules

The bot checks for:
- ✅ Required sections present and non-empty:
  - "The problem"
  - "How to reproduce"
  - "Music Providers"
  - "Player Providers"
  - "Full log output"
  - "Additional information"
- ✅ Log file is attached (not pasted inline)
- ✅ No placeholder text remains in the issue

## Configuration

### Adding New Providers

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

### Supported Providers

#### Music Providers
- Spotify
- Tidal
- Qobuz
- YouTube Music
- Apple Music
- Deezer
- SoundCloud
- TuneIn
- RadioBrowser
- Plex
- Jellyfin
- Subsonic
- Filesystem (Local)
- URL
- Builtin
- Audiobookshelf

#### Player Providers
- Slimproto (Squeezebox)
- Sonos
- AirPlay
- Cast (Chromecast/Google Cast)
- DLNA
- Snapcast
- Home Assistant
- Fully Kiosk

## Files

- `.github/workflows/issue_triage_bot.yml` - GitHub Actions workflow
- `.github/scripts/triage_bot.py` - Main bot logic
- `.github/scripts/provider_mappings.json` - Provider name mappings
- `.github/scripts/README.md` - This documentation

## Future Enhancements

### Planned Features
- Log file analysis for common errors
- Automatic detection of known issues with links to existing issues
- Documentation cross-referencing based on error patterns
- Severity classification based on issue content

### Log Analysis Patterns (Future)
- Connection timeouts
- Authentication failures
- Network configuration issues
- Missing dependencies
- API rate limiting
- Media format incompatibilities

## Maintenance

### Updating Provider Mappings
When new providers are added to the server repository:
1. Edit `provider_mappings.json`
2. Add the provider directory name as a key
3. Add common aliases as values in the array
4. Commit and push

### Testing Changes
To test the bot locally:
```bash
cd .github/scripts
export GITHUB_TOKEN="your_token"
export ISSUE_NUMBER="123"
export ISSUE_BODY="$(gh issue view 123 --json body -q .body)"
export ISSUE_TITLE="$(gh issue view 123 --json title -q .title)"
export REPOSITORY="music-assistant/support"
export IS_PULL_REQUEST="false"
python triage_bot.py
```

### Debugging
The bot outputs detailed logs in the GitHub Actions run:
- Detected providers
- Labels added
- Maintainers assigned
- Validation issues found

Check the Actions tab for each run's output.

## Permissions

The workflow requires:
- `issues: write` - To add labels and assign users
- `pull-requests: write` - To triage PRs
- `contents: read` - To checkout the repository

## Dependencies

- Python 3.11+
- PyGithub - GitHub API wrapper
- requests - HTTP client for fetching manifests
