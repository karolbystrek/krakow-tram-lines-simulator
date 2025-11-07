# Krakow Tram Lines Simulator

Application for simulating the expected number of passengers based on tram line, tram stop, and hour of the day.

## Getting Started

These instructions will get you a copy of the project up and running on your local machine.

## Prerequisites

This project requires Python 3.8+ and the following libraries:

* Playwright (for data scraping)
* Folium (for map visualization)

You can install all required dependencies by running:

```bash
pip install playwright folium
```

After installing Playwright, you must also install the browser binaries it needs to operate:

```bash
playwright install chromium
```

## Data Loading

The application relies on local data files. The data loading script is located in the `src` directory. To fetch the necessary data, run the following command from the root directory of your project:

```bash
python src/load_tram_data.py
```

This script will scrape the required tram line information and save it as individual JSON files in the `data/` directory.

## Running the Visualization

To view a map of all the tram stops, run the visualizer module. Make sure you have already loaded the data as described above.

From the root directory of your project, run:

```bash
python -m src.visualizer
```

This will generate a file named `krakow_stops_map.html` in the root directory and automatically open it in your default web browser.
