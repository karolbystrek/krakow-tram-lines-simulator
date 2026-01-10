# Feature Implementation Plan: filter-stops-by-active-blocks

## 📋 Todo Checklist
- [x] ✅ Update `loader.py` with name-based filtering and robust name cleaning.
- [x] ✅ Update `SimulationEngine` to collect active stops and trigger filtering on service load.
- [x] ✅ Update `main.py` to serve currently active stops via `/api/stops`.
- [x] ✅ Update frontend to refresh stops on the map when the service day changes.
- [x] ✅ Final Review and Testing

## 🔍 Analysis & Investigation

### Codebase Structure
- **`backend/app/simulation/loader.py`**: Contains `load_tram_stops` which currently filters stops globally using coordinates from all service days.
- **`backend/app/simulation/engine.py`**: Manages the simulation state. `_load_service` loads blocks but doesn't currently trigger a stop re-load.
- **`backend/app/main.py`**: Initializes the engine and serves endpoints. `/api/stops` currently serves a static set of stops loaded on startup.
- **`frontend/src/js/simulation/SimulationController.js`**: Handles WebSocket messages. Currently clears trams but not stops upon service change.

### Current Architecture
The system loads a global set of stops once. While it has some filtering logic (`get_tram_stop_map_from_schedules`), it is not specific to the active service day and relies on coordinate matching which can be less precise than the requested name-based matching.

### Dependencies & Integration Points
- **GeoJSON**: The source of truth for stop geometries and metadata (`Nazwa_przystanku_nr`).
- **Tram Blocks (JSON)**: Provide the scheduled stop times with `stop_name` and `stop_num`.
- **WebSocket**: Used to communicate service changes to the frontend.

### Considerations & Challenges
- **Name Normalization**: `stop_name` in blocks can contain `(nz)` or `(nż)` which must be stripped.
- **Full Name Construction**: Must be exactly `{clean_name} {stop_num}` to match the `Nazwa_przystanku_nr` property in the GeoJSON.
- **Performance**: Scanning blocks for unique stops is fast, but reloading the GeoJSON file on every service change should be optimized (e.g., by caching the GeoJSON features in memory).
- **Frontend Sync**: The Leaflet map needs to be cleared of old stops and repopulated to reflect the filtered list.

## 📝 Implementation Plan

### Prerequisites
- None. All data is already available in the local environment.

### Step-by-Step Implementation

1. **Step 1: Enhance `loader.py` filtering logic**
   - Files to modify: `backend/app/simulation/loader.py`
   - Changes needed:
     - Update `load_tram_stops` signature: `def load_tram_stops(filter_names: Optional[Set[str]] = None) -> Dict[str, Stop]:`.
     - Implement filtering by `filter_names` against the `Nazwa_przystanku_nr` property.
     - Add logic to parse `clean_name` and `stop_num` from `Nazwa_przystanku_nr` (usually by splitting at the last space) if `filter_names` is used.
     - Ensure `clean_stop_name` correctly handles both `(nz)` and `(nż)`.

2. **Step 2: Update `SimulationEngine` to handle per-service stops**
   - Files to modify: `backend/app/simulation/engine.py`
   - Changes needed:
     - In `_load_service(self, service_id: str)`, after loading `all_blocks`:
       - Iterate through all `StopTime`s in all blocks.
       - Collect unique `full_name` strings (already constructed as `{clean_name} {stop_num}` in `load_tram_blocks`).
       - Call `load_tram_stops(filter_names=active_full_names)`.
       - Assign the result to `self._cached_stops`.
     - Update `restart()` to ensure it correctly uses the current `_cached_stops`.

3. **Step 3: Update `main.py` endpoints**
   - Files to modify: `backend/app/main.py`
   - Changes needed:
     - Update `startup_event` to initialize `app.state.tram_stops` from `simulation_engine._cached_stops` after the engine has loaded the default service.
     - Update `/api/stops` to return `simulation_engine._cached_stops` (or fallback to `app.state.tram_stops`) to ensure it always returns the stops for the active service day.

4. **Step 4: Update Frontend to refresh stops**
   - Files to modify: `frontend/src/js/simulation/SimulationController.js`
   - Changes needed:
     - In the `handleUpdate` method, when receiving a `service_changed` message:
       - Clear the `stopsLayer` (e.g., `this.stopsLayer.clearLayers()`).
       - Reset `this.stopMarkers = {}`.
       - Call `loadTramStops(this.stopsLayer, this.map, this)` (you may need to pass `this.stopsLayer` or ensure it's accessible).
       - Note: Ensure `this.stopsLayer` is stored as a property on the controller if it's not already.

### Testing Strategy
- **Manual Test 1**: Start the simulation and verify that only stops present in the current day's schedule are visible.
- **Manual Test 2**: Change the service day via the UI and verify that the map updates to show a different set of stops.
- **Manual Test 3**: Verify that stops with `(nz)` or `(nż)` in the schedule are correctly matched to their counterparts in the GeoJSON.
- **Log Verification**: Check backend logs to see the number of stops loaded/filtered for each service.

## 🎯 Success Criteria
- The simulation only processes and displays stops that are part of the active service day's tram blocks.
- Stop matching is performed based on the name + number format (e.g., "Łagiewniki 04").
- The filtering happens automatically on startup, restart, and service change.
- The frontend map stays in sync with the filtered list of stops.
