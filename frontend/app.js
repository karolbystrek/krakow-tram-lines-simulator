// Configuration constants
const CONFIG = {
  MAP_CENTER: [50.0614, 19.9366],
  MAP_ZOOM: 13,
  MAP_BOUNDS: [[49.97, 19.80], [50.13, 20.20]], // Kraków bounds [southwest, northeast]
  STOPS: {
    RADIUS: 6,
    COLOR: '#1E6BB8',
    WEIGHT: 2,
    FILL_COLOR: '#DBEDFF',
    FILL_OPACITY: 0.9
  },
  ROUTES: {
    COLOR: '#4DA6FF',
    WEIGHT: 3,
    OPACITY: 0.7
  }
};

// Map initialization
function initializeMap() {
  const map = L.map('map', {
    center: CONFIG.MAP_CENTER,
    zoom: CONFIG.MAP_ZOOM,
    maxBounds: CONFIG.MAP_BOUNDS,
    maxBoundsViscosity: 1.0, // Prevent panning outside bounds
    zoomControl: false // Remove +/- zoom buttons
  });

  // Fix map size after initialization
  setTimeout(() => map.invalidateSize(), 100);
  window.addEventListener('resize', () => {
    setTimeout(() => map.invalidateSize(), 100);
  });

  return map;
}

// Create Voyager tile layer (hardcoded)
function createVoyagerTileLayer() {
  return L.tileLayer('https://{s}.basemaps.cartocdn.com/rastertiles/voyager/{z}/{x}/{y}{r}.png', {
    maxZoom: 19,
    attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors &copy; <a href="https://carto.com/attributions">CARTO</a>'
  });
}

// Create stop marker
function createStopMarker(feature) {
  const props = feature.properties;
  const [lon, lat] = feature.geometry.coordinates;

  const marker = L.circleMarker([lat, lon], {
    radius: CONFIG.STOPS.RADIUS,
    color: CONFIG.STOPS.COLOR,
    weight: CONFIG.STOPS.WEIGHT,
    fill: true,
    fillColor: CONFIG.STOPS.FILL_COLOR,
    fillOpacity: CONFIG.STOPS.FILL_OPACITY
  });

  const popupContent = `<b>${props.name || props.stop_name}</b><br>Code: ${props.kod_busman || ''}<br>ID: ${props.id || ''}`;
  marker.bindPopup(popupContent, { maxWidth: 300 });
  marker.bindTooltip(props.name || props.stop_name);

  return marker;
}

// Create route polyline
function createRoutePolyline(feature, lineNumber) {
  const coords = feature.geometry.coordinates;
  const latLngs = coords.map(([lon, lat]) => [lat, lon]);

  const polyline = L.polyline(latLngs, {
    color: CONFIG.ROUTES.COLOR,
    weight: CONFIG.ROUTES.WEIGHT,
    opacity: CONFIG.ROUTES.OPACITY
  });

  // Bind tooltip that follows the mouse cursor
  polyline.bindTooltip(`Tram Line ${lineNumber}`, {
    permanent: false,
    sticky: true,
    direction: 'top'
  });

  // Make tooltip appear at cursor position on mouse move
  polyline.on('mousemove', function (e) {
    if (this._tooltip) {
      this._tooltip.setLatLng(e.latlng);
    }
  });

  return polyline;
}

// Sort line numbers (numeric if possible, otherwise alphabetical)
function sortLineNumbers(a, b) {
  const aNum = parseInt(a);
  const bNum = parseInt(b);
  if (!isNaN(aNum) && !isNaN(bNum)) {
    return aNum - bNum;
  }
  return a.localeCompare(b);
}

// Load and display tram stops
async function loadTramStops(stopsLayer, map) {
  try {
    const response = await fetch('/api/stops');
    if (!response.ok) throw new Error(`HTTP error! status: ${response.status}`);

    const data = await response.json();
    if (data.type !== 'FeatureCollection' || !data.features) {
      throw new Error('Invalid GeoJSON format');
    }

    data.features.forEach(feature => {
      createStopMarker(feature).addTo(stopsLayer);
    });

    stopsLayer.addTo(map);
    console.log(`Loaded ${data.features.length} tram stops`);

    return true;
  } catch (error) {
    console.error('Error loading tram stops:', error);
    return false;
  }
}

// Load and display tram routes
async function loadTramRoutes(map, overlayMaps) {
  try {
    const response = await fetch('/api/routes');
    if (!response.ok) throw new Error(`HTTP error! status: ${response.status}`);

    const data = await response.json();
    if (data.type !== 'FeatureCollection' || !data.features) {
      throw new Error('Invalid GeoJSON format');
    }

    // Group features by line number
    const featuresByLine = {};
    data.features.forEach(feature => {
      const lineNumber = feature.properties.line_number || feature.properties.line_name;
      if (!featuresByLine[lineNumber]) {
        featuresByLine[lineNumber] = [];
      }
      featuresByLine[lineNumber].push(feature);
    });

    const lineLayers = {};
    const sortedLineNumbers = Object.keys(featuresByLine).sort(sortLineNumbers);

    // Create layer group for each line
    sortedLineNumbers.forEach(lineNumber => {
      const lineLayer = L.layerGroup();
      featuresByLine[lineNumber].forEach(feature => {
        createRoutePolyline(feature, lineNumber).addTo(lineLayer);
      });

      lineLayers[lineNumber] = lineLayer;
      overlayMaps[`Line ${lineNumber}`] = lineLayer;
      lineLayer.addTo(map);
    });

    console.log(`Loaded ${data.features.length} route segments for ${sortedLineNumbers.length} lines`);
    return { success: true, lineLayers, lineNumbers: sortedLineNumbers };
  } catch (error) {
    console.error('Error loading tram routes:', error);
    return { success: false, lineLayers: {}, lineNumbers: [] };
  }
}

// Create toggle HTML for a line
function createLineToggleHTML(lineNumber, id) {
  return `
    <div class="settings-item">
      <label class="toggle-label toggle-label-line">
        <span class="toggle-text toggle-text-line">Line ${lineNumber}</span>
        <input type="checkbox" id="${id}" class="toggle-input toggle-line" data-line="${lineNumber}" checked>
        <span class="toggle-slider toggle-slider-small"></span>
      </label>
    </div>
  `;
}

// Initialize settings panel
function initializeSettingsPanel(map, stopsLayer, lineLayers, lineNumbers) {
  const toggle = document.getElementById('settings-toggle');
  const content = document.getElementById('settings-content');
  const stopsCheckbox = document.getElementById('toggle-stops');

  // Toggle panel visibility
  toggle.addEventListener('click', () => {
    content.classList.toggle('settings-content-open');
    toggle.classList.toggle('settings-toggle-btn-active');
  });

  // Toggle stops visibility
  stopsCheckbox.addEventListener('change', (e) => {
    if (e.target.checked) {
      if (!map.hasLayer(stopsLayer)) {
        stopsLayer.addTo(map);
      }
    } else {
      if (map.hasLayer(stopsLayer)) {
        map.removeLayer(stopsLayer);
      }
    }
  });

  // Add master toggle for all lines
  const masterToggleItem = document.createElement('div');
  masterToggleItem.className = 'settings-item settings-item-master';
  masterToggleItem.innerHTML = `
    <label class="toggle-label">
      <span class="toggle-text">Toggle All Lines</span>
      <input type="checkbox" id="toggle-all-lines" class="toggle-input toggle-master" checked>
      <span class="toggle-slider"></span>
    </label>
  `;
  content.appendChild(masterToggleItem);

  // Add individual line toggles directly to main content
  const fragment = document.createDocumentFragment();
  lineNumbers.forEach(lineNumber => {
    const toggleId = `toggle-line-${lineNumber}`;
    const tempDiv = document.createElement('div');
    tempDiv.innerHTML = createLineToggleHTML(lineNumber, toggleId);
    const lineItem = tempDiv.firstElementChild;
    lineItem.classList.add('settings-item-line');
    fragment.appendChild(lineItem);
  });
  content.appendChild(fragment);

  // Handle master toggle
  const masterToggle = document.getElementById('toggle-all-lines');
  masterToggle.addEventListener('change', (e) => {
    const isChecked = e.target.checked;
    const lineToggles = document.querySelectorAll('.toggle-line');

    masterToggle.indeterminate = false;
    lineToggles.forEach(toggle => {
      toggle.checked = isChecked;
      const lineNumber = toggle.dataset.line;
      const lineLayer = lineLayers[lineNumber];

      if (isChecked) {
        if (!map.hasLayer(lineLayer)) {
          lineLayer.addTo(map);
        }
      } else {
        if (map.hasLayer(lineLayer)) {
          map.removeLayer(lineLayer);
        }
      }
    });
  });

  // Handle individual line toggles
  lineNumbers.forEach(lineNumber => {
    const toggleId = `toggle-line-${lineNumber}`;
    const lineToggle = document.getElementById(toggleId);
    const lineLayer = lineLayers[lineNumber];

    lineToggle.addEventListener('change', (e) => {
      const isChecked = e.target.checked;

      if (isChecked) {
        if (!map.hasLayer(lineLayer)) {
          lineLayer.addTo(map);
        }
      } else {
        if (map.hasLayer(lineLayer)) {
          map.removeLayer(lineLayer);
        }
      }

      // Update master toggle state
      const allChecked = Array.from(document.querySelectorAll('.toggle-line')).every(t => t.checked);
      const allUnchecked = Array.from(document.querySelectorAll('.toggle-line')).every(t => !t.checked);

      masterToggle.indeterminate = false;
      if (allChecked) {
        masterToggle.checked = true;
      } else if (allUnchecked) {
        masterToggle.checked = false;
      } else {
        masterToggle.indeterminate = true;
      }
    });
  });
}

// Simulation Controller
class SimulationController {
  constructor(map) {
    this.map = map;
    this.markers = {}; // tramId -> { marker, data }
    this.ws = null;
    this.timeDisplay = null;
    
    this.timeDisplay = document.getElementById('simulation-time');
    if (!this.timeDisplay) {
        console.error('Time display element not found!');
    } else {
        this.timeDisplay.textContent = 'Connecting...';
    }
  }

  connect() {
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const wsUrl = `${protocol}//${window.location.host}/ws/simulation`;
    
    console.log(`Connecting to WebSocket: ${wsUrl}`);
    this.ws = new WebSocket(wsUrl);

    this.ws.onopen = () => {
      console.log('WebSocket connected');
      this.timeDisplay.textContent = 'Connected';
    };

    this.ws.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data);
        this.handleUpdate(data);
      } catch (e) {
        console.error('Error parsing WebSocket message:', e);
      }
    };

    this.ws.onclose = (event) => {
      console.log('WebSocket disconnected. Code:', event.code, 'Reason:', event.reason);
      if (this.timeDisplay) this.timeDisplay.textContent = 'Disconnected';
      setTimeout(() => this.connect(), 5000);
    };
    
    this.ws.onerror = (error) => {
      console.error('WebSocket error:', error);
    };

    // Button Event Listeners
    const pauseBtn = document.getElementById('btn-pause');
    const restartBtn = document.getElementById('btn-restart');

    if (pauseBtn) {
      pauseBtn.addEventListener('click', () => {
        const isPaused = pauseBtn.textContent.includes('Resume');
        const command = isPaused ? 'resume' : 'pause';
        this.sendCommand(command);
      });
    }

    if (restartBtn) {
      restartBtn.addEventListener('click', () => {
        this.sendCommand('restart');
      });
    }
  }

  sendCommand(command) {
    if (this.ws && this.ws.readyState === WebSocket.OPEN) {
      console.log('Sending command:', command);
      this.ws.send(JSON.stringify({ command }));
    } else {
      console.warn('WebSocket not connected, cannot send command:', command);
    }
  }

  handleUpdate(data) {
    // Update time
    if (data.time) {
      this.timeDisplay.textContent = `Time: ${data.time.time_str}`;
      
      // Update button text based on status
      const pauseBtn = document.getElementById('btn-pause');
      if (pauseBtn) {
        if (data.status === 'paused') {
            pauseBtn.innerHTML = '<i class="fas fa-play"></i> Resume';
        } else {
            pauseBtn.innerHTML = '<i class="fas fa-pause"></i> Pause';
        }
      }
    }

    // Update trams
    if (data.trams) {
      this.updateTrams(data.trams);
    }
  }

  updateTrams(trams) {
    const currentTramIds = new Set();

    trams.forEach(tram => {
      currentTramIds.add(tram.id);
      
      if (this.markers[tram.id]) {
        // Update existing marker
        const marker = this.markers[tram.id].marker;
        marker.setLatLng([tram.lat, tram.lon]);
      } else {
        // Create new marker
        const marker = L.marker([tram.lat, tram.lon], {
          icon: L.AwesomeMarkers.icon({
            icon: 'train',
            prefix: 'fa',
            markerColor: 'red',
            iconColor: 'white'
          })
        });
        
        marker.bindTooltip(`Line ${tram.line} - ${tram.id}`, {
          direction: 'top',
          offset: [0, -35]
        });
        
        marker.addTo(this.map);
        this.markers[tram.id] = { marker, data: tram };
      }
    });

    // Remove markers for trams that are no longer active
    Object.keys(this.markers).forEach(tramId => {
      if (!currentTramIds.has(tramId)) {
        this.map.removeLayer(this.markers[tramId].marker);
        delete this.markers[tramId];
      }
    });
  }
}

// Main initialization
window.addEventListener('DOMContentLoaded', async () => {
  try {
    const map = initializeMap();
    console.log('Map initialized');
    
    const stopsLayer = L.featureGroup();
    const overlayMaps = { 'Tram Stops': stopsLayer };

    // Add Voyager tile layer (hardcoded)
    createVoyagerTileLayer().addTo(map);

    // Initialize simulation EARLY to verify it works
    console.log('Initializing simulation controller...');
    const simulation = new SimulationController(map);
    console.log('Connecting simulation...');
    simulation.connect();

    // Load data
    console.log('Loading data...');
    const [routesResult, stopsLoaded] = await Promise.all([
      loadTramRoutes(map, overlayMaps),
      loadTramStops(stopsLayer, map),
    ]);
    console.log('Data loaded', { stopsLoaded, routesResult });

    // Initialize settings panel with line layers
    console.log('Initializing settings panel...');
    initializeSettingsPanel(map, stopsLayer, routesResult.lineLayers, routesResult.lineNumbers);
    console.log('Settings panel initialized');

  } catch (error) {
    console.error('Critical error during initialization:', error);
    alert('Error initializing application: ' + error.message);
  }
});
