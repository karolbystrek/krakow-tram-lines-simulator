# Feature Implementation Plan: Rethink Passenger Model

The current passenger model suffers from several issues: destination selection is limited to the current trip, passengers are forced to alight at every trip terminus, and tram arrivals at stops are handled via a polling mechanism that can miss events or process them incorrectly at trip boundaries. This leads to unrealistic statistics, such as excessive alights at terminal stops and zero boardings at major hubs. Additionally, some stops used in schedules are incorrectly filtered out during loading due to strict name matching.

The proposed solution involves a fundamental rethink: moving to an **O-D (Origin-Destination) based passenger model** where destinations are assigned at the moment of arrival at a stop, an **event-driven simulation** for tram-stop arrivals, and a **robust coordinate-based stop loading** mechanism.

## 📋 Todo Checklist
- [x] ✅ Implement Robust Stop Loading (Coordinate-based matching)
- [x] ✅ Implement Line Weights Configuration (Loading/Saving `line_weights.json`)
- [x] ✅ Initialize Line-specific Reachability Maps
- [x] ✅ Refactor `Passenger` model to include `target_line` and `destination_stop_id`
- [x] ✅ Update `ArrivalRateModel` to assign line (weighted) and destination upon generation
- [x] ✅ Refactor `SimulationEngine` to use event-driven SimPy processes for trams
- [x] ✅ Update `PassengerManager` for line-aware boarding and destination-aware alighting
- [x] ✅ Remove forced-alighting logic at trip termini
- [x] ✅ Final Review and Testing

## 🔍 Analysis & Investigation

### Codebase Structure
- `backend/app/simulation/passenger_model.py`: Defines `Passenger`, `StopState`, and `TramState`.
- `backend/app/simulation/arrival_model.py`: Handles global demand curves, stop-level arrival rates, and now line popularity.
- `backend/app/simulation/passenger_handling.py`: Contains boarding/alighting logic.
- `backend/app/simulation/engine.py`: Orchestrates the simulation, currently using a polling loop for tram arrivals.
- `backend/app/simulation/models.py`: Defines GTFS-like structures (`Trip`, `StopTime`, `TramBlock`).
- `backend/app/simulation/loader.py`: Handles loading of stops and blocks.

### Current Architecture
The simulation currently uses a hybrid approach:
1.  **Polling**: Every 0.1 simulation minutes, the engine checks all trams to see if they are near a scheduled stop time.
2.  **Limited Destination Scope**: When boarding, a passenger is assigned a destination only from the remaining stops of the *current trip*.
3.  **Forced Alighting**: At the last stop of any trip, all passengers are forced to alight, regardless of their intended destination.
4.  **Strict Filtering**: Stops are filtered during loading based on exact name matches with the schedule.

### Dependencies & Integration Points
- **Line Weights**: A new configuration file `backend/app/data/line_weights.json` will store popularity factors for each tram line (e.g., "50": 2.5, "18": 1.2).
- **SimPy**: Used as the discrete event simulation engine.
- **FastAPI/WebSockets**: Broadcasts state updates and configuration changes.

### Considerations & Challenges
- **Line-based Reachability**: A passenger generated at Stop A for Line 18 will only board Line 18. This ensures that their destination (selected from Line 18's path) is always reachable.
- **Line Popularity**: If Lines 18 and 50 both stop at a station, but Line 50 has a higher weight, more passengers will be generated with "50" as their `target_line`.
- **Stop Identity**: Some stops might have multiple `kod_busman` identifiers for the same physical location.

## 📝 Implementation Plan

### Prerequisites
- None.

### Step-by-Step Implementation

1. **Step 1: Robust Stop Loading**
   - Files to modify: `backend/app/simulation/loader.py`, `backend/app/simulation/engine.py`
   - Changes needed:
     - Update `_load_service` in `engine.py` to collect unique `(lat, lon)` coordinates from the schedule.
     - Modify `load_tram_stops` in `loader.py` to perform coordinate-based matching.

2. **Step 2: Configuration and Reachability Initialization**
   - Files to modify: `backend/app/simulation/engine.py`, `backend/app/simulation/arrival_model.py`
   - Changes needed: 
     - Create `line_weights.json` with default values (1.0 for all lines).
     - Update `ArrivalRateModel` to load/save these weights.
     - Create a `line_reachability` map: `Dict[LineNumber, Dict[OriginStopID, List[DestinationStopID]]]`.
     - For each `TramBlock`, populate which destinations are reachable from which origins on that specific line across its entire daily schedule.

3. **Step 3: Update Passenger and Arrival Models**
   - Files to modify: `backend/app/simulation/passenger_model.py`, `backend/app/simulation/arrival_model.py`
   - Changes needed:
     - Update `Passenger` class to add `target_line: str`.
     - Modify `ArrivalRateModel.generate_arrivals` to:
       1. Identify all lines passing through the current stop.
       2. Use `line_weights` to perform a weighted selection of one `target_line` for the passenger.
       3. Pick a `destination_stop_id` from the `line_reachability` for that specific line using a gravity model.
       4. This ensures every passenger has a guaranteed viable route and respects line popularity.

4. **Step 4: Event-Driven Tram Simulation**
   - Files to modify: `backend/app/simulation/engine.py`
   - Changes needed:
     - Create a new SimPy process `_tram_lifecycle_process(block_id)`.
     - Use `yield self.env.timeout()` to wait for scheduled arrival times.
     - Remove the `_process_tram_arrivals` polling loop.

5. **Step 5: Refactor Passenger Handling Logic**
   - Files to modify: `backend/app/simulation/passenger_handling.py`
   - Changes needed:
     - **Boarding**: Trams of Line L board passengers whose `target_line == L` and whose destination is in the future path of the block.
     - **Alighting**: Passengers alight only if `current_stop.full_name == p.destination_stop_id`.
     - **Termini**: Remove forced-alighting logic.

6. **Step 6: Statistics Correction**
   - Files to modify: `backend/app/simulation/engine.py`
   - Changes needed: Ensure statistics are updated correctly in the new event-driven flow.

### Testing Strategy
- **Line Weights**: Verify that increasing a line's weight results in more passengers being generated for that line.
- **Stop Loading**: Verify all stops from schedules are now present.
- **Trip Viability**: Verify that no passenger is ever "stuck" on a tram.
- **Terminal Stats**: Verify that terminal stops show realistic alighting numbers.

## 🎯 Success Criteria
- Passengers are associated with a specific line (weighted by popularity) and destination at generation.
- Trams only pick up passengers for their specific line.
- Passengers always reach their destination stop.
- Line and stop weights are persistent and configurable.
- Final statistics reflect real-world passenger flows.
