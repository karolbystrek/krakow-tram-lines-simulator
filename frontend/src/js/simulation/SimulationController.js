import { TramMarker } from '../map/tramMarker.js';
import { updateStopMarker } from '../map/stopsLayer.js';
import { SimulationClient } from './SimulationClient.js';
import { SimulationUI } from './SimulationUI.js';

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
    this.ui.update(data);

    if (data.type === 'service_changed') {
        this.updateTrams([]);
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
