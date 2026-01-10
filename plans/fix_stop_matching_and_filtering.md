# Feature Implementation Plan: Fix Stop Matching and Filtering

There is an issue in the passenger model where passengers are generated for stops that are not present in the current service day's schedule. This is caused by loose coordinate-based matching and inconsistent stop name handling between the GeoJSON data and the tram block schedule files. Additionally, stop names in schedule files often contain suffixes like `(nz)` or `(nż)` which should be trimmed for consistent matching.

## 📋 Todo Checklist
- [x] ✅ Refine `clean_stop_name` utility for robust suffix removal.
- [x] ✅ Implement strict stop filtering based on service-specific schedules.
- [x] ✅ Standardize `full_name` construction across the backend.
- [x] ✅ Remove legacy phantom stop creation fallback in `SimulationEngine`.
- [x] ✅ Synchronize cleaning logic between `loader.py`, `engine.py`, and `arrival_model.py`.
- [x] ✅ Final Review and Testing.

## 🔍 Analysis & Investigation

### Codebase Structure
- `backend/app/simulation/loader.py`: Responsible for loading GeoJSON stops and JSON tram blocks. Contains the core filtering and name extraction logic.
- `backend/app/simulation/engine.py`: Orchestrates simulation lifecycle and initializes passenger simulation state.
- `backend/app/simulation/arrival_model.py`: Uses stop names and IDs for weight distribution and destination selection.

### Current Architecture
Stops are loaded from `krakow_tram_stops.geojson`. They are filtered by comparing their coordinates against a map of "active coordinates" collected from the tram blocks. Currently, this comparison uses a very loose epsilon (`0.001` degrees, approx. 111m), which causes multiple nearby stops (e.g., across the street or bus stops) to be incorrectly included in the simulation if they are near a tram stop. These "extra" stops then receive passengers that no tram ever picks up.

### Dependencies & Integration Points
- **GeoJSON Source**: `Nazwa_przystanku_nr` contains the full name (e.g., "TAURON Arena Kraków Wieczysta 03").
- **Schedule Source**: `stop_name` ("Elektromontaż (nż)") and `stop_num` ("02") must be joined and cleaned to match GeoJSON.

### Considerations & Challenges
- **Name-Based Matching**: The loader must NOT rely on coordinates for matching stops. It must match the GeoJSON "Nazwa_przystanku_nr" against the joined "stop_name" and "stop_num" from the schedule files.
- **Naming Consistency**: The suffix `(nz)`/`(nż)` must be removed consistently to ensure "Stop Name (nz) 01" matches "Stop Name 01".
- **Service Isolation**: Each service day (Monday-Friday, Saturday, Sunday) has different active stops. The passenger model must only generate passengers for stops active in the *currently selected* service.

## 📝 Implementation Plan

### Prerequisites
- None.

### Step-by-Step Implementation

1. **Step 1: Refine Suffix Cleaning**
   - Files to modify: `backend/app/simulation/loader.py`
   - Changes needed:
     - Update `clean_stop_name(name)` to be more robust (handle case variations and multiple spaces).
     - Ensure it is used consistently when loading both GeoJSON and block data.

2. **Step 2: Name-Only Stop Filtering in `loader.py`**
   - Files to modify: `backend/app/simulation/loader.py`
   - Changes needed:
     - Update `load_tram_stops` to accept an `active_full_names` set.
     - Remove all coordinate-based matching/filtering logic in `load_tram_stops`.
     - Filter GeoJSON features by checking if their cleaned `full_name` (derived from `Nazwa_przystanku_nr`) exists in the `active_full_names` set.

3. **Step 3: Update `SimulationEngine` Initialization**
   - Files to modify: `backend/app/simulation/engine.py`
   - Changes needed:
     - In `_load_service`, collect a set of `active_full_names` from all `stop_times` in the current service's blocks.
     - Construct each `full_name` as `f"{clean_stop_name(stop_name)} {stop_num}".strip()`.
     - Pass this set to `load_tram_stops` instead of the `active_coords_map`.
     - In `_handle_tram_arrival`, remove the fallback code that creates `StopState` objects on the fly for missing stops.

4. **Step 4: Consolidate Cleaning Logic**
   - Files to modify: `backend/app/simulation/engine.py`, `backend/app/simulation/arrival_model.py`
   - Changes needed:
     - Ensure `ArrivalRateModel` and `SimulationEngine` use the centralized `clean_stop_name` from `loader.py`.

5. **Step 5: Verify Destination Selection**
   - Files to modify: `backend/app/simulation/arrival_model.py`
   - Changes needed:
     - Verify that `_select_line_and_destination` uses the correctly joined `full_name` for reachability lookups.

### Testing Strategy
- **Service Switch Test**: Start the simulation on a weekday, then switch to Sunday. Verify (via logs or API) that only stops served on Sunday are generating passengers.
- **Phantom Stop Prevention**: Monitor console output for "Created new stop state" messages; they should no longer appear if matching is working correctly.
- **Name Match Verification**: Verify that a tram arriving at "Stop A (nz) 01" correctly picks up passengers from the "Stop A 01" `StopState` initialized from GeoJSON.

## 🎯 Success Criteria
- Passengers are only generated for stops present in the active service's block files.
- Stop names are correctly matched between `blocks_*.json` and `krakow_tram_stops.geojson` regardless of `(nz)` suffixes.
- The `SimulationEngine` no longer creates "fallback" stop states during tram arrival processing.
- Statistics accurately reflect boardings and alightings at valid GeoJSON stops.
