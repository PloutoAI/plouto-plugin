# scalene-mcp

Client-side MCP tool for [Scalene](https://github.com/mtrbls/scalene). Syncs Claude Code session metadata to your Scalene dashboard.

## Install

```bash
claude mcp add --transport http scalene https://app.scalene.dev/u/<your-token>/mcp
```

Then in Claude Code:

```
"sync my Claude Code history to Scalene"
```

## What it does

The sync script runs **entirely on your machine**. It reads `~/.claude/projects/` and exports only metadata: session timestamps, token counts, model IDs, tool names. Never prompt text, file contents, or tool arguments.

## Privacy

Audit the source: [sync_script.py](./sync_script.py)
