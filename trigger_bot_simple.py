#!/usr/bin/env python3
"""
Simple script to trigger the triage bot on existing issues.

This works by making a tiny edit to the issue (adds/removes a trailing space)
which triggers the 'issues.edited' event and runs the workflow automatically.

Usage:
    export GITHUB_TOKEN=your_token_here
    python trigger_bot_simple.py --issues 4380 4355 4298

Or process multiple by label:
    python trigger_bot_simple.py --label triage --max 5
"""

import os
import sys
import argparse
import time
from github import Github

def has_bot_comment(issue):
    """Check if the bot has already commented on this issue."""
    for comment in issue.get_comments():
        body_lower = comment.body.lower()
        if "automated issue triage" in body_lower or \
           "automatic log analysis" in body_lower or \
           "similar issues found" in body_lower:
            return True
    return False

def trigger_workflow(issue, dry_run=False):
    """
    Trigger the workflow by making a tiny edit to the issue.

    This adds a space to the end of the issue body, which triggers
    the 'issues.edited' event without changing the visible content.
    """
    print(f"\nIssue #{issue.number}: {issue.title}")

    if dry_run:
        print(f"  [DRY RUN] Would trigger workflow")
        return True

    try:
        # Add a space at the end of the body to trigger the edit event
        # This is invisible to users but triggers the workflow
        current_body = issue.body or ''

        # Toggle between adding/removing space to allow re-triggering
        if current_body.endswith(' '):
            new_body = current_body.rstrip()
        else:
            new_body = current_body + ' '

        issue.edit(body=new_body)
        print(f"  ✓ Triggered workflow (edited issue body)")
        return True

    except Exception as e:
        print(f"  ✗ Error: {e}")
        return False

def main():
    parser = argparse.ArgumentParser(
        description='Trigger triage bot on existing issues',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Process specific issues
  python trigger_bot_simple.py --issues 4380 4355 4298

  # Process all open issues with 'triage' label
  python trigger_bot_simple.py --label triage --max 10

  # Dry run to see what would happen
  python trigger_bot_simple.py --label triage --max 5 --dry-run

  # Skip issues the bot already processed
  python trigger_bot_simple.py --label triage --skip-processed --max 20
        """
    )
    parser.add_argument('--repo', default='music-assistant/support',
                       help='Repository (default: music-assistant/support)')
    parser.add_argument('--issues', type=int, nargs='+',
                       help='Specific issue numbers to process')
    parser.add_argument('--label',
                       help='Process all open issues with this label')
    parser.add_argument('--max', type=int, default=10,
                       help='Maximum number of issues to process (default: 10)')
    parser.add_argument('--skip-processed', action='store_true',
                       help='Skip issues the bot already commented on')
    parser.add_argument('--dry-run', action='store_true',
                       help='Show what would be done without doing it')
    parser.add_argument('--delay', type=int, default=3,
                       help='Delay between issues in seconds (default: 3)')

    args = parser.parse_args()

    # Validate arguments
    if not args.issues and not args.label:
        parser.error("Must specify either --issues or --label")

    # Check for GitHub token
    if 'GITHUB_TOKEN' not in os.environ:
        print("❌ Error: GITHUB_TOKEN environment variable not set")
        print("\nPlease set it with:")
        print("  export GITHUB_TOKEN=your_token_here")
        print("\nYou can create a token at: https://github.com/settings/tokens")
        print("Required scopes: repo")
        sys.exit(1)

    # Connect to GitHub
    print(f"🔗 Connecting to GitHub repository: {args.repo}")
    g = Github(os.environ['GITHUB_TOKEN'])

    try:
        repo = g.get_repo(args.repo)
        print(f"✓ Connected successfully\n")
    except Exception as e:
        print(f"❌ Error accessing repository: {e}")
        sys.exit(1)

    # Get issues to process
    issues_to_process = []

    if args.issues:
        # Specific issues
        print(f"📋 Fetching {len(args.issues)} specific issue(s)...")
        for issue_num in args.issues:
            try:
                issue = repo.get_issue(issue_num)
                if not issue.pull_request:
                    issues_to_process.append(issue)
                else:
                    print(f"  ⊘ Skipping #{issue_num} (is a pull request)")
            except Exception as e:
                print(f"  ✗ Error fetching #{issue_num}: {e}")

    elif args.label:
        # Issues by label
        print(f"📋 Fetching open issues with label '{args.label}'...")
        issues = repo.get_issues(state='open', labels=[args.label], sort='created', direction='desc')

        for issue in issues:
            if len(issues_to_process) >= args.max:
                break
            if not issue.pull_request:
                issues_to_process.append(issue)

    if not issues_to_process:
        print("❌ No issues to process!")
        sys.exit(0)

    print(f"✓ Found {len(issues_to_process)} issue(s) to process\n")

    # Process issues
    print("=" * 80)
    print(f"🤖 {'[DRY RUN] ' if args.dry_run else ''}Starting batch processing")
    print("=" * 80)

    processed = 0
    skipped = 0
    errors = 0

    for issue in issues_to_process:
        # Check if already processed
        if args.skip_processed and has_bot_comment(issue):
            print(f"\nIssue #{issue.number}: {issue.title}")
            print(f"  ⊘ Skipping (bot already commented)")
            skipped += 1
            continue

        # Trigger workflow
        success = trigger_workflow(issue, args.dry_run)

        if success:
            processed += 1
            if not args.dry_run:
                print(f"  ⏳ Workflow will run in ~10-30 seconds")
                print(f"  📊 Check: https://github.com/{args.repo}/actions")
        else:
            errors += 1

        # Delay between issues to avoid overwhelming the system
        if not args.dry_run and processed < len(issues_to_process):
            time.sleep(args.delay)

    # Summary
    print("\n" + "=" * 80)
    print("✅ Batch processing complete!")
    print("=" * 80)
    print(f"  Triggered: {processed}")
    print(f"  Skipped:   {skipped}")
    print(f"  Errors:    {errors}")

    if processed > 0 and not args.dry_run:
        print(f"\n💡 The bot will process these issues automatically.")
        print(f"   Check progress at: https://github.com/{args.repo}/actions")
        print(f"   Each workflow run takes ~10-30 seconds")

    print()

if __name__ == '__main__':
    main()
