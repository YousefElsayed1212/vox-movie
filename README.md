# VOX Movies Booking Monitor

Telegram alert bot for **VOX Cinemas Egypt — City Centre Almaza**.

## Movies monitored

- **Dune: Part Three** — all listed showtimes and formats.
- **Avengers: Doomsday** — showtimes outside the Infinity Vision hall.
- **Avengers: Doomsday (Infinity Vision)** — showtimes specifically listed under the Infinity Vision hall.

The bot detects new showtime booking IDs and sends a Telegram alert with the date, time, hall, and a direct booking button. It checks every five minutes through GitHub Actions, so your computer can be off.

## How it works

- Uses **Selenium with headless Chrome** to load VOX like a real browser, including page-rendered content.
- Discovers the dates currently open for booking from the VOX date navigation.
- Reads showtime booking IDs from the showtime list items.
- Saves previously seen slots in `seen.json` and avoids duplicate alerts.
- Sends an alert only after Telegram confirms the message was sent.
- Uploads HTML and screenshot debug files if VOX fails to load.

## GitHub setup

1. In **Settings → Secrets and variables → Actions**, add either:
   - `TOKEN` and `CHAT_ID`, or
   - `TELEGRAM_BOT_TOKEN` and `TELEGRAM_CHAT_ID`.
2. In **Settings → Actions → General → Workflow permissions**, enable read and write access to repository contents.
3. Open **Actions → VOX Movies Monitor → Run workflow** to test it.
4. The first complete successful scan creates a baseline. Existing showtimes will not trigger alerts; only later additions will.

## Troubleshooting

If a VOX page does not load or its showtime cards are not found, the workflow uploads debug snapshots under **Artifacts → vox-debug-snapshots**. These files help identify whether Chrome received a block page, a timeout, or changed page markup.

## Important

GitHub Actions schedules are not guaranteed to start at the exact minute. VOX may also change its website or restrict automated traffic. The bot only observes availability and sends alerts; it does not reserve seats or purchase tickets.
