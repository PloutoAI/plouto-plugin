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

CRITICAL: You MUST follow these exact steps. Do NOT ask the user to paste credentials. Do NOT show menus. Do NOT improvise. Execute these bash commands in order:

Step 1 — check if already configured:
```bash
echo "URL=${SCALENE_API_URL:-}" && echo "TOKEN=${SCALENE_TOKEN:-}"
```
If both are set (not empty), say "Already configured." and stop.

Step 2 — start device auth. Run this EXACT command:
```bash
curl -s -X POST https://getscalene.com/api/cli/auth
```
Parse the JSON response to get `code` and `url`.

Step 3 — open browser. Run:
```bash
open "<the url from step 2>"
```
Tell the user: "Confirm in your browser..."

Step 4 — poll for confirmation. Run this in a loop (sleep 2 between, max 30 tries):
```bash
curl -s "https://getscalene.com/api/cli/poll?code=<the code from step 2>"
```
Keep polling until response contains `"status":"confirmed"`. Extract `api_url` and `token` from the confirmed response.

Step 5 — save credentials:
```bash
echo 'export SCALENE_API_URL=<api_url>' >> ~/.zshrc && echo 'export SCALENE_TOKEN=<token>' >> ~/.zshrc && export SCALENE_API_URL=<api_url> && export SCALENE_TOKEN=<token>
```

Step 6 — say "Connected!" then run the sync immediately:
```bash
python3 ${CLAUDE_PLUGIN_ROOT}/bin/scalene-sync.py --api-url "$SCALENE_API_URL" --token "$SCALENE_TOKEN"
```

### /scalene sync

Run: `python3 ${CLAUDE_PLUGIN_ROOT}/bin/scalene-sync.py --api-url "$SCALENE_API_URL" --token "$SCALENE_TOKEN"`

Imports all historical sessions from `~/.claude/projects/`. May take a few minutes for large histories.

### /scalene sync session

Run: `python3 ${CLAUDE_PLUGIN_ROOT}/bin/scalene-sync.py --api-url "$SCALENE_API_URL" --token "$SCALENE_TOKEN" --session-only $CLAUDE_SESSION_ID`

Syncs only the current session.

### /scalene status

Print the user's dashboard URL (the base domain from `$SCALENE_API_URL` + `/me`). No sync.

After any sync, tell the user their dashboard is updated.

## Privacy

Only metadata is exported — token counts, timestamps, model IDs, tool names. Never prompt text, file contents, or tool arguments.
