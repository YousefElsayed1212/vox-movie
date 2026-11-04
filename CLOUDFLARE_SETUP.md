# Cloudflare Worker setup — VOX alerts

This version only watches these three listings at City Centre Almaza:
- Dune: Part Three
- Avengers: Doomsday
- Avengers: Doomsday (Infinity Vision)

It sends **only the direct booking URL** to Telegram when a new booking ID appears. It does not book tickets.

## 1. Create the KV namespace
1. Open Cloudflare Dashboard → Workers & Pages → KV.
2. Create a namespace named `VOX_BOOKING_STATE`.
3. Copy its namespace ID.
4. In `wrangler.toml`, replace `REPLACE_WITH_YOUR_KV_NAMESPACE_ID` with that ID.

## 2. Add Telegram secrets
In Workers & Pages → `vox-movie-alerts` → Settings → Variables and Secrets, add:
- `TELEGRAM_BOT_TOKEN` — your Telegram bot token
- `TELEGRAM_CHAT_ID` — your Telegram chat ID

Mark both as secrets. Do not put either value in GitHub.

## 3. Deploy
From the repository folder, run:
```bash
npm install -g wrangler
npx wrangler login
npx wrangler deploy
```

The Worker uses the Cron Trigger `* * * * *` (every minute). After deployment, open the Worker → Triggers to confirm the schedule, then check Observability → Logs.

## Important limitations
- The Worker checks the date index and each date VOX currently publishes. If VOX blocks Cloudflare requests (for example HTTP 403) or changes its HTML, the run logs an error and does not treat that as “no bookings.”
- Cloudflare Workers Free currently has a 10 ms CPU limit per Cron invocation. The page parsing and the number of active VOX dates may exceed that limit; if that happens, a paid Workers plan or a lighter official VOX data endpoint will be needed.
- Cron schedules run every minute, but Cloudflare does not guarantee exact-to-the-second delivery.
- Telegram messages contain only the direct booking URL.
