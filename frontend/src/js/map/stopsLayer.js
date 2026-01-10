import { CONFIG } from './mapConfig.js';


// Create stop marker
export function createStopMarker(feature, simulationController) {
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
  marker.stopName = props.name || props.stop_name || 'Stop';
  marker.waitingCount = 0;

  marker.bindPopup(() => {
    const container = document.createElement('div');
    container.innerHTML = `<b>${marker.stopName}</b><br>Code: ${props.kod_busman || ''}<br>ID: ${props.id || ''}<br><span id="stop-passengers-${marker.stopId}">Waiting: ${marker.waitingCount}</span>`;

    if (simulationController && simulationController.weightSettings) {
      const btn = document.createElement('button');
      btn.textContent = 'Adjust Weight';
      btn.style.marginTop = '8px';
      btn.style.width = '100%';
      // Simple inline styles to match the dark/light theme neutral look
      btn.style.backgroundColor = '#6c757d';
      btn.style.color = 'white';
      btn.style.border = 'none';
      btn.style.padding = '4px 8px';
      btn.style.borderRadius = '4px';
      btn.style.cursor = 'pointer';

      btn.onclick = () => {
        simulationController.weightSettings.open(marker.stopName);
        marker.closePopup();
      };

      container.appendChild(document.createElement('br'));
      container.appendChild(btn);
    }
    return container;
  }, { maxWidth: 300 });

  marker.bindTooltip(marker.stopName);

  return marker;
}

export function updateStopMarker(marker, waitingCount) {
  if (!marker) return;

  if (marker.waitingCount === waitingCount) {
    return;
  }

  marker.waitingCount = waitingCount;

  let color = CONFIG.STOPS.COLOR;
  let fillColor = CONFIG.STOPS.FILL_COLOR;

  marker.setStyle({
    color: color,
    fillColor: fillColor
  });

  const stopName = marker.stopName || 'Stop';
  marker.setTooltipContent(`${stopName}<br>Waiting: ${waitingCount}`);

  if (marker.isPopupOpen()) {
    const popupElement = document.getElementById(`stop-passengers-${marker.stopId}`);
    if (popupElement) {
      popupElement.textContent = `Waiting: ${waitingCount}`;
    }
  }
}


// Load and display tram stops
export async function loadTramStops(stopsLayer, map, simulationController) {
  try {
    const response = await fetch('/api/stops');
    if (!response.ok) throw new Error(`HTTP error! status: ${response.status}`);

    const data = await response.json();
    if (data.type !== 'FeatureCollection' || !data.features) {
      throw new Error('Invalid GeoJSON format');
    }

    data.features.forEach(feature => {
      const marker = createStopMarker(feature, simulationController);
      marker.addTo(stopsLayer);

      const kod_busman = feature.properties.kod_busman || '';
      const id = feature.properties.id || '';
      const stopId = kod_busman || id;

      if (stopId && simulationController) {
        simulationController.stopMarkers[stopId] = marker;
        if (kod_busman && id && kod_busman !== id) {
          simulationController.stopMarkers[id] = marker;
        }
      }
    });

    stopsLayer.addTo(map);

    return true;
  } catch (error) {
    return false;
  }
}
