import json
import os
import re
from datetime import datetime
from urllib.parse import parse_qs, urljoin, urlparse
from zoneinfo import ZoneInfo

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from bs4 import BeautifulSoup

BASE_URL = "https://egy.voxcinemas.com"
SHOWTIMES_URL = f"{BASE_URL}/showtimes"
COMING_SOON_URL = f"{BASE_URL}/movies/comingsoon"
CINEMA = "city-centre-almaza"
BRANCH = "City Centre Almaza"
STATE_FILE = "seen.json"

TOKEN = os.getenv("TOKEN") or os.getenv("TELEGRAM_BOT_TOKEN")
CHAT_ID = os.getenv("CHAT_ID") or os.getenv("TELEGRAM_CHAT_ID")
if not TOKEN or not CHAT_ID:
    raise RuntimeError("Missing Telegram secrets. Add TOKEN and CHAT_ID (or TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID).")

session = requests.Session()

# VOX can respond slowly or temporarily drop connections.
retry_policy = Retry(
    total=4,
    connect=4,
    read=4,
    status=3,
    backoff_factor=3,
    status_forcelist=(429, 500, 502, 503, 504),
    allowed_methods=frozenset(["GET"]),
    respect_retry_after_header=True,
)
adapter = HTTPAdapter(max_retries=retry_policy, pool_connections=10, pool_maxsize=10)
session.mount("https://", adapter)
session.mount("http://", adapter)

session.headers.update({
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/126.0 Safari/537.36",
    "Accept-Language": "en-US,en;q=0.9",
})


def get_soup(url, params=None):
    print(f"Requesting: {url}" + (f" | params={params}" if params else ""), flush=True)
    try:
        response = session.get(url, params=params, timeout=(20, 90))
        response.raise_for_status()
    except requests.exceptions.RequestException as error:
        print(f"VOX request failed after retries: {error}", flush=True)
        raise
    print(f"Received {len(response.content)} bytes from VOX.", flush=True)
    return BeautifulSoup(response.text, "html.parser")


def send_telegram(message):
    # Telegram text messages are limited to 4096 characters.
    if len(message) > 4000:
        message = message[:3950] + "\n…"
    response = session.post(
        f"https://api.telegram.org/bot{TOKEN}/sendMessage",
        data={"chat_id": CHAT_ID, "text": message, "disable_web_page_preview": True},
        timeout=25,
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


def extract_showtimes(soup, date):
    found = {}
    for article in soup.select("article.movie-compare"):
        heading = article.select_one("h2")
        if not heading:
            continue

        name = heading.get_text(" ", strip=True)
        slug = article.get("data-slug")
        if not slug:
            continue

        details = article.select_one("a.read-more[href]")
        movie_url = urljoin(BASE_URL, details["href"]) if details else SHOWTIMES_URL
        movie = found.setdefault(slug, {"name": name, "link": movie_url, "slots": {}})

        for group in article.select("ol.showtimes > li"):
            format_tag = group.find("strong")
            cinema_format = format_tag.get_text(" ", strip=True) if format_tag else "Standard"

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


def extract_coming_soon(soup):
    """Extract upcoming films without depending on one exact card class."""
    movies = {}

    for link in soup.select('a[href*="/movies/"]'):
        href = link.get("href", "")
        path = urlparse(href).path.rstrip("/")
        if not path or path in ("/movies/comingsoon", "/movies/whatson"):
            continue

        # Find a nearby card/container that contains the movie title and release date.
        container = link
        for _ in range(5):
            if container.parent and getattr(container.parent, "name", None):
                container = container.parent
            text = container.get_text(" ", strip=True)
            heading = container.find(["h1", "h2", "h3", "h4"])
            if heading and re.search(r"release\s*date", text, re.I):
                break

        heading = container.find(["h1", "h2", "h3", "h4"])
        if not heading:
            heading = link.find(["h1", "h2", "h3", "h4"])
        name = heading.get_text(" ", strip=True) if heading else link.get_text(" ", strip=True)
        if not name or len(name) > 180:
            continue

        text = container.get_text(" ", strip=True)
        match = re.search(
            r"Release\s*Date\s*:?\s*(.*?)(?=Starring\s*:|Language\s*:|View\s*Movie|$)",
            text,
            re.I,
        )
        release_date = re.sub(r"\s+", " ", match.group(1)).strip() if match else "Not announced"
        movie_url = urljoin(BASE_URL, href)
        slug = path.split("/")[-1]
        movies[slug] = {"name": name, "link": movie_url, "release_date": release_date}

    if not movies:
        raise RuntimeError("Coming Soon extraction returned zero films; refusing to overwrite saved state.")
    return movies


def load_state():
    if not os.path.exists(STATE_FILE):
        return {"initialized": False, "movies": {}, "coming_soon": {}}
    with open(STATE_FILE, "r", encoding="utf-8") as file:
        data = json.load(file)
    return {
        "initialized": bool(data.get("initialized", False)),
        "movies": data.get("movies", {}),
        "coming_soon": data.get("coming_soon", {}),
    }


def main():
    today = datetime.now(ZoneInfo("Africa/Cairo")).strftime("%Y%m%d")
    print(f"VOX monitor started — {BRANCH} — {today}")

    first_page = get_soup(SHOWTIMES_URL, {"c": CINEMA, "d": today})
    dates = get_available_dates(first_page, today)
    current_movies = {}

    for date in dates:
        print(f"Checking showtimes for {date}")
        page = first_page if date == today else get_soup(
            SHOWTIMES_URL, {"c": CINEMA, "d": date}
        )
        for slug, movie in extract_showtimes(page, date).items():
            item = current_movies.setdefault(
                slug, {"name": movie["name"], "link": movie["link"], "slots": {}}
            )
            item["slots"].update(movie["slots"])

    if not current_movies:
        raise RuntimeError("No showtimes found for City Centre Almaza; refusing to overwrite saved state.")

    print("Checking Coming Soon page")
    current_coming = extract_coming_soon(get_soup(COMING_SOON_URL))
    print(f"Found {len(current_movies)} movies with showtimes and {len(current_coming)} coming-soon movies.")

    old = load_state()
    old_movies = old["movies"]
    old_coming = old["coming_soon"]

    if not old["initialized"]:
        print("First successful run: creating baseline; no notifications will be sent.")
    else:
        for slug, movie in current_coming.items():
            if slug not in old_coming:
                send_telegram(
                    "🎬 فيلم جديد في Coming Soon!\n\n"
                    f"🍿 {movie['name']}\n"
                    f"📅 Release: {movie['release_date']}\n"
                    f"🔗 {movie['link']}"
                )

        for slug, movie in current_movies.items():
            previous = old_movies.get(slug, {})
            old_slots = set(previous.get("slots", {}))
            new_slots = set(movie["slots"]) - old_slots

            if slug not in old_movies and not old_slots:
                print(f"New showtime listing: {movie['name']}")

            for key in sorted(new_slots):
                slot = movie["slots"][key]
                send_telegram(
                    "🆕 موعد عرض/حجز جديد!\n\n"
                    f"🎬 {movie['name']}\n"
                    f"📍 {BRANCH}\n"
                    f"📅 {slot['date']}\n"
                    f"🕒 {slot['time']}\n"
                    f"🎥 {slot['format']}\n\n"
                    f"🎟️ احجز الآن:\n{slot['booking']}"
                )

    # Preserve previously seen slots so a temporarily missing date does not cause repeat alerts.
    merged_movies = {}
    for slug, movie in current_movies.items():
        previous_slots = old_movies.get(slug, {}).get("slots", {})
        merged_movies[slug] = {
            "name": movie["name"],
            "link": movie["link"],
            "slots": {**previous_slots, **movie["slots"]},
        }

    state = {
        "initialized": True,
        "movies": merged_movies,
        "coming_soon": current_coming,
        "updated_at": datetime.now(ZoneInfo("Africa/Cairo")).isoformat(),
    }
    with open(STATE_FILE, "w", encoding="utf-8") as file:
        json.dump(state, file, ensure_ascii=False, indent=2)

    print("Monitoring completed successfully.")


if __name__ == "__main__":
    main()
