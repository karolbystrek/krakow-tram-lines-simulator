import os
import json
import folium
import webbrowser
from .models import Stop
from folium.plugins import MiniMap, Fullscreen, LocateControl


def load_stops_from_json(data_directory: str) -> dict:
    unique_stops = {}

    for filename in os.listdir(data_directory):
        if filename.endswith(".json"):
            filepath = os.path.join(data_directory, filename)
            try:
                with open(filepath, 'r', encoding='utf-8') as f:
                    data = json.load(f)

                for stop_data in data.get('stops', []):
                    stop_id = stop_data['stop_id']
                    if stop_id not in unique_stops:
                        unique_stops[stop_id] = Stop(
                            id=stop_id,
                            name=stop_data['stop_name'],
                            lat=stop_data['stop_lat'],
                            lon=stop_data['stop_lon']
                        )
            except Exception as e:
                print(f"Error processing {filename}: {e}")

    return unique_stops


def create_stop_map(stops: dict, output_filename="krakow_stops_map.html"):
    krakow_center = [50.0614, 19.9366]
    m = folium.Map(location=krakow_center, zoom_start=12, tiles="CartoDB positron")

    stop_layer = folium.FeatureGroup(name="Tram Stops", show=True).add_to(m)


    for stop_id, stop in stops.items():
        folium.CircleMarker(
            location=[stop.lat, stop.lon],
            radius=4,
            color='#0078A8',
            weight=1,
            fill=True,
            fill_color='#0078A8',
            fill_opacity=0.7,
            popup=f"<b>{stop.name}</b><br>(ID: {stop.id})"
        ).add_to(stop_layer)

    folium.LayerControl().add_to(m)
    MiniMap(toggle_display=True).add_to(m)
    Fullscreen(position="topright").add_to(m)
    LocateControl().add_to(m)

    output_path = os.path.abspath(output_filename)
    m.save(output_path)

    print(f"Successfully generated map: '{output_path}'")
    webbrowser.open(f"file://{output_path}")


if __name__ == '__main__':
    project_root = os.path.dirname(os.path.abspath(__file__))
    data_dir = os.path.join(project_root, '..', 'data')

    all_stops = load_stops_from_json(data_dir)

    if all_stops:
        create_stop_map(all_stops)
    else:
        print("No stop data could be loaded. Please run 'load_tram_data.py' first.")
