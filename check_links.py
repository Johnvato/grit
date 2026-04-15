#!/usr/bin/env python3
"""Link checker for Pollygraph (runs every 4 hours via GitHub Actions).

Scans app.py for every URL, checks each one, and for broken links:
  1. Tries to replace with a Wayback Machine archived snapshot.
  2. If no archive exists, removes the broken link from app.py.

For controversy source tuples like  ("label", "https://..."),
the entire tuple line is removed.  For standalone URLs embedded
in markdown or HTML, the URL (and any wrapping anchor/link) is
stripped.  Writes a summary to stdout.
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
    except Exception:
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


def remove_broken_link(source: str, url: str) -> str:
    """Remove a broken link from the source code.

    Handles these patterns (most specific first):
      1. Source tuple line:  ("label", "https://..."),
      2. Markdown link:     [text](https://...)
      3. HTML anchor:       <a href="https://...">...</a>
      4. Bare URL in a string
    """
    # Pattern 1: controversy source tuple — remove entire line
    # e.g.   ("ABC News — whatever", "https://broken.example.com/path"),
    tuple_re = re.compile(
        r'[ \t]*\(".*?",\s*"' + re.escape(url) + r'"\),?\s*\n',
    )
    if tuple_re.search(source):
        return tuple_re.sub("", source)

    # Pattern 2: markdown link [label](url) → remove the whole link
    md_re = re.compile(r'\[([^\]]*)\]\(' + re.escape(url) + r'\)')
    if md_re.search(source):
        return md_re.sub("", source)

    # Pattern 3: HTML <a> tag wrapping the URL → remove entire tag
    a_re = re.compile(
        r'<a\s[^>]*href="' + re.escape(url) + r'"[^>]*>.*?</a>',
        re.DOTALL,
    )
    if a_re.search(source):
        return a_re.sub("", source)

    # Pattern 4: bare URL in a quoted string → remove just the URL
    return source.replace(url, "")


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
        time.sleep(0.3)

    print(f"\n{ok_count} OK, {len(broken)} broken\n")

    if not broken:
        print("All links healthy — nothing to do.")
        return

    replaced = 0
    removed = 0
    updated_source = source

    for url, status, reason in broken:
        wb = wayback_url(url)
        if wb:
            print(f"  REPLACE {url}\n       -> {wb}")
            updated_source = updated_source.replace(url, wb)
            replaced += 1
        else:
            print(f"  REMOVE  {url}  (no archive available)")
            updated_source = remove_broken_link(updated_source, url)
            removed += 1

    if replaced or removed:
        APP_PY.write_text(updated_source)
        parts = []
        if replaced:
            parts.append(f"{replaced} replaced with archive")
        if removed:
            parts.append(f"{removed} removed")
        print(f"\nUpdated app.py: {', '.join(parts)}.")
    else:
        print("\nNo changes needed.")


if __name__ == "__main__":
    main()
