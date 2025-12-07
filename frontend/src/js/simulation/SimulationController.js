import { TramMarker } from '../map/tramMarker.js';
import { debounce } from '../utils/debounce.js';
import { getDefaultService } from '../utils/time.js';
import { updateStopMarker } from '../map/stopsLayer.js';


// Simulation Controller
export class SimulationController {
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