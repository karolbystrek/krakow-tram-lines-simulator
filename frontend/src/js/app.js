import {loadTramStops} from "./map/stopsLayer.js";
import { loadTramRoutes } from './map/routesLayer.js';
import { initializeSettingsPanel } from './ui/settingsPanel.js';
import { SimulationController } from './simulation/SimulationController.js';
import { initializeMap, createVoyagerTileLayer } from './map/mapInit.js';

window.addEventListener('DOMContentLoaded', async () => {
  try {
    const map = initializeMap();

    const stopsLayer = L.featureGroup();
    const overlayMaps = { 'Tram Stops': stopsLayer };

    createVoyagerTileLayer().addTo(map);

    const simulation = new SimulationController(map);
    simulation.stopsLayer = stopsLayer;
    simulation.connect();

    const [routesResult, stopsLoaded] = await Promise.all([
      loadTramRoutes(map, overlayMaps, simulation),
      loadTramStops(stopsLayer, map, simulation),
    ]);

    // Ensure stops layer is visible (checkbox is checked by default)
    if (stopsLoaded && !map.hasLayer(stopsLayer)) {
      console.log('Adding stops layer to map (should be visible)');
      stopsLayer.addTo(map);
    }

    initializeSettingsPanel(map, stopsLayer, routesResult.lineLayers, routesResult.lineNumbers, simulation);
  } catch (error) {
    alert('Error initializing application: ' + error.message);
  }
});
