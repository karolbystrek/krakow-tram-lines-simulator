import asyncio
import threading
from typing import Any, Dict, List, Optional, Tuple

import simpy

from .models import TramBlock, Trip, StopTime
from .loader import load_tram_blocks, load_tram_stops
from .passenger_model import StopState, TramState
from .arrival_model import ArrivalRateModel
from .passenger_handling import PassengerManager

class SimulationEngine:
    def __init__(self, service_id: str = "service_1"):
        print(f"Initializing simulation engine with service: {service_id}")
        self.blocks: List[TramBlock] = []
        self.running = False
        self.paused = False
        self.start_time_minutes = 0
        self.end_time_minutes = 24 * 60
        self.task = None # Keep task for potential cancellation if needed later
        self.service_id = service_id
        self.simulation_speed_factor = 1.0 # Default: 1 real sec = 1 sim minute

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
        
        # Track which stops have been processed to avoid duplicate processing
        # Key: (block_id, stop_num), Value: last processed time
        self.processed_stops: Dict[Tuple[str, str], float] = {}

        # Statistics
        self.stats = {
            "total_boarded": 0,
            "total_alighted": 0,
            "hourly_stats": {}
        }
        
        # Lazy-load services: Only load the needed service initially for faster startup
        # Other services will be loaded on-demand when switching services
        print(f"Loading initial service: {service_id}...")
        self._load_service(service_id)
    
    @property
    def current_time_minutes(self) -> float:
        """Get current simulation time from simpy environment."""
        with self._time_lock:
            return self.env.now if hasattr(self, 'env') and self.env else 0.0

    async def start(self):
        """Start the simulation loop."""
        if self.running:
            return

        
        self.running = True
        self.paused = False
        
        # Load blocks from cache if not already loaded
        if not self.blocks:
            print(f"Starting simulation with service: {self.service_id}")
            if self.service_id in self.cached_services:
                self.blocks = self.cached_services[self.service_id]
                self.start_time_minutes, self.end_time_minutes = self.service_bounds[self.service_id]
                
                print(f"Simulation range: {self.start_time_minutes // 60:02d}:{self.start_time_minutes % 60:02d} - {self.end_time_minutes // 60:02d}:{self.end_time_minutes % 60:02d}")
            else:
                print(f"Error: Service {self.service_id} not found in cache!")
                self.blocks = []
        
        # Initialize passenger simulation (only if blocks are loaded)
        if self.blocks:
            # Stops will be passed from main.py if available, otherwise load them
            self._initialize_passenger_simulation(getattr(self, '_cached_stops', None))
        else:
            print("Warning: No blocks loaded, skipping passenger simulation initialization")
        
        # Initialize and start simpy
        self._reset_env(self.start_time_minutes)
            
        print("Simulation started.")
        self.task = asyncio.create_task(self._loop())

    def _load_service(self, service_id: str):
        """Load a service into cache if not already loaded."""
        if service_id in self.cached_services:
            return  # Already loaded
        
        print(f"Loading {service_id}...")
        blocks_by_line = load_tram_blocks(service=service_id)
        all_blocks = []
        for line_blocks in blocks_by_line.values():
            all_blocks.extend(line_blocks)
        
        self.cached_services[service_id] = all_blocks
        
        # Calculate bounds for this service
        min_time = 24 * 60
        max_time = 0
        
        for block in all_blocks:
            for trip in block.trips:
                trip.initialize_shape_indices()
                start = trip.get_start_time_minutes()
                end = trip.get_end_time_minutes()
                if start < min_time: min_time = start
                if end > max_time: max_time = end
        
        if not all_blocks:
            min_time = 0
            max_time = 24 * 60
            
        self.service_bounds[service_id] = (min_time, max_time)
        print(f"Loaded {service_id}: {len(all_blocks)} blocks, range {min_time}-{max_time}")

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
        self.stats = {
            "total_boarded": 0,
            "total_alighted": 0,
            "hourly_stats": {}
        }

        # Reset passenger simulation (use cached stops if available)
        self._initialize_passenger_simulation(getattr(self, '_cached_stops', None))
        # Reset simpy environment/thread
        self._reset_env(self.start_time_minutes)
        print("Simulation restarted.")

    def _run_simpy(self):
        """Run simpy simulation in a separate thread."""
        import time as real_time
        try:
            while self.simpy_running:
                if not self.paused:
                    # Run simpy for a small step (0.1 minutes)
                    # Match original speed: 0.1 minutes simulation = 0.1 seconds real time
                    start_real_time = real_time.time()
                    current_simpy_time = self.env.now
                    next_timeout = min(current_simpy_time + 0.1, self.end_time_minutes)
                    
                    if next_timeout > current_simpy_time:
                        # Run simpy until next timeout
                        self.env.run(until=next_timeout)
                        
                        # Wait to match real-time speed (0.1 minutes sim = 0.1 seconds real at 1x)
                        # Speed factor 1.0: 0.1s real -> 0.1m sim
                        # Speed factor 2.0: 0.05s real -> 0.1m sim
                        elapsed_real = real_time.time() - start_real_time
                        target_real_duration = 0.1 / max(0.1, self.simulation_speed_factor)
                        sleep_time = max(0, target_real_duration - elapsed_real)
                        if sleep_time > 0:
                            real_time.sleep(sleep_time)
                        
                        # Check if we've reached the end
                        if self.env.now >= self.end_time_minutes:
                            print("Simulation finished (end time reached).")
                            self.running = False
                            self.simpy_running = False
                            break
                    else:
                        # Reached end time
                        break
                else:
                    # When paused, just sleep a bit to avoid busy waiting
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
            # Wait for 0.1 minutes of simulation time
            yield self.env.timeout(0.1)
            
            # Update passenger simulation (only if initialized)
            if self.stop_states:
                self._update_passenger_simulation(delta_time=0.1)
            
            # Check if we've reached the end
            if self.env.now >= self.end_time_minutes:
                break

    async def _loop(self):
        """Main asyncio loop for WebSocket updates."""
        print("Simulation loop started.")
        while self.running:
            # 0.1 second real time for WebSocket updates
            await asyncio.sleep(0.1)
            # Time is managed by simpy, we just keep the loop running for WebSocket updates

    def _reset_env(self, initial_time: float):
        """Reset SimPy environment and thread safely."""
        # Stop existing simpy loop if running
        self.simpy_running = False
        if self.simpy_thread and self.simpy_thread.is_alive():
            self.simpy_thread.join(timeout=1.0)

        # Create new environment
        with self._time_lock:
            self.env = simpy.Environment(initial_time=initial_time)
            self.simpy_running = True
            self.env.process(self._simpy_passenger_update_loop())

        # Start simpy in a separate thread
        self.simpy_thread = threading.Thread(target=self._run_simpy, daemon=True)
        self.simpy_thread.start()

    def get_tram_positions(self) -> List[Dict[str, Any]]:
        """Get current positions of all active trams."""
        trams = []
        for block in self.blocks:
            pos = self._get_tram_position_at_time(block, self.current_time_minutes)
            if pos:
                lat, lon = pos
                # Get occupancy from tram state
                tram_state = self.tram_states.get(block.block_id)
                occupancy = tram_state.current_occupancy if tram_state else 0
                max_capacity = tram_state.max_capacity if tram_state else 200
                occupancy_percent = (occupancy / max_capacity * 100) if max_capacity > 0 else 0
                
                trams.append({
                    "id": block.block_id,
                    "line": block.line_number,
                    "lat": lat,
                    "lon": lon,
                    "occupancy": occupancy,
                    "max_capacity": max_capacity,
                    "occupancy_percent": round(occupancy_percent, 1)
                })
        return trams
    
    def get_stop_states(self) -> Dict[str, Dict[str, Any]]:
        """Get current passenger states at all stops."""
        stop_data = {}
        for stop_id, stop_state in self.stop_states.items():
            waiting_count = len([p for p in stop_state.waiting_passengers if p.status == "WAITING"])
            stop_data[stop_id] = {
                "waiting_count": waiting_count,
                "total_arrived": stop_state.total_arrived,
                "total_boarded": stop_state.total_boarded,
                "arrival_rate": stop_state.arrival_rate_per_minute
            }
        return stop_data

    def set_time(self, time_minutes: float):
        """Set the simulation time manually."""
        # Clamp time to valid range
        old_time = self.current_time_minutes
        target_time = max(self.start_time_minutes, min(time_minutes, self.end_time_minutes))
        
        print(f"Setting time to: {int(target_time // 60):02d}:{int(target_time % 60):02d} (was {int(old_time // 60):02d}:{int(old_time % 60):02d})")

        # 1. Stop the asynchronous runner loop temporarily
        self.simpy_running = False
        if self.simpy_thread and self.simpy_thread.is_alive():
            self.simpy_thread.join(timeout=1.0)

        # IMPORTANT: Set simpy_running = True so the generator process (_simpy_passenger_update_loop)
        # does not exit when we run the environment synchronously in _fast_forward.
        # The thread is stopped, so it won't run in the background, but env.run() needs this flag.
        self.simpy_running = True

        try:
            # 2. Determine if we need to reset/jump back
            # If moving backward OR if we simply need to re-calculate stats from start
            if target_time < old_time:
                print("Time jumped backward, resetting simulation state...")
                
                # Reset statistics
                self.stats = {
                    "total_boarded": 0,
                    "total_alighted": 0,
                    "hourly_stats": {}
                }
                
                # Reset passenger simulation
                self._initialize_passenger_simulation(getattr(self, '_cached_stops', None))
                
                # Reset SimPy environment to START time
                with self._time_lock:
                    self.env = simpy.Environment(initial_time=self.start_time_minutes)
                    # Attach the passenger update process to the NEW environment
                    self.env.process(self._simpy_passenger_update_loop())
                    
                # Fast forward from start to target_time
                self._fast_forward(target_time)
                
            else:
                # Moving forward: fast forward from current time to target time
                # Only if target > current, otherwise we are already there
                if target_time > self.env.now:
                    print(f"Fast forwarding from {self.env.now} to {target_time}...")
                    self._fast_forward(target_time)
        except Exception as e:
            print(f"Error during time set operations: {e}")
            import traceback
            traceback.print_exc()

        # 3. Restart the runner loop if needed
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
            "speed": self.simulation_speed_factor
        }

    def _interpolate_position_on_shape(
        self,
        trip: Trip,
        start_dist: float,
        end_dist: float,
        fraction: float
    ) -> Tuple[float, float]:
        """Interpolate position along the shape path."""
        target_dist = start_dist + (end_dist - start_dist) * fraction
        
        # Find the segment in trip.shape that contains target_dist
        # trip._shape_distances is monotonic
        
        # Binary search or linear search? Linear is fine for now as shapes aren't huge
        # and we can optimize later if needed.
        
        distances = trip._shape_distances
        if not distances:
            return trip.shape[0]

        for i in range(len(distances) - 1):
            d1 = distances[i]
            d2 = distances[i+1]
            
            if d1 <= target_dist <= d2:
                # Found the segment
                segment_len = d2 - d1
                if segment_len == 0:
                    return trip.shape[i]
                
                segment_fraction = (target_dist - d1) / segment_len
                lat1, lon1 = trip.shape[i]
                lat2, lon2 = trip.shape[i+1]
                
                lat = lat1 + (lat2 - lat1) * segment_fraction
                lon = lon1 + (lon2 - lon1) * segment_fraction
                return lat, lon
                
        # Fallback if out of bounds (shouldn't happen with correct logic)
        return trip.shape[-1]

    def _get_tram_position_at_time(
        self, block: TramBlock, time_minutes: float
    ) -> Optional[Tuple[float, float]]:
        """Calculate tram position at a specific time in minutes since midnight."""

        active_trip = block.get_active_trip(time_minutes)

        if not active_trip:
            # Tram waiting at terminus - show at last stop of previous trip
            # Or check if it's in depot
            # For simplicity, let's just check if it's between trips
            if block.trips:
                first_start = block.trips[0].get_start_time_minutes()
                last_end = block.trips[-1].get_end_time_minutes()

                if first_start <= time_minutes <= last_end:
                     # Find the previous trip
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

        # Get current segment (between which two stops)
        segment = active_trip.get_current_segment(time_minutes)

        if not segment:
            # Might be at a stop exactly
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

        # Use shape-based interpolation if available
        if active_trip._shape_distances:
             return self._interpolate_position_on_shape(
                 active_trip,
                 prev_stop.shape_dist_traveled,
                 next_stop.shape_dist_traveled,
                 fraction
             )

        # Fallback to linear interpolation between stops
        lat = prev_stop.stop_lat + (next_stop.stop_lat - prev_stop.stop_lat) * fraction
        lon = prev_stop.stop_lon + (next_stop.stop_lon - prev_stop.stop_lon) * fraction
        
        return lat, lon
    
    def _initialize_passenger_simulation(self, stops: Optional[Dict] = None):
        """Initialize passenger simulation state.
        
        Args:
            stops: Optional pre-loaded stops dict to avoid reloading. If None, loads stops.
        """
        # Use provided stops or load them
        if stops is None:
            stops = load_tram_stops()
        
        # Initialize stop states for all stops (by kod_busman)
        # These are the stops where passengers will actually wait
        self.stop_states = {}
        for stop_id, stop in stops.items():
            self.stop_states[stop_id] = StopState(stop_id=stop_id)
        
        # Create mapping from stop_num coordinates to kod_busman
        # This allows us to find the correct stop state when trams arrive
        # Key: (lat, lon) rounded to 6 decimals, Value: List[kod_busman] (can be multiple stops at same location)
        self.stop_num_to_kod_busman = {}
        
        # Build mapping by matching stop_num coordinates to geojson stop coordinates
        for block in self.blocks:
            for trip in block.trips:
                for stop_time in trip.stop_times:
                    if stop_time.stop_num and stop_time.stop_lat and stop_time.stop_lon:
                        # Round coordinates to match precision used in filtering
                        sched_lat = round(float(stop_time.stop_lat), 6)
                        sched_lon = round(float(stop_time.stop_lon), 6)
                        coord_key = (sched_lat, sched_lon)
                        
                        # Find ALL matching geojson stops by coordinates (multiple stops can share coordinates)
                        if coord_key not in self.stop_num_to_kod_busman:
                            matching_stops = []
                            for kod_busman, geojson_stop in stops.items():
                                geojson_lat = round(float(geojson_stop.lat), 6)
                                geojson_lon = round(float(geojson_stop.lon), 6)
                                
                                # Match within small threshold (0.001 degrees ~ 11 meters)
                                if abs(sched_lat - geojson_lat) < 0.001 and abs(sched_lon - geojson_lon) < 0.001:
                                    matching_stops.append(kod_busman)
                            
                            # Store list of matching stops (can be empty, single, or multiple)
                            if matching_stops:
                                self.stop_num_to_kod_busman[coord_key] = matching_stops
        
        # Initialize tram states for all blocks
        self.tram_states = {}
        for block in self.blocks:
            self.tram_states[block.block_id] = TramState(block_id=block.block_id)
        
        # Reset processed stops tracking
        self.processed_stops = {}
        
        print(f"Initialized passenger simulation: {len(self.stop_states)} stops, {len(self.tram_states)} trams")
        print(f"Created {len(self.stop_num_to_kod_busman)} stop_num to kod_busman mappings")
    
    def _update_passenger_simulation(self, delta_time: float):
        """Update passenger simulation for one time step."""
        current_time = self.env.now
        
        # 1. Generate new arrivals at all stops
        for stop_state in self.stop_states.values():
            new_passengers = self.arrival_model.generate_arrivals(
                stop_state,
                current_time,
                delta_time,
                self.service_id
            )
            stop_state.waiting_passengers.extend(new_passengers)
        
        # 2. Check if any trams are arriving at stops
        self._process_tram_arrivals()
        
        # 3. Clean up old processed_stops entries (older than 10 minutes) to prevent memory growth
        if len(self.processed_stops) > 1000:  # Only clean if we have many entries
            cutoff_time = current_time - 10.0
            self.processed_stops = {
                k: v for k, v in self.processed_stops.items() 
                if v > cutoff_time
            }
    
    def _process_tram_arrivals(self):
        """Check all active trams and process arrivals at stops."""
        current_time = self.env.now
        
        for block in self.blocks:
            active_trip = block.get_active_trip(current_time)
            if not active_trip:
                continue
            
            # Check if tram is at a stop (within tolerance)
            # Increased tolerance to 0.5 minutes (30 seconds) to ensure stops aren't missed
            for stop_time in active_trip.stop_times:
                scheduled_time = stop_time.to_minutes()
                time_diff = abs(current_time - scheduled_time)
                
                # If within 0.5 minute of scheduled stop time (before or after)
                # Also check that we haven't already processed this stop recently
                stop_key = (block.block_id, stop_time.stop_num)
                last_processed = self.processed_stops.get(stop_key, -999)
                
                # Process if within time window AND not processed in last 1 minute
                if time_diff < 0.5 and (current_time - last_processed) > 1.0:
                    # Find ALL matching stop states by matching coordinates
                    # Multiple stops can share the same coordinates, and we need to board passengers from ALL of them
                    matching_stop_states = []
                    
                    if stop_time.stop_lat and stop_time.stop_lon:
                        # Round coordinates to match precision
                        sched_lat = round(float(stop_time.stop_lat), 6)
                        sched_lon = round(float(stop_time.stop_lon), 6)
                        coord_key = (sched_lat, sched_lon)
                        
                        # Find ALL matching kod_busman values from mapping (can be multiple stops at same location)
                        kod_busman_list = self.stop_num_to_kod_busman.get(coord_key)
                        if kod_busman_list:
                            # kod_busman_list is now a list, not a single value
                            for kod_busman in kod_busman_list:
                                stop_state = self.stop_states.get(kod_busman)
                                if stop_state:
                                    matching_stop_states.append(stop_state)
                    
                    # Fallback: try direct lookup by stop_num (for backwards compatibility)
                    if not matching_stop_states:
                        stop_id = stop_time.stop_num
                        stop_state = self.stop_states.get(stop_id)
                        if stop_state:
                            matching_stop_states.append(stop_state)
                    
                    # Create if somehow missing
                    if not matching_stop_states:
                        # Use stop_num as fallback
                        stop_id = stop_time.stop_num
                        stop_state = StopState(stop_id=stop_id)
                        self.stop_states[stop_id] = stop_state
                        matching_stop_states.append(stop_state)
                        print(f"DEBUG: Created new stop state for {stop_id} (fallback). Coordinates: {stop_time.stop_lat}, {stop_time.stop_lon}")
                    
                    # Get tram state (should already exist)
                    tram_state = self.tram_states.get(block.block_id)
                    if not tram_state:
                        tram_state = TramState(block_id=block.block_id)
                        self.tram_states[block.block_id] = tram_state
                    
                    # Handle boarding/alighting
                    # Alighting happens once (based on stop_num), but boarding happens from ALL matching stops
                    total_boarded = 0
                    total_alighted = 0
                    
                    # Process first stop with alighting + boarding
                    if matching_stop_states:
                        boarded, alighted = self.passenger_manager.handle_tram_at_stop(
                            block, stop_time, current_time,
                            matching_stop_states[0], tram_state,
                            skip_alighting=False
                        )
                        total_boarded += boarded
                        total_alighted = alighted
                    
                        boarded, _ = self.passenger_manager.handle_tram_at_stop(
                            block, stop_time, current_time,
                            stop_state, tram_state,
                            skip_alighting=True
                        )
                        total_boarded += boarded

                    # Update statistics
                    self._update_stats(total_boarded, total_alighted, current_time)
                    
                    # Mark this stop as processed
                    self.processed_stops[stop_key] = current_time
                    
                    # Only process once per stop arrival (avoid duplicate processing)
                    # Move to next block after processing one stop
                    break
    
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
