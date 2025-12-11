"""
Passenger arrival and destination selection models
"""
import random
import math
from typing import List, Dict, Optional
from .models import Trip, StopTime
from .passenger_model import Passenger, StopState


class ArrivalRateModel:
    """
    Models passenger arrival rates:
    - Weekdays: sharp double-peaked Gaussian profile (morning/evening rush)
    - Weekends: simple time-of-day multipliers (quieter overall)
    """

    def __init__(self):
        self.offpeak_rate = 0.05

        # Peak amplitudes (pass/min added during peak)
        self.morning_peak_amplitude = 2
        self.evening_peak_amplitude = 1.5
        self.base_amplitude = 0.3

        # Gaussian width – narrow for sharp real-life peaks (20–30 min)
        self.morning_width = 40
        self.evening_width = 50
        self.base_width = 10*60
        # Peak times
        self.morning_peak_time = 7.5 * 60   # 7:30
        self.evening_peak_time = 16 * 60  # 16:00
        self.noon = 12*60

        # Weekend multipliers
        self.rush_hour_multiplier = 1.6
        self.off_peak_multiplier = 0.6
        self.night_multiplier = 0.08

        # Rush hour times for weekends
        self.morning_rush = [7, 8, 9]
        self.evening_rush = [16, 17, 18]

        # Optional overrides
        self.stop_specific_rates: Dict[str, float] = {}

    def gaussian(self, x: float, mu: float, sigma: float) -> float:
        """Calculate Gaussian value."""
        if sigma == 0:
            return 0.0
        return math.exp(-((x - mu)**2) / (2 * sigma * sigma))

    def weekday_arrival_rate(self, time_minutes: float, stop_id: str) -> float:
        """High-fidelity weekday arrival model with sharp peaks."""

        t = time_minutes % 1440

        base = self.stop_specific_rates.get(stop_id, self.offpeak_rate)
        g1 = self.gaussian(t, self.morning_peak_time, self.morning_width)
        morning_peak = self.morning_peak_amplitude * g1
        g2 = self.gaussian(t, self.evening_peak_time, self.evening_width)
        evening_peak = self.evening_peak_amplitude * g2
        g3 = self.gaussian(t, self.noon, self.base_width)
        base_gauss = self.base_amplitude * g3
        return base + morning_peak + evening_peak + base_gauss

    def weekend_arrival_rate(self, time_minutes: float, stop_id: str) -> float:
        """Weekend model remains multiplicative but separate from weekday logic."""
        base_rate = self.stop_specific_rates.get(stop_id, self.offpeak_rate)

        hour = int(time_minutes // 60) % 24

        if hour in self.morning_rush or hour in self.evening_rush:
            multiplier = self.rush_hour_multiplier
        elif 22 <= hour or hour < 5:
            multiplier = self.night_multiplier
        else:
            multiplier = self.off_peak_multiplier

        service_multiplier = 0.7
        return base_rate * multiplier * service_multiplier

    def get_arrival_rate(
        self,
        stop_id: str,
        time_minutes: float,
        service_id: str
    ) -> float:
        """Final arrival rate selection."""

        if service_id in ["service_1", "service_4", "service_5"]:
            return self.weekday_arrival_rate(time_minutes, stop_id)
        else:
            return self.weekend_arrival_rate(time_minutes, stop_id)

    def generate_arrivals(
        self,
        stop_state: StopState,
        time_minutes: float,
        delta_time: float,
        service_id: str = "service_1"
    ) -> List[Passenger]:

        arrival_rate = self.get_arrival_rate(
            stop_state.stop_id,
            time_minutes,
            service_id
        )

        stop_state.arrival_rate_per_minute = arrival_rate

        expected_arrivals = arrival_rate * delta_time
        new_passengers = []

        if expected_arrivals >= 1.0:
            num_arrivals = (
                int(expected_arrivals)
                + (1 if random.random() < (expected_arrivals % 1.0) else 0)
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
                status="WAITING"
            )
            new_passengers.append(passenger)
            stop_state.total_arrived += 1

        return new_passengers


class DestinationModel:
    """Models passenger destination selection."""

    def select_destination(
        self,
        origin_stop_id: str,
        line_number: str,
        trip: Trip
    ) -> Optional[str]:

        if not trip.stop_times or len(trip.stop_times) < 2:
            return None

        origin_idx = None
        for i, stop_time in enumerate(trip.stop_times):
            if stop_time.stop_num == origin_stop_id:
                origin_idx = i
                break

        if origin_idx is None or origin_idx >= len(trip.stop_times) - 1:
            return None

        possible_destinations = trip.stop_times[origin_idx + 1:]
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
