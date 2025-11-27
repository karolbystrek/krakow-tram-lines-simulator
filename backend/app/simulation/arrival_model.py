"""
Passenger arrival and destination selection models
"""
import random
from typing import List, Dict, Optional
from .models import Trip, StopTime
from .passenger_model import Passenger, StopState


class ArrivalRateModel:
    """
    Models passenger arrival rates at stops based on:
    - Time of day (hour)
    - Day of week (affects which service is active)
    - Stop characteristics (city center vs. suburbs)
    """
    
    def __init__(self):
        # Base arrival rate (passengers per minute) for average stop
        # Reduced from 0.5 to 0.2 to prevent excessive accumulation
        # During rush hour: 0.2 * 3.0 = 0.6 passengers/min = 36 passengers/hour per stop
        self.base_arrival_rate = 0.2
        
        # Time-of-day multipliers
        self.rush_hour_multiplier = 4.0  # 7-9 AM, 4-6 PM (increased from 2.0)
        self.off_peak_multiplier = 0.5   # Reduced from 0.7
        self.night_multiplier = 0.1      # Reduced from 0.2
        
        # Rush hour definitions
        self.morning_rush = [7, 8, 9]  # 7-9 AM
        self.evening_rush = [16, 17, 18]  # 4-6 PM
        
        # Stop-specific rate overrides (can be configured later)
        self.stop_specific_rates: Dict[str, float] = {}
    
    def get_arrival_rate(
        self, 
        stop_id: str, 
        hour: int, 
        service_id: str
    ) -> float:
        """
        Returns passengers per minute arriving at this stop
        
        Uses:
        - Base rate per stop (could be from config or historical data)
        - Time-of-day multiplier (rush hour = 2x, night = 0.2x)
        - Service multiplier (weekday vs. weekend)
        """
        # Check for stop-specific override
        if stop_id in self.stop_specific_rates:
            base_rate = self.stop_specific_rates[stop_id]
        else:
            base_rate = self.base_arrival_rate
        
        # Determine time-of-day multiplier
        if hour in self.morning_rush or hour in self.evening_rush:
            multiplier = self.rush_hour_multiplier
        elif 22 <= hour or hour < 5:  # Night hours (10 PM - 5 AM)
            multiplier = self.night_multiplier
        else:
            multiplier = self.off_peak_multiplier
        
        # Service multiplier (weekend services might have different rates)
        service_multiplier = 1.0
        if service_id in ["service_2", "service_3"]:  # Saturday, Sunday
            service_multiplier = 0.8  # Slightly lower on weekends
        
        return base_rate * multiplier * service_multiplier
    
    def generate_arrivals(
        self, 
        stop_state: StopState, 
        time_minutes: float, 
        delta_time: float,
        service_id: str = "service_1"
    ) -> List[Passenger]:
        """
        Generate new passengers arriving at stop during time delta
        
        Algorithm:
        1. Get arrival rate for current hour
        2. Calculate expected arrivals = rate * delta_time
        3. Use Poisson approximation to determine actual arrivals
        4. For each arrival, assign destination (see destination model)
        5. Create Passenger objects and add to waiting queue
        """
        hour = int(time_minutes // 60) % 24
        arrival_rate = self.get_arrival_rate(
            stop_state.stop_id, 
            hour, 
            service_id
        )
        
        # Update stop state arrival rate
        stop_state.arrival_rate_per_minute = arrival_rate
        
        # Calculate expected arrivals (Poisson process approximation)
        expected_arrivals = arrival_rate * delta_time
        
        # Generate arrivals using Poisson approximation
        # For small expected values, use simple probability
        new_passengers = []
        
        if expected_arrivals >= 1.0:
            # For high rates, generate multiple passengers
            num_arrivals = int(expected_arrivals) + (1 if random.random() < (expected_arrivals % 1.0) else 0)
        else:
            # For low rates, use probability
            num_arrivals = 1 if random.random() < expected_arrivals else 0
        
        # Generate passengers (destination will be assigned when boarding)
        for i in range(num_arrivals):
            passenger_id = f"p_{stop_state.stop_id}_{int(time_minutes * 10)}_{i}"
            passenger = Passenger(
                passenger_id=passenger_id,
                origin_stop_id=stop_state.stop_id,
                destination_stop_id="",  # Will be set when boarding
                arrival_time_minutes=time_minutes,
                status="WAITING"
            )
            new_passengers.append(passenger)
            stop_state.total_arrived += 1
        
        return new_passengers


class DestinationModel:
    """
    Models passenger destination selection
    """
    
    def select_destination(
        self, 
        origin_stop_id: str, 
        line_number: str,
        trip: Trip
    ) -> Optional[str]:
        """
        Select destination stop for a passenger
        
        Strategy: Weighted random selection from stops further along the line
        - Closer stops more likely for short trips
        - Some stops (end stops) are more common destinations
        
        Returns: destination_stop_id (stop_num) or None if no valid destination
        """
        if not trip.stop_times or len(trip.stop_times) < 2:
            return None
        
        # Find origin stop index in trip
        origin_idx = None
        for i, stop_time in enumerate(trip.stop_times):
            if stop_time.stop_num == origin_stop_id:
                origin_idx = i
                break
        
        if origin_idx is None or origin_idx >= len(trip.stop_times) - 1:
            return None
        
        # Get possible destinations (stops after origin)
        possible_destinations = trip.stop_times[origin_idx + 1:]
        
        if not possible_destinations:
            return None
        
        # Weight destinations by distance (closer = more likely)
        # Also give higher weight to last stop (common destination)
        weights = []
        for i, stop_time in enumerate(possible_destinations):
            # Base weight: inverse of distance (closer = higher weight)
            distance_weight = 1.0 / (i + 1)
            
            # Bonus for last stop (common destination)
            if i == len(possible_destinations) - 1:
                distance_weight *= 2.0
            
            weights.append(distance_weight)
        
        # Normalize weights
        total_weight = sum(weights)
        if total_weight == 0:
            return possible_destinations[0].stop_num
        
        # Select destination based on weights
        r = random.random() * total_weight
        cumulative = 0
        for i, weight in enumerate(weights):
            cumulative += weight
            if r <= cumulative:
                return possible_destinations[i].stop_num
        
        # Fallback to last stop
        return possible_destinations[-1].stop_num

