import { debounce } from '../utils/debounce.js';

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

function createSliderHTML(id, label, min, max, value, step = 1) {
    return `
      <div class="settings-item settings-slider-item">
          <div class="slider-header">
            <label for="${id}">${label}</label>
            <span id="${id}-value" class="slider-value">${value}</span>
          </div>
          <input type="range" id="${id}" min="${min}" max="${max}" value="${value}" step="${step}" class="slider-input">
      </div>
    `;
}

function formatTime(minutes) {
    const h = Math.floor(minutes / 60);
    const m = Math.floor(minutes % 60);
    return `${h.toString().padStart(2, '0')}:${m.toString().padStart(2, '0')}`;
}


// Initialize settings panel
export function initializeSettingsPanel(map, stopsLayer, lineLayers, lineNumbers, simulation) {
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

  // --- Line Controls ---
  const linesHeader = document.createElement('h3');
  linesHeader.className = 'settings-section-header';
  linesHeader.textContent = 'Tram Lines';
  content.appendChild(linesHeader);

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
