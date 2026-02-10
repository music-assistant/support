# Music Assistant

Turn your Home Assistant instance into a jukebox, hassle free streaming of your favourite media to Home Assistant media players.

[![latest version](https://img.shields.io/github/release/music-assistant/server?display_name=tag&include_prereleases&label=latest%20version)](https://github.com/music-assistant/server/releases)
[![discord](https://img.shields.io/discord/753947050995089438?label=Chat&logo=discord)](https://discord.gg/kaVm8hGpne)

https://music-assistant.io

## I need help, I have feedback

- [Documentation](https://music-assistant.io)
- [Issue tracker](https://github.com/music-assistant/support/issues) to create bug reports, please include detailed info and logfiles. Please check if your issue has already been reported.
- [Feature requests](https://github.com/music-assistant/support/discussions/categories/feature-requests-and-ideas): Give your vote to an existing request, join the discussion or add a new request.
- [Q&A section](https://github.com/music-assistant/support/discussions/categories/q-a) Frequently asked questions and tutorials
- [Discord community](https://discord.gg/kaVm8hGpne) Join the community and get support!

## Issue Automation

This repository uses automated workflows to manage issues efficiently.

### Issue Lifecycle

```
┌─────────────────────────────────────────────────────────────────────────┐
│                        ISSUE OPENED / REOPENED                          │
└────────────────────────────────┬────────────────────────────────────────┘
                                 │
                    ┌────────────▼────────────┐
                    │   Triage Bot runs:      │
                    │   - Provider labels     │
                    │   - Maintainer assigned  │
                    │   - Template validation  │
                    │   - Log analysis        │
                    └────────────┬────────────┘
                                 │
              ┌──────────────────┴──────────────────┐
              │                                     │
     Template valid                        Template invalid
              │                                     │
              ▼                                     ▼
   ┌──────────────────┐                  ┌──────────────────┐
   │ + needs-attention │                  │ + waiting-for-user│
   └────────┬─────────┘                  │ (bot asks user to │
            │                            │  fix their issue)  │
            │                            └────────┬──────────┘
            │                                     │
            └──────────────┬──────────────────────┘
                           │
                           ▼
         ┌─────────────────────────────────┐
         │     RESPONSE TRACKING LOOP      │
         │                                 │
         │  Maintainer and issue author    │
         │  go back and forth until the    │
         │  issue is confirmed as a bug    │
         │  or resolved.                   │
         └─────────────────┬───────────────┘
                           │
            ┌──────────────┴──────────────┐
            │                             │
   Maintainer comments              Issue author comments
   (not issue author)
            │                             │
            ▼                             ▼
 ┌────────────────────┐        ┌────────────────────┐
 │ - needs-attention   │        │ - waiting-for-user  │
 │ + waiting-for-user  │        │ + needs-attention   │
 └─────────┬──────────┘        └─────────┬──────────┘
           │                             │
           └─────────────┬───────────────┘
                         │
            ┌────────────▼────────────┐
            │  Bug confirmed?         │
            │  (+ 'bug' or            │
            │  'Fix to be Confirmed') │
            └────────────┬────────────┘
                         │
              YES ───────┴─────── NO
              │                   │
              ▼                   ▼
   ┌──────────────────┐  Response tracking
   │  TRACKING STOPS  │  loop continues
   │  Labels frozen — │       │
   │  issue is now in │       │
   │  dev pipeline    │       │
   └──────────────────┘       │
                              │
          ┌───────────────────┴───────────────────┐
          │                                       │
          ▼                                       ▼
   Has 'waiting-for-user'                No response-state labels
   (user not responding)                 (fell through the cracks)
          │                                       │
          ▼                                       ▼
   14 days ──► 'stale' warning             60 days ──► 'stale' warning
          │                                       │
          ▼                                       ▼
   3 more days ──► AUTO-CLOSED             14 more days ──► AUTO-CLOSED
   + 'auto-closed' label                  + 'auto-closed' label
          │                                       │
          └───────────────────┬───────────────────┘
                              │
                              ▼
                   ┌──────────────────┐
                   │   ISSUE CLOSED   │
                   └────────┬─────────┘
                            │
                         30 days
                            │
                            ▼
                   ┌──────────────────┐
                   │  THREAD LOCKED   │
                   │  (no more        │
                   │   comments)      │
                   └──────────────────┘
```

**Notes:**
- Bot and community comments do **not** trigger label changes
- Issues with `bug`, `Fix to be Confirmed`, `enhancement`, or `pinned` are **exempt** from auto-close
- Any new activity removes the `stale` label automatically
- See [.github/scripts/README.md](.github/scripts/README.md) for detailed automation docs

## I want to help

See here https://music-assistant.io/help/

---

[![A project from the Open Home Foundation](https://www.openhomefoundation.org/badges/ohf-project.png)](https://www.openhomefoundation.org/)
