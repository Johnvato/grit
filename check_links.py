#!/usr/bin/env python3
"""Nightly link checker for Pollygraph.

Scans app.py for every URL, HEAD-checks each one, and for any that
return 4xx/5xx (or timeout) attempts to swap the URL for a working
Wayback Machine snapshot.  Writes a summary to stdout and, if any
links were replaced, updates app.py in-place so the GitHub Action
can commit the change.
"""

import re
import sys
import time
import urllib.request
import urllib.error
import json
from pathlib import Path

APP_PY = Path(__file__).with_name("app.py")

TIMEOUT = 15  # seconds per request
SKIP_DOMAINS = {
    "nominatim.openstreetmap.org",  # API endpoint, not a page
    "theyvoteforyou.org.au",        # blocks bot User-Agents but works in browsers
    "aemo.com.au",                  # blocks bot User-Agents but works in browsers
}

URL_RE = re.compile(r'https?://[^\s"\'<>\)]+')


def extract_urls(text: str) -> list[str]:
    """Return deduplicated URLs in order of first appearance."""
    seen = set()
    urls = []
    for m in URL_RE.finditer(text):
        url = m.group().rstrip(",;.")
        if url not in seen:
            seen.add(url)
            urls.append(url)
    return urls


def check_url(url: str) -> tuple[int | None, str]:
    """HEAD-check a URL; returns (status_code, reason).

    Returns (None, reason) on network/timeout errors.
    """
    for domain in SKIP_DOMAINS:
        if domain in url:
            return (200, "skipped")
    req = urllib.request.Request(url, method="HEAD", headers={
        "User-Agent": "PollygraphLinkChecker/1.0",
    })
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
            return (resp.status, resp.reason)
    except urllib.error.HTTPError as e:
        return (e.code, str(e.reason))
    except Exception as e:
        # Retry with GET — some servers reject HEAD
        req_get = urllib.request.Request(url, method="GET", headers={
            "User-Agent": "PollygraphLinkChecker/1.0",
        })
        try:
            with urllib.request.urlopen(req_get, timeout=TIMEOUT) as resp:
                return (resp.status, resp.reason)
        except urllib.error.HTTPError as e2:
            return (e2.code, str(e2.reason))
        except Exception as e2:
            return (None, str(e2))


def wayback_url(original: str) -> str | None:
    """Ask the Wayback Machine for the latest snapshot of a URL."""
    api = f"https://archive.org/wayback/available?url={original}"
    req = urllib.request.Request(api, headers={
        "User-Agent": "PollygraphLinkChecker/1.0",
    })
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
            data = json.loads(resp.read())
        snap = data.get("archived_snapshots", {}).get("closest")
        if snap and snap.get("available"):
            return snap["url"]
    except Exception:
        pass
    return None


def main():
    source = APP_PY.read_text()
    urls = extract_urls(source)
    print(f"Found {len(urls)} unique URLs in app.py\n")

    broken: list[tuple[str, int | None, str]] = []
    ok_count = 0

    for url in urls:
        status, reason = check_url(url)
        if status and 200 <= status < 400:
            ok_count += 1
            print(f"  OK  {status} {url}")
        else:
            broken.append((url, status, reason))
            print(f"  FAIL {status} {url}  ({reason})")
        time.sleep(0.3)  # polite delay

    print(f"\n{ok_count} OK, {len(broken)} broken\n")

    if not broken:
        print("All links healthy — nothing to do.")
        return

    replaced = 0
    updated_source = source
    for url, status, reason in broken:
        wb = wayback_url(url)
        if wb:
            print(f"  REPLACE {url}\n       -> {wb}")
            updated_source = updated_source.replace(url, wb)
            replaced += 1
        else:
            print(f"  NO ARCHIVE for {url}")

    if replaced:
        APP_PY.write_text(updated_source)
        print(f"\nReplaced {replaced} broken link(s) in app.py")
    else:
        print("\nNo archive replacements available.")

    # Exit with code 1 if any broken links remain unfixed
    unfixed = len(broken) - replaced
    if unfixed:
        print(f"\n⚠ {unfixed} broken link(s) could not be auto-fixed.")
        sys.exit(1)


if __name__ == "__main__":
    main()
