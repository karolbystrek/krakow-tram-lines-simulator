const icons = {
  green: L.AwesomeMarkers.icon({
    icon: 'train',
    prefix: 'fa',
    markerColor: 'green',
    iconColor: 'white'
  }),
  orange: L.AwesomeMarkers.icon({
    icon: 'train',
    prefix: 'fa',
    markerColor: 'orange',
    iconColor: 'white'
  }),
  red: L.AwesomeMarkers.icon({
    icon: 'train',
    prefix: 'fa',
    markerColor: 'red',
    iconColor: 'white'
  }),
  darkred: L.AwesomeMarkers.icon({
    icon: 'train',
    prefix: 'fa',
    markerColor: 'darkred',
    iconColor: 'white'
  })
};



export class TramMarker {
  constructor(id, data, map) {
    this.id = id;
    this.map = map;
    this.data = data;

    // Update marker color if occupancy changed
    const occupancy = data.occupancy || 0;
    const occupancyIcon = this.getOccupancyIcon(occupancy);

    // Create Leaflet marker
    this.marker = L.marker([data.lat, data.lon], occupancyIcon);

    this.marker.bindTooltip(`Line ${data.line} - ${id}`, {
      direction: 'top',
      offset: [0, -35]
    });

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

  getOccupancyIcon(occupancyNumber) {
  if (occupancyNumber < 50) {
    return icons.green;
  } else if (occupancyNumber < 100) {
    return icons.orange;
  } else if (occupancyNumber < 150) {
    return icons.red;
  } else {
    return icons.darkred;
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

    // Create Leaflet marker
    this.marker.setIcon(this.getOccupancyIcon(this.data.occupancy))

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
