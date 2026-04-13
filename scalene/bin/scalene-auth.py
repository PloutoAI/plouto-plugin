#!/usr/bin/env python3
"""Scalene device auth — opens browser, polls for confirmation, saves credentials."""

import json
import os
import subprocess
import sys
import time
import urllib.request

API = "https://getscalene.com"


def main():
    # Start auth
    req = urllib.request.Request(
        f"{API}/api/cli/auth",
        method="POST",
        data=b"",
        headers={"Content-Type": "application/json"},
    )
    resp = json.loads(urllib.request.urlopen(req, timeout=10).read())
    code, url = resp["code"], resp["url"]

    print(f"Opening browser... confirm code: {code}")
    subprocess.run(["open", url], check=False)

    # Poll
    for i in range(30):
        time.sleep(2)
        r = json.loads(
            urllib.request.urlopen(
                f"{API}/api/cli/poll?code={code}", timeout=10
            ).read()
        )
        if r["status"] == "confirmed":
            api_url, token = r["api_url"], r["token"]
            # Save to zshrc
            with open(os.path.expanduser("~/.zshrc"), "a") as f:
                f.write(f"\nexport SCALENE_API_URL={api_url}\n")
                f.write(f"export SCALENE_TOKEN={token}\n")
            print(f"Connected! Credentials saved to ~/.zshrc")
            print(f"SCALENE_API_URL={api_url}")
            print(f"SCALENE_TOKEN={token}")
            return
        if i % 5 == 0 and i > 0:
            print("Waiting for browser confirmation...")

    print("Timed out. Try again.")
    sys.exit(1)


if __name__ == "__main__":
    main()
