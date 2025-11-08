from pathlib import Path
from typing import Dict

import folium
from folium.plugins import Fullscreen

from src.data_loader import load_tram_lines, load_tram_stops, get_bounding_box
from src.models import TramLine, Stop

KRAKOW_BOUNDS = [[49.97, 19.80], [50.13, 20.20]]
TRAM_LINE_COLOR = "#4DA6FF"
TRAM_STOP_COLOR = "#1E6BB8"
TRAM_STOP_FILL_COLOR = "#DBEDFF"


def add_tram_shapes_to_map(
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


def create_tram_network_map(
    tram_lines: Dict[str, TramLine],
    output_filename: str = "krakow_tram_network_map.html",
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

    add_tram_shapes_to_map(m, tram_lines, show_by_default=True)
    add_tram_stops_to_map(m, load_tram_stops(), show_by_default=True)

    folium.LayerControl(collapsed=False).add_to(m)
    Fullscreen(position="topright").add_to(m)

    m.save(str(Path(output_filename).resolve()))


def main() -> None:
    try:
        tram_lines = load_tram_lines()

        if not tram_lines:
            print("No tram lines found. Please check the data directory.")
            return

        print(f"Successfully loaded {len(tram_lines)} tram lines")
        create_tram_network_map(tram_lines)
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
