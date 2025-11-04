#!/usr/bin/env python3
"""
Batch process existing issues with the triage bot.

This script runs the triage bot logic on existing issues that haven't been processed yet.
It can be run manually to retroactively apply the bot to older issues.

Usage:
    python batch_process_issues.py --repo music-assistant/support --max 10

Environment variables required:
    GITHUB_TOKEN - GitHub personal access token with repo access
"""

import os
import sys
import argparse
import subprocess
import time
from github import Github

def has_bot_comment(issue):
    """Check if the bot has already commented on this issue."""
    for comment in issue.get_comments():
        if "automated issue triage" in comment.body.lower() or \
           "automatic log analysis" in comment.body.lower() or \
           "similar issues found" in comment.body.lower():
            return True
    return False

def trigger_bot_on_issue(issue_number, repo_name, dry_run=False):
    """
    Trigger the bot by simulating the GitHub Actions workflow locally.

    This sets up the same environment variables that the workflow would set,
    then calls the triage bot directly.
    """
    print(f"\n{'[DRY RUN] ' if dry_run else ''}Processing issue #{issue_number}...")

    if dry_run:
        print(f"  Would run triage bot on issue #{issue_number}")
        return True

    # Get issue details
    g = Github(os.environ['GITHUB_TOKEN'])
    repo = g.get_repo(repo_name)
    issue = repo.get_issue(issue_number)

    # Set environment variables as the workflow would
    env = os.environ.copy()
    env['ISSUE_NUMBER'] = str(issue_number)
    env['ISSUE_BODY'] = issue.body or ''
    env['ISSUE_TITLE'] = issue.title
    env['IS_PULL_REQUEST'] = 'false'
    env['REPOSITORY'] = repo_name
    env['GITHUB_TOKEN'] = os.environ['GITHUB_TOKEN']

    # Run the triage bot
    try:
        result = subprocess.run(
            ['python3', '.github/scripts/triage_bot.py'],
            env=env,
            capture_output=True,
            text=True,
            timeout=120
        )

        if result.returncode == 0:
            print(f"  ✓ Successfully processed issue #{issue_number}")
            print(f"    Output: {result.stdout[:200]}...")
            return True
        else:
            print(f"  ✗ Error processing issue #{issue_number}")
            print(f"    Error: {result.stderr[:200]}")
            return False

    except subprocess.TimeoutExpired:
        print(f"  ✗ Timeout processing issue #{issue_number}")
        return False
    except Exception as e:
        print(f"  ✗ Exception processing issue #{issue_number}: {e}")
        return False

def main():
    parser = argparse.ArgumentParser(description='Batch process existing issues with triage bot')
    parser.add_argument('--repo', default='music-assistant/support', help='Repository (owner/name)')
    parser.add_argument('--max', type=int, default=10, help='Maximum number of issues to process')
    parser.add_argument('--label', default='triage', help='Only process issues with this label')
    parser.add_argument('--skip-processed', action='store_true', help='Skip issues the bot already commented on')
    parser.add_argument('--dry-run', action='store_true', help='Show what would be done without doing it')
    parser.add_argument('--delay', type=int, default=5, help='Delay between issues (seconds)')
    parser.add_argument('--start-from', type=int, help='Start from this issue number')

    args = parser.parse_args()

    # Check for GitHub token
    if 'GITHUB_TOKEN' not in os.environ:
        print("Error: GITHUB_TOKEN environment variable not set")
        print("Please set it with: export GITHUB_TOKEN=your_token_here")
        sys.exit(1)

    # Connect to GitHub
    print(f"Connecting to GitHub repository: {args.repo}")
    g = Github(os.environ['GITHUB_TOKEN'])

    try:
        repo = g.get_repo(args.repo)
    except Exception as e:
        print(f"Error accessing repository: {e}")
        sys.exit(1)

    # Get issues to process
    print(f"\nFetching open issues with label '{args.label}'...")
    issues = repo.get_issues(state='open', labels=[args.label], sort='created', direction='desc')

    processed_count = 0
    skipped_count = 0
    error_count = 0

    print(f"\n{'='*80}")
    print(f"Starting batch processing (max {args.max} issues)")
    print(f"Dry run: {args.dry_run}")
    print(f"Skip already processed: {args.skip_processed}")
    print(f"{'='*80}")

    for issue in issues:
        # Stop if we've hit the max
        if processed_count >= args.max:
            print(f"\nReached maximum of {args.max} issues. Stopping.")
            break

        # Skip if before start point
        if args.start_from and issue.number < args.start_from:
            continue

        # Skip pull requests
        if issue.pull_request:
            continue

        # Skip if already processed
        if args.skip_processed and has_bot_comment(issue):
            print(f"  ⊘ Skipping #{issue.number} (already processed)")
            skipped_count += 1
            continue

        # Process the issue
        success = trigger_bot_on_issue(issue.number, args.repo, args.dry_run)

        if success:
            processed_count += 1
        else:
            error_count += 1

        # Delay to avoid rate limiting
        if not args.dry_run and processed_count < args.max:
            time.sleep(args.delay)

    # Summary
    print(f"\n{'='*80}")
    print(f"Batch processing complete!")
    print(f"  Processed: {processed_count}")
    print(f"  Skipped: {skipped_count}")
    print(f"  Errors: {error_count}")
    print(f"{'='*80}\n")

if __name__ == '__main__':
    main()
