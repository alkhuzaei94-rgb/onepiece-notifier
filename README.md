# 🏴‍☠️ One Piece Chapter Notifier

Get a push notification on your phone the moment [TCB Scans](https://tcbonepiecechapters.com/mangas/5/one-piece)
uploads a new One Piece chapter. Runs entirely on **GitHub Actions** — no server,
no always-on machine. Notifications are delivered via [ntfy.sh](https://ntfy.sh)
(free) and, optionally, a Discord webhook.

## How it works

A GitHub Actions job runs [`check_chapter.py`](check_chapter.py). GitHub's own
cron is too unreliable for this (a "every 15 min" schedule really fired every
4–8 hours), so during the **Wed–Fri (UTC) release window** a run stays alive and
checks the site **every 60 seconds** for ~5.5 hours, then starts the next run
itself — continuous coverage until the chapter appears. The rest of the week it
does an occasional single check. Each check:

1. Fetches the TCB One Piece chapter list with a browser User-Agent.
2. Parses every `/chapters/{id}/one-piece-chapter-{number}` link and picks the
   highest chapter number (e.g. `1053-4` is compared as `1053.4`).
3. Compares it against the number stored in [`last_chapter.txt`](last_chapter.txt).
4. If it's newer, sends an ntfy (and optional Discord) notification, then commits
   the new number back to the repo so it isn't announced twice.

If the page can't be fetched or no chapters parse, the run logs it and exits quietly
and `last_chapter.txt` is left untouched, so the next run simply retries.

## Setup

### 1. Install the ntfy app and subscribe to a topic

- Install **ntfy** from the [Play Store](https://play.google.com/store/apps/details?id=io.heckel.ntfy)
  or [App Store](https://apps.apple.com/us/app/ntfy/id1625396347).
- Tap **+ → Subscribe to topic** and enter a **secret, hard-to-guess** topic name,
  e.g. `mk-onepiece-a8f3k1`.

> ⚠️ Anyone who knows the topic name can read *and* publish to it. Treat it like a
> password — make it random.

### 2. Create a GitHub repo and push this folder

Create a new **private** repo (e.g. `onepiece-notifier`). The contents of this
`onepiece-notifier/` folder should sit at the **root** of the repo (so
`check_chapter.py` and `.github/workflows/check.yml` are at the top level).

```bash
cd onepiece-notifier
git init
git add .
git commit -m "Initial commit"
git branch -M main
git remote add origin https://github.com/<you>/onepiece-notifier.git
git push -u origin main
```

### 3. Add repository secrets

Repo → **Settings → Secrets and variables → Actions → New repository secret**:

| Secret name           | Value                                                   |
| --------------------- | ------------------------------------------------------- |
| `NTFY_TOPIC`          | your topic name, e.g. `mk-onepiece-a8f3k1` (**required**) |
| `DISCORD_WEBHOOK_URL` | a Discord webhook URL (**optional** — skip to disable)  |

### 4. Test it

- Go to the **Actions** tab → select **Check for new One Piece chapter** →
  **Run workflow**.
- For a real end-to-end test, edit `last_chapter.txt` on GitHub to a lower number
  (e.g. `1186`) and run the workflow again. Your phone should buzz with the latest
  chapter within seconds, and the workflow will auto-correct `last_chapter.txt`.

That's it. From now on GitHub checks the site on the schedule above and pushes a
notification (whose tap opens the chapter directly) the moment a new one drops.

## Notification format

**ntfy**
- Title: `🏴‍☠️ New One Piece chapter!`
- Body: `One Piece Chapter 1188 — <subtitle>`
- Tapping the notification opens the chapter (`Click` header), priority `high`.

**Discord** (if `DISCORD_WEBHOOK_URL` is set)
```
🏴‍☠️ **One Piece Chapter 1188** — <subtitle>
<chapter_url>
```

## Running locally

```bash
pip install -r requirements.txt
NTFY_TOPIC=your-topic python check_chapter.py        # Linux/macOS
# PowerShell:  $env:NTFY_TOPIC="your-topic"; python check_chapter.py
```

## Caveats

- **GitHub cron is best-effort** — it's only used to (re)start the watcher; the
  watcher itself polls every minute, so notifications land within ~1–2 min.
- **Cloudflare**: if TCB ever starts returning `403` to GitHub's IP ranges,
  swap `requests` for [`cloudscraper`](https://pypi.org/project/cloudscraper/) —
  it's a near drop-in replacement that solves Cloudflare's basic challenge. Add
  `cloudscraper` to `requirements.txt` and replace `requests.get(...)` in
  `fetch_chapters()` with a `cloudscraper.create_scraper()` session.
- **Actions minutes / cost**: the watcher uses up to ~72 runner-hours a week.
  That's free because **this repo is public**. Don't make it private — that
  would blow through the 2,000 free min/month.
  Either way, set your Actions **spending limit to $0**
  (github.com/settings/billing) to guarantee you're never charged.
