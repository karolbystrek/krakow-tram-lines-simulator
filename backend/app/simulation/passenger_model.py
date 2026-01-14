from dataclasses import dataclass, field
from typing import List, Optional


@dataclass
class Passenger:
    passenger_id: str
    origin_stop_id: str
    destination_stop_id: str
    target_line: str  # The line this passenger was generated for (preferred), but can board any valid line
    arrival_time_minutes: float
    boarding_time_minutes: Optional[float] = None
    alighting_time_minutes: Optional[float] = None
    current_tram_id: Optional[str] = None
    status: str = "WAITING"  # WAITING, ON_TRAM, ALIGHTED


@dataclass
class StopState:
    stop_id: str
    name: str = ""
    full_name: str = ""
    waiting_passengers: List[Passenger] = field(default_factory=list)
    total_arrived: int = 0
    total_boarded: int = 0
    total_alighted: int = 0
    arrival_rate_per_minute: float = 0.0


@dataclass
class TramState:
    block_id: str
    passengers: List[Passenger] = field(default_factory=list)
    max_capacity: int = 500
    current_occupancy: int = 0

    def get_available_space(self) -> int:
        return max(0, self.max_capacity - self.current_occupancy)

    def update_occupancy(self):
        self.current_occupancy = len(
            [p for p in self.passengers if p.status == "ON_TRAM"]
        )
        self.passengers = [p for p in self.passengers if p.status == "ON_TRAM"]
