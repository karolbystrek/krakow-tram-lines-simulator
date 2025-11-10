import json
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import folium
from folium.plugins import Fullscreen

from src.data_loader import (
    load_tram_lines,
    load_tram_stops,
    load_tram_blocks,
    get_bounding_box,
)
from src.models import TramLine, Stop, TramBlock

KRAKOW_BOUNDS = [[49.97, 19.80], [50.13, 20.20]]
TRAM_LINE_COLOR = "#4DA6FF"
TRAM_STOP_COLOR = "#1E6BB8"
TRAM_STOP_FILL_COLOR = "#DBEDFF"


def add_tram_lines_to_map(
    map_object: folium.Map,
    tram_lines: Dict[str, TramLine],
    show_by_default: bool = True,
) -> None:
    for line_number, tram_line in sorted(
        tram_lines.items(), key=lambda x: int(x[0]) if x[0].isdigit() else 999
    ):
        line_layer = folium.FeatureGroup(
            name=f"Line {line_number}", show=show_by_default
        )

        for shape in tram_line.shapes:
            if shape.coordinates:
                folium.PolyLine(
                    locations=shape.coordinates,
                    color=TRAM_LINE_COLOR,
                    weight=3,
                    opacity=0.7,
                    tooltip=f"Tram Line {line_number}",
                ).add_to(line_layer)

        line_layer.add_to(map_object)


def add_tram_stops_to_map(
    map_object: folium.Map, stops: Dict[str, Stop], show_by_default: bool = True
) -> None:
    stops_layer = folium.FeatureGroup(name="Tram Stops", show=show_by_default)

    for stop in stops.values():
        folium.CircleMarker(
            location=[stop.lat, stop.lon],
            radius=6,
            color=TRAM_STOP_COLOR,
            weight=2,
            fill=True,
            fill_color=TRAM_STOP_FILL_COLOR,
            fill_opacity=0.9,
            popup=folium.Popup(
                f"<b>{stop.name}</b><br>Code: {stop.kod_busman}<br>ID: {stop.id}",
                max_width=300,
            ),
            tooltip=stop.name,
        ).add_to(stops_layer)

    stops_layer.add_to(map_object)


def interpolate_position(
    start_pos: Tuple[float, float],
    end_pos: Tuple[float, float],
    start_time_minutes: int,
    end_time_minutes: int,
    current_time_minutes: int,
) -> Tuple[float, float]:
    """Linear interpolation between two positions based on time."""
    if end_time_minutes == start_time_minutes:
        return start_pos

    progress = (current_time_minutes - start_time_minutes) / (
        end_time_minutes - start_time_minutes
    )
    progress = max(0.0, min(1.0, progress))

    lat = start_pos[0] + (end_pos[0] - start_pos[0]) * progress
    lon = start_pos[1] + (end_pos[1] - start_pos[1]) * progress

    return lat, lon


def get_tram_position_at_time(
    block: TramBlock, time_minutes: int
) -> Optional[Tuple[float, float]]:
    """Calculate tram position at a specific time in minutes since midnight."""
    status = block.get_status_at_time(time_minutes)

    if status == "IN_DEPOT":
        return None

    active_trip = block.get_active_trip(time_minutes)

    if not active_trip:
        # Tram waiting at terminus - show at last stop of previous trip
        last_trip = None
        for trip in block.trips:
            if trip.get_end_time_minutes() <= time_minutes:
                last_trip = trip
        if last_trip and last_trip.stop_times:
            last_stop = last_trip.stop_times[-1]
            return last_stop.stop_lat, last_stop.stop_lon
        return None

    # Get current segment (between which two stops)
    segment = active_trip.get_current_segment(time_minutes)

    if not segment:
        return None

    prev_stop, next_stop = segment

    # Interpolate position between the two stops
    position = interpolate_position(
        start_pos=(prev_stop.stop_lat, prev_stop.stop_lon),
        end_pos=(next_stop.stop_lat, next_stop.stop_lon),
        start_time_minutes=prev_stop.to_minutes(),
        end_time_minutes=next_stop.to_minutes(),
        current_time_minutes=time_minutes,
    )

    return position


def add_animated_trams_to_map(
    map_object: folium.Map,
    blocks_by_line: Dict[str, List[TramBlock]],
    start_time_minutes: int = 3 * 60,  # 03:00
    end_time_minutes: int = 24 * 60,  # 24:00
    update_interval_ms: int = 1000,  # 1 second = 1 minute
) -> None:
    """Add trams with schedule-based animation to the map."""
    # Collect all tram data for JavaScript
    tram_data = []
    marker_names = []

    for line_number, blocks in blocks_by_line.items():
        for block in blocks:
            # Calculate all positions for this tram throughout the day
            positions = []
            for time_min in range(start_time_minutes, end_time_minutes + 1):
                pos = get_tram_position_at_time(block, time_min)
                if pos:
                    positions.append({"time": time_min, "lat": pos[0], "lon": pos[1]})

            if positions:
                # Create folium marker for this tram
                tram_marker = folium.Marker(
                    location=[positions[0]["lat"], positions[0]["lon"]],
                    icon=folium.Icon(color="red", icon="train", prefix="fa"),
                    tooltip=f"Line {line_number} - {block.block_id}",
                )
                tram_marker.add_to(map_object)

                marker_names.append(tram_marker.get_name())

                tram_data.append(
                    {
                        "id": block.block_id,
                        "line": line_number,
                        "positions": positions,
                        "marker_name": tram_marker.get_name(),
                    }
                )

    if not tram_data:
        print("No tram data to animate")
        return

    # Generate JavaScript for animation
    tram_data_json = json.dumps(tram_data)

    js_code = f"""
    <script>
    document.addEventListener('DOMContentLoaded', function() {{
        console.log('DOM loaded, initializing tram animation...');

        var tramData = {tram_data_json};
        console.log('Loaded ' + tramData.length + ' trams');

        var tramMarkers = {{}};
        var currentTime = {start_time_minutes};
        var endTime = {end_time_minutes};
        var updateInterval = {update_interval_ms};
        var isRunning = true;
        var animationTimeout = null;

        // Wait for map to be ready
        setTimeout(function() {{
            console.log('Linking tram markers...');

            // Link existing folium markers to tram data
            tramData.forEach(function(tram) {{
                var marker = window[tram.marker_name];
                if (marker) {{
                    marker.setOpacity(0);  // Hide initially
                    tramMarkers[tram.id] = {{marker: marker, data: tram}};
                }}
            }});

            console.log('Linked ' + Object.keys(tramMarkers).length + ' markers');

            // Function to find position at specific time
            function getPositionAtTime(positions, time) {{
                for (var i = 0; i < positions.length; i++) {{
                    if (positions[i].time === time) {{
                        return positions[i];
                    }}
                }}
                return null;
            }}

            // Animation update function
            function updateTrams() {{
                var hours = Math.floor(currentTime / 60);
                var minutes = currentTime % 60;
                var timeStr = String(hours).padStart(2, '0') + ':' + String(minutes).padStart(2, '0');

                // Update time display
                var timeDisplay = document.getElementById('simulation-time');
                if (timeDisplay) {{
                    timeDisplay.textContent = 'Time: ' + timeStr;
                }}

                // Update each tram position
                var visibleCount = 0;
                Object.keys(tramMarkers).forEach(function(tramId) {{
                    var tram = tramMarkers[tramId];
                    var pos = getPositionAtTime(tram.data.positions, currentTime);

                    if (pos) {{
                        tram.marker.setLatLng([pos.lat, pos.lon]);
                        tram.marker.setOpacity(1);
                        visibleCount++;
                    }} else {{
                        tram.marker.setOpacity(0);  // Hide when in depot
                    }}
                }});

                currentTime++;
                if (currentTime <= endTime && isRunning) {{
                    animationTimeout = setTimeout(updateTrams, updateInterval);
                }} else if (currentTime > endTime) {{
                    console.log('Animation complete!');
                }}
            }}

            // Toggle play/pause
            window.toggleAnimation = function() {{
                isRunning = !isRunning;
                var btn = document.getElementById('play-pause-btn');
                if (isRunning) {{
                    btn.textContent = 'Pause';
                    updateTrams();
                }} else {{
                    btn.textContent = 'Play';
                    if (animationTimeout) {{
                        clearTimeout(animationTimeout);
                    }}
                }}
            }};

            // Start animation
            console.log('Starting animation from time ' + currentTime + ' to ' + endTime);
            updateTrams();
        }}, 1000);
    }});
    </script>
    """

    map_object.get_root().html.add_child(folium.Element(js_code))

    # Add time display element with play/pause button
    time_display_html = """
    <div style="
        position: fixed;
        top: 10px;
        left: 10px;
        z-index: 1000;
        background: white;
        padding: 10px 15px;
        border-radius: 5px;
        box-shadow: 0 2px 5px rgba(0,0,0,0.3);
        font-family: Arial, sans-serif;
    ">
        <div id="simulation-time" style="
            font-size: 16px;
            font-weight: bold;
            margin-bottom: 10px;
        ">
            Time: 03:00
        </div>
        <button id="play-pause-btn" onclick="toggleAnimation()" style="
            width: 100%;
            padding: 8px 16px;
            background-color: #4CAF50;
            color: white;
            border: none;
            border-radius: 4px;
            cursor: pointer;
            font-size: 14px;
            font-weight: bold;
        ">
            Pause
        </button>
    </div>
    """
    map_object.get_root().html.add_child(folium.Element(time_display_html))


def create_tram_network_map(
    tram_lines: Dict[str, TramLine],
    tram_stops: Dict[str, Stop],
    blocks_by_line: Dict[str, List[TramBlock]],
    output_filename: str = "krakow_tram_network_map.html",
    animate_trams: bool = True,
) -> None:
    min_lat, max_lat, min_lon, max_lon = get_bounding_box(tram_lines)
    center_lat = (min_lat + max_lat) / 2
    center_lon = (min_lon + max_lon) / 2

    m = folium.Map(
        location=[center_lat, center_lon],
        zoom_start=12,
        tiles=None,
        max_bounds=True,
        min_lat=KRAKOW_BOUNDS[0][0],
        max_lat=KRAKOW_BOUNDS[1][0],
        min_lon=KRAKOW_BOUNDS[0][1],
        max_lon=KRAKOW_BOUNDS[1][1],
    )

    folium.TileLayer(
        tiles="CartoDB positron", name="CartoDB Positron (Light)", attr="CartoDB"
    ).add_to(m)
    folium.TileLayer(
        tiles="OpenStreetMap", name="OpenStreetMap (Terrain)", attr="OpenStreetMap"
    ).add_to(m)
    folium.TileLayer(
        tiles="CartoDB Voyager", name="Voyager (Transit)", attr="CartoDB"
    ).add_to(m)

    add_tram_lines_to_map(m, tram_lines, show_by_default=True)
    add_tram_stops_to_map(m, tram_stops, show_by_default=True)

    if animate_trams and blocks_by_line:
        add_animated_trams_to_map(m, blocks_by_line)

    folium.LayerControl(collapsed=False).add_to(m)
    Fullscreen(position="topright").add_to(m)

    m.save(str(Path(output_filename).resolve()))


def main() -> None:
    try:
        tram_lines = load_tram_lines()
        tram_stops = load_tram_stops()
        blocks_by_line = load_tram_blocks(service="service_1")

        if not tram_lines or not tram_stops or not blocks_by_line:
            print("No tram lines found. Please check the data directory.")
            return

        print(f"Successfully loaded {len(tram_lines)} tram lines")
        print(f"Successfully loaded {len(tram_stops)} tram stops")
        print(f"Successfully loaded blocks for {len(blocks_by_line)} lines")

        create_tram_network_map(
            tram_lines, tram_stops, blocks_by_line, animate_trams=True
        )
        print(f"Map saved to 'krakow_tram_network_map.html'")

    except FileNotFoundError as e:
        print(f"Error: {e}")
        print(
            "Please ensure the required GeoJSON files are present in the data directory."
        )
    except Exception as e:
        print(f"Unexpected error: {e}")
        raise


if __name__ == "__main__":
    main()
