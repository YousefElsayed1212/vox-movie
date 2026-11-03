import html
import json
import os
import re
import time
from datetime import datetime
from urllib.parse import urljoin
from zoneinfo import ZoneInfo

import requests
from selenium import webdriver
from selenium.common.exceptions import TimeoutException, WebDriverException
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait

BASE_URL = "https://egy.voxcinemas.com"
VOX_BASE_URL = f"{BASE_URL}/showtimes?c=city-centre-almaza"
BRANCH = "City Centre Almaza"
STATE_FILE = "seen.json"
EGYPT_TZ = ZoneInfo("Africa/Cairo")

TOKEN = (
    os.getenv("TOKEN")
    or os.getenv("TELEGRAM_BOT_TOKEN")
    or os.getenv("TELEGRAM_TOKEN")
)
CHAT_ID = (
    os.getenv("CHAT_ID")
    or os.getenv("TELEGRAM_CHAT_ID")
)
if not TOKEN or not CHAT_ID:
    raise RuntimeError("Missing Telegram secrets: TOKEN/CHAT_ID or TELEGRAM_BOT_TOKEN/TELEGRAM_CHAT_ID.")

TARGET_DUNE = "dune part three"
TARGET_AVENGERS = "avengers doomsday"


def normalize(value):
    value = (value or "").lower().replace("&", " and ")
    return re.sub(r"[^a-z0-9]+", " ", value).strip()


def now_egypt():
    return datetime.now(EGYPT_TZ)


def today_egypt():
    return now_egypt().date()


def date_label(target_date):
    difference = (target_date - today_egypt()).days
    if difference == 0:
        return "Today"
    if difference == 1:
        return "Tomorrow"
    return target_date.strftime("%a %d %b")


def url_for_date(target_date):
    if target_date == today_egypt():
        return VOX_BASE_URL
    return f"{VOX_BASE_URL}&d={target_date.strftime('%Y%m%d')}"


def new_browser():
    options = Options()
    options.add_argument("--headless=new")
    options.add_argument("--disable-gpu")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--window-size=1920,1080")
    options.add_argument("--disable-blink-features=AutomationControlled")
    options.add_argument(
        "user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"
    )
    driver = webdriver.Chrome(options=options)
    driver.set_page_load_timeout(35)
    return driver


def save_debug_snapshot(driver, label):
    try:
        driver.save_screenshot(f"debug_vox_{label}.png")
        with open(f"debug_vox_{label}.html", "w", encoding="utf-8") as file:
            file.write(driver.page_source)
        print(f"Saved debug snapshot: debug_vox_{label}.html/png", flush=True)
    except Exception as error:
        print(f"Could not save debug snapshot: {error}", flush=True)


def load_vox_page(driver, url, attempts=2):
    for attempt in range(1, attempts + 1):
        try:
            print(f"Opening VOX page (attempt {attempt}/{attempts}): {url}", flush=True)
            driver.get(url)
            WebDriverWait(driver, 25).until(
                EC.presence_of_element_located(
                    (By.CSS_SELECTOR, "article.movie-compare")
                )
            )
            print("VOX showtime cards loaded in Chrome.", flush=True)
            return True
        except (TimeoutException, WebDriverException) as error:
            print(f"VOX page attempt {attempt} failed: {type(error).__name__}: {error}", flush=True)
            if attempt < attempts:
                time.sleep(3)
    return False


def discover_open_dates(driver):
    dates = {today_egypt()}
    links = driver.find_elements(By.CSS_SELECTOR, "nav.date-filter li a[href]")
    for link in links:
        href = link.get_attribute("href") or ""
        match = re.search(r"[?&]d=(\d{8})", href)
        if match:
            try:
                dates.add(datetime.strptime(match.group(1), "%Y%m%d").date())
            except ValueError:
                pass
    return sorted(dates)


def target_kind(title, hall_name):
    normalized_title = normalize(title)
    normalized_hall = normalize(hall_name)

    # Match the movie title independently from the auditorium/format.
    # Every showtime for either target movie is monitored, including MAX,
    # IMAX, Standard, and any newly introduced format.
    if TARGET_DUNE in normalized_title or "dune part 3" in normalized_title:
        return "Dune: Part Three"

    if TARGET_AVENGERS in normalized_title:
        # Infinity Vision may be shown in the movie title or hall label,
        # depending on how VOX renders the listing.
        if "infinity vision" in normalized_title or "infinity vision" in normalized_hall:
            return "Avengers: Doomsday (Infinity Vision)"
        return "Avengers: Doomsday"

    return None


def extract_target_slots(driver, target_date):
    slots = {}
    articles = driver.find_elements(By.CSS_SELECTOR, "article.movie-compare")

    for article in articles:
        title_elements = article.find_elements(By.TAG_NAME, "h2")
        if not title_elements:
            continue
        title = title_elements[0].text.strip()
        if TARGET_DUNE not in normalize(title) and "dune part 3" not in normalize(title) and TARGET_AVENGERS not in normalize(title):
            continue

        info_elements = article.find_elements(By.CSS_SELECTOR, "a.read-more")
        info_url = info_elements[0].get_attribute("href") if info_elements else ""

        hall_groups = article.find_elements(
            By.CSS_SELECTOR, "div.dates ol.showtimes > li"
        )
        for hall in hall_groups:
            strong_elements = hall.find_elements(By.TAG_NAME, "strong")
            hall_name = strong_elements[0].text.strip() if strong_elements else "Standard"

            kind = target_kind(title, hall_name)
            if not kind:
                continue

            time_items = hall.find_elements(By.CSS_SELECTOR, "ol > li")
            for item in time_items:
                booking_id = item.get_attribute("data-id") or ""
                link_elements = item.find_elements(By.CSS_SELECTOR, "a.showtime")
                if not booking_id or not link_elements:
                    continue

                time_text = link_elements[0].text.strip()
                booking_url = link_elements[0].get_attribute("href") or ""
                if not time_text or not booking_url:
                    continue

                key = f"{target_date.isoformat()}:{booking_id}"
                slots[key] = {
                    "key": key,
                    "movie": kind,
                    "listed_title": title,
                    "hall": hall_name,
                    "date": target_date.isoformat(),
                    "day": date_label(target_date),
                    "time": time_text,
                    "booking": urljoin(BASE_URL, booking_url),
                    "movie_info": urljoin(BASE_URL, info_url) if info_url else "",
                }

    return slots


def load_state():
    if not os.path.exists(STATE_FILE):
        return {"initialized": False, "slots": {}}

    with open(STATE_FILE, "r", encoding="utf-8") as file:
        data = json.load(file)

    # Convert the earlier nested seen.json format, if one exists.
    slots = data.get("slots", {})
    if not slots and isinstance(data.get("movies"), dict):
        for movie in data["movies"].values():
            for key, old_slot in movie.get("slots", {}).items():
                slots[key] = old_slot

    return {
        "initialized": bool(data.get("initialized", False)),
        "slots": slots,
    }


def send_telegram(message, booking_url):
    payload = {
        "chat_id": CHAT_ID,
        "text": message,
        "disable_web_page_preview": True,
        "reply_markup": {
            "inline_keyboard": [[
                {"text": "🎟️ احجز الآن", "url": booking_url}
            ]]
        },
    }
    response = requests.post(
        f"https://api.telegram.org/bot{TOKEN}/sendMessage",
        json=payload,
        timeout=(8, 20),
    )
    response.raise_for_status()
    result = response.json()
    if not result.get("ok"):
        raise RuntimeError(f"Telegram API returned an error: {result}")


def alert_message(slot):
    return (
        "🚨 NEW VOX BOOKING AVAILABLE!\n\n"
        f"🎬 {slot['movie']}\n"
        f"📍 {BRANCH}\n"
        f"📅 {slot['day']} ({slot['date']})\n"
        f"🕒 {slot['time']}\n"
        f"🎥 {slot['hall']}\n\n"
        "🎟️ Booking link is attached below."
    )


def main():
    today = today_egypt()
    print(
        f"VOX booking monitor started — {BRANCH} — {today.strftime('%Y%m%d')}",
        flush=True,
    )
    print(
        "Targets: Dune: Part Three; Avengers: Doomsday; "
        "Avengers: Doomsday (Infinity Vision)",
        flush=True,
    )

    old = load_state()
    driver = new_browser()
    scraped_slots = {}
    failed_dates = []

    try:
        if not load_vox_page(driver, url_for_date(today)):
            save_debug_snapshot(driver, "today")
            raise RuntimeError(
                "VOX did not render showtime cards in headless Chrome. "
                "Debug snapshots were saved; state was not changed."
            )

        dates = discover_open_dates(driver)
        print(
            "Dates currently open for booking: "
            + ", ".join(date.isoformat() for date in dates),
            flush=True,
        )

        for target_date in dates:
            if target_date != today:
                url = url_for_date(target_date)
                if not load_vox_page(driver, url):
                    failed_dates.append(target_date.isoformat())
                    save_debug_snapshot(driver, target_date.isoformat())
                    continue

            day_slots = extract_target_slots(driver, target_date)
            scraped_slots.update(day_slots)
            print(
                f"{target_date}: found {len(day_slots)} target booking slot(s).",
                flush=True,
            )
            time.sleep(1)

    finally:
        driver.quit()

    print(f"Total target slots found: {len(scraped_slots)}", flush=True)
    if failed_dates:
        print(
            "Some dates could not be checked and will be retried next run: "
            + ", ".join(failed_dates),
            flush=True,
        )

    if not old["initialized"]:
        if failed_dates:
            print(
                "Baseline not finalized because some dates failed. "
                "A complete scan is required before alerts are enabled.",
                flush=True,
            )
        else:
            print(
                "Creating initial baseline. Existing slots will not trigger alerts.",
                flush=True,
            )
    else:
        for key, slot in sorted(scraped_slots.items()):
            if key in old["slots"]:
                continue
            send_telegram(alert_message(slot), slot["booking"])
            print(
                f"Telegram alert sent: {slot['movie']} | {slot['date']} | "
                f"{slot['time']} | {slot['hall']}",
                flush=True,
            )

    # Preserve previously known slots if a date could not be checked.
    merged_slots = dict(old["slots"])
    merged_slots.update(scraped_slots)

    initialized = old["initialized"] or not failed_dates
    state = {
        "initialized": initialized,
        "slots": merged_slots,
        "updated_at": now_egypt().isoformat(),
    }
    with open(STATE_FILE, "w", encoding="utf-8") as file:
        json.dump(state, file, ensure_ascii=False, indent=2)

    if failed_dates:
        print("Monitoring completed with warnings.", flush=True)
    else:
        print("Monitoring completed successfully.", flush=True)


if __name__ == "__main__":
    main()
