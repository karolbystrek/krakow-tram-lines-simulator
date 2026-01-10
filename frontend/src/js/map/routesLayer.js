import { CONFIG } from './mapConfig.js';


// Sort line numbers (numeric if possible, otherwise alphabetical)
function sortLineNumbers(a, b) {
  const aNum = parseInt(a);
  const bNum = parseInt(b);
  if (!isNaN(aNum) && !isNaN(bNum)) {
    return aNum - bNum;
  }
  return a.localeCompare(b);
}

// Create route polyline
function createRoutePolyline(feature, lineNumber, simulationController) {
  const coords = feature.geometry.coordinates;
  const latLngs = coords.map(([lon, lat]) => [lat, lon]);

  const polyline = L.polyline(latLngs, {
    color: CONFIG.ROUTES.COLOR,
    weight: CONFIG.ROUTES.WEIGHT,
    opacity: CONFIG.ROUTES.OPACITY
  });

  polyline.bindPopup(() => {
    const container = document.createElement('div');
    container.innerHTML = `<b>Tram Line ${lineNumber}</b>`;

    if (simulationController && simulationController.lineWeightSettings) {
      const btn = document.createElement('button');
      btn.textContent = 'Adjust Weight';
      btn.style.marginTop = '8px';
      btn.style.width = '100%';
      btn.style.backgroundColor = '#6c757d';
      btn.style.color = 'white';
      btn.style.border = 'none';
      btn.style.padding = '4px 8px';
      btn.style.borderRadius = '4px';
      btn.style.cursor = 'pointer';

      btn.onclick = () => {
        simulationController.lineWeightSettings.open(lineNumber);
        polyline.closePopup();
      };

      container.appendChild(document.createElement('br'));
      container.appendChild(btn);
    }
    return container;
  }, { maxWidth: 300 });

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

// Load and display tram routes
export async function loadTramRoutes(map, overlayMaps, simulationController) {
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
        createRoutePolyline(feature, lineNumber, simulationController).addTo(lineLayer);
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

