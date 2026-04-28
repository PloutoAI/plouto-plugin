---
name: plouto
description: AI Engineering Intelligence
arguments:
  - name: action
    description: "setup = authenticate and sync, sync = import all history, sync session = current session only, audit = run audit on current session, comply = clear policy gate after running /model, status = show dashboard link"
    required: true
---

## Instructions

The sync script is at `${CLAUDE_PLUGIN_ROOT}/bin/plouto-sync.py`. Credentials are in `$PLOUTO_API_URL` / `$PLOUTO_TOKEN` (legacy `$SCALENE_API_URL` / `$SCALENE_TOKEN` are honored as fallbacks).

When running any sync/audit command, resolve the credentials first with this prelude:

```bash
API_URL="${PLOUTO_API_URL:-$SCALENE_API_URL}"
TOKEN="${PLOUTO_TOKEN:-$SCALENE_TOKEN}"
```

### /plouto setup

Run this ONE command. It opens the browser for OAuth login, saves the token, and syncs history:

```bash
python3 ${CLAUDE_PLUGIN_ROOT}/bin/plouto-auth.py
```

### /plouto setup auth

Force re-authentication (clears existing credentials first):

```bash
python3 ${CLAUDE_PLUGIN_ROOT}/bin/plouto-auth.py --force
```

### /plouto sync

```bash
API_URL="${PLOUTO_API_URL:-$SCALENE_API_URL}"
TOKEN="${PLOUTO_TOKEN:-$SCALENE_TOKEN}"
python3 ${CLAUDE_PLUGIN_ROOT}/bin/plouto-sync.py --bulk --api-url "$API_URL" --token "$TOKEN"
```

Collects all data locally, uploads in one request.

### /plouto sync session

```bash
API_URL="${PLOUTO_API_URL:-$SCALENE_API_URL}"
TOKEN="${PLOUTO_TOKEN:-$SCALENE_TOKEN}"
python3 ${CLAUDE_PLUGIN_ROOT}/bin/plouto-sync.py --api-url "$API_URL" --token "$TOKEN" --session-only $CLAUDE_SESSION_ID
```

Syncs only the current session.

### /plouto audit

Sync the current session, then print the audit URL.

```bash
API_URL="${PLOUTO_API_URL:-$SCALENE_API_URL}"
TOKEN="${PLOUTO_TOKEN:-$SCALENE_TOKEN}"
python3 ${CLAUDE_PLUGIN_ROOT}/bin/plouto-sync.py --api-url "$API_URL" --token "$TOKEN" --session-only $CLAUDE_SESSION_ID
DASHBOARD="${API_URL/api./}"
echo "Plouto Audit: $DASHBOARD/audit"
```

Then tell the user "Your audit is ready: <DASHBOARD>/audit". If `${API_URL/api./}` produced no change (e.g. running against localhost or a dev API that doesn't sit behind `api.`), fall back to `$API_URL/audit`.

### /plouto comply

Clear the workspace-policy gate flag for the current session. Run this after `/model <required-model>` so the user's tool calls (Edit, Write, Bash, etc.) are no longer blocked by the policy enforcer.

```bash
rm -f $HOME/.claude/plouto/policy-violation
echo "Plouto policy gate cleared."
echo "[$(date -u +%Y-%m-%dT%H:%M:%SZ)] /plouto comply: gate cleared by user $CLAUDE_SESSION_ID" >> $HOME/.claude/plouto.log
```

After running this, tell the user the gate is cleared and tool calls will proceed on the model they just selected with `/model`.

### /plouto status

Print the user's dashboard URL: take the base domain from `$PLOUTO_API_URL` (stripping `api.` if present) and append `/me`. No sync.

After any sync, tell the user their dashboard is updated.

## Privacy

Only metadata is exported: token counts, timestamps, model IDs, tool names. Never prompt text, file contents, or tool arguments.
