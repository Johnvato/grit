#!/usr/bin/env python3
"""Link checker for Pollygraph (runs every 4 hours via GitHub Actions).

Scans app.py for every URL, checks each one, and for broken links:
  1. Tries to replace with a Wayback Machine archived snapshot.
  2. If no archive exists, removes the broken link from app.py.

For controversy sections: if ALL source links for a controversy are
dead and un-archivable, the entire controversy entry is removed
(unsourced claims must not appear on the site).

For other links (parliament, council, markdown, HTML), individual
broken links are removed.
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

# Matches one full controversy dict entry: { ... },
CONTROVERSY_RE = re.compile(
    r'        \{\s*\n'
    r'            "title":\s*"(?P<title>[^"]+)",\s*\n'
    r'(?:.*?\n)*?'
    r'            "sources":\s*\[\s*\n'
    r'(?P<sources>(?:.*?\n)*?)'
    r'            \],\s*\n'
    r'        \},?\s*\n',
)

SOURCE_TUPLE_RE = re.compile(
    r'\("(?P<label>[^"]+)",\s*"(?P<url>[^"]+)"\)'
)


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
    """HEAD-check a URL. Returns (status_code, reason)."""
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


def parse_controversies(source: str) -> list[dict]:
    """Extract controversy entries with their source URLs and positions."""
    entries = []
    for m in CONTROVERSY_RE.finditer(source):
        title = m.group("title")
        urls = [sm.group("url") for sm in SOURCE_TUPLE_RE.finditer(m.group("sources"))]
        entries.append({
            "title": title,
            "urls": urls,
            "start": m.start(),
            "end": m.end(),
            "text": m.group(),
        })
    return entries


def remove_broken_link(source: str, url: str) -> str:
    """Remove a single broken link from the source code.

    Handles:
      1. Source tuple line:  ("label", "https://..."),
      2. Markdown link:     [text](https://...)
      3. HTML anchor:       <a href="https://...">...</a>
      4. Bare URL in a string
    """
    tuple_re = re.compile(
        r'[ \t]*\(".*?",\s*"' + re.escape(url) + r'"\),?\s*\n',
    )
    if tuple_re.search(source):
        return tuple_re.sub("", source)

    md_re = re.compile(r'\[([^\]]*)\]\(' + re.escape(url) + r'\)')
    if md_re.search(source):
        return md_re.sub("", source)

    a_re = re.compile(
        r'<a\s[^>]*href="' + re.escape(url) + r'"[^>]*>.*?</a>',
        re.DOTALL,
    )
    if a_re.search(source):
        return a_re.sub("", source)

    return source.replace(url, "")


def main():
    source = APP_PY.read_text()
    urls = extract_urls(source)
    print(f"Found {len(urls)} unique URLs in app.py\n")

    # Phase 1: check every URL
    url_status: dict[str, tuple[int | None, str]] = {}
    broken_urls: set[str] = set()
    ok_count = 0

    for url in urls:
        status, reason = check_url(url)
        url_status[url] = (status, reason)
        if status and 200 <= status < 400:
            ok_count += 1
            print(f"  OK  {status} {url}")
        else:
            broken_urls.add(url)
            print(f"  FAIL {status} {url}  ({reason})")
        time.sleep(0.3)

    print(f"\n{ok_count} OK, {len(broken_urls)} broken\n")

    if not broken_urls:
        print("All links healthy — nothing to do.")
        return

    # Phase 2: handle controversy sections first
    controversies = parse_controversies(source)
    controversy_urls_handled: set[str] = set()
    entries_removed = 0
    updated_source = source

    for entry in controversies:
        entry_broken = [u for u in entry["urls"] if u in broken_urls]
        if not entry_broken:
            continue

        # Try to archive each broken link in this entry
        surviving = 0
        for u in entry["urls"]:
            if u not in broken_urls:
                surviving += 1
            else:
                wb = wayback_url(u)
                if wb:
                    print(f"  REPLACE {u}\n       -> {wb}")
                    updated_source = updated_source.replace(u, wb)
                    controversy_urls_handled.add(u)
                    surviving += 1
                else:
                    controversy_urls_handled.add(u)

        if surviving == 0:
            # ALL sources dead and un-archivable — remove entire entry
            print(f"  REMOVE CONTROVERSY \"{entry['title']}\" (all sources dead)")
            updated_source = updated_source.replace(entry["text"], "")
            entries_removed += 1
        else:
            # Some sources survived — just remove the dead tuple lines
            for u in entry_broken:
                if u in controversy_urls_handled:
                    wb_check = wayback_url(u)
                    if not wb_check:
                        print(f"  REMOVE SOURCE {u} from \"{entry['title']}\"")
                        updated_source = remove_broken_link(updated_source, u)

    # Phase 3: handle all other broken links (non-controversy)
    replaced = 0
    removed = 0
    for url in broken_urls:
        if url in controversy_urls_handled:
            continue
        wb = wayback_url(url)
        if wb:
            print(f"  REPLACE {url}\n       -> {wb}")
            updated_source = updated_source.replace(url, wb)
            replaced += 1
        else:
            print(f"  REMOVE  {url}  (no archive available)")
            updated_source = remove_broken_link(updated_source, url)
            removed += 1

    # Phase 4: write if changed
    if updated_source != source:
        APP_PY.write_text(updated_source)
        parts = []
        if entries_removed:
            parts.append(f"{entries_removed} controversy section(s) removed (unsourced)")
        if replaced:
            parts.append(f"{replaced} link(s) replaced with archive")
        if removed:
            parts.append(f"{removed} link(s) removed")
        print(f"\nUpdated app.py: {', '.join(parts)}.")
    else:
        print("\nNo changes needed.")


if __name__ == "__main__":
    main()
