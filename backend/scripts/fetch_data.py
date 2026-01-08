import json
import time
from pathlib import Path
from typing import List, Dict, Any

import httpx

from backend.app.config import (
    TRAM_LINE_SHAPES_DIR,
    TRAM_STOPS_DIR,
    TRAM_LINES_DIR,
)

ROUTES_URL = "https://tomekzaw-ttss-gtfs.herokuapp.com/api/routes"
BLOCKS_URL = "https://tomekzaw-ttss-gtfs.herokuapp.com/api/blocks/tram"
LINE_SHAPES_URL = "https://services-eu1.arcgis.com/svTzSt3AvH7sK6q9/arcgis/rest/services/Linie_KMK/FeatureServer/replicafilescache/Linie_KMK_7975846146257302888.geojson"
STOPS_URL = "https://services-eu1.arcgis.com/svTzSt3AvH7sK6q9/ArcGIS/rest/services/Przystanki_Komunikacji_Miejskiej_w_Krakowie/FeatureServer/0/query?where=1%3D1&outFields=*&f=geojson"


def _get_tram_line_numbers() -> List[str]:
    print(f"Fetching routes from {ROUTES_URL}...")
    try:
        resp = httpx.get(ROUTES_URL, timeout=10.0)
        resp.raise_for_status()
        data = resp.json()
        for group in data.get("groups", []):
            if group.get("group_name") == "Linie tramwajowe dzienne":
                return group.get("route_short_names", [])
    except Exception as e:
        print(f"Error fetching route list: {e}")
    return []


def _fetch_line_api_data(line_number: str) -> Dict[str, Any]:
    resp = httpx.get(f"{ROUTES_URL}/{line_number}", timeout=10.0)
    resp.raise_for_status()
    return resp.json()


def _save_data_to_json(data: Dict[str, Any], file_path: Path):
    file_path.parent.mkdir(parents=True, exist_ok=True)
    with file_path.open("w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def fetch_tram_shapes_geojson() -> None:
    output_file = TRAM_LINE_SHAPES_DIR / "krakow_tram_lines.geojson"
    try:
        print("Fetching tram shapes...")
        resp = httpx.get(LINE_SHAPES_URL, timeout=10.0, follow_redirects=True)
        resp.raise_for_status()
        _save_data_to_json(resp.json(), output_file)
        print(f"Fetched tram route shapes geojson")
    except Exception as e:
        print(f"Error fetching shapes: {e}")


def fetch_tram_stops_geojson() -> None:
    output_file = TRAM_STOPS_DIR / "krakow_tram_stops.geojson"
    try:
        print("Fetching tram stops...")
        resp = httpx.get(STOPS_URL, timeout=10.0)
        resp.raise_for_status()
        _save_data_to_json(resp.json(), output_file)
        print(f"Fetched tram stops geojson")
    except Exception as e:
        print(f"Failed to fetch stops: {e}")
        return


def fetch_tram_data():
    line_numbers = _get_tram_line_numbers()
    if not line_numbers:
        print("No tram lines found or error fetching list.")
        return

    for line_number in line_numbers:
        line_dir = TRAM_LINES_DIR / line_number

        try:
            line_data = _fetch_line_api_data(line_number)
            _save_data_to_json(line_data, line_dir / f"{line_number}.json")
            print(f"Fetched line data for {line_number}")

            blocks = line_data.get("blocks", [])

            for block in blocks:
                service_id = block["service_id"]
                block_id = block["block_id"]

                try:
                    url = f"{BLOCKS_URL}/{service_id}/{block_id}/stop_times"
                    resp = httpx.get(url, timeout=10.0)
                    resp.raise_for_status()
                    stop_times_data = resp.json()

                    print(
                        f"Fetched stop times for block {block_id} of line {line_number}"
                    )

                    block_file = line_dir / service_id / f"{block_id}.json"
                    _save_data_to_json(stop_times_data, block_file)
                except Exception as e:
                    print(f"Failed to fetch stop times for {block_id}: {e}")

            time.sleep(0.1)

        except Exception as e:
            print(f"Error processing line {line_number}: {e}")

    fetch_tram_shapes_geojson()
    fetch_tram_stops_geojson()


if __name__ == "__main__":
    fetch_tram_data()
