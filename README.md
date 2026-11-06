# 🏴‍☠️ One Piece Chapter Notifier

Get a push notification on your phone the moment [TCB Scans](https://tcbonepiecechapters.com/mangas/5/one-piece)
uploads a new One Piece chapter. Runs entirely on **GitHub Actions** — no server,
no always-on machine. Notifications are delivered via [ntfy.sh](https://ntfy.sh)
(free) and, optionally, a Discord webhook.

## How it works

A GitHub Actions job runs [`check_chapter.py`](check_chapter.py) every few
minutes, triggered by a free external cron service (see
[Getting notified on time](#5-getting-notified-on-time-external-trigger)), with
GitHub's own schedule — every 15 minutes on Wed/Thu/Fri and every 3 hours the
rest of the week — as a fallback. Each run:

1. Fetches the TCB One Piece chapter list with a browser User-Agent, retrying
   briefly if TCB answers with a 5xx/timeout (it often does for a few seconds).
2. Parses every `/chapters/{id}/one-piece-chapter-{number}` link and picks the
   highest chapter number (e.g. `1053-4` is compared as `1053.4`).
3. Compares it against the number stored in [`last_chapter.txt`](last_chapter.txt).
4. If it's newer, sends an ntfy (and optional Discord) notification, then commits
   the new number back to the repo so it isn't announced twice.

If the page can't be fetched or no chapters parse, the run fails **red** (exit 1)
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

### 5. Getting notified on time (external trigger)

**Don't skip this step.** GitHub's built-in schedule is unreliable: although the
workflow asks for a check every 15 minutes on Wed–Fri, GitHub has actually been
running it only every **3–5 hours** (see [Caveats](#caveats)), so a chapter could
sit on TCB for hours before you heard about it. Manually triggered runs, by
contrast, start within seconds, so let a free cron service trigger the workflow
for you.

1. **Create a token that can only start this workflow.** GitHub → Settings →
   Developer settings → Personal access tokens → **Fine-grained tokens** →
   *Generate new token*:
   - Repository access: **Only select repositories** → `onepiece-notifier`
   - Repository permissions: **Actions → Read and write** (nothing else)
   - Pick an expiration and set yourself a reminder to renew it.
2. **Create a cron job** at [cron-job.org](https://cron-job.org) (free) →
   *Create cronjob*:
   - URL: `https://api.github.com/repos/<you>/onepiece-notifier/actions/workflows/check.yml/dispatches`
   - Schedule: **every 5 minutes** on **Wednesday, Thursday and Friday**
     (timezone UTC). GitHub's 3-hourly fallback covers the other days.
   - *Advanced* tab → Request method **POST**, request body `{"ref":"main"}`,
     and these headers:

     | Header                 | Value                         |
     | ---------------------- | ----------------------------- |
     | `Accept`               | `application/vnd.github+json` |
     | `Authorization`        | `Bearer <your token>`         |
     | `X-GitHub-Api-Version` | `2022-11-28`                  |
3. Click **Test run**. It should return **HTTP 204**, and a new
   `workflow_dispatch` run should appear in the Actions tab a few seconds later.

You can test the token from a terminal too:

```bash
curl -X POST https://api.github.com/repos/<you>/onepiece-notifier/actions/workflows/check.yml/dispatches \
  -H "Accept: application/vnd.github+json" \
  -H "Authorization: Bearer <your token>" \
  -d '{"ref":"main"}'
```

That's it. From now on the site is checked every few minutes during the release
window, and you get a notification (whose tap opens the chapter directly) within
minutes of a new one dropping.

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

- **GitHub's schedule alone is too slow.** Scheduled runs are best-effort and
  GitHub silently drops them under load. In this repo the every-15-min Wed–Fri
  schedule actually fired every 45–90 min in July/August and every **3–5 h**
  from September on (e.g. chapter 1196 was picked up at 07:05 UTC on a Friday;
  the previous check had been at 02:04). That's why the external trigger in
  step 5 is needed. The fallback schedule avoids the `:00`/`:15`/`:30`/`:45`
  minute marks, which GitHub documents as its busiest times.
- **Cloudflare**: if TCB ever starts returning `403` to GitHub's IP ranges,
  swap `requests` for [`cloudscraper`](https://pypi.org/project/cloudscraper/) —
  it's a near drop-in replacement that solves Cloudflare's basic challenge. Add
  `cloudscraper` to `requirements.txt` and replace `requests.get(...)` in
  `fetch_chapters()` with a `cloudscraper.create_scraper()` session.
- **Actions minutes / cost**: **public repos get unlimited free Actions** (this
  repo is public — recommended). If you make it private instead, you get 2,000
  free min/month and every run is billed as at least 1 minute, so an
  every-5-minute Wed–Fri trigger (~3,700 runs/month) would *not* fit — trigger
  every 10 minutes on Thu/Fri only instead. Either way, set your Actions
  **spending limit to $0** (github.com/settings/billing) to guarantee you're
  never charged.
