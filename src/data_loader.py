import json
from typing import Dict, Tuple, List
from datetime import time

from src.models import Stop, Shape, TramLine, Trip, StopTime, TramBlock
from src.fetch_tram_data import (
    TRAM_SHAPES_DATA_DIR,
    TRAM_STOPS_DATA_DIR,
    TRAM_LINES_DATA_DIR,
)

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

    return stops_dict


def load_tram_lines() -> Dict[str, TramLine]:
    geojson_shapes = load_shapes_from_geojson()
    tram_lines = {
        line_number: TramLine(line_number=line_number, stops={}, shapes=shapes)
        for line_number, shapes in geojson_shapes.items()
    }
    return tram_lines


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


def parse_time_string(time_str: str) -> time:
    """Parse time string in format HH:MM:SS to time object"""
    parts = time_str.split(":")
    hour = int(parts[0])
    minute = int(parts[1])
    second = int(parts[2])

    # Handle times >= 24:00:00 (next day)
    if hour >= 24:
        hour = hour % 24

    return time(hour, minute, second)


def load_tram_blocks(service: str = "service_1") -> Dict[str, List[TramBlock]]:
    """Load and process tram schedule data for all lines and blocks in a service."""
    if not TRAM_LINES_DATA_DIR.exists():
        print(f"Warning: Lines data directory not found at {TRAM_LINES_DATA_DIR}")
        return {}

    blocks_by_line: Dict[str, List[TramBlock]] = {}

    # Scan all line directories
    for line_dir in TRAM_LINES_DATA_DIR.iterdir():
        if not line_dir.is_dir():
            continue

        line_number = line_dir.name
        service_dir = line_dir / service

        if not service_dir.exists():
            continue

        # Get all block files for this line
        block_files = sorted(service_dir.glob("block_*.json"))
        if not block_files:
            continue

        line_blocks = []

        for block_path in block_files:
            try:
                with open(block_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
            except Exception as e:
                print(f"Error loading block file {block_path}: {e}")
                continue

            block_id = block_path.stem  # e.g., "block_298"

            tram_block = TramBlock(
                block_id=block_id,
                line_number=line_number,
                service_type=service,
                trips=[],
            )

            # Parse stop_times and organize by trip
            stop_times_by_trip: Dict[str, List[StopTime]] = {}

            for stop_time_data in data.get("stop_times", []):
                trip_id = stop_time_data.get("trip_id")
                if not trip_id:
                    continue

                stop_time = StopTime(
                    stop_name=stop_time_data.get("stop_name", ""),
                    stop_lat=stop_time_data.get("stop_lat", 0.0),
                    stop_lon=stop_time_data.get("stop_lon", 0.0),
                    stop_num=stop_time_data.get("stop_num", ""),
                    departure_time=parse_time_string(
                        stop_time_data.get("departure_time", "00:00:00")
                    ),
                    departure_time_str=stop_time_data.get("departure_time", "00:00:00"),
                    stop_sequence=stop_time_data.get("stop_sequence", 0),
                    trip_id=trip_id,
                    trip_num=stop_time_data.get("trip_num", 0),
                )

                if trip_id not in stop_times_by_trip:
                    stop_times_by_trip[trip_id] = []
                stop_times_by_trip[trip_id].append(stop_time)

            # Sort stop times within each trip by stop_sequence
            for trip_id in stop_times_by_trip:
                stop_times_by_trip[trip_id].sort(key=lambda st: st.stop_sequence)

            # Parse trips
            for trip_data in data.get("trips", []):
                trip_id = trip_data.get("trip_id")
                if not trip_id:
                    continue

                # Parse shape coordinates
                shape_coords = []
                for coord in trip_data.get("shape", []):
                    lat = coord.get("latitude", 0.0)
                    lon = coord.get("longitude", 0.0)
                    shape_coords.append((lat, lon))

                # Create Trip object
                trip = Trip(
                    trip_id=trip_id,
                    trip_num=trip_data.get("trip_num", 0),
                    route_short_name=trip_data.get("route_short_name", ""),
                    trip_headsign=trip_data.get("trip_headsign", ""),
                    shape=shape_coords,
                    stop_times=stop_times_by_trip.get(trip_id, []),
                )

                tram_block.trips.append(trip)

            # Sort trips by trip_num
            tram_block.trips.sort(key=lambda t: t.trip_num)
            line_blocks.append(tram_block)

        blocks_by_line[line_number] = line_blocks

    print(f"\nTotal: Loaded blocks for {len(blocks_by_line)} lines")
    return blocks_by_line
