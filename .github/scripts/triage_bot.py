#!/usr/bin/env python3
"""
Music Assistant Issue Triage Bot

This bot automatically:
1. Assigns provider labels based on issue content
2. Assigns maintainers from provider manifests
3. Validates issue template completion
4. Analyzes log files for common issues (Phase 2)
5. Posts helpful comments when validation fails or issues detected
"""

import os
import re
import json
import sys
import asyncio
from typing import List, Set, Dict, Optional
from github import Github, GithubException
import requests

# Import log analyzer
from log_analyzer import LogAnalyzer, analyze_with_ai

# Server repository containing provider manifests
SERVER_REPO = "music-assistant/server"
MANIFEST_PATH = "music_assistant/providers/{provider}/manifest.json"

# Load provider mappings from configuration file
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
MAPPINGS_FILE = os.path.join(SCRIPT_DIR, "provider_mappings.json")

def load_provider_mappings() -> Dict[str, str]:
    """Load provider mappings from JSON configuration file."""
    try:
        with open(MAPPINGS_FILE, 'r') as f:
            config = json.load(f)

        # Flatten the mappings into a single dict (display_name -> provider_dir)
        mappings = {}
        for provider_dir, aliases in config.get("music_providers", {}).items():
            for alias in aliases:
                mappings[alias.lower()] = provider_dir

        for provider_dir, aliases in config.get("player_providers", {}).items():
            for alias in aliases:
                mappings[alias.lower()] = provider_dir

        return mappings
    except (FileNotFoundError, json.JSONDecodeError) as e:
        print(f"Warning: Could not load provider mappings: {e}")
        return {}

PROVIDER_MAPPINGS = load_provider_mappings()


def normalize_provider_name(name: str) -> str:
    """Normalize provider name for comparison."""
    return name.lower().strip()


def extract_providers_from_text(text: str) -> Set[str]:
    """Extract provider names from issue text."""
    if not text:
        return set()

    text_lower = text.lower()
    detected = set()

    # Look for provider names in the text
    for display_name, dir_name in PROVIDER_MAPPINGS.items():
        if display_name in text_lower:
            detected.add(dir_name)

    return detected


def parse_issue_sections(issue_body: str) -> Dict[str, str]:
    """Parse issue body into sections based on headers."""
    if not issue_body:
        return {}

    sections = {}
    current_section = None
    current_content = []

    for line in issue_body.split('\n'):
        # Check for section headers (### Header)
        if line.startswith('###'):
            if current_section:
                sections[current_section] = '\n'.join(current_content).strip()
            current_section = line.replace('#', '').strip()
            current_content = []
        elif current_section:
            current_content.append(line)

    # Add last section
    if current_section:
        sections[current_section] = '\n'.join(current_content).strip()

    return sections


def get_providers_from_issue(issue_body: str) -> Set[str]:
    """Extract provider names from issue body."""
    providers = set()

    # Parse issue into sections
    sections = parse_issue_sections(issue_body)

    # Look in Music Providers section
    if "Music Providers" in sections:
        providers.update(extract_providers_from_text(sections["Music Providers"]))

    # Look in Player Providers section
    if "Player Providers" in sections:
        providers.update(extract_providers_from_text(sections["Player Providers"]))

    # Also check the problem description and title
    if "The problem" in sections:
        providers.update(extract_providers_from_text(sections["The problem"]))

    return providers


def fetch_provider_manifest(provider: str) -> Optional[Dict]:
    """Fetch manifest.json for a provider from the server repo."""
    manifest_url = f"https://raw.githubusercontent.com/{SERVER_REPO}/main/{MANIFEST_PATH.format(provider=provider)}"

    try:
        response = requests.get(manifest_url, timeout=10)
        response.raise_for_status()
        return response.json()
    except (requests.RequestException, json.JSONDecodeError) as e:
        print(f"Could not fetch manifest for {provider}: {e}")
        return None


def get_maintainers_from_manifest(manifest: Dict) -> List[str]:
    """Extract maintainer usernames from manifest."""
    maintainers = manifest.get("maintainers", [])

    # Filter out generic "music_assistant" maintainer
    return [m for m in maintainers if m.lower() != "music_assistant"]


def validate_issue_template(issue_body: str, has_attachments: bool) -> List[str]:
    """Validate that issue template is filled out correctly."""
    issues = []

    if not issue_body:
        issues.append("Issue body is empty")
        return issues

    sections = parse_issue_sections(issue_body)

    # Check for required sections
    required_sections = [
        "The problem",
        "How to reproduce",
        "Music Providers",
        "Player Providers",
        "Full log output",
        "Additional information"
    ]

    for section in required_sections:
        if section not in sections or not sections[section].strip():
            issues.append(f"Section '{section}' is missing or empty")

    # Check if log output section contains actual log paste (which is wrong)
    if "Full log output" in sections:
        log_section = sections["Full log output"]
        # Check if they pasted logs instead of attaching
        if len(log_section) > 200 or "DO NOT PASTE" in log_section:
            if not has_attachments:
                issues.append("Please ATTACH the log file instead of pasting it. See instructions in the template.")

    # Check for log attachment
    if not has_attachments and "Full log output" in sections:
        log_section = sections["Full log output"]
        if len(log_section) < 50:  # Probably didn't attach anything
            issues.append("No log file appears to be attached. Please attach the full log file.")

    # Check for generic/placeholder text
    placeholder_texts = [
        "DO NOT PASTE the log here",
        "For Audiobookshelf include broken book ASINs here"
    ]

    for section_name, content in sections.items():
        for placeholder in placeholder_texts:
            if placeholder in content and len(content) < 100:
                issues.append(f"Section '{section_name}' appears to contain placeholder text")

    return issues


def extract_log_file_urls(issue_body: str) -> List[str]:
    """Extract GitHub file attachment URLs from issue body."""
    # Pattern for GitHub file uploads
    pattern = r'https://github\.com/[^/]+/[^/]+/files/\d+/[\w\.-]+'
    urls = re.findall(pattern, issue_body)
    return urls


def download_log_content(url: str) -> Optional[str]:
    """Download log file content from GitHub attachment URL."""
    try:
        response = requests.get(url, timeout=30)
        response.raise_for_status()

        # Try to decode as text
        try:
            content = response.content.decode('utf-8')
        except UnicodeDecodeError:
            # Try with different encoding
            try:
                content = response.content.decode('latin-1')
            except UnicodeDecodeError:
                print(f"Could not decode log file from {url}")
                return None

        return content
    except requests.RequestException as e:
        print(f"Failed to download log from {url}: {e}")
        return None


async def analyze_issue_logs(item, issue_title: str, issue_body: str) -> Optional[str]:
    """
    Analyze log files attached to an issue.

    Args:
        item: GitHub issue object
        issue_title: Issue title
        issue_body: Issue body

    Returns:
        Analysis comment or None
    """
    # Extract log file URLs from issue body
    log_urls = extract_log_file_urls(issue_body)

    if not log_urls:
        print("No log file attachments found")
        return None

    print(f"Found {len(log_urls)} log file(s)")

    # Download and combine all log files
    all_logs = []
    for url in log_urls:
        log_content = download_log_content(url)
        if log_content:
            all_logs.append(log_content)
            print(f"Downloaded log file: {url}")

    if not all_logs:
        print("Could not download any log files")
        return None

    combined_logs = "\n\n=== LOG FILE BOUNDARY ===\n\n".join(all_logs)

    # Run pattern-based analysis
    analyzer = LogAnalyzer(combined_logs)
    analyzer.analyze()
    pattern_comment = analyzer.generate_comment(max_issues=5)

    # Try AI analysis if API key is available
    ai_comment = None
    if os.environ.get('ANTHROPIC_API_KEY'):
        print("Running AI-powered log analysis...")
        try:
            ai_comment = await analyze_with_ai(combined_logs, issue_title, issue_body)
        except Exception as e:
            print(f"AI analysis failed: {e}")

    # Combine analyses
    final_comment = ""

    if pattern_comment:
        final_comment += pattern_comment

    if ai_comment:
        if final_comment:
            final_comment += "\n\n---\n\n"
        final_comment += ai_comment

    return final_comment if final_comment else None


def main():
    """Main bot logic."""
    # Get environment variables
    github_token = os.environ.get('GITHUB_TOKEN')
    issue_number = os.environ.get('ISSUE_NUMBER')
    issue_body = os.environ.get('ISSUE_BODY', '')
    issue_title = os.environ.get('ISSUE_TITLE', '')
    is_pr = os.environ.get('IS_PULL_REQUEST', 'false').lower() == 'true'
    repository = os.environ.get('REPOSITORY')
    pr_user = os.environ.get('PR_USER', '')

    if not all([github_token, issue_number, repository]):
        print("Missing required environment variables")
        sys.exit(1)

    # Initialize GitHub client
    g = Github(github_token)
    repo = g.get_repo(repository)

    # Get the issue or PR
    if is_pr:
        item = repo.get_pull(int(issue_number))
        print(f"Processing PR #{issue_number}")
    else:
        item = repo.get_issue(int(issue_number))
        print(f"Processing issue #{issue_number}")

    # Extract providers from issue/PR
    all_text = f"{issue_title}\n{issue_body}"
    detected_providers = get_providers_from_issue(all_text)

    print(f"Detected providers: {detected_providers}")

    # Process each detected provider
    labels_to_add = set()
    maintainers_to_assign = set()

    for provider in detected_providers:
        print(f"Processing provider: {provider}")

        # Add provider label
        labels_to_add.add(provider)

        # Fetch manifest and get maintainers
        manifest = fetch_provider_manifest(provider)
        if manifest:
            maintainers = get_maintainers_from_manifest(manifest)
            maintainers_to_assign.update(maintainers)
            print(f"  Maintainers: {maintainers}")

    # Get existing labels
    existing_labels = {label.name for label in item.labels}
    print(f"Existing labels: {existing_labels}")

    # Add new labels
    new_labels = labels_to_add - existing_labels
    if new_labels:
        print(f"Adding labels: {new_labels}")
        try:
            # Try to add labels (will create if they don't exist)
            for label in new_labels:
                try:
                    item.add_to_labels(label)
                    print(f"  Added label: {label}")
                except GithubException as e:
                    print(f"  Could not add label '{label}': {e}")
        except GithubException as e:
            print(f"Error adding labels: {e}")

    # Assign maintainers
    if maintainers_to_assign:
        current_assignees = {assignee.login for assignee in item.assignees}
        new_assignees = maintainers_to_assign - current_assignees

        if new_assignees:
            print(f"Assigning maintainers: {new_assignees}")
            try:
                item.add_to_assignees(*list(new_assignees))
            except GithubException as e:
                print(f"Error assigning maintainers: {e}")
                # Try to mention them in a comment instead
                if not is_pr:
                    mentions = ' '.join(f"@{m}" for m in new_assignees)
                    try:
                        item.create_comment(
                            f"👋 {mentions} - This issue appears to be related to a provider you maintain."
                        )
                    except GithubException:
                        pass

    # Validate template (only for issues, not PRs)
    if not is_pr:
        # Check for attachments
        has_attachments = len(list(item.get_comments())) > 0  # Simplified check
        # Better attachment check: look for URLs in the body
        has_attachments = has_attachments or bool(re.search(r'https://github\.com/.*/files/', issue_body))

        validation_issues = validate_issue_template(issue_body, has_attachments)

        if validation_issues:
            print(f"Template validation issues: {validation_issues}")

            # Check if we already posted a validation comment
            existing_comments = list(item.get_comments())
            bot_already_commented = any(
                "template validation" in comment.body.lower()
                for comment in existing_comments
            )

            if not bot_already_commented:
                comment_body = "## ⚠️ Issue Template Validation\n\n"
                comment_body += "Thank you for reporting this issue! However, there are some problems with the issue template:\n\n"

                for issue_text in validation_issues:
                    comment_body += f"- {issue_text}\n"

                comment_body += "\n"
                comment_body += "Please update your issue with the missing information. "
                comment_body += "Providing complete information helps us resolve issues faster. "
                comment_body += "See the [Troubleshooting Guide](https://music-assistant.io/faq/troubleshooting/) for more details.\n"

                try:
                    item.create_comment(comment_body)
                    print("Posted validation comment")
                except GithubException as e:
                    print(f"Error posting comment: {e}")

        # Phase 2: Analyze log files (only for issues, not PRs)
        print("Checking for log files to analyze...")

        # Check if we already posted a log analysis comment
        existing_comments = list(item.get_comments())
        log_analysis_already_posted = any(
            "automatic log analysis" in comment.body.lower() or
            "ai-powered log analysis" in comment.body.lower()
            for comment in existing_comments
        )

        if not log_analysis_already_posted:
            # Run log analysis (async)
            try:
                log_analysis_comment = asyncio.run(
                    analyze_issue_logs(item, issue_title, issue_body)
                )

                if log_analysis_comment:
                    print("Posting log analysis comment...")
                    try:
                        item.create_comment(log_analysis_comment)
                        print("Successfully posted log analysis")
                    except GithubException as e:
                        print(f"Error posting log analysis comment: {e}")
                else:
                    print("No issues detected in logs or no logs found")
            except Exception as e:
                print(f"Log analysis failed: {e}")
        else:
            print("Log analysis comment already exists, skipping")

    print("Triage bot completed successfully")


if __name__ == "__main__":
    main()
