"""Configuration and path management for the backend application"""
from pathlib import Path

# Base directory for the app
APP_DIR = Path(__file__).resolve().parent

# Data directory
DATA_DIR = APP_DIR / "data"

# Data subdirectories
TRAM_SHAPES_DATA_DIR = DATA_DIR / "line-shapes"
TRAM_STOPS_DATA_DIR = DATA_DIR / "stops"
TRAM_LINES_DATA_DIR = DATA_DIR / "lines"

# GeoJSON file paths
GEOJSON_SHAPES_PATH = TRAM_SHAPES_DATA_DIR / "krakow_tram_lines.geojson"
GEOJSON_STOPS_PATH = TRAM_STOPS_DATA_DIR / "krakow_tram_stops.geojson"

