# Passenger Simulation System - Implementation Documentation

## 🎯 Overview

This document describes the **actual implementation** of the passenger simulation system in the Krakow Tram Lines Simulator. The system simulates passenger arrivals at stops, boarding onto trams, and alighting at destinations, with real-time tracking of tram occupancy and stop waiting counts.

---

## 📐 Architecture Overview

### High-Level Flow

```
Simulation Time Advances (0.1 minute steps)
    ↓
1. Generate new passengers arriving at stops (based on arrival rates)
    ↓
2. Check if any trams are arriving at stops (within 0.5 minute tolerance)
    ↓
3. When tram arrives at stop:
   a. Passengers alight (destination matches current stop_num)
   b. Waiting passengers board (up to capacity, destination assigned on boarding)
    ↓
4. Update tram occupancy and stop waiting counts
    ↓
5. Frontend displays real-time passenger data
```

---

## 🏗️ Component Architecture

### File Structure

```
backend/app/simulation/
├── passenger_model.py      # Data models: Passenger, StopState, TramState
├── arrival_model.py         # ArrivalRateModel, DestinationModel
├── passenger_handling.py    # PassengerManager (boarding/alighting logic)
├── engine.py                # SimulationEngine integration
└── loader.py               # Stop loading with coordinate-based matching
```

---

## 📁 File-by-File Documentation

### 1. `passenger_model.py` - Data Models

This file defines the core data structures used throughout the passenger simulation.

#### 1.1 `Passenger` Class

**Location**: `backend/app/simulation/passenger_model.py:8-18`

```python
@dataclass
class Passenger:
    passenger_id: str              # Unique identifier: "p_{stop_id}_{time}_{index}"
    origin_stop_id: str            # kod_busman where passenger started waiting
    destination_stop_id: str       # stop_num where passenger wants to go (assigned on boarding)
    arrival_time_minutes: float    # When passenger arrived at stop
    boarding_time_minutes: Optional[float] = None  # When passenger boarded tram
    alighting_time_minutes: Optional[float] = None # When passenger alighted
    current_tram_id: Optional[str] = None          # block_id of tram passenger is on
    status: str = "WAITING"        # "WAITING" | "ON_TRAM" | "ALIGHTED"
```

**Purpose**: Represents a single passenger in the simulation. Tracks their journey from arrival at a stop through boarding, riding, and alighting.

**Key Points**:
- `origin_stop_id` uses `kod_busman` (from GeoJSON)
- `destination_stop_id` uses `stop_num` (from schedule data)
- Status transitions: `WAITING` → `ON_TRAM` → `ALIGHTED`

#### 1.2 `StopState` Class

**Location**: `backend/app/simulation/passenger_model.py:21-28`

```python
@dataclass
class StopState:
    stop_id: str                                    # kod_busman identifier
    waiting_passengers: List[Passenger]             # Queue of passengers waiting to board
    total_arrived: int = 0                         # Total passengers that arrived today
    total_boarded: int = 0                         # Total passengers that boarded today
    arrival_rate_per_minute: float = 0.0           # Current arrival rate (updated each step)
```

**Purpose**: Tracks the state of passengers at a single stop. One `StopState` exists for each stop in the system.

**Key Points**:
- `stop_id` is the `kod_busman` from GeoJSON (e.g., "116-04", "448-03")
- `waiting_passengers` is a list that grows as passengers arrive and shrinks as they board
- `arrival_rate_per_minute` is dynamically updated based on time of day

#### 1.3 `TramState` Class

**Location**: `backend/app/simulation/passenger_model.py:31-51`

```python
@dataclass
class TramState:
    block_id: str                      # Unique tram identifier
    passengers: List[Passenger]        # List of passengers currently on tram
    max_capacity: int = 200            # Maximum tram capacity
    current_occupancy: int = 0          # Current number of passengers (ON_TRAM status)
    
    def get_available_space(self) -> int:
        """Returns available space: max_capacity - current_occupancy"""
        
    def update_occupancy(self):
        """Updates current_occupancy from passenger list and removes non-ON_TRAM passengers"""
```

**Purpose**: Tracks the state of passengers on a single tram. One `TramState` exists for each `TramBlock`.

**Key Methods**:
- `get_available_space()`: Calculates how many more passengers can board
- `update_occupancy()`: Counts `ON_TRAM` passengers and removes any `ALIGHTED` passengers (defensive cleanup)

---

### 2. `arrival_model.py` - Passenger Generation

This file handles passenger arrival generation and destination selection.

#### 2.1 `ArrivalRateModel` Class

**Location**: `backend/app/simulation/arrival_model.py:10-125`

**Purpose**: Models passenger arrival rates at stops based on time of day, day of week, and stop characteristics.

##### Configuration (Current Values)

```python
self.base_arrival_rate = 0.2          # Base rate: 0.2 passengers/min per stop
self.rush_hour_multiplier = 4.0       # Rush hour: 0.2 * 4.0 = 0.8 passengers/min
self.off_peak_multiplier = 0.5        # Off-peak: 0.2 * 0.5 = 0.1 passengers/min
self.night_multiplier = 0.1           # Night: 0.2 * 0.1 = 0.02 passengers/min

self.morning_rush = [7, 8, 9]         # 7-9 AM
self.evening_rush = [16, 17, 18]      # 4-6 PM
```

**Rush Hour Example**: During 8 AM rush hour, each stop generates:
- `0.2 * 4.0 = 0.8 passengers/minute`
- `= 48 passengers/hour per stop`

##### Methods

**`get_arrival_rate(stop_id, hour, service_id) -> float`**
- **Location**: `arrival_model.py:36-69`
- **Purpose**: Calculates arrival rate for a specific stop at a specific time
- **Logic**:
  1. Check for stop-specific override (if configured)
  2. Determine time-of-day multiplier (rush/off-peak/night)
  3. Apply service multiplier (weekend services: 0.8x)
  4. Return: `base_rate * multiplier * service_multiplier`

**`generate_arrivals(stop_state, time_minutes, delta_time, service_id) -> List[Passenger]`**
- **Location**: `arrival_model.py:71-125`
- **Purpose**: Generates new passengers arriving at a stop during a time step
- **Algorithm**:
  1. Get arrival rate for current hour
  2. Calculate `expected_arrivals = rate * delta_time`
  3. Use Poisson approximation:
     - If `expected_arrivals >= 1.0`: Generate `int(expected) + random chance`
     - If `expected_arrivals < 1.0`: Use probability `random() < expected`
  4. Create `Passenger` objects with:
     - `origin_stop_id` = `stop_state.stop_id` (kod_busman)
     - `destination_stop_id` = `""` (assigned later when boarding)
     - `status` = `"WAITING"`
  5. Add to `stop_state.waiting_passengers`
  6. Increment `stop_state.total_arrived`

#### 2.2 `DestinationModel` Class

**Location**: `backend/app/simulation/arrival_model.py:128-194`

**Purpose**: Selects destination stops for passengers when they board a tram.

##### Methods

**`select_destination(origin_stop_id, line_number, trip) -> Optional[str]`**
- **Location**: `arrival_model.py:133-194`
- **Purpose**: Selects a destination stop for a passenger based on their origin
- **Parameters**:
  - `origin_stop_id`: `stop_num` of current stop (e.g., "01", "02")
  - `line_number`: Tram line number (e.g., "8", "52")
  - `trip`: The active `Trip` object containing all stops
- **Algorithm**:
  1. Find origin stop index in `trip.stop_times`
  2. Get all stops after origin: `possible_destinations = trip.stop_times[origin_idx + 1:]`
  3. Calculate weights for each destination:
     - Base weight: `1.0 / (distance_index + 1)` (closer = higher weight)
     - Last stop bonus: `weight * 2.0` (end stops are common destinations)
  4. Select destination using weighted random selection
  5. Return `stop_num` of selected destination
- **Returns**: `stop_num` string (e.g., "05") or `None` if no valid destination

**Example**: Passenger at stop "02" on a trip with stops ["01", "02", "03", "04", "05"]:
- Possible destinations: ["03", "04", "05"]
- Weights: [1.0, 0.5, 0.33*2.0=0.66]
- More likely to choose "03" (closest) or "05" (end stop)

---

### 3. `passenger_handling.py` - Boarding and Alighting

This file handles the core logic of passengers boarding and alighting from trams.

#### 3.1 `PassengerManager` Class

**Location**: `backend/app/simulation/passenger_handling.py:10-129`

**Purpose**: Manages passenger boarding and alighting operations when trams arrive at stops.

##### Methods

**`handle_tram_at_stop(tram_block, stop_time, current_time_minutes, stop_state, tram_state) -> Tuple[int, int]`**
- **Location**: `passenger_handling.py:18-129`
- **Purpose**: Handles all passenger operations when a tram arrives at a stop
- **Returns**: `(passengers_boarded, passengers_alighted)`

**Step 1: Alighting** (Lines 38-58)
1. Find passengers on tram whose `destination_stop_id == stop_time.stop_num`
2. For each passenger to alight:
   - Set `status = "ALIGHTED"`
   - Set `alighting_time_minutes = current_time_minutes`
   - Set `current_tram_id = None`
3. Remove alighted passengers from `tram_state.passengers`
   - Filter: Keep only passengers with `status == "ON_TRAM"`
4. Update tram occupancy: `tram_state.update_occupancy()`

**Step 2: Boarding** (Lines 60-127)
1. Get waiting passengers: Filter `stop_state.waiting_passengers` for `status == "WAITING"`
2. Get active trip: `tram_block.get_active_trip(current_time_minutes)`
3. For each waiting passenger:
   - **Recalculate available space** (important: recalculated each iteration)
   - If no space available, break
   - **Assign destination** if not set:
     - Call `destination_model.select_destination(origin, line, trip)`
     - If no destination found, skip passenger (can't board without destination)
   - **Board passenger**:
     - Set `status = "ON_TRAM"`
     - Set `boarding_time_minutes = current_time_minutes`
     - Set `current_tram_id = tram_block.block_id`
     - Append to `tram_state.passengers`
     - **Update occupancy immediately** (so next iteration has correct available_space)
4. Remove boarded passengers from `stop_state.waiting_passengers`
5. Final occupancy update

**Key Implementation Details**:
- Available space is recalculated **inside the loop** to account for passengers just boarded
- Occupancy is updated **immediately after each boarding** to ensure accurate capacity tracking
- Passengers without destinations are skipped (can't board without knowing where to go)

---

### 4. `engine.py` - Simulation Engine Integration

This file integrates passenger simulation into the main simulation loop.

#### 4.1 `SimulationEngine` Class - Passenger Components

**Location**: `backend/app/simulation/engine.py:10-474`

##### Initialization

**`__init__(service_id)`** - Passenger-related initialization:
```python
# Passenger simulation components
self.passenger_manager = PassengerManager()
self.arrival_model = ArrivalRateModel()
self.stop_states: Dict[str, StopState] = {}           # Key: kod_busman
self.tram_states: Dict[str, TramState] = {}           # Key: block_id
self.stop_num_to_kod_busman: Dict[Tuple[float, float], str] = {}  # Coordinate mapping
self.processed_stops: Dict[Tuple[str, str], float] = {}  # (block_id, stop_num) -> time
```

##### Methods

**`_initialize_passenger_simulation()`**
- **Location**: `engine.py:338-384`
- **Purpose**: Initializes passenger simulation state when simulation starts
- **Steps**:
  1. Load all stops from GeoJSON (returns dict keyed by `kod_busman`)
  2. Create `StopState` for each stop (keyed by `kod_busman`)
  3. **Build coordinate mapping** (`stop_num_to_kod_busman`):
     - Iterate through all trips in all blocks
     - For each `stop_time`, extract coordinates and `stop_num`
     - Match coordinates to GeoJSON stops (within 0.0001° ≈ 10 meters)
     - Store mapping: `(lat, lon) -> kod_busman`
  4. Create `TramState` for each block
  5. Reset `processed_stops` tracking

**`_update_passenger_simulation(delta_time)`**
- **Location**: `engine.py:386-407`
- **Purpose**: Updates passenger simulation for one time step (called every 0.1 minutes)
- **Steps**:
  1. **Generate arrivals**: For each stop, call `arrival_model.generate_arrivals()`
  2. **Process tram arrivals**: Call `_process_tram_arrivals()`
  3. **Cleanup**: Remove old `processed_stops` entries (if > 1000 entries)

**`_process_tram_arrivals()`**
- **Location**: `engine.py:409-473`
- **Purpose**: Detects when trams arrive at stops and triggers boarding/alighting
- **Algorithm**:
  1. For each block (tram):
     - Get active trip: `block.get_active_trip(current_time_minutes)`
     - If no active trip, skip
  2. For each stop in active trip:
     - Calculate time difference: `abs(current_time - scheduled_time)`
     - Check if within **0.5 minute tolerance** (30 seconds)
     - Check if not processed in last **1.0 minute** (prevents duplicate processing)
  3. **Find correct stop state** (coordinate-based matching):
     - Extract coordinates from `stop_time`
     - Round to 6 decimal places
     - Look up `kod_busman` in `stop_num_to_kod_busman` mapping
     - Get `StopState` using `kod_busman` (where passengers are waiting)
     - Fallback: Try direct lookup by `stop_num`
  4. Get or create `TramState` for this block
  5. Call `passenger_manager.handle_tram_at_stop()` to process boarding/alighting
  6. Mark stop as processed: `processed_stops[(block_id, stop_num)] = current_time`
  7. Break (process only one stop per block per cycle)

**Key Implementation Details**:
- **Time window**: 0.5 minutes (30 seconds) tolerance for tram arrival detection
- **Duplicate prevention**: Tracks last processed time per `(block_id, stop_num)` pair
- **Coordinate matching**: Uses coordinate-based mapping to match `stop_num` (from schedules) to `kod_busman` (from GeoJSON) where passengers actually wait

**`get_tram_positions() -> List[Dict]`**
- **Location**: `engine.py:166-188`
- **Purpose**: Returns current tram positions with occupancy data for frontend
- **Returns**: List of dicts with:
  - `id`, `line`, `lat`, `lon`
  - `occupancy`: Current passenger count
  - `max_capacity`: Tram capacity (200)
  - `occupancy_percent`: Percentage full

**`get_stop_states() -> Dict[str, Dict]`**
- **Location**: `engine.py:190-201`
- **Purpose**: Returns current passenger states at all stops for frontend
- **Returns**: Dict keyed by `stop_id` (kod_busman) with:
  - `waiting_count`: Number of passengers waiting
  - `total_arrived`: Total arrivals today
  - `total_boarded`: Total boardings today
  - `arrival_rate`: Current arrival rate (passengers/min)

---

## 🔄 Data Flow - Step by Step

### Example: Passenger Journey

**Time: 08:15:00** (Rush Hour)

1. **Arrival Generation** (`_update_passenger_simulation`):
   - For stop "116-04" (kod_busman):
     - `get_arrival_rate("116-04", 8, "service_1")` → `0.2 * 4.0 = 0.8 passengers/min`
     - `generate_arrivals()` → Creates 1 new passenger (Poisson approximation)
     - Passenger added to `stop_states["116-04"].waiting_passengers`
     - Passenger has: `origin_stop_id="116-04"`, `destination_stop_id=""`, `status="WAITING"`

2. **Tram Arrival Detection** (`_process_tram_arrivals`):
   - Tram block_47 (line 8) arrives at stop with `stop_num="02"`
   - Time check: `abs(08:15:00 - 08:15:00) < 0.5 min` ✓
   - Coordinate matching:
     - Extract coordinates from `stop_time`: `(50.081524, 19.888593)`
     - Round: `(50.081524, 19.888593)`
     - Lookup in `stop_num_to_kod_busman` → finds `"116-04"`
     - Get `stop_state = stop_states["116-04"]` (where passengers are waiting)

3. **Boarding Process** (`handle_tram_at_stop`):
   - **Alighting**: Check if any passengers on tram have `destination_stop_id == "02"` → None
   - **Boarding**:
     - Get waiting passengers: 1 passenger waiting
     - Get active trip for destination assignment
     - For waiting passenger:
       - `select_destination("02", "8", trip)` → Returns `"05"` (weighted random)
       - Set `passenger.destination_stop_id = "05"`
       - Set `passenger.status = "ON_TRAM"`
       - Add to `tram_state.passengers`
       - Update occupancy: `tram_state.current_occupancy = 1`
     - Remove passenger from `stop_state.waiting_passengers`
   - Return: `(boarded=1, alighted=0)`

4. **Tram Continues**:
   - Passenger remains on tram with `status="ON_TRAM"`, `destination_stop_id="05"`
   - Occupancy tracked in `tram_state.current_occupancy`

5. **Alighting** (Later, at stop "05"):
   - Tram arrives at stop with `stop_num="05"`
   - Find passenger with `destination_stop_id == "05"` → Found
   - Set `passenger.status = "ALIGHTED"`
   - Remove from `tram_state.passengers`
   - Update occupancy: `tram_state.current_occupancy = 0`

---

## 🔑 Key Design Decisions

### 1. Coordinate-Based Stop Matching

**Problem**: Schedule data uses `stop_num` (e.g., "01", "02"), but GeoJSON uses `kod_busman` (e.g., "116-04", "448-03"). These don't directly correspond.

**Solution**: Create mapping using coordinates:
- Extract coordinates from schedule `stop_times`
- Match to GeoJSON stop coordinates (within 0.0001° ≈ 10 meters)
- Store mapping: `(lat, lon) -> kod_busman`
- When tram arrives, use coordinates to find correct `kod_busman` stop state

**Implementation**: `engine.py:349-373` (mapping creation), `engine.py:433-442` (mapping usage)

### 2. Time Window for Tram Arrivals

**Problem**: Simulation runs in 0.1-minute steps, but scheduled times are exact minutes.

**Solution**: Use 0.5-minute (30-second) tolerance window:
- Process stop if `abs(current_time - scheduled_time) < 0.5 minutes`
- Prevents missing stops due to timing precision
- Prevents duplicate processing with 1-minute cooldown

**Implementation**: `engine.py:428`

### 3. Destination Assignment on Boarding

**Problem**: Passengers need destinations, but we don't know which tram they'll board until it arrives.

**Solution**: Assign destination when passenger boards:
- Passenger created with `destination_stop_id = ""`
- When tram arrives, `select_destination()` is called with the active trip
- Destination selected from stops further along the line
- Passenger can only board if valid destination is found

**Implementation**: `passenger_handling.py:86-97`

### 4. Occupancy Update Strategy

**Problem**: Available space must be accurate during boarding loop.

**Solution**: Update occupancy immediately after each passenger boards:
- Recalculate `available_space` inside the loop
- Update `tram_state.current_occupancy` immediately after each boarding
- Ensures next iteration has correct capacity calculation

**Implementation**: `passenger_handling.py:79-111`

### 5. Duplicate Processing Prevention

**Problem**: Same stop might be processed multiple times in rapid succession.

**Solution**: Track processed stops with timestamp:
- Key: `(block_id, stop_num)`
- Value: Last processed time
- Only process if `(current_time - last_processed) > 1.0 minute`
- Cleanup old entries periodically

**Implementation**: `engine.py:424-428`, `engine.py:401-407`

---

## 📊 Current Configuration Values

### Arrival Rates

| Time Period | Multiplier | Rate (passengers/min) | Rate (passengers/hour) |
|------------|-----------|----------------------|------------------------|
| Rush Hour (7-9 AM, 4-6 PM) | 4.0 | 0.8 | 48 |
| Off-Peak | 0.5 | 0.1 | 6 |
| Night (10 PM - 5 AM) | 0.1 | 0.02 | 1.2 |
| Weekend Services | 0.8x | (multiplied) | (multiplied) |

**Base Rate**: 0.2 passengers/min per stop

### Tram Capacity

- **Default Capacity**: 200 passengers per tram
- **Occupancy Calculation**: Count of passengers with `status == "ON_TRAM"`

### Time Windows

- **Arrival Detection Tolerance**: 0.5 minutes (30 seconds)
- **Duplicate Prevention Cooldown**: 1.0 minute
- **Simulation Step**: 0.1 minutes (6 seconds real time)

---

## 📝 Summary

The passenger simulation system:

1. **Generates passengers** at stops based on time-of-day arrival rates
2. **Tracks passengers** in `StopState` objects (keyed by `kod_busman`)
3. **Detects tram arrivals** using time windows and coordinate matching
4. **Boards passengers** when trams arrive, assigning destinations on-the-fly
5. **Tracks occupancy** in `TramState` objects, updating immediately after each boarding
6. **Alights passengers** when trams reach their destination stops
7. **Prevents duplicates** using processed_stops tracking

The system uses coordinate-based matching to bridge the gap between schedule data (`stop_num`) and GeoJSON data (`kod_busman`), ensuring passengers waiting at stops can be found when trams arrive.

---

## 🔄 Integration with Main Simulation

### Simulation Loop Integration

```python
async def _loop(self):
    while self.running:
        await asyncio.sleep(0.1)  # 0.1 second real time
        
        if not self.paused:
            self.current_time_minutes += 0.1  # 0.1 minute simulation time
            
            # Passenger simulation step
            if self.stop_states:
                self._update_passenger_simulation(delta_time=0.1)
```

### WebSocket Integration

The engine provides:
- `get_tram_positions()`: Returns trams with occupancy data
- `get_stop_states()`: Returns stops with waiting passenger counts

These are sent to the frontend via WebSocket for real-time visualization.

---

## 🎯 Future Enhancements

Potential improvements (not yet implemented):

1. **Statistics Collection**: Per-stop, per-hour statistics tracking
2. **Configuration File**: YAML/JSON config for arrival rates
3. **Stop-Specific Rates**: Override base rates for specific stops
4. **Historical O-D Matrix**: Use real origin-destination data for destination selection
5. **Performance Optimization**: Limit detailed tracking for very large passenger counts

---

*Last Updated: Based on current implementation as of latest changes*
