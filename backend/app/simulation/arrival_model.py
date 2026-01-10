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
STOP_WEIGHTS_PATH = DATA_DIR / "stop_weights.json"

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
        self.stop_weights_by_full_name: Dict[str, float] = {}
        self.total_system_weight: float = 0.0

        # Load weights from file
        self.file_weights = self.load_weights_from_file()

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
            
    def load_weights_from_file(self) -> Dict[str, float]:
        """Load stop weights from JSON file."""
        if not STOP_WEIGHTS_PATH.exists():
            print("No stop weights file found, using defaults.")
            return {}
            
        try:
            with open(STOP_WEIGHTS_PATH, 'r') as f:
                weights = json.load(f)
                print(f"Loaded {len(weights)} stop weights from {STOP_WEIGHTS_PATH}")
                return weights
        except Exception as e:
            print(f"Error loading stop weights: {e}")
            return {}

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

    def save_weights(self):
        """Save current stop weights to JSON file."""
        try:
            STOP_WEIGHTS_PATH.parent.mkdir(parents=True, exist_ok=True)
            
            # Save the full runtime state (ID -> Weight)
            # This ensures we persist exactly what the simulation is using
            with open(STOP_WEIGHTS_PATH, 'w') as f:
                json.dump(self.stop_weights, f, indent=2)
            print(f"Saved stop weights to {STOP_WEIGHTS_PATH}")
        except Exception as e:
            print(f"Error saving stop weights: {e}")

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
        # Update run-time map
        if stop_id in self.stop_weights:
            self.total_system_weight -= self.stop_weights[stop_id]
        
        self.stop_weights[stop_id] = weight
        self.total_system_weight += weight
        
        # Also update the configuration map (by name if possible, or ID)
        # This is tricky because we don't have the name here easily unless we look it up.
        # For now, we update the runtime mainly. 
        # If we want persistence, we should probably update self.file_weights too using the stop name.
        pass 

    def update_weight_config(self, name_or_id: str, weight: float):
        """Update the persistent configuration for a stop weight."""
        self.file_weights[name_or_id] = weight
        # Note: This doesn't automatically update self.stop_weights until re-initialization
        # or we need to iterate and update all matching stops.

    def initialize_weights(self, stops: List[StopState]):
        """
        Initialize weights for all provided stops.
        Applies weights from loaded configuration.
        """
        self.stop_weights = {}
        self.stop_weights_by_full_name = {}
        self.total_system_weight = 0.0

        for stop in stops:
            weight = 1.0

            # 1. Try exact match by Stop ID
            if stop.stop_id in self.file_weights:
                weight = self.file_weights[stop.stop_id]
            # 2. Try exact match by Name
            elif stop.name in self.file_weights:
                weight = self.file_weights[stop.name]
            else:
                # 3. Partial match for names (e.g. "Rondo Mogilskie" in "Rondo Mogilskie 01")
                # Sort keys by length descending to match longest specific name first
                for key in sorted(self.file_weights.keys(), key=len, reverse=True):
                    if key in stop.name:
                        weight = self.file_weights[key]
                        break

            self.stop_weights[stop.stop_id] = weight
            if stop.full_name:
                self.stop_weights_by_full_name[stop.full_name] = weight
                
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
    
    def __init__(self):
        self.stop_weights: Dict[str, float] = {}

    def set_weights(self, weights: Dict[str, float]):
        """Update the knowledge of stop weights for destination logic."""
        self.stop_weights = weights

    def select_destination(self, origin_stop_id: str, trip: Trip) -> Optional[str]:

        if not trip.stop_times or len(trip.stop_times) < 2:
            return None

        origin_idx = None
        for i, stop_time in enumerate(trip.stop_times):
            if stop_time.full_name == origin_stop_id:
                origin_idx = i
                break

        if origin_idx is None or origin_idx >= len(trip.stop_times) - 1:
            return None

        possible_destinations = trip.stop_times[origin_idx + 1 :]
        if not possible_destinations:
            return None

        weights = []
        origin_dist = trip.stop_times[origin_idx].shape_dist_traveled
        
        for stop_time in possible_destinations:
            # Passenger distribution should be influenced by stop weights
            # AND distance (Gravity Model) to avoid excessive accumulation at terminals.
            
            # 1. Get Stop "Mass" (Weight)
            stop_mass = self.stop_weights.get(stop_time.full_name, 1.0)
            
            # 2. Get Distance along the shape
            dist = max(50.0, stop_time.shape_dist_traveled - origin_dist)
            
            # 3. Calculate Weight using a balanced decay function
            # Adding a constant (800m) to distance makes short trips likely 
            # but doesn't make long trips impossible.
            w = stop_mass / (dist + 800.0)
            
            weights.append(w)

        total_weight = sum(weights)
        if total_weight == 0:
            return possible_destinations[0].full_name

        r = random.random() * total_weight
        cumulative = 0
        for i, w in enumerate(weights):
            cumulative += w
            if r <= cumulative:
                return possible_destinations[i].full_name

        return possible_destinations[-1].full_name
