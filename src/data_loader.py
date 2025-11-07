import os
import json
from typing import Dict, List, Tuple
from src.models import Stop, Line, Trip


def load_all_data(data_directory: str) -> Tuple[Dict[str, Line], Dict[str, List[Trip]]]:
    """
    Loads all tram line data from a directory of JSON files.
    """
    all_lines: Dict[str, Line] = {}
    all_trips: Dict[str, List[Trip]] = {}

    print(f"--- Loading JSON line data from '{data_directory}' ---")

    for filename in os.listdir(data_directory):
        if not filename.endswith(".json"):
            continue

        line_number = filename.replace(".json", "")
        filepath = os.path.join(data_directory, filename)

        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                data = json.load(f)

            stops_in_file = {
                stop_data['stop_id']: Stop(
                    id=stop_data['stop_id'],
                    name=stop_data['stop_name'],
                    lat=stop_data['stop_lat'],
                    lon=stop_data['stop_lon']
                ) for stop_data in data.get('stops', [])
            }

            trips_for_line = [
                Trip(
                    trip_id=trip_data['trip_id'],
                    direction=trip_data.get('trip_headsign', 'N/A'),
                    schedule=[(st['stop_id'], st['arrival_time'], st['departure_time']) for st in
                              trip_data.get('stop_times', [])]
                ) for trip_data in data.get('trips', [])
            ]

            all_lines[line_number] = Line(
                line_number=line_number,
                stops=stops_in_file,
                shapes=data.get('shapes', [])
            )
            all_trips[line_number] = trips_for_line

        except Exception as e:
            print(f"  - Error processing file {filename}: {e}. Skipping.")

    print(f"--- JSON Data Load Complete. Found {len(all_lines)} lines. ---")
    return all_lines, all_trips
