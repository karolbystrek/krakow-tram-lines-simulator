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

  // Store stop ID for later updates
  marker.stopId = props.kod_busman || props.id || '';
  marker.waitingCount = 0;

  const popupContent = `<b>${props.name || props.stop_name}</b><br>Code: ${props.kod_busman || ''}<br>ID: ${props.id || ''}<br><span id="stop-passengers-${marker.stopId}">Waiting: 0</span>`;
  marker.bindPopup(popupContent, { maxWidth: 300 });
  marker.bindTooltip(props.name || props.stop_name);

  return marker;
}

// Update stop marker with passenger data
function updateStopMarker(marker, waitingCount) {
  if (!marker) return;
  
  marker.waitingCount = waitingCount;
  
  // Update color based on waiting passengers
  let color = CONFIG.STOPS.COLOR;
  let fillColor = CONFIG.STOPS.FILL_COLOR;
  
  if (waitingCount > 20) {
    color = '#FF0000';  // Red for high passenger count
    fillColor = '#FFCCCC';
  } else if (waitingCount > 10) {
    color = '#FF8800';  // Orange for medium-high
    fillColor = '#FFE0CC';
  } else if (waitingCount > 5) {
    color = '#FFAA00';  // Yellow for medium
    fillColor = '#FFF4CC';
  }
  
  marker.setStyle({
    color: color,
    fillColor: fillColor
  });
  
  // Update tooltip
  const stopName = marker.getTooltip() ? marker.getTooltip().getContent() : 'Stop';
  marker.setTooltipContent(`${stopName}<br>Waiting: ${waitingCount}`);
  
  // Update popup if open
  if (marker.isPopupOpen()) {
    const popupElement = document.getElementById(`stop-passengers-${marker.stopId}`);
    if (popupElement) {
      popupElement.textContent = `Waiting: ${waitingCount}`;
    }
  }
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

// Get current weekday in Poland
function getPolandWeekday() {
  const date = new Date();
  const options = { timeZone: 'Europe/Warsaw', weekday: 'long' };
  const dayName = new Intl.DateTimeFormat('en-US', options).format(date);
  return dayName;
}

// Get default service ID based on Poland weekday
function getDefaultService() {
  const day = getPolandWeekday();
  switch (day) {
    case 'Monday':
    case 'Tuesday':
    case 'Wednesday':
      return 'service_1';
    case 'Thursday':
      return 'service_5';
    case 'Friday':
      return 'service_4';
    case 'Saturday':
      return 'service_2';
    case 'Sunday':
      return 'service_3';
    default:
      return 'service_1';
  }
}

// Load and display tram stops
async function loadTramStops(stopsLayer, map, simulationController) {
  try {
    const response = await fetch('/api/stops');
    if (!response.ok) throw new Error(`HTTP error! status: ${response.status}`);

    const data = await response.json();
    if (data.type !== 'FeatureCollection' || !data.features) {
      throw new Error('Invalid GeoJSON format');
    }

    data.features.forEach(feature => {
      const marker = createStopMarker(feature);
      marker.addTo(stopsLayer);
      
      // Store marker in simulation controller for updates
      // Try multiple ID fields to ensure we can match with backend
      const kod_busman = feature.properties.kod_busman || '';
      const id = feature.properties.id || '';
      const stopId = kod_busman || id;
      
      if (stopId && simulationController) {
        simulationController.stopMarkers[stopId] = marker;
        // Also store by both IDs if they differ
        if (kod_busman && id && kod_busman !== id) {
          simulationController.stopMarkers[id] = marker;
        }
      }
    });

    stopsLayer.addTo(map);
    console.log(`Loaded ${data.features.length} tram stops`);
    console.log(`Stored ${Object.keys(simulationController?.stopMarkers || {}).length} stop markers for updates`);

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
function initializeSettingsPanel(map, stopsLayer, lineLayers, lineNumbers, simulation) {
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
        simulation.setLineVisibility(lineNumber, true);
      } else {
        if (map.hasLayer(lineLayer)) {
          map.removeLayer(lineLayer);
        }
        simulation.setLineVisibility(lineNumber, false);
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
        simulation.setLineVisibility(lineNumber, true);
      } else {
        if (map.hasLayer(lineLayer)) {
          map.removeLayer(lineLayer);
        }
        simulation.setLineVisibility(lineNumber, false);
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

// Tram Marker with interpolation
class TramMarker {
  constructor(id, data, map) {
    this.id = id;
    this.map = map;
    this.data = data;
    
    // Get occupancy for color coding
    const occupancy = data.occupancy_percent || 0;
    const markerColor = this.getOccupancyColor(occupancy);
    
    // Create Leaflet marker
    this.marker = L.marker([data.lat, data.lon], {
      icon: L.AwesomeMarkers.icon({
        icon: 'train',
        prefix: 'fa',
        markerColor: markerColor,
        iconColor: 'white'
      })
    });

    // this.marker.bindTooltip(`Line ${data.line} - ${id}`, {
    //   direction: 'top',
    //   offset: [0, -35]
    // });

    this.data.occupancy = data.occupancy;
    this.marker.bindTooltip(`<b>Line:</b> ${this.data.line} - ${id}<br>
                             <b>Occupancy:</b> ${this.data.occupancy}`, {
      direction: 'top',
      offset: [0, -35]
    });

    this.marker.addTo(map);

    // Interpolation state
    this.currentLat = data.lat;
    this.currentLon = data.lon;
    this.targetLat = data.lat;
    this.targetLon = data.lon;
    this.lastUpdate = performance.now();
    this.animationDuration = 1000; // Default fallback duration
    this.animating = false;
  }
  
  getOccupancyColor(occupancyPercent) {
    // Color code by occupancy: green (empty) -> yellow (half) -> red (full)
    if (occupancyPercent < 30) {
      return 'green';  // Empty to low
    } else if (occupancyPercent < 60) {
      return 'blue';  // Low to medium
    } else if (occupancyPercent < 80) {
      return 'orange';  // Medium to high
    } else {
      return 'red';  // High to full
    }
  }
  
  updateTooltip(data) {
    const occupancy = data.occupancy_percent || 0;
    const occupancyText = data.occupancy !== undefined 
      ? `${data.occupancy}/${data.max_capacity || 200} (${occupancy.toFixed(1)}%)`
      : 'N/A';
    
    this.marker.bindTooltip(
      `Line ${data.line} - ${this.id}<br>Occupancy: ${occupancyText}`,
      {
        direction: 'top',
        offset: [0, -35]
      }
    );
  }

  updateTarget(data) {
    const now = performance.now();
    // Calculate time since last update to adjust animation duration dynamically
    // This makes it modular: if server sends every 100ms, duration becomes ~100ms.
    // If server sends every 1s, duration becomes ~1s.
    const timeDelta = now - this.lastUpdate;
    
    // Smooth out jitter by averaging or clamping? 
    // For simplicity, just use the delta, but clamp it to reasonable bounds to avoid jumps on pauses
    if (timeDelta > 0 && timeDelta < 5000) {
        this.animationDuration = timeDelta;
    }
    
    this.lastUpdate = now;
    this.startLat = this.currentLat;
    this.startLon = this.currentLon;
    this.targetLat = data.lat;
    this.targetLon = data.lon;
    this.startTime = now;

    this.data.occupancy = data.occupancy;
            this.marker.setTooltipContent(`
                <b>Line:</b> ${this.data.line} - ${this.id}<br>
                <b>Occupancy:</b> ${this.data.occupancy}
            `);

    if (!this.animating) {
      this.animate();
    }
  }

  animate() {
    this.animating = true;
    
    requestAnimationFrame((timestamp) => {
      const now = performance.now();
      const elapsed = now - this.startTime;
      const progress = Math.min(elapsed / this.animationDuration, 1.0);

      // Linear interpolation
      this.currentLat = this.startLat + (this.targetLat - this.startLat) * progress;
      this.currentLon = this.startLon + (this.targetLon - this.startLon) * progress;

      this.marker.setLatLng([this.currentLat, this.currentLon]);

      if (progress < 1.0) {
        this.animate();
      } else {
        this.animating = false;
      }
    });
  }

  remove() {
    this.map.removeLayer(this.marker);
  }

  hide() {
    if (this.map.hasLayer(this.marker)) {
      this.map.removeLayer(this.marker);
    }
  }

  show() {
    if (!this.map.hasLayer(this.marker)) {
      this.marker.addTo(this.map);
    }
  }
}

// Debounce utility
function debounce(func, wait) {
  let timeout;
  return function executedFunction(...args) {
    const later = () => {
      clearTimeout(timeout);
      func(...args);
    };
    clearTimeout(timeout);
    timeout = setTimeout(later, wait);
  };
}

// Simulation Controller
class SimulationController {
  constructor(map) {
    this.map = map;
    this.trams = {}; // tramId -> TramMarker instance
    this.stopMarkers = {}; // stopId -> marker instance
    this.ws = null;
    this.timeDisplay = null;
    this.timeSlider = null;
    this.isDraggingSlider = false;
    this.hiddenLines = new Set(); // Track which lines are currently hidden
    
    this.timeDisplay = document.getElementById('simulation-time');
    this.timeSlider = document.getElementById('time-slider');
    
    if (!this.timeDisplay) {
        console.error('Time display element not found!');
    } else {
        this.timeDisplay.textContent = 'Connecting...';
    }

    if (this.timeSlider) {
        this.initializeSlider();
    }
  }

  initializeSlider() {
      const debouncedSetTime = debounce((time) => {
          this.sendCommand('set_time', { time: time });
      }, 100); // 100ms debounce

      this.timeSlider.addEventListener('input', (e) => {
          this.isDraggingSlider = true;
          const time = parseFloat(e.target.value);
          
          // Update time display immediately for better UX
          const hours = Math.floor(time / 60);
          const minutes = Math.floor(time % 60);
          this.timeDisplay.textContent = `${hours.toString().padStart(2, '0')}:${minutes.toString().padStart(2, '0')}:00`;
          
          debouncedSetTime(time);
      });

      this.timeSlider.addEventListener('change', (e) => {
          this.isDraggingSlider = false;
          // Ensure final value is sent
          this.sendCommand('set_time', { time: parseFloat(e.target.value) });
      });
      
      // Handle mouse up/leave to clear dragging state just in case
      this.timeSlider.addEventListener('mouseup', () => { this.isDraggingSlider = false; });
      this.timeSlider.addEventListener('mouseleave', () => { this.isDraggingSlider = false; });
      this.timeSlider.addEventListener('touchend', () => { this.isDraggingSlider = false; });
  }

  // Set line visibility
  setLineVisibility(lineNumber, isVisible) {
    if (isVisible) {
      this.hiddenLines.delete(lineNumber);
    } else {
      this.hiddenLines.add(lineNumber);
    }
    
    // Update existing tram markers for this line
    Object.values(this.trams).forEach(tram => {
      if (tram.data.line === lineNumber) {
        if (isVisible) {
          tram.show();
        } else {
          tram.hide();
        }
      }
    });
  }

  // Check if a line is visible
  isLineVisible(lineNumber) {
    return !this.hiddenLines.has(lineNumber);
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
        if (data.type === 'service_changed') {
            console.log('Service changed to:', data.service_id);
            // Optional: Show a notification or just let the time update handle it
        } else {
            this.handleUpdate(data);
        }
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
      const newPauseBtn = pauseBtn.cloneNode(true);
      pauseBtn.parentNode.replaceChild(newPauseBtn, pauseBtn);
      
      newPauseBtn.addEventListener('click', () => {
        const isPaused = newPauseBtn.textContent.includes('Resume');
        const command = isPaused ? 'resume' : 'pause';
        this.sendCommand(command);
      });
    }

    if (restartBtn) {
      const newRestartBtn = restartBtn.cloneNode(true);
      restartBtn.parentNode.replaceChild(newRestartBtn, restartBtn);

      newRestartBtn.addEventListener('click', () => {
        this.sendCommand('restart');
      });
    }

    // Service Selector
    const serviceSelector = document.getElementById('service-selector');
    if (serviceSelector) {
        // Set default value based on Poland time
        const defaultService = getDefaultService();
        serviceSelector.value = defaultService;
        
        serviceSelector.addEventListener('change', (e) => {
            const serviceId = e.target.value;
            console.log(`Changing service to ${serviceId}`);
            this.sendCommand('change_service', { service_id: serviceId });
            
            // Show loading state
            if (this.timeDisplay) {
                this.timeDisplay.textContent = 'Loading...';
            }
            
            // Clear existing trams immediately to avoid confusion
            this.updateTrams([]);
        });
    }
  }

  sendCommand(command, data = {}) {
    if (this.ws && this.ws.readyState === WebSocket.OPEN) {
      console.log('Sending command:', command, data);
      this.ws.send(JSON.stringify({ command, ...data }));
    } else {
      console.warn('WebSocket not connected, cannot send command:', command);
    }
  }

  handleUpdate(data) {
    // Update time
    if (data.time) {
      this.timeDisplay.textContent = `${data.time.time_str}`;
      
      // Update slider if it exists and user is not dragging it
      if (this.timeSlider) {
          // Update range if changed (e.g. on service reload)
          if (data.time.start_time_minutes !== undefined && data.time.end_time_minutes !== undefined) {
              if (this.timeSlider.min != data.time.start_time_minutes) this.timeSlider.min = data.time.start_time_minutes;
              if (this.timeSlider.max != data.time.end_time_minutes) this.timeSlider.max = data.time.end_time_minutes;
          }
          
          if (!this.isDraggingSlider) {
              this.timeSlider.value = data.time.time_minutes;
          }
      }
      
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
    
    // Update stop states with passenger data
    if (data.stop_states) {
      this.updateStopStates(data.stop_states);
    }
    
    // Log passenger data for debugging (occasionally)
    if (data.passengers && Math.random() < 0.01) {
      console.log(`Passengers - Waiting: ${data.passengers.total_waiting}, On trams: ${data.passengers.total_on_trams}`);
    }
  }
  
  updateStopStates(stopStates) {
    // Update each stop marker with waiting passenger count
    let updatedCount = 0;
    for (const [stopId, stopData] of Object.entries(stopStates)) {
      const marker = this.stopMarkers[stopId];
      if (marker) {
        updateStopMarker(marker, stopData.waiting_count || 0);
        updatedCount++;
      }
    }
    // Log if we have stop states but no matching markers
    if (Object.keys(stopStates).length > 0 && updatedCount === 0) {
      console.warn(`Stop states received but no markers matched. Stop IDs in states: ${Object.keys(stopStates).slice(0, 5).join(', ')}...`);
      console.warn(`Available marker IDs: ${Object.keys(this.stopMarkers).slice(0, 5).join(', ')}...`);
    }
  }

  updateTrams(tramsData) {
    const currentTramIds = new Set();

    tramsData.forEach(tramData => {
      currentTramIds.add(tramData.id);
      
      if (this.trams[tramData.id]) {
        // Update existing tram target
        this.trams[tramData.id].updateTarget(tramData);
      } else {
        // Create new tram and apply line visibility
        const tram = new TramMarker(tramData.id, tramData, this.map);
        this.trams[tramData.id] = tram;
        
        // Hide if the line is currently hidden
        if (!this.isLineVisible(tramData.line)) {
          tram.hide();
        }
      }
    });

    // Remove markers for trams that are no longer active
    Object.keys(this.trams).forEach(tramId => {
      if (!currentTramIds.has(tramId)) {
        this.trams[tramId].remove();
        delete this.trams[tramId];
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
      loadTramStops(stopsLayer, map, simulation),
    ]);
    console.log('Data loaded', { stopsLoaded, routesResult });
    
    // Ensure stops layer is visible (checkbox is checked by default)
    if (stopsLoaded && !map.hasLayer(stopsLayer)) {
      console.log('Adding stops layer to map (should be visible)');
      stopsLayer.addTo(map);
    }
    
    // Log stop markers for debugging
    console.log(`Stop markers stored: ${Object.keys(simulation.stopMarkers).length}`);

    // Initialize settings panel with line layers
    console.log('Initializing settings panel...');
    initializeSettingsPanel(map, stopsLayer, routesResult.lineLayers, routesResult.lineNumbers, simulation);
    console.log('Settings panel initialized');

  } catch (error) {
    console.error('Critical error during initialization:', error);
    alert('Error initializing application: ' + error.message);
  }
});
