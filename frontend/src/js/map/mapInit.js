import { CONFIG } from './mapConfig.js';

// Map initialization
export function initializeMap() {
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
export function createVoyagerTileLayer() {
  return L.tileLayer('https://{s}.basemaps.cartocdn.com/rastertiles/voyager/{z}/{x}/{y}{r}.png', {
    maxZoom: 19,
    attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors &copy; <a href="https://carto.com/attributions">CARTO</a>'
  });
}
