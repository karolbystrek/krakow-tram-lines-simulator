import json
from typing import Dict, Tuple, List
from datetime import time

from .models import Stop, Shape, TramLine, Trip, StopTime, TramBlock
from ..config import (
    GEOJSON_SHAPES_PATH,
    GEOJSON_STOPS_PATH,
    TRAM_LINES_DATA_DIR,
)


def load_shapes_from_geojson() -> Dict[str, List[Shape]]:
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


# Cache for stop coordinates to avoid rescanning all services
_cached_stop_coordinates = None

def get_tram_stop_coordinates_from_schedules() -> set:
    """
    Collect all unique stop coordinates from tram schedule data across all services.
    This identifies which stops are actually used by trams.
    
    Since kod_busman format in geojson doesn't match the line-stop format in schedules,
    we match stops by coordinates instead.
    
    Returns:
        Set of tuples (lat, lon) representing stop coordinates used in tram schedules
    """
    global _cached_stop_coordinates
    
    # Return cached result if available
    if _cached_stop_coordinates is not None:
        return _cached_stop_coordinates
    
    tram_stop_coords = set()
    
    if not TRAM_LINES_DATA_DIR.exists():
        _cached_stop_coordinates = tram_stop_coords
        return tram_stop_coords
    
    # Check all services
    services = ["service_1", "service_2", "service_3", "service_4", "service_5"]
    
    for service in services:
        # Scan all line directories
        for line_dir in TRAM_LINES_DATA_DIR.iterdir():
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
                    
                    # Extract coordinates from all stop_times
                    for stop_time_data in data.get("stop_times", []):
                        stop_lat = stop_time_data.get("stop_lat")
                        stop_lon = stop_time_data.get("stop_lon")
                        if stop_lat is not None and stop_lon is not None:
                            # Round to 6 decimal places (~0.1 meter precision) to handle floating point differences
                            lat_rounded = round(float(stop_lat), 6)
                            lon_rounded = round(float(stop_lon), 6)
                            tram_stop_coords.add((lat_rounded, lon_rounded))
                except Exception as e:
                    # Skip files that can't be read
                    continue
    
    # Cache the result
    _cached_stop_coordinates = tram_stop_coords
    return tram_stop_coords


def load_tram_stops(filter_by_tram_schedules: bool = True) -> Dict[str, Stop]:
    """
    Load tram stops from GeoJSON file.
    
    Args:
        filter_by_tram_schedules: If True, only include stops that are used in tram schedules.
                                  This filters out bus-only stops.
    
    Returns:
        Dictionary mapping kod_busman to Stop objects
    """
    if not GEOJSON_STOPS_PATH.exists():
        print(f"Warning: Tram stops GeoJSON file not found at {GEOJSON_STOPS_PATH}")
        return {}

    # Get set of stop coordinates used in tram schedules if filtering is enabled
    tram_stop_coords = set()
    if filter_by_tram_schedules:
        print("Collecting stop coordinates from tram schedules...")
        tram_stop_coords = get_tram_stop_coordinates_from_schedules()
        print(f"Found {len(tram_stop_coords)} unique stops used in tram schedules")

    with open(GEOJSON_STOPS_PATH, "r", encoding="utf-8") as f:
        geojson_data = json.load(f)

    stops_dict = {}
    skipped_count = 0
    filtered_count = 0
    
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
        
        # Filter: Only include stops that are used in tram schedules
        # Match by coordinates (within 0.001 degrees ~ 100 meters)
        if filter_by_tram_schedules and tram_stop_coords:
            geojson_lat = round(float(coordinates[1]), 6)
            geojson_lon = round(float(coordinates[0]), 6)
            
            # Check if this stop's coordinates match any schedule stop coordinates
            matched = False
            for sched_lat, sched_lon in tram_stop_coords:
                # Use a small threshold to account for coordinate precision differences
                if abs(geojson_lat - sched_lat) < 0.001 and abs(geojson_lon - sched_lon) < 0.001:
                    matched = True
                    break
            
            if not matched:
                filtered_count += 1
                continue
        
        # Skip if we already have a stop with this kod_busman (avoid duplicates)
        if kod_busman in stops_dict:
            skipped_count += 1
            continue

        try:
            stops_dict[kod_busman] = Stop(
                id=str(properties.get("OBJECTID", "")),
                name=properties.get("Nazwa_przystanku_nr", ""),
                lat=coordinates[1],
                lon=coordinates[0],
                kod_busman=kod_busman,
            )
        except Exception as e:
            # Skip stops that fail validation
            print(f"Warning: Skipping stop with kod_busman={kod_busman}: {e}")
            skipped_count += 1
            continue
    
    if skipped_count > 0:
        print(f"Warning: Skipped {skipped_count} stops due to missing or invalid kod_busman")
    
    if filter_by_tram_schedules and filtered_count > 0:
        print(f"Filtered out {filtered_count} stops not used in tram schedules (bus-only stops)")
    
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
                    departure_time_minutes=parse_time_to_minutes(
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

    return blocks_by_line
