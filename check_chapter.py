#!/usr/bin/env python3
"""One Piece chapter release notifier for TCB Scans.

Fetches the TCB One Piece chapter list, finds the newest chapter, and if it is
newer than the last one we recorded, fires an ntfy (and optionally Discord)
notification, then records the new chapter number.

Exit codes:
  0  success (whether or not a new chapter was found)
  1  the page fetch failed, no chapter links were parsed, or a configured
     ntfy notification could not be delivered. In these cases last_chapter.txt
     is left untouched so the next run retries.
"""
import os
import re
import sys

import requests
from bs4 import BeautifulSoup

CHAPTER_LIST_URL = "https://tcbonepiecechapters.com/mangas/5/one-piece"
BASE_URL = "https://tcbonepiecechapters.com"
LAST_CHAPTER_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "last_chapter.txt")
REQUEST_TIMEOUT = 30

# A real browser User-Agent so we are not trivially blocked by Cloudflare.
USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/125.0.0.0 Safari/537.36"
)

# Matches both relative (/chapters/123/one-piece-chapter-1187) and absolute
# (https://tcbonepiecechapters.com/chapters/123/one-piece-chapter-1187) hrefs.
# The chapter number may contain dots represented as dashes, e.g. 1053-4.
HREF_RE = re.compile(
    r"^(?:https?://tcbonepiecechapters\.com)?/chapters/\d+/one-piece-chapter-([\d-]+)$"
)

# Pulls the subtitle out of a link's text, e.g.
# "One Piece Chapter 1187 The Cause" -> "The Cause".
TITLE_RE = re.compile(r"^one piece chapter\s+[\d.]+\s*(.*)$", re.IGNORECASE)


def parse_chapter_number(raw):
    """Convert a slug fragment like '1053-4' into the float 1053.4."""
    return float(raw.replace("-", ".", 1))


def format_number(value):
    """Render a chapter float cleanly: 1187.0 -> '1187', 1053.4 -> '1053.4'."""
    return str(int(value)) if value == int(value) else str(value)


def split_title(full_title, number):
    """Return (chapter_label, subtitle) derived from a link's full text."""
    chapter_label = f"One Piece Chapter {format_number(number)}"
    match = TITLE_RE.match(full_title)
    subtitle = match.group(1).strip() if match else ""
    return chapter_label, subtitle


def fetch_chapters():
    """Fetch and parse the chapter list.

    Returns a list of (number_float, full_title, absolute_url) tuples. Raises
    requests.RequestException on network/HTTP errors. Returns [] if the page
    loaded but contained no recognizable chapter links.
    """
    resp = requests.get(
        CHAPTER_LIST_URL,
        headers={"User-Agent": USER_AGENT},
        timeout=REQUEST_TIMEOUT,
    )
    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, "html.parser")

    chapters = []
    for anchor in soup.find_all("a", href=True):
        href = anchor["href"].strip()
        match = HREF_RE.match(href)
        if not match:
            continue
        try:
            number = parse_chapter_number(match.group(1))
        except ValueError:
            continue
        title = " ".join(anchor.get_text().split())
        url = href if href.startswith("http") else BASE_URL + href
        chapters.append((number, title, url))
    return chapters


def read_last_chapter():
    """Read the last-seen chapter number; return 0.0 if missing/unreadable."""
    try:
        # utf-8-sig transparently strips a BOM if one sneaks in (e.g. the file
        # was edited via a Windows tool or the GitHub web editor).
        with open(LAST_CHAPTER_FILE, "r", encoding="utf-8-sig") as fh:
            raw = fh.read().strip()
    except FileNotFoundError:
        return 0.0
    if not raw:
        return 0.0
    try:
        return parse_chapter_number(raw)
    except ValueError:
        return 0.0


def write_last_chapter(number):
    with open(LAST_CHAPTER_FILE, "w", encoding="utf-8") as fh:
        fh.write(format_number(number) + "\n")


def send_ntfy(topic, body, click_url):
    """Publish a notification to ntfy.sh. Raises on HTTP error."""
    resp = requests.post(
        f"https://ntfy.sh/{topic}",
        data=body.encode("utf-8"),
        headers={
            # Emoji must be sent as raw UTF-8 bytes: HTTP header values are
            # latin-1 by default and requests would raise UnicodeEncodeError on
            # a str containing the pirate flag. ntfy decodes the header as UTF-8.
            "Title": "\U0001F3F4‍☠️ New One Piece chapter!".encode("utf-8"),
            "Click": click_url,
            "Priority": "high",
            "Tags": "pirate_flag",
        },
        timeout=REQUEST_TIMEOUT,
    )
    resp.raise_for_status()


def send_discord(webhook_url, content):
    """Post a message to a Discord webhook. Raises on HTTP error."""
    resp = requests.post(webhook_url, json={"content": content}, timeout=REQUEST_TIMEOUT)
    resp.raise_for_status()


def main():
    topic = os.environ.get("NTFY_TOPIC")
    discord_url = os.environ.get("DISCORD_WEBHOOK_URL")

    # 1. Fetch + parse.
    try:
        chapters = fetch_chapters()
    except requests.RequestException as exc:
        print(f"ERROR: failed to fetch chapter list: {exc}", file=sys.stderr)
        return 1

    if not chapters:
        print(
            "ERROR: no chapter links found (page layout changed or blocked?)",
            file=sys.stderr,
        )
        return 1

    # 2. Newest = highest number found (don't rely on page ordering).
    number, title, url = max(chapters, key=lambda c: c[0])
    last = read_last_chapter()

    # 3. Nothing new.
    if number <= last:
        print(f"No new chapter (latest: {format_number(number)})")
        return 0

    # 4. New chapter -> build notification text.
    chapter_label, subtitle = split_title(title, number)
    if subtitle:
        ntfy_body = f"{chapter_label} — {subtitle}"
        discord_content = f"\U0001F3F4‍☠️ **{chapter_label}** — {subtitle}\n{url}"
    else:
        ntfy_body = chapter_label
        discord_content = f"\U0001F3F4‍☠️ **{chapter_label}**\n{url}"

    # 5a. ntfy (required). If it fails, leave last_chapter.txt alone so the next
    #     run retries, and exit non-zero so the failure is visible.
    if topic:
        try:
            send_ntfy(topic, ntfy_body, url)
            print(f"Sent ntfy notification to topic '{topic}'")
        except requests.RequestException as exc:
            print(f"ERROR: ntfy notification failed: {exc}", file=sys.stderr)
            return 1
    else:
        print("ERROR: NTFY_TOPIC is not set; cannot notify.", file=sys.stderr)
        return 1

    # 5b. Discord (optional). A failure here is non-fatal.
    if discord_url:
        try:
            send_discord(discord_url, discord_content)
            print("Sent Discord notification")
        except requests.RequestException as exc:
            print(f"WARNING: Discord notification failed: {exc}", file=sys.stderr)

    # 5c. Record the new chapter.
    write_last_chapter(number)

    print(f"New chapter detected: {ntfy_body}")
    print(f"URL: {url}")
    print(f"Updated last_chapter.txt: {format_number(last)} -> {format_number(number)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
