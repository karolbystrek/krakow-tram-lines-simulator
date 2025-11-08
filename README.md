# Krakow Tram Lines Simulator

Interactive visualization and simulation of Krakow's tram network with passenger prediction capabilities.

## Requirements

- Python 3.8+
- Playwright (for web scraping)

## Setup

1. **Create virtual environment and install dependencies**

   ```bash
   python3 -m venv .venv
   source .venv/bin/activate  # Windows: .venv\Scripts\activate
   pip install -r requirements.txt
   playwright install chromium
   ```

2. **Fetch tram network data**

   ```bash
   python src/fetch_tram_data.py
   ```

   Downloads tram lines, stops, and route shapes from official Krakow data sources.

3. **Generate visualization**

   ```bash
   python -m src.visualizer
   ```

   Creates `krakow_tram_network_map.html` with an interactive map featuring:

   - All tram routes with layered controls
   - Tram stops with detailed information
   - Multiple map styles (Light, Terrain, Transit)
   - Full-screen viewing and zoom controls

## Project Structure

```text
src/
├── fetch_tram_data.py    # Data scraping and downloading
├── data_loader.py        # GeoJSON data parsing
├── models.py             # Data models (Stop, Shape, TramLine)
└── visualizer.py         # Interactive map generation
```

## Usage

Open `krakow_tram_network_map.html` in your browser to explore the tram network. Use the layer control to toggle individual lines and stops.
