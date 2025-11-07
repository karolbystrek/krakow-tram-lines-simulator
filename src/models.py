from dataclasses import dataclass, field
from typing import List, Dict, Tuple, Optional

@dataclass
class Stop:
    id: str
    name: str
    lat: float
    lon: float

@dataclass
class Trip:
    trip_id: str
    direction: str
    schedule: List[Tuple[str, str, str]] = field(default_factory=list)

@dataclass
class Line:
    line_number: str
    stops: Dict[str, Stop] = field(default_factory=dict)
    trips: List[Trip] = field(default_factory=list)

@dataclass
class Tram:
    tram_id: str
    current_trip: Optional[Trip] = None
    position: Optional[Tuple[float, float]] = None
    status: str = "DEPOT"
    occupancy: float = 0.0
