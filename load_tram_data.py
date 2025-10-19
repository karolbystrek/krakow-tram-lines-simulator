import re
import json

from playwright.sync_api import sync_playwright


TRAM_LINES_URL = "https://tomekzaw.pl/ttss/linie"
API_URL = "https://tomekzaw-ttss-gtfs.herokuapp.com/api/routes/"

with sync_playwright() as pw:
    browser = pw.chromium.launch(headless=True)
    context = browser.new_context()
    page = context.new_page()

    page.goto(TRAM_LINES_URL)
    page.wait_for_selector("text=Linie tramwajowe dzienne")

    header = page.get_by_text("Linie tramwajowe dzienne")
    parent = header.locator("xpath=..")
    lines = parent.locator("a")

    for line_index in range(lines.count()):
        link = lines.nth(line_index)
        line_number = link.inner_text().strip()

        if not line_number:
            continue

        response = context.request.fetch(f"{API_URL}{line_number}")

        line_data = response.json()

        with open(f"data/{line_number}.json", "w", encoding="utf-8") as f:
            json.dump(line_data, f, ensure_ascii=False, indent=2)
