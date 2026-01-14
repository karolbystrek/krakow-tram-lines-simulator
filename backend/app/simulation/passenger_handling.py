from typing import Tuple

from .models import TramBlock, StopTime
from .passenger_model import StopState, TramState


class PassengerManager:
    """
    Manages passenger boarding and alighting operations
    """

    def __init__(self):
        pass

    def _is_stop_reachable(
        self,
        tram_block: TramBlock,
        current_stop_time: StopTime,
        destination_stop_id: str,
    ) -> bool:
        """
        Check if a stop is reachable from current position in the future path of the block.
        """
        found_current = False
        for trip in tram_block.trips:
            for st in trip.stop_times:
                if not found_current:
                    # We need to find where we are first (exact object match or ID+time)
                    if st == current_stop_time:
                        found_current = True
                    continue

                # Once we found current stop, all subsequent stops are potential destinations
                if st.full_name == destination_stop_id:
                    return True
        return False

    def handle_tram_at_stop(
        self,
        tram_block: TramBlock,
        stop_time: StopTime,
        current_time_minutes: float,
        stop_state: StopState,
        tram_state: TramState,
        skip_alighting: bool = False,
    ) -> Tuple[int, int]:
        """
        Handle passenger boarding and alighting at a stop

        Args:
            skip_alighting: If True, skip alighting step (useful when multiple stops share coordinates)

        Returns: (passengers_boarded, passengers_alighted)

        Steps:
        1. Alighting: Passengers alight if their destination_stop_id matches current stop.
        2. Boarding: Board passengers if:
            - destination is reachable in the block's future path
            - capacity allows
        """
        passengers_alighted = 0
        passengers_boarded = 0

        # Step 1: Alighting
        if not skip_alighting:
            # Passengers alight ONLY if they reached their destination
            # No more forced alighting at trip termini!
            passengers_to_alight = [
                p
                for p in tram_state.passengers
                if p.status == "ON_TRAM"
                and p.destination_stop_id == stop_time.full_name
            ]

            for passenger in passengers_to_alight:
                passenger.status = "ALIGHTED"
                passenger.alighting_time_minutes = current_time_minutes
                passenger.current_tram_id = None
                passengers_alighted += 1

            stop_state.total_alighted += passengers_alighted

            # Remove alighted passengers from tram
            tram_state.passengers = [
                p for p in tram_state.passengers if p.status == "ON_TRAM"
            ]
            tram_state.update_occupancy()

        # Step 2: Boarding
        # Get waiting passengers at this stop
        waiting_passengers = [
            p for p in stop_state.waiting_passengers if p.status == "WAITING"
        ]

        if not waiting_passengers:
            return passengers_boarded, passengers_alighted

        # Try to board passengers
        passengers_to_remove = []
        for passenger in waiting_passengers:
            # 1. Check if capacity allows
            available_space = tram_state.get_available_space()
            if available_space <= 0:
                break

            # 2. Check if destination is reachable with this tram block
            if not self._is_stop_reachable(
                tram_block, stop_time, passenger.destination_stop_id
            ):
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
        remove_ids = set(p.passenger_id for p in passengers_to_remove)
        stop_state.waiting_passengers = [
            p
            for p in stop_state.waiting_passengers
            if p.passenger_id not in remove_ids and p.status == "WAITING"
        ]

        # Update tram occupancy
        tram_state.update_occupancy()

        return passengers_boarded, passengers_alighted
