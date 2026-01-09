"""
Passenger arrival and destination selection models
"""

import math
import random
import json
from dataclasses import dataclass, asdict
from typing import List, Dict, Optional
from pathlib import Path

from .models import Trip
from .passenger_model import Passenger, StopState

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
DEMAND_PROFILE_PATH = DATA_DIR / "demand_profile.json"

@dataclass
class Peak:
    """Represents a demand peak (Gaussian distribution)."""
    time: float
    width: float
    height: float

    def to_dict(self):
        return asdict(self)

    @classmethod
    def from_dict(cls, data):
        return cls(**data)


@dataclass
class DemandProfile:
    """
    Configuration for the global passenger demand curve.
    Dynamic model with configurable peaks.
    """

    # Base Load (Constant background traffic)
    base_demand_rate: float = 50.0  # passengers per minute system-wide

    # Dynamic Peaks list
    peaks: List[Peak] = None

    def __post_init__(self):
        if self.peaks is None:
            self.peaks = [
                Peak(time=7.5 * 60, width=90.0, height=700.0),   # Morning
                Peak(time=13.5 * 60, width=150.0, height=420.0), # Midday
                Peak(time=17.0 * 60, width=120.0, height=700.0)  # Evening
            ]

    def to_dict(self):
        return {
            "base_demand_rate": self.base_demand_rate,
            "peaks": [p.to_dict() for p in self.peaks]
        }

    @classmethod
    def from_dict(cls, data):
        profile = cls(base_demand_rate=data.get("base_demand_rate", 50.0))
        if "peaks" in data:
            profile.peaks = [Peak.from_dict(p) for p in data["peaks"]]
        return profile


class ArrivalRateModel:
    """
    Models passenger arrival rates using a global demand curve distributed
    to stops based on their weights.
    """

    def __init__(self, profile: DemandProfile = None):
        if profile:
            self.profile = profile
        else:
            # Try loading from file
            loaded_profile = self.load_from_file()
            self.profile = loaded_profile if loaded_profile else DemandProfile()
        
        # Stop weights registry
        self.stop_weights: Dict[str, float] = {}
        self.total_system_weight: float = 0.0

        # Known major hubs in Krakow with higher passenger generation
        # These are partial string matches for stop names
        self.HUB_WEIGHTS = {
            "Rondo Mogilskie": 8.0,
            "Teatr Bagatela": 7.5,
            "Dworzec Główny": 9.0,
            "Rondo Grzegórzeckie": 6.5,
            "Starowiślna": 6.0,
            "Plac Wszystkich Świętych": 5.5,
            "Poczta Główna": 5.5,
            "Rondo Matecznego": 5.0,
            "Rondo Czyżyńskie": 5.0,
            "Biprostal": 4.0,
            "Stary Kleparz": 4.5,
        }

    def load_from_file(self) -> Optional[DemandProfile]:
        """Load demand profile from JSON file."""
        if not DEMAND_PROFILE_PATH.exists():
            return None
        
        try:
            with open(DEMAND_PROFILE_PATH, 'r') as f:
                data = json.load(f)
                print(f"Loaded demand profile from {DEMAND_PROFILE_PATH}")
                return DemandProfile.from_dict(data)
        except Exception as e:
            print(f"Error loading demand profile: {e}")
            return None

    def save_to_file(self):
        """Save current demand profile to JSON file."""
        try:
            # Ensure directory exists
            DEMAND_PROFILE_PATH.parent.mkdir(parents=True, exist_ok=True)
            
            with open(DEMAND_PROFILE_PATH, 'w') as f:
                json.dump(self.profile.to_dict(), f, indent=2)
            print(f"Saved demand profile to {DEMAND_PROFILE_PATH}")
        except Exception as e:
            print(f"Error saving demand profile: {e}")

    def update_profile(self, params: Dict):
        """
        Update the demand profile parameters dynamically.
        Params expected format:
        {
            "base_demand_rate": float,
            "peaks": [
                {"time": float, "width": float, "height": float},
                ...
            ]
        }
        """
        if "base_demand_rate" in params:
            self.profile.base_demand_rate = float(params["base_demand_rate"])
        
        if "peaks" in params and isinstance(params["peaks"], list):
            new_peaks = []
            for p_data in params["peaks"]:
                new_peaks.append(Peak(
                    time=float(p_data.get("time", 0)),
                    width=float(p_data.get("width", 60)),
                    height=float(p_data.get("height", 100))
                ))
            self.profile.peaks = new_peaks

        print(f"Updated demand profile. Base: {self.profile.base_demand_rate}, Peaks: {len(self.profile.peaks)}")

    def gaussian(self, x: float, mu: float, sigma: float) -> float:
        """Calculate Gaussian value."""
        if sigma == 0:
            return 0.0
        return math.exp(-((x - mu) ** 2) / (2 * sigma * sigma))

    def _calculate_global_demand_rate(self, time_minutes: float) -> float:
        """
        Returns the total system-wide passengers per minute at a given time.
        """
        t = time_minutes % 1440
        total_rate = self.profile.base_demand_rate

        for peak in self.profile.peaks:
            total_rate += peak.height * self.gaussian(t, peak.time, peak.width)

        return total_rate

    def set_stop_weight(self, stop_id: str, weight: float):
        """Updates weight for a specific stop and recalculates total."""
        if stop_id in self.stop_weights:
            self.total_system_weight -= self.stop_weights[stop_id]

        self.stop_weights[stop_id] = weight
        self.total_system_weight += weight

    def initialize_weights(self, stops: List[StopState]):
        """
        Initialize weights for all provided stops.
        Applies heuristic boosting for major hubs based on name.
        """
        self.stop_weights = {}
        self.total_system_weight = 0.0

        for stop in stops:
            weight = 1.0

            # Apply Hub Multipliers
            for hub_name, multiplier in self.HUB_WEIGHTS.items():
                if hub_name in stop.name:
                    weight = multiplier
                    break

            self.stop_weights[stop.stop_id] = weight
            self.total_system_weight += weight

        print(
            f"Initialized weights for {len(stops)} stops. Total system weight: {self.total_system_weight:.2f}"
        )

    def get_arrival_rate(self, stop_id: str, time_minutes: float) -> float:
        """
        Calculate arrival rate for a specific stop at a specific time.
        Rate = Global_Rate(t) * (Stop_Weight / Total_Weights)
        """
        if self.total_system_weight == 0 or stop_id not in self.stop_weights:
            return 0.0

        global_rate = self._calculate_global_demand_rate(time_minutes)
        local_share = self.stop_weights[stop_id] / self.total_system_weight

        return global_rate * local_share

    def generate_arrivals(
        self, stop_state: StopState, time_minutes: float, delta_time: float
    ) -> List[Passenger]:

        arrival_rate = self.get_arrival_rate(stop_state.stop_id, time_minutes)

        stop_state.arrival_rate_per_minute = arrival_rate

        expected_arrivals = arrival_rate * delta_time
        new_passengers = []

        # Poisson-like sampling for integer arrivals
        if expected_arrivals >= 1.0:
            num_arrivals = int(expected_arrivals) + (
                1 if random.random() < (expected_arrivals % 1.0) else 0
            )
        else:
            num_arrivals = 1 if random.random() < expected_arrivals else 0

        for i in range(num_arrivals):
            passenger_id = f"p_{stop_state.stop_id}_{int(time_minutes * 10)}_{i}"
            passenger = Passenger(
                passenger_id=passenger_id,
                origin_stop_id=stop_state.stop_id,
                destination_stop_id="",
                arrival_time_minutes=time_minutes,
                status="WAITING",
            )
            new_passengers.append(passenger)
            stop_state.total_arrived += 1

        return new_passengers


class DestinationModel:
    """Models passenger destination selection."""

    def select_destination(self, origin_stop_id: str, trip: Trip) -> Optional[str]:

        if not trip.stop_times or len(trip.stop_times) < 2:
            return None

        origin_idx = None
        for i, stop_time in enumerate(trip.stop_times):
            if stop_time.stop_num == origin_stop_id:
                origin_idx = i
                break

        if origin_idx is None or origin_idx >= len(trip.stop_times) - 1:
            return None

        possible_destinations = trip.stop_times[origin_idx + 1 :]
        if not possible_destinations:
            return None

        weights = []
        for i, stop_time in enumerate(possible_destinations):
            w = 1.0 / (i + 1)
            if i == len(possible_destinations) - 1:
                w *= 2.0
            weights.append(w)

        total_weight = sum(weights)
        if total_weight == 0:
            return possible_destinations[0].stop_num

        r = random.random() * total_weight
        cumulative = 0
        for i, w in enumerate(weights):
            cumulative += w
            if r <= cumulative:
                return possible_destinations[i].stop_num

        return possible_destinations[-1].stop_num
