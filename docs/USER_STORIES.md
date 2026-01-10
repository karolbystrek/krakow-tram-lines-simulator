## User Story 1: Adjust Stop Weight from Map

**As a** Simulation User,
**I want** to adjust the passenger generation weight of a specific stop directly from the map,
**So that** I can easily fine-tune the demand for specific locations without searching through a long list.

**Acceptance Criteria:**
1.  Clicking a stop marker on the map opens a popup.
2.  The popup contains an "Adjust Weight" button.
3.  Clicking "Adjust Weight" opens the Weight Configuration modal.
4.  The modal is automatically filtered to show the selected stop.

## User Story 2: Fix Passenger Simulation Distribution

**As a** simulation operator,
**I want** passengers to be distributed more evenly across stops
**So that** the simulation results are more realistic and not heavily biased towards nearby stops or specific hubs.

**Acceptance Criteria:**
1.  Passenger destination selection is primarily influenced by stop weights.
2.  The distance-based penalty (gravity model) is removed from destination selection.
3.  The artificial boost for the last stop of a trip is removed.
4.  Stop name matching (full_name) is consistent across all data loaders to ensure passengers can always alight at their intended destination.
5.  Stops with 1.0 weight (default) should have a similar probability of being chosen as a destination if they are on the same trip.