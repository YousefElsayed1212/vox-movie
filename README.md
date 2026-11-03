# VOX Movies Monitor

Telegram monitor for **VOX Cinemas Egypt — City Centre Almaza**.

## What it monitors

- **Showtimes:** new booking/showtime slots, including date, time, cinema format, and booking link.
- **Coming Soon:** newly listed upcoming films and their release dates.
- Checks every **5 minutes** using GitHub Actions, so your computer does not need to stay on.
- Saves seen movies and showtimes in `seen.json` to avoid duplicate notifications.

## Setup

1. Open **Settings → Secrets and variables → Actions**.
2. Add your Telegram bot token and chat ID as repository secrets. Either naming pair is supported:
   - `TOKEN` and `CHAT_ID`, or
   - `TELEGRAM_BOT_TOKEN` and `TELEGRAM_CHAT_ID`.
3. Open **Actions**, enable workflows if GitHub asks, then run **VOX Movies Monitor** once using **Run workflow**.
4. The first successful run creates a baseline and does not send notifications for everything already listed. New items are reported on later runs.

## Notes

- GitHub Actions scheduled runs are not guaranteed to start at the exact minute; GitHub may delay scheduled workflows.
- The workflow commits `seen.json` back to the repository. Keep the repository's Actions permission to write contents enabled.
- If VOX changes its website markup or blocks requests, open the latest workflow run and inspect its logs.
- The Coming Soon page parser is defensive but depends on VOX's live page structure. A zero-result extraction fails safely rather than clearing the saved state.
