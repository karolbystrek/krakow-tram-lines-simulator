from __future__ import annotations
from dataclasses import dataclass, field
from typing import List, Tuple, Optional, Dict
from datetime import time

from pydantic import BaseModel, ConfigDict


class Stop(BaseModel):
    """Represents a tram stop"""
    id: str
    name: str
    lat: float
    lon: float
    kod_busman: str

    model_config = ConfigDict(arbitrary_types_allowed=True)


class Shape(BaseModel):
    """Represents a line shape (path coordinates)"""
    coordinates: List[Tuple[float, float]]

    model_config = ConfigDict(arbitrary_types_allowed=True)

    @classmethod
    def from_json_format(cls, json_coords: List[List[float]]) -> "Shape":
        return cls(coordinates=[(coord[1], coord[0]) for coord in json_coords])


@dataclass
class TramLine:
    """Represents a tram line with stops and shapes"""
    line_number: str
    stops: Dict[str, Stop] = field(default_factory=dict)
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
    departure_time_minutes: int  # Minutes since midnight (can be > 24*60)
    departure_time: time  # Parsed time object for easy comparison
    departure_time_str: str  # Original string format (HH:MM:SS)
    stop_sequence: int
    trip_id: str
    trip_num: int
    shape_dist_traveled: float = 0.0  # Distance along the shape from start

    def to_minutes(self) -> int:
        """Convert departure time to minutes since midnight"""
        return self.departure_time_minutes


@dataclass
class Trip:
    """Represents a single trip from start to end"""

    trip_id: str
    trip_num: int
    route_short_name: str
    trip_headsign: str  # Destination name
    shape: List[Tuple[float, float]]  # Path coordinates (lat, lon)
    stop_times: List[StopTime] = field(default_factory=list)
    _shape_distances: List[float] = field(default_factory=list) # Cumulative distance for each point in shape

    def get_start_time_minutes(self) -> int:
        """Get trip start time in minutes since midnight"""
        return self.stop_times[0].to_minutes() if self.stop_times else 0

    def get_end_time_minutes(self) -> int:
        """Get trip end time in minutes since midnight"""
        return self.stop_times[-1].to_minutes() if self.stop_times else 0

    def is_active_at(self, time_minutes: float) -> bool:
        """Check if trip is active at given time (in minutes since midnight)"""
        return self.get_start_time_minutes() <= time_minutes <= self.get_end_time_minutes()

    def get_current_segment(self, time_minutes: float) -> Optional[Tuple[StopTime, StopTime]]:
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

    def initialize_shape_indices(self):
        """
        Pre-calculate distances along the shape and map stops to distances.
        This allows for efficient interpolation along the path.
        """
        if not self.shape:
            return

        # 1. Calculate cumulative distances for the shape path
        from math import radians, cos, sin, asin, sqrt

        def haversine(lon1, lat1, lon2, lat2):
            """
            Calculate the great circle distance between two points 
            on the earth (specified in decimal degrees)
            """
            # convert decimal degrees to radians 
            lon1, lat1, lon2, lat2 = map(radians, [lon1, lat1, lon2, lat2])

            # haversine formula 
            dlon = lon2 - lon1 
            dlat = lat2 - lat1 
            a = sin(dlat/2)**2 + cos(lat1) * cos(lat2) * sin(dlon/2)**2
            c = 2 * asin(sqrt(a)) 
            r = 6371 # Radius of earth in kilometers. Use 6371000 for meters
            return c * r * 1000 # meters

        self._shape_distances = [0.0] * len(self.shape)
        total_dist = 0.0
        for i in range(1, len(self.shape)):
            lat1, lon1 = self.shape[i-1]
            lat2, lon2 = self.shape[i]
            dist = haversine(lon1, lat1, lon2, lat2)
            total_dist += dist
            self._shape_distances[i] = total_dist

        # 2. Map each stop to the closest point on the shape and store its distance
        # We assume stops appear in order along the path
        last_idx = 0
        for stop_time in self.stop_times:
            best_dist = float('inf')
            best_idx = last_idx
            
            # Search for closest point on shape, starting from previous stop's position
            # to avoid backtracking (unless the path loops, but tram paths usually don't loop tightly)
            # We search a bit ahead
            for i in range(last_idx, len(self.shape)):
                lat_s, lon_s = self.shape[i]
                # Simple Euclidean distance for finding closest point is enough for small areas
                # or use haversine if precision needed. 
                # Since we just want the index, simple dist is faster.
                d = (lat_s - stop_time.stop_lat)**2 + (lon_s - stop_time.stop_lon)**2
                if d < best_dist:
                    best_dist = d
                    best_idx = i
                
                # Optimization: if distance starts growing significantly, we might have passed the stop
                # But paths can be curvy, so be careful. 
                # For now, full scan from last_idx is safer.
            
            stop_time.shape_dist_traveled = self._shape_distances[best_idx]
            last_idx = best_idx


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


