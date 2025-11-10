from dataclasses import dataclass, field
from typing import List, Tuple, Optional
from datetime import time


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
class StopTime:
    """Represents a scheduled stop on a trip"""

    stop_name: str
    stop_lat: float
    stop_lon: float
    stop_num: str
    departure_time: time  # Parsed time object for easy comparison
    departure_time_str: str  # Original string format (HH:MM:SS)
    stop_sequence: int
    trip_id: str
    trip_num: int

    def to_minutes(self) -> int:
        """Convert departure time to minutes since midnight"""
        return self.departure_time.hour * 60 + self.departure_time.minute


@dataclass
class Trip:
    """Represents a single trip from start to end"""

    trip_id: str
    trip_num: int
    route_short_name: str
    trip_headsign: str  # Destination name
    shape: List[Tuple[float, float]]  # Path coordinates (lat, lon)
    stop_times: List[StopTime] = field(default_factory=list)

    def get_start_time_minutes(self) -> int:
        """Get trip start time in minutes since midnight"""
        return self.stop_times[0].to_minutes() if self.stop_times else 0

    def get_end_time_minutes(self) -> int:
        """Get trip end time in minutes since midnight"""
        return self.stop_times[-1].to_minutes() if self.stop_times else 0

    def is_active_at(self, time_minutes: int) -> bool:
        """Check if trip is active at given time (in minutes since midnight)"""
        return self.get_start_time_minutes() <= time_minutes <= self.get_end_time_minutes()

    def get_current_segment(self, time_minutes: int) -> Optional[Tuple[StopTime, StopTime]]:
        """
        Get the two stops the tram is between at the given time.
        Returns (previous_stop, next_stop) or None if not in transit.
        """
        if not self.is_active_at(time_minutes):
            return None

        for i in range(len(self.stop_times) - 1):
            current_stop = self.stop_times[i]
            next_stop = self.stop_times[i + 1]

            if current_stop.to_minutes() <= time_minutes <= next_stop.to_minutes():
                return current_stop, next_stop

        return None


@dataclass
class TramBlock:
    """Represents a tram block (vehicle) with all its trips for the day"""

    block_id: str
    line_number: str
    service_type: str  # e.g., "service_1"
    trips: List[Trip] = field(default_factory=list)

    def get_active_trip(self, time_minutes: int) -> Optional[Trip]:
        """
        Get the trip that is active at the given simulation time.
        Returns None if tram is waiting at terminus or in depot.
        """
        for trip in self.trips:
            if trip.is_active_at(time_minutes):
                return trip
        return None

    def get_status_at_time(self, time_minutes: int) -> str:
        """
        Get tram status: 'IN_TRANSIT', 'AT_TERMINUS', or 'IN_DEPOT'
        """
        active_trip = self.get_active_trip(time_minutes)
        if active_trip:
            return 'IN_TRANSIT'

        # Check if between trips (at terminus)
        if self.trips:
            first_start = self.trips[0].get_start_time_minutes()
            last_end = self.trips[-1].get_end_time_minutes()

            if first_start <= time_minutes <= last_end:
                return 'AT_TERMINUS'

        return 'IN_DEPOT'


@dataclass
class Tram:
    tram_id: str
    line: TramLine
    current_trip: Optional[Trip] = None
    position: Optional[Tuple[float, float]] = None
    status: str = "DEPOT"
    occupancy: float = 0.0
