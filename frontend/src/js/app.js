import {loadTramStops} from "./map/stopsLayer.js";
import { loadTramRoutes } from './map/routesLayer.js';
import { initializeSettingsPanel } from './ui/settingsPanel.js';
import { SimulationController } from './simulation/SimulationController.js';
import { initializeMap, createVoyagerTileLayer } from './map/mapInit.js';

window.addEventListener('DOMContentLoaded', async () => {
  const map = initializeMap();
  createVoyagerTileLayer().addTo(map);

  const stopsLayer = L.featureGroup();
  const overlayMaps = {};

  const simulation = new SimulationController(map);
  simulation.connect();

  const routesResult = await loadTramRoutes(map, overlayMaps);
  await loadTramStops(stopsLayer, map, simulation);

  stopsLayer.addTo(map);

  initializeSettingsPanel(
    map,
    stopsLayer,
    routesResult.lineLayers,
    routesResult.lineNumbers,
    simulation
  );
});

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
