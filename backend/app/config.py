from pathlib import Path

DATA_DIR = Path(__file__).resolve().parent / "data"

TRAM_LINE_SHAPES_DIR = DATA_DIR / "line-shapes"
TRAM_STOPS_DIR = DATA_DIR / "stops"
TRAM_LINES_DIR = DATA_DIR / "lines"

GEOJSON_LINE_SHAPES_PATH = TRAM_LINE_SHAPES_DIR / "krakow_tram_lines.geojson"
GEOJSON_STOPS_PATH = TRAM_STOPS_DIR / "krakow_tram_stops.geojson"
