"""
Passenger simulation models
"""
from dataclasses import dataclass, field
from typing import List, Optional


@dataclass
class Passenger:
    """Represents a single passenger"""
    passenger_id: str  # Unique ID
    origin_stop_id: str  # Where they started waiting
    destination_stop_id: str  # Where they want to go
    arrival_time_minutes: float  # When they arrived at stop
    boarding_time_minutes: Optional[float] = None  # When they boarded tram
    alighting_time_minutes: Optional[float] = None  # When they alighted
    current_tram_id: Optional[str] = None  # Which tram they're on
    status: str = "WAITING"  # WAITING, ON_TRAM, ALIGHTED


@dataclass
class StopState:
    """Tracks passenger state at a stop"""
    stop_id: str
    waiting_passengers: List[Passenger] = field(default_factory=list)
    total_arrived: int = 0  # Total passengers that arrived today
    total_boarded: int = 0  # Total passengers that boarded today
    arrival_rate_per_minute: float = 0.0  # Current arrival rate


@dataclass
class TramState:
    """Tracks passenger state on a tram"""
    block_id: str
    passengers: List[Passenger] = field(default_factory=list)
    max_capacity: int = 200  # Typical tram capacity
    current_occupancy: int = 0
    
    def get_available_space(self) -> int:
        """Get available space on the tram"""
        return max(0, self.max_capacity - self.current_occupancy)
    
    def update_occupancy(self):
        """Update occupancy count from passenger list"""
        # Count only passengers that are actually ON_TRAM
        # Also ensure we don't have any invalid passengers
        self.current_occupancy = len([p for p in self.passengers if p.status == "ON_TRAM"])
        
        # Defensive: Remove any passengers that are not ON_TRAM (shouldn't be in the list)
        # This prevents accumulation of ALIGHTED passengers
        self.passengers = [p for p in self.passengers if p.status == "ON_TRAM"]

