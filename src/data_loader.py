import json
from typing import Dict, Tuple, List

from src.models import Stop, Shape, TramLine, Trip, Tram
from src.fetch_tram_data import TRAM_SHAPES_DATA_DIR, TRAM_STOPS_DATA_DIR, TRAM_LINES_DATA_DIR

GEOJSON_SHAPES_PATH = TRAM_SHAPES_DATA_DIR / "krakow_tram_lines.geojson"
GEOJSON_STOPS_PATH = TRAM_STOPS_DATA_DIR / "krakow_tram_stops.geojson"


def load_shapes_from_geojson() -> Dict[str, list[Shape]]:
    if not GEOJSON_SHAPES_PATH.exists():
        print(f"Warning: GeoJSON file not found at {GEOJSON_SHAPES_PATH}")
        return {}

    with open(GEOJSON_SHAPES_PATH, "r", encoding="utf-8") as f:
        geojson_data = json.load(f)

    shapes_by_line = {}
    for feature in geojson_data.get("features", []):
        line_number = str(feature["properties"]["Numer"])
        geometry = feature.get("geometry", {})

        if geometry.get("type") == "LineString":
            coordinates = [(c[1], c[0]) for c in geometry.get("coordinates", [])]
            shapes_by_line.setdefault(line_number, []).append(
                Shape(coordinates=coordinates)
            )

    return shapes_by_line


def load_tram_stops() -> Dict[str, Stop]:
    if not GEOJSON_STOPS_PATH.exists():
        print(f"Warning: Tram stops GeoJSON file not found at {GEOJSON_STOPS_PATH}")
        return {}

    with open(GEOJSON_STOPS_PATH, "r", encoding="utf-8") as f:
        geojson_data = json.load(f)

    stops_dict = {}
    for feature in geojson_data.get("features", []):
        properties = feature.get("properties", {})
        coordinates = feature.get("geometry", {}).get("coordinates", [])
        kod_busman = properties.get("kod_busman", "")

        stops_dict[kod_busman] = Stop(
            id=str(properties.get("OBJECTID", "")),
            name=properties.get("Nazwa_przystanku_nr", ""),
            lat=coordinates[1],
            lon=coordinates[0],
            kod_busman=kod_busman,
        )

    print(f"Loaded {len(stops_dict)} tram stops from GeoJSON")
    return stops_dict


def load_tram_lines() -> Dict[str, TramLine]:
    geojson_shapes = load_shapes_from_geojson()
    tram_lines = {
        line_number: TramLine(line_number=line_number, stops={}, shapes=shapes)
        for line_number, shapes in geojson_shapes.items()
    }
    print(f"Loaded {len(tram_lines)} tram lines from GeoJSON")
    return tram_lines


def load_trams() -> List[Tram]:
    trams: List[Tram] = []
    tram_lines = load_tram_lines()

    if not TRAM_LINES_DATA_DIR.exists():
        print(f"Warning: Tram lines data dir not found at {TRAM_LINES_DATA_DIR}")
        return trams

    for fp in sorted(TRAM_LINES_DATA_DIR.glob("*.json")):
        try:
            with open(fp, "r", encoding="utf-8") as f:
                data = json.load(f)
            line_number = fp.stem
        except Exception as e:
            print(f"Failed to load {fp.name}: {e}")
            continue


        tram_line = tram_lines.get(line_number)
        if not tram_line:
            print(f"Warning: No tram line data found for line {line_number}")
            continue

        for block in data.get("blocks", []):
            block_id = block.get("block_id", "")
            route_names = block.get("route_short_names") or []
            direction = route_names[0] if route_names else ""
            vehicles = block.get("vehicles_on_block", []) or []

            for v in vehicles:
                kmk = v.get("kmk_id")
                if not kmk:
                    continue
                trip = Trip(trip_id=block_id, direction=direction)
                tram = Tram(
                    tram_id=kmk,
                    line=tram_line,
                    current_trip=trip,
                    position=None,
                    status="ACTIVE"
                )
                trams.append(tram)

    print(f"Loaded {len(trams)} Tram objects from {TRAM_LINES_DATA_DIR}")
    return trams

def get_bounding_box(
    tram_lines: Dict[str, TramLine],
) -> Tuple[float, float, float, float]:
    default = (50.0614, 50.0614, 19.9366, 19.9366)
    if not tram_lines:
        return default

    all_coords = []
    for line in tram_lines.values():
        all_coords.extend(line.get_all_coordinates())
        all_coords.extend((stop.lat, stop.lon) for stop in line.stops.values())

    if not all_coords:
        return default

    lats, lons = zip(*all_coords)
    return (min(lats), max(lats), min(lons), max(lons))
