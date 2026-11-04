const BASE_URL = "https://egy.voxcinemas.com";
const SHOWTIMES_URL = `${BASE_URL}/showtimes?c=city-centre-almaza`;
const BRANCH = "City Centre Almaza";

// Existing booking IDs imported from the repository's seen.json.
// This prevents the first Cloudflare run from re-alerting old showtimes.
const INITIAL_SEEN = [
  "2026-12-16:0047-276866",
  "2026-12-17:0047-276742",
  "2026-12-17:0047-276743",
  "2026-12-17:0047-276744",
  "2026-12-17:0047-276745",
  "2026-12-18:0047-276746",
  "2026-12-18:0047-276747",
  "2026-12-18:0047-276748",
  "2026-12-18:0047-276749",
  "2026-12-18:0047-276775",
  "2026-12-18:0047-276903",
  "2026-12-18:0047-276901",
  "2026-12-18:0047-276904",
  "2026-12-19:0047-276750",
  "2026-12-19:0047-276751",
  "2026-12-19:0047-276752",
  "2026-12-19:0047-276753",
  "2026-12-19:0047-276914",
  "2026-12-19:0047-276778",
  "2026-12-19:0047-276779",
  "2026-12-19:0047-276992",
  "2026-12-19:0047-276993",
  "2026-12-19:0047-276994",
  "2026-12-19:0047-276995",
  "2026-12-20:0047-276754",
  "2026-12-20:0047-276755",
  "2026-12-20:0047-276756",
  "2026-12-20:0047-276757",
  "2026-12-20:0047-276943",
  "2026-12-20:0047-276939",
  "2026-12-20:0047-276937",
  "2026-12-20:0047-276782",
  "2026-12-20:0047-276783",
  "2026-12-20:0047-276785",
  "2026-12-20:0047-276996",
  "2026-12-20:0047-276997",
  "2026-12-20:0047-276998",
  "2026-12-20:0047-276999",
  "2026-12-21:0047-276758",
  "2026-12-21:0047-276759",
  "2026-12-21:0047-276760",
  "2026-12-21:0047-276761",
  "2026-12-21:0047-276958",
  "2026-12-21:0047-276954",
  "2026-12-21:0047-276956",
  "2026-12-21:0047-276786",
  "2026-12-21:0047-276787",
  "2026-12-21:0047-276788",
  "2026-12-21:0047-276789",
  "2026-12-21:0047-276944",
  "2026-12-21:0047-276949",
  "2026-12-21:0047-276947",
  "2026-12-21:0047-276951",
  "2026-12-21:0047-276950",
  "2026-12-21:0047-277000",
  "2026-12-21:0047-277001",
  "2026-12-21:0047-277002",
  "2026-12-21:0047-277003",
  "2026-12-22:0047-276762",
  "2026-12-22:0047-276763",
  "2026-12-22:0047-276764",
  "2026-12-22:0047-276765",
  "2026-12-22:0047-276973",
  "2026-12-22:0047-276969",
  "2026-12-22:0047-276971",
  "2026-12-22:0047-276967",
  "2026-12-22:0047-276790",
  "2026-12-22:0047-276791",
  "2026-12-22:0047-276792",
  "2026-12-22:0047-276793",
  "2026-12-22:0047-276959",
  "2026-12-22:0047-276964",
  "2026-12-22:0047-276962",
  "2026-12-22:0047-276963",
  "2026-12-22:0047-277004",
  "2026-12-22:0047-277005",
  "2026-12-22:0047-277006",
  "2026-12-22:0047-277007",
  "2026-12-23:0047-276766",
  "2026-12-23:0047-276767",
  "2026-12-23:0047-276768",
  "2026-12-23:0047-276769",
  "2026-12-23:0047-276988",
  "2026-12-23:0047-276984",
  "2026-12-23:0047-276982",
  "2026-12-23:0047-276794",
  "2026-12-23:0047-276795",
  "2026-12-23:0047-276796",
  "2026-12-23:0047-276797",
  "2026-12-23:0047-276974",
  "2026-12-23:0047-276979",
  "2026-12-23:0047-276977",
  "2026-12-23:0047-276978",
  "2026-12-23:0047-277008",
  "2026-12-23:0047-277009",
  "2026-12-23:0047-277010",
  "2026-12-23:0047-277011",
  "2026-12-23:0047-276986",
  "2026-12-18:0047-276900",
  "2026-12-21:0047-276952",
  "2026-12-16:0047-276798",
  "2026-12-16:0047-276799",
  "2026-12-17:0047-276871",
  "2026-12-17:0047-276894"
];

function cleanText(value = "") {
  return value
    .replace(/<[^>]*>/g, " ")
    .replace(/&amp;/g, "&")
    .replace(/&#39;|&apos;/g, "'")
    .replace(/&quot;/g, '"')
    .replace(/&nbsp;/g, " ")
    .replace(/\s+/g, " ")
    .trim();
}

function normalize(value = "") {
  return cleanText(value).toLowerCase().replace(/&/g, " and ").replace(/[^a-z0-9]+/g, " ").trim();
}

function getMovieName(title, hall) {
  const t = normalize(title);
  const h = normalize(hall);

  if (t.includes("dune part three") || t.includes("dune part 3")) {
    return "Dune: Part Three";
  }

  if (t.includes("avengers doomsday")) {
    return (t.includes("infinity vision") || h.includes("infinity vision"))
      ? "Avengers: Doomsday (Infinity Vision)"
      : "Avengers: Doomsday";
  }

  return null;
}

function discoverDates(html) {
  const dates = new Set();
  const links = html.match(/<a\b[^>]*href=["'][^"']+["'][^>]*>/gi) || [];

  for (const tag of links) {
    const hrefMatch = tag.match(/href=["']([^"']+)["']/i);
    if (!hrefMatch) continue;

    try {
      const url = new URL(hrefMatch[1].replace(/&amp;/g, "&"), SHOWTIMES_URL);
      const date = url.searchParams.get("d");
      if (/^\d{8}$/.test(date || "")) dates.add(date);
    } catch {}
  }

  return [...dates].sort();
}

function extractSlots(html, date) {
  const slots = [];
  const articles = html.match(/<article\b[^>]*class=["'][^"']*\bmovie-compare\b[^"']*["'][^>]*>[\s\S]*?<\/article>/gi) || [];

  for (const article of articles) {
    const titleMatch = article.match(/<h2\b[^>]*>([\s\S]*?)<\/h2>/i);
    if (!titleMatch) continue;

    const title = cleanText(titleMatch[1]);
    if (!/dune\s+part\s+(three|3)|avengers\s+doomsday/i.test(title)) continue;

    const itemRegex = /<li\b[^>]*\bdata-id=["']([^"']+)["'][^>]*>([\s\S]*?)<\/li>/gi;
    let itemMatch;

    while ((itemMatch = itemRegex.exec(article)) !== null) {
      const bookingId = itemMatch[1].trim();
      const itemHtml = itemMatch[2];
      const linkMatch = itemHtml.match(/<a\b[^>]*class=["'][^"']*\bshowtime\b[^"']*["'][^>]*href=["']([^"']+)["'][^>]*>([\s\S]*?)<\/a>/i);
      if (!bookingId || !linkMatch) continue;

      const beforeItem = article.slice(0, itemMatch.index);
      const strongMatches = [...beforeItem.matchAll(/<strong\b[^>]*>([\s\S]*?)<\/strong>/gi)];
      const hall = strongMatches.length
        ? cleanText(strongMatches[strongMatches.length - 1][1])
        : "Standard";
      const movie = getMovieName(title, hall);
      if (!movie) continue;

      let bookingUrl;
      try {
        bookingUrl = new URL(linkMatch[1].replace(/&amp;/g, "&"), BASE_URL).href;
      } catch {
        continue;
      }

      if (!bookingUrl.startsWith(BASE_URL + "/booking/")) continue;

      slots.push({
        key: `${dateKey}:${bookingId}`,
        booking: bookingUrl,
        movie
      });
    }
  }

  return slots;
}

async function fetchShowtimes(date) {
  const url = date
    ? `${SHOWTIMES_URL}&d=${date}`
    : SHOWTIMES_URL;

  const response = await fetch(url, {
    headers: {
      "Accept": "text/html,application/xhtml+xml",
      "Accept-Language": "en-US,en;q=0.9",
      "User-Agent": "Mozilla/5.0 (compatible; VOXBookingMonitor/1.0)"
    },
    redirect: "follow"
  });

  if (!response.ok) {
    throw new Error(`VOX returned HTTP ${response.status} for ${date || "today"}`);
  }

  const html = await response.text();
  if (!html.includes("movie-compare")) {
    throw new Error(`VOX page markup was not found for ${date || "today"} (possible block or site change)`);
  }

  return extractSlots(html, date || new Date().toISOString().slice(0, 10));
}

async function sendTelegram(url, env) {
  const response = await fetch(`https://api.telegram.org/bot${env.TELEGRAM_BOT_TOKEN}/sendMessage`, {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify({
      chat_id: env.TELEGRAM_CHAT_ID,
      text: url,
      disable_web_page_preview: false
    })
  });

  const result = await response.json();
  if (!response.ok || !result.ok) {
    throw new Error(`Telegram send failed: ${JSON.stringify(result)}`);
  }
}

async function monitor(env) {
  if (!env.STATE) throw new Error("Missing STATE KV binding.");
  if (!env.TELEGRAM_BOT_TOKEN || !env.TELEGRAM_CHAT_ID) {
    throw new Error("Missing TELEGRAM_BOT_TOKEN or TELEGRAM_CHAT_ID secret.");
  }

  const saved = await env.STATE.get("seen", "json");
  const seen = new Set(Array.isArray(saved) ? saved : INITIAL_SEEN);

  // First request discovers all dates currently listed by VOX.
  const firstUrl = await fetch(SHOWTIMES_URL, {
    headers: {
      "Accept": "text/html,application/xhtml+xml",
      "Accept-Language": "en-US,en;q=0.9",
      "User-Agent": "Mozilla/5.0 (compatible; VOXBookingMonitor/1.0)"
    },
    redirect: "follow"
  });

  if (!firstUrl.ok) throw new Error(`VOX returned HTTP ${firstUrl.status} on the date index`);
  const indexHtml = await firstUrl.text();
  if (!indexHtml.includes("movie-compare")) {
    throw new Error("VOX date index did not contain showtime cards (possible 403 or markup change).");
  }

  const dates = discoverDates(indexHtml);
  const dateList = [null, ...dates];

  // Fetch all currently published dates in parallel so every date is checked each minute.
  const results = await Promise.allSettled(dateList.map(fetchShowtimes));
  const failed = [];
  const found = new Map();

  results.forEach((result, index) => {
    if (result.status === "fulfilled") {
      for (const slot of result.value) found.set(slot.key, slot);
    } else {
      failed.push({ date: dateList[index] || "today", error: String(result.reason) });
    }
  });

  if (failed.length === dateList.length) {
    throw new Error("All VOX date checks failed: " + JSON.stringify(failed));
  }

  let sent = 0;
  for (const slot of found.values()) {
    if (seen.has(slot.key)) continue;
    // Only record a slot after Telegram confirms delivery.
    await sendTelegram(slot.booking, env);
    seen.add(slot.key);
    sent++;
    console.log("New VOX booking link sent:", slot.booking);
  }

  if (sent > 0) {
    await env.STATE.put("seen", JSON.stringify([...seen]));
  }

  console.log(JSON.stringify({
    checkedAt: new Date().toISOString(),
    datesChecked: dateList.length,
    slotsFound: found.size,
    alertsSent: sent,
    failedDates: failed
  }));
}

export default {
  async scheduled(controller, env, ctx) {
    ctx.waitUntil(monitor(env));
  },

  async fetch(request, env) {
    const url = new URL(request.url);
    if (url.pathname === "/health") {
      return new Response("VOX monitor worker is deployed. Cron: every minute.", {
        headers: { "content-type": "text/plain; charset=utf-8" }
      });
    }
    return new Response("Not found", { status: 404 });
  }
};
