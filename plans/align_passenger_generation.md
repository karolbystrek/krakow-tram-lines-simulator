# Feature Implementation Plan: Align Passenger Generation with Projections

The discrepancy between projected (~639k) and actual (~417k) passengers is primarily due to two factors:
1.  **Terminal Stop "Leakage"**: Stops that only serve as trip termini (where trams arrive but don't depart for further stops) still receive a share of the system-wide demand weight, but those generated passengers are immediately dropped because they have no reachable destinations.
2.  **Simulation Time Window**: The simulation currently runs only when trams are active (e.g., 4 AM to 11 PM), losing all demand generated outside this window.

## 📋 Todo Checklist
- [x] ✅ Refactor `ArrivalRateModel.initialize_weights` to calculate reachability first.
- [x] ✅ Exclude "exit-only" stops (those with no reachable destinations) from `total_system_weight`.
- [x] ✅ Set default simulation time range to full 24 hours (0-1440).
- [x] ✅ Update `SimulationEngine` to respect the full 24h window by default.
- [x] ✅ Final Review and Testing.

## 🔍 Analysis & Investigation

### Codebase Structure
- `backend/app/simulation/arrival_model.py`: Controls demand distribution and destination selection.
- `backend/app/simulation/engine.py`: Controls simulation time bounds and lifecycle.

### Current Architecture
- Demand is distributed to ALL active stops based on their weight.
- If a stop has no reachable destinations (e.g., a terminal stop), the passenger is silently dropped during generation.
- The simulation loop terminates when the last tram completes its last trip.

### Considerations & Challenges
- **Wait Time at Night**: If generating passengers 24/7, stops will accumulate "waiting" passengers during the night when no trams run. This is actually realistic (people waiting for the first morning tram).
- **Service Changes**: When switching services, the reachability and boarding-capable stops might change.

## 📝 Implementation Plan

### Step-by-Step Implementation

1. **Step 1: Refactor `ArrivalRateModel.initialize_weights`**
   - Files to modify: `backend/app/simulation/arrival_model.py`
   - Changes needed:
     - Move reachability initialization to the beginning of the function.
     - Before calculating `stop_weights`, determine which stops are "boarding-capable" (have at least one destination in `line_reachability` for any line).
     - Only add weight to `total_system_weight` for boarding-capable stops.
     - Set weight to 0.0 for non-boarding stops.

2. **Step 2: Extend Simulation Time to 24h**
   - Files to modify: `backend/app/simulation/engine.py`
   - Changes needed:
     - In `__init__`, set `self.start_time_minutes = 0` and `self.end_time_minutes = 1440`.
     - In `_load_service`, store the tram activity bounds (`min_time`, `max_time`) but do NOT overwrite `self.start_time_minutes` and `self.end_time_minutes` for the active simulation session.
     - Ensure `SimulationEngine.start()` and `reload_service()` use the 0-1440 range.

3. **Step 3: Verification**
   - Add logging to backend to report:
     - Total boarding-capable stops vs total stops.
     - Total projected integral vs actual generated count at the end of simulation.

## 🎯 Success Criteria
- Total generated passengers at the end of a full 24h run matches the "Total Projected Daily Passengers" in the UI within a small margin of error.
- Non-boarding stops do not "steal" demand from the system.
