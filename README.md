# Krakow Tram Lines Simulator

Application for simulating the expected number of passengers based on tram line, tram stop, and hour of the day.

## Getting Started

These instructions will get you a copy of the project up and running on your local machine.

## Prerequisites

Python 3.8 or higher is required.

## Installation

1. **Create and activate a virtual environment**

   ```bash
   python3 -m venv .venv
   source .venv/bin/activate  # On Windows: .venv\Scripts\activate
   ```

2. **Install dependencies**

   ```bash
   pip install -r requirements.txt
   ```

3. **Install Playwright browser binaries**

   ```bash
   playwright install chromium
   ```

## Data Loading

The application relies on local data files. The data loading script is located in the `src` directory. To fetch the
necessary data, run the following command from the root directory of your project:

```bash
python src/fetch_tram_data.py
```

This script will scrape the required tram line information and save it as individual JSON files in the `data/`
directory.

## Running the Visualization

To view an interactive map of the complete tram network (routes and stops), run the visualizer module. Make sure you
have already loaded the data as described above.

From the root directory of your project, run:

```bash
python -m src.visualizer
```

This will generate a file named `krakow_tram_network_map.html` in the root directory. Open this file in your web
browser to view the map. The map includes:

* **Tram Routes**: Colored polylines showing the paths of all tram lines
* **Tram Stops**: Interactive markers for each stop with detailed information
* **Layer Control**: Toggle visibility of routes and stops independently
* **Interactive Features**: Zoom, pan, fullscreen, and location controls
