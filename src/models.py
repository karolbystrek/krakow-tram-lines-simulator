from dataclasses import dataclass, field
from typing import List, Tuple, Optional


@dataclass
class Stop:
    id: str
    name: str
    lat: float
    lon: float
    kod_busman: str


@dataclass
class Shape:
    coordinates: List[Tuple[float, float]]

    @classmethod
    def from_json_format(cls, json_coords: List[List[float]]) -> "Shape":
        return cls(coordinates=[(coord[1], coord[0]) for coord in json_coords])


@dataclass
class TramLine:
    line_number: str
    stops: dict[str, Stop] = field(default_factory=dict)
    shapes: List[Shape] = field(default_factory=list)

    def get_all_coordinates(self) -> List[Tuple[float, float]]:
        return [coord for shape in self.shapes for coord in shape.coordinates]


@dataclass
class Trip:
    trip_id: str
    direction: str
    schedule: List[Tuple[str, str, str]] = field(default_factory=list)


@dataclass
class Tram:
    tram_id: str
    current_trip: Optional[Trip] = None
    position: Optional[Tuple[float, float]] = None
    status: str = "DEPOT"
    occupancy: float = 0.0
