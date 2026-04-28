#!/usr/bin/env python3
"""PreToolUse hook step: deny code-touching tool calls when policy
is violated.

A flag file at ``~/.claude/plouto/policy-violation`` (set by
plouto-policy.py at SessionStart when the active model doesn't match
the workspace's required model) means we should refuse Edit / Write /
Bash / Task / Read-side-effect tool calls until the user complies.

Output schema follows the documented PreToolUse hook contract:

```json
{
  "hookSpecificOutput": {
    "hookEventName": "PreToolUse",
    "permissionDecision": "deny",
    "permissionDecisionReason": "..."
  }
}
```

When the flag is absent, this script exits silently and Claude Code
proceeds with the tool call. Failures here MUST not block the user
(no flag → no block); a network or filesystem error never converts
into a tool denial.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path


_FLAG = Path.home() / ".claude" / "plouto" / "policy-violation"
_GATED_TOOLS = {
    "Edit",
    "Write",
    "MultiEdit",
    "NotebookEdit",
    "Bash",
    "BashOutput",
    "Task",
}


def main() -> None:
    if not _FLAG.exists():
        return  # no violation, allow

    try:
        raw = sys.stdin.read() or "{}"
        hook_input = json.loads(raw)
    except json.JSONDecodeError:
        return

    tool_name = hook_input.get("tool_name") or ""
    if tool_name not in _GATED_TOOLS:
        return  # only gate tools that touch code or shell

    try:
        reason_detail = _FLAG.read_text().strip()
    except OSError:
        reason_detail = "policy mismatch"

    reason = (
        f"Plouto policy: {reason_detail}. "
        f"Run `/model <required-model>` then `/plouto comply` to clear "
        f"this for the current session, or `/exit` and `claude --resume` "
        f"to restart on the policy model."
    )

    payload = {
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": "deny",
            "permissionDecisionReason": reason,
        }
    }
    sys.stdout.write(json.dumps(payload))


if __name__ == "__main__":
    main()
