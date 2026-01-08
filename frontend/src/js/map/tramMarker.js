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
    this.currentOccupancyLevel = -1;

    const occupancy = data.occupancy || 0;
    const occupancyIcon = this.getOccupancyIcon(occupancy);
    this.currentOccupancyLevel = this.getOccupancyLevel(occupancy);
    
    this.marker = L.marker([data.lat, data.lon], { icon: occupancyIcon });

    this.data.occupancy = data.occupancy;
    this.marker.bindTooltip(this.getTooltipContent(data), {
      direction: 'top',
      offset: [0, -35]
    });

    this.marker.addTo(map);

    this.currentLat = data.lat;
    this.currentLon = data.lon;
    this.targetLat = data.lat;
    this.targetLon = data.lon;
    this.lastUpdate = performance.now();
    this.animationDuration = 1000;
    this.animating = false;
  }

  getOccupancyLevel(occupancy) {
    if (occupancy < 50) return 0;
    if (occupancy < 100) return 1;
    if (occupancy < 150) return 2;
    return 3;
  }

  getOccupancyIcon(occupancyNumber) {
    const level = this.getOccupancyLevel(occupancyNumber);
    switch (level) {
      case 0: return icons.green;
      case 1: return icons.orange;
      case 2: return icons.red;
      default: return icons.darkred;
    }
  }

  getTooltipContent(data) {
    const occupancy = data.occupancy || 0;
    return `<b>Line:</b> ${data.line} - ${this.id}<br><b>Occupancy:</b> ${occupancy}`;
  }

  updateTarget(data) {
    const now = performance.now();
    const timeDelta = now - this.lastUpdate;

    if (timeDelta > 0 && timeDelta < 5000) {
        this.animationDuration = timeDelta;
    }

    this.lastUpdate = now;
    this.startLat = this.currentLat;
    this.startLon = this.currentLon;
    this.targetLat = data.lat;
    this.targetLon = data.lon;
    this.startTime = now;

    if (this.data.occupancy !== data.occupancy) {
        this.data.occupancy = data.occupancy;
        this.marker.setTooltipContent(this.getTooltipContent(data));
        
        const newLevel = this.getOccupancyLevel(data.occupancy);
        if (newLevel !== this.currentOccupancyLevel) {
            this.currentOccupancyLevel = newLevel;
            this.marker.setIcon(this.getOccupancyIcon(data.occupancy));
        }
    }

    if (!this.animating) {
      this.animate();
    }
  }

  animate() {
    this.animating = true;

    requestAnimationFrame(() => {
      const now = performance.now();
      const elapsed = now - this.startTime;
      const progress = Math.min(elapsed / this.animationDuration, 1.0);

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
