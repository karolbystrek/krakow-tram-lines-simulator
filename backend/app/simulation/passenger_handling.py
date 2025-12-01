"""
Passenger boarding and alighting logic
"""
from typing import Tuple, Dict
from .models import TramBlock, StopTime
from .passenger_model import Passenger, StopState, TramState
from .arrival_model import DestinationModel


class PassengerManager:
    """
    Manages passenger boarding and alighting operations
    """
    
    def __init__(self):
        self.destination_model = DestinationModel()
    
    def handle_tram_at_stop(
        self,
        tram_block: TramBlock,
        stop_time: StopTime,
        current_time_minutes: float,
        stop_state: StopState,
        tram_state: TramState,
        skip_alighting: bool = False
    ) -> Tuple[int, int]:
        """
        Handle passenger boarding and alighting at a stop
        
        Args:
            skip_alighting: If True, skip alighting step (useful when multiple stops share coordinates)
        
        Returns: (passengers_boarded, passengers_alighted)
        
        Steps:
        1. Alighting: Find all passengers on tram with destination = current stop
        2. Boarding: Get waiting passengers, board up to capacity
        """
        passengers_alighted = 0
        passengers_boarded = 0
        
        # Step 1: Alighting (skip if requested - used when multiple stops share coordinates)
        if not skip_alighting:
            # Find passengers whose destination is this stop
            # Only alight passengers whose destination exactly matches this stop's stop_num
            passengers_to_alight = [
                p for p in tram_state.passengers 
                if p.status == "ON_TRAM" and p.destination_stop_id == stop_time.stop_num
            ]
            
            for passenger in passengers_to_alight:
                passenger.status = "ALIGHTED"
                passenger.alighting_time_minutes = current_time_minutes
                passenger.current_tram_id = None
                passengers_alighted += 1
            
            # Remove alighted passengers from tram
            # Keep only passengers that are still ON_TRAM
            tram_state.passengers = [
                p for p in tram_state.passengers 
                if p.status == "ON_TRAM"
            ]
            tram_state.update_occupancy()
        
        # Step 2: Boarding
        # Get waiting passengers at this stop
        waiting_passengers = [
            p for p in stop_state.waiting_passengers 
            if p.status == "WAITING"
        ]
        
        if not waiting_passengers:
            return passengers_boarded, passengers_alighted
        
        # Get active trip for destination assignment
        active_trip = tram_block.get_active_trip(current_time_minutes)
        
        if not active_trip:
            return passengers_boarded, passengers_alighted
        
        # Try to board passengers
        passengers_to_remove = []
        for passenger in waiting_passengers:
            # Recalculate available space for each passenger (in case capacity changed)
            available_space = tram_state.get_available_space()
            
            if available_space <= 0:
                break
            
            # Assign destination if not already set
            if not passenger.destination_stop_id or passenger.destination_stop_id == "":
                destination = self.destination_model.select_destination(
                    stop_time.stop_num,
                    tram_block.line_number,
                    active_trip
                )
                if destination:
                    passenger.destination_stop_id = destination
                else:
                    # Skip if no valid destination (can't board without destination)
                    # This can happen if we're at the last stop or origin not found in trip
                    continue
            
            # Board the passenger
            passenger.status = "ON_TRAM"
            passenger.boarding_time_minutes = current_time_minutes
            passenger.current_tram_id = tram_block.block_id
            
            # Move to tram
            tram_state.passengers.append(passenger)
            passengers_to_remove.append(passenger)
            passengers_boarded += 1
            stop_state.total_boarded += 1
            
            # Update occupancy immediately so next iteration has correct available_space
            tram_state.update_occupancy()
        
        # Remove boarded passengers from waiting queue
        # Use list comprehension to filter out boarded passengers
        remove_ids = set(p.passenger_id for p in passengers_to_remove)
        stop_state.waiting_passengers = [
            p for p in stop_state.waiting_passengers 
            if p.passenger_id not in remove_ids and p.status == "WAITING"
        ]
        
        # Also clean up any passengers that are no longer WAITING (defensive)
        stop_state.waiting_passengers = [
            p for p in stop_state.waiting_passengers 
            if p.status == "WAITING"
        ]
        
        # Update tram occupancy
        tram_state.update_occupancy()
        
        return passengers_boarded, passengers_alighted

