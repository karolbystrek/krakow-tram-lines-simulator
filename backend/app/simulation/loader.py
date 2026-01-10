import json
from datetime import time
from typing import Dict, Tuple, List, Optional, Set

from .models import Stop, Shape, TramLine, Trip, StopTime, TramBlock
from ..config import (
    GEOJSON_LINE_SHAPES_PATH,
    GEOJSON_STOPS_PATH,
    TRAM_LINES_DIR,
)


def load_shapes_from_geojson() -> Dict[str, List[Shape]]:
    if not GEOJSON_LINE_SHAPES_PATH.exists():
        print(f"Warning: GeoJSON file not found at {GEOJSON_LINE_SHAPES_PATH}")
        return {}

    with open(GEOJSON_LINE_SHAPES_PATH, "r", encoding="utf-8") as f:
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


# Cache for stop coordinates to avoid rescanning all services
_cached_stop_details = None


def clean_stop_name(name: str) -> str:
    """
    Remove suffixes like (nż), (nz) from stop names, handling variations and spaces.
    """
    if not name:
        return ""
    
    import re
    # Remove suffixes like (nż), (nz), (nż.), (nz.) with or without parentheses
    cleaned = re.sub(r"\(?nż\.?\)?", "", name, flags=re.IGNORECASE)
    cleaned = re.sub(r"\(?nz\.?\)?", "", cleaned, flags=re.IGNORECASE)
    
    # Remove extra spaces and return
    return " ".join(cleaned.split())


def get_tram_stop_names_from_schedules() -> Set[str]:
    """
    Collect all unique full stop names from tram schedule data across all services.
    Returns a set of full_name strings.
    """
    global _cached_stop_details

    # Return cached result if available (reuse _cached_stop_details for names if it's a set)
    if isinstance(_cached_stop_details, set):
        return _cached_stop_details

    stop_names = set()

    if not TRAM_LINES_DIR.exists():
        _cached_stop_details = stop_names
        return stop_names

    # Check all services
    services = ["service_1", "service_2", "service_3", "service_4", "service_5"]

    for service in services:
        # Scan all line directories
        for line_dir in TRAM_LINES_DIR.iterdir():
            if not line_dir.is_dir():
                continue

            service_dir = line_dir / service
            if not service_dir.exists():
                continue

            # Get all block files for this line and service
            block_files = sorted(service_dir.glob("block_*.json"))

            for block_path in block_files:
                try:
                    with open(block_path, "r", encoding="utf-8") as f:
                        data = json.load(f)

                    # Extract names from all stop_times
                    for stop_time_data in data.get("stop_times", []):
                        stop_name = stop_time_data.get("stop_name", "")
                        stop_num = stop_time_data.get("stop_num", "")
                        
                        clean_name = clean_stop_name(stop_name)
                        full_name = f"{clean_name} {stop_num}".strip()
                        if full_name:
                            stop_names.add(full_name)
                            
                except Exception as e:
                    # Skip files that can't be read
                    continue

    # Cache the result
    _cached_stop_details = stop_names
    return stop_names


def load_tram_stops(
    filter_by_tram_schedules: bool = True,
    active_full_names: Optional[Set[str]] = None,
) -> Dict[str, Stop]:
    """
    Load tram stops from GeoJSON file.

    Args:
        filter_by_tram_schedules: If True and active_full_names is None,
                                  only include stops that are used in any tram schedule.
        active_full_names: Optional set of full stop names (e.g., "Stop Name 01") to filter by.

    Returns:
        Dictionary mapping kod_busman to Stop objects
    """
    if not GEOJSON_STOPS_PATH.exists():
        print(f"Warning: Tram stops GeoJSON file not found at {GEOJSON_STOPS_PATH}")
        return {}

    # Get set of stop names used in tram schedules if filtering is enabled and no explicit filters provided
    if filter_by_tram_schedules and active_full_names is None:
        print("Collecting stop names from tram schedules...")
        active_full_names = get_tram_stop_names_from_schedules()
        print(f"Found {len(active_full_names)} unique stop names used in tram schedules")

    with open(GEOJSON_STOPS_PATH, "r", encoding="utf-8") as f:
        geojson_data = json.load(f)

    stops_dict = {}
    skipped_count = 0
    filtered_count = 0
    filtered_names_dropped = set()

    for feature in geojson_data.get("features", []):
        properties = feature.get("properties", {})
        coordinates = feature.get("geometry", {}).get("coordinates", [])

        # Handle kod_busman - it might be None, empty string, or missing
        kod_busman = properties.get("kod_busman")
        if kod_busman is None:
            # Try to use OBJECTID as fallback identifier
            objectid = properties.get("OBJECTID")
            if objectid is not None:
                kod_busman = f"OBJ_{objectid}"
            else:
                # Skip stops without any identifier
                skipped_count += 1
                continue
        elif not isinstance(kod_busman, str) or not kod_busman.strip():
            # If kod_busman is not a valid string, use OBJECTID as fallback
            objectid = properties.get("OBJECTID")
            if objectid is not None:
                kod_busman = f"OBJ_{objectid}"
            else:
                skipped_count += 1
                continue

        # Ensure kod_busman is a non-empty string
        kod_busman = str(kod_busman).strip()
        if not kod_busman:
            skipped_count += 1
            continue

        # Determine name and number from GeoJSON properties
        raw_name_with_num = properties.get("Nazwa_przystanku_nr", "")
        # Clean the name as it appears in GeoJSON
        geojson_full_name = clean_stop_name(raw_name_with_num)

        # Filtering logic
        if filter_by_tram_schedules and active_full_names is not None:
            if geojson_full_name not in active_full_names:
                filtered_count += 1
                filtered_names_dropped.add(geojson_full_name)
                continue

        # Determine final name and number for internal Stop object
        clean_name = geojson_full_name
        stop_num = ""

        # If we have a number at the end, extract it
        if " " in clean_name:
            parts = clean_name.rsplit(" ", 1)
            # Check if last part is numeric or looks like a stop number
            if parts[1].isdigit() or (
                len(parts[1]) <= 3 and any(c.isdigit() for c in parts[1])
            ):
                clean_name = parts[0]
                stop_num = parts[1]

        # Final full name construction (standardized)
        full_name = f"{clean_name} {stop_num}".strip()

        # Skip if we already have a stop with this kod_busman (avoid duplicates)
        if kod_busman in stops_dict:
            skipped_count += 1
            continue

        try:
            stops_dict[kod_busman] = Stop(
                id=str(properties.get("OBJECTID", "")),
                name=raw_name_with_num,
                lat=coordinates[1],
                lon=coordinates[0],
                kod_busman=kod_busman,
                stop_num=stop_num,
                clean_name=clean_name,
                full_name=full_name,
            )
        except Exception as e:
            # Skip stops that fail validation
            print(f"Warning: Skipping stop with kod_busman={kod_busman}: {e}")
            skipped_count += 1
            continue


    if skipped_count > 0:
        print(
            f"Warning: Skipped {skipped_count} stops due to missing or invalid kod_busman"
        )

    if filter_by_tram_schedules and filtered_count > 0:
        print(
            f"Filtered out {filtered_count} stops not used in tram schedules (bus-only or inactive stops):"
        )
        print(f"Dropped: {sorted(filtered_names_dropped)}")

    print(f"Loaded {len(stops_dict)} valid tram stops")
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


def get_service_for_weekday(weekday: int) -> str:
    """
    Map weekday index to service_id.

    Args:
        weekday: Integer 0-6 (Monday=0, Sunday=6)

    Returns:
        service_id string (service_1 to service_5)

    Service mapping:
    - service_1: Monday, Tuesday, Wednesday
    - service_5: Thursday
    - service_4: Friday
    - service_2: Saturday
    - service_3: Sunday
    """
    # Monday=0, Tuesday=1, Wednesday=2 -> service_1
    if weekday in [0, 1, 2]:
        return "service_1"
    # Thursday=3 -> service_5
    elif weekday == 3:
        return "service_5"
    # Friday=4 -> service_4
    elif weekday == 4:
        return "service_4"
    # Saturday=5 -> service_2
    elif weekday == 5:
        return "service_2"
    # Sunday=6 -> service_3
    else:
        return "service_3"


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


def parse_time_to_minutes(time_str: str) -> int:
    """Parse time string in format HH:MM:SS to minutes since midnight"""
    parts = time_str.split(":")
    hour = int(parts[0])
    minute = int(parts[1])
    # second = int(parts[2]) # We don't need seconds for minute precision

    return hour * 60 + minute


def load_tram_blocks(service: str = "service_1") -> Dict[str, List[TramBlock]]:
    """Load and process tram schedule data for all lines and blocks in a service."""
    if not TRAM_LINES_DIR.exists():
        print(f"Warning: Lines data directory not found at {TRAM_LINES_DIR}")
        return {}

    blocks_by_line: Dict[str, List[TramBlock]] = {}

    # Scan all line directories
    for line_dir in TRAM_LINES_DIR.iterdir():
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

                raw_stop_name = stop_time_data.get("stop_name", "")
                stop_num = stop_time_data.get("stop_num", "")
                clean_name = clean_stop_name(raw_stop_name)
                full_name = f"{clean_name} {stop_num}".strip()

                stop_time = StopTime(
                    stop_name=raw_stop_name,
                    stop_lat=stop_time_data.get("stop_lat", 0.0),
                    stop_lon=stop_time_data.get("stop_lon", 0.0),
                    stop_num=stop_num,
                    departure_time=parse_time_string(
                        stop_time_data.get("departure_time", "00:00:00")
                    ),
                    departure_time_minutes=parse_time_to_minutes(
                        stop_time_data.get("departure_time", "00:00:00")
                    ),
                    departure_time_str=stop_time_data.get("departure_time", "00:00:00"),
                    stop_sequence=stop_time_data.get("stop_sequence", 0),
                    trip_id=trip_id,
                    trip_num=stop_time_data.get("trip_num", 0),
                    full_name=full_name,
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

    return blocks_by_line
