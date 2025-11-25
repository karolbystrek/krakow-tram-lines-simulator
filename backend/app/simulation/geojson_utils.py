from typing import Dict, List
from .models import Stop, Shape


def stops_to_geojson(stops: Dict[str, Stop]) -> dict:
    """Convert Stop objects to GeoJSON FeatureCollection format."""
    features = []

    for kod_busman, stop in stops.items():
        feature = {
            "type": "Feature",
            "geometry": {
                "type": "Point",
                "coordinates": [stop.lon, stop.lat],  # GeoJSON uses [lon, lat]
            },
            "properties": {
                "id": stop.id,
                "name": stop.name,
                "kod_busman": stop.kod_busman,
                "stop_name": stop.name,  # Alias for frontend compatibility
            },
        }
        features.append(feature)

    return {"type": "FeatureCollection", "features": features}


def shapes_to_geojson(shapes_by_line: Dict[str, List[Shape]]) -> dict:
    """Convert Shape objects to GeoJSON FeatureCollection format."""
    features = []

    for line_number, shapes in shapes_by_line.items():
        for shape in shapes:
            # Convert coordinates to GeoJSON format [lon, lat]
            coordinates = [[lon, lat] for lat, lon in shape.coordinates]

            feature = {
                "type": "Feature",
                "geometry": {"type": "LineString", "coordinates": coordinates},
                "properties": {
                    "line_number": line_number,
                    "line_name": line_number,  # Alias for frontend compatibility
                    "color": "#4DA6FF",  # Default tram line color
                },
            }
            features.append(feature)

    return {"type": "FeatureCollection", "features": features}
