import asyncio
import threading
from typing import Any, Dict, List, Optional, Tuple

import simpy

from .arrival_model import ArrivalRateModel
from .loader import load_tram_blocks, load_tram_stops, clean_stop_name
from .models import TramBlock, Trip
from .passenger_handling import PassengerManager
from .passenger_model import StopState, TramState


class SimulationEngine:
    def __init__(self, service_id: str = "service_1"):
        print(f"Initializing simulation engine with service: {service_id}")
        self.blocks: List[TramBlock] = []
        self.running = False
        self.paused = False
        self.start_time_minutes = 0
        self.end_time_minutes = 24 * 60
        self.task = None  # Keep task for potential cancellation if needed later
        self.service_id = service_id
        self.simulation_speed_factor = 1.0  # Default: 1 real sec = 1 sim minute

        # SimPy environment
        self.env = simpy.Environment()
        self.simpy_thread = None
        self.simpy_running = False
        self._time_lock = threading.Lock()

        # Cache for all services
        self.cached_services: Dict[str, List[TramBlock]] = {}
        self.service_bounds: Dict[str, Tuple[int, int]] = {}

        # Passenger simulation components
        self.passenger_manager = PassengerManager()
        self.arrival_model = ArrivalRateModel()
        self.stop_states: Dict[str, StopState] = {}
        self.tram_states: Dict[str, TramState] = {}
        self.max_wait_minutes: int = 60

        # Statistics
        self.stats = {"total_boarded": 0, "total_alighted": 0, "hourly_stats": {}, "total_removed_timeout": 0}

        # Time-series data for charts
        self.stop_passenger_history: Dict[str, List[Tuple[float, int]]] = {}  # stop_id -> [(time, waiting_count), ...]
        self.tram_occupancy_history: Dict[str, List[Tuple[float, int]]] = {}  # tram_id -> [(time, occupancy), ...]
        self.last_history_update = 0.0  # Track last time we updated history

        # Lazy-load services: Only load the needed service initially for faster startup
        # Other services will be loaded on-demand when switching services
        print(f"Loading initial service: {service_id}...")
        self._load_service(service_id)

    @property
    def current_time_minutes(self) -> float:
        """Get current simulation time from simpy environment."""
        with self._time_lock:
            return self.env.now if hasattr(self, "env") and self.env else 0.0

    async def start(self):
        """Start the simulation loop."""
        if self.running:
            return

        self.running = True
        self.paused = True

        # Load blocks from cache if not already loaded
        if not self.blocks:
            print(f"Starting simulation with service: {self.service_id}")
            if self.service_id in self.cached_services:
                self.blocks = self.cached_services[self.service_id]
                self.start_time_minutes, self.end_time_minutes = self.service_bounds[
                    self.service_id
                ]

                print(
                    f"Simulation range: {self.start_time_minutes // 60:02d}:{self.start_time_minutes % 60:02d} - {self.end_time_minutes // 60:02d}:{self.end_time_minutes % 60:02d}"
                )
            else:
                print(f"Error: Service {self.service_id} not found in cache!")
                self.blocks = []

        # Initialize passenger simulation (only if blocks are loaded)
        if self.blocks:
            # Stops will be passed from main.py if available, otherwise load them
            self._initialize_passenger_simulation(getattr(self, "_cached_stops", None))
        else:
            print(
                "Warning: No blocks loaded, skipping passenger simulation initialization"
            )

        # Initialize and start simpy
        self._reset_env(self.start_time_minutes)

        print("Simulation started.")
        self.task = asyncio.create_task(self._loop())

    def _load_service(self, service_id: str):
        """Load a service into cache if not already loaded."""
        if service_id in self.cached_services:
            # Still need to set _cached_stops even if service is cached
            all_blocks = self.cached_services[service_id]
            active_full_names = set()
            for block in all_blocks:
                for trip in block.trips:
                    for stop_time in trip.stop_times:
                        active_full_names.add(stop_time.full_name)
            
            self._cached_stops = load_tram_stops(active_full_names=active_full_names)
            return

        print(f"Loading {service_id}...")
        blocks_by_line = load_tram_blocks(service=service_id)
        all_blocks = []
        for line_blocks in blocks_by_line.values():
            all_blocks.extend(line_blocks)

        self.cached_services[service_id] = all_blocks

        # Collect active stop names for filtering
        active_full_names = set()
        for block in all_blocks:
            for trip in block.trips:
                for stop_time in trip.stop_times:
                    active_full_names.add(stop_time.full_name)

        print(
            f"Filtering stops for {service_id}, found {len(active_full_names)} unique stop names in schedule"
        )
        self._cached_stops = load_tram_stops(active_full_names=active_full_names)

        # Calculate bounds for this service
        min_time = 24 * 60
        max_time = 0

        for block in all_blocks:
            for trip in block.trips:
                trip.initialize_shape_indices()
                start = trip.get_start_time_minutes()
                end = trip.get_end_time_minutes()
                if start < min_time:
                    min_time = start
                if end > max_time:
                    max_time = end

        if not all_blocks:
            min_time = 0
            max_time = 24 * 60

        self.service_bounds[service_id] = (min_time, max_time)
        
        # Restore old behavior: Simulation runs only during tram activity hours
        self.start_time_minutes = min_time
        self.end_time_minutes = max_time
        
        print(
            f"Loaded {service_id}: {len(all_blocks)} blocks, range {min_time // 60:02d}:{min_time % 60:02d} - {max_time // 60:02d}:{max_time % 60:02d}"
        )

    async def reload_service(self, service_id: str):
        """Reload the simulation with a new service ID."""
        print(f"Reloading simulation with service: {service_id}")

        # Load the service if not already cached
        self._load_service(service_id)

        # Stop current simulation
        await self.stop()

        # Clear existing data
        self.blocks = []
        self.service_id = service_id
        # Clear passenger simulation state
        self.stop_states = {}
        self.tram_states = {}

        # Restart simulation (start() will pick up new service from cache and use cached stops)
        await self.start()

    async def stop(self):
        """Stop the simulation."""
        self.running = False
        self.simpy_running = False
        if self.task:
            self.task.cancel()
            try:
                await self.task
            except asyncio.CancelledError:
                pass

        # Wait for simpy thread to finish
        if self.simpy_thread and self.simpy_thread.is_alive():
            self.simpy_thread.join(timeout=1.0)

        print("Simulation stopped.")

    def pause(self):
        """Pause the simulation."""
        self.paused = True
        print("Simulation paused.")

    def resume(self):
        """Resume the simulation."""
        self.paused = False
        print("Simulation resumed.")

    def restart(self):
        """Restart the simulation."""
        self.paused = False

        # Reset statistics
        self.stats = {"total_boarded": 0, "total_alighted": 0, "hourly_stats": {}}

        # Reset passenger simulation (use cached stops if available)
        self._initialize_passenger_simulation(getattr(self, "_cached_stops", None))
        # Reset simpy environment/thread
        self._reset_env(self.start_time_minutes)
        print("Simulation restarted.")

    def _run_simpy(self):
        """Run simpy simulation in a separate thread."""
        import time as real_time

        try:
            while self.simpy_running:
                if not self.paused:
                    start_real_time = real_time.time()
                    current_simpy_time = self.env.now
                    next_timeout = min(current_simpy_time + 0.1, self.end_time_minutes)

                    if next_timeout > current_simpy_time:
                        self.env.run(until=next_timeout)

                        elapsed_real = real_time.time() - start_real_time
                        target_real_duration = 0.1 / max(
                            0.1, self.simulation_speed_factor
                        )
                        sleep_time = max(0, target_real_duration - elapsed_real)
                        if sleep_time > 0:
                            real_time.sleep(sleep_time)

                        if self.env.now >= self.end_time_minutes:
                            print("Simulation finished (end time reached).")
                            self.running = False
                            self.simpy_running = False
                            break
                    else:
                        break
                else:
                    real_time.sleep(0.1)
        except Exception as e:
            print(f"Error in simpy thread: {e}")
            import traceback

            traceback.print_exc()
            self.running = False
            self.simpy_running = False

    def _simpy_passenger_update_loop(self):
        """Simpy process for passenger simulation updates."""
        while self.simpy_running and self.env.now < self.end_time_minutes:
            yield self.env.timeout(0.1)

            if self.stop_states:
                self._update_passenger_simulation(delta_time=0.1)

            if self.env.now >= self.end_time_minutes:
                break

    def _tram_lifecycle_process(self, block: TramBlock):
        """Simpy process for a single tram block lifecycle."""
        for trip in block.trips:
            for stop_time in trip.stop_times:
                scheduled_time = stop_time.to_minutes()
                
                # Wait until scheduled time
                if scheduled_time > self.env.now:
                    yield self.env.timeout(scheduled_time - self.env.now)
                
                # Double check we are not past the end time
                if self.env.now >= self.end_time_minutes:
                    return

                # Process arrival at this stop
                self._handle_tram_arrival(block, stop_time)

    def _handle_tram_arrival(self, block: TramBlock, stop_time: Any):
        """Process tram arrival at a stop."""
        current_time = self.env.now
        
        matching_stop_states = self._find_matching_stop_states(stop_time)

        if not matching_stop_states:
            return

        tram_state = self.tram_states.get(block.block_id)
        if not tram_state:
            tram_state = TramState(block_id=block.block_id)
            self.tram_states[block.block_id] = tram_state

        total_boarded = 0
        total_alighted = 0

        for i, stop_state_to_process in enumerate(matching_stop_states):
            should_skip_alighting = i > 0

            boarded, alighted = self.passenger_manager.handle_tram_at_stop(
                block,
                stop_time,
                current_time,
                stop_state_to_process,
                tram_state,
                skip_alighting=should_skip_alighting,
            )
            total_boarded += boarded
            total_alighted += alighted

        self._update_stats(total_boarded, total_alighted, current_time)

    async def _loop(self):
        """Main asyncio loop for WebSocket updates."""
        print("Simulation loop started.")
        while self.running:
            await asyncio.sleep(0.1)

    def _reset_env(self, initial_time: float, start_thread: bool = True):
        """Reset SimPy environment and thread safely."""
        self.simpy_running = False
        if self.simpy_thread and self.simpy_thread.is_alive():
            self.simpy_thread.join(timeout=1.0)

        with self._time_lock:
            self.env = simpy.Environment(initial_time=initial_time)
            self.simpy_running = True
            
            # Start passenger arrival generation loop
            self.env.process(self._simpy_passenger_update_loop())
            
            # Start lifecycle process for each tram block
            for block in self.blocks:
                self.env.process(self._tram_lifecycle_process(block))

        if start_thread:
            self.simpy_thread = threading.Thread(target=self._run_simpy, daemon=True)
            self.simpy_thread.start()

    def get_tram_positions(self) -> List[Dict[str, Any]]:
        """Get current positions of all active trams."""
        trams = []
        for block in self.blocks:
            pos = self._get_tram_position_at_time(block, self.current_time_minutes)
            if pos:
                lat, lon = pos
                tram_state = self.tram_states.get(block.block_id)
                occupancy = tram_state.current_occupancy if tram_state else 0
                max_capacity = tram_state.max_capacity if tram_state else 200
                occupancy_percent = (
                    (occupancy / max_capacity * 100) if max_capacity > 0 else 0
                )

                trams.append(
                    {
                        "id": block.block_id,
                        "line": block.line_number,
                        "lat": lat,
                        "lon": lon,
                        "occupancy": occupancy,
                        "max_capacity": max_capacity,
                        "occupancy_percent": round(occupancy_percent, 1),
                    }
                )
        return trams

    def get_stop_states(self) -> Dict[str, Dict[str, Any]]:
        """Get current passenger states at all stops."""
        stop_data = {}
        for stop_id, stop_state in self.stop_states.items():
            waiting_count = len(
                [p for p in stop_state.waiting_passengers if p.status == "WAITING"]
            )
            stop_data[stop_id] = {
                "waiting_count": waiting_count,
                "total_arrived": stop_state.total_arrived,
                "total_boarded": stop_state.total_boarded,
                "arrival_rate": stop_state.arrival_rate_per_minute,
            }
        return stop_data

    def set_time(self, time_minutes: float):
        """Set the simulation time manually."""
        old_time = self.current_time_minutes
        target_time = max(
            self.start_time_minutes, min(time_minutes, self.end_time_minutes)
        )

        print(
            f"Setting time to: {int(target_time // 60):02d}:{int(target_time % 60):02d} (was {int(old_time // 60):02d}:{int(old_time % 60):02d})"
        )

        try:
            if target_time < old_time:
                print("Time jumped backward, resetting simulation state...")
                self.stats = {
                    "total_boarded": 0,
                    "total_alighted": 0,
                    "hourly_stats": {},
                }
                self._initialize_passenger_simulation(
                    getattr(self, "_cached_stops", None)
                )
                
                # Reset environment to start_time but don't start thread yet
                self._reset_env(self.start_time_minutes, start_thread=False)

                # Fast forward to target time
                self._fast_forward(target_time)

            else:
                # Stop thread temporarily to fast-forward safely
                self.simpy_running = False
                if self.simpy_thread and self.simpy_thread.is_alive():
                    self.simpy_thread.join(timeout=1.0)
                
                self.simpy_running = True
                if target_time > self.env.now:
                    print(f"Fast forwarding from {self.env.now} to {target_time}...")
                    self._fast_forward(target_time)
        except Exception as e:
            print(f"Error during time set operations: {e}")
            import traceback

            traceback.print_exc()

        if self.running and target_time < self.end_time_minutes:
            self.simpy_thread = threading.Thread(target=self._run_simpy, daemon=True)
            self.simpy_thread.start()
        else:
            self.simpy_running = False

    def _fast_forward(self, target_time: float):
        """Fast forward simulation to target time, processing all events."""
        if not self.env:
            return

        try:
            if self.env.now < target_time:
                self.env.run(until=target_time)
        except Exception as e:
            print(f"Error during fast forward: {e}")

    def set_speed(self, speed: float):
        """Set the simulation speed factor."""
        self.simulation_speed_factor = max(0.1, speed)
        print(f"Simulation speed set to: {self.simulation_speed_factor}x")

    def update_generation_params(self, params: Dict[str, Any]):
        """Update passenger generation parameters."""
        if self.arrival_model:
            self.arrival_model.update_profile(params)
            print(f"Updated generation params: {params}")

    def get_generation_params(self) -> Dict[str, Any]:
        """Get current passenger generation parameters."""
        if self.arrival_model and self.arrival_model.profile:
            return self.arrival_model.profile.to_dict()
        return {}

    def save_generation_params(self):
        """Save current generation parameters to file."""
        if self.arrival_model:
            self.arrival_model.save_to_file()

    def get_status(self) -> Dict[str, Any]:
        """Get current simulation status."""
        hours = int(self.current_time_minutes // 60)
        minutes = int(self.current_time_minutes % 60)
        seconds = int((self.current_time_minutes * 60) % 60)
        return {
            "time_str": f"{hours:02d}:{minutes:02d}:{seconds:02d}",
            "time_minutes": self.current_time_minutes,
            "start_time_minutes": self.start_time_minutes,
            "end_time_minutes": self.end_time_minutes,
            "running": self.running,
            "paused": self.paused,
            "speed": self.simulation_speed_factor,
        }

    def _interpolate_position_on_shape(
        self, trip: Trip, start_dist: float, end_dist: float, fraction: float
    ) -> Tuple[float, float]:
        """Interpolate position along the shape path."""
        target_dist = start_dist + (end_dist - start_dist) * fraction

        distances = trip._shape_distances
        if not distances:
            return trip.shape[0]

        for i in range(len(distances) - 1):
            d1 = distances[i]
            d2 = distances[i + 1]

            if d1 <= target_dist <= d2:
                segment_len = d2 - d1
                if segment_len == 0:
                    return trip.shape[i]

                segment_fraction = (target_dist - d1) / segment_len
                lat1, lon1 = trip.shape[i]
                lat2, lon2 = trip.shape[i + 1]

                lat = lat1 + (lat2 - lat1) * segment_fraction
                lon = lon1 + (lon2 - lon1) * segment_fraction
                return lat, lon

        return trip.shape[-1]

    def _get_tram_position_at_time(
        self, block: TramBlock, time_minutes: float
    ) -> Optional[Tuple[float, float]]:
        """Calculate tram position at a specific time in minutes since midnight."""

        active_trip = block.get_active_trip(time_minutes)

        if not active_trip:
            if block.trips:
                first_start = block.trips[0].get_start_time_minutes()
                last_end = block.trips[-1].get_end_time_minutes()

                if first_start <= time_minutes <= last_end:
                    last_trip = None
                    for trip in block.trips:
                        if trip.get_end_time_minutes() <= time_minutes:
                            last_trip = trip
                        else:
                            break

                    if last_trip and last_trip.stop_times:
                        last_stop = last_trip.stop_times[-1]
                        return last_stop.stop_lat, last_stop.stop_lon

            return None

        segment = active_trip.get_current_segment(time_minutes)

        if not segment:
            for stop_time in active_trip.stop_times:
                if stop_time.to_minutes() == time_minutes:
                    return stop_time.stop_lat, stop_time.stop_lon
            return None

        prev_stop, next_stop = segment

        start_time = prev_stop.to_minutes()
        end_time = next_stop.to_minutes()

        if end_time == start_time:
            return prev_stop.stop_lat, prev_stop.stop_lon

        fraction = (time_minutes - start_time) / (end_time - start_time)
        fraction = max(0.0, min(1.0, fraction))

        if active_trip._shape_distances:
            return self._interpolate_position_on_shape(
                active_trip,
                prev_stop.shape_dist_traveled,
                next_stop.shape_dist_traveled,
                fraction,
            )

        lat = prev_stop.stop_lat + (next_stop.stop_lat - prev_stop.stop_lat) * fraction
        lon = prev_stop.stop_lon + (next_stop.stop_lon - prev_stop.stop_lon) * fraction

        return lat, lon

    def _initialize_passenger_simulation(self, stops: Optional[Dict] = None):
        """Initialize passenger simulation state.

        Args:
            stops: Optional pre-loaded stops dict to avoid reloading. If None, loads stops.
        """
        if stops is None:
            stops = load_tram_stops()

        self.stop_states = {}
        for stop_id, stop in stops.items():
            self.stop_states[stop_id] = StopState(stop_id=stop_id, name=stop.name, full_name=stop.full_name)

        self.arrival_model.initialize_weights(list(self.stop_states.values()), self.blocks)

        # Map full_name from schedule to list of kod_busman from GeoJSON
        self.stop_name_to_kod_busman = {}

        for kod_busman, stop in stops.items():
            fn = stop.full_name
            if fn not in self.stop_name_to_kod_busman:
                self.stop_name_to_kod_busman[fn] = []
            self.stop_name_to_kod_busman[fn].append(kod_busman)

        self.tram_states = {}
        for block in self.blocks:
            self.tram_states[block.block_id] = TramState(block_id=block.block_id)

        print(
            f"Initialized passenger simulation: {len(self.stop_states)} stops, {len(self.tram_states)} trams"
        )
        print(
            f"Created {len(self.stop_name_to_kod_busman)} stop name to kod_busman mappings"
        )

    def _update_passenger_simulation(self, delta_time: float):
        """Update passenger simulation for one time step."""
        current_time = self.env.now

        for stop_state in self.stop_states.values():
            new_passengers = self.arrival_model.generate_arrivals(
                stop_state, current_time, delta_time
            )
            stop_state.waiting_passengers.extend(new_passengers)

            # Purge waiting passengers who exceeded max wait time
            # We treat only passengers with status == 'WAITING'
            if self.max_wait_minutes is not None and self.max_wait_minutes > 0:
                timed_out = [
                    p
                    for p in stop_state.waiting_passengers
                    if p.status == "WAITING"
                    and (current_time - p.arrival_time_minutes) >= self.max_wait_minutes
                ]

                if timed_out:
                    count = len(timed_out)
                    # Remove them from waiting list
                    remaining = [p for p in stop_state.waiting_passengers if p not in timed_out]
                    stop_state.waiting_passengers = remaining

                    # Update counters
                    stop_state.total_timed_out += count
                    self.stats["total_removed_timeout"] += count

        # Record passenger history every minute
        if current_time - self.last_history_update >= 1.0:
            self._record_passenger_history(current_time)
            self.last_history_update = current_time

    def _find_matching_stop_states(self, stop_time: Any) -> List[StopState]:
        """Find matching StopStates for a given stop_time from schedule using full_name."""
        matching_stop_states = []

        full_name = stop_time.full_name
        kod_busman_list = self.stop_name_to_kod_busman.get(full_name)
        
        if kod_busman_list:
            for kod_busman in kod_busman_list:
                stop_state = self.stop_states.get(kod_busman)
                if stop_state:
                    matching_stop_states.append(stop_state)

        return matching_stop_states


    def _update_stats(self, boarded: int, alighted: int, time_minutes: float):
        """Update simulation statistics."""
        if boarded == 0 and alighted == 0:
            return

        self.stats["total_boarded"] += boarded
        self.stats["total_alighted"] += alighted

        # Calculate hour index (0-based from start of day, continuously increasing)
        hour_index = int(time_minutes // 60)

        if hour_index not in self.stats["hourly_stats"]:
            self.stats["hourly_stats"][hour_index] = {"boarded": 0, "alighted": 0}

        self.stats["hourly_stats"][hour_index]["boarded"] += boarded
        self.stats["hourly_stats"][hour_index]["alighted"] += alighted

    def get_statistics(self) -> Dict[str, Any]:
        """Get current simulation statistics."""
        return self.stats

    def _record_passenger_history(self, current_time: float):
        """Record current passenger counts for charts."""
        # Record stop passenger counts
        for stop_id, stop_state in self.stop_states.items():
            waiting_count = len([p for p in stop_state.waiting_passengers if p.status == "WAITING"])
            if stop_id not in self.stop_passenger_history:
                self.stop_passenger_history[stop_id] = []
            self.stop_passenger_history[stop_id].append((current_time, waiting_count))

        # Record tram occupancy
        for tram_id, tram_state in self.tram_states.items():
            if tram_id not in self.tram_occupancy_history:
                self.tram_occupancy_history[tram_id] = []
            self.tram_occupancy_history[tram_id].append((current_time, tram_state.current_occupancy))

    def get_stop_passenger_history(self, stop_id: str) -> List[Tuple[float, int]]:
        """Get passenger history for a specific stop."""
        return self.stop_passenger_history.get(stop_id, [])

    def get_tram_occupancy_history(self, tram_id: str) -> List[Tuple[float, int]]:
        """Get occupancy history for a specific tram."""
        return self.tram_occupancy_history.get(tram_id, [])
