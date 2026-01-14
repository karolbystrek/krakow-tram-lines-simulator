"""
Passenger arrival and destination selection models
"""

import json
import math
import random
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import List, Dict, Optional, Tuple

from .loader import clean_stop_name
from .models import TramBlock
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
                Peak(time=7.5 * 60, width=90.0, height=700.0),  # Morning
                Peak(time=13.5 * 60, width=150.0, height=420.0),  # Midday
                Peak(time=17.0 * 60, width=120.0, height=700.0),  # Evening
            ]

    def to_dict(self):
        return {
            "base_demand_rate": self.base_demand_rate,
            "peaks": [p.to_dict() for p in self.peaks],
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
        self.fullname_to_id: Dict[str, str] = {}
        self.total_system_weight: float = 0.0

        # Reachability map: Dict[OriginFullName, Dict[DestinationFullName, MinDistance]]
        self.global_reachability: Dict[str, Dict[str, float]] = {}
        # OD Lines map: Dict[OriginFullName, Dict[DestinationFullName, Set[LineID]]]
        self.od_lines: Dict[str, Dict[str, set]] = {}
        # Cache for gravity model weights: OriginFullName -> (List[DestNames], List[Weights])
        self.cached_gravity_weights: Dict[str, Tuple[List[str], List[float]]] = {}

        # Load weights from file
        self.file_weights = self.load_weights_from_file()

        # Cache for current simulation state to allow runtime weight updates
        self.current_stops: List[StopState] = []
        self.current_blocks: List[TramBlock] = []
        self.accessibility_scores: Dict[str, float] = {}

        self.last_departure_by_stop_id: Dict[str, int] = {}

        self._skipped_generation_after_service: int = 0
        self._skipped_generation_no_future_service: int = 0
        self._skipped_generation_depot_destination: int = 0
        self._skipped_depot_trips_count: int = 0
        self._skipped_generation_due_to_long_trip: int = 0
        self.max_wait_to_board_minutes: int = 30
        self.max_allowed_trip_duration_minutes: int = 120

    def load_from_file(self) -> Optional[DemandProfile]:
        """Load demand profile from JSON file."""
        if not DEMAND_PROFILE_PATH.exists():
            return None

    def get_detailed_weights(self) -> List[Dict]:
        """Return detailed weight breakdown for UI."""
        details = []
        for stop_id, gen_weight in self.stop_weights.items():
            # Find full name
            full_name = None
            for name, sid in self.fullname_to_id.items():
                if sid == stop_id:
                    full_name = name
                    break
            
            base_weight = 1.0
            if full_name and full_name in self.stop_weights_by_full_name:
                base_weight = self.stop_weights_by_full_name[full_name]
            elif stop_id in self.file_weights:
                base_weight = self.file_weights[stop_id]
                
            acc_score = self.accessibility_scores.get(stop_id, 0.0)
            
            details.append({
                "id": stop_id,
                "name": full_name if full_name else stop_id,
                "base_weight": base_weight,
                "accessibility_score": acc_score,
                "final_weight": gen_weight
            })
        return details

    def update_base_weights(self, updates: Dict[str, float]):
        """Update base weights and re-initialize model."""
        self.file_weights.update(updates)
        # Re-initialize to propagate changes (Mass update affects Accessibility of others)
        if self.current_stops and self.current_blocks:
            self.initialize_weights(self.current_stops, self.current_blocks)

        try:
            with open(DEMAND_PROFILE_PATH, "r") as f:
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
            with open(STOP_WEIGHTS_PATH, "r") as f:
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

            with open(DEMAND_PROFILE_PATH, "w") as f:
                json.dump(self.profile.to_dict(), f, indent=2)
            print(f"Saved demand profile to {DEMAND_PROFILE_PATH}")
        except Exception as e:
            print(f"Error saving demand profile: {e}")

    def save_weights(self):
        """Save current stop weights (BASE WEIGHTS) to JSON file."""
        try:
            STOP_WEIGHTS_PATH.parent.mkdir(parents=True, exist_ok=True)

            # Reconstruct ID -> BaseWeight map
            weights_to_save = {}
            # Use fullname_to_id to reverse map
            for full_name, base_weight in self.stop_weights_by_full_name.items():
                if full_name in self.fullname_to_id:
                    stop_id = self.fullname_to_id[full_name]
                    weights_to_save[stop_id] = base_weight
            
            with open(STOP_WEIGHTS_PATH, "w") as f:
                json.dump(weights_to_save, f, indent=2)
            print(f"Saved stop weights to {STOP_WEIGHTS_PATH}")
        except Exception as e:
            print(f"Error saving stop weights: {e}")

    def clean_stop_name(self, name: str) -> str:
        """Utility to clean stop names consistently with loader."""
        return clean_stop_name(name)

    def update_profile(self, params: Dict):
        """
        Update the demand profile parameters dynamically.
        Params expected format:
        {
            "base_demand_rate": float,
            "peaks": [...],
            "line_weights": {"line_num": float, ...},
            "stop_weights": {"stop_name_or_id": float, ...}
        }
        """
        if "base_demand_rate" in params:
            self.profile.base_demand_rate = float(params["base_demand_rate"])

        if "peaks" in params and isinstance(params["peaks"], list):
            new_peaks = []
            for p_data in params["peaks"]:
                new_peaks.append(
                    Peak(
                        time=float(p_data.get("time", 0)),
                        width=float(p_data.get("width", 60)),
                        height=float(p_data.get("height", 100)),
                    )
                )
            self.profile.peaks = new_peaks

        if "stop_weights" in params:
            self.file_weights.update(params["stop_weights"])
            # Re-initialize weights if we have active stops
            if self.current_stops:
                self.initialize_weights(self.current_stops, self.current_blocks)

        print(
            f"Updated demand profile. Base: {self.profile.base_demand_rate}, Peaks: {len(self.profile.peaks)}"
        )

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

    def initialize_weights(self, stops: List[StopState], blocks: List[TramBlock]):
        """
        Initialize weights for all provided stops and lines.
        Also builds the global reachability map for the gravity model.
        """
        self.current_stops = stops
        self.current_blocks = blocks

        self.stop_weights = {}
        self.stop_weights_by_full_name = {}
        self.fullname_to_id = {}
        self.total_system_weight = 0.0
        self.accessibility_scores = {}

        # 1. Build Global Direct Reachability Map
        #    Structure: OriginFullName -> {DestFullName -> MinDistance}
        #    Also map: OriginFullName -> {DestFullName -> Set[LineID]}
        self.global_reachability = {}
        self.od_lines = {}
        # Cache for gravity model weights: OriginFullName -> (List[DestNames], List[Weights])
        self.cached_gravity_weights = {}

        boarding_capable_full_names = set()

        for block in blocks:
            ln = block.line_number
            for trip in block.trips:
                # Skip trips that start or end at depot (likely deadhead/repositioning trips)
                if self._is_depot_trip(trip):
                    self._skipped_depot_trips_count += 1
                    continue

                for i, stop_time_origin in enumerate(trip.stop_times):
                    origin = stop_time_origin.full_name
                    if not origin:
                        continue

                    # Skip technical stops (Depots/Point stops)
                    if origin.startswith("PH") or origin.startswith("PT"):
                        continue

                    if origin not in self.global_reachability:
                        self.global_reachability[origin] = {}
                        self.od_lines[origin] = {}

                    origin_dist = stop_time_origin.shape_dist_traveled

                    for stop_time_dest in trip.stop_times[i + 1 :]:
                        dest = stop_time_dest.full_name
                        if not dest:
                            continue

                        # Skip technical stops as destinations too
                        if dest.startswith("PH") or dest.startswith("PT"):
                            continue

                        # Distance calculation
                        dist = max(
                            50.0, stop_time_dest.shape_dist_traveled - origin_dist
                        )

                        # Update Minimum Distance
                        if (
                            dest not in self.global_reachability[origin]
                            or dist < self.global_reachability[origin][dest]
                        ):
                            self.global_reachability[origin][dest] = dist

                        # Track Lines serving this pair
                        if dest not in self.od_lines[origin]:
                            self.od_lines[origin][dest] = set()
                        self.od_lines[origin][dest].add(ln)

                        # Mark origin as capable of boarding
                        boarding_capable_full_names.add(origin)

        # 2. Initialize stop weights
        for stop in stops:
            # Default base weight
            weight = 1.0

            # Try to get custom weight from config
            if stop.stop_id in self.file_weights:
                weight = self.file_weights[stop.stop_id]
            elif stop.name in self.file_weights:
                weight = self.file_weights[stop.name]
            else:
                # Fallback: substring match
                for key in sorted(self.file_weights.keys(), key=len, reverse=True):
                    if key in stop.name:
                        weight = self.file_weights[key]
                        break

            # If not boarding capable, we might want to reduce its generation potential?
            # But for gravity model (attraction), it needs full weight.
            # We accept that termini have weights.

            # Store BASE weight for Attraction (Mass)
            if stop.full_name:
                self.stop_weights_by_full_name[stop.full_name] = weight
                self.fullname_to_id[stop.full_name] = stop.stop_id
            
            # Initialize Generation Weight to 0.0 (will be updated in Step 3 if active)
            self.stop_weights[stop.stop_id] = 0.0

            # Only add to total system weight if it can actually generate passengers?
            # If we add Terminus to total_weight, it dilutes the global rate.
            # But get_arrival_rate uses stop_weight / total_weight.
            # If Terminus has weight but generates 0 passengers (checked later),
            # then we are "wasting" part of the global demand on the terminus.
            # ideally total_system_weight should be sum of weights of BOARDING stops.

            if stop.full_name in boarding_capable_full_names:
                self.total_system_weight += weight

        # 3. Pre-calculate Gravity Weights for all origins AND update Stop Weights based on Accessibility
        print("Pre-calculating gravity weights and accessibility scores...")
        
        # We need to rebuild total_system_weight based on the new accessibility-weighted values
        self.total_system_weight = 0.0
        
        for origin in self.global_reachability:
            destinations_dict = self.global_reachability[origin]
            if not destinations_dict:
                # If no destinations, accessibility is 0. 
                if origin in self.fullname_to_id:
                    stop_id = self.fullname_to_id[origin]
                    self.stop_weights[stop_id] = 0.0
                    self.accessibility_scores[stop_id] = 0.0
                continue

            dest_names = list(destinations_dict.keys())
            dest_weights = []
            accessibility_sum = 0.0

            for d_name in dest_names:
                dist = destinations_dict[d_name]
                # Use Base Weight for Attraction (Mass)
                stop_mass = self.stop_weights_by_full_name.get(d_name, 1.0)
                # Gravity Formula
                w = stop_mass / (dist + 800.0)
                dest_weights.append(w)
                accessibility_sum += w

            self.cached_gravity_weights[origin] = (dest_names, dest_weights)

            # Update Generation Weight based on Accessibility
            # We multiply the Base Weight (User Input) by the Accessibility Score
            if origin in self.fullname_to_id:
                stop_id = self.fullname_to_id[origin]
                base_weight = self.stop_weights_by_full_name.get(origin, 1.0)
                
                new_gen_weight = base_weight * accessibility_sum
                self.stop_weights[stop_id] = new_gen_weight
                self.accessibility_scores[stop_id] = accessibility_sum
                self.total_system_weight += new_gen_weight

        print(
            f"Initialized weights for {len(stops)} stops. Boarding-capable: {len(boarding_capable_full_names)}. Total system weight: {self.total_system_weight:.2f}"
        )
        print(
            f"Initialized global reachability for {len(self.global_reachability)} origins"
        )
        print(f"Skipped {self._skipped_depot_trips_count} depot/reposition trips when building reachability")

        self.last_departure_by_stop_id = {}
        for block in blocks:
            for trip in block.trips:
                if self._is_depot_trip(trip):
                    continue
                for st in trip.stop_times:
                    if not st.full_name:
                        continue
                    stop_id = self._get_stop_id_by_name(st.full_name)
                    if not stop_id:
                        continue
                    prev = self.last_departure_by_stop_id.get(stop_id, -1)
                    if st.departure_time_minutes > prev:
                        self.last_departure_by_stop_id[stop_id] = st.departure_time_minutes

        print(f"Computed last departures for {len(self.last_departure_by_stop_id)} stops.")

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

    def _select_destination_gravity(
        self, origin_full_name: str
    ) -> Optional[Tuple[str, str]]:
        """
        Select a destination and a valid target line using the gravity model.
        Returns (target_line, destination_stop_id) or None.
        """
        # 1. Get cached probabilities
        if origin_full_name not in self.cached_gravity_weights:
            return None

        dest_names, dest_weights = self.cached_gravity_weights[origin_full_name]

        if not dest_names:
            return None

        # 2. Select Destination (Fast random choice)
        destination_full_name = random.choices(dest_names, weights=dest_weights, k=1)[0]

        # 3. Select a valid line for this O-D pair
        # We pick one randomly among those that serve this direct connection
        valid_lines = list(self.od_lines[origin_full_name][destination_full_name])
        target_line = random.choice(valid_lines)

        # Previous implementation relied on full_name being stored in destination_stop_id
        # because PassengerManager compares it against stop_time.full_name.
        # So we return the full_name directly.
        return target_line, destination_full_name

    def _get_stop_id_by_name(self, full_name: str) -> Optional[str]:
        # Simple cache or search.
        # Since we need this frequent, let's build a map in initialize_weights.
        # But for now, let's do a linear search on current_stops (inefficient but safe)
        # Better: Add `self.fullname_to_id` in `initialize_weights`.
        if hasattr(self, "fullname_to_id") and full_name in self.fullname_to_id:
            return self.fullname_to_id[full_name]

        for s in self.current_stops:
            if s.full_name == full_name:
                return s.stop_id
        return None

    def _is_depot_stop(self, full_name: str) -> bool:
        """Return True if a stop name points to a depot/garage or is a technical stop."""
        if not full_name:
            return False
        fn = full_name.lower()
        if fn.startswith("ph") or fn.startswith("pt"):
            return True
        return False

    def _is_depot_trip(self, trip) -> bool:
        """Return True if a trip appears to start or end at a depot stop."""
        if not trip.stop_times:
            return False
        start_fn = trip.stop_times[0].full_name or ""
        end_fn = trip.stop_times[-1].full_name or ""
        return self._is_depot_stop(start_fn) or self._is_depot_stop(end_fn)

    def _has_future_service(self, origin_full_name: str, destination_full_name: str, time_minutes: float) -> bool:
        """Return True if there exists a trip after time_minutes that serves origin -> destination.

        This checks all known blocks and their trips on lines that serve the O-D pair.
        """

        if origin_full_name not in self.od_lines:
            return False
        if destination_full_name not in self.od_lines[origin_full_name]:
            return False

        valid_lines = self.od_lines[origin_full_name][destination_full_name]

        found_but_too_long_or_late = False
        for block in self.current_blocks:
            if block.line_number not in valid_lines:
                continue
            for trip in block.trips:
                if self._is_depot_trip(trip):
                    continue

                origin_td = None
                dest_td = None
                for st in trip.stop_times:
                    if st.full_name == origin_full_name:
                        origin_td = st.departure_time_minutes
                    if st.full_name == destination_full_name:
                        dest_td = st.departure_time_minutes

                if origin_td is not None and dest_td is not None:
                    if origin_td <= time_minutes or dest_td < origin_td:
                        continue

                    wait_minutes = origin_td - time_minutes
                    trip_duration = dest_td - origin_td

                    if (
                        wait_minutes <= self.max_wait_to_board_minutes
                        and trip_duration <= self.max_allowed_trip_duration_minutes
                    ):
                        return True

                    found_but_too_long_or_late = True

        if found_but_too_long_or_late:
            self._skipped_generation_due_to_long_trip += 1

        return False

    def generate_arrivals(
        self, stop_state: StopState, time_minutes: float, delta_time: float
    ) -> List[Passenger]:

        # Skip generation for technical stops or depot stops
        if stop_state.full_name.startswith("PH") or stop_state.full_name.startswith(
            "PT"
        ) or self._is_depot_stop(stop_state.full_name):
            return []

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

        last_dep = self.last_departure_by_stop_id.get(stop_state.stop_id)
        if last_dep is not None and time_minutes >= last_dep:
            self._skipped_generation_after_service += num_arrivals
            return []

        for i in range(num_arrivals):
            attempts = 0
            chosen = None
            while attempts < 3:
                line_and_dest = self._select_destination_gravity(stop_state.full_name)
                if not line_and_dest:
                    break

                target_line, destination_stop_id = line_and_dest
                if self._is_depot_stop(destination_stop_id):
                    self._skipped_generation_depot_destination += 1
                    attempts += 1
                    continue
                if self._has_future_service(stop_state.full_name, destination_stop_id, time_minutes):
                    chosen = (target_line, destination_stop_id)
                    break

                attempts += 1

            if not chosen:
                self._skipped_generation_no_future_service += 1
                continue

            target_line, destination_stop_id = chosen

            passenger_id = f"p_{stop_state.stop_id}_{int(time_minutes * 10)}_{i}"
            passenger = Passenger(
                passenger_id=passenger_id,
                origin_stop_id=stop_state.stop_id,
                destination_stop_id=destination_stop_id,
                target_line=target_line,
                arrival_time_minutes=time_minutes,
                status="WAITING",
            )
            new_passengers.append(passenger)
            stop_state.total_arrived += 1

        return new_passengers
