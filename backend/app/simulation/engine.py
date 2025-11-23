import asyncio
import time
from typing import Any, Dict, List, Optional, Tuple
from .models import TramBlock, Trip, StopTime
from .loader import load_tram_blocks

class SimulationEngine:
    def __init__(self, service_id: str = "service_1"):
        print(f"Initializing simulation engine with service: {service_id}")
        self.blocks: List[TramBlock] = []
        self.running = False
        self.paused = False
        self.start_time_minutes = 0
        self.end_time_minutes = 24 * 60
        self.current_time_minutes = 0
        self.task = None # Keep task for potential cancellation if needed later
        self.service_id = service_id
        
        # Cache for all services
        self.cached_services: Dict[str, List[TramBlock]] = {}
        self.service_bounds: Dict[str, Tuple[int, int]] = {}
        
        # Preload all services
        services = ["service_1", "service_2", "service_3", "service_4", "service_5"]
        print("Preloading all services...")
        
        for svc in services:
            print(f"Loading {svc}...")
            blocks_by_line = load_tram_blocks(service=svc)
            all_blocks = []
            for line_blocks in blocks_by_line.values():
                all_blocks.extend(line_blocks)
            
            self.cached_services[svc] = all_blocks
            
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
                
            self.service_bounds[svc] = (min_time, max_time)
            print(f"Loaded {svc}: {len(all_blocks)} blocks, range {min_time}-{max_time}")

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
                self.current_time_minutes = self.start_time_minutes
                
                print(f"Simulation range: {self.start_time_minutes // 60:02d}:{self.start_time_minutes % 60:02d} - {self.end_time_minutes // 60:02d}:{self.end_time_minutes % 60:02d}")
            else:
                print(f"Error: Service {self.service_id} not found in cache!")
                self.blocks = []
            
        print("Simulation started.")
        self.task = asyncio.create_task(self._loop())

    async def reload_service(self, service_id: str):
        """Reload the simulation with a new service ID."""
        print(f"Reloading simulation with service: {service_id}")
        
        # Stop current simulation
        await self.stop()
        
        # Clear existing data
        self.blocks = []
        self.service_id = service_id
        
        # Restart simulation (start() will pick up new service from cache)
        await self.start()

    async def stop(self):
        """Stop the simulation."""
        self.running = False
        if self.task:
            self.task.cancel()
            try:
                await self.task
            except asyncio.CancelledError:
                pass
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
        self.current_time_minutes = self.start_time_minutes
        self.paused = False
        print("Simulation restarted.")

    async def _loop(self):
        """Main simulation loop."""
        print("Simulation loop started.")
        while self.running:
            # 0.1 second real time = 0.1 minute simulation time
            await asyncio.sleep(0.1)
            
            if not self.paused:
                self.current_time_minutes += 0.1
                
                # Stop if we go past the end time
                if self.current_time_minutes > self.end_time_minutes:
                    print("Simulation finished (end time reached).")
                    self.running = False
                    break
            
            # print(f"Simulation time: {self.current_time_minutes // 60:02d}:{self.current_time_minutes % 60:02d}")

    def get_tram_positions(self) -> List[Dict[str, Any]]:
        """Get current positions of all active trams."""
        trams = []
        for block in self.blocks:
            pos = self._get_tram_position_at_time(block, self.current_time_minutes)
            if pos:
                lat, lon = pos
                trams.append({
                    "id": block.block_id,
                    "line": block.line_number,
                    "lat": lat,
                    "lon": lon
                })
        return trams

    def set_time(self, time_minutes: float):
        """Set the simulation time manually."""
        # Clamp time to valid range
        time_minutes = max(self.start_time_minutes, min(time_minutes, self.end_time_minutes))
        self.current_time_minutes = time_minutes
        print(f"Simulation time manually set to: {int(self.current_time_minutes // 60):02d}:{int(self.current_time_minutes % 60):02d}")

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
            "paused": self.paused
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
