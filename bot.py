import json
import os
import re
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from urllib.parse import parse_qs, urljoin, urlparse
from zoneinfo import ZoneInfo

import requests
from bs4 import BeautifulSoup
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

BASE_URL = "https://egy.voxcinemas.com"
SHOWTIMES_URL = f"{BASE_URL}/showtimes"
CINEMA = "city-centre-almaza"
BRANCH = "City Centre Almaza"
STATE_FILE = "seen.json"

# Only alert for these three movie versions.
TARGET_MOVIES = {
    "dune part three",
    "avengers doomsday",
    "avengers doomsday infinity vision",
}

TOKEN = os.getenv("TOKEN") or os.getenv("TELEGRAM_BOT_TOKEN")
CHAT_ID = os.getenv("CHAT_ID") or os.getenv("TELEGRAM_CHAT_ID")
if not TOKEN or not CHAT_ID:
    raise RuntimeError(
        "Missing Telegram secrets. Add TOKEN and CHAT_ID "
        "(or TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID)."
    )

session = requests.Session()
# Fail quickly. The workflow runs every five minutes, so the next run can retry.
retry_policy = Retry(
    total=0,
    connect=0,
    read=0,
    status=0,
    allowed_methods=frozenset(["GET"]),
)
adapter = HTTPAdapter(max_retries=retry_policy)
session.mount("https://", adapter)
session.mount("http://", adapter)
session.headers.update({
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 Chrome/126.0 Safari/537.36"
    ),
    "Accept-Language": "en-US,en;q=0.9",
    "Cache-Control": "no-cache",
})


def normalize_title(value):
    value = value.lower().replace("&", " and ")
    return re.sub(r"[^a-z0-9]+", " ", value).strip()


def get_soup(url, params=None):
    print(
        f"Requesting: {url}" + (f" | params={params}" if params else ""),
        flush=True,
    )
    response = session.get(url, params=params, timeout=(6, 18))
    response.raise_for_status()
    print(f"Received {len(response.content)} bytes from VOX.", flush=True)
    return BeautifulSoup(response.text, "html.parser")


def send_telegram(message):
    if len(message) > 4000:
        message = message[:3950] + "\n…"
    response = session.post(
        f"https://api.telegram.org/bot{TOKEN}/sendMessage",
        data={
            "chat_id": CHAT_ID,
            "text": message,
            "disable_web_page_preview": True,
        },
        timeout=(6, 15),
    )
    response.raise_for_status()
    payload = response.json()
    if not payload.get("ok"):
        raise RuntimeError(f"Telegram API error: {payload}")


def get_available_dates(soup, today):
    dates = {today}
    for link in soup.select("a[href]"):
        query = parse_qs(urlparse(link.get("href", "")).query)
        for value in query.get("d", []):
            if re.fullmatch(r"\d{8}", value):
                dates.add(value)
    return sorted(dates)


def extract_target_showtimes(soup, date):
    found = {}

    for article in soup.select("article.movie-compare"):
        heading = article.select_one("h2")
        if not heading:
            continue

        name = heading.get_text(" ", strip=True)
        normalized = normalize_title(name)
        if normalized not in TARGET_MOVIES:
            continue

        slug = article.get("data-slug") or normalized.replace(" ", "-")
        details = article.select_one("a.read-more[href]")
        movie_url = urljoin(BASE_URL, details["href"]) if details else SHOWTIMES_URL
        movie = found.setdefault(
            slug, {"name": name, "link": movie_url, "slots": {}}
        )

        for group in article.select("ol.showtimes > li"):
            format_tag = group.find("strong")
            cinema_format = (
                format_tag.get_text(" ", strip=True) if format_tag else "Standard"
            )

            for link in group.select("a.showtime[href]"):
                slot_id = link.get("data-id")
                if not slot_id:
                    continue

                key = f"{date}_{slot_id}"
                movie["slots"][key] = {
                    "date": date,
                    "time": link.get_text(" ", strip=True),
                    "format": cinema_format,
                    "booking": urljoin(BASE_URL, link["href"]),
                }

    return found


def load_state():
    if not os.path.exists(STATE_FILE):
        return {"initialized": False, "movies": {}}

    with open(STATE_FILE, "r", encoding="utf-8") as file:
        data = json.load(file)

    return {
        "initialized": bool(data.get("initialized", False)),
        "movies": data.get("movies", {}),
    }


def main():
    today = datetime.now(ZoneInfo("Africa/Cairo")).strftime("%Y%m%d")
    print(
        f"VOX booking monitor started — {BRANCH} — {today}",
        flush=True,
    )
    print("Targets: Dune: Part Three; Avengers: Doomsday; Avengers: Doomsday (Infinity Vision)", flush=True)

    old = load_state()
    old_movies = old["movies"]

    # The current date page also provides links to the upcoming showtime dates.
    first_page = get_soup(
        SHOWTIMES_URL,
        {"c": CINEMA, "d": today},
    )

    page_text = first_page.get_text(" ", strip=True).lower()
    if "view times and book" not in page_text or "city centre almaza" not in page_text:
        raise RuntimeError(
            "VOX page did not contain the expected cinema/showtimes content; "
            "saved state was not changed."
        )

    dates = get_available_dates(first_page, today)
    print(f"Dates discovered: {', '.join(dates)}", flush=True)

    scraped_movies = {}
    failed_dates = []

    def fetch_date(date):
        page = first_page if date == today else get_soup(
            SHOWTIMES_URL, {"c": CINEMA, "d": date}
        )
        return date, extract_target_showtimes(page, date)

    # Check dates concurrently so a long list of future dates does not delay alerts.
    with ThreadPoolExecutor(max_workers=4) as executor:
        futures = {executor.submit(fetch_date, date): date for date in dates}
        for future in as_completed(futures):
            date = futures[future]
            try:
                _, day_movies = future.result()
                for slug, movie in day_movies.items():
                    item = scraped_movies.setdefault(
                        slug,
                        {"name": movie["name"], "link": movie["link"], "slots": {}},
                    )
                    item["slots"].update(movie["slots"])
            except requests.exceptions.RequestException as error:
                failed_dates.append(date)
                print(f"WARNING: Could not check {date}: {error}", flush=True)

    print(
        f"Target movies found: {len(scraped_movies)}; "
        f"slots found: {sum(len(m['slots']) for m in scraped_movies.values())}",
        flush=True,
    )
    if failed_dates:
        print(
            "WARNING: Some dates could not be checked: " + ", ".join(sorted(failed_dates)),
            flush=True,
        )

    # An empty result is valid: it means these films do not have bookable slots yet.
    if not old["initialized"]:
        print(
            "Creating first baseline. Any slots already visible now will not trigger alerts.",
            flush=True,
        )
    else:
        for slug, movie in scraped_movies.items():
            previous = old_movies.get(slug, {})
            old_slots = set(previous.get("slots", {}))
            new_slots = set(movie["slots"]) - old_slots

            for key in sorted(new_slots):
                slot = movie["slots"][key]
                send_telegram(
                    "🚨 NEW VOX BOOKING AVAILABLE!\n\n"
                    f"🎬 {movie['name']}\n"
                    f"📍 {BRANCH}\n"
                    f"📅 {slot['date']}\n"
                    f"🕒 {slot['time']}\n"
                    f"🎥 {slot['format']}\n\n"
                    f"🎟️ BOOK NOW:\n{slot['booking']}"
                )
                print(f"Telegram alert sent: {movie['name']} — {slot['date']} {slot['time']}", flush=True)

    # Keep old slots too, so a slot disappearing and later reappearing is not
    # mistaken for a brand-new booking.
    merged_movies = dict(old_movies)
    for slug, movie in scraped_movies.items():
        previous_slots = old_movies.get(slug, {}).get("slots", {})
        merged_movies[slug] = {
            "name": movie["name"],
            "link": movie["link"],
            "slots": {**previous_slots, **movie["slots"]},
        }

    state = {
        "initialized": True,
        "movies": merged_movies,
        "updated_at": datetime.now(ZoneInfo("Africa/Cairo")).isoformat(),
    }
    with open(STATE_FILE, "w", encoding="utf-8") as file:
        json.dump(state, file, ensure_ascii=False, indent=2)

    if failed_dates:
        print("Monitoring completed with warnings; failed dates will be retried next run.", flush=True)
    else:
        print("Monitoring completed successfully.", flush=True)


if __name__ == "__main__":
    main()
