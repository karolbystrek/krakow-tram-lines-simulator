"""
Passenger simulation models
"""

from dataclasses import dataclass, field
from typing import List, Optional


@dataclass
class Passenger:
    """Represents a single passenger"""

    passenger_id: str
    origin_stop_id: str
    destination_stop_id: str
    arrival_time_minutes: float
    boarding_time_minutes: Optional[float] = None
    alighting_time_minutes: Optional[float] = None
    current_tram_id: Optional[str] = None
    status: str = "WAITING"  # WAITING, ON_TRAM, ALIGHTED


@dataclass
class StopState:
    """Tracks passenger state at a stop"""

    stop_id: str
    name: str = ""
    waiting_passengers: List[Passenger] = field(default_factory=list)
    total_arrived: int = 0
    total_boarded: int = 0
    total_alighted: int = 0
    arrival_rate_per_minute: float = 0.0


@dataclass
class TramState:
    """Tracks passenger state on a tram"""

    block_id: str
    passengers: List[Passenger] = field(default_factory=list)
    max_capacity: int = 200
    current_occupancy: int = 0

    def get_available_space(self) -> int:
        """Get available space on the tram"""
        return max(0, self.max_capacity - self.current_occupancy)

    def update_occupancy(self):
        """Update occupancy count from passenger list"""
        # Count only passengers that are actually ON_TRAM
        # Also ensure we don't have any invalid passengers
        self.current_occupancy = len(
            [p for p in self.passengers if p.status == "ON_TRAM"]
        )

        # Defensive: Remove any passengers that are not ON_TRAM (shouldn't be in the list)
        # This prevents accumulation of ALIGHTED passengers
        self.passengers = [p for p in self.passengers if p.status == "ON_TRAM"]
