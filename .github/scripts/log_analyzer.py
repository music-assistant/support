#!/usr/bin/env python3
"""
Enhanced Log Analysis Module for Music Assistant

This module analyzes Music Assistant log files for common issues using:
1. Pattern-based detection for known errors
2. Provider-specific error analysis
3. AI-powered intelligent analysis (optional, requires Anthropic API key)
"""

import re
import os
from typing import List, Dict, Optional, Set
from dataclasses import dataclass
from enum import Enum


class Severity(Enum):
    """Issue severity levels."""
    CRITICAL = "critical"
    ERROR = "error"
    WARNING = "warning"
    INFO = "info"


@dataclass
class DetectedIssue:
    """Represents a detected issue in the log."""
    type: str
    severity: Severity
    title: str
    description: str
    suggestion: str
    provider: Optional[str] = None
    doc_link: Optional[str] = None


class LogAnalyzer:
    """Analyzes Music Assistant log files for common issues."""

    # Base documentation URL
    DOCS_BASE = "https://music-assistant.io/faq/troubleshooting"

    # Comprehensive error patterns based on research
    ERROR_PATTERNS = {
        # Authentication & Token Issues
        "token_expired": {
            "pattern": r"(token.*expired|refresh.*token.*failed|re-authentication required|loginf?ailed)",
            "severity": Severity.ERROR,
            "title": "Authentication Token Expired",
            "description": "Provider authentication has expired or failed",
            "suggestion": (
                "Your provider authentication needs to be refreshed:\n"
                "1. Go to MA Settings → Providers\n"
                "2. Find the affected provider and re-authenticate\n"
                "3. If issues persist, remove and re-add the provider\n"
                "4. Check that your provider account is active and in good standing"
            )
        },

        "spotify_auth": {
            "pattern": r"(spotify.*authentication|spotify.*login|spotify.*token)",
            "severity": Severity.ERROR,
            "title": "Spotify Authentication Issue",
            "description": "Spotify authentication failed",
            "suggestion": (
                "Spotify authentication problems:\n"
                "- Go to Settings → Providers → Spotify and re-authenticate\n"
                "- Consider using a custom Spotify Client ID for better reliability\n"
                "- Ensure popup blockers aren't preventing the auth window\n"
                "- Verify you're using a Spotify Premium account"
            ),
            "provider": "spotify"
        },

        "tidal_auth": {
            "pattern": r"(tidal.*authentication|tidal.*login|tidal.*session)",
            "severity": Severity.ERROR,
            "title": "Tidal Authentication Issue",
            "description": "Tidal session or authentication failed",
            "suggestion": (
                "Tidal authentication needs refresh:\n"
                "- Re-authenticate in Settings → Providers → Tidal\n"
                "- Make sure to copy the full redirect URL correctly\n"
                "- Verify your Tidal subscription is active"
            ),
            "provider": "tidal"
        },

        # Network & Connectivity Issues
        "network_timeout": {
            "pattern": r"(connection\s+timeout|timed?\s+out|connection.*refused|network.*unreachable)",
            "severity": Severity.WARNING,
            "title": "Network Connection Timeout",
            "description": "Network connectivity issues detected",
            "suggestion": (
                "Network connectivity problems detected. Common causes:\n\n"
                "**If using Pi-hole, AdGuard, or pfSense:**\n"
                "- These tools can block mDNS/multicast traffic\n"
                "- Add exceptions for your local network\n"
                "- Disable DNS blocking temporarily to test\n\n"
                "**If using VPN or VLAN:**\n"
                "- Music Assistant must be on the same network as your players\n"
                "- VPN/VLAN separation prevents device discovery\n"
                "- Move MA to the same network or disable VPN\n\n"
                "**General network troubleshooting:**\n"
                "- Use wired connection instead of WiFi if possible\n"
                "- Check firewall isn't blocking local traffic\n"
                "- Verify mDNS/multicast is enabled on your network\n"
                "- Restart your router and Music Assistant"
            )
        },

        "mdns_discovery": {
            "pattern": r"(mdns.*fail|multicast.*block|discovery.*fail|player.*not.*found|device.*not.*reach)",
            "severity": Severity.WARNING,
            "title": "Player Discovery Issues (mDNS/Multicast)",
            "description": "Players cannot be discovered on the network",
            "suggestion": (
                "Player discovery is failing. This is almost always a network configuration issue:\n\n"
                "**Required network configuration:**\n"
                "- mDNS/multicast traffic must NOT be blocked\n"
                "- Music Assistant and players must be on same Layer 2 network\n"
                "- IGMP snooping should be properly configured\n\n"
                "**Common blockers:**\n"
                "- Pi-hole, AdGuard, pfSense blocking multicast\n"
                "- VPN/VLAN separating networks\n"
                "- Firewall blocking discovery protocols\n"
                "- Enterprise WiFi with client isolation\n\n"
                "**Solutions:**\n"
                "- Check WiFi settings for multicast/broadcast blocking\n"
                "- Ensure devices are on same subnet\n"
                "- Use manual IP configuration if mDNS fails\n"
                f"- See: {DOCS_BASE}/#network-issues"
            )
        },

        "connection_reset": {
            "pattern": r"(connection reset|connectionreseterror|broken pipe|stream.*disconnect)",
            "severity": Severity.WARNING,
            "title": "Connection Reset During Playback",
            "description": "Network connection dropped during streaming",
            "suggestion": (
                "Connections are being reset during playback:\n"
                "- Switch to wired connection (WiFi can be unstable)\n"
                "- Check for network interference or weak signal\n"
                "- Verify no bandwidth throttling or QoS issues\n"
                "- Try restarting the affected player device"
            )
        },

        # Rate Limiting
        "rate_limit_spotify": {
            "pattern": r"(spotify.*rate.*limit|spotify.*429|spotify.*too many requests)",
            "severity": Severity.WARNING,
            "title": "Spotify API Rate Limit",
            "description": "Spotify rate limit reached",
            "suggestion": (
                "Spotify's API rate limit has been reached:\n"
                "- This is temporary and resolves automatically\n"
                "- Using the default/generic Client ID has heavy rate limiting\n"
                "- **Solution:** Configure a custom Spotify Client ID\n"
                "  - Go to Settings → Providers → Spotify\n"
                "  - Add your own Client ID/Secret from Spotify Developer Dashboard\n"
                "  - This gives you a dedicated rate limit quota\n"
                "- Avoid multiple instances using the same credentials"
            ),
            "provider": "spotify"
        },

        "rate_limit_generic": {
            "pattern": r"(rate.*limit|429|too many requests|throttle)",
            "severity": Severity.WARNING,
            "title": "API Rate Limit Exceeded",
            "description": "Provider API rate limit reached",
            "suggestion": (
                "API rate limit exceeded. This usually resolves automatically:\n"
                "- Wait 30-60 seconds for the limit window to reset\n"
                "- Reduce concurrent operations if possible\n"
                "- Check if multiple instances are using same credentials"
            )
        },

        # Provider-Specific Errors
        "librespot_timeout": {
            "pattern": r"(no audio received from librespot|librespot.*timeout|librespot.*error)",
            "severity": Severity.WARNING,
            "title": "Spotify Streaming Timeout (Librespot)",
            "description": "Librespot failed to deliver audio stream",
            "suggestion": (
                "Spotify's audio streaming component (librespot) timed out:\n"
                "- This usually resolves with automatic retry\n"
                "- Check network stability (use wired if possible)\n"
                "- If persistent, restart Music Assistant\n"
                "- Verify Spotify service is not experiencing issues"
            ),
            "provider": "spotify"
        },

        "youtube_music_po_token": {
            "pattern": r"(po.*token.*server|ytmusic.*potoken|youtube.*po token)",
            "severity": Severity.ERROR,
            "title": "YouTube Music PO Token Server Missing",
            "description": "YouTube Music requires PO token server",
            "suggestion": (
                "YouTube Music provider requires a PO Token server:\n"
                "- Install the PO Token server addon\n"
                "- Configure the server URL in YouTube Music provider settings\n"
                "- Note: YouTube Music is experimental/beta\n"
                f"- See YouTube Music documentation for setup instructions"
            ),
            "provider": "youtube_music"
        },

        # Playback Quality Issues
        "audio_dropout": {
            "pattern": r"(audio.*dropout|playback.*stop|sound.*output.*stop|no sound)",
            "severity": Severity.WARNING,
            "title": "Audio Dropout / Playback Stopped",
            "description": "Audio playback interrupted or stopped",
            "suggestion": (
                "Audio playback issues detected:\n\n"
                "**Network-related:**\n"
                "- Switch to wired connection\n"
                "- Check for WiFi interference\n"
                "- Verify sufficient bandwidth\n\n"
                "**Device-related:**\n"
                "- Power cycle the player device\n"
                "- Check device firmware is up to date\n"
                "- Verify device has sufficient resources (CPU/memory)\n\n"
                "**Music Assistant:**\n"
                "- Restart Music Assistant\n"
                "- Check buffer settings in advanced configuration\n"
                "- Try different audio quality settings"
            )
        },

        "buffer_underrun": {
            "pattern": r"(buffer.*underrun|buffering|stream.*lag|playback.*stutter)",
            "severity": Severity.WARNING,
            "title": "Audio Buffering Issues",
            "description": "Audio buffer underrun causing playback issues",
            "suggestion": (
                "Audio buffering problems (buffer underrun):\n"
                "- Network too slow for selected quality\n"
                "- Try lower quality settings\n"
                "- Use wired connection instead of WiFi\n"
                "- Check for network congestion\n"
                "- Increase buffer size in advanced settings if available"
            )
        },

        # Metadata & File Issues
        "tag_error": {
            "pattern": r"(tag.*error|metadata.*invalid|id3.*error|corrupt.*tag)",
            "severity": Severity.INFO,
            "title": "Media File Tag/Metadata Issues",
            "description": "Audio file metadata is corrupted or invalid",
            "suggestion": (
                "Media file tags/metadata have issues:\n"
                "- Use a tag editor (like MusicBrainz Picard, Mp3tag) to fix metadata\n"
                "- Common issues: corrupted ID3 tags, wrong encoding\n"
                "- After fixing tags, rescan your library in MA\n"
                "- For local files: verify file integrity\n"
                f"- See: {DOCS_BASE}/#tag-issues"
            )
        },

        # Player Sync Issues
        "sync_error": {
            "pattern": r"(player.*already.*sync|sync.*conflict|group.*error|player.*unavailable)",
            "severity": Severity.WARNING,
            "title": "Player Sync/Grouping Issues",
            "description": "Problems syncing or grouping players",
            "suggestion": (
                "Player synchronization issues:\n"
                "- Ungroup all players and try again\n"
                "- Restart affected player devices\n"
                "- Check all players are on the same network\n"
                "- Verify firmware is up to date on all devices\n"
                "- Some device combinations cannot be grouped (different protocols)"
            )
        },

        # SSL/Certificate Issues
        "ssl_error": {
            "pattern": r"(ssl.*error|certificate.*verif.*fail|certifi?cate.*invalid|https.*error)",
            "severity": Severity.ERROR,
            "title": "SSL/Certificate Error",
            "description": "SSL certificate validation failed",
            "suggestion": (
                "SSL certificate validation errors:\n"
                "- **Check system time:** Wrong date/time causes cert validation to fail\n"
                "- Update CA certificates on your system\n"
                "- If using local SSL without proper setup, disable it\n"
                "- For Docker: ensure container has updated certificates\n"
                "- Don't use self-signed certificates without proper configuration"
            )
        },

        # Installation/Dependency Issues
        "missing_module": {
            "pattern": r"(modulenotfounderror|importerror|no module named)",
            "severity": Severity.CRITICAL,
            "title": "Missing Python Dependencies",
            "description": "Required Python module is missing",
            "suggestion": (
                "Critical: Python dependencies are missing:\n"
                "- This indicates installation corruption\n"
                "- **For HA Addon:** Restart the addon or reinstall\n"
                "- **For Docker:** Rebuild the container\n"
                "- **For manual install:** Run pip install with requirements.txt\n"
                "- If issue persists, report as a bug with full logs"
            )
        },

        # Region/License Issues
        "region_restriction": {
            "pattern": r"(not available in.*region|geo.*block|region.*restrict|content.*unavailable)",
            "severity": Severity.INFO,
            "title": "Region Restriction",
            "description": "Content not available in your region",
            "suggestion": (
                "Content is restricted in your geographic region:\n"
                "- Verify your account region matches the provider region\n"
                "- Some content is only available in specific countries\n"
                "- Check provider account settings for region configuration\n"
                "- This is a provider limitation, not a Music Assistant issue"
            )
        }
    }

    def __init__(self, log_content: str):
        """Initialize with log file content."""
        self.log_content = log_content if log_content else ""
        self.detected_issues: List[DetectedIssue] = []
        self.providers_mentioned: Set[str] = set()

    def detect_providers(self) -> Set[str]:
        """Detect which providers are mentioned in the log."""
        # Map of provider identifiers to canonical names
        provider_aliases = {
            "spotify": ["spotify"],
            "tidal": ["tidal"],
            "qobuz": ["qobuz"],
            "apple_music": ["apple", "applemusic", "apple music"],
            "deezer": ["deezer"],
            "youtube_music": ["ytmusic", "youtubemusic", "youtube music", "youtube_music"],
            "soundcloud": ["soundcloud"],
            "tunein": ["tunein"],
            "plex": ["plex"],
            "jellyfin": ["jellyfin"],
            "subsonic": ["subsonic"],
            "sonos": ["sonos"],
            "airplay": ["airplay"],
            "cast": ["cast", "chromecast"],
            "dlna": ["dlna"],
            "snapcast": ["snapcast"],
            "slimproto": ["slimproto", "squeezebox"]
        }

        log_lower = self.log_content.lower()
        for provider, aliases in provider_aliases.items():
            for alias in aliases:
                if alias in log_lower:
                    self.providers_mentioned.add(provider)
                    break

        return self.providers_mentioned

    def analyze(self) -> List[DetectedIssue]:
        """
        Analyze log content for known issues using pattern matching.

        Returns:
            List of detected issues
        """
        if not self.log_content:
            return []

        # Detect providers first
        self.detect_providers()

        # Check all error patterns
        for issue_type, config in self.ERROR_PATTERNS.items():
            if re.search(config["pattern"], self.log_content, re.IGNORECASE | re.MULTILINE):
                # Skip provider-specific patterns if provider not mentioned
                if "provider" in config:
                    if config["provider"] not in self.providers_mentioned:
                        continue

                issue = DetectedIssue(
                    type=issue_type,
                    severity=config["severity"],
                    title=config["title"],
                    description=config["description"],
                    suggestion=config["suggestion"],
                    provider=config.get("provider"),
                    doc_link=config.get("doc_link")
                )
                self.detected_issues.append(issue)

        # Deduplicate by title
        seen_titles = set()
        unique_issues = []
        for issue in self.detected_issues:
            if issue.title not in seen_titles:
                seen_titles.add(issue.title)
                unique_issues.append(issue)

        self.detected_issues = unique_issues
        return self.detected_issues

    def generate_comment(self, max_issues: int = 5) -> Optional[str]:
        """
        Generate a helpful comment based on detected issues.

        Args:
            max_issues: Maximum number of issues to include in comment

        Returns:
            Markdown formatted comment or None if no issues detected
        """
        if not self.detected_issues:
            return None

        # Sort by severity (critical > error > warning > info)
        severity_order = {
            Severity.CRITICAL: 0,
            Severity.ERROR: 1,
            Severity.WARNING: 2,
            Severity.INFO: 3
        }
        sorted_issues = sorted(
            self.detected_issues,
            key=lambda x: severity_order.get(x.severity, 99)
        )

        # Limit to max_issues
        issues_to_show = sorted_issues[:max_issues]

        comment = "## 🔍 Automatic Log Analysis\n\n"
        comment += "I've analyzed the log file and detected the following potential issues:\n\n"

        for issue in issues_to_show:
            severity_emoji = {
                Severity.CRITICAL: "🚨",
                Severity.ERROR: "❌",
                Severity.WARNING: "⚠️",
                Severity.INFO: "ℹ️"
            }.get(issue.severity, "•")

            comment += f"### {severity_emoji} {issue.title}\n\n"

            if issue.provider:
                comment += f"**Provider:** {issue.provider.replace('_', ' ').title()}\n\n"

            comment += f"{issue.suggestion}\n\n"

        if len(self.detected_issues) > max_issues:
            comment += f"*... and {len(self.detected_issues) - max_issues} more issue(s) detected.*\n\n"

        comment += "---\n"
        comment += "*This is an automated pattern-based analysis. "
        comment += "Please review the suggestions and provide additional context if needed.*\n"

        return comment


async def analyze_with_ai(log_content: str, issue_title: str, issue_body: str) -> Optional[str]:
    """
    Use Claude AI to analyze logs intelligently (optional, requires API key).

    This provides more contextual analysis than pattern matching alone.

    Args:
        log_content: The log file content
        issue_title: The issue title for context
        issue_body: The issue body for context

    Returns:
        AI-generated analysis comment or None
    """
    api_key = os.environ.get('ANTHROPIC_API_KEY')
    if not api_key:
        return None

    try:
        # Only import if API key is available
        import anthropic

        client = anthropic.Anthropic(api_key=api_key)

        # Truncate log if too large (keep first and last portions)
        max_log_chars = 50000
        if len(log_content) > max_log_chars:
            log_content = (
                log_content[:max_log_chars//2] +
                "\n\n... [log truncated] ...\n\n" +
                log_content[-max_log_chars//2:]
            )

        prompt = f"""You are analyzing a Music Assistant log file for a bug report.

Issue Title: {issue_title}

Issue Description:
{issue_body[:2000]}

Log Content:
{log_content}

Please analyze this log and provide:
1. Root cause of the issue (if identifiable)
2. Specific error messages or patterns that are problematic
3. Step-by-step troubleshooting suggestions
4. Whether this appears to be a bug or user configuration issue

Focus on actionable insights. Be concise but specific. Use markdown formatting.
If you detect network issues, authentication problems, or provider-specific errors, explain them clearly.
"""

        message = client.messages.create(
            model="claude-3-5-sonnet-20241022",
            max_tokens=2000,
            messages=[{"role": "user", "content": prompt}]
        )

        ai_analysis = message.content[0].text

        comment = "## 🤖 AI-Powered Log Analysis\n\n"
        comment += ai_analysis + "\n\n"
        comment += "---\n"
        comment += "*This analysis was generated using AI and should be reviewed for accuracy.*\n"

        return comment

    except ImportError:
        print("anthropic package not installed, skipping AI analysis")
        return None
    except Exception as e:
        print(f"AI analysis failed: {e}")
        return None


def analyze_log_file(log_content: str) -> Optional[str]:
    """
    Convenience function to analyze a log file and return a comment.

    Args:
        log_content: The log file content as a string

    Returns:
        Markdown formatted comment or None
    """
    analyzer = LogAnalyzer(log_content)
    analyzer.analyze()
    return analyzer.generate_comment()
