---
name: scalene
description: Scalene AI coding scorecard
arguments:
  - name: action
    description: "setup = configure credentials, sync = import all history, sync session = current session only, status = show dashboard link"
    required: true
---

## Instructions

The sync script is at `${CLAUDE_PLUGIN_ROOT}/bin/scalene-sync.py`. Credentials are in `$SCALENE_API_URL` and `$SCALENE_TOKEN` environment variables.

### /scalene setup

CRITICAL: Do NOT ask the user to paste credentials. Do NOT show menus. Do NOT check env vars yourself. Just run this ONE command:

```bash
python3 ${CLAUDE_PLUGIN_ROOT}/bin/scalene-auth.py
```

This single script handles everything: checks credentials, authenticates if needed (opens browser), saves to ~/.zshrc, and runs the sync. No other commands needed.

### /scalene sync

Run: `python3 ${CLAUDE_PLUGIN_ROOT}/bin/scalene-sync.py --bulk --api-url "$SCALENE_API_URL" --token "$SCALENE_TOKEN"`

Collects all data locally, uploads in one request. Much faster than streaming.

### /scalene sync session

Run: `python3 ${CLAUDE_PLUGIN_ROOT}/bin/scalene-sync.py --api-url "$SCALENE_API_URL" --token "$SCALENE_TOKEN" --session-only $CLAUDE_SESSION_ID`

Syncs only the current session.

### /scalene status

Print the user's dashboard URL (the base domain from `$SCALENE_API_URL` + `/me`). No sync.

After any sync, tell the user their dashboard is updated.

## Privacy

Only metadata is exported — token counts, timestamps, model IDs, tool names. Never prompt text, file contents, or tool arguments.
