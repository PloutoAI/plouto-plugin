#!/usr/bin/env python3
"""Scalene sync — self-contained, zero-dependency privacy-first exporter.

This script is delivered by the Scalene MCP tool and executed locally by
the Claude Code agent. It walks ~/.claude/projects/, extracts ONLY
metadata from each JSONL session file, and POSTs the result to the
Scalene API. No prompt text, response text, tool inputs, or thinking
blocks ever leave the machine.

The privacy whitelist is enforced HERE, on the developer's machine,
not on the server. Read this file to verify — it's ~120 lines.

Usage (the agent runs this automatically):
    python3 sync_script.py --api-url https://app.scalene.dev --token <bearer>

Or for the current session only (used by the Stop hook):
    python3 sync_script.py --api-url ... --token ... --session-only <session-id>
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import urllib.request
import urllib.error
from pathlib import Path


# ── Privacy whitelist ─────────────────────────────────────────────────
# ONLY these fields are extracted. Everything else is dropped.

def extract_session(line: dict) -> dict | None:
    """Extract session-level metadata from a JSONL line, or None."""
    if line.get("type") not in ("user", "assistant"):
        return None
    sid = line.get("sessionId")
    if not sid:
        return None
    return {
        "id": sid,
        "workspace_id": "default",
        "cwd": line.get("cwd", ""),
        "git_branch": line.get("gitBranch"),
        "cli_version": line.get("version"),
        "user_type": line.get("userType"),
        "entrypoint": line.get("entrypoint"),
        "started_at": line.get("timestamp"),
    }


def extract_turn(line: dict) -> dict | None:
    """Extract per-turn metadata. NEVER extracts text content."""
    uuid = line.get("uuid")
    if not uuid:
        return None
    turn_type = line.get("type")
    if turn_type not in ("user", "assistant", "tool_result"):
        return None

    msg = line.get("message", {})
    usage = msg.get("usage", {})
    cache = usage.get("cache_creation", {})
    tools = msg.get("server_tool_use", {})

    # Tool name only — NEVER tool_input or content.
    tool_name = None
    for block in msg.get("content", []):
        if isinstance(block, dict) and block.get("type") == "tool_use":
            tool_name = block.get("name")
            break

    return {
        "uuid": uuid,
        "session_id": line.get("sessionId"),
        "workspace_id": "default",
        "parent_uuid": line.get("parentUuid"),
        "turn_type": turn_type,
        "timestamp": line.get("timestamp"),
        "model_id": msg.get("model"),
        "input_tokens": usage.get("input_tokens", 0),
        "output_tokens": usage.get("output_tokens", 0),
        "cache_read_tokens": usage.get("cache_read_input_tokens", 0),
        "cache_creation_5m_tokens": cache.get("five_minute_tokens", 0),
        "cache_creation_1h_tokens": cache.get("one_hour_tokens", 0),
        "web_search_count": tools.get("web_search", 0),
        "web_fetch_count": tools.get("web_fetch", 0),
        "tool_name": tool_name,
    }


# ── File walking ──────────────────────────────────────────────────────

def iter_jsonl(path: Path):
    with path.open("r", encoding="utf-8") as f:
        for raw in f:
            raw = raw.strip()
            if not raw:
                continue
            try:
                yield json.loads(raw)
            except json.JSONDecodeError:
                pass


def find_sessions(root: Path):
    if not root.exists():
        return
    for project_dir in sorted(root.iterdir()):
        if not project_dir.is_dir():
            continue
        # All JSONL files in the project tree (main + subagents).
        # Subagent files share turn UUIDs with the parent, so we
        # dedupe by UUID in the extract loop below.
        for jsonl in sorted(project_dir.rglob("*.jsonl")):
            yield jsonl


def encode_path(cwd: str) -> str:
    return cwd.replace("/", "-")


# ── Git identity (for agent_identity) ────────────────────────────────

def git_email() -> str | None:
    try:
        r = subprocess.run(
            ["git", "config", "--global", "user.email"],
            capture_output=True, text=True, timeout=2, check=False,
        )
        return r.stdout.strip() or None
    except Exception:
        return None


def git_name() -> str | None:
    try:
        r = subprocess.run(
            ["git", "config", "--global", "user.name"],
            capture_output=True, text=True, timeout=2, check=False,
        )
        return r.stdout.strip() or None
    except Exception:
        return None


# ── Main ──────────────────────────────────────────────────────────────

def sync(api_url: str, token: str, root: Path, session_filter: str | None = None):
    email = git_email()
    identity = None
    if email:
        identity = {"email": email}
        name = git_name()
        if name:
            identity["display_name"] = name

    sessions_total = 0
    turns_total = 0

    # Global dedup sets — subagent JSONL files share turn UUIDs with
    # the parent session file. Without dedup the server rejects the
    # batch on a unique-constraint violation.
    seen_session_ids: set[str] = set()
    seen_turn_uuids: set[str] = set()

    for jsonl_path in find_sessions(root):
        if session_filter and session_filter not in str(jsonl_path):
            continue

        sessions: list[dict] = []
        turns: list[dict] = []

        for line in iter_jsonl(jsonl_path):
            sm = extract_session(line)
            if sm and sm["id"] not in seen_session_ids:
                seen_session_ids.add(sm["id"])
                sessions.append({
                    **sm,
                    "project_path_encoded": encode_path(sm["cwd"]),
                    "jsonl_path": str(jsonl_path),
                    "jsonl_offset": 0,
                    "total_turns": 0,
                    "is_subagent": 0,
                })

            tm = extract_turn(line)
            if tm and tm["uuid"] not in seen_turn_uuids:
                seen_turn_uuids.add(tm["uuid"])
                turns.append(tm)

        if not sessions and not turns:
            continue

        # POST batch
        payload: dict = {"sessions": sessions, "turns": turns}
        if identity:
            payload["agent_identity"] = identity

        data = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(
            f"{api_url.rstrip('/')}/api/ingest/sessions",
            data=data,
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {token}",
            },
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                body = json.loads(resp.read())
                sessions_total += body.get("sessions_upserted", 0)
                turns_total += body.get("turns_upserted", 0)
        except urllib.error.HTTPError as e:
            print(f"  error: {e.code} {e.read().decode()[:200]}", file=sys.stderr)
        except Exception as e:
            print(f"  error: {e}", file=sys.stderr)

    print(f"Synced {sessions_total} sessions, {turns_total} turns to {api_url}")
    return sessions_total, turns_total


def sync_history_stubs(api_url: str, token: str, history_path: Path, root: Path):
    """Import activity dates from history.jsonl for sessions whose JSONL
    files have been purged by Claude Code. Creates lightweight stub
    sessions — enough for the heatmap but no token/tool detail."""
    if not history_path.exists():
        return

    with history_path.open("r", encoding="utf-8") as f:
        lines = []
        for raw in f:
            raw = raw.strip()
            if not raw:
                continue
            try:
                lines.append(json.loads(raw))
            except json.JSONDecodeError:
                pass

    # Collect existing session dates from the JSONL files so we don't
    # duplicate what the main sync already imported.
    jsonl_dates: set[str] = set()  # "YYYY-MM-DD"
    for jsonl_path in find_sessions(root):
        for line in iter_jsonl(jsonl_path):
            ts = line.get("timestamp", "")
            if ts and len(ts) >= 10:
                jsonl_dates.add(ts[:10])

    # Group history entries by (date, project)
    from collections import defaultdict as _ddict
    from datetime import datetime as _dt
    stubs_by_key: dict[tuple, list] = _ddict(list)
    for entry in lines:
        ts = entry.get("timestamp", 0)
        project = entry.get("project", "")
        if not (ts > 1000000000000 and project):
            continue
        dt = _dt.fromtimestamp(ts / 1000)
        date_str = dt.strftime("%Y-%m-%d")
        if date_str in jsonl_dates:
            continue  # real data exists for this date
        stubs_by_key[(date_str, project)].append(dt.isoformat())

    if not stubs_by_key:
        print("No purged history to recover.")
        return

    # POST stubs as sessions with no turns
    import uuid as _uuid
    stub_sessions = []
    for (date_str, project), timestamps in sorted(stubs_by_key.items()):
        earliest = min(timestamps)
        stub_sessions.append({
            "id": str(_uuid.uuid4()),
            "workspace_id": "default",
            "cwd": project,
            "project_path_encoded": project.replace("/", "-"),
            "started_at": earliest,
            "total_turns": len(timestamps),
            "is_subagent": 0,
            "jsonl_path": "history.jsonl",
            "jsonl_offset": 0,
        })

    # Batch into groups of 50
    email = git_email()
    identity = None
    if email:
        identity = {"email": email}
        name = git_name()
        if name:
            identity["display_name"] = name

    total = 0
    for i in range(0, len(stub_sessions), 50):
        batch = stub_sessions[i:i + 50]
        payload: dict = {"sessions": batch, "turns": []}
        if identity:
            payload["agent_identity"] = identity
        data = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(
            f"{api_url.rstrip('/')}/api/ingest/sessions",
            data=data,
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {token}",
            },
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                body = json.loads(resp.read())
                total += body.get("sessions_upserted", 0)
        except Exception as e:
            print(f"  stub error: {e}", file=sys.stderr)

    print(f"Recovered {total} activity stubs from purged history")


if __name__ == "__main__":
    import argparse
    p = argparse.ArgumentParser(description="Scalene privacy-first sync")
    p.add_argument("--api-url", required=True)
    p.add_argument("--token", required=True)
    p.add_argument("--session-only", default=None, help="Sync only this session ID")
    p.add_argument("--root", default=str(Path.home() / ".claude" / "projects"))
    args = p.parse_args()
    sync(args.api_url, args.token, Path(args.root), args.session_only)
    # Also recover any purged history
    if not args.session_only:
        history = Path.home() / ".claude" / "history.jsonl"
        sync_history_stubs(args.api_url, args.token, history, Path(args.root))
