# krakow-tram-lines-simulator

Application for simulating the expected number of passangers based on tram line, tram stop and hour of the day

## Tram lines data

### Prerequisites

Install the required dependencies:

```bash
pip install playwright
playwright install chromium
```

### Loading data

To fetch and save tram line data from the Kraków public transport API:

```bash
python load_tram_data.py
```

This will scrape all available tram lines and save their route information as individual JSON files in the `data/` directory.
