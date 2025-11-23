import asyncio
import time
from typing import Any, Dict, List, Optional, Tuple
from .models import TramBlock, Trip, StopTime
from .loader import load_tram_blocks

class SimulationEngine:
    def __init__(self):
        print("Initializing simulation engine...")
        self.blocks: List[TramBlock] = []
        self.running = False
        self.paused = False
        self.start_time_minutes = 3 * 60  # Start at 03:00
        self.current_time_minutes = self.start_time_minutes
        self.task = None # Keep task for potential cancellation if needed later

    async def start(self):
        """Start the simulation loop."""
        if self.running:
            return
        
        self.running = True
        self.paused = False
        # Load blocks if not already loaded (optional check)
        if not self.blocks:
            # The original loader returns Dict[str, List[TramBlock]], need to flatten it
            blocks_by_line_dict = load_tram_blocks()
            for line_blocks in blocks_by_line_dict.values():
                self.blocks.extend(line_blocks)
            print(f"Total: Loaded {len(self.blocks)} blocks for {len(blocks_by_line_dict)} lines")
            
        print("Simulation started.")
        self.task = asyncio.create_task(self._loop())

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
            # 1 second real time = 1 minute simulation time
            await asyncio.sleep(1)
            
            if not self.paused:
                self.current_time_minutes += 1
                
                # Reset if we go past 24 hours (optional, but good for long runs)
                if self.current_time_minutes >= 24 * 60:
                    self.current_time_minutes = 0
            
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

    def get_status(self) -> Dict[str, Any]:
        """Get current simulation status."""
        hours = self.current_time_minutes // 60
        minutes = self.current_time_minutes % 60
        return {
            "time_str": f"{hours:02d}:{minutes:02d}",
            "time_minutes": self.current_time_minutes,
            "running": self.running,
            "paused": self.paused
        }

    def _interpolate_position(
        self,
        start_pos: Tuple[float, float],
        end_pos: Tuple[float, float],
        start_time_minutes: int,
        end_time_minutes: int,
        current_time_minutes: int,
    ) -> Tuple[float, float]:
        """Linearly interpolate position between two stops."""
        if end_time_minutes == start_time_minutes:
            return start_pos

        fraction = (current_time_minutes - start_time_minutes) / (
            end_time_minutes - start_time_minutes
        )
        # Ensure fraction is within [0, 1] range
        fraction = max(0.0, min(1.0, fraction))
        
        lat = start_pos[0] + (end_pos[0] - start_pos[0]) * fraction
        lon = start_pos[1] + (end_pos[1] - start_pos[1]) * fraction
        
        return lat, lon

    def _get_tram_position_at_time(
        self, block: TramBlock, time_minutes: int
    ) -> Optional[Tuple[float, float]]:
        """Calculate tram position at a specific time in minutes since midnight."""
        
        status = block.get_status_at_time(time_minutes)

        if status == "IN_DEPOT":
            return None

        active_trip = block.get_active_trip(time_minutes)

        if not active_trip:
            # Tram waiting at terminus - show at last stop of previous trip
            last_trip = None
            for trip in block.trips:
                if trip.get_end_time_minutes() <= time_minutes:
                    last_trip = trip
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

        # Interpolate position between the two stops
        position = self._interpolate_position(
            start_pos=(prev_stop.stop_lat, prev_stop.stop_lon),
            end_pos=(next_stop.stop_lat, next_stop.stop_lon),
            start_time_minutes=prev_stop.to_minutes(),
            end_time_minutes=next_stop.to_minutes(),
            current_time_minutes=time_minutes,
        )

        return position
