# Kraków Tram Lines Simulator

A real-time simulation and visualization of the Kraków tram network. This application fetches real-time data and schedule information to simulate tram movements on an interactive map.

## 🚀 Features

- **Real-time Simulation**: Visualizes tram movements based on actual schedule data.
- **Interactive Map**: Built with Leaflet.js, showing tram lines, stops, and live tram positions.
- **Simulation Controls**: Pause, resume, restart, and adjust the time scale (speed) of the simulation.
- **Live Data**: Fetches the latest tram lines, stops, and schedules from official sources.

## 🛠️ Prerequisites

- **Python 3.8+**
- **pip** (Python package installer)

## ⚙️ Installation

1.  **Clone the repository**
    ```bash
    git clone git@github.com:karolbystrek/krakow-tram-lines-simulator.git
    cd krakow-tram-lines-simulator
    ```

2.  **Create and activate a virtual environment**
    ```bash
    python3 -m venv .venv
    
    # macOS/Linux
    source .venv/bin/activate
    
    # Windows
    .venv\Scripts\activate
    ```

3.  **Install dependencies**
    ```bash
    pip install -r requirements.txt
    ```

4.  **Install Playwright browser** (required for data fetching)
    ```bash
    python -m playwright install chromium
    ```

## 🏃 Usage

### 1. Fetch Tram Data
Before starting the simulation, you must fetch the latest network data (lines, stops, schedules). Run the following script:

```bash
python backend/scripts/fetch_data.py
```
*This will download the necessary JSON and GeoJSON files into `backend/app/data/`.*

### 2. Start the Application
Run the backend server:

```bash
python backend/run.py
```
*Alternatively, you can use uvicorn directly: `uvicorn backend.app.main:app --reload`*

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

## 🐳 Docker Support

You can also run the application using Docker, which automatically handles all dependencies (including Playwright).

### Prerequisites
- **Docker** and **Docker Compose**

### Running with Docker

1.  **Build and start the container**
    ```bash
    docker-compose up --build
    ```
    *First run might take a while to fetch the base image and download tram data.*

2.  **Access the application**
    Open [http://localhost:8000](http://localhost:8000)

The Docker setup allows for data persistence using a volume. **Note:** You must have the tram data fetched locally in `backend/app/data` (or the volume must be populated) before running, or check the logs if errors occur.
