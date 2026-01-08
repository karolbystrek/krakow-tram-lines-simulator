# Kraków Tram Lines Simulator

A real-time simulation and visualization of the Kraków tram network. This application fetches real-time data and
schedule information to simulate tram movements on an interactive map.

## 🚀 Features

- **Real-time Simulation**: Visualizes tram movements based on actual schedule data.
- **Interactive Map**: Built with Leaflet.js, showing tram lines, stops, and live tram positions.
- **Simulation Controls**: Pause, resume, restart, and adjust the time scale (speed) of the simulation.
- **Live Data**: Fetches the latest tram lines, stops, and schedules from official sources.

## 🏃 Usage

### 1. Fetch Tram Data

Before starting the simulation, you must fetch the latest network data (lines, stops, schedules). Run the following
script:

```bash
python backend/scripts/fetch_data.py
```

*This will download the necessary JSON and GeoJSON files into `backend/app/data/`.*

### 2. Start the Application

```bash
docker compose up --build
```

### 3. Open the Simulator

Open your web browser and navigate to:

**[http://localhost:8000](http://localhost:8000)**

## 📂 Project Structure

The project is organized into a clear frontend-backend architecture:

```
krakow-tram-lines-simulator/
├── backend/                # Python FastAPI backend
│   ├── app/                # Application logic
│   │   ├── main.py         # API and WebSocket server
│   │   └── simulation/     # Simulation engine and models
│   ├── scripts/            # Utility scripts
│   │   └── fetch_data.py   # Data fetching script
│   └── run.py              # Entry point to run the server
├── frontend/               # Web frontend
│   ├── public/             # Static assets (HTML)
│   └── src/                # Source code (JS, CSS)
├── requirements.txt        # Python dependencies
└── README.md               # Project documentation
```
