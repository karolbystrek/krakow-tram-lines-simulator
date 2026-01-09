# GEMINI.MD: AI Collaboration Guide

This document provides essential context for AI models interacting with this project. Adhering to these guidelines will
ensure consistency and maintain code quality.

## 1. Project Overview & Purpose

* **Primary Goal:** Real-time simulation and visualization of the Kraków tram network. The application fetches real-time
  schedule and geospatial data to simulate tram movements and passenger flows on an interactive map.
* **Business Domain:** Public Transportation Simulation, Geospatial Visualization, Discrete Event Simulation.

## 2. Core Technologies & Stack

* **Languages:** Python 3.14 (Backend), JavaScript (ES6+ Frontend).
* **Frameworks & Runtimes:**
    * **Backend:** FastAPI (Web Framework), Uvicorn (ASGI Server), SimPy (Discrete Event Simulation Engine).
    * **Frontend:** Vanilla JavaScript (ES Modules), Leaflet.js (Maps).
    * **Containerization:** Docker, Docker Compose.
* **Databases/Storage:** File-based storage (JSON/GeoJSON) for network data (lines, stops, schedules). No traditional
  RDBMS is currently visible; data is processed in-memory using Pandas.
* **Key Libraries/Dependencies:**
    * **Python:** `simpy` (Simulation), `fastapi`, `websockets`, `geojson`, `pandas`, `httpx`.
    * **Frontend:** Leaflet.js (Mapping).
* **Package Manager(s):** `pip` (Python). No Node.js/npm package manager detected for the frontend; it relies on
  browser-native ES modules.

## 3. Architectural Patterns

* **Overall Architecture:** Client-Server with Real-time WebSocket Communication.
    * **Backend:** Acts as the simulation server. It runs the SimPy environment, calculates tram positions and passenger
      states, and broadcasts updates via WebSockets. It also serves the static frontend files.
    * **Frontend:** A Single Page Application (SPA) that connects to the backend WebSocket to receive state updates and
      render them on a Leaflet map.
* **Directory Structure Philosophy:**
    * `backend/`: Contains all server-side logic.
        * `app/`: Main application package.
            * `main.py`: API and WebSocket server entry point.
            * `simulation/`: Core simulation logic (engine, models, passenger handling).
            * `data/`: Stores fetched JSON/GeoJSON data.
        * `scripts/`: Utility scripts (e.g., `fetch_data.py` for downloading initial data).
        * `run.py`: Entry point for starting the Uvicorn server.
    * `frontend/`: Static web assets.
        * `public/`: HTML entry point.
        * `src/`: JavaScript source code (structured by modules: `map`, `simulation`, `ui`, `utils`).
    * `compose.yml`: Orchestrates the application services.

## 4. Coding Conventions & Style Guide

* **Formatting:**
    * **Python:** Adheres to PEP 8.
        * Indentation: 4 spaces.
        * Type Hinting: extensively used (e.g., `def method(self, arg: str) -> None:`).
    * **JavaScript:** Standard ES6+ conventions.
        * Indentation: 2 spaces (inferred).
        * Modules: Uses `import/export`.
* **Naming Conventions:**
    * **Python:**
        * Variables/Functions: `snake_case` (e.g., `load_tram_blocks`, `current_time_minutes`).
        * Classes: `PascalCase` (e.g., `SimulationEngine`, `TramBlock`).
        * Files: `snake_case` (e.g., `passenger_model.py`).
    * **JavaScript:**
        * Variables/Functions: `camelCase` (e.g., `initializeMap`, `sendCommand`).
        * Classes: `PascalCase` (e.g., `SimulationClient`).
        * Files: `camelCase` (e.g., `mapInit.js`, `routesLayer.js`).
* **API Design:**
    * **Communication:** Primarily WebSocket-based for simulation state sync.
    * **Protocol:** JSON messages.
        * Client sends commands (e.g., `{ command: "PAUSE" }`).
        * Server broadcasts updates (e.g., tram positions, stats).
* **Error Handling:**
    * **Python:** `try...except` blocks, especially around async tasks and simulation steps. Uses
      `traceback.print_exc()` for debugging simulation errors.
    * **JavaScript:** `try...catch` blocks for async operations and WebSocket message parsing.

## 5. Key Files & Entrypoints

* **Main Entrypoint(s):**
    * **Backend:** `backend/run.py` (starts the FastAPI app defined in `backend/app/main.py`).
    * **Frontend:** `frontend/src/js/app.js` (bootstraps the UI and simulation controller).
* **Configuration:**
    * `backend/app/config.py`: Likely contains application settings (inferred from file list).
    * `compose.yml`: Container and environment configuration.
* **Data Scripts:**
    * `backend/scripts/fetch_data.py`: Critical for initializing the system with required data.

## 6. Development & Testing Workflow

* **Local Development Environment:**
    1. **Data Setup:** Run `python backend/scripts/fetch_data.py` to populate `backend/app/data/`.
    2. **Execution:** Run `docker compose up --build`.
    3. **Access:** Application available at `http://localhost:8000`.
* **Testing:**
    * No explicit testing framework (like `pytest`) configuration was detected in the root. For this project do not
      create any tests. The user will test it manually.
* **Deployment:** Docker-based deployment via `Dockerfile` and `compose.yml`.

## 7. Specific Instructions for AI Collaboration

* **Simulation Logic:** When modifying `backend/app/simulation/`, ensure strict adherence to `simpy` patterns. The
  simulation runs in a separate thread/process managed by `SimulationEngine`. Be careful with thread safety when
  interacting between the FastAPI async loop and the SimPy environment.
* **Type Safety:** Always add type hints to new Python functions and classes.
* **Frontend/Backend Sync:** If you modify the data structure sent by the backend (e.g., in `get_tram_positions`),
  immediately update the corresponding parsing logic in `frontend/src/js/simulation/SimulationClient.js` or
  `SimulationUI.js`.
* **Data Integrity:** The application relies on specific JSON structures for lines and stops. Validate input data before
  processing in the simulation.
* **Docker:** If adding new Python dependencies, update `requirements.txt` and remind the user to rebuild the docker
  container.
