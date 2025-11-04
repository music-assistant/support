#!/usr/bin/env python3
"""
Music Assistant Issue Triage Bot

This bot automatically:
1. Assigns provider labels based on issue content
2. Assigns maintainers from provider manifests
3. Validates issue template completion
4. Posts helpful comments when validation fails
"""

import os
import re
import json
import sys
from typing import List, Set, Dict, Optional
from github import Github, GithubException
import requests

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

    print("Triage bot completed successfully")


if __name__ == "__main__":
    main()
