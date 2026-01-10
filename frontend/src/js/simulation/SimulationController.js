import { TramMarker } from '../map/tramMarker.js';
import { updateStopMarker, loadTramStops } from '../map/stopsLayer.js';
import { SimulationClient } from './SimulationClient.js';
import { SimulationUI } from './SimulationUI.js';
import { StatisticsUI } from '../ui/stats.js';
import { PassengerGenerationModal } from '../ui/PassengerGenerationModal.js';
import { WeightSettings } from '../ui/WeightSettings.js';
import { LineWeightSettings } from '../ui/LineWeightSettings.js';

export class SimulationController {
  constructor(map) {
    this.map = map;
    this.trams = {}; // tramId -> TramMarker
    this.stopMarkers = {}; // stopId -> marker
    this.hiddenLines = new Set();
    
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const wsUrl = `${protocol}//${window.location.host}/ws/simulation`;
    
    this.client = new SimulationClient(
      wsUrl,
      this.handleUpdate.bind(this),
      this.onConnect.bind(this),
      this.onDisconnect.bind(this),
      this.onError.bind(this)
    );

    this.ui = new SimulationUI(this.client);
    this.statsUI = new StatisticsUI();
    this.generationModal = new PassengerGenerationModal(this.client, this);
    this.weightSettings = new WeightSettings(this.client, this);
    this.lineWeightSettings = new LineWeightSettings(this.client, this);
    this.stopsLayer = null;
    
    this.isPaused = false;
    this.wasRunningBeforeStats = false;
    
    this.setupStatistics();
    this.setupConfiguration();
  }

  setupConfiguration() {
    const configToggle = document.getElementById('config-toggle');
    const configContent = document.getElementById('config-content');
    
    if (configToggle && configContent) {
        configToggle.addEventListener('click', () => {
            configContent.classList.toggle('settings-content-open');
            configToggle.classList.toggle('settings-toggle-btn-active');
        });

        document.addEventListener('keydown', (e) => {
            if (e.key === 'Escape' && configContent.classList.contains('settings-content-open')) {
                configContent.classList.remove('settings-content-open');
                configToggle.classList.remove('settings-toggle-btn-active');
            }
        });

        document.addEventListener('click', (e) => {
            if (configContent.classList.contains('settings-content-open')) {
                if (!configContent.contains(e.target) && !configToggle.contains(e.target)) {
                    configContent.classList.remove('settings-content-open');
                    configToggle.classList.remove('settings-toggle-btn-active');
                }
            }
        });
    }

    const btnDemand = document.getElementById('btn-config-demand');
    if (btnDemand) {
        btnDemand.addEventListener('click', () => {
            if (this.generationModal) this.generationModal.open();
            configContent.classList.remove('settings-content-open');
            configToggle.classList.remove('settings-toggle-btn-active');
        });
    }

    const btnWeights = document.getElementById('btn-config-weights');
    if (btnWeights) {
        btnWeights.addEventListener('click', () => {
            if (this.weightSettings) this.weightSettings.open();
            configContent.classList.remove('settings-content-open');
            configToggle.classList.remove('settings-toggle-btn-active');
        });
    }

    const btnLineWeights = document.getElementById('btn-config-line-weights');
    if (btnLineWeights) {
        btnLineWeights.addEventListener('click', () => {
            if (this.lineWeightSettings) this.lineWeightSettings.open();
            configContent.classList.remove('settings-content-open');
            configToggle.classList.remove('settings-toggle-btn-active');
        });
    }
  }

  setupStatistics() {
    this.statsBtn = document.getElementById('btn-stats');
    if (this.statsBtn) {
        this.statsBtn.addEventListener('click', () => {
             this.openStatistics();
        });
    }

    this.statsUI.onClose = () => {
        this.closeStatistics();
    };
  }

  openStatistics() {
    this.wasRunningBeforeStats = !this.isPaused; 
    
    if (this.wasRunningBeforeStats) {
        this.client.sendCommand('pause');
    }

    this.statsUI.loadDetailedStats();
  }

  closeStatistics() {
    // Resume if we were running
    if (this.wasRunningBeforeStats) {
        this.client.sendCommand('resume');
    }
  }

  connect() {
    this.client.connect();
  }

  onConnect() {
    this.ui.setConnected(true);
  }

  onDisconnect() {
    this.ui.setConnected(false);
  }

  onError(error) {
    console.error('Simulation error:', error);
  }

  handleUpdate(data) {
    // Update local pause state tracking
    if (data.status) {
        this.isPaused = data.status === 'paused';
    }

    if ((data.type === 'simulation_ended' || data.type === 'statistics_update') && data.statistics) {
        console.log("Received statistics. Showing UI.");
        this.statsUI.show(data.statistics);
        this.statsUI.loadDetailedStats();
        if (data.type === 'simulation_ended') {
            this.wasRunningBeforeStats = false; 
        }
        return;
    }

    if (data.type === 'generation_params') {
        if (this.generationModal) {
            this.generationModal.setParams(data.params);
        }
        return;
    }

    this.ui.update(data);

    if (data.type === 'service_changed') {
        this.updateTrams([]);
        if (this.stopsLayer) {
            console.log('Service changed, refreshing stops...');
            this.stopsLayer.clearLayers();
            this.stopMarkers = {};
            loadTramStops(this.stopsLayer, this.map, this);
        }
        return;
    }

    if (data.trams) {
      this.updateTrams(data.trams);
    }

    if (data.stop_states) {
      this.updateStopStates(data.stop_states);
    }
  }

  updateStopStates(stopStates) {
    for (const [stopId, stop] of Object.entries(stopStates)) {
      const marker = this.stopMarkers[stopId];
      if (marker) {
        updateStopMarker(marker, stop.waiting_count || 0);
      }
    }
  }

  updateTrams(tramsData) {
    const currentTramIds = new Set();
    
    for (const tramData of tramsData) {
      currentTramIds.add(tramData.id);

      if (this.trams[tramData.id]) {
        this.trams[tramData.id].updateTarget(tramData);
      } else {
        this.createTram(tramData);
      }
    }

    for (const tramId in this.trams) {
      if (!currentTramIds.has(tramId)) {
        this.trams[tramId].remove();
        delete this.trams[tramId];
      }
    }
  }

  createTram(tramData) {
    const tram = new TramMarker(tramData.id, tramData, this.map);
    this.trams[tramData.id] = tram;

    if (!this.isLineVisible(tramData.line)) {
      tram.hide();
    }
  }

  setLineVisibility(lineNumber, isVisible) {
    if (isVisible) {
      this.hiddenLines.delete(lineNumber);
    } else {
      this.hiddenLines.add(lineNumber);
    }

    Object.values(this.trams).forEach(tram => {
      if (tram.data.line === lineNumber) {
        isVisible ? tram.show() : tram.hide();
      }
    });
  }

  isLineVisible(lineNumber) {
    return !this.hiddenLines.has(lineNumber);
  }
}
