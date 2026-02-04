from playwright.sync_api import sync_playwright
import time
from bs4 import BeautifulSoup

HUMHUB_URL = "https://humhub.sizaf.com"
USERNAME = "humhub"
PASSWORD = "Humhub@2025"

def fetch_notifications():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)  # set False to debug
        context = browser.new_context()
        page = context.new_page()

        # 1️⃣ Open login page
        page.goto(f"{HUMHUB_URL}/user/auth/login", timeout=60000)

        # 2️⃣ Login
        page.fill('input[name="Login[username]"]', USERNAME)
        page.fill('input[name="Login[password]"]', PASSWORD)
        page.click('button[type="submit"]')

        # 3️⃣ Wait for dashboard
        page.wait_for_url("**/dashboard**", timeout=60000)
        time.sleep(5)  # let activity stream load

        # 4️⃣ Get fully-rendered HTML
        html = page.content()

        browser.close()
        return html


def parse_notifications(html):
    soup = BeautifulSoup(html, "html.parser")
    notifications = []

    for div in soup.select("div.flex-grow-1.text-break"):
        sender = div.find("strong")
        time_tag = div.find("time")

        if not sender or not time_tag:
            continue

        sender_name = sender.text.strip()
        full_text = div.get_text(" ", strip=True)
        message = full_text.replace(sender_name, "").strip()

        timestamp = time_tag["datetime"]

        notifications.append({
            "sender": sender_name,
            "message": message,
            "timestamp": timestamp
        })

    return notifications


if __name__ == "__main__":
    html = fetch_notifications()
    notes = parse_notifications(html)

    print("FOUND:", len(notes))
    for n in notes:
        print(n)
