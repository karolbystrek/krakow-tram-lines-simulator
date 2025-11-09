import json
from pathlib import Path
from typing import List, Dict, Any

from playwright.sync_api import sync_playwright, Page, BrowserContext

TRAM_LINES_URL = "https://tomekzaw.pl/ttss/linie"
API_URL = "https://tomekzaw-ttss-gtfs.herokuapp.com/api/routes/"
BLOCKS_API_URL = "https://tomekzaw-ttss-gtfs.herokuapp.com/api/blocks/tram"
TRAM_SHAPES_GEOJSON_URL = "https://services-eu1.arcgis.com/svTzSt3AvH7sK6q9/arcgis/rest/services/Linie_KMK/FeatureServer/replicafilescache/Linie_KMK_7975846146257302888.geojson"
TRAM_STOPS_GEOJSON_URL = "https://services-eu1.arcgis.com/svTzSt3AvH7sK6q9/arcgis/rest/services/Przystanki_Komunikacji_Miejskiej_w_Krakowie/FeatureServer/replicafiles/Przystanki_Komunikacji_Miejskiej_w_Krakowie_a0e9215fd033414eb9f5f0d6d3ae21ab.geojson"
DATA_DIR = Path(__file__).parent / "data"
TRAM_LINES_DATA_DIR = DATA_DIR / "lines"
TRAM_SHAPES_DATA_DIR = DATA_DIR / "line-shapes"
TRAM_STOPS_DATA_DIR = DATA_DIR / "stops"


def _get_tram_line_numbers(page: Page) -> List[str]:
    page.goto(TRAM_LINES_URL)
    page.wait_for_selector("text=Linie tramwajowe dzienne")
    header = page.get_by_text("Linie tramwajowe dzienne")
    line_links = header.locator("xpath=..").locator("a")
    return [
        line_links.nth(i).inner_text().strip()
        for i in range(line_links.count())
        if line_links.nth(i).inner_text().strip()
    ]


def _fetch_line_api_data(context: BrowserContext, line_number: str) -> Dict[str, Any]:
    return context.request.fetch(f"{API_URL}{line_number}").json()


def _save_data_to_json(data: Dict[str, Any], file_path: Path):
    file_path.parent.mkdir(parents=True, exist_ok=True)
    with file_path.open("w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def fetch_tram_shapes_geojson(context: BrowserContext) -> None:
    output_file = TRAM_SHAPES_DATA_DIR / "krakow_tram_lines.geojson"
    _save_data_to_json(
        context.request.fetch(TRAM_SHAPES_GEOJSON_URL).json(), output_file
    )


def fetch_tram_stops_geojson(context: BrowserContext) -> None:
    output_file = TRAM_STOPS_DATA_DIR / "krakow_tram_stops.geojson"
    _save_data_to_json(
        context.request.fetch(TRAM_STOPS_GEOJSON_URL).json(), output_file
    )


def fetch_tram_data():
    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=True)
        context = browser.new_context()
        page = context.new_page()

        try:
            line_numbers = _get_tram_line_numbers(page)
            # Fetch line data, save to JSON files, and fetch block info
            for line_number in line_numbers:
                # Create directory for this line
                line_dir = TRAM_LINES_DATA_DIR / line_number

                # Fetch and save line data
                line_data = _fetch_line_api_data(context, line_number)
                _save_data_to_json(line_data, line_dir / f"{line_number}.json")

                # Parse blocks and fetch stop times for this line
                blocks = line_data.get("blocks", [])

                for block in blocks:
                    service_id = block["service_id"]
                    block_id = block["block_id"]

                    try:
                        url = f"{BLOCKS_API_URL}/{service_id}/{block_id}/stop_times"
                        stop_times_data = context.request.fetch(url).json()

                        # Save block stop times data in /{service_id}/ subdirectory
                        block_dir = line_dir / service_id
                        block_file = block_dir / f"{block_id}.json"
                        _save_data_to_json(stop_times_data, block_file)
                    except Exception as e:
                        print(f"Failed to fetch stop times for {block_id}: {e}")

            fetch_tram_shapes_geojson(context)
            fetch_tram_stops_geojson(context)
        finally:
            browser.close()


if __name__ == "__main__":
    fetch_tram_data()
